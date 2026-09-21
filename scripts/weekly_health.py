#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 結果マガ 週次ヘルスチェック+素材自動補充(2026-09-21 小柳さん指示「極限まで自動化」)

いままでツヅルがチャットで毎週月曜に手作業でやっていた点検を機械化する:
 1. X体験共有の投稿欠落点検(直近7日の月・木がログにあるか=ニドナシ#19の常設工程)
 2. 素材キューの残量点検+残量2以下ならAIで自動補充(実際に起きたこと=KPIメモと
    ニドナシ台帳の直近行だけを素材源にし、taikenと同じガードで検査)
 3. 公開待ち記事の滞留点検(下書き済み・未公開が3日超)
 4. KPI台帳の鮮度点検(最終記録が8日超)
 5. noteの公開情報(記事数・スキ数)をAPIから取得(ビュー・売上は管理画面のみ=取得不可)
結果はLINEで週次ヘルス通知として届く(毎週月曜に必ず1通届く=通知経路の生存確認も兼ねる)。

使い方: python scripts/weekly_health.py
出力: report=<LINE本文ファイルパス> / replenished=<追加素材数>
"""
import json
import os
import re
import sys
import urllib.request
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_x_taiken as gx

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = gx.BASE
NIDONASHI_PATH = os.path.join(BASE, "docs", "結果マガ_ニドナシプロンプト.md")
NOTE_API = "https://note.com/api/v2/creators/kekka_mag/contents?kind=note&page=1"


def check_taiken_gaps():
    """直近7日の月(0)・木(3)にtaiken投稿があるか(投稿日はJST)。"""
    log = gx.load_json(gx.LOG_PATH, {"posts": []})
    posted = {p.get("date") for p in log.get("posts", [])}
    today = gx.today_jst()
    missing = []
    for d in range(1, 8):
        day = today - timedelta(days=d)
        if day.weekday() in (0, 3) and day.isoformat() not in posted:
            missing.append(day.isoformat())
    return sorted(missing)


def material_state():
    data = gx.load_json(gx.MATERIAL_PATH, {"queue": []})
    unused = [m for m in data.get("queue", []) if not m.get("used")]
    return data, unused


def check_awaiting():
    topics = gx.load_json(gx.TOPICS_PATH, {"queue": []}).get("queue", [])
    today = gx.today_jst()
    out = []
    for t in topics:
        if t.get("published_url") or not t.get("drafted_at"):
            continue
        try:
            from datetime import date
            days = (today - date.fromisoformat(t["drafted_at"])).days
        except Exception:
            continue
        if days >= 3:
            out.append(f"{t.get('id')}({days}日)")
    return out


def kpi_freshness():
    kpi = gx.load_json(gx.KPI_PATH, {})
    weeks = kpi.get("weeks", [])
    if not weeks:
        return None, 999
    last = weeks[-1].get("date", "")
    try:
        from datetime import date
        age = (gx.today_jst() - date.fromisoformat(last)).days
    except Exception:
        age = 999
    return last, age


def fetch_note_public():
    """note公開APIから記事数とスキ合計を取る(失敗しても点検は続行)。"""
    try:
        req = urllib.request.Request(NOTE_API, headers={"User-Agent": "hojo-hq-kekka-health/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        notes = data.get("data", {}).get("contents", [])
        likes = sum(n.get("likeCount", 0) for n in notes)
        return len(notes), likes
    except Exception as e:
        print(f"::warning::note公開APIの取得に失敗: {e}", file=sys.stderr)
        return None, None


def replenish_materials(data, unused):
    """素材残量2以下なら、KPIメモ+ニドナシ台帳の直近行から2件を自動生成して補充する。
    素材源のテキストに無い数字は書けない(taikenと同じガード)。"""
    if len(unused) > 2:
        return 0
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("::warning::素材残量が少ないがANTHROPIC_API_KEY未設定のため補充できず", file=sys.stderr)
        return 0
    import anthropic

    kpi = gx.load_json(gx.KPI_PATH, {})
    memos = "\n".join(w.get("memo", "") for w in kpi.get("weeks", [])[-2:])
    try:
        rows = [l for l in open(NIDONASHI_PATH, encoding="utf-8").read().splitlines() if l.startswith("| 2")]
        ledger_tail = "\n".join(rows[-3:])
    except Exception:
        ledger_tail = ""
    source = memos + "\n" + ledger_tail
    facts = gx.build_facts()
    allowed = gx.allowed_numbers(facts, source)
    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""「AIだけでnoteマガジンを運営する実験」のX体験共有投稿の素材メモを2件書く。
素材は下の実記録(週次メモ・運営ミス台帳)に書かれている出来事・実測値だけから作る。
創作・推測・ここに無い数字は禁止。1件80〜140字・事実の記述のみ(投稿文はあとで別のAIが書く)。

# 実記録
{source}

# 出力形式(JSON配列のみ)
["素材1の本文", "素材2の本文"]"""
    try:
        msg = client.messages.create(model="claude-sonnet-5", max_tokens=1000,
                                     messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        m = re.search(r"\[.*\]", text, flags=re.S)
        cands = json.loads(m.group(0)) if m else []
    except Exception as e:
        print(f"::warning::素材補充の生成に失敗: {e}", file=sys.stderr)
        return 0
    added = 0
    next_no = len(data.get("queue", [])) + 1
    for cand in cands[:2]:
        if not isinstance(cand, str):
            continue
        problems = [w for w in gx.BANNED if w in cand]
        problems += [ng for ng in ("小柳", "ミカタ", "ALLGROUP", "GLOW", "フクギイロ", "嶺井") if ng in cand]
        problems += gx.check_numbers(cand, allowed)
        if problems or "http" in cand:
            print(f"::warning::素材候補がガード不合格のため破棄: {problems}", file=sys.stderr)
            continue
        data["queue"].append({"id": f"m{next_no}", "text": cand, "used": False, "auto": True})
        next_no += 1
        added += 1
    if added:
        json.dump(data, open(gx.MATERIAL_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return added


def main():
    gaps = check_taiken_gaps()
    data, unused = material_state()
    added = replenish_materials(data, unused)
    data, unused = material_state()
    awaiting = check_awaiting()
    last_kpi, kpi_age = kpi_freshness()
    note_count, note_likes = fetch_note_public()

    lines = ["📋【結果マガ】週次ヘルスチェック(自動)"]
    lines.append(f"・X体験共有: {'欠落なし' if not gaps else '未投稿あり ' + '・'.join(gaps) + '(仕組みの修理が必要)'}")
    lines.append(f"・投稿素材の残り: {len(unused)}件" + (f"(自動補充 +{added})" if added else ""))
    if awaiting:
        lines.append(f"・公開待ちの下書き: {'・'.join(awaiting)} ← 時間のあるときに公開をお願いします")
    if note_count is not None:
        lines.append(f"・note公開情報: 記事{note_count}本・スキ合計{note_likes}(公開APIの実測)")
    lines.append(f"・KPI台帳の最終記録: {last_kpi}" + ("(8日超・今週の数字スクショをお待ちしています)" if kpi_age >= 8 else ""))
    lines.append("ビュー数と売上のスクショは、いつもどおりチャットへどうぞ(それ以外は全自動で回っています)")

    out = os.path.join(BASE, "data", "kekka_health_report.txt")
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print(f"report={os.path.relpath(out, BASE)}")
    print(f"replenished={added}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
