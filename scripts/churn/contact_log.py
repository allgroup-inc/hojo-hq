"""保全アクションログ（結果記録）の取込。

列: 顧客ID・契約日・接触日・対応内容・結果区分・顧客反応（column_mapで対応づけ）。
訪問保全の対話ログ拡張（任意）: 接触手段(medium=架電/訪問)・懸念(concern)・返し方/対話内容(approach)・
次アクション(next_action)。主観を減らすため選択式タグ中心が望ましい（docs/churn/訪問保全と教育ループ設計）。
クローズドループ（docs/churn/クローズドループ設計.md）の入力。実データは private/ 限定・審査後。
"""
from __future__ import annotations
import csv
import os

from .schema import parse_date


def _get(row, cmap, key):
    col = cmap.get(key)
    return row.get(col) if col else None


# 追記時の列の並び（system key）。column_map にあるものだけ、この順で列を作る。
_WRITE_ORDER = ["customer_id", "apply_id", "apply_date", "contact_date", "medium",
                "action", "concern", "approach", "result", "reaction", "next_action"]


def append_contact(path, column_map, values):
    """対応記録を1件、ログCSVに追記する（無ければヘッダ付きで新規作成）。

    保全コンソール（記録一体）の書き込み口。values は system key の dict、列名は column_map で対応。
    churn-pii-guard: 実データの出力先は private/ 限定・統制環境。公開リポには置かない。
    """
    keys = [k for k in _WRITE_ORDER if k in column_map]
    header = [column_map[k] for k in keys]
    exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(header)
        w.writerow([str(values.get(k, "") or "") for k in keys])


def load_contacts(path, column_map):
    """保全ログCSV → 正規化した接触レコードの並び。日付はパースする。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for row in rows:
        out.append({
            "customer_id": _get(row, column_map, "customer_id"),
            "apply_id": _get(row, column_map, "apply_id"),
            "apply_date": parse_date(_get(row, column_map, "apply_date")),
            "contact_date": parse_date(_get(row, column_map, "contact_date")),
            "action": (_get(row, column_map, "action") or ""),
            "result": (_get(row, column_map, "result") or ""),
            "reaction": (_get(row, column_map, "reaction") or ""),
            # 対話ログ拡張（任意・未マップなら空）
            "medium": (_get(row, column_map, "medium") or ""),
            "concern": (_get(row, column_map, "concern") or ""),
            "approach": (_get(row, column_map, "approach") or ""),
            "next_action": (_get(row, column_map, "next_action") or ""),
        })
    return out
