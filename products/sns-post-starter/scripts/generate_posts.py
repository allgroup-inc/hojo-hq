#!/usr/bin/env python3
"""SNS投稿下書き生成(2026年版の発見ロジック対応)。

設計方針(2026年のSNSの現実に合わせている):
- ハッシュタグは「リーチ増加の裏技」ではなく「分類と検索の補助」。Instagramは
  実質5個上限のため、内容に直結する3〜5個だけを生成し、汎用メガタグは禁止
- 発見の主役は「ソーシャルSEO」= キャプション本文に、読者が実際に検索する
  キーワードを自然に含めること。特に冒頭80字が重視される
- 冒頭1行はフック(約125字で「…続きを読む」に切られる前提で、内容に忠実に惹きつける)
- 手順・リスト系のトピックはカルーセル(スライド)下書きも同時生成

機能:
- config/brand.yml の口調・NGワード・検索キーワード設定を毎回プロンプトに反映
- 生成後にプログラム側でも検証: NGワード / X文字数 / タグ数上限 / キャプション長
- 出力: output/posts_<日付>.csv / .md。成功した行は topics.csv に done を書き戻す

使い方:
  python scripts/generate_posts.py             # 通常実行(要 ANTHROPIC_API_KEY)
  python scripts/generate_posts.py --offline   # ダミー生成のテスト実行
"""
import argparse
import csv
import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TOPICS_FILE = ROOT / "input" / "topics.csv"
OUTPUT_DIR = ROOT / "output"

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

# 媒体別の上限(2026年時点。変更されることがあるので docs/FAQ 参照)
X_MAX_CHARS = 140          # 全角換算の安全ライン
IG_CAPTION_MAX = 2200      # Instagramキャプション上限
IG_HASHTAG_MAX = 5         # Instagramの実質上限(2025年〜)

POST_SCHEMA = {
    "type": "object",
    "properties": {
        "seo_keyword": {
            "type": "string",
            "description": "この投稿の主要検索キーワード(読者が実際に検索窓に入れる言葉を1つ。例: 那覇 パン屋 / 補助金 飲食店)"},
        "instagram_caption": {
            "type": "string",
            "description": "Instagram用キャプション。冒頭1行は約125字で切られる前提で、内容に忠実なフック(驚き・具体的な数字・共感のどれか)にする。seo_keywordを冒頭80字以内に自然に含める。改行を活かした読みやすい構成、最後にCTA"},
        "x_post": {
            "type": "string",
            "description": "X(旧Twitter)用の短文版。全角140字以内厳守。冒頭で惹きつける"},
        "hashtags": {
            "type": "array", "items": {"type": "string"},
            "description": "内容に直結するハッシュタグ3〜5個(#付き)。ニッチ〜中規模のタグを優先し、#love #instagood #fyp のような汎用メガタグは絶対に入れない"},
        "carousel_slides": {
            "type": "array", "items": {"type": "string"},
            "description": "このトピックが手順・リスト・ビフォーアフター等のカルーセル向きの場合のみ、スライド文言を5〜8枚(1枚目は表紙: フック+スワイプで得られることの約束、最後は保存を促す締め。1枚1メッセージ・短文)。カルーセル向きでなければ空配列"},
        "image_idea": {
            "type": "string",
            "description": "この投稿に添える画像・写真のアイデア(撮影指示レベルで具体的に)"},
    },
    "required": ["seo_keyword", "instagram_caption", "x_post", "hashtags",
                 "carousel_slides", "image_idea"],
    "additionalProperties": False,
}


def build_system_prompt(brand: dict) -> str:
    ng = "、".join(brand.get("ng_words", [])) or "(指定なし)"
    kw = "、".join(brand.get("seo_keywords", [])) or "(指定なし。トピックから推定)"
    return f"""あなたは「{brand.get('brand_name', '')}」のSNS担当です。

ブランド設定:
- ターゲット: {brand.get('audience', '一般')}
- トーン: {brand.get('tone', '自然体')}
- 話者イメージ: {brand.get('persona', '')}
- CTA(行動喚起): {brand.get('cta', '')}
- よく狙う検索キーワード群: {kw}

2026年の発見ロジック(厳守):
- 発見の主役はハッシュタグではなくキャプション内の検索キーワード。冒頭80字に自然に入れる
- ハッシュタグは内容の分類。3〜5個だけ、内容に直結するニッチ〜中規模タグを選ぶ
- 冒頭1行は内容に忠実なフック。内容が約束を果たせない誇張フックは禁止

厳守事項:
- 次の表現は絶対に使わない: {ng}
- 与えられた事実(note)にないことを書かない。効果・実績の誇張をしない
- 誇大広告・断定的な効能表現を避ける(景品表示法・薬機法に配慮)
- テンプレ臭い定型文ではなく、話者が自分の言葉で話している文章に"""


def generate(client, brand: dict, topic: str, note: str) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=build_system_prompt(brand),
        output_config={"format": {"type": "json_schema", "schema": POST_SCHEMA}},
        messages=[{"role": "user", "content":
                   f"次のトピックで投稿下書きを作ってください。\n\nトピック: {topic}\n盛り込む事実: {note or '(特になし)'}"}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("モデルが生成を拒否しました")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def offline_stub(topic: str) -> dict:
    return {
        "seo_keyword": "テスト キーワード",
        "instagram_caption": f"(オフラインテスト)「{topic}」のキャプションがここに生成されます。",
        "x_post": f"(オフラインテスト){topic}",
        "hashtags": ["#テスト"],
        "carousel_slides": [],
        "image_idea": "(オフラインテスト)",
    }


def validate_post(post: dict, brand: dict) -> list:
    """媒体別ルールとブランドルールの機械チェック。問題は文字列リストで返す。"""
    issues = []
    text_all = post["instagram_caption"] + post["x_post"] + " ".join(post["hashtags"])
    ng_hits = [w for w in brand.get("ng_words", []) if w and w in text_all]
    if ng_hits:
        issues.append(f"NGワード: {'、'.join(ng_hits)}")
    if len(post["x_post"]) > X_MAX_CHARS:
        issues.append(f"X文字数超過({len(post['x_post'])}字 > {X_MAX_CHARS})")
    if len(post["instagram_caption"]) > IG_CAPTION_MAX:
        issues.append(f"IGキャプション超過({len(post['instagram_caption'])}字)")
    slides = post.get("carousel_slides", [])
    if slides and not (2 <= len(slides) <= 10):
        issues.append(f"カルーセル枚数が不正({len(slides)}枚)")
    kw = post.get("seo_keyword", "").split()[0] if post.get("seo_keyword") else ""
    if kw and kw not in post["instagram_caption"][:120]:
        issues.append("ヒント: 検索キーワードがキャプション冒頭に入っていない")
    return issues


def cap_hashtags(post: dict, base_tags: list) -> None:
    """固定タグ+生成タグを重複排除し、Instagram上限(5個)に収める。"""
    merged = list(dict.fromkeys(base_tags + post["hashtags"]))
    post["hashtags"] = merged[:IG_HASHTAG_MAX]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    brand = yaml.safe_load((ROOT / "config" / "brand.yml").read_text(encoding="utf-8"))
    limit = int(brand.get("max_posts_per_run", 7))

    with TOPICS_FILE.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    todo = [r for r in rows if not (r.get("status") or "").strip()][:limit]
    if not todo:
        print("生成対象なし(input/topics.csv の status 空欄行がありません)")
        return 0

    client = None
    if not args.offline:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("エラー: ANTHROPIC_API_KEY が未設定です(テストは --offline)")
            return 1
        import anthropic
        client = anthropic.Anthropic()

    results = []
    for row in todo:
        topic = row["topic"].strip()
        print(f"生成中: {topic[:40]}")
        try:
            post = offline_stub(topic) if args.offline else generate(client, brand, topic, row.get("note", ""))
        except Exception as e:
            print(f"  ! 失敗(status空欄のまま残ります): {e}")
            continue
        cap_hashtags(post, brand.get("base_hashtags", []))
        issues = validate_post(post, brand)
        hard = [i for i in issues if not i.startswith("ヒント")]
        results.append({
            "topic": topic,
            "flag": f"要修正({' / '.join(hard)})" if hard else ("OK " + " ".join(i for i in issues if i.startswith("ヒント"))).strip(),
            **post,
        })
        row["status"] = "done"

    if not results:
        print("生成できた投稿がありません")
        return 1

    today = date.today().isoformat()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = OUTPUT_DIR / f"posts_{today}.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["topic", "flag", "seo_keyword", "instagram_caption", "x_post",
                         "hashtags", "carousel_slides", "image_idea"])
        for r in results:
            writer.writerow([r["topic"], r["flag"], r["seo_keyword"], r["instagram_caption"],
                             r["x_post"], " ".join(r["hashtags"]),
                             " / ".join(r["carousel_slides"]), r["image_idea"]])

    md_lines = [f"# 投稿下書き {today}", "",
                "確認して問題なければコピペで投稿してください。「要修正」フラグの投稿は必ず直すこと。", ""]
    for i, r in enumerate(results, 1):
        md_lines += [
            f"## {i}. {r['topic']}  —  {r['flag']}", "",
            f"検索キーワード: {r['seo_keyword']}", "",
            "**Instagram**", "", "```", r["instagram_caption"], "",
            " ".join(r["hashtags"]), "```", "",
            "**X**", "", "```", r["x_post"], "```", "",
        ]
        if r["carousel_slides"]:
            md_lines += ["**カルーセル案(1枚目=表紙)**", ""]
            md_lines += [f"{n}. {s}" for n, s in enumerate(r["carousel_slides"], 1)]
            md_lines += [""]
        md_lines += [f"**画像アイデア**: {r['image_idea']}", ""]
    (OUTPUT_DIR / f"posts_{today}.md").write_text("\n".join(md_lines), encoding="utf-8")

    # 成功した行にdoneを書き戻す
    with TOPICS_FILE.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"生成 {len(results)} 件 → output/posts_{today}.md / .csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
