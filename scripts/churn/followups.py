"""要フォロー一覧：高リスク×直近接触なし(放置)の顧客を洗い出す。"""
from __future__ import annotations
import html
from datetime import date

_MIN = date(1, 1, 1)


def list_followups(customers):
    rows = [c for c in customers.values() if c.get("needs_followup")]
    # 最終接触が古い順(未接触=最優先)
    rows.sort(key=lambda c: c.get("last_contact_date") or _MIN)
    return rows


def render_html(rows, path):
    trs = []
    for c in rows:
        last = c.get("last_contact_date") or "接触なし"
        trs.append(
            f"<tr><td>{html.escape(str(c.get('customer_id')))}</td>"
            f"<td>{html.escape(str(c.get('age_band')))} / {html.escape(str(c.get('area')))}</td>"
            f"<td>{c.get('n_active')}</td><td>{html.escape(str(last))}</td></tr>")
    doc = (
        '<!doctype html><meta charset="utf-8"><title>要フォロー一覧</title>'
        '<style>body{font-family:"Noto Sans JP","Meiryo",sans-serif;padding:20px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #dce4ec;padding:8px}'
        'th{background:#dc4e28;color:#fff}h1{font-size:18px}</style>'
        '<h1>⚠️ 要フォロー(高リスク×直近接触なし)</h1>'
        '<table><thead><tr><th>顧客ID</th><th>属性</th><th>継続中</th><th>最終接触</th></tr></thead>'
        f'<tbody>{"".join(trs) or "<tr><td colspan=4>該当なし</td></tr>"}</tbody></table>'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
