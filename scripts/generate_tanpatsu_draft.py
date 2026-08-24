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
  自分の体験と偽らない(実体験は自分たちの情報メディア運営の実録のみ・媒体名は書かない=名義分離)
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

# note運用規程3-3: 機械検査はスクリプトから外さない(緩和は決裁事項)
BANNED_WORDS = ("必ず", "絶対", "誰でも", "楽して", "確実に稼")

# 名義分離(2026-08-06): kekka_mag名義の記事にミカタへの誘導リンクは置かない
FOOTER = """
---

**監修について**
この連載の監修者は、会社員時代は「下から数えた方が早い」くらいのできないやつだった人物です。
そこから結果を変えた方法は、特別な才能ではなく「うまくいっている人の真似と情報収集」だけでした。
その後1,000人規模の企業の役員を経て起業し、10年以上会社を経営しています。
このマガジンは、その「真似と情報収集」をAIで仕組み化したもの——という立場から、
全記事を実務目線で検品しています。

この記事はAIが下書きを作成し、人間が内容を確認してから公開しています。
記事中の事例・数字はすべて公表されている情報のリサーチにもとづくもので、
成果を保証するものではありません。出典は本文中に明記しています。

続きの研究はマガジン「結果の出し方がわかってしまうマガジン」に集めています。
フォローすると新しい研究レポートが届きます。
"""


def load_topics():
    with open(TOPICS_PATH, encoding="utf-8") as f:
        return json.load(f)


def pick_topic(topics, topic_id=None):
    for t in topics.get("queue", []):
        if topic_id:
            if t.get("id") == topic_id and t.get("status") == "pending":
                return t
        elif t.get("status") == "pending":
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
        "書き手は「AI編集部」(AIが下書きし人間が確認して出す編集部)。自分の実体験として"
        "語ってよいのは、自分たちが運営する地域向け情報メディア(AIが毎日データ収集・"
        "人間が検品して公開)の話だけ。媒体名・事業名・社名は一切書かない(名義分離)。"
        "それ以外の事例はすべて『公表されている事例のリサーチ』として出典つきで紹介する。",
    )
    return f"""あなたはnoteの有料記事シリーズを書くAI編集部です。
シリーズのコンセプトは「そのジャンルで結果を出した世の中の成功事例を、多い順にぜんぶ集めて、共通の型にする」。
読者への約束は「最高の時短」(自分で何百件も調べなくても、結果の出し方の型が1記事でわかる)。
ただし成果の保証はせず、「成功例の共通項」として提示する。この線を越えない。
noteの有料単発記事の下書きを1本書いてください。

# お題
- ジャンル: {t['genre']}
- タイトルの方向性: {t['title_hint']}
- 切り口: {t['angle']}
- 提案価格: {t.get('paid_price', 980)}円

# 使ってよいファクト(この一覧にない数字・事例・固有名詞の実績は書かない)
{facts_md}

# 書き手の立場
{persona}

# 想定読者
{t.get('reader', '沖縄・地方の中小企業経営者')}

# 構成ルール — 無料部分は「販売テンプレ12」(docs/note販売テンプレ12_黄金構成.md)の順に組む
無料部分(見出しは立てず自然な流れで):
1. 冒頭100文字で想定読者が「自分のことだ」と感じる掴み(悩みの言語化か意外な数字)
2. 誰のどんな悩みを解決する記事かを明示する
3. 読まない場合に知らないままになること/読んだ後にできるようになることの差を、事実ベースで見せる(不安を煽らない・成果を約束しない)
4. 自己紹介: 実運営の事実のみ(AIが毎日収集・人間が検品する地域向け情報メディアの運営)。媒体名・事業名は書かない。それ以外を実績として語らない。「経営歴10年以上の実務家が監修している」ことに1文だけ触れてよい(詳細は記事末尾の監修欄に自動で入るため本文で繰り返さない)
5. 執筆のきっかけを1〜2文のストーリーで
6. 有料部分の目次を2〜3行チラ見せして期待をつくる
7. オススメする人・しない人を正直に書き分ける(あえて絞る)
8. 価格の心理的ハードルを下げる一言(ランチ1回分など。安さの実感であって値引きの約束ではない)
9. 一番気になる問いを立てた直後に「====(ここから有料ライン)====」で寸止めして切る
※口コミ・特典・数量限定の枠は使わない(実在する声・実物・実際の決裁がある場合のみ人間が追記する)

有料部分:
{'''- 型②「失敗回避ぜんぶ盛り」: 「失敗事例・逆効果の実証の紹介(多い順) → 共通の落とし穴の型 → 回避の手順(チェックリスト形式)」の順
- 失敗した実在の企業・個人を晒す書き方をしない(固有名詞は報道済みの教訓事例のみ・構造の説明として)。不安を煽らない。「これをやらなければ大丈夫」という安全保証もしない''' if t.get('article_type') == 'shippai_kaihi' else '- 型①「成功例ぜんぶ盛り」: 「成功事例の紹介(多いほどよい) → そこから抽出できる共通の型 → 想定読者が明日から使える実務への翻訳」の順'}
- 事例を紹介するたびに、文中に出典(媒体名とURL)を明記する
- 冒頭の寸止めの問いには、有料部分の早い段階で答える(引っ張りすぎない)

全体:
- 有料部分の事例・節のタイトルは太字ではなく見出し(「### 事例1: 〜」「## 共通の型」等)で書く(noteで目次に載り、読みやすくなるため。太字は文中の強調のみに使う)
- 分量: 全体で3,500〜5,000字程度
- 文体: です・ます調。専門用語はやさしく翻訳する(ブランドトーン)

# 禁止事項(1つでも破ると不合格)
- 「必ず」「絶対」「誰でも」「楽して」「確実に稼げる」等の保証・誇大表現
- ファクト一覧にない数字・事例・実績を書くこと(推測で数字を埋めない)
- 他人の事例を自分の体験のように書くこと
- 収益額の約束(「あなたも月◯万円」型の表現)
- 絵文字の多用・不自然な箇条書きの乱発

# 推敲ループ(案B・2026-08-17適用: 出力前に必ず3周する。周回の過程は出力しない)
1周目【writer→humanizer】: 下書きを読み返し、AIっぽさを削る —
  定型フレーズ(「いかがでしたか」「〜ではないでしょうか」の乱発)・同じ文末の3連続・
  過剰な箇条書き・記号の乱用を、人が書いたような自然な文に直す。声に出して読める文だけ残す
2周目【hook批評】: タイトルと冒頭100文字だけを読者の目で見直す —
  タイトルは「想定読者が検索・一覧で見た瞬間に自分ごとになる言葉」か。冒頭は具体的な数字か
  意外性で始まっているか。弱ければこの2箇所だけ書き直す(本文との約束を裏切る釣りは禁止)
3周目【critic検品】: 禁止事項に1つずつ照らして最終チェック —
  保証・誇大表現ゼロ / ファクト一覧外の数字ゼロ / 全事例に出典 / 寸止めの問いに有料側で回答済み

# 出力形式
1行目に「# 」で始まるタイトル、その後に本文Markdownのみを出力。挨拶や説明は不要。"""


def build_xpack(title, t):
    # x_hookが未登録のパターンは出力しない(プレースホルダー指示文を書くと、
    # record_publication.pyがそのままX告知として抽出・実投稿してしまう。
    # 2026-08-23 お題13で実投稿に至った不具合の対策=ニドナシ台帳#16)
    price = t.get("paid_price", 980)
    patterns = [
        ("A", "数字フック", t.get("x_hook_a"), f"詳しくはnoteに書きました({price}円)→(記事URL)"),
        ("B", "学びの共有", t.get("x_hook_b"), "出典つきで整理しました→(記事URL)"),
        ("C", "問いかけ", t.get("x_hook_c"), "世界の公表事例を調べてまとめました→(記事URL)"),
    ]
    blocks = [
        f"【パターン{key}: {label}】\n{hook}\n{tail}"
        for key, label, hook, tail in patterns
        if hook
    ]
    if not blocks:
        # 【パターン】マーカーを含めない(record_publicationに抽出させないため)
        return (
            "⚠ X告知文が未登録のお題です。このままではX告知は自動投稿されません。\n"
            "  公開前に data/tanpatsu_topics.json の当該お題へ x_hook_a/b/c を登録して\n"
            "  再生成するか、公開後に x-post ワークフローで手動投稿してください。\n"
        )
    return "📣 X告知文パック(公開後、記事URLを足して使う。1日1本まで)\n\n" + "\n\n".join(blocks) + "\n"


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
    ap.add_argument("--id", dest="topic_id", default=None, help="お題IDを指定して生成(省略時はキュー先頭のpending)")
    args = ap.parse_args()

    topics = load_topics()
    t = pick_topic(topics, args.topic_id)
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
[マガジン「結果の出し方がわかってしまうマガジン」収載の単発/お題ID {t['id']}/提案価格{t.get('paid_price', 980)}円/有料ラインは本文中の「====」の位置に設定]
[公開時: noteでこのマガジンに追加すること]
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

    # 貼るだけ版(noteに編集作業ゼロで貼れる本文)と有料ライン見出しを自動生成
    paste_dir = os.path.join(BASE, "posts", "note", "paste")
    os.makedirs(paste_dir, exist_ok=True)
    lines = body.split("\n")
    paste_body = "\n".join(lines[1:]).lstrip("\n")  # タイトル行を除去
    paywall_heading = ""
    if "====" in paste_body:
        after = paste_body.split("====", 2)[-1]
        for ln in after.split("\n"):
            if ln.startswith("## "):
                paywall_heading = ln[3:].strip()
                break
        paste_body = re.sub(r"^====.*====\n*", "", paste_body, flags=re.M)
    paste_path = os.path.join(paste_dir, f"{t['id']}_hariduke_you.md")
    with open(paste_path, "w", encoding="utf-8") as f:
        f.write(paste_body + FOOTER)

    # アイキャッチ自動生成(PIL未導入環境ではスキップ)
    try:
        from generate_kekka_assets import make_eyecatch
        eyecatch_path = os.path.join(BASE, "assets", "kekka", f"eyecatch_{t['id']}.png")
        os.makedirs(os.path.dirname(eyecatch_path), exist_ok=True)
        make_eyecatch(title, eyecatch_path)
    except Exception as e:
        print(f"アイキャッチ生成スキップ: {e}", file=sys.stderr)

    t["status"] = "drafted"
    t["drafted_at"] = today
    with open(TOPICS_PATH, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)
        f.write("\n")

    if args.preview:
        print(f"stem={stem}")
        print(f"title={title}")
        print(f"topic_id={t['id']}")
        print(f"price={t.get('paid_price', 980)}")
        print(f"paywall={paywall_heading}")
    else:
        print(f"生成完了: {out_path} / 貼るだけ版: {paste_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
