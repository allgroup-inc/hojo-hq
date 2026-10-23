#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フィールド保持スクリプト（update.yml ブロッカー #1 解決）

背景：
- update.yml が毎日4回、subsidies.json を fetch_jgrants.py と fetch_local.py で再生成
- この過程で、既存の verified / ig_priority / ig_template 等が消える
- Sunday 18:00 の IG 自動投稿生成がこれらのフィールドに依存

対策：
- 既存の data/subsidies.json から verified と ig_* フィールドを抽出
- 新しく生成された data/subsidies.json にそれらをマージ
- スクリプトの実行順: fetch_jgrants.py → fetch_local.py → preserve_fields.py

実行タイミング：
- update.yml の Fetch local (自治体) data の直後に実行
- 当日の変更を検出した場合のみ再生成
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
SUBSIDIES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "subsidies.json")
BACKUP_SUFFIX = ".backup"


def load_json(path: str) -> dict:
    """JSON ファイルを安全に読み込む"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[error] Failed to load {path}: {e}", file=sys.stderr)
        return {}


def save_json(path: str, data: dict) -> bool:
    """JSON ファイルを安全に保存"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return True
    except Exception as e:
        print(f"[error] Failed to save {path}: {e}", file=sys.stderr)
        return False


def preserve_fields():
    """
    既存の data/subsidies.json から verified / ig_* フィールドを抽出し、
    新しく生成された同ファイルにマージ
    """
    # ステップ1: バックアップから既存フィールドを抽出
    backup_path = SUBSIDIES_PATH + BACKUP_SUFFIX
    old_data = load_json(backup_path)
    old_items = {item["id"]: item for item in old_data.get("items", [])}

    # ステップ2: 新しく生成されたファイルを読み込み
    new_data = load_json(SUBSIDIES_PATH)
    if not new_data or "items" not in new_data:
        print("[warn] No new data to process", file=sys.stderr)
        return False

    # ステップ3: 既存フィールドをマージ
    preserved_count = 0
    for item in new_data.get("items", []):
        item_id = item.get("id")
        if item_id and item_id in old_items:
            old_item = old_items[item_id]
            # 保持すべきフィールド
            for field in ["verified", "ig_priority", "ig_template", "ig_example_industry",
                          "ig_before_amount", "ig_after_amount", "ig_exclude"]:
                if field in old_item and field not in item:
                    item[field] = old_item[field]
                elif field in old_item:
                    # 既に存在する場合、古い値を保持（fetch では上書きしない）
                    pass
            preserved_count += 1

    # ステップ4: 変更があったかチェック
    if preserved_count == 0:
        print("[info] No fields to preserve (all items are new)", file=sys.stderr)
    else:
        print(f"[info] Preserved fields for {preserved_count} items", file=sys.stderr)

    # ステップ5: 保存
    if save_json(SUBSIDIES_PATH, new_data):
        print(f"[success] Preserved {preserved_count} items' existing fields", file=sys.stderr)
        return True
    return False


def main():
    print(f"[{datetime.now(JST).isoformat()}] preserve_fields.py started", file=sys.stderr)

    # バックアップが存在しない場合は、現在のファイルをバックアップ
    backup_path = SUBSIDIES_PATH + BACKUP_SUFFIX
    if not os.path.exists(backup_path):
        current_data = load_json(SUBSIDIES_PATH)
        if current_data:
            save_json(backup_path, current_data)
            print(f"[info] Created backup: {backup_path}", file=sys.stderr)

    # フィールド保持処理
    success = preserve_fields()

    # バックアップを現在のファイルで更新（次回実行用）
    new_data = load_json(SUBSIDIES_PATH)
    if new_data:
        save_json(backup_path, new_data)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
