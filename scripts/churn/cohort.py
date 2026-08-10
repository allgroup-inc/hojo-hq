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


def render_html(rows, overall, path, target=0.03):
    """コホート表＋全体率と目標ラインをHTML出力（表示層・出力は private/ 限定）。"""
    import html
    trs = []
    for r in rows:
        if r["observing"]:
            cell = "観測中(未確定)"
        elif r["rate"] is None:
            cell = "確定なし"
        else:
            cell = f'{r["rate"]*100:.1f}%' + (" 参考" if r["reference"] else "")
        trs.append(f'<tr><td>{html.escape(r["ym"])}</td><td>{r["total"]}</td>'
                   f'<td>{r["resolved"]}</td><td>{r["churn"]}</td><td>{cell}</td></tr>')
    o = overall["rate"] * 100
    doc = (
        '<!doctype html><meta charset="utf-8"><title>早期解約率コホート</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse}th,td{border:1px solid #ccc;padding:6px}'
        'th{background:#00335C;color:#fff}</style>'
        f'<h1>早期解約率 コホート（成熟分のみ）</h1>'
        f'<p>全体 <b>{o:.1f}%</b> ／ 目標 {target*100:.0f}%（差 {o-target*100:+.1f}pt）'
        f' ／ 成熟 {overall["churn"]}/{overall["resolved"]}件</p>'
        '<p style="font-size:12px;color:#888">観測中(6ヶ月未確定)は率を出さず全体からも除外。少件数は参考。合成データ。</p>'
        '<table><thead><tr><th>契約月</th><th>契約数</th><th>確定</th><th>解約</th><th>早期解約率</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
