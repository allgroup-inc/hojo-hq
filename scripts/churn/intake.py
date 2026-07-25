"""CSV取込：実列 → column_map → 正規化レコード。"""
from __future__ import annotations
import csv
import json

from .schema import normalize_record


def load_column_map(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_rows(csv_path):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_records(csv_path, column_map, as_of):
    return [normalize_record(row, column_map, as_of) for row in read_rows(csv_path)]
