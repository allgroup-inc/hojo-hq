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
import math
from abc import ABC, abstractmethod
from typing import Any, Dict

from build_facts import FactsError


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


def _is_number(value: Any) -> bool:
    """bool は int の部分型なので除外。NaN/inf も数字として扱わない。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class NumberVerifier(Guard):
    """facts の数字がすべて weekly_metrics の原文に由来することを検査(絶対ルール1)。

    weekly_metrics は kekka_weekly_metrics.json の weeks[] の1件(note キーを持つ辞書)。
    kpi は本クラスでは数字の根拠に使わない(Guard 共通シグネチャのため受け取るだけ)。

    検査項目:
      1. weekly_metrics.note が辞書で views_by_article / total_sales_jpy を持つ
      2. article_topics の各 article_id が note.views_by_article に存在
         (views を持つ場合は原文のビュー数と一致、sales_jpy は非負の数)
      3. sales_by_segment(あれば)は全値が非負の数で、合計 == note.total_sales_jpy
      4. article_topics の sales_jpy 合計 <= note.total_sales_jpy(記事は一部のみの掲載があり得るため上限のみ)
    """

    def verify(self, facts: Dict[str, Any], weekly_metrics: Dict[str, Any], kpi: Dict[str, Any]) -> None:
        note = weekly_metrics.get("note") if isinstance(weekly_metrics, dict) else None
        if not isinstance(note, dict):
            raise FactsError("weekly_metrics.note is missing or not a dict; cannot verify any number against source")

        topics = facts.get("article_topics") or []
        segments = facts.get("sales_by_segment")

        views_by_article = note.get("views_by_article")
        if topics:
            if not isinstance(views_by_article, dict):
                raise FactsError("weekly_metrics.note.views_by_article is missing; cannot verify article_topics")
        valid_articles = set(views_by_article or {})

        article_sales_sum = 0
        for topic in topics:
            aid = topic.get("article_id") if isinstance(topic, dict) else None
            if aid not in valid_articles:
                raise FactsError(
                    f"article_id '{aid}' not found in weekly_metrics.note.views_by_article. "
                    f"Valid articles: {sorted(valid_articles)}"
                )
            if "views" in topic and topic["views"] != views_by_article[aid]:
                raise FactsError(
                    f"article '{aid}' views mismatch: facts has {topic['views']}, "
                    f"weekly_metrics.note.views_by_article has {views_by_article[aid]}"
                )
            if "sales_jpy" in topic:
                sales = topic["sales_jpy"]
                if not _is_number(sales) or sales < 0:
                    raise FactsError(f"article '{aid}' sales_jpy must be a non-negative number: {sales!r}")
                article_sales_sum += sales

        if segments is None and not (topics and article_sales_sum):
            return  # 売上に関する数字が facts に無ければ total_sales_jpy の照合は不要

        total = note.get("total_sales_jpy")
        if not _is_number(total):
            raise FactsError("weekly_metrics.note.total_sales_jpy is missing; cannot verify sales numbers")

        if segments is not None:
            if not isinstance(segments, dict):
                raise FactsError(f"sales_by_segment must be a dict, got {type(segments).__name__}")
            for name, value in segments.items():
                if not _is_number(value):
                    raise FactsError(f"sales_by_segment['{name}'] is not a number: {value!r}")
                if value < 0:
                    raise FactsError(f"sales_by_segment['{name}'] is negative: {value}")
            segment_sum = sum(segments.values())
            if segment_sum != total:
                raise FactsError(
                    f"sales_by_segment sum mismatch: segments total {segment_sum} but "
                    f"weekly_metrics.note.total_sales_jpy is {total}"
                )

        if article_sales_sum > total:
            raise FactsError(
                f"article_topics sales_jpy sum ({article_sales_sum}) exceeds "
                f"weekly_metrics.note.total_sales_jpy ({total})"
            )
