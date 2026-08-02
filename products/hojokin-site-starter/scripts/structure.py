#!/usr/bin/env python3
"""[2] 構造化: data/raw/pending/ の生データをClaude APIで config/schema.json の形に整形し、
data/items/ に保存する。処理済みの生データは data/raw/done/ に移動する。

正確性の設計(重要):
- 収集時に構造化データが取れている項目(prefill: 締切・上限額など)は、
  AIの出力を **prefillの値で上書き** する。数値・日付をAIに書かせない
- 原文から確認できない値は「要確認」と出力させ、断定させない
- 各アイテムには必ず出典URL(url)と取得日時(collected_at)が残る
"""
import json
import os
import shutil
import sys
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
PENDING_DIR = ROOT / "data" / "raw" / "pending"
DONE_DIR = ROOT / "data" / "raw" / "done"
ITEMS_DIR = ROOT / "data" / "items"

# 品質重視なら claude-opus-5(既定)。費用を抑えたい場合は
# 環境変数 ANTHROPIC_MODEL=claude-haiku-4-5 などで差し替え可能。
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5")

SYSTEM_PROMPT = """あなたは補助金・支援制度の情報整理の専門家です。与えられた原文から、指定されたスキーマに沿って情報を抽出します。

厳守事項:
- 原文に書かれていることだけを抽出する。推測・補完・誇張をしない
- 原文から確認できない項目は「要確認」とする(対象地域・実施機関も同様)
- 締切・金額・補助率・要件は特に慎重に。少しでも曖昧なら「要確認」
- 要約は経営者向けに専門用語をやさしく言い換える。ただし事実のみ、宣伝的表現は禁止
- 「もらえる」「必ず採択」のような断定・誇張表現は使わない"""


def structure_item(client: anthropic.Anthropic, schema: dict, raw: dict) -> dict:
    user_content = (
        f"情報源: {raw['source_name']}\n"
        f"URL: {raw['url']}\n"
        f"タイトル: {raw['title']}\n"
        f"公開日情報: {raw.get('published', '')}\n"
        f"--- 原文ここから ---\n{raw['body']}\n--- 原文ここまで ---"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user_content}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("モデルが処理を拒否しました(コンテンツ内容を確認してください)")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("エラー: 環境変数 ANTHROPIC_API_KEY が未設定です")
        return 1

    schema = json.loads((ROOT / "config" / "schema.json").read_text(encoding="utf-8"))
    schema.pop("$comment", None)

    pending = sorted(PENDING_DIR.glob("*.json")) if PENDING_DIR.exists() else []
    if not pending:
        print("処理対象なし(data/raw/pending/ が空です)")
        return 0

    ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    client = anthropic.Anthropic()

    ok, failed = 0, 0
    for path in pending:
        raw = json.loads(path.read_text(encoding="utf-8"))
        print(f"構造化中: {raw['title'][:50]}")
        try:
            data = structure_item(client, schema, raw)
        except Exception as e:
            print(f"  ! 失敗(次回再試行されます): {e}")
            failed += 1
            continue
        # 機械転記優先: 収集時に確定している値でAI出力を上書きする
        data.update({k: v for k, v in raw.get("prefill", {}).items() if v})
        item = {
            "id": raw["id"],
            "source_id": raw["source_id"],
            "source_name": raw["source_name"],
            "url": raw["url"],
            "collected_at": raw.get("collected_at", ""),
            **data,
        }
        (ITEMS_DIR / f"{raw['id']}.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=1), encoding="utf-8")
        shutil.move(str(path), DONE_DIR / path.name)
        ok += 1

    print(f"構造化 完了 {ok} 件 / 失敗 {failed} 件")
    return 0  # 失敗分はpendingに残り次回リトライ


if __name__ == "__main__":
    sys.exit(main())
