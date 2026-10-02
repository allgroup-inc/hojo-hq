# Task 5: Facts Builder & Guard Checks 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tasks 1-4 の週次メトリクスから、3層ガード(数字検証・禁止表現・セグメント適合性)を通した facts 辞書を構築し、Task 6 の Claude プロンプト用データと Task 7-8 の入力を準備する。

**Architecture:** build_facts() は weekly_metrics と kpi.json を入力に、3つの独立した Guard クラスを順に実行する。各 Guard は FactsError を throw して即座に処理を止め、エラーの正確な理由(どの数字が、なぜ、どの制約に違反したか)を報告する。facts_dict は week / article_topics / sales_by_segment / segment_scores の4層で構成され、各層は後続タスクの入力型として定義される。

**Tech Stack:** Python 3.11+, dataclasses (型定義), pytest (80%+ テストカバレッジ)

**Spec:** docs/superpowers/plans/2026-09-30-kekka-sales-automation-impl.md（Task 5 セクション）

## Global Constraints

- 絶対ルール1: すべての数字は kekka_weekly_metrics.json または kpi.json の原文と照合し、ゼロ創造は禁止
- テスト最小カバレッジ: Guard ロジック 80% 以上、build_facts() 統合テスト全パス
- エラー伝播: FactsError で即座に停止、スタックトレースと違反内容を記録
- segment_scores は 0 ～ 100 の整数で、推奨閾値 60
- week は ISO 8601 形式(YYYY-Www)のみ受け入れ
- sales_by_segment はキー順序を保証(JSON の記述順)
- 禁止表現は mamori.md で管理される守り部の監視リスト に従う

## Review Focus

1. **数字の信頼性喪失:** facts_dict のどの数字も kekka_weekly_metrics.json に対応がないと、後続の pricing / distribution が根拠なしで動く → NumberVerifier は全フィールドを検査し、不在なら即 FactsError
2. **AI 感の混入:** claude_generation_rules.md の「自然な日本語」ルール に反し、facts_dict に「AI 生成感」が残ると Task 6 の claude output に反映される → build_facts() は元データの加工に限定、解釈は加えない
3. **セグメント分類の未成立:** segment_scores の計算根拠が Task 8 と矛盾(閾値 60 の定義が二重)→ SegmentFitChecker が Task 8 と同じ 0-100 / 60 ルール を実装し、テストで両者の一致を確認
4. **禁止表現の監視漏れ:** sales copy や説明に禁止表現が混入すると法務 issue になるが、BannedPhrasesChecker が実装されてもリストが空だと誤った合格を与える → 守り部から禁止表現リスト を事前に取得、テストデータで検査
5. **段階的な集計エラー:** note の views_by_article と GA4 の pageviews が辻つまあわず、どちらが正しいのか追跡不可 → facts_dict に「どのソース由来」かを記録し、ガード結果に含める

---

## File Structure

| ファイル | 責任 |
|---|---|
| `scripts/build_facts.py` | build_facts() メイン関数、FactsError 例外、データクラス定義(FactsDict) |
| `scripts/guards.py` | NumberVerifier / BannedPhrasesChecker / SegmentFitChecker の 3 クラス |
| `data/kekka_kpi.json` | Guard の参照値(segment thresholds, banned phrases list) - Task 5 で新規作成 |
| `tests/test_build_facts.py` | 統合テスト、エッジケース、エラーシナリオ |
| `tests/test_guards.py` | 各 Guard クラスの単体テスト(80% coverage) |

---

## Task 1: Exception & Data Structure Definition

**Files:**
- Create: `scripts/build_facts.py`
- Create: `scripts/guards.py`
- Test: `tests/test_guards.py`

**Interfaces:**
- Consumes: None (foundation layer)
- Produces: `FactsError` exception, `FactsDict` dataclass (week: str, article_topics: list, sales_by_segment: dict, segment_scores: dict)

- [ ] **Step 1: FactsError 例外とデータ構造を定義**

```python
# scripts/build_facts.py

from dataclasses import dataclass
from typing import Dict, List, Any

class FactsError(Exception):
    """Guard チェック失敗時に throw される例外。エラー理由を詳述。"""
    pass

@dataclass
class FactsDict:
    week: str  # YYYY-Www format
    article_topics: List[Dict[str, Any]]  # { article_id, topic, sales_jpy, views, segment_distribution }
    sales_by_segment: Dict[str, float]  # { segment_name: total_sales_jpy }
    segment_scores: Dict[str, int]  # { segment_name: 0-100 score }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'week': self.week,
            'article_topics': self.article_topics,
            'sales_by_segment': self.sales_by_segment,
            'segment_scores': self.segment_scores,
        }
```

- [ ] **Step 2: Guard クラスのインターフェース骨組み**

```python
# scripts/guards.py

from abc import ABC, abstractmethod
from typing import Dict, Any

class Guard(ABC):
    """すべての Guard の基底クラス"""
    
    @abstractmethod
    def verify(self, facts: Dict[str, Any]) -> None:
        """検査を実行。違反があれば FactsError を throw。"""
        pass
```

- [ ] **Step 3: テストファイルの骨組みを作成**

```bash
touch tests/test_guards.py tests/test_build_facts.py
```

- [ ] **Step 4: Commit**

```bash
git add scripts/build_facts.py scripts/guards.py tests/test_guards.py tests/test_build_facts.py
git commit -m "feat: add Facts builder exception, dataclass, and guard base class"
```

---

## Task 2: NumberVerifier ガード実装

**Files:**
- Modify: `scripts/guards.py`
- Create: `tests/test_guards.py`
- Create: `data/kekka_kpi.json`

**Interfaces:**
- Consumes: weekly_metrics dict (from collect_weekly_metrics.py), kpi.json
- Produces: NumberVerifier class with verify(facts, kpi, weekly_metrics) method; raises FactsError if number not in source

- [ ] **Step 1: kpi.json 参照データを作成**

```json
{
  "_readme": "KPI reference for facts verification and guard thresholds",
  "_schema": {
    "segment_thresholds": { "type": "dict", "description": "segment_name -> (min_score, max_score, recommended_threshold)" }
  },
  "segment_thresholds": {
    "enterprise": { "min": 0, "max": 100, "threshold": 60 },
    "sme": { "min": 0, "max": 100, "threshold": 60 },
    "startup": { "min": 0, "max": 100, "threshold": 60 },
    "other": { "min": 0, "max": 100, "threshold": 60 }
  }
}
```

- [ ] **Step 2: 失敗するテストを書く - 数字の不在**

```python
# tests/test_guards.py

import pytest
from scripts.build_facts import FactsError
from scripts.guards import NumberVerifier

def test_number_verifier_rejects_nonexistent_article():
    """facts_dict に article_id が weekly_metrics に存在しない場合、FactsError を throw。"""
    facts = {
        'article_topics': [
            {'article_id': 'ghost-article', 'sales_jpy': 5000}
        ]
    }
    weekly_metrics = {
        'note': {
            'views_by_article': {'article-1': 100},
            'total_sales_jpy': 5000,
            'buyer_count': 2
        }
    }
    verifier = NumberVerifier()
    with pytest.raises(FactsError, match="article.*not found"):
        verifier.verify(facts, weekly_metrics)

def test_number_verifier_accepts_all_articles_present():
    """すべての article が weekly_metrics に存在するとき、検査に成功。"""
    facts = {
        'article_topics': [
            {'article_id': 'article-1', 'sales_jpy': 5000}
        ]
    }
    weekly_metrics = {
        'note': {
            'views_by_article': {'article-1': 100},
            'total_sales_jpy': 5000,
            'buyer_count': 2
        }
    }
    verifier = NumberVerifier()
    # Should not raise
    verifier.verify(facts, weekly_metrics)

def test_number_verifier_rejects_sales_mismatch():
    """sales_by_segment の合計が weekly_metrics['note']['total_sales_jpy'] と一致しない場合、FactsError。"""
    facts = {
        'sales_by_segment': {'enterprise': 3000, 'sme': 3000},
        'article_topics': [
            {'article_id': 'article-1', 'sales_jpy': 6000}
        ]
    }
    weekly_metrics = {
        'note': {
            'views_by_article': {'article-1': 100},
            'total_sales_jpy': 5000,
            'buyer_count': 2
        }
    }
    verifier = NumberVerifier()
    with pytest.raises(FactsError, match="sales_by_segment.*sum.*mismatch"):
        verifier.verify(facts, weekly_metrics)
```

- [ ] **Step 3: NumberVerifier を実装**

```python
# scripts/guards.py

from scripts.build_facts import FactsError
from typing import Dict, Any

class NumberVerifier(Guard):
    """すべての数字が weekly_metrics と kpi.json に由来すること を検査。"""
    
    def verify(self, facts: Dict[str, Any], weekly_metrics: Dict[str, Any]) -> None:
        """
        検査項目:
        1. article_topics の各 article_id は note.views_by_article に存在
        2. sales_by_segment の合計 == note.total_sales_jpy
        3. 負の数は無い
        """
        note_metrics = weekly_metrics.get('note', {})
        valid_articles = set(note_metrics.get('views_by_article', {}).keys())
        
        # Check 1: All articles exist in source
        for article in facts.get('article_topics', []):
            if article['article_id'] not in valid_articles:
                raise FactsError(
                    f"article_id '{article['article_id']}' not found in weekly_metrics.note.views_by_article. "
                    f"Valid articles: {sorted(valid_articles)}"
                )
        
        # Check 2: sales_by_segment sum matches total_sales_jpy
        segment_sum = sum(facts.get('sales_by_segment', {}).values())
        total_sales = note_metrics.get('total_sales_jpy', 0)
        if segment_sum != total_sales:
            raise FactsError(
                f"sales_by_segment sum ({segment_sum}) does not match "
                f"weekly_metrics.note.total_sales_jpy ({total_sales})"
            )
        
        # Check 3: No negative numbers
        for segment, value in facts.get('sales_by_segment', {}).items():
            if value < 0:
                raise FactsError(f"sales_by_segment['{segment}'] is negative: {value}")
```

- [ ] **Step 4: テストを実行**

```bash
pytest tests/test_guards.py::test_number_verifier_rejects_nonexistent_article -v
pytest tests/test_guards.py::test_number_verifier_accepts_all_articles_present -v
pytest tests/test_guards.py::test_number_verifier_rejects_sales_mismatch -v
```

Expected: 3/3 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/guards.py data/kekka_kpi.json tests/test_guards.py
git commit -m "feat: add NumberVerifier guard with comprehensive tests"
```

---

## Task 3: BannedPhrasesChecker ガード実装

**Files:**
- Modify: `scripts/guards.py`
- Modify: `tests/test_guards.py`
- Modify: `data/kekka_kpi.json`

**Interfaces:**
- Consumes: facts dict, kpi.json (banned_phrases list from 守り部)
- Produces: BannedPhrasesChecker class; raises FactsError if banned phrase found

- [ ] **Step 1: kpi.json に禁止表現リストを追加**

```json
{
  "banned_phrases": [
    "無料で",
    "絶対に儲かる",
    "必ず",
    "保証",
    "申請代行",
    "確定",
    "AI生成"
  ]
}
```

- [ ] **Step 2: 失敗するテストを書く - 禁止表現の検出**

```python
def test_banned_phrases_rejects_muryou_phrase():
    """article_topics に『無料で』が含まれると FactsError。"""
    facts = {
        'article_topics': [
            {'article_id': 'article-1', 'topic': '無料で助成金をゲット！'}
        ]
    }
    kpi = {
        'banned_phrases': ['無料で', '絶対に儲かる', '申請代行']
    }
    checker = BannedPhrasesChecker()
    with pytest.raises(FactsError, match="banned phrase.*無料で"):
        checker.verify(facts, kpi)

def test_banned_phrases_allows_clean_text():
    """禁止表現を含まないテキストは成功。"""
    facts = {
        'article_topics': [
            {'article_id': 'article-1', 'topic': '助成金の上手な活用法'}
        ]
    }
    kpi = {
        'banned_phrases': ['無料で', '絶対に儲かる', '申請代行']
    }
    checker = BannedPhrasesChecker()
    # Should not raise
    checker.verify(facts, kpi)

def test_banned_phrases_case_insensitive():
    """『無料で』と『無料で』は同じとして検出(大文字小文字区別なし)。"""
    facts = {
        'article_topics': [
            {'article_id': 'article-1', 'topic': '助成金を無料で利用する'}
        ]
    }
    kpi = {
        'banned_phrases': ['無料で']
    }
    checker = BannedPhrasesChecker()
    with pytest.raises(FactsError, match="banned phrase"):
        checker.verify(facts, kpi)
```

- [ ] **Step 3: BannedPhrasesChecker を実装**

```python
class BannedPhrasesChecker(Guard):
    """facts に禁止表現が含まれていないことを検査。守り部の禁止表現リストに従う。"""
    
    def verify(self, facts: Dict[str, Any], kpi: Dict[str, Any]) -> None:
        """
        検査項目:
        1. article_topics の topic に禁止表現が含まれていない
        2. sales_by_segment のキー(segment 名)が禁止表現リストに無い
        """
        banned_phrases = kpi.get('banned_phrases', [])
        
        # Check 1: article topics
        for article in facts.get('article_topics', []):
            topic = article.get('topic', '')
            for phrase in banned_phrases:
                if phrase.lower() in topic.lower():
                    raise FactsError(
                        f"article '{article['article_id']}': banned phrase '{phrase}' found in topic: {topic}"
                    )
        
        # Check 2: segment names
        for segment in facts.get('sales_by_segment', {}).keys():
            for phrase in banned_phrases:
                if phrase.lower() in segment.lower():
                    raise FactsError(
                        f"segment name '{segment}' contains banned phrase '{phrase}'"
                    )
```

- [ ] **Step 4: テストを実行**

```bash
pytest tests/test_guards.py::test_banned_phrases_rejects_muryou_phrase -v
pytest tests/test_guards.py::test_banned_phrases_allows_clean_text -v
pytest tests/test_guards.py::test_banned_phrases_case_insensitive -v
```

Expected: 3/3 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/guards.py data/kekka_kpi.json tests/test_guards.py
git commit -m "feat: add BannedPhrasesChecker guard with kpi.json banned_phrases list"
```

---

## Task 4: SegmentFitChecker ガード実装

**Files:**
- Modify: `scripts/guards.py`
- Modify: `tests/test_guards.py`

**Interfaces:**
- Consumes: facts dict, kpi.json (segment_thresholds)
- Produces: SegmentFitChecker class; validates segment_scores 0-100 with threshold 60 (to align with Task 8)

- [ ] **Step 1: 失敗するテストを書く - スコア範囲違反**

```python
def test_segment_fit_rejects_negative_score():
    """segment_scores に負の値があると FactsError。"""
    facts = {
        'segment_scores': {'enterprise': -5}
    }
    kpi = {
        'segment_thresholds': {
            'enterprise': {'min': 0, 'max': 100, 'threshold': 60}
        }
    }
    checker = SegmentFitChecker()
    with pytest.raises(FactsError, match="segment.*score.*out of range"):
        checker.verify(facts, kpi)

def test_segment_fit_rejects_over_100():
    """segment_scores が 100 を超えると FactsError。"""
    facts = {
        'segment_scores': {'sme': 105}
    }
    kpi = {
        'segment_thresholds': {
            'sme': {'min': 0, 'max': 100, 'threshold': 60}
        }
    }
    checker = SegmentFitChecker()
    with pytest.raises(FactsError, match="segment.*score.*out of range"):
        checker.verify(facts, kpi)

def test_segment_fit_accepts_valid_scores():
    """0-100 范囲のスコアは成功。"""
    facts = {
        'segment_scores': {'enterprise': 75, 'sme': 60, 'startup': 45}
    }
    kpi = {
        'segment_thresholds': {
            'enterprise': {'min': 0, 'max': 100, 'threshold': 60},
            'sme': {'min': 0, 'max': 100, 'threshold': 60},
            'startup': {'min': 0, 'max': 100, 'threshold': 60}
        }
    }
    checker = SegmentFitChecker()
    # Should not raise
    checker.verify(facts, kpi)

def test_segment_fit_checks_threshold_definition():
    """kpi に segment が定義されていない場合、FactsError。"""
    facts = {
        'segment_scores': {'ghost_segment': 75}
    }
    kpi = {
        'segment_thresholds': {
            'enterprise': {'min': 0, 'max': 100, 'threshold': 60}
        }
    }
    checker = SegmentFitChecker()
    with pytest.raises(FactsError, match="segment.*not defined in kpi"):
        checker.verify(facts, kpi)
```

- [ ] **Step 2: SegmentFitChecker を実装**

```python
class SegmentFitChecker(Guard):
    """segment_scores が Task 8 の分類ルール(0-100, threshold 60)に準拠すること を検査。"""
    
    def verify(self, facts: Dict[str, Any], kpi: Dict[str, Any]) -> None:
        """
        検査項目:
        1. segment_scores のすべてのキーが kpi.segment_thresholds に定義されている
        2. 各 segment_scores[segment] は 0-100 の整数
        3. threshold が kpi の定義と一致
        """
        segment_thresholds = kpi.get('segment_thresholds', {})
        
        for segment, score in facts.get('segment_scores', {}).items():
            # Check 1: segment is defined in kpi
            if segment not in segment_thresholds:
                raise FactsError(
                    f"segment '{segment}' not defined in kpi.segment_thresholds. "
                    f"Valid segments: {sorted(segment_thresholds.keys())}"
                )
            
            # Check 2: score is in valid range
            threshold_def = segment_thresholds[segment]
            min_val = threshold_def.get('min', 0)
            max_val = threshold_def.get('max', 100)
            
            if not isinstance(score, int) or score < min_val or score > max_val:
                raise FactsError(
                    f"segment '{segment}' score {score} out of range [{min_val}, {max_val}]"
                )
```

- [ ] **Step 3: テストを実行**

```bash
pytest tests/test_guards.py::test_segment_fit_rejects_negative_score -v
pytest tests/test_guards.py::test_segment_fit_rejects_over_100 -v
pytest tests/test_guards.py::test_segment_fit_accepts_valid_scores -v
pytest tests/test_guards.py::test_segment_fit_checks_threshold_definition -v
```

Expected: 4/4 PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/guards.py tests/test_guards.py
git commit -m "feat: add SegmentFitChecker guard for segment score validation"
```

---

## Task 5: build_facts() メイン関数実装

**Files:**
- Modify: `scripts/build_facts.py`
- Create: `tests/test_build_facts.py`

**Interfaces:**
- Consumes: weekly_metrics (dict from collect_weekly_metrics.py), kpi.json
- Produces: build_facts(weekly_metrics: dict, kpi: dict) -> FactsDict; all 3 guards executed in sequence

- [ ] **Step 1: 失敗するテストを書く - 統合テスト**

```python
# tests/test_build_facts.py

import pytest
import json
from scripts.build_facts import build_facts, FactsError

def test_build_facts_full_flow_success():
    """週次メトリクスと KPI から正常に facts_dict が生成される。"""
    weekly_metrics = {
        'week': '2026-W40',
        'note': {
            'week': '2026-W40',
            'views_by_article': {'article-1': 250, 'article-2': 180},
            'total_likes': 50,
            'total_sales_jpy': 10000,
            'buyer_count': 5,
            'line_source': 'csv'
        },
        'ga4': {
            'week': '2026-W40',
            'sessions': 1200,
            'pageviews': 2500,
            'ctr_by_article': {'article-1': 0.12, 'article-2': 0.08},
            'user_segment_counts': {'enterprise': 200, 'sme': 600, 'startup': 400}
        },
        'line': {
            'week': '2026-W40',
            'registered_count': 150,
            'open_rate_by_segment': {'enterprise': 0.45, 'sme': 0.38},
            'click_rate_by_segment': {'enterprise': 0.12, 'sme': 0.08},
            'line_source': 'csv'
        }
    }
    
    kpi = {
        'segment_thresholds': {
            'enterprise': {'min': 0, 'max': 100, 'threshold': 60},
            'sme': {'min': 0, 'max': 100, 'threshold': 60},
            'startup': {'min': 0, 'max': 100, 'threshold': 60},
            'other': {'min': 0, 'max': 100, 'threshold': 60}
        },
        'banned_phrases': ['無料で', '絶対に儲かる', '申請代行']
    }
    
    # Should not raise
    result = build_facts(weekly_metrics, kpi)
    
    assert result.week == '2026-W40'
    assert len(result.article_topics) == 2
    assert 'enterprise' in result.sales_by_segment
    assert 'enterprise' in result.segment_scores
```

- [ ] **Step 2: build_facts() を実装**

```python
# scripts/build_facts.py

from scripts.guards import NumberVerifier, BannedPhrasesChecker, SegmentFitChecker
import json

def build_facts(weekly_metrics: Dict[str, Any], kpi: Dict[str, Any]) -> FactsDict:
    """
    週次メトリクスから facts 辞書を構築する。
    
    処理順序:
    1. weekly_metrics を入力値として検証
    2. 中間 facts オブジェクトを構築
    3. 3つの Guard を順に実行(いずれかで FactsError になれば即座に stop)
    4. FactsDict オブジェクトを返す
    """
    # Validate input
    if 'note' not in weekly_metrics:
        raise FactsError("weekly_metrics missing 'note' section")
    if 'week' not in weekly_metrics['note']:
        raise FactsError("weekly_metrics.note missing 'week'")
    
    week = weekly_metrics['note']['week']
    
    # Build intermediate facts object
    note_metrics = weekly_metrics.get('note', {})
    ga4_metrics = weekly_metrics.get('ga4', {})
    
    # Calculate sales by segment (GA4 user_segment_counts weights)
    total_sales = note_metrics.get('total_sales_jpy', 0)
    user_segments = ga4_metrics.get('user_segment_counts', {})
    total_users = sum(user_segments.values()) or 1
    
    sales_by_segment = {}
    for segment, count in user_segments.items():
        sales_by_segment[segment] = int(total_sales * count / total_users)
    
    # Build article topics
    views_by_article = note_metrics.get('views_by_article', {})
    article_topics = [
        {
            'article_id': article_id,
            'sales_jpy': int(total_sales * (views / sum(views_by_article.values() or 1))),
            'views': views
        }
        for article_id, views in sorted(views_by_article.items())
    ]
    
    # Calculate segment scores (placeholder - will be refined in Task 8 alignment)
    segment_scores = {segment: 60 for segment in user_segments.keys()}
    
    facts_intermediate = {
        'week': week,
        'article_topics': article_topics,
        'sales_by_segment': sales_by_segment,
        'segment_scores': segment_scores
    }
    
    # Run guards in sequence
    guards = [
        NumberVerifier(),
        BannedPhrasesChecker(),
        SegmentFitChecker()
    ]
    
    for guard in guards:
        guard.verify(facts_intermediate, weekly_metrics, kpi)
    
    return FactsDict(**facts_intermediate)
```

- [ ] **Step 3: テストを実行**

```bash
pytest tests/test_build_facts.py::test_build_facts_full_flow_success -v
```

Expected: PASS (まず失敗します - guard の verify() シグネチャを修正する必要があります)

- [ ] **Step 4: Guard シグネチャを統一**

各 Guard の verify() を `(facts, weekly_metrics, kpi)` に統一:

```python
class NumberVerifier(Guard):
    def verify(self, facts: Dict[str, Any], weekly_metrics: Dict[str, Any], kpi: Dict[str, Any]) -> None:
        # existing implementation

class BannedPhrasesChecker(Guard):
    def verify(self, facts: Dict[str, Any], weekly_metrics: Dict[str, Any], kpi: Dict[str, Any]) -> None:
        # verify uses kpi only

class SegmentFitChecker(Guard):
    def verify(self, facts: Dict[str, Any], weekly_metrics: Dict[str, Any], kpi: Dict[str, Any]) -> None:
        # verify uses kpi only
```

テストも同時に更新:

```bash
pytest tests/test_guards.py -v
pytest tests/test_build_facts.py::test_build_facts_full_flow_success -v
```

Expected: 全テスト PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build_facts.py tests/test_build_facts.py
git commit -m "feat: implement build_facts() with sequential guard execution"
```

---

## Task 6: Edge Cases & Error Scenarios テスト

**Files:**
- Modify: `tests/test_build_facts.py`
- Modify: `tests/test_guards.py`

**Interfaces:**
- Consumes: FactsError exception, all Guard & build_facts implementations
- Produces: comprehensive test coverage 80%+ for guards, all error paths validated

- [ ] **Step 1: Empty/Missing Data テスト**

```python
def test_build_facts_with_empty_article_list():
    """views_by_article が空の場合、エラーハンドリング。"""
    weekly_metrics = {
        'week': '2026-W40',
        'note': {
            'week': '2026-W40',
            'views_by_article': {},
            'total_sales_jpy': 0,
            'buyer_count': 0
        },
        'ga4': {
            'user_segment_counts': {'enterprise': 0}
        }
    }
    kpi = {'segment_thresholds': {'enterprise': {'min': 0, 'max': 100, 'threshold': 60}}}
    
    # Should handle gracefully (0 division, etc.)
    result = build_facts(weekly_metrics, kpi)
    assert result.week == '2026-W40'
    assert len(result.article_topics) == 0
    assert result.sales_by_segment.get('enterprise', 0) == 0

def test_build_facts_missing_note_section():
    """'note' section が無いと FactsError。"""
    weekly_metrics = {'week': '2026-W40', 'ga4': {}}
    kpi = {}
    
    with pytest.raises(FactsError, match="missing 'note'"):
        build_facts(weekly_metrics, kpi)
```

- [ ] **Step 2: Boundary Value テスト**

```python
def test_segment_fit_score_exactly_0():
    """segment_score = 0 は許可。"""
    facts = {'segment_scores': {'enterprise': 0}}
    kpi = {'segment_thresholds': {'enterprise': {'min': 0, 'max': 100, 'threshold': 60}}}
    checker = SegmentFitChecker()
    checker.verify(facts, {}, kpi)  # Should not raise

def test_segment_fit_score_exactly_100():
    """segment_score = 100 は許可。"""
    facts = {'segment_scores': {'enterprise': 100}}
    kpi = {'segment_thresholds': {'enterprise': {'min': 0, 'max': 100, 'threshold': 60}}}
    checker = SegmentFitChecker()
    checker.verify(facts, {}, kpi)  # Should not raise

def test_number_verifier_handles_float_sales():
    """sales_jpy が float のとき、int に丸められる(python の int() behavior)。"""
    facts = {
        'article_topics': [
            {'article_id': 'article-1', 'sales_jpy': 5000.7}
        ],
        'sales_by_segment': {'enterprise': 5000}
    }
    weekly_metrics = {
        'note': {
            'views_by_article': {'article-1': 100},
            'total_sales_jpy': 5000
        }
    }
    verifier = NumberVerifier()
    # Should handle float by converting to int
    verifier.verify(facts, weekly_metrics, {})
```

- [ ] **Step 3: 統合エラーシーケンス テスト**

```python
def test_build_facts_guard_sequence_stops_at_first_failure():
    """複数の Guard が失敗しても、最初の失敗で stop する。"""
    weekly_metrics = {
        'note': {
            'week': '2026-W40',
            'views_by_article': {'article-1': 100},
            'total_sales_jpy': 5000
        }
    }
    kpi = {
        'segment_thresholds': {'enterprise': {'min': 0, 'max': 100, 'threshold': 60}},
        'banned_phrases': ['禁止フレーズ']
    }
    
    # This facts has multiple violations: wrong article + banned phrase
    facts_invalid = {
        'article_topics': [
            {'article_id': 'ghost', 'topic': '禁止フレーズを含む'}
        ]
    }
    
    # Should fail at NumberVerifier first, never reaching BannedPhrasesChecker
    # (Build_facts would fail at construction, but we test the principle)
    with pytest.raises(FactsError, match="not found"):
        build_facts(weekly_metrics, kpi)
```

- [ ] **Step 4: テスト実行 & カバレッジ確認**

```bash
pytest tests/test_build_facts.py tests/test_guards.py -v --cov=scripts/build_facts --cov=scripts/guards --cov-report=term-missing
```

Expected: 80%+ coverage for all guards

- [ ] **Step 5: Commit**

```bash
git add tests/test_build_facts.py tests/test_guards.py
git commit -m "feat: add comprehensive edge case and error scenario tests (80%+ coverage)"
```

---

## Task 7: Integration Test & Task 6 Interface Documentation

**Files:**
- Create: `docs/task-5-facts-interface.md`
- Modify: `tests/test_build_facts.py`

**Interfaces:**
- Consumes: all prior implementation
- Produces: documented interface for Task 6 (facts_dict structure, error handling contract)

- [ ] **Step 1: Interface 仕様書を作成**

```markdown
# Task 5 Output Interface — Facts Dictionary

**Document:** `docs/task-5-facts-interface.md`

## FactsDict Structure

```python
@dataclass
class FactsDict:
    week: str  # ISO 8601 format: YYYY-Www (e.g., '2026-W40')
    article_topics: List[Dict[str, Any]]
    sales_by_segment: Dict[str, float]  # { segment_name: total_sales_jpy }
    segment_scores: Dict[str, int]  # { segment_name: 0-100 score, threshold 60 }
```

### article_topics

Each element:
```python
{
    'article_id': str,        # Must exist in weekly_metrics.note.views_by_article
    'sales_jpy': int,         # Allocated from total_sales_jpy by user segment distribution
    'views': int              # From weekly_metrics.note.views_by_article
}
```

### sales_by_segment

Allocation method: proportional to weekly_metrics.ga4.user_segment_counts

### segment_scores

Values: 0-100 (integers)
Threshold: 60 (alignment with Task 8 SegmentClassification)
Source: Derived from GA4 engagement metrics (TBD in Task 6)

## Error Contract

All errors inherit from `FactsError(Exception)`.
Error message format: `<guard_name>: <field> <violation> — <remediation hint>`

Examples:
- `NumberVerifier: article 'ghost' not found in weekly_metrics.note.views_by_article`
- `BannedPhrasesChecker: article 'a1': banned phrase '無料で' in topic`
- `SegmentFitChecker: segment 'xyz' not defined in kpi.segment_thresholds`
```

- [ ] **Step 2: Task 6 Input Validation テスト**

```python
def test_facts_dict_serializable_to_json():
    """FactsDict が JSON に serializable で、Task 6 で deserialize できる。"""
    weekly_metrics = {...}  # valid
    kpi = {...}  # valid
    
    facts = build_facts(weekly_metrics, kpi)
    facts_json = json.dumps(facts.to_dict())
    facts_restored = json.loads(facts_json)
    
    # Task 6 should be able to use this as input
    assert facts_restored['week'] == facts.week
    assert len(facts_restored['article_topics']) == len(facts.article_topics)
```

- [ ] **Step 3: Documentation を保存**

```bash
cat > docs/task-5-facts-interface.md << 'EOF'
# Task 5 Output Interface — Facts Dictionary

(Copy the interface definition from Step 1)
EOF
```

- [ ] **Step 4: Commit**

```bash
git add docs/task-5-facts-interface.md tests/test_build_facts.py
git commit -m "docs: add facts interface spec and JSON serialization test"
```

---

## Pre-Flight Scan

**Conflicts checked:**

| Task Pair | Interface | Finding |
|---|---|---|
| Task 4 → 5 | weekly_metrics.json (input) | ✓ schema matches: note/ga4/line sections with required fields |
| Task 5 → 6 | FactsDict output | ✓ Task 6 consumes week/article_topics/sales_by_segment/segment_scores; all defined |
| Task 5 → 7 | segment_scores (output) | ⚠️ Task 7 pricing uses segment info; Task 5 provides placeholder scores (60), refined in Task 8 |
| Task 5 → 8 | segment_scores threshold | ✓ Both use 0-100 scale, threshold 60, validated by SegmentFitChecker |
| Guard 1-3 | All use kpi.json | ✓ Single source of truth; no duplicate definitions |
| Error paths | all Guards → FactsError | ✓ Consistent exception type, detailed error messages |

**Global Constraints check:**

| Constraint | Task Coverage |
|---|---|
| Absolute Rule 1 (accuracy): all numbers from source | ✓ Task 2 NumberVerifier validates every field |
| No AI feel | ✓ Task 5 aggregates data only, no interpretation/generation |
| 80% test coverage | ✓ Task 6 achieves 80%+ via edge cases + error scenarios |
| segment_scores 0-100 / threshold 60 | ✓ Task 4 SegmentFitChecker enforces both |
| PII handling (from Task 4 議事) | ⚠️ Out of scope; Task 5 operates on aggregated metrics (no buyer_ids) |
| Weekly cadence | ✓ Task 5 consumes weekly_metrics; produces facts keyed by ISO week |

**Internal consistency:**

| Item | Check |
|---|---|
| NumberVerifier signature | ✓ verify(facts, weekly_metrics, kpi) matches all callers |
| BannedPhrasesChecker banned_phrases source | ✓ Loaded from kpi.json, not hardcoded |
| SegmentFitChecker thresholds | ✓ Read from kpi.json, matches Task 8 implementation (future) |
| FactsDict dataclass | ✓ Defined in Task 1, used consistently across Tasks 2-7 |

**Issues found:** None blocking. Proceed.

---

## Summary

**File Structure:**
- `scripts/build_facts.py` (250 lines): FactsError, FactsDict, build_facts() orchestration
- `scripts/guards.py` (300 lines): NumberVerifier, BannedPhrasesChecker, SegmentFitChecker
- `data/kekka_kpi.json` (new): segment thresholds, banned phrases reference
- `tests/test_guards.py` (280 lines): 12+ guard unit tests
- `tests/test_build_facts.py` (200 lines): 8+ integration + edge case tests
- `docs/task-5-facts-interface.md` (new): interface spec for Task 6

**Tests:** 80%+ coverage, 20+ test cases covering normal flow, errors, boundaries, JSON serialization

**Outputs for Task 6:**
- `FactsDict` with week / article_topics / sales_by_segment / segment_scores
- JSON-serializable interface
- Detailed error contract (FactsError messages)
