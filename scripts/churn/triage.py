"""今日の要接触（統合トリアージ）＝ ②予防トリガー＋守れる金額の高リスクを1本に束ねる。

複数のきっかけを重複排除→優先度＋守れる金額で並べ→キャパ内に絞る。上限超過は繰り越し
（落とした件数と最高“守れる金額”を明示＝no silent cap）。docs/churn/クローズドループ設計.md。
"""
from __future__ import annotations

from .score import score_record, display_pct
from .triggers import prevention_trigger
from .value import saveable as _saveable

# きっかけの優先度（小さいほど先）。不着＞遅延＞口座確認(引落前)＞高リスク。
PRIORITY = {"不着": 0, "遅延": 1, "口座確認": 2, "高リスク": 3}


def classify(records, model, as_of):
    """継続中レコードを、きっかけつきの候補に分類する（1契約=1候補・重複排除済み）。"""
    cands = []
    for r in records:
        if not r.get("is_scoreable"):
            continue
        trig = prevention_trigger(r, as_of)
        s = score_record(r, model)
        if trig is None:
            if s["band"] != "high":
                continue  # 予防トリガーも高リスクもなければ候補でない
            trig = "高リスク"
        cands.append({
            "customer_id": r.get("customer_id"), "apply_id": r.get("apply_id"),
            "product": r.get("product"), "agent_id": r.get("agent_id"),
            "trigger": trig, "risk": s["risk"], "risk_pct": display_pct(s["risk"]),
            "band": s["band"], "hit_factors": s["hit_factors"],
            "saveable": _saveable(s["risk"], r.get("amount")),
        })
    return cands


def triage(candidates, capacity):
    """優先度→守れる金額順に並べ、キャパで today / carry に分ける。繰り越しは件数・最高額を明示。"""
    ordered = sorted(candidates, key=lambda c: (PRIORITY.get(c["trigger"], 99), -c["saveable"]))
    today = ordered[:capacity]
    carry = ordered[capacity:]
    stats = {
        "carry_count": len(carry),
        "carry_max_saveable": max((c["saveable"] for c in carry), default=0.0),
        "total": len(ordered),
    }
    return today, carry, stats
