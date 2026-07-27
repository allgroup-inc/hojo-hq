"""顧客の束ね：申込み＋接触履歴を顧客IDで結合し、プロファイルを作る。"""
from __future__ import annotations

from .score import score_record
from .config import FOLLOWUP_DAYS, ADDITIONAL_GUIDANCE_KINDS

_BAND_RANK = {"low": 0, "med": 1, "high": 2}


def highest_band(bands):
    ranked = [b for b in bands if b in _BAND_RANK]
    if not ranked:
        return None
    return max(ranked, key=lambda b: _BAND_RANK[b])


def _scored_application(app, model):
    out = dict(app)
    if app.get("is_scoreable"):
        s = score_record(app, model)
        out["risk"] = s["risk"]
        out["band"] = s["band"]
        out["hit_factors"] = s["hit_factors"]
    else:
        out["risk"] = None
        out["band"] = None
        out["hit_factors"] = []
    return out


def build_customers(app_records, interaction_records, model, as_of):
    groups = {}
    for app in app_records:
        cid = app.get("customer_id")
        if not cid:  # 未紐付(顧客ID欠損)は束ねない
            continue
        groups.setdefault(cid, {"apps": [], "inters": []})["apps"].append(app)
    for it in interaction_records:
        cid = it.get("customer_id")
        if not cid:
            continue
        groups.setdefault(cid, {"apps": [], "inters": []})["inters"].append(it)

    customers = {}
    for cid, g in groups.items():
        apps = [_scored_application(a, model) for a in g["apps"]]
        inters = sorted(
            [i for i in g["inters"] if i.get("date")],
            key=lambda i: i["date"], reverse=True)
        active = [a for a in apps if a.get("is_scoreable")]
        max_band = highest_band([a["band"] for a in active if a.get("band")])
        last_contact = inters[0]["date"] if inters else None
        needs_followup = (
            max_band == "high"
            and (last_contact is None or (as_of - last_contact).days > FOLLOWUP_DAYS))
        latest_attr = g["apps"][-1] if g["apps"] else {}
        customers[cid] = {
            "customer_id": cid,
            "age_band": latest_attr.get("age_band", "不明"),
            "gender": latest_attr.get("gender", "不明"),
            "area": latest_attr.get("area", "不明"),
            "n_applications": len(apps),
            "n_active": len(active),
            "n_cancelled": sum(1 for a in apps if a.get("cancel_date")),
            "n_early_churn": sum(1 for a in apps if a.get("is_early_churn") == 1),
            "n_additional_guidance": sum(1 for i in g["inters"]
                                         if i.get("kind") in ADDITIONAL_GUIDANCE_KINDS),
            "applications": apps,
            "interactions": inters,
            "max_risk_band": max_band,
            "last_contact_date": last_contact,
            "needs_followup": needs_followup,
        }
    return customers
