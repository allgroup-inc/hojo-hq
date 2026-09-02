#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 結果マガのX体験共有投稿の自動生成(2026-08-23 小柳さん決裁で解禁)

「告知のみ」だったX運用に、運営実録の体験共有を追加する自動投稿の生成部。
議事: docs/議事_20260823_X体験共有解禁と運営実録.md / 運転ルール: 1日1本・公式APIのみ。

設計(resilient-agent-design準拠): 判断(文面生成)だけAI、状態は外部保存
(data/kekka_x_log.json / kekka_x_material.json)、同日重複はべき等性キー(日付)で拒否。

機械ガード(全部通らないと投稿されない):
  1. 同日重複ガード: ログ+お題キューのx_posted_atに今日(JST)があれば生成しない(1日1本の機械化)
  2. 禁止語検査(規程3-3)+shipping_gateの禁止表現(post_x_announce.py側でも再検査)
  3. 数字の実数照合: 生成文中の数字は、渡したfacts(台帳の実数)に含まれるものだけ許可
     (AIの数字捏造をコードで遮断。ニドナシ#16の教訓=不正な文面を機械が検知せず素通しした)
  4. 長さ検査: X加重長(全角2/半角1)260以内
  5. プレースホルダー検知(テンプレ指示文の混入)

使い方:
  python scripts/generate_x_taiken.py            # 生成してGITHUB_OUTPUT形式で出力
  python scripts/generate_x_taiken.py --record --url https://x.com/... \
      --material-id m1 --text "..."              # 投稿成功後の記録(ログ追記+素材消込)
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
KPI_PATH = os.path.join(BASE, "data", "kekka_kpi.json")
TOPICS_PATH = os.path.join(BASE, "data", "tanpatsu_topics.json")
MATERIAL_PATH = os.path.join(BASE, "data", "kekka_x_material.json")
LOG_PATH = os.path.join(BASE, "data", "kekka_x_log.json")

BANNED = ("必ず", "絶対", "誰でも", "楽して", "確実に稼")
PLACEHOLDER_MARKERS = ("(記事の", "(事例から", "(読者の", "を1つ引用して", "を1行で紹介", "問いかけ形式で", "{", "}")
FIRST_PUBLISH = "2026-08-06"  # 記事⑤の公開日(運営実録の起点)


def x_weighted_len(text: str) -> int:
    return sum(1 if ord(c) < 0x80 else 2 for c in text)


def load_json(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        return default


def today_jst():
    return datetime.now(JST).date()


def already_posted_today():
    """1日1本ルールの機械化。ログとお題キューのX投稿記録に今日の日付があればTrue。"""
    today = today_jst().isoformat()
    log = load_json(LOG_PATH, {"posts": []})
    for p in log.get("posts", []):
        if p.get("date") == today:
            return True
    topics = load_json(TOPICS_PATH, {"queue": []})
    for t in topics.get("queue", []):
        if t.get("x_posted_at") == today:
            return True
    return False


def build_facts():
    """台帳の実数だけを facts にまとめる(この文字列に無い数字は投稿文に書けない)。"""
    kpi = load_json(KPI_PATH, {})
    weeks = kpi.get("weeks", [])
    latest = weeks[-1] if weeks else {}
    note = latest.get("note", {})
    # 売上が「未報告」の週は、直近の実数報告値へフォールバック(数字ガードで0円が書けなくなるのを防ぐ)
    sales = note.get("sales")
    if not isinstance(sales, (int, float)):
        for w in reversed(weeks):
            s = w.get("note", {}).get("sales")
            if isinstance(s, (int, float)):
                sales = s
                break
    topics = load_json(TOPICS_PATH, {"queue": []})
    published = [t for t in topics.get("queue", []) if t.get("status") == "published"]
    days = (today_jst() - datetime.strptime(FIRST_PUBLISH, "%Y-%m-%d").date()).days
    facts = {
        "今日": today_jst().isoformat(),
        "初公開からの日数": days,
        "初公開からの週数": days // 7,
        "公開済み記事数(自動生成キュー分)": len(published),
        "公開済み記事数(手動執筆含む合計)": len(kpi.get("articles", {})),
        "直近週次の計測日": latest.get("date"),
        "note累計ビュー": note.get("total_views"),
        "noteスキ": note.get("likes"),
        "note売上(直近実数)": sales,
    }
    return facts


def allowed_numbers(*sources) -> set:
    nums = set()
    for s in sources:
        text = json.dumps(s, ensure_ascii=False) if not isinstance(s, str) else s
        text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        nums.update(re.findall(r"\d+[万千億]?", text))  # 単位付きトークンも許可リストに入れる
        nums.update(re.findall(r"\d+", text))
    return nums


def check_numbers(text: str, allowed: set):
    """全角数字を半角化してから、facts/素材に無い数字を列挙する。

    「1」「2」「3」の単独は文章表現(1本・2回・3周など)で頻出のため許容するが、
    万・千・億の単位付き(「1万人」等)は桁の捏造になり得るため、単位込みの文字列が
    素材・factsに無ければ不合格にする。
    """
    normalized = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    bad = []
    for m in re.finditer(r"\d+[万千億]?", normalized):
        token = m.group(0)
        digits = token.rstrip("万千億")
        if token != digits:  # 単位付きはトークン全体で照合(allowedには素材の原文も入れる)
            if token not in allowed and digits not in allowed:
                bad.append(token)
        elif digits not in allowed and digits not in ("1", "2", "3"):
            bad.append(digits)
    return bad


def guard(text: str, allowed: set):
    problems = []
    for w in BANNED:
        if w in text:
            problems.append(f"禁止語: {w}")
    for m in PLACEHOLDER_MARKERS:
        if m in text:
            problems.append(f"プレースホルダー/テンプレ残存: {m}")
    bad_nums = check_numbers(text, allowed)
    if bad_nums:
        problems.append(f"factsに無い数字(捏造の疑い): {','.join(bad_nums)}")
    length = x_weighted_len(text)
    if length > 260:
        problems.append(f"長すぎ({length}/260 X加重長)")
    if "http" in text or "note.com" in text:
        problems.append("リンクは本文に入れない(体験共有投稿はリンクなし)")
    if "\n\n\n" in text:
        problems.append("空行が多すぎる")
    return problems


def pick_material():
    data = load_json(MATERIAL_PATH, {"queue": []})
    for m in data.get("queue", []):
        if not m.get("used"):
            return m
    return None


def build_prompt(facts, material):
    return f"""あなたは「結果の出し方がわかってしまうマガジン」(note×X×AIの実験)のX投稿を書く。
このアカウントは「AIだけでnoteマガジンを運営したらどうなるか」を実況する体験共有アカウント。
今日の投稿を1本だけ書く。

# 今日の素材(この出来事・学びを軸に書く)
{material['text']}

# 使ってよい実数(台帳の実測値。ここに無い数字は一切書かない)
{json.dumps(facts, ensure_ascii=False, indent=1)}

# 書き方
- 一人称は「私」または主語なし。AIが運営していることは隠さない(それがこのアカウントの一次情報)
- 実況・等身大のトーン。売り込まない。教えたがらない。起きたことと数字を正直に
- 成果の約束・誇大表現は禁止(必ず/絶対/誰でも/楽して/確実に稼〜)
- リンク・ハッシュタグ・絵文字は入れない
- 全角135文字以内。改行は最大2回
- 数字は上のfactsにあるものだけ。日付・曜日も書くならfactsの値から

# 出力形式
投稿本文のみを出力。前置き・説明・かぎかっこ囲みは不要。"""


def generate():
    # 時刻窓ガード(2026-09-01 ニドナシ#18): GitHubのcronが数時間遅延して日付をまたぐと、
    # 「前夜の投稿」が翌日の1日1本枠を先食いする(実例: 8/31 21:05枠が9/1 4:28に投稿され、
    # 同日の記事告知と合わせて2本になった)。想定枠(21〜23時JST)の外なら投稿せず見送る
    hour = datetime.now(JST).hour
    if not (21 <= hour <= 23) and not os.environ.get("KEKKA_TAIKEN_FORCE"):
        print("skipped=out_of_window")
        print(f"::warning::実行がJST{hour}時のため投稿を見送り(想定枠21〜23時。cron遅延で日付またぎの枠先食いを防止)", file=sys.stderr)
        return 0
    if already_posted_today():
        print("skipped=already_posted_today")
        return 0
    material = pick_material()
    if not material:
        print("skipped=no_material")
        print("::warning::体験共有の素材キューが空です。週次運転で補充してください", file=sys.stderr)
        return 0
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("エラー: ANTHROPIC_API_KEY未設定", file=sys.stderr)
        return 1
    import anthropic

    facts = build_facts()
    allowed = allowed_numbers(facts, material["text"])
    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_prompt(facts, material)
    last_problems = []
    for _ in range(2):
        msg = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if b.type == "text").strip().strip("「」\"")
        problems = guard(text, allowed)
        if not problems:
            # GITHUB_OUTPUT は1行値のみ→改行はエスケープせず、投稿用に本文ファイルも書く
            out_path = os.path.join(BASE, "data", "kekka_x_taiken_draft.txt")
            open(out_path, "w", encoding="utf-8").write(text)
            print(f"material_id={material['id']}")
            print("text_file=data/kekka_x_taiken_draft.txt")
            print("generated=1")
            return 0
        last_problems = problems
        prompt += (
            f"\n\n# 再生成指示\n前回の出力は検査不合格({' / '.join(problems)})。"
            "ガードを厳守して書き直してください。"
        )
    print(f"エラー: 検査不合格が続いたため生成中止: {' / '.join(last_problems)}", file=sys.stderr)
    return 1


def record(url, material_id, text):
    today = today_jst().isoformat()
    log = load_json(LOG_PATH, {"_readme": "", "posts": []})
    if any(p.get("url") == url for p in log.get("posts", [])):
        print("already=1")
        return 0
    log.setdefault("posts", []).append(
        {"date": today, "type": "taiken", "material_id": material_id, "text": text, "url": url}
    )
    json.dump(log, open(LOG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    data = load_json(MATERIAL_PATH, {"queue": []})
    for m in data.get("queue", []):
        if m.get("id") == material_id:
            m["used"] = True
            m["used_at"] = today
    json.dump(data, open(MATERIAL_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("recorded=1")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--url")
    ap.add_argument("--material-id")
    ap.add_argument("--text", default="")
    args = ap.parse_args()
    if args.record:
        if not (args.url and args.material_id):
            print("エラー: --record には --url と --material-id が必要", file=sys.stderr)
            return 1
        return record(args.url, args.material_id, args.text)
    return generate()


if __name__ == "__main__":
    sys.exit(main())
