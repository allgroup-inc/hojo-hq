#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — Facts Builder で週次メトリクスから facts 辞書を構築する(売上自動化 Task 5)

Task 5 全体の責務:
1. collect_weekly_metrics.py の出力(kekka_weekly_metrics.json)を入力に
2. 3層のガード(数字検証・禁止表現・セグメント適合性)を通す
3. facts_dict(FactsDict)を構築して Task 6 の Claude プロンプト用データと Task 7-8 の入力を準備

FactsError: すべての Guard チェック失敗時に throw される例外。エラー理由を詳述。
FactsDict: 検証済みの facts 辞書。week / article_topics / sales_by_segment / segment_scores の4層で構成。
"""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


class FactsError(Exception):
    """Guard チェック失敗時に throw される例外。エラー理由を詳述。"""


@dataclass
class FactsDict:
    """検証済みの facts 辞書。各層は後続タスクの入力型として定義される。"""
    week: str  # YYYY-Www format (e.g., '2026-W40')
    article_topics: List[Dict[str, Any]]  # { article_id, sales_jpy, views, ... }
    sales_by_segment: Dict[str, float]    # { segment_name: total_sales_jpy }
    segment_scores: Dict[str, int]        # { segment_name: 0-100 score }

    def to_dict(self) -> Dict[str, Any]:
        """JSON-compatible dict に serialize。"""
        return asdict(self)
