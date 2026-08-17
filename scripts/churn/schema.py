"""生CSV行 → 内部正規化レコード。成熟度・早期解約フラグまで計算する。"""
from __future__ import annotations
from datetime import date

from .config import AGE_BANDS, AMOUNT_EDGES, AMOUNT_LABELS, EARLY_CHURN_MONTHS
from .dates import has_reached_months, is_within_months
from .status import status_scope
from .unpaid import parse_unpaid, bin_unpaid_count


def bin_age(age):
    if age is None:
        return "不明"
    for lo, hi, label in AGE_BANDS:
        if lo <= age <= hi:
            return label
    return "不明"


def bin_amount(amount, edges=AMOUNT_EDGES):
    if amount is None:
        return "不明"
    for i, edge in enumerate(edges):
        if amount < edge:
            return AMOUNT_LABELS[i]
    return AMOUNT_LABELS[len(edges)]


def parse_date(value):
    if not value or not str(value).strip():
        return None
    text = str(value).strip().replace("/", "-")
    parts = text.split("-")
    if len(parts) != 3:
        raise ValueError(f"日付を解釈できません: {value!r}")
    y, m, d = (int(p) for p in parts)
    return date(y, m, d)


def parse_amount(value):
    if value is None:
        return None
    text = str(value).replace(",", "").replace("円", "").strip()
    if not text:
        return None
    return float(text)


def _get(raw, column_map, key):
    """column_map[key] で指す実列の値。マップに無ければ None。"""
    col = column_map.get(key)
    if col is None:
        return None
    return raw.get(col)


def normalize_record(raw, column_map, as_of):
    apply_date = parse_date(_get(raw, column_map, "apply_date"))
    cancel_date = parse_date(_get(raw, column_map, "cancel_date"))
    try:
        # 引落予定日は自由記述（「毎月27日」等）があり得る。解釈不能はNoneに落とし全読込を止めない
        debit_due = parse_date(_get(raw, column_map, "debit_due"))
    except ValueError:
        debit_due = None
    age_raw = _get(raw, column_map, "age")
    age = int(str(age_raw).strip()) if age_raw and str(age_raw).strip() else None
    amount = parse_amount(_get(raw, column_map, "amount"))

    is_early_churn = None
    is_resolved = False
    is_scoreable = False
    # 現ステータス（実データ）: docs/churn/現ステータス分類ルール.md
    status_val = _get(raw, column_map, "status")
    status_category = None
    in_scope = True
    excluded_reason = None
    date_missing = False
    payment_route = _get(raw, column_map, "payment_route")
    # Ⅳ列（口座振替の未収履歴）。未マップなら count=0 / band="0"
    up = parse_unpaid(_get(raw, column_map, "unpaid"))

    if status_val is not None and str(status_val).strip():
        sc = status_scope(status_val, apply_date, cancel_date, as_of, EARLY_CHURN_MONTHS)
        status_category = sc["category"]
        in_scope = sc["in_scope"]
        excluded_reason = sc["excluded_reason"]
        date_missing = sc["date_missing"]
        is_resolved = sc["is_resolved"]
        is_scoreable = sc["is_continuing"]
        if sc["is_resolved"]:
            is_early_churn = 1 if sc["is_early_churn"] else 0
        # 成立済など早期解約でない場合、着金日は解約日ではない → downstream用にNone化
        if sc["category"] != "早期解約":
            cancel_date = None
    elif cancel_date is not None and apply_date is not None:
        is_resolved = True
        is_early_churn = 1 if is_within_months(apply_date, cancel_date, EARLY_CHURN_MONTHS) else 0
    elif apply_date is not None:
        if has_reached_months(apply_date, as_of, EARLY_CHURN_MONTHS):
            is_resolved = True
            is_early_churn = 0  # 6ヶ月生存
        else:
            is_scoreable = True  # 継続中・6ヶ月未満 = これから手を打てる

    return {
        "customer_id": _get(raw, column_map, "customer_id"),
        "apply_id": _get(raw, column_map, "apply_id"),
        "apply_date": apply_date,
        "product": (_get(raw, column_map, "product") or "不明"),
        "channel": (_get(raw, column_map, "channel") or "不明"),
        "apply_form": (_get(raw, column_map, "apply_form") or "不明"),
        "amount": amount,
        "amount_band": bin_amount(amount),
        "age_band": bin_age(age),
        "gender": (_get(raw, column_map, "gender") or "不明"),
        "area": (_get(raw, column_map, "area") or "不明"),
        "agent_id": (_get(raw, column_map, "agent_id") or "不明"),
        "cancel_date": cancel_date,
        "cancel_reason": (_get(raw, column_map, "cancel_reason") or ""),
        # 予防トリガー用（口座普段使い / 初回引落結果 / 引落予定日）。欠損は既定値。
        "account_daily": (_get(raw, column_map, "account_daily") or ""),
        "debit_result": (_get(raw, column_map, "debit_result") or ""),
        "debit_due": debit_due,
        "is_early_churn": is_early_churn,
        "is_resolved": is_resolved,
        "is_scoreable": is_scoreable,
        # 現ステータス由来（実データ）。status列が無ければ status_category=None・in_scope=True
        "status_category": status_category,
        "in_scope": in_scope,
        "excluded_reason": excluded_reason,
        "date_missing": date_missing,
        "payment_route": payment_route,
        # Ⅳ列（未収履歴）由来。unpaid_band は要因（繰り返し未収＝高リスク）
        "unpaid_count": up["unpaid_count"],
        "unpaid_months": up["unpaid_months"],
        "unpaid_band": bin_unpaid_count(up["unpaid_count"]),
        "unpaid_contacted": up["contacted"],
        "unpaid_konbini": up["konbini_sent"],
        "unpaid_account_issue": up["account_issue"],
    }
