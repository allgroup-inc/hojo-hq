"""効果測定 → 学習（クローズドループ後半）。

- 効果測定: 保全接触あり/なしで早期解約率を比較。ただし成熟契約のみ・解約前の接触のみを
  「あり」に数える（打ち切り／免疫時間バイアス回避）。単純比較は当てにならない前提で、
  本番は段階導入で因果を測る（docs/churn/クローズドループ設計.md / churn-retention-ops）。
- 学習: 対応内容ごとの早期解約率を並べ「効いた一手」を出す。母数不足は「参考」。

いずれも成熟実績（is_resolved かつ契約が mature_before より前）に限定する。
"""
from __future__ import annotations

from .config import MIN_RELIABLE_N


def _mature_resolved(records, mature_before):
    return [r for r in records if r.get("is_resolved") and r.get("apply_date")
            and r["apply_date"] < mature_before]


def _contacts_index(contacts):
    idx = {}
    for c in contacts:
        idx.setdefault((c.get("customer_id"), c.get("apply_date")), []).append(c)
    return idx


def _qualifying_actions(record, idx):
    """解約前の接触のみ（免疫時間除外）の対応内容リストを返す。"""
    cs = idx.get((record.get("customer_id"), record.get("apply_date")), [])
    cancel = record.get("cancel_date")
    out = []
    for c in cs:
        cd = c.get("contact_date")
        if cd is None:
            continue
        if cancel is None or cd < cancel:   # 解約後の接触は数えない
            out.append(c.get("action") or "")
    return out


def _rate(recs):
    return (sum(r.get("is_early_churn") or 0 for r in recs) / len(recs)) if recs else 0.0


def effect(records, contacts, mature_before, min_reliable=MIN_RELIABLE_N):
    idx = _contacts_index(contacts)
    contacted, not_contacted = [], []
    for r in _mature_resolved(records, mature_before):
        (contacted if _qualifying_actions(r, idx) else not_contacted).append(r)
    rc, rn = _rate(contacted), _rate(not_contacted)
    return {
        "n_c": len(contacted), "rate_c": rc,
        "n_n": len(not_contacted), "rate_n": rn, "diff": rc - rn,
        "reference": min(len(contacted), len(not_contacted)) < min_reliable,
    }


def learning(records, contacts, mature_before, min_reliable=MIN_RELIABLE_N):
    """対応内容ごとの早期解約率（低い＝効いた順）。1レコードに複数の一手があれば各々に計上。"""
    idx = _contacts_index(contacts)
    per = {}
    for r in _mature_resolved(records, mature_before):
        churn = r.get("is_early_churn") or 0
        for action in set(_qualifying_actions(r, idx)):
            b = per.setdefault(action, {"n": 0, "churn": 0})
            b["n"] += 1
            b["churn"] += churn
    rows = [{"action": a, "n": v["n"], "churn": v["churn"],
             "rate": v["churn"] / v["n"] if v["n"] else 0.0,
             "reference": v["n"] < min_reliable} for a, v in per.items()]
    rows.sort(key=lambda x: x["rate"])
    return rows
