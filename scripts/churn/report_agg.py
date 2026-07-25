"""集計レポート：営業マン別/チャネル別/商品別の解約傾向と、保全の効果測定。"""
from __future__ import annotations
import html


def aggregate_by(records, field):
    resolved = [r for r in records if r.get("is_resolved")]
    buckets = {}
    for r in resolved:
        value = r.get(field, "不明")
        b = buckets.setdefault(value, {"n": 0, "churn": 0})
        b["n"] += 1
        b["churn"] += r["is_early_churn"]
    rows = [{"value": v, "n": b["n"], "churn": b["churn"],
             "churn_rate": b["churn"] / b["n"] if b["n"] else 0.0}
            for v, b in buckets.items()]
    rows.sort(key=lambda x: x["churn_rate"], reverse=True)
    return rows


def effect_compare(followed, not_followed):
    def rate(recs):
        r = [x for x in recs if x.get("is_resolved")]
        return (sum(x["is_early_churn"] for x in r) / len(r)) if r else 0.0
    fr, nr = rate(followed), rate(not_followed)
    return {"followed_rate": fr, "not_followed_rate": nr, "diff": fr - nr,
            "n_followed": len(followed), "n_not_followed": len(not_followed)}


def render_html(sections, path):
    blocks = []
    for title, rows in sections.items():
        trs = "".join(
            f'<tr><td>{html.escape(str(r["value"]))}</td><td>{r["n"]}</td>'
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
        'th{background:#00335C;color:#fff}</style>'
        '<h1>解約傾向レポート（成熟実績ベース）</h1>' + "".join(blocks)
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
