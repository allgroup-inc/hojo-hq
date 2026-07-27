"""保全の効果測定：申込後に保全接触があった群/なかった群で実早期解約率を比較。"""
from __future__ import annotations


def was_contacted(customer_id, apply_date, interactions_by_cid, kinds, within_days):
    if apply_date is None:
        return False
    for it in interactions_by_cid.get(customer_id, []):
        d = it.get("date")
        if d is None or it.get("kind") not in kinds:
            continue
        delta = (d - apply_date).days
        if 0 <= delta <= within_days:
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
        if was_contacted(cid, a.get("apply_date"), by_cid, kinds, within_days):
            contacted.append(a)
        else:
            not_contacted.append(a)

    def rate(group):
        return (sum(x["is_early_churn"] for x in group) / len(group)) if group else 0.0

    cr, nr = rate(contacted), rate(not_contacted)
    return {"contacted_rate": cr, "not_contacted_rate": nr, "diff": cr - nr,
            "n_contacted": len(contacted), "n_not_contacted": len(not_contacted)}
