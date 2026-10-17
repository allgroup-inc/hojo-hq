"""「守れる金額」= リスク% × 年間保険料の目安。保全の優先順位づけに使う共有ヘルパー。

同じリスクでも高額契約を優先＝守れる保険料が大きい順に手を打つ、という考え方。
保険料は月額×12の概算（docs/churn/改善レビュー・予防トリガー設計 参照）。
"""
from __future__ import annotations

MONTHS_PER_YEAR = 12


def saveable(risk, monthly_amount):
    """期待“守れる”保険料 = risk（0〜1）× 月額 × 12。月額が無ければ0。"""
    return float(risk) * (monthly_amount or 0) * MONTHS_PER_YEAR
