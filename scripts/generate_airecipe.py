#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""うごくAIレシピ — 週2回のnote下書き自動生成+実行検証パイプライン。

docs/うごくAIレシピ_設計.md / docs/議事_note新路線_うごくAIレシピ_2026-08-09.md に基づく。

流れ(検証に成功したときだけ記事とキュー更新が書き込まれる):
  1. data/airecipe_topics.json の先頭 pending を1件取る
  2. Claude API でレシピ(プロンプト+手順)をJSON生成
  3. 生成されたプロンプトを sample_input に対して実際に実行(=検証)
  4. 機械バリデーション(必須要素・文字数・BANNED_WORDS・実行ログ非空)
  5. 記事Markdownを組版して posts/airecipe/ へ書き込み、お題を drafted に更新

捏造フォールバックはしない: 生成や検証に失敗したらお題は pending のまま持ち越し、
ワークフローを失敗させてLINEで気づけるようにする。

usage:
  python scripts/generate_airecipe.py --preview          # 生成(CI用。GITHUB_OUTPUT形式で出力)
  python scripts/generate_airecipe.py --topic-id 3       # お題を指定して生成
  python scripts/generate_airecipe.py --dry-run          # APIなしで組版だけ確認(canned data)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
BASE = Path(__file__).resolve().parent.parent
TOPICS_PATH = BASE / "data" / "airecipe_topics.json"
OUT_DIR = BASE / "posts" / "airecipe"

MODEL = "claude-opus-5"
# 誇大表現の機械禁止(CLAUDE.md 憲法 + note運用規程v3)
BANNED_WORDS = ["必ず", "絶対", "誰でも", "楽して", "確実に稼"]
# 検証環境の明記(議事の裁定1: 欠落したら失敗扱い)。組版側で挿入し、最終チェックでも確認する
VERIFY_NOTICE = "このレシピは公開前にClaude(claude-opus-5)で実際に実行し、その実行ログを原文のまま載せています。"
DISCLAIMER = (
    "※ お使いのAI(ChatGPT・Gemini等)やモデルの版によって、出力の中身や質は変わります。"
    "この記事が保証するのは「検証日にClaudeで動いた」ことまでで、成果や効果を約束するものではありません。"
)

PRICE_HINT = "980"  # 単発価格の提案値。決裁は小柳さん(記事本文には書かない)

RECIPE_SYSTEM = """あなたは「うごくAIレシピ」というnoteマガジンの編集者です。
読者は、AIにくわしくない普通の働く人。専門用語をやさしく翻訳する立ち位置で書きます。

与えられたお題から、読者がそのままコピペして使える「AIレシピ」を1本作ってください。
必ず次のJSONだけを出力します(前後の説明文・コードフェンス不要):

{
  "title": "記事タイトル(32字以内)。公式=【作業の悩み】×【数字のギャップ】×【条件の軽さ】。例:「会議メモを貼るだけ、30分の議事録づくりが1分になる」。数字はuse_caseにあるものだけを使う(捏造しない)。煽らない",
  "title_alts": ["タイトル別案を2つ(各32字以内)。1つ目=読者の悩みを言語化した問いかけ型(例:「その清書、まだ手でやっていますか」)。2つ目=常識破り型(例:「議事録は会議後に書くものではなくなった」)"],
  "lead": "リード文(120〜200字。読者の困りごと→このレシピで何が変わるか)",
  "dekiru": ["このレシピでできることを3つ、それぞれ40字以内"],
  "prompt_text": "コピペ用プロンプト全文(300〜900字。役割・目的・出力形式・制約を含む。文頭に『あなたは〜』で役割を与える。最後は『それでは、以下の入力を処理してください。』で締める)",
  "steps": ["使い方の手順を3〜5個、それぞれ60字以内"],
  "arrange": ["自分用にアレンジする方法を2〜3個、それぞれ80字以内"],
  "trouble": "うまく動かないときの対処(100〜200字)"
}

守ること:
- 次の語を使わない: 必ず / 絶対 / 誰でも / 楽して / 確実に稼
- 成果・収入・効果を断定しない(「〜できます」は動作の説明のみ可)
- 実在の企業名・人名・商品名を出さない
- prompt_text は与えられた sample_input のような入力に対して単体で動く完結したプロンプトにする"""


def now_jst():
    return datetime.now(JST)


def load_topics():
    return json.loads(TOPICS_PATH.read_text(encoding="utf-8"))


def pick_topic(data, topic_id=None):
    for t in data["topics"]:
        if topic_id is not None:
            if t["id"] == topic_id:
                return t
        elif t.get("status") == "pending":
            return t
    return None


def banned_hits(text):
    return [w for w in BANNED_WORDS if w in text]


def validate_recipe(r):
    """完了条件はAIの自己申告でなくシステムで判定する(設計原則2)。"""
    errors = []
    need = {"title": str, "title_alts": list, "lead": str, "dekiru": list,
            "prompt_text": str, "steps": list, "arrange": list, "trouble": str}
    for k, typ in need.items():
        if not isinstance(r.get(k), typ) or not r.get(k):
            errors.append(f"欠落/型不正: {k}")
    if errors:
        return errors
    if len(r["title"]) > 40:
        errors.append(f"title長すぎ({len(r['title'])}字)")
    if not (200 <= len(r["prompt_text"]) <= 1200):
        errors.append(f"prompt_text長({len(r['prompt_text'])}字)が範囲外")
    if not (3 <= len(r["steps"]) <= 5):
        errors.append("stepsは3〜5個")
    if len(r["dekiru"]) != 3:
        errors.append("dekiruは3個")
    if len(r["title_alts"]) != 2:
        errors.append("title_altsは2個")
    for t in r["title_alts"]:
        if not isinstance(t, str) or len(t) > 40:
            errors.append("title_altsが不正/長すぎ")
            break
    # 禁止語検査は読者向けの文のみ。prompt_text(AIへの指示文)内の「必ずJSON形式で」等は
    # 読者への誇大表現ではないため対象外(2026-08-17 監査議事。8/11の失敗の再発防止)
    reader_facing = {k: v for k, v in r.items() if k != "prompt_text"}
    joined = json.dumps(reader_facing, ensure_ascii=False)
    hits = banned_hits(joined)
    if hits:
        errors.append("禁止語: " + "/".join(hits))
    return errors


def parse_json_loose(text):
    """コードフェンスや前後の説明が混ざっても最初のJSONオブジェクトを取り出す。"""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("JSONが見つからない")
    return json.loads(m.group(0))


def call_claude(client, system, user, max_tokens):
    kwargs = dict(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": "low"},
    )
    if system:
        kwargs["system"] = system
    resp = client.messages.create(**kwargs)
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"生成中断: stop_reason={resp.stop_reason}")
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


def generate_recipe(client, topic, feedback=None):
    user = (
        f"お題: {topic['theme']}\n"
        f"想定読者と使いどころ: {topic['use_case']}\n"
        f"sample_input(検証に使う入力例):\n{topic['sample_input']}"
    )
    if feedback:
        user += ("\n\n【重要】前回の出力は次の理由で不合格でした。全て修正した完全版を出力してください:\n- "
                 + "\n- ".join(feedback))
    raw = call_claude(client, RECIPE_SYSTEM, user, max_tokens=3000)
    return parse_json_loose(raw)


def run_verification(client, recipe, topic):
    """生成されたプロンプトを、読者がやるのと同じ形で実際に実行する(=検証)。"""
    user = recipe["prompt_text"] + "\n\n---\n\n" + topic["sample_input"]
    out = call_claude(client, system="", user=user, max_tokens=2000)
    if len(out) < 80:
        raise RuntimeError(f"検証出力が短すぎる({len(out)}字)")
    return out


def canned_recipe(topic):
    """--dry-run 用。組版とバリデーションの動作確認のみに使う(記事には使わない)。"""
    return {
        "title": "(dry-run)組版テスト用レシピ",
        "title_alts": ["(dry-run)別案1", "(dry-run)別案2"],
        "lead": "これはdry-runの組版テストです。" * 8,
        "dekiru": ["テスト1", "テスト2", "テスト3"],
        "prompt_text": "あなたはテスト用のアシスタントです。" + "入力を整理して出力形式に従って返します。" * 12
                       + "それでは、以下の入力を処理してください。",
        "steps": ["手順1", "手順2", "手順3"],
        "arrange": ["アレンジ1", "アレンジ2"],
        "trouble": "dry-runのため実際の対処は生成されません。" * 4,
    }


def build_xpack(recipe, topic):
    a = f"A(数字): {recipe['title']}。プロンプトは公開前に実際に実行して、動いた実行ログごと記事に載せました"
    b = ("B(学び): プロンプト集は「動くかどうか」が読む前にわからないのが弱点です。"
         "このマガジンは公開前に機械で実行し、実行ログを原文のまま載せる方式にしました")
    c = f"C(問い): {topic['use_case'].split('が')[0]}の時間、AIに渡せるとしたら何分ほしいですか"
    alts = recipe.get("title_alts", [])
    return "\n".join([
        "▼▼ 公開前にこのブロックを削除 ▼▼",
        "🏷 タイトル別案(しっくり来なければ差し替えOK。基本は数字ギャップ型の本題のまま)",
        *[f"・{t}" for t in alts],
        "",
        "📣 X告知文パック(公開後、記事URLをリプ欄に。1日1本まで)",
        a, b, c,
        "▲▲ ここまで削除 ▲▲",
        "",
    ])


def build_article(recipe, topic, verify_output, date):
    dstr = date.strftime("%Y-%m-%d")
    excerpt = verify_output.strip()
    if len(excerpt) > 900:
        excerpt = excerpt[:900] + "\n(以下略)"
    L = []
    L.append(f"# {recipe['title']}")
    L.append("")
    L.append(recipe["lead"])
    L.append("")
    L.append("## このレシピでできること")
    L.append("")
    for d in recipe["dekiru"]:
        L.append(f"- {d}")
    L.append("")
    L.append("## 実行ログ(抜粋・原文ママ)")
    L.append("")
    L.append("サンプル入力(架空の例です):")
    L.append("")
    L.append("> " + topic["sample_input"].replace("\n", "\n> "))
    L.append("")
    L.append("これを本記事のレシピに渡した、実際の出力がこちらです。")
    L.append("")
    L.append("```")
    L.append(excerpt)
    L.append("```")
    L.append("")
    L.append(f"{VERIFY_NOTICE}(検証日: {dstr})")
    L.append("")
    L.append("---")
    L.append("")
    L.append("ここから先が有料パートです。コピペで使えるレシピ全文と、手順・アレンジ・つまずいたときの対処が続きます。")
    L.append("")
    L.append("## レシピ全文(コピペ用)")
    L.append("")
    L.append("```")
    L.append(recipe["prompt_text"])
    L.append("```")
    L.append("")
    L.append("## 手順")
    L.append("")
    for i, s in enumerate(recipe["steps"], 1):
        L.append(f"{i}. {s}")
    L.append("")
    L.append("## 自分用にアレンジする")
    L.append("")
    for a in recipe["arrange"]:
        L.append(f"- {a}")
    L.append("")
    L.append("## うまく動かないとき")
    L.append("")
    L.append(recipe["trouble"])
    L.append("")
    L.append("---")
    L.append("")
    L.append(DISCLAIMER)
    L.append("")
    article = "\n".join(L)
    # 最終チェック: 必須文言と禁止語(組版後の全文に対して)
    if VERIFY_NOTICE not in article:
        raise RuntimeError("検証明記の文言が記事にない")
    # プロンプト本文と実行ログ(AI向け指示とその出力)を除いた読者向けの文だけを検査
    reader_text = article.replace(recipe["prompt_text"], "").replace(excerpt, "")
    hits = banned_hits(reader_text)
    if hits:
        raise RuntimeError("組版後の記事に禁止語: " + "/".join(hits))
    return article


def gh_output(k, v):
    print(f"{k}={str(v).replace(chr(10), ' ')}")


def unpublished_stock():
    """未公開在庫の本数(公開済みは冒頭に published: 行が追記される運用)。"""
    n = 0
    for p in OUT_DIR.glob("*.md"):
        if "published:" not in p.read_text(encoding="utf-8")[:2000]:
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="GITHUB_OUTPUT形式で結果を出力")
    ap.add_argument("--topic-id", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="APIなしで組版確認(キュー更新もしない)")
    args = ap.parse_args()

    today = now_jst()
    data = load_topics()

    # 同日ガード(べき等性): リトライ枠での二重生成を防ぐ。--topic-id 指定時は明示操作なので通す
    dstr = today.strftime("%Y-%m-%d")
    if args.topic_id is None and not args.dry_run:
        done_today = [t for t in data["topics"] if t.get("drafted_at") == dstr]
        if done_today:
            t = done_today[0]
            gh_output("stem", f"{t['id']:02d}_{t['slug']}")
            gh_output("title", "(本日分は生成済みのためスキップ)")
            gh_output("xpost", "")
            gh_output("status", "already_done")
            return

    topic = pick_topic(data, args.topic_id)
    if topic is None:
        gh_output("stem", "")
        gh_output("title", "お題キューが空です(data/airecipe_topics.json に追加してください)")
        gh_output("xpost", "")
        gh_output("status", "empty_queue")
        return

    if args.dry_run:
        recipe = canned_recipe(topic)
        errors = validate_recipe(recipe)
        if errors:
            raise SystemExit("バリデーション失敗: " + " / ".join(errors))
        verify_output = "(dry-run: 検証実行はスキップ)" + " " * 80
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise SystemExit("ANTHROPIC_API_KEY がありません(捏造フォールバックはしない方針のため中断)")
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        recipe = generate_recipe(client, topic)
        errors = validate_recipe(recipe)
        if errors:
            # 不合格理由を渡して再生成1回まで(resilient-agent-design: 上限つきリトライ。
            # 2026-08-17 監査議事。それでも不合格なら持ち越し=捏造しない)
            recipe = generate_recipe(client, topic, feedback=errors)
            errors = validate_recipe(recipe)
        if errors:
            raise SystemExit("バリデーション失敗・再生成でも不合格(お題は持ち越し): " + " / ".join(errors))
        verify_output = run_verification(client, recipe, topic)

    article = build_article(recipe, topic, verify_output, today)
    stem = f"{topic['id']:02d}_{topic['slug']}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{stem}.md"
    xpack = build_xpack(recipe, topic)
    out_path.write_text(xpack + article, encoding="utf-8")

    if not args.dry_run:
        topic["status"] = "drafted"
        topic["drafted_at"] = dstr
        TOPICS_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.preview:
        stock = unpublished_stock()
        gh_output("stem", stem)
        gh_output("title", recipe["title"])
        gh_output("xpost", f"A(数字): {recipe['title']}。実行ログ付きで公開しました")
        gh_output("status", "ok")
        gh_output("eyecatch", f"eyecatch_{topic['id']:02d}.png")
        gh_output("stock", stock)
        gh_output("stockwarn",
                  f"⚠️ 未公開の在庫が{stock}本たまっています(生成ペース見直しの警告ライン)" if stock >= 4 else "")
    else:
        print(f"生成完了: {out_path}")


if __name__ == "__main__":
    main()
