"""接触履歴の取込：実列 → interaction_column_map → 正規化レコード。"""
from __future__ import annotations

from .schema import parse_date
from .intake import read_rows
from .config import INTERACTION_KIND_MAP


def normalize_kind(raw_kind):
    if raw_kind is None or not str(raw_kind).strip():
        return "その他"
    key = str(raw_kind).strip()
    return INTERACTION_KIND_MAP.get(key, key)


def _get(raw, imap, key):
    col = imap.get(key)
    return raw.get(col) if col is not None else None


def normalize_interaction(raw, imap):
    return {
        "customer_id": _get(raw, imap, "customer_id"),
        "date": parse_date(_get(raw, imap, "date")),
        "kind": normalize_kind(_get(raw, imap, "kind")),
        "agent": (_get(raw, imap, "agent") or "不明"),
        "content": (_get(raw, imap, "content") or ""),
        "memo": (_get(raw, imap, "memo") or ""),
    }


def load_interactions(csv_path, imap):
    return [normalize_interaction(row, imap) for row in read_rows(csv_path)]
