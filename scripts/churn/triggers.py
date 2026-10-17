"""予防トリガー：初回引落"前"の口座確認(A)＋支払い挙動ウォッチ(B)。

早期失効の最大要因＝初回引落の失敗を「起こる前に」潰し、以降も毎月見張る
（docs/churn/予防トリガー設計.md）。継続中(is_scoreable)の契約だけを対象にする。

- B 支払い挙動ウォッチ: 初回引落結果が「不着」→最優先 / 「遅延」→高優先。
- A 初回引落"前"の口座確認: まだ引落されておらず(結果なし)、引落予定日が近い未来で、
  口座が「いいえ／未確認」の契約 → 引落前に口座確認。
"""
from __future__ import annotations
from datetime import timedelta

from .config import PRE_DEBIT_LEAD_DAYS, INITIAL_CONTACT_DAYS
from .effect_learning import _contacts_index

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


def _has_contact_since(record, idx, as_of):
    """契約日以降・as_of以前にこの契約への接触があるか。突合は (顧客ID, apply_id) 優先。"""
    by_id, by_date = idx
    cs = by_id.get((record.get("customer_id"), record.get("apply_id")))
    if cs is None:
        cs = by_date.get((record.get("customer_id"), record.get("apply_date")), [])
    ap = record.get("apply_date")
    for c in cs:
        cd = c.get("contact_date")
        if cd is not None and (ap is None or cd >= ap) and cd <= as_of:
            return True
    return False


def initial_contact_trigger(record, contacts_index, as_of, days=INITIAL_CONTACT_DAYS):
    """契約後 days 日以内・未接触の継続契約なら「初動」。保全は早いほど効く。

    contacts_index は effect_learning._contacts_index(contacts) の戻り値。
    """
    if not record.get("is_scoreable"):
        return None
    ap = record.get("apply_date")
    if ap is None:
        return None
    age_days = (as_of - ap).days
    if 0 <= age_days <= days and not _has_contact_since(record, contacts_index, as_of):
        return "初動"
    return None


def initial_contact_candidates(records, contacts, as_of, days=INITIAL_CONTACT_DAYS):
    """(record, "初動") の並びを、初動トリガーが立つものだけ返す。"""
    idx = _contacts_index(contacts)
    out = []
    for r in records:
        if initial_contact_trigger(r, idx, as_of, days) is not None:
            out.append((r, "初動"))
    return out


def _recent_streak(unpaid_months, as_of):
    """as_of 直近から連続する未収月数（年跨ぎ対応）。年欠損の月(year=None)は timeline に載せない。"""
    idx = {y * 12 + (m - 1) for (y, m) in unpaid_months if y}
    cur = as_of.year * 12 + (as_of.month - 1)
    s = 0
    while (cur - 1 - s) in idx:   # 直近月(as_of-1)から遡って連続
        s += 1
    return s


def unpaid_trigger(record, as_of):
    """継続契約の未収連鎖トリガー。3ヶ月連続=未払消滅目前（4ヶ月連続で消滅）、2ヶ月連続=未収2連続。

    「未払消滅（4ヶ月連続未払で契約消滅）を消滅前に止める」ための先回り検知（docs/churn/連動アイデア）。
    未払消滅は**契約テニュアに関係なく**起きるため、6ヶ月未満(is_scoreable)に限定せず、継続中の契約
    （現ステータス＝継続、または status 無しの合成/従来レコードでは is_scoreable）を広く対象にする。
    """
    active = record.get("is_scoreable") or record.get("status_category") == "継続"
    if not active:
        return None
    streak = _recent_streak(record.get("unpaid_months", []), as_of)
    if streak >= 3:
        return "未払消滅目前"
    if streak == 2:
        return "未収2連続"
    return None
