"""予防トリガー：初回引落"前"の口座確認(A)＋支払い挙動ウォッチ(B)。

早期失効の最大要因＝初回引落の失敗を「起こる前に」潰し、以降も毎月見張る
（docs/churn/予防トリガー設計.md）。継続中(is_scoreable)の契約だけを対象にする。

- B 支払い挙動ウォッチ: 初回引落結果が「不着」→最優先 / 「遅延」→高優先。
- A 初回引落"前"の口座確認: まだ引落されておらず(結果なし)、引落予定日が近い未来で、
  口座が「いいえ／未確認」の契約 → 引落前に口座確認。
"""
from __future__ import annotations
from datetime import timedelta

from .config import PRE_DEBIT_LEAD_DAYS

_ACCOUNT_PROBLEM = ("いいえ", "未確認")


def prevention_trigger(record, as_of, lead_days=PRE_DEBIT_LEAD_DAYS):
    """継続中レコードの予防トリガー種別を返す（無ければ None）。"""
    if not record.get("is_scoreable"):
        return None
    debit = record.get("debit_result") or ""
    if debit == "不着":
        return "不着"
    if debit == "遅延":
        return "遅延"
    # 引落前（結果なし）× 口座に問題 × 予定日が [as_of, as_of+lead] に入る
    if debit == "" and record.get("account_daily") in _ACCOUNT_PROBLEM:
        due = record.get("debit_due")
        if due is not None and as_of <= due <= as_of + timedelta(days=lead_days):
            return "口座確認"
    return None


def prevention_candidates(records, as_of, lead_days=PRE_DEBIT_LEAD_DAYS):
    """(record, trigger) の並びを、トリガーが立つものだけ返す。"""
    out = []
    for r in records:
        t = prevention_trigger(r, as_of, lead_days)
        if t is not None:
            out.append((r, t))
    return out
