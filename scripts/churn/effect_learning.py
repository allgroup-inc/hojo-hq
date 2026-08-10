"""効果測定 → 学習（クローズドループ後半）。

- 効果測定: 保全接触あり/なしで早期解約率を比較。成熟契約のみ・解約前の接触のみを「あり」に
  数える（打ち切り／免疫時間バイアスを一部回避）。ただし**接触の有無は無作為でない**ため
  生存者バイアスが残る（長く続いた契約ほど接触されやすい）。**diff は因果ではない**。単純比較で
  断定せず、本番は段階導入（先行/後発）で因果を測る（churn-retention-ops）。
- 学習: 対応内容ごとの早期解約率を並べ「効いた一手」を出す。母数不足は「参考」。

いずれも成熟実績（is_resolved かつ契約が mature_before より前）に限定する。
接触の突合キーは (customer_id, apply_date)。同一顧客が同日に複数契約する場合は二重計上し得るため、
実運用では apply_id をログに持たせて契約単位で突合するのが望ましい（既知の制約）。
"""
from __future__ import annotations

from .config import MIN_RELIABLE_N


def _mature_resolved(records, mature_before):
    return [r for r in records if r.get("is_resolved") and r.get("apply_date")
            and r["apply_date"] < mature_before]


def _contacts_index(contacts):
    """apply_id を持つ接触は (顧客ID, apply_id) で、無い接触は (顧客ID, 契約日) で索引する。"""
    by_id, by_date = {}, {}
    for c in contacts:
        aid = c.get("apply_id")
        if aid:
            by_id.setdefault((c.get("customer_id"), aid), []).append(c)
        else:
            by_date.setdefault((c.get("customer_id"), c.get("apply_date")), []).append(c)
    return by_id, by_date


def _qualifying_actions(record, idx):
    """解約前の接触のみ（免疫時間除外）の対応内容リストを返す。
    突合は (顧客ID, apply_id) 優先＝同日複数契約の二重計上を避ける。無ければ (顧客ID, 契約日)。"""
    by_id, by_date = idx
    cs = by_id.get((record.get("customer_id"), record.get("apply_id")))
    if cs is None:
        cs = by_date.get((record.get("customer_id"), record.get("apply_date")), [])
    cancel = record.get("cancel_date")
    out = []
    for c in cs:
        cd = c.get("contact_date")
        action = (c.get("action") or "").strip()
        if cd is None or not action:      # 日付なし・対応内容が空の接触は数えない
            continue
        if cancel is None or cd < cancel:  # 解約後の接触は数えない（免疫時間除外）
            out.append(action)
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
