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
import unicodedata
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

        no_segments = segments is None or (isinstance(segments, dict) and not segments)  # 空dict=セグメント別データ無し
        if no_segments and not (topics and article_sales_sum):
            return  # 売上に関する数字が facts に無ければ total_sales_jpy の照合は不要

        total = note.get("total_sales_jpy")
        if not _is_number(total):
            raise FactsError("weekly_metrics.note.total_sales_jpy is missing; cannot verify sales numbers")

        if not no_segments:
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


def _normalize(text: str) -> str:
    """全角半角・大文字小文字の揺れを吸収する(例: 'ＣｈａｔＧＰＴ' == 'chatgpt')。"""
    return unicodedata.normalize("NFKC", text).casefold()


def _iter_strings(value: Any, path: str):
    """facts の中の文字列を (フィールドパス, 文字列) で再帰的に列挙する。"""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _iter_strings(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for i, child in enumerate(value):
            yield from _iter_strings(child, f"{path}[{i}]")


class BannedPhrasesChecker(Guard):
    """facts の文字列に守り部の禁止表現(kpi["banned_phrases"])が含まれないことを検査。

    検査対象:
      - article_topics の全文字列フィールド(title / description / topic 等。article_id は識別子なので除外)
      - sales_by_segment / segment_scores のキー(セグメント名)
    照合は部分一致のリテラル比較(正規表現ではない。'100%' 等もそのまま使える)。
    NFKC正規化+casefold で全角半角・大文字小文字を区別しない。

    禁止表現リストが無い・空・不正な場合は検査を黙って素通りさせず FactsError にする
    (リスト欠落でガードが無効化されるのを防ぐ)。weekly_metrics は本クラスでは使わない。
    """

    def verify(self, facts: Dict[str, Any], weekly_metrics: Dict[str, Any], kpi: Dict[str, Any]) -> None:
        phrases = kpi.get("banned_phrases") if isinstance(kpi, dict) else None
        if not isinstance(phrases, list) or not phrases:
            raise FactsError(
                "kpi['banned_phrases'] is missing or empty; refusing to skip the banned-phrase check "
                "(add the 守り部 list to data/kekka_kpi.json)"
            )
        normalized = []
        for phrase in phrases:
            if not isinstance(phrase, str) or not phrase.strip():
                raise FactsError(f"kpi['banned_phrases'] contains an invalid entry: {phrase!r}")
            normalized.append((phrase, _normalize(phrase)))

        targets = []
        for i, topic in enumerate(facts.get("article_topics") or []):
            if not isinstance(topic, dict):
                continue
            for key, value in topic.items():
                if key != "article_id":
                    targets.extend(_iter_strings(value, f"article_topics[{i}].{key}"))
        for section in ("sales_by_segment", "segment_scores"):
            names = facts.get(section)
            if isinstance(names, dict):
                targets.extend((f"{section} key", name) for name in names if isinstance(name, str))

        for field, text in targets:
            haystack = _normalize(text)
            for phrase, needle in normalized:
                if needle in haystack:
                    raise FactsError(f"banned phrase '{phrase}' found in {field}: {text!r}")


_SEGMENT_DEFAULT_MIN = 0
_SEGMENT_DEFAULT_MAX = 100
_SEGMENT_DEFAULT_THRESHOLD = 60


class SegmentFitChecker(Guard):
    """facts["segment_scores"] が Task 8 の分類ルール(0-100 の整数・閾値60)に準拠することを検査。

    kpi["segment_thresholds"][segment] = {"min": 0, "max": 100, "threshold": 60}。
    min/max/threshold を省略した場合は 0 / 100 / 60 を使う。

    検査項目(segment_scores の各セグメントについて):
      1. セグメント名が kpi.segment_thresholds に定義されている
      2. 閾値定義そのものが妥当(数値で 0 <= min <= threshold <= max <= 100)
      3. スコアが整数(bool・小数は不可)
      4. スコアが [min, max] の範囲内

    threshold(既定60)は下流(Task 6/8 の分類)が使うメタデータで、本ガードは強制しない
    (低スコアも正当なデータ。2026-10-02 統括裁定)。定義の妥当性だけ検査する。

    segment_scores が無い・空なら検査対象が無いので素通り。検査対象があるのに
    segment_thresholds が無い・空・不正なときは、ガード無効化を防ぐため FactsError にする。
    weekly_metrics は本クラスでは使わない。
    """

    def verify(self, facts: Dict[str, Any], weekly_metrics: Dict[str, Any], kpi: Dict[str, Any]) -> None:
        scores = facts.get("segment_scores")
        if scores is None or scores == {}:
            return
        if not isinstance(scores, dict):
            raise FactsError(f"segment_scores must be a dict, got {type(scores).__name__}")

        thresholds = kpi.get("segment_thresholds") if isinstance(kpi, dict) else None
        if not isinstance(thresholds, dict) or not thresholds:
            raise FactsError(
                "kpi['segment_thresholds'] is missing or empty; refusing to skip the segment score check "
                "(add segment_thresholds to data/kekka_kpi.json)"
            )

        for segment, score in scores.items():
            if segment not in thresholds:
                raise FactsError(
                    f"segment '{segment}' not defined in kpi.segment_thresholds. "
                    f"Valid segments: {sorted(thresholds)}"
                )
            min_val, max_val, _threshold = self._rule(segment, thresholds[segment])

            if not isinstance(score, int) or isinstance(score, bool):
                raise FactsError(f"segment '{segment}' score must be an integer, got {score!r}")
            if score < min_val or score > max_val:
                raise FactsError(f"segment '{segment}' score {score} out of range [{min_val}, {max_val}]")

    @staticmethod
    def _rule(segment: str, rule: Any):
        """kpi の閾値定義を検証して (min, max, threshold) を返す。"""
        if not isinstance(rule, dict):
            raise FactsError(f"kpi.segment_thresholds['{segment}'] must be a dict, got {rule!r}")
        min_val = rule.get("min", _SEGMENT_DEFAULT_MIN)
        max_val = rule.get("max", _SEGMENT_DEFAULT_MAX)
        threshold = rule.get("threshold", _SEGMENT_DEFAULT_THRESHOLD)
        for label, value in (("min", min_val), ("max", max_val), ("threshold", threshold)):
            if not _is_number(value):
                raise FactsError(f"kpi.segment_thresholds['{segment}'].{label} must be a number, got {value!r}")
        if not (_SEGMENT_DEFAULT_MIN <= min_val <= threshold <= max_val <= _SEGMENT_DEFAULT_MAX):
            raise FactsError(
                f"kpi.segment_thresholds['{segment}'] is invalid: need "
                f"0 <= min({min_val}) <= threshold({threshold}) <= max({max_val}) <= 100"
            )
        return min_val, max_val, threshold
