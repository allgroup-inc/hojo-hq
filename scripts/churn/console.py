"""運用コンソール生成：顧客インデックス＋各カルテ＋要フォローを private/ に出す。"""
from __future__ import annotations
import html
import os
import re

from .karte import render_html as render_karte_html
from .followups import list_followups, render_html as render_followups_html

_BAND_RANK = {"high": 2, "med": 1, "low": 0}
_BAND_JP = {"high": "🔴 高", "med": "🟡 中", "low": "🟢 低", None: "—"}


def karte_filename(customer_id):
    safe = re.sub(r"[^0-9A-Za-z_-]", "_", str(customer_id))
    return f"karte_{safe}.html"


def build_index_rows(customers):
    rows = []
    for c in customers.values():
        rows.append({
            "customer_id": c["customer_id"],
            "attr": f'{c.get("age_band","不明")} / {c.get("gender","不明")} / {c.get("area","不明")}',
            "n_applications": c.get("n_applications", 0),
            "n_active": c.get("n_active", 0),
            "n_additional_guidance": c.get("n_additional_guidance", 0),
            "max_risk_band": c.get("max_risk_band"),
            "last_contact_date": c.get("last_contact_date"),
            "needs_followup": bool(c.get("needs_followup")),
            "karte_file": karte_filename(c["customer_id"]),
        })
    rows.sort(key=lambda r: (
        not r["needs_followup"],
        -_BAND_RANK.get(r["max_risk_band"], -1),
        str(r["customer_id"]),
    ))
    return rows


def render_index_html(rows, path):
    trs = []
    for r in rows:
        fu = '<span class="fu">要フォロー</span>' if r["needs_followup"] else ""
        last = r["last_contact_date"] or "接触なし"
        trs.append(
            f'<tr><td><a href="{html.escape(r["karte_file"])}">{html.escape(str(r["customer_id"]))}</a> {fu}</td>'
            f'<td>{html.escape(str(r["attr"]))}</td><td>{r["n_applications"]}</td>'
            f'<td>{r["n_active"]}</td><td>{r["n_additional_guidance"]}</td>'
            f'<td>{_BAND_JP.get(r["max_risk_band"])}</td><td>{html.escape(str(last))}</td></tr>')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>顧客インデックス</title>'
        '<style>body{font-family:"Noto Sans JP","Meiryo",sans-serif;padding:20px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #dce4ec;padding:8px;font-size:13px}'
        'th{background:#00335c;color:#fff}a{color:#0a4a7a;font-weight:700}'
        '.fu{background:#fbe9e2;color:#dc4e28;border-radius:6px;padding:1px 7px;font-size:11px;font-weight:700}'
        'h1{font-size:18px}</style>'
        '<h1>顧客インデックス(顧客IDで名寄せ)</h1>'
        '<table><thead><tr><th>顧客ID</th><th>属性</th><th>累計申込</th><th>継続中</th>'
        '<th>追加案内</th><th>最大リスク</th><th>最終接触</th></tr></thead>'
        f'<tbody>{"".join(trs) or "<tr><td colspan=7>顧客なし</td></tr>"}</tbody></table>'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


def generate(customers, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    n = 0
    seen = {}  # karte_filename -> customer_id（衝突検知用）
    for c in customers.values():
        fname = karte_filename(c["customer_id"])
        if fname in seen:
            raise SystemExit(
                f"[console] カルテファイル名が衝突しました: 顧客ID {seen[fname]!r} と "
                f"{c['customer_id']!r} がどちらも {fname} になります。"
                "顧客IDのサニタイズ後が一致するため、誤った顧客のカルテへのリンクを防ぐため停止します。"
            )
        seen[fname] = c["customer_id"]
        render_karte_html(c, os.path.join(out_dir, fname))
        n += 1
    index_path = os.path.join(out_dir, "index.html")
    render_index_html(build_index_rows(customers), index_path)
    fu_path = os.path.join(out_dir, "followups.html")
    render_followups_html(list_followups(customers), fu_path)
    return {"index": index_path, "n_kartes": n, "followups": fu_path}
