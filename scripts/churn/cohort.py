"""早期解約率のコホート集計（契約月別）＝ 3%目標のスコアボード。

品質規律（churn-model-quality-gate）:
- 早期解約率は確定分（is_resolved）のみで算出。
- 観測中コホート（6ヶ月窓が未確定で生存者が定まらず率が跳ねる）は observing フラグを立て、
  全体率からも除外する（免疫時間／打ち切りバイアス回避）。
- 確定数が少ないコホート（< MIN_RELIABLE_N）は reference（参考）。
"""
from __future__ import annotations

from .config import MIN_RELIABLE_N

# 確定率（resolved/total）がこの値未満のコホートは「観測中（未確定）」とみなす
MATURE_RATIO = 0.8


def _ym(d):
    return f"{d.year}-{d.month:02d}"


def cohort_rows(records, as_of, mature_ratio=MATURE_RATIO, min_reliable=MIN_RELIABLE_N):
    groups = {}
    for r in records:
        ad = r.get("apply_date")
        if not ad:
            continue
        g = groups.setdefault(_ym(ad), {"total": 0, "resolved": 0, "churn": 0})
        g["total"] += 1
        if r.get("is_resolved"):
            g["resolved"] += 1
            g["churn"] += r.get("is_early_churn") or 0
    rows = []
    for ym in sorted(groups):
        g = groups[ym]
        maturity = g["resolved"] / g["total"] if g["total"] else 0.0
        rows.append({
            "ym": ym, "total": g["total"], "resolved": g["resolved"], "churn": g["churn"],
            "rate": (g["churn"] / g["resolved"]) if g["resolved"] else None,
            "maturity": maturity,
            "observing": maturity < mature_ratio,
            "reference": g["resolved"] < min_reliable,
        })
    return rows


def overall_rate(rows):
    """全体の早期解約率（観測中コホートを除いた成熟分のみ）。"""
    res = sum(r["resolved"] for r in rows if not r["observing"])
    churn = sum(r["churn"] for r in rows if not r["observing"])
    return {"resolved": res, "churn": churn, "rate": (churn / res) if res else 0.0}
