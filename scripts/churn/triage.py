"""今日の要接触（統合トリアージ）＝ ②予防トリガー＋守れる金額の高リスクを1本に束ねる。

複数のきっかけを重複排除→優先度＋守れる金額で並べ→キャパ内に絞る。上限超過は繰り越し
（落とした件数と最高“守れる金額”を明示＝no silent cap）。docs/churn/クローズドループ設計.md。
"""
from __future__ import annotations

from .score import score_record, display_pct
from .triggers import prevention_trigger, initial_contact_trigger
from .effect_learning import _contacts_index
from .value import saveable as _saveable

# きっかけの優先度（小さいほど先）。不着＞遅延＞口座確認(引落前)＞初動(未接触新規)＞高リスク。
PRIORITY = {"不着": 0, "遅延": 1, "口座確認": 2, "初動": 3, "高リスク": 4}


def classify(records, model, as_of, contacts=None):
    """継続中レコードを、きっかけつきの候補に分類する（1契約=1候補・重複排除済み）。

    contacts を渡すと、契約直後・未接触の継続契約を「初動」として拾う（保全は早いほど効く）。
    優先度: 予防トリガー(不着/遅延/口座確認) ＞ 初動 ＞ 高リスク。
    """
    idx = _contacts_index(contacts) if contacts is not None else None
    cands = []
    for r in records:
        if not r.get("is_scoreable"):
            continue
        trig = prevention_trigger(r, as_of)
        if trig is None and idx is not None:
            trig = initial_contact_trigger(r, idx, as_of)
        s = score_record(r, model)
        if trig is None:
            if s["band"] != "high":
                continue  # 予防トリガーも初動も高リスクもなければ候補でない
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


def render_html(today, carry, stats, path, capacity):
    """今日の要接触をHTML出力（表示層・出力は private/ 限定）。"""
    import html
    trs = []
    for i, c in enumerate(today, 1):
        trs.append(
            f'<tr><td>{i}</td><td>{html.escape(str(c["trigger"]))}</td>'
            f'<td>{html.escape(str(c.get("customer_id") or "—"))}</td>'
            f'<td>{html.escape(str(c.get("product")))}</td>'
            f'<td>{c["risk_pct"]}%</td><td>{c["saveable"]:,.0f}円</td></tr>')
    carry_note = (
        f'キャパ{capacity}件/日 超過 {stats["carry_count"]}件は翌日へ繰り越し'
        f'（最高“守れる金額” {stats["carry_max_saveable"]:,.0f}円）'
        if stats["carry_count"] else 'キャパ内・取りこぼしなし')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>今日の要接触</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px;font-size:13px}'
        'th{background:#00335C;color:#fff}</style>'
        f'<h1>今日の要接触（{len(today)}件 / 要接触合計 {stats["total"]}件）</h1>'
        f'<p>{carry_note}。優先度：不着＞遅延＞口座確認＞初動＞高リスク、各内で守れる金額順。'
        '顧客連絡は人が実行。合成データ。</p>'
        '<table><thead><tr><th>#</th><th>きっかけ</th><th>顧客ID</th><th>商品</th>'
        '<th>リスク</th><th>守れる金額</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
