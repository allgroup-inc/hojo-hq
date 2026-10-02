#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — Guard クラス基底型とその実装(売上自動化 Task 5)

Guard 基底クラス:
- すべての Guard が継承する抽象基底クラス
- verify() メソッドを実装して facts オブジェクトを検査する
- 違反があれば FactsError を throw し、エラー理由を詳述する

実装される Guard クラス:
1. NumberVerifier: すべての数字が weekly_metrics/kpi の原文と照合(絶対ルール1)
2. BannedPhrasesChecker: article_topics と segment 名に禁止表現が無いことを検査
3. SegmentFitChecker: segment_scores が Task 8 ルール(0-100, threshold 60)に準拠
"""
from abc import ABC, abstractmethod
from typing import Any, Dict


class Guard(ABC):
    """すべての Guard の基底クラス。検査ロジックは verify() で実装される。"""

    @abstractmethod
    def verify(self, facts: Dict[str, Any], weekly_metrics: Dict[str, Any], kpi: Dict[str, Any]) -> None:
        """
        facts オブジェクトを検査し、違反があれば FactsError を throw。

        Args:
            facts: 検査対象の facts 辞書(FactsDict の中身)
            weekly_metrics: 参照値 weekly_metrics(Task 4 の collect_weekly_metrics.py 出力)
            kpi: 参照値 kpi.json(segment_thresholds, banned_phrases, etc.)

        Raises:
            FactsError: 検査が失敗した場合。エラーメッセージに違反内容と救済策を含める。
        """
        pass
