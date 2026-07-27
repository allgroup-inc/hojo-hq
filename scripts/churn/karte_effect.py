"""保全の効果測定：申込後に保全接触があった群/なかった群で実早期解約率を比較。"""
from __future__ import annotations

from .config import MIN_RELIABLE_N


def was_contacted(customer_id, apply_date, interactions_by_cid, kinds, within_days,
                   cancel_date=None):
    if apply_date is None:
        return False
    for it in interactions_by_cid.get(customer_id, []):
        d = it.get("date")
        if d is None or it.get("kind") not in kinds:
            continue
        if d < apply_date:
            continue
        delta = (d - apply_date).days
        if delta > within_days:
            continue
        # 免疫時間バイアス対策：解約後の接触は「保全接触あり」に数えない
        if cancel_date is not None and d > cancel_date:
            continue
        return True
    return False


def contact_effect(app_records, interaction_records, kinds=("架電", "案内", "追加案内"),
                   within_days=90):
    by_cid = {}
    for it in interaction_records:
        cid = it.get("customer_id")
        if cid:
            by_cid.setdefault(cid, []).append(it)

    contacted, not_contacted = [], []
    for a in app_records:
        cid = a.get("customer_id")
        if not cid or not a.get("is_resolved"):
            continue
        if was_contacted(cid, a.get("apply_date"), by_cid, kinds, within_days,
                          cancel_date=a.get("cancel_date")):
            contacted.append(a)
        else:
            not_contacted.append(a)

    def rate(group):
        return (sum(x["is_early_churn"] for x in group) / len(group)) if group else 0.0

    cr, nr = rate(contacted), rate(not_contacted)
    n_contacted, n_not_contacted = len(contacted), len(not_contacted)
    reference = (n_contacted < MIN_RELIABLE_N) or (n_not_contacted < MIN_RELIABLE_N)
    return {"contacted_rate": cr, "not_contacted_rate": nr, "diff": cr - nr,
            "n_contacted": n_contacted, "n_not_contacted": n_not_contacted,
            "reference": reference}
