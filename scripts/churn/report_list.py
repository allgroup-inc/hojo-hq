"""一覧出力：継続中×6ヶ月未満をリスク高い順に並べる（CSV / HTML）。"""
from __future__ import annotations
import csv
import html

from .score import score_record, display_pct
from .actions import action_for_band
from .console import karte_filename

_HEADERS = ["customer_id", "apply_id", "agent_id", "product", "channel", "risk_pct", "band", "hit_summary", "action"]
_BAND_COLOR = {"high": "#F88800", "med": "#FFD27F", "low": "#EAF2F8"}


def _hit_summary(hit_factors):
    parts = []
    for f in hit_factors:
        arrow = "↑" if f["direction"] == "up" else "↓"
        ref = "(参考)" if f["reference"] else ""
        parts.append(f'{f["field"]}={f["value"]}{arrow}×{f["odds_ratio"]:.1f}{ref}')
    return " / ".join(parts)


def build_rows(scoreable_records, model):
    rows = []
    for r in scoreable_records:
        s = score_record(r, model)
        rows.append({
            "customer_id": r.get("customer_id") or "",
            "karte_link": karte_filename(r.get("customer_id")) if r.get("customer_id") else "",
            "apply_id": r.get("apply_id"), "agent_id": r.get("agent_id"),
            "product": r.get("product"), "channel": r.get("channel"),
            "risk": s["risk"], "risk_pct": display_pct(s["risk"]),
            "band": s["band"], "hit_summary": _hit_summary(s["hit_factors"]),
            "action": action_for_band(s["band"]),
        })
    rows.sort(key=lambda x: x["risk"], reverse=True)
    return rows


def render_csv(rows, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_HEADERS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def render_html(rows, path):
    th = "".join(f"<th>{h}</th>" for h in _HEADERS)
    trs = []
    for r in rows:
        color = _BAND_COLOR.get(r["band"], "#fff")
        cells = []
        for h in _HEADERS:
            val = html.escape(str(r.get(h, "")))
            if h == "customer_id" and r.get("karte_link"):
                val = f'<a href="{html.escape(r["karte_link"])}">{val}</a>'
            cells.append(f"<td>{val}</td>")
        trs.append(f'<tr style="background:{color}">{"".join(cells)}</tr>')
    doc = (
        '<!doctype html><meta charset="utf-8">'
        '<title>早期解約リスク一覧</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px;font-size:13px}'
        'th{background:#00335C;color:#fff}</style>'
        '<h1>早期解約リスク一覧（継続中・6ヶ月未満）</h1>'
        f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
