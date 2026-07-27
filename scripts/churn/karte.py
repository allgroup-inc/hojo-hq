"""顧客カルテHTML：申込み履歴＋接触タイムライン＋現在リスク＋放置検知。"""
from __future__ import annotations
import html

from .score import display_pct

_BAND_JP = {"high": "🔴 高", "med": "🟡 中", "low": "🟢 低", None: "—"}


def _e(v):
    return html.escape(str(v if v is not None else ""))


def _status(app):
    if app.get("is_early_churn") == 1:
        return "早期解約"
    if app.get("cancel_date"):
        return "解約"
    return "継続中"


def _app_rows(apps):
    out = []
    for a in apps:
        risk = f"{display_pct(a['risk'])}%" if a.get("risk") is not None else "—"
        out.append(
            f"<tr><td>{_e(a.get('apply_id'))}</td><td>{_e(a.get('product'))}</td>"
            f"<td>{_e(a.get('amount'))}</td><td>{_e(a.get('channel'))}</td>"
            f"<td>{_e(a.get('agent_id'))}</td><td>{_e(a.get('apply_date'))}</td>"
            f"<td>{_e(_status(a))}</td><td>{risk} {_BAND_JP.get(a.get('band'))}</td></tr>")
    return "".join(out)


def _timeline(inters):
    out = []
    for i in inters:
        out.append(
            f"<li><b>{_e(i.get('date'))}</b> <span class='kind'>{_e(i.get('kind'))}</span> "
            f"／ {_e(i.get('agent'))}<br>{_e(i.get('content'))}"
            f"<span class='memo'>{_e(i.get('memo'))}</span></li>")
    return "".join(out) or "<li>接触履歴なし</li>"


def render_html(profile, path):
    p = profile
    followup = ('<div class="followup">⚠️ 要フォロー：高リスクなのに直近の接触がありません</div>'
                if p.get("needs_followup") else "")
    doc = (
        '<!doctype html><meta charset="utf-8"><title>顧客カルテ ' + _e(p["customer_id"]) + '</title>'
        '<style>body{font-family:"Noto Sans JP","Meiryo",sans-serif;padding:20px;max-width:920px;margin:auto;color:#12212e}'
        'h1{font-size:20px}.sum{display:flex;gap:18px;flex-wrap:wrap;margin:12px 0}'
        '.sum div{background:#eef3f8;border-radius:10px;padding:10px 14px;font-size:13px}'
        '.sum b{font-size:20px;display:block}'
        '.followup{background:#fbe9e2;color:#dc4e28;font-weight:700;padding:10px 14px;border-radius:10px;margin:10px 0}'
        'table{border-collapse:collapse;width:100%;margin:8px 0;font-size:13px}'
        'th,td{border:1px solid #dce4ec;padding:7px 9px;text-align:left}th{background:#00335c;color:#fff}'
        'ul.tl{list-style:none;padding:0}ul.tl li{border-left:3px solid #f88800;padding:6px 12px;margin:6px 0;background:#f7f9fb;font-size:13px}'
        '.kind{background:#00335c;color:#fff;border-radius:4px;padding:1px 7px;font-size:11px}'
        '.memo{color:#5c6e7e;margin-left:8px}h2{font-size:15px;border-bottom:2px solid #dce4ec;padding-bottom:4px;margin-top:24px}</style>'
        f'<h1>顧客カルテ — {_e(p["customer_id"])}</h1>'
        f'<div>{_e(p["age_band"])} ／ {_e(p["gender"])} ／ {_e(p["area"])}</div>'
        f'{followup}'
        '<div class="sum">'
        f'<div>累計申込<b>{p["n_applications"]}回</b></div>'
        f'<div>継続中<b>{p["n_active"]}件</b></div>'
        f'<div>解約<b>{p["n_cancelled"]}件</b></div>'
        f'<div>早期解約<b>{p["n_early_churn"]}件</b></div>'
        f'<div>追加案内<b>{p["n_additional_guidance"]}回</b></div>'
        f'<div>現在の最大リスク<b>{_BAND_JP.get(p["max_risk_band"])}</b></div>'
        '</div>'
        '<h2>申込み履歴</h2>'
        '<table><thead><tr><th>申込ID</th><th>商品</th><th>金額</th><th>集客</th>'
        '<th>担当</th><th>申込日</th><th>状態</th><th>リスク</th></tr></thead>'
        f'<tbody>{_app_rows(p["applications"])}</tbody></table>'
        '<h2>接触タイムライン</h2>'
        f'<ul class="tl">{_timeline(p["interactions"])}</ul>'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
