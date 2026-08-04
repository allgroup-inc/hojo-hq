#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 多ジャンル単発記事(実例研究シリーズ)自動下書きジェネレータ
(設計・議事: docs/note収益化_運営計画v3_月30万.md / 2026-08-04 起案)

data/tanpatsu_topics.json のお題キューから1件を取り、
リサーチ済みファクト(出典URL必須)だけを材料に Claude API で
noteにそのまま貼れる単発記事の下書きを posts/note/tanpatsu/ に生成する。
あわせてX告知文パック(3パターン)を同梱する。

制約(CLAUDE.md 絶対ルール#1 / note運用規程3-3):
- 記事は「世界・国内の公表事例のリサーチ報告」として書く。
  自分の体験と偽らない(実体験はミカタ自身の運営実録のみ・お題側で明示)
- ファクトはお題キューに登録された claim+source のみ。AIが新しい数字・事実を作らない
- 収益の保証表現は禁止。禁止語(必ず/絶対/誰でも/楽して/確実に稼)検査に落ちたら
  リトライ1回→それでも落ちたら生成失敗として終了(捏造・緩和で埋めない)
- 公開は人間(noteに投稿公式APIはなく、非公式手段は絶対ルール2により使わない)

使い方:
  python scripts/generate_tanpatsu_draft.py            # 次のpendingお題で生成
  python scripts/generate_tanpatsu_draft.py --dry-run  # 標準出力のみ
  python scripts/generate_tanpatsu_draft.py --preview  # Actions用: key=value 出力
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
TOPICS_PATH = os.path.join(BASE, "data", "tanpatsu_topics.json")
OUT_DIR = os.path.join(BASE, "posts", "note", "tanpatsu")

SITE_URL = "https://allgroup-inc.github.io/hojo-hq/?utm_source=note&utm_medium=article&utm_campaign=tanpatsu"

# note運用規程3-3: 機械検査はスクリプトから外さない(緩和は決裁事項)
BANNED_WORDS = ("必ず", "絶対", "誰でも", "楽して", "確実に稼")

FOOTER = f"""
---

この記事はAIが下書きを作成し、人間が内容を確認してから公開しています。
記事中の事例・数字はすべて公表されている情報のリサーチにもとづくもので、
成果を保証するものではありません。出典は本文中に明記しています。

沖縄の中小企業向けに、補助金・助成金の情報を毎日AIで収集・公開しています。
▶ 沖縄企業のミカタ {SITE_URL}
"""


def load_topics():
    with open(TOPICS_PATH, encoding="utf-8") as f:
        return json.load(f)


def pick_topic(topics):
    for t in topics.get("queue", []):
        if t.get("status") == "pending":
            return t
    return None


def validate_topic(t):
    """出典URLのないファクトが1つでもあれば生成を拒否する(正確性最優先)。"""
    errors = []
    facts = t.get("facts", [])
    if not facts:
        errors.append("factsが空(リサーチ済みファクトなしでは書かない)")
    for i, f in enumerate(facts):
        if not f.get("claim"):
            errors.append(f"facts[{i}]: claimなし")
        if not (f.get("source") or "").startswith("http"):
            errors.append(f"facts[{i}]: 出典URLなし")
    return errors


def banned_hits(text):
    return [w for w in BANNED_WORDS if w in text]


def build_prompt(t):
    facts_md = "\n".join(
        f"- {f['claim']}(出典: {f.get('source_name', '')} {f['source']}"
        + (f" / {f['date']}時点" if f.get("date") else "")
        + ")"
        for f in t["facts"]
    )
    persona = t.get(
        "persona_note",
        "書き手は「沖縄企業のミカタ AI編集部」。自分の実体験として語ってよいのは"
        "ミカタ自身の運営(AIによる毎日の補助金データ収集・公開)の話だけ。"
        "それ以外の事例はすべて『公表されている事例のリサーチ』として出典つきで紹介する。",
    )
    return f"""あなたは沖縄の中小企業向けメディア「沖縄企業のミカタ」のAI編集部です。
noteの有料単発記事(実例研究シリーズ)の下書きを1本書いてください。

# お題
- ジャンル: {t['genre']}
- タイトルの方向性: {t['title_hint']}
- 切り口: {t['angle']}
- 提案価格: {t.get('paid_price', 980)}円

# 使ってよいファクト(この一覧にない数字・事例・固有名詞の実績は書かない)
{facts_md}

# 書き手の立場
{persona}

# 構成ルール — 無料部分は「販売テンプレ12」(docs/note販売テンプレ12_黄金構成.md)の順に組む
無料部分(見出しは立てず自然な流れで):
1. 冒頭100文字で読者(沖縄・地方の中小企業経営者)が「自分のことだ」と感じる掴み(悩みの言語化か意外な数字)
2. 誰のどんな悩みを解決する記事かを明示する
3. 読まない場合に知らないままになること/読んだ後にできるようになることの差を、事実ベースで見せる(不安を煽らない・成果を約束しない)
4. 自己紹介: ミカタの実運営の事実のみ(AIが毎日収集・人間が検品する補助金メディアの運営)。それ以外を実績として語らない
5. 執筆のきっかけを1〜2文のストーリーで
6. 有料部分の目次を2〜3行チラ見せして期待をつくる
7. オススメする人・しない人を正直に書き分ける(あえて絞る)
8. 価格の心理的ハードルを下げる一言(ランチ1回分など。安さの実感であって値引きの約束ではない)
9. 一番気になる問いを立てた直後に「====(ここから有料ライン)====」で寸止めして切る
※口コミ・特典・数量限定の枠は使わない(実在する声・実物・実際の決裁がある場合のみ人間が追記する)

有料部分:
- 「事例の紹介 → そこから抽出できる共通の型 → 沖縄・地方の中小企業が明日から使える実務への翻訳」の順
- 事例を紹介するたびに、文中に出典(媒体名とURL)を明記する
- 冒頭の寸止めの問いには、有料部分の早い段階で答える(引っ張りすぎない)

全体:
- 分量: 全体で3,500〜5,000字程度
- 文体: です・ます調。専門用語はやさしく翻訳する(ブランドトーン)

# 禁止事項(1つでも破ると不合格)
- 「必ず」「絶対」「誰でも」「楽して」「確実に稼げる」等の保証・誇大表現
- ファクト一覧にない数字・事例・実績を書くこと(推測で数字を埋めない)
- 他人の事例を自分の体験のように書くこと
- 収益額の約束(「あなたも月◯万円」型の表現)
- 絵文字の多用・不自然な箇条書きの乱発

# 出力形式
1行目に「# 」で始まるタイトル、その後に本文Markdownのみを出力。挨拶や説明は不要。"""


def build_xpack(title, t):
    price = t.get("paid_price", 980)
    return f"""📣 X告知文パック(公開後、記事URLを足して使う。1日1本まで)

【パターンA: 数字フック】
{t.get('x_hook_a', '(記事の冒頭の数字を1つ引用して驚きを短く)')}
詳しくはnoteに書きました({price}円)→(記事URL)

【パターンB: 学びの共有】
{t.get('x_hook_b', '(事例から抽出した「型」を1行で紹介)')}
出典つきで整理しました→(記事URL)

【パターンC: 問いかけ】
{t.get('x_hook_c', '(読者の悩みを問いかけ形式で)')}
世界の公表事例を調べてまとめました→(記事URL)
"""


def generate_body(t):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "ANTHROPIC_API_KEY未設定のためスキップ(手動執筆または後日再実行)"
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_prompt(t)
    last_hits = []
    for attempt in range(2):
        msg = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        if msg.stop_reason == "max_tokens":
            last_hits = ["(途中切れ)"]
            continue
        body = "".join(b.text for b in msg.content if b.type == "text").strip()
        hits = banned_hits(body)
        if not hits and "====" in body and body.startswith("# "):
            return body, None
        last_hits = hits or ["(形式不備: タイトル行または有料ラインなし)"]
        prompt += (
            f"\n\n# 再生成指示\n前回の出力は不合格({'・'.join(last_hits)})。"
            "禁止事項と出力形式を厳守して書き直してください。"
        )
    return None, f"検査不合格が続いたため生成中止: {'・'.join(last_hits)}(捏造・緩和で埋めない)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()

    topics = load_topics()
    t = pick_topic(topics)
    if t is None:
        print("skipped=empty_queue" if args.preview else "お題キューにpendingがありません(data/tanpatsu_topics.json に追加を)")
        return 0

    errors = validate_topic(t)
    if errors:
        msg = "お題の検証に失敗: " + " / ".join(errors)
        if args.preview:
            print("skipped=invalid_topic")
        print(msg, file=sys.stderr)
        return 1

    body, skip_reason = generate_body(t)
    if body is None:
        if "スキップ" in (skip_reason or ""):
            print("skipped=no_api_key" if args.preview else skip_reason)
            return 0
        print(skip_reason, file=sys.stderr)
        return 1

    title = body.splitlines()[0].lstrip("# ").strip()
    today = datetime.now(JST).date().isoformat()
    stem = f"{t['id']}_{t.get('slug', 'kiji')}"
    header = f"""▼▼ 公開前にこのブロックを削除 ▼▼
[単発・実例研究シリーズ/お題ID {t['id']}/提案価格{t.get('paid_price', 980)}円/有料ラインは本文中の「====」の位置に設定]
[この記事は自動下書き({today}生成)。公開前チェックリスト(note運用規程3-1)を通すこと。
 とくに: 出典URLが実在するか無料部分から2件抜き取りで開いて確認/事例を体験と誤読させる表現がないか]

{build_xpack(title, t)}
▲▲ ここまで削除 ▲▲

"""
    content = header + body + "\n" + FOOTER

    if args.dry_run:
        print(content)
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{stem}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    t["status"] = "drafted"
    t["drafted_at"] = today
    with open(TOPICS_PATH, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)
        f.write("\n")

    if args.preview:
        print(f"stem={stem}")
        print(f"title={title}")
    else:
        print(f"生成完了: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
