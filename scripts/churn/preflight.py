"""投入前チェック（preflight）＝ 実データを入れる前の“行かない検査”。

実CSVの見出しと column_map の突合（必須キー・対応列の欠落）、日付のパース可否、
成熟/継続中/未紐付の件数を出す。**顧客の値は出力しない**（集計と列名のみ）。

churn-pii-guard: レポートに個人の値を含めない。実データでの実行は統制環境で・審査後。
"""
from __future__ import annotations
import csv

from .intake import read_rows
from .schema import parse_date, normalize_record
from .config import ACCOUNT_DAILY_DOMAIN, FORBIDDEN_NAME_KEYS

# パイプラインに最低限必要なキー（予防用の debit_* は任意）
REQUIRED_KEYS = ["customer_id", "apply_date", "cancel_date", "product", "channel",
                 "apply_form", "amount", "age", "gender", "area", "agent_id"]
_DATE_KEYS = ["apply_date", "cancel_date", "debit_due"]


def _headers(csv_path):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f), [])


def preflight_report(csv_path, column_map, as_of, required_keys=REQUIRED_KEYS):
    headers = _headers(csv_path)
    missing_keys = [k for k in required_keys if k not in column_map]
    missing_columns = [column_map[k] for k in required_keys
                       if k in column_map and column_map[k] not in headers]

    rows = read_rows(csv_path)
    n_total = len(rows)
    cust_col = column_map.get("customer_id")
    n_unlinked = sum(1 for r in rows if not (r.get(cust_col) or "").strip()) if cust_col else n_total

    # 日付パス可否（非空で解釈できない件数）
    fails = {}
    for key in _DATE_KEYS:
        col = column_map.get(key)
        c = 0
        if col:
            for r in rows:
                v = r.get(col)
                if v and str(v).strip():
                    try:
                        parse_date(v)
                    except ValueError:
                        c += 1
        fails[key] = c

    # 前提: 顧客名は持ち込まずID管理。氏名系キーのマッピングは門前で禁止（データ最小化）
    forbidden_name_keys = [k for k in column_map
                           if str(k).strip().lower() in FORBIDDEN_NAME_KEYS]

    core_dates_ok = fails["apply_date"] == 0 and fails["cancel_date"] == 0
    ok = (not missing_keys and not missing_columns and core_dates_ok
          and not forbidden_name_keys)

    # 口座“普段使い”フラグの想定外値（#142 項目4）。件数だけ数える（値は出さない・okは落とさない）
    acc_col = column_map.get("account_daily")
    account_flag_unexpected = 0
    if acc_col:
        for r in rows:
            v = (r.get(acc_col) or "").strip()
            if v and v not in ACCOUNT_DAILY_DOMAIN:
                account_flag_unexpected += 1

    n_resolved = n_scoreable = None
    if ok:
        recs = [normalize_record(r, column_map, as_of) for r in rows]
        n_resolved = sum(1 for r in recs if r.get("is_resolved"))
        n_scoreable = sum(1 for r in recs if r.get("is_scoreable"))

    return {
        "ok": ok,
        "missing_keys": missing_keys,
        "missing_columns": missing_columns,
        "forbidden_name_keys": forbidden_name_keys,
        "date_parse_fails": fails,
        "n_total": n_total,
        "n_unlinked": n_unlinked,
        "n_resolved": n_resolved,
        "n_scoreable": n_scoreable,
        "account_flag_unexpected": account_flag_unexpected,
    }
