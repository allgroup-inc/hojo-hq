"""対話ログの効果測定（対話タイプ別）— 訪問保全設計 スライス2。

保全の対話ログ（懸念 concern・返し方/対話内容 approach・接触手段 medium）を、成熟実績の
早期解約率と突き合わせ、「どの対話タイプが効いたか」を出す。教育ナレッジ（スライス3）の土台。

規律（churn-retention-ops / churn-model-quality-gate）:
- 成熟実績（is_resolved かつ mature_before より前）のみ。解約前の接触だけ数える（免疫時間）。
- 空タグは数えない。母数不足（< MIN_RELIABLE_N）は reference で明示し断定しない。
- **接触は無作為でない＝生存者バイアスが残る。率の差は因果ではない**（因果は experiment の段階導入）。
"""
from __future__ import annotations

from .config import MIN_RELIABLE_N
from .effect_learning import _contacts_index, _mature_resolved, _qualifying_contacts


def _qualifying_values(record, idx, field):
    """解約前・当該タグが非空の接触の、field 値リスト（免疫時間・空タグ除外）。"""
    return [v for c in _qualifying_contacts(record, idx)
            if (v := (c.get(field) or "").strip())]


def dialog_effect(records, contacts, mature_before, field="approach",
                  min_reliable=MIN_RELIABLE_N):
    """対話タイプ（field=approach/concern/medium 等）別の早期解約率（低い＝効いた順）。"""
    idx = _contacts_index(contacts)
    per = {}
    for r in _mature_resolved(records, mature_before):
        churn = r.get("is_early_churn") or 0
        for v in set(_qualifying_values(r, idx, field)):
            b = per.setdefault(v, {"n": 0, "churn": 0})
            b["n"] += 1
            b["churn"] += churn
    rows = [{"value": v, "n": b["n"], "churn": b["churn"],
             "rate": b["churn"] / b["n"] if b["n"] else 0.0,
             "reference": b["n"] < min_reliable} for v, b in per.items()]
    rows.sort(key=lambda x: x["rate"])
    return rows


def render_html(rows, path, field_label="返し方"):
    """対話タイプ別の効果をHTML出力（表示層・出力は private/ 限定）。"""
    import html
    trs = []
    for r in rows:
        ref = ' <span style="color:#6B6B6B">参考</span>' if r["reference"] else ""
        trs.append(f'<tr><td>{html.escape(str(r["value"]))}</td><td>{r["n"]}</td>'
                   f'<td>{r["churn"]}</td><td>{r["rate"]*100:.1f}%{ref}</td></tr>')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>対話タイプ別の効果</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px;font-size:13px}'
        'th{background:#00335C;color:#fff}</style>'
        f'<h1>{html.escape(field_label)}別の早期解約率（低い＝効いた順）</h1>'
        '<p style="font-size:12px;color:#6B6B6B">接触は無作為でないため率の差は参考（生存者バイアス）。'
        '因果は段階導入(uplift)で確認。母数不足は参考。合成データ。</p>'
        f'<table><thead><tr><th>{html.escape(field_label)}</th><th>件数</th>'
        '<th>解約</th><th>早期解約率</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
