#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 結果マガ 無料実録ログ記事の週次自動生成(2026-09-16 小柳さん決裁「1」=案1)

判定日(9/16)に流入仮説を棄却した再設計の実装。唯一実証された流入装置=note公式ピックアップの
「抽選回数」を増やすため、週1で無料の実録ログ記事を自動生成する。
議事: docs/議事_20260916_判定日_流入仮説棄却とチャネル再設計.md

設計:
- facts は台帳(kekka_kpi.json)の実数のみ。数字ガードは generate_x_taiken と共用
  (台帳に無い数字を含む本文は生成失敗=ニドナシ#16の教訓)
- 出力は tanpatsu 互換(記事ヘッダーに告知パック/貼るだけ版/お題キューへL{NN}登録)。
  公開後は publish-record --id L{NN} がそのまま動く(記録・X告知・べき等性)
- 有料記事への内部導線は AI 出力ではなくコードが末尾に付加(AI出力へのリンク混入はガードで禁止)
- 同日重複ガード: キューのL系エントリの drafted_at が今日ならスキップ(リトライ枠の二重生成防止)

使い方: python scripts/generate_kekka_log.py [--dry-run]
出力(GITHUB_OUTPUT形式): stem= / title= / log_id= / eyecatch= または skipped=
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_x_taiken as gx  # facts・数字ガードを共用

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = gx.BASE
ARTICLE_DIR = os.path.join(BASE, "posts", "note", "tanpatsu")
PASTE_DIR = os.path.join(BASE, "posts", "note", "paste")
MAGAZINE_URL = "https://note.com/kekka_mag"


def load_topics():
    return json.load(open(gx.TOPICS_PATH, encoding="utf-8"))


def guard_log(text: str, allowed: set):
    """記事版ガード(長さ上限なし・それ以外は体験共有と同基準)。"""
    problems = []
    for w in gx.BANNED:
        if w in text:
            problems.append(f"禁止語: {w}")
    for m in gx.PLACEHOLDER_MARKERS:
        if m in text:
            problems.append(f"プレースホルダー/テンプレ残存: {m}")
    bad = gx.check_numbers(text, allowed)
    if bad:
        problems.append(f"factsに無い数字(捏造の疑い): {','.join(bad)}")
    if "http" in text:
        problems.append("本文にリンクを入れない(導線はコードが末尾に付加する)")
    if not text.startswith("# "):
        problems.append("1行目がタイトル(# )でない")
    # 名義分離(絶対枠)と内部IDの機械検査(ニドナシ#21: 初回ログに個人名と丸数字IDが混入)
    for ng in ("小柳", "ミカタ", "ALLGROUP", "GLOW", "フクギイロ", "嶺井"):
        if ng in text:
            problems.append(f"名義分離違反: {ng}")
    if re.search(r"[①-㊿⓪]", text):
        problems.append("内部ID(丸数字)は読者に通じない。記事名で書く")
    return problems


def build_week_facts():
    """体験共有のfactsに、週次の実測(前週比・記事別)を足す。"""
    facts = gx.build_facts()
    kpi = gx.load_json(gx.KPI_PATH, {})
    weeks = kpi.get("weeks", [])
    latest = weeks[-1] if weeks else {}
    prev = weeks[-2] if len(weeks) >= 2 else {}
    facts["今週の記事別ビュー"] = latest.get("note", {}).get("views_by_article", {})
    facts["前週の累計ビュー"] = prev.get("note", {}).get("total_views")
    facts["今週の週次メモ(実測の文脈)"] = latest.get("memo", "")
    facts["週番号"] = facts["初公開からの日数"] // 7 + 1
    return facts


def build_prompt(facts):
    return f"""あなたは「結果の出し方がわかってしまうマガジン」の編集AI。
このマガジンは「AIだけでnoteマガジンを運営したら月30万円の収益を作れるか」を公開実験している。
毎週1本、その週の実録ログを**無料記事**として書く。読者は途中経過を追いかけている人。

# 使ってよい実数(台帳の実測値。ここに無い数字は一切書かない)
{json.dumps(facts, ensure_ascii=False, indent=1)}

# 書き方
- 1行目は「# 」で始まるタイトル。「第{facts['週番号']}週」と実測の数字を1つ入れ、正直で具体的に
  (例の形式: 実録・第N週 — 累計◯ビューの現在地と、今週変えたこと)
- 分量は600〜1200字。無料記事なので有料ラインは作らない
- 構成: ①今週の実数(前週比も) ②今週起きたこと・変えたこと(週次メモの内容を自分の言葉で)
  ③正直な学び ④来週やること1つ
- 一人称は「私たち」または主語なし。AIが運営していることは隠さない
- 実況・等身大。売り込まない。うまくいっていない数字も隠さない
- 固有名・組織名(運営者の氏名や関連企業名)は書かない。決裁者への言及は「運営の決裁者」等の一般表現
- ①〜㉒のような内部の記事番号は使わない。記事に触れるときは記事名(の一部)で書く
- 誇大表現は禁止(必ず/絶対/誰でも/楽して/確実に稼〜)。成果の約束をしない
- リンク・URLは本文に書かない(導線は編集部が後から付ける)
- 見出しは「## 」を使ってよい

# 出力形式
タイトル行+本文Markdownのみ。前置き・説明は不要。"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    topics = load_topics()
    today = gx.today_jst().isoformat()
    log_entries = [t for t in topics["queue"] if str(t.get("id", "")).startswith("L")]
    if any(t.get("drafted_at") == today for t in log_entries):
        print("skipped=already_drafted_today")
        return 0
    log_id = f"L{len(log_entries) + 1:02d}"

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("エラー: ANTHROPIC_API_KEY未設定", file=sys.stderr)
        return 1
    import anthropic

    facts = build_week_facts()
    allowed = gx.allowed_numbers(facts)
    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_prompt(facts)
    body, last_problems = None, []
    for _ in range(2):
        msg = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        cand = "".join(b.text for b in msg.content if b.type == "text").strip()
        problems = guard_log(cand, allowed)
        if not problems:
            body = cand
            break
        last_problems = problems
        prompt += f"\n\n# 再生成指示\n前回の出力は検査不合格({' / '.join(problems)})。ガードを厳守して書き直してください。"
    if body is None:
        print(f"エラー: 検査不合格が続いたため生成中止: {' / '.join(last_problems)}", file=sys.stderr)
        return 1

    title = body.split("\n", 1)[0][2:].strip()

    # 内部導線(コードで付加。実測: ピックアップだけがビューを動かした→無料読者を有料研究へ)
    paid = [t for t in topics["queue"] if t.get("status") == "published" and t.get("published_url")]
    paid.sort(key=lambda t: t.get("published_at", ""))
    latest_paid = paid[-1] if paid else None
    lead = "\n\n---\n\nこの実験の有料研究レポートは「結果の出し方がわかってしまうマガジン」にまとめています。\n" + MAGAZINE_URL + "\n"
    if latest_paid:
        lead += f"\n直近のレポート: {latest_paid.get('title_hint', '').split(' — ')[0]}\n{latest_paid['published_url']}\n"
    body_full = body + lead

    # X告知フック(実測数字で機械組み立て=AI生成なし・捏造リスクゼロ)
    views = facts.get("note累計ビュー")
    week_no = facts["週番号"]
    hook_a = f"AIだけでnoteマガジンを運営する実験、第{week_no}週。累計{views}ビュー・売上{facts.get('note売上(直近実数)', 0)}円の実録ログを無料で公開しました"
    hook_b = f"うまくいっていない数字も毎週そのまま出す実録、第{week_no}週分です。今週の実測と変えたことをまとめました"

    # 記事ファイル(publish-record互換ヘッダー)
    header = f"""▼▼ 公開前にこのブロックを削除 ▼▼
[無料の実録ログ記事/ID {log_id}/価格0円(無料)/有料ラインなし]
[公開時: noteでマガジンに追加すること。数字は台帳実測(公開前に管理画面と一目照合)]

📣 X告知文パック(公開後、記事URLをリプ欄に。1日1本まで)
A(数字): {hook_a}
B(学び): {hook_b}
▲▲ ここまで削除 ▲▲

"""
    stem = f"{log_id}_unei_log_{today.replace('-', '')}"
    os.makedirs(ARTICLE_DIR, exist_ok=True)
    os.makedirs(PASTE_DIR, exist_ok=True)
    if not args.dry_run:
        open(os.path.join(ARTICLE_DIR, f"{stem}.md"), "w", encoding="utf-8").write(header + body_full + "\n")
        # 貼るだけ版(1行目=タイトル・以降が本文。tanpatsuと同じ運用)
        open(os.path.join(PASTE_DIR, f"{log_id}_hariduke_you.md"), "w", encoding="utf-8").write(
            title + "\n\n" + body_full.split("\n", 1)[1].lstrip("\n") + "\n"
        )
        topics["queue"].append({
            "id": log_id,
            "slug": "unei_log",
            "genre": "実録ログ(無料)",
            "title_hint": title,
            "paid_price": 0,
            "status": "log_drafted",
            "drafted_at": today,
            "note": "週次無料ログ(議事_20260916 案1)。公開後は publish-record --id " + log_id,
        })
        json.dump(topics, open(gx.TOPICS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        # 見出し画像(失敗しても記事生成は成立させる)
        eyecatch = ""
        try:
            import generate_kekka_assets as ka
            out = os.path.join(BASE, "assets", "kekka", f"eyecatch_{log_id}.png")
            ka.make_eyecatch(title, out)
            eyecatch = f"assets/kekka/eyecatch_{log_id}.png"
        except Exception as e:
            print(f"::warning::見出し画像の生成に失敗(記事は生成済み): {e}", file=sys.stderr)
        print(f"eyecatch={eyecatch}")
    print(f"log_id={log_id}")
    print(f"stem={stem}")
    print(f"title={title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
