#!/usr/bin/env python3
"""SNS投稿下書き生成。

- input/topics.csv の status が空の行を対象に、Claude APIで下書きを生成
- config/brand.yml の口調・NGワード設定を毎回プロンプトに含めるのでトーンが固定される
- 生成後にNGワードをプログラム側でも再チェック(含まれていたら「要修正」フラグ)
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

POST_SCHEMA = {
    "type": "object",
    "properties": {
        "instagram_caption": {"type": "string",
                              "description": "Instagram用キャプション。冒頭1行で惹きつけ、改行を活かした読みやすい構成。最後にCTA"},
        "x_post": {"type": "string",
                   "description": "X(旧Twitter)用の短文版。全角140字以内"},
        "hashtags": {"type": "array", "items": {"type": "string"},
                     "description": "内容に合ったハッシュタグ5〜10個(#付き)"},
        "image_idea": {"type": "string",
                       "description": "この投稿に添える画像・写真のアイデア(撮影指示レベルで具体的に)"},
    },
    "required": ["instagram_caption", "x_post", "hashtags", "image_idea"],
    "additionalProperties": False,
}


def build_system_prompt(brand: dict) -> str:
    ng = "、".join(brand.get("ng_words", [])) or "(指定なし)"
    return f"""あなたは「{brand.get('brand_name', '')}」のSNS担当です。

ブランド設定:
- ターゲット: {brand.get('audience', '一般')}
- トーン: {brand.get('tone', '自然体')}
- 話者イメージ: {brand.get('persona', '')}
- CTA(行動喚起): {brand.get('cta', '')}

厳守事項:
- 次の表現は絶対に使わない: {ng}
- 与えられた事実(note)にないことを書かない。効果・実績の誇張をしない
- 誇大広告・断定的な効能表現を避ける(景品表示法・薬機法に配慮)
- テンプレ臭い定型文ではなく、話者が自分の言葉で話している文章に"""


def generate(client, brand: dict, topic: str, note: str) -> dict:
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
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
        "instagram_caption": f"(オフラインテスト)「{topic}」のキャプションがここに生成されます。",
        "x_post": f"(オフラインテスト){topic}",
        "hashtags": ["#テスト"],
        "image_idea": "(オフラインテスト)",
    }


def ng_check(post: dict, ng_words: list) -> list:
    text = post["instagram_caption"] + post["x_post"] + " ".join(post["hashtags"])
    return [w for w in ng_words if w and w in text]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    brand = yaml.safe_load((ROOT / "config" / "brand.yml").read_text(encoding="utf-8"))
    limit = int(brand.get("max_posts_per_run", 7))
    base_tags = brand.get("base_hashtags", [])

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
        post["hashtags"] = list(dict.fromkeys(base_tags + post["hashtags"]))
        hits = ng_check(post, brand.get("ng_words", []))
        results.append({
            "topic": topic,
            "flag": f"要修正(NGワード: {'、'.join(hits)})" if hits else "OK",
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
        writer.writerow(["topic", "flag", "instagram_caption", "x_post", "hashtags", "image_idea"])
        for r in results:
            writer.writerow([r["topic"], r["flag"], r["instagram_caption"],
                             r["x_post"], " ".join(r["hashtags"]), r["image_idea"]])

    md_lines = [f"# 投稿下書き {today}", "",
                "確認して問題なければコピペで投稿してください。「要修正」フラグの投稿は必ず直すこと。", ""]
    for i, r in enumerate(results, 1):
        md_lines += [
            f"## {i}. {r['topic']}  —  {r['flag']}", "",
            "**Instagram**", "", "```", r["instagram_caption"], "",
            " ".join(r["hashtags"]), "```", "",
            "**X**", "", "```", r["x_post"], "```", "",
            f"**画像アイデア**: {r['image_idea']}", "",
        ]
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
