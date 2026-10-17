"""リスク帯 → 手厚い保全アクションの型（テアツ部門設計）。"""
from __future__ import annotations

_ACTIONS = {
    "high": "申込直後の安心コール＋3ヶ月まで定期接触＋ヒット要因に応じた個別フォロー（7日以内に初回）",
    "med": "オンボーディング配信＋1回フォロー。改善なければ高扱いへ",
    "low": "通常運用",
}


def action_for_band(band):
    return _ACTIONS.get(band, "通常運用")
