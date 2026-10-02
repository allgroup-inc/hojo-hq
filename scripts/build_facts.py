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
import re
from dataclasses import asdict, dataclass
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


_ISO_WEEK_RE = re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")
_DEFAULT_SEGMENT_SCORE = 60  # Task 8 で精緻化するまでのプレースホルダ(推奨閾値と同値)


def _extract_week(weekly_metrics: Dict[str, Any]) -> str:
    """週キーを取り出して ISO 8601 形式(YYYY-Www)を検証する。top-level と note.week が食い違えばエラー。"""
    note = weekly_metrics.get("note")
    candidates = [w for w in (weekly_metrics.get("week"), note.get("week") if isinstance(note, dict) else None)
                  if w is not None]
    if not candidates:
        raise FactsError("weekly_metrics has no 'week' (expected top-level 'week' or note.week)")
    week = candidates[0]
    if any(c != week for c in candidates):
        raise FactsError(f"weekly_metrics week mismatch between top-level and note: {candidates!r}")
    if not isinstance(week, str) or not _ISO_WEEK_RE.match(week):
        raise FactsError(f"week must be ISO 8601 'YYYY-Www' (e.g. '2026-W40'), got {week!r}")
    return week


def build_facts(weekly_metrics: Dict[str, Any], kpi: Dict[str, Any]) -> Dict[str, Any]:
    """週次メトリクス1件と kpi から facts 辞書を構築し、3つの Guard を通して返す。

    Args:
        weekly_metrics: kekka_weekly_metrics.json の weeks[] の1件(ファイル全体ではない)。
            呼び出し側は build_facts(weeks[-1], kpi) のように渡す。
        kpi: data/kekka_kpi.json の内容(segment_thresholds / banned_phrases)。

    Returns:
        FactsDict.to_dict()(JSON シリアライズ可能な dict)。

    Raises:
        FactsError: 入力が None・空・不正、または Guard(数字・禁止表現・セグメント)が失敗した場合。

    加工は元データの転記に限定する(解釈・推計はしない。絶対ルール1)。
    """
    # --- 入力検証 ---
    for name, value in (("weekly_metrics", weekly_metrics), ("kpi", kpi)):
        if value is None:
            raise FactsError(f"{name} is None")
        if not isinstance(value, dict):
            raise FactsError(f"{name} must be a dict, got {type(value).__name__}")
        if not value:
            raise FactsError(f"{name} is empty")

    note = weekly_metrics.get("note")
    if not isinstance(note, dict):
        raise FactsError("weekly_metrics.note is missing or not a dict")
    views_by_article = note.get("views_by_article")
    if not isinstance(views_by_article, dict):
        raise FactsError("weekly_metrics.note.views_by_article is missing or not a dict")

    week = _extract_week(weekly_metrics)

    # --- facts 構築(原文の転記のみ) ---
    sales_by_article = note.get("sales_by_article")
    if sales_by_article is not None and not isinstance(sales_by_article, dict):
        raise FactsError("weekly_metrics.note.sales_by_article must be a dict when present")

    article_topics: List[Dict[str, Any]] = []
    for article_id, views in views_by_article.items():
        topic: Dict[str, Any] = {"article_id": article_id, "views": views}
        if sales_by_article and article_id in sales_by_article:
            topic["sales_jpy"] = sales_by_article[article_id]
        article_topics.append(topic)

    sales_by_segment = weekly_metrics.get("sales_by_segment", note.get("sales_by_segment"))
    if sales_by_segment is None:
        sales_by_segment = {}
    elif not isinstance(sales_by_segment, dict):
        raise FactsError(f"sales_by_segment must be a dict when present, got {type(sales_by_segment).__name__}")
    sales_by_segment = dict(sales_by_segment)  # 入力を共有しない(キー順は保持)

    thresholds = kpi.get("segment_thresholds")
    if not isinstance(thresholds, dict) or not thresholds:
        raise FactsError("kpi['segment_thresholds'] is missing or empty; cannot build segment_scores")
    segment_scores = {name: _DEFAULT_SEGMENT_SCORE for name in thresholds}  # プレースホルダ(Task 8 で精緻化)

    facts = FactsDict(
        week=week,
        article_topics=article_topics,
        sales_by_segment=sales_by_segment,
        segment_scores=segment_scores,
    )
    facts_dict = facts.to_dict()

    # --- Guard チェーン(guards は build_facts を import するため、循環回避で遅延 import) ---
    from guards import BannedPhrasesChecker, NumberVerifier, SegmentFitChecker

    for guard in (NumberVerifier(), BannedPhrasesChecker(), SegmentFitChecker()):
        guard.verify(facts_dict, weekly_metrics, kpi)

    return facts_dict
