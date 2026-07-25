"""集計レポート：営業マン別/チャネル別/商品別の解約傾向と、保全の効果測定。"""
from __future__ import annotations
import html

from .config import MIN_RELIABLE_N


def aggregate_by(records, field):
    resolved = [r for r in records if r.get("is_resolved")]
    buckets = {}
    for r in resolved:
        value = r.get(field, "不明")
        b = buckets.setdefault(value, {"n": 0, "churn": 0})
        b["n"] += 1
        b["churn"] += r["is_early_churn"]
    rows = [{"value": v, "n": b["n"], "churn": b["churn"],
             "churn_rate": b["churn"] / b["n"] if b["n"] else 0.0,
             "reference": b["n"] < MIN_RELIABLE_N}
            for v, b in buckets.items()]
    # 母数が少ない行（参考値）は上位に来ないよう、信頼できる行を優先し、その中で解約率降順
    rows.sort(key=lambda x: (x["reference"], -x["churn_rate"]))
    return rows


def effect_compare(followed, not_followed):
    def rate(recs):
        r = [x for x in recs if x.get("is_resolved")]
        return (sum(x["is_early_churn"] for x in r) / len(r)) if r else 0.0
    fr, nr = rate(followed), rate(not_followed)
    return {"followed_rate": fr, "not_followed_rate": nr, "diff": fr - nr,
            "n_followed": len(followed), "n_not_followed": len(not_followed)}


def _value_cell(r):
    label = html.escape(str(r["value"]))
    if r["reference"]:
        label += f' <span class="ref">参考(n&lt;{MIN_RELIABLE_N})</span>'
    return label


def render_html(sections, path):
    blocks = []
    for title, rows in sections.items():
        trs = "".join(
            f'<tr><td>{_value_cell(r)}</td><td>{r["n"]}</td>'
            f'<td>{r["churn"]}</td><td>{r["churn_rate"]*100:.1f}%</td></tr>'
            for r in rows)
        blocks.append(
            f'<h2>{html.escape(title)}</h2>'
            f'<table><thead><tr><th>値</th><th>件数</th><th>早期解約</th><th>解約率</th></tr></thead>'
            f'<tbody>{trs}</tbody></table>')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>解約傾向レポート</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse;margin-bottom:24px}th,td{border:1px solid #ccc;padding:6px}'
        'th{background:#00335C;color:#fff}.ref{color:#999;font-size:11px}</style>'
        '<h1>解約傾向レポート（成熟実績ベース）</h1>'
        '<p class="ref">「参考」表示は件数不足（母数閾値未満）のため、人事評価等の判断材料に使わないでください。</p>'
        + "".join(blocks)
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
