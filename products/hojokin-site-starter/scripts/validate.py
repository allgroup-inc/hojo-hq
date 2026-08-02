#!/usr/bin/env python3
"""[3] 品質ゲート: data/items/ の構造化データを検証し、公開用の data/public/items.json を作る。

- スキーマの必須項目がすべて埋まっているかチェック
- date(締切)は YYYY-MM-DD /「随時」/「要確認」のみ許可
- 出典URL(url)のないアイテムは公開しない(掲載保留=隔離)
- 不合格アイテムは data/quarantine/ に隔離(ログで理由を表示)
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ITEMS_DIR = ROOT / "data" / "items"
PUBLIC_FILE = ROOT / "data" / "public" / "items.json"
QUARANTINE_DIR = ROOT / "data" / "quarantine"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_SPECIAL = ("要確認", "随時")


def problems(item: dict, required: list) -> list:
    issues = []
    for key in required:
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"必須項目 '{key}' が空")
    if not (item.get("url") or "").startswith(("http://", "https://")):
        issues.append("出典URLがない(原文に当たれない情報は公開しない)")
    date = item.get("date", "")
    if date and date not in DATE_SPECIAL and not DATE_RE.match(date):
        issues.append(f"date の形式が不正: {date!r}(YYYY-MM-DD /「随時」/「要確認」)")
    return issues


def sort_key(item: dict):
    """締切が近い順。日付なし(随時/要確認)は後ろ、締切の後ろには置かない。"""
    date = item.get("date", "")
    if DATE_RE.match(date or ""):
        return (0, date)
    return (1, "9999-99-99")


def main() -> int:
    schema = json.loads((ROOT / "config" / "schema.json").read_text(encoding="utf-8"))
    required = schema.get("required", [])

    items, quarantined = [], 0
    for path in sorted(ITEMS_DIR.glob("*.json")) if ITEMS_DIR.exists() else []:
        item = json.loads(path.read_text(encoding="utf-8"))
        issues = problems(item, required)
        if issues:
            QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), QUARANTINE_DIR / path.name)
            quarantined += 1
            print(f"隔離: {item.get('title', path.name)[:50]}")
            for issue in issues:
                print(f"  - {issue}")
            continue
        items.append(item)

    items.sort(key=sort_key)

    PUBLIC_FILE.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"公開データ更新: {len(items)} 件(隔離 {quarantined} 件)→ {PUBLIC_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
