"""カード出力：申込1件の「%・なぜ高いか・型アクション」。"""
from __future__ import annotations
import html

from .score import score_record
from .actions import action_for_band

_BAND_LABEL = {"high": "🔴 高リスク", "med": "🟡 中リスク", "low": "🟢 低リスク"}


def _reason(f):
    direction = "上げている" if f["direction"] == "up" else "下げている"
    ref = "（件数が少なく参考値）" if f["reference"] else ""
    return f'{f["field"]}={f["value"]} がリスクを{direction}（×{f["odds_ratio"]:.1f}）{ref}'


def build_card(record, model):
    s = score_record(record, model)
    return {
        "apply_id": record.get("apply_id"),
        "risk_pct": round(s["risk"] * 100, 1),
        "band": s["band"],
        "base_pct": round(s["base_rate"] * 100, 1),
        "hit_factors": s["hit_factors"],
        "action": action_for_band(s["band"]),
        "reasons": [_reason(f) for f in s["hit_factors"]],
    }


def render_html(card, path):
    reasons = "".join(f"<li>{html.escape(r)}</li>" for r in card["reasons"])
    doc = (
        '<!doctype html><meta charset="utf-8"><title>リスクカード</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:24px;max-width:640px}'
        '.pct{font-size:48px;color:#F88800;font-weight:bold}'
        '.band{font-size:20px;margin:8px 0}.action{background:#EAF2F8;padding:12px;border-radius:8px}</style>'
        f'<h1>申込 {html.escape(str(card["apply_id"]))} のリスク</h1>'
        f'<div class="pct">{card["risk_pct"]}%</div>'
        f'<div class="band">{_BAND_LABEL.get(card["band"], card["band"])}（全体平均 {card["base_pct"]}%）</div>'
        f'<h2>なぜ高い/低いか</h2><ul>{reasons}</ul>'
        f'<h2>推奨アクション</h2><div class="action">{html.escape(card["action"])}</div>'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
