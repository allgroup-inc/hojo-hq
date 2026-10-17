"""理由ドリブンの打ち手（この層にはこの一手）。

解約理由（cancel_reason）をセグメント別に集計し、learning（対応内容ごとの早期解約率）と
突き合わせて、「このセグメントで多い解約理由」と「このセグメントで最も効いた一手」を並べる。

規律（churn-retention-ops / churn-model-quality-gate）:
- 「効いた一手」＝ learning の最小解約率の対応内容。ただし**接触は無作為でない**ため
  生存者バイアスが残る（因果は experiment.py の対照群比較で確かめる）。ここは運用の当たりを
  つけるための**参考**。母数不足（< MIN_RELIABLE_N）は reference=True で明示し断定しない。
- 成熟実績（is_resolved かつ mature_before より前）のみを対象にする。
"""
from __future__ import annotations
from collections import Counter

from .config import MIN_RELIABLE_N
from .effect_learning import learning, _mature_resolved


def _top_reason(recs):
    """早期解約したレコードの中で最も多い解約理由と件数。"""
    c = Counter((r.get("cancel_reason") or "不明")
                for r in recs if r.get("is_early_churn"))
    if not c:
        return (None, 0)
    reason, n = c.most_common(1)[0]
    return (reason, n)


def segment_playbook(records, contacts, mature_before, segment_field="product",
                     min_reliable=MIN_RELIABLE_N):
    """セグメント別に『多い解約理由』と『効いた一手（推奨）』を対応づける。"""
    mature = _mature_resolved(records, mature_before)
    segments = {}
    for r in mature:
        segments.setdefault(r.get(segment_field, "不明"), []).append(r)

    rows = []
    for seg, recs in segments.items():
        lrows = learning(recs, contacts, mature_before, min_reliable)
        best = lrows[0] if lrows else None   # 最小解約率＝効いた一手
        reason, rcount = _top_reason(recs)
        rows.append({
            "segment": seg,
            "n": len(recs),
            "top_reason": reason, "reason_count": rcount,
            "recommended_action": best["action"] if best else None,
            "action_rate": best["rate"] if best else None,
            "action_n": best["n"] if best else 0,
            # 推奨の一手が母数不足、またはセグメント自体が少数なら参考
            "reference": (best["reference"] if best else True) or len(recs) < min_reliable,
        })
    rows.sort(key=lambda x: x["segment"])
    return rows


def render_html(rows, path, segment_label="商品"):
    """理由×一手のプレイブックをHTML出力（表示層・出力は private/ 限定）。"""
    import html
    trs = []
    for r in rows:
        reason = html.escape(str(r["top_reason"] or "—"))
        action = html.escape(str(r["recommended_action"] or "—"))
        rate = "—" if r["action_rate"] is None else f'{r["action_rate"]*100:.1f}%'
        ref = " <span style=\"color:#888\">参考</span>" if r["reference"] else ""
        trs.append(
            f'<tr><td>{html.escape(str(r["segment"]))}</td><td>{r["n"]}</td>'
            f'<td>{reason}（{r["reason_count"]}件）</td>'
            f'<td>{action}（解約{rate}・n={r["action_n"]}）{ref}</td></tr>')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>理由ドリブンの打ち手</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px;font-size:13px}'
        'th{background:#00335C;color:#fff}</style>'
        '<h1>この層には、この一手（理由×効いた一手）</h1>'
        '<p style="font-size:12px;color:#888">「効いた一手」は接触の当たりをつける参考（無作為でないため'
        '生存者バイアスあり・因果は段階導入で確認）。母数不足は参考。合成データ。</p>'
        f'<table><thead><tr><th>{html.escape(segment_label)}</th><th>成熟</th>'
        '<th>多い解約理由</th><th>推奨の一手</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
