"""保全アクションログ（結果記録）の取込。

列: 顧客ID・契約日・接触日・対応内容・結果区分・顧客反応（column_mapで対応づけ）。
クローズドループ（docs/churn/クローズドループ設計.md）の入力。実データは private/ 限定・審査後。
"""
from __future__ import annotations
import csv

from .schema import parse_date


def _get(row, cmap, key):
    col = cmap.get(key)
    return row.get(col) if col else None


def load_contacts(path, column_map):
    """保全ログCSV → 正規化した接触レコードの並び。日付はパースする。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for row in rows:
        out.append({
            "customer_id": _get(row, column_map, "customer_id"),
            "apply_date": parse_date(_get(row, column_map, "apply_date")),
            "contact_date": parse_date(_get(row, column_map, "contact_date")),
            "action": (_get(row, column_map, "action") or ""),
            "result": (_get(row, column_map, "result") or ""),
            "reaction": (_get(row, column_map, "reaction") or ""),
        })
    return out
