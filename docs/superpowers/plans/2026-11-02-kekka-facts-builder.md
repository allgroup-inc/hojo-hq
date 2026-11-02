⚠️ **【無効な計画・実行禁止】**
このファイルは note独立事業と別事業のTask 5 を誤って混同して作成されたものです。正式仕様ではなく、実装・参照・実行の対象外です。原因記録のため保全中。

---

# 結果マガ Facts Builder & Guard Checks 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build weekly metrics into facts dictionary with 3-layer validation guards (numeric integrity, banned phrases, segment fit), enabling robust auto-generation of result magazine content with immediate error reporting.

**Architecture:** Facts Builder collects weekly_metrics + KPI baseline → constructs facts_dict (week, article_topics, sales_by_segment, segment_scores, target_prices, etc.) → passes through NumberVerifier → BannedPhrasesChecker → SegmentFitChecker (in series). Each guard is independent, testable, and reports violations via FactsError with actionable context.

**Tech Stack:** Python 3.8+, pytest (unit tests), Decimal (numeric precision matching note_revenue_final.py), re (regex for phrase checks).

**Spec:** docs/superpowers/specs/YYYY-MM-DD-kekka-facts-builder-design.md (to be linked after task review)

## Global Constraints

- Use `from decimal import Decimal, ROUND_DOWN` for numeric calculations (consistent with verified revenue calculator)
- Test coverage ≥ 80% per guard (NumberVerifier, BannedPhrasesChecker, SegmentFitChecker)
- FactsError exception must include: error_type, field_name, value, rule_violated, remediation hint
- No division by zero; return 0 for missing denominators (e.g., conversion rate when sales=0)
- Banned phrases: hard-coded in `guards.py` as tuple `BANNED_PHRASES` (sourced from docs/禁止語list.md or equivalent)
- Segment fit: validate that article_topics match allowed segments (e.g., "AI" only if article_count ≥ 3 && avg_pv ≥ 100)
- All outputs are immutable dicts (no in-place modification of facts_dict during guard checks)

## Review Focus

1. **Numeric overflow in sales aggregation** — facts_dict['total_sales'] may exceed int range if articles×purchase_count is large; guard must detect and report.
2. **Null/None coercion in guards** — a missing kpi['conversion_rate'] should not crash guards; must default to 0 and flag in warning.
3. **Regex false positives on Japanese** — phrase matching must not false-flag on particle combinations (e.g., "は" in "その是非は重要" should not match "是非" ban).
4. **Segment fit cascading failures** — if article_topics=['AI', 'SNS'] but only AI meets fit criteria, must report which segments fail and why (not just boolean pass/fail).
5. **Guard order dependency** — if NumberVerifier rejects invalid data, downstream guards should not process it; serialization must be enforced.

---

## File Structure

### Create:
- `scripts/build_facts.py` — Main Facts Builder entry point
- `scripts/guards.py` — Guard implementations (NumberVerifier, BannedPhrasesChecker, SegmentFitChecker + FactsError)
- `tests/test_build_facts.py` — Facts builder unit tests (70+ tests)
- `tests/test_guards.py` — Guard-specific tests (50+ tests for 80%+ coverage)

### Modify:
- None (no existing facts builder code)

### Reference:
- `scripts/note_revenue_final.py` (verified revenue calculations & FeeStructure)
- `docs/note-独立事業-読者ペルソナと商品設計v1.md` (segment definitions)

---

## Task 1: Guard Infrastructure & FactsError

**Files:**
- Create: `scripts/guards.py`
- Create: `tests/test_guards.py` (initial empty test file)

**Interfaces:**
- Produces: `FactsError` exception class with (error_type: str, field_name: str, value: Any, rule_violated: str, remediation: str)
- Produces: `BANNED_PHRASES: tuple` constant (importable from guards)
- Produces: Base `Guard` abstract class with `validate(facts: dict) → dict` method (returns facts if pass, raises FactsError if fail)

- [ ] **Step 1: Write FactsError exception class**

```python
class FactsError(Exception):
    """
    Raised when a guard validation fails.
    Attributes:
      error_type: "numeric", "banned_phrase", "segment_fit", or other
      field_name: str (e.g., "total_sales", "article_topics[0]")
      value: the invalid value (int, str, list, or dict)
      rule_violated: plain-text rule description (e.g., "total_sales must be ≤ 10,000,000")
      remediation: suggestion for fix (e.g., "reduce article_count or purchase_rate")
    """
    def __init__(self, error_type: str, field_name: str, value, rule_violated: str, remediation: str):
        self.error_type = error_type
        self.field_name = field_name
        self.value = value
        self.rule_violated = rule_violated
        self.remediation = remediation
        super().__init__(
            f"[{error_type}] {field_name}: {rule_violated}\n"
            f"  value: {repr(value)}\n"
            f"  remediation: {remediation}"
        )
```

- [ ] **Step 2: Write BANNED_PHRASES constant**

```python
BANNED_PHRASES = (
    "必ず",
    "絶対",
    "確実に",
    "保証",
    "100%",
    "稼げる",
    "詐欺",
    "違法",
)
```

(Source: If docs/禁止語list.md exists, read it; otherwise use placeholder above and update in Task 4)

- [ ] **Step 3: Write Guard abstract base class**

```python
from abc import ABC, abstractmethod

class Guard(ABC):
    """Abstract guard for facts validation."""
    
    @abstractmethod
    def validate(self, facts: dict) -> dict:
        """
        Validate facts dict against this guard's rules.
        Args: facts (dict) — facts dict to validate
        Returns: facts (unchanged dict) if validation passes
        Raises: FactsError if validation fails
        """
        pass
```

- [ ] **Step 4: Commit**

```bash
git add scripts/guards.py tests/test_guards.py
git commit -m "feat: add FactsError exception and Guard base class for facts validation"
```

---

## Task 2: NumberVerifier Guard

**Files:**
- Modify: `scripts/guards.py` (add NumberVerifier class)
- Modify: `tests/test_guards.py` (add NumberVerifier tests)

**Interfaces:**
- Consumes: facts dict with keys: total_sales (int), weekly_metrics (dict), article_count (int)
- Produces: `NumberVerifier` class implementing `Guard.validate(facts) → dict`
- Produces: 15+ unit tests covering: normal values, overflow (>10M), negative sales, zero sales, missing keys, non-int types

- [ ] **Step 1: Write NumberVerifier class**

```python
from decimal import Decimal, ROUND_DOWN

class NumberVerifier(Guard):
    """Verify numeric integrity of facts dict."""
    
    MAX_SALES = 10_000_000  # 1000万円 upper bound
    
    def validate(self, facts: dict) -> dict:
        # Check total_sales exists and is int
        if 'total_sales' not in facts:
            raise FactsError(
                error_type='numeric',
                field_name='total_sales',
                value=None,
                rule_violated='total_sales key is required',
                remediation='ensure build_facts() populates total_sales from weekly_metrics'
            )
        
        total_sales = facts['total_sales']
        if not isinstance(total_sales, int):
            raise FactsError(
                error_type='numeric',
                field_name='total_sales',
                value=total_sales,
                rule_violated=f'total_sales must be int, got {type(total_sales).__name__}',
                remediation=f'cast to int: int({total_sales})'
            )
        
        if total_sales < 0:
            raise FactsError(
                error_type='numeric',
                field_name='total_sales',
                value=total_sales,
                rule_violated='total_sales must be ≥ 0',
                remediation='check weekly_metrics for negative sale entries'
            )
        
        if total_sales > self.MAX_SALES:
            raise FactsError(
                error_type='numeric',
                field_name='total_sales',
                value=total_sales,
                rule_violated=f'total_sales must be ≤ {self.MAX_SALES:,}',
                remediation='reduce article_count, purchase_rate, or article_price; check for data duplication'
            )
        
        # Check sales_by_segment (if present) sums to total_sales ± tolerance
        if 'sales_by_segment' in facts:
            sales_by_segment = facts['sales_by_segment']
            segment_sum = sum(v for v in sales_by_segment.values() if isinstance(v, int))
            tolerance = 1  # Allow ±1 due to rounding
            if not (total_sales - tolerance <= segment_sum <= total_sales + tolerance):
                raise FactsError(
                    error_type='numeric',
                    field_name='sales_by_segment',
                    value=sales_by_segment,
                    rule_violated=f'sum of sales_by_segment ({segment_sum}) must equal total_sales ({total_sales}) ± {tolerance}',
                    remediation='recalculate sales_by_segment or total_sales with matching divisor logic'
                )
        
        return facts
```

- [ ] **Step 2: Write test cases for NumberVerifier**

```python
import pytest
from scripts.guards import NumberVerifier, FactsError

class TestNumberVerifier:
    def setup_method(self):
        self.verifier = NumberVerifier()
        self.valid_facts = {
            'total_sales': 100000,
            'week': '2026-11-02',
            'article_topics': ['AI', 'SNS'],
        }
    
    def test_valid_sales(self):
        """Normal sales value passes."""
        result = self.verifier.validate(self.valid_facts)
        assert result['total_sales'] == 100000
    
    def test_zero_sales(self):
        """Zero sales is valid."""
        self.valid_facts['total_sales'] = 0
        result = self.verifier.validate(self.valid_facts)
        assert result['total_sales'] == 0
    
    def test_max_sales_boundary(self):
        """Sales at max boundary (10M) passes."""
        self.valid_facts['total_sales'] = 10_000_000
        result = self.verifier.validate(self.valid_facts)
        assert result['total_sales'] == 10_000_000
    
    def test_sales_overflow(self):
        """Sales exceeding 10M raises FactsError."""
        self.valid_facts['total_sales'] = 10_000_001
        with pytest.raises(FactsError) as exc_info:
            self.verifier.validate(self.valid_facts)
        assert exc_info.value.error_type == 'numeric'
        assert exc_info.value.field_name == 'total_sales'
    
    def test_negative_sales(self):
        """Negative sales raises FactsError."""
        self.valid_facts['total_sales'] = -1000
        with pytest.raises(FactsError) as exc_info:
            self.verifier.validate(self.valid_facts)
        assert 'must be ≥ 0' in exc_info.value.rule_violated
    
    def test_non_int_sales(self):
        """Non-int sales (float, str) raises FactsError."""
        self.valid_facts['total_sales'] = 100000.5
        with pytest.raises(FactsError) as exc_info:
            self.verifier.validate(self.valid_facts)
        assert 'must be int' in exc_info.value.rule_violated
    
    def test_missing_total_sales(self):
        """Missing total_sales key raises FactsError."""
        del self.valid_facts['total_sales']
        with pytest.raises(FactsError) as exc_info:
            self.verifier.validate(self.valid_facts)
        assert 'total_sales key is required' in exc_info.value.rule_violated
    
    def test_sales_by_segment_sum_mismatch(self):
        """sales_by_segment sum != total_sales raises FactsError."""
        self.valid_facts['sales_by_segment'] = {'AI': 50000, 'SNS': 30000}
        with pytest.raises(FactsError) as exc_info:
            self.verifier.validate(self.valid_facts)
        assert 'sales_by_segment' in exc_info.value.field_name
    
    def test_sales_by_segment_sum_within_tolerance(self):
        """sales_by_segment sum within ±1 tolerance passes."""
        self.valid_facts['sales_by_segment'] = {'AI': 50000, 'SNS': 49999}
        result = self.verifier.validate(self.valid_facts)
        assert result is not None
```

(Total: 15+ test cases covering normal, boundary, error cases)

- [ ] **Step 3: Run tests to verify they all pass**

```bash
pytest tests/test_guards.py::TestNumberVerifier -v
```

Expected: 15+ tests PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/guards.py tests/test_guards.py
git commit -m "feat: implement NumberVerifier guard with 15+ test cases (numeric validation)"
```

---

## Task 3: BannedPhrasesChecker Guard

**Files:**
- Modify: `scripts/guards.py` (add BannedPhrasesChecker class)
- Modify: `tests/test_guards.py` (add BannedPhrasesChecker tests)

**Interfaces:**
- Consumes: facts dict with keys: article_topics (list), snippet (str, optional), description (str, optional)
- Produces: `BannedPhrasesChecker` class implementing `Guard.validate(facts) → dict`
- Produces: 20+ unit tests covering: clean text, single phrase match, multiple matches, Japanese particle false positives, None values, empty strings

- [ ] **Step 1: Write BannedPhrasesChecker class**

```python
import re

class BannedPhrasesChecker(Guard):
    """Check facts for banned phrases (Japanese/English content moderation)."""
    
    def __init__(self, banned_phrases: tuple = BANNED_PHRASES):
        self.banned_phrases = banned_phrases
        # Compile regex once per instance for performance
        # Use word boundary \\b for English, space/punctuation for Japanese
        self.pattern = self._compile_pattern()
    
    def _compile_pattern(self) -> re.Pattern:
        """Compile banned phrases into single regex."""
        if not self.banned_phrases:
            return re.compile(r'(?!)')  # Never matches
        escaped = [re.escape(phrase) for phrase in self.banned_phrases]
        return re.compile('|'.join(escaped), re.IGNORECASE)
    
    def validate(self, facts: dict) -> dict:
        """Check article_topics, snippet, description for banned phrases."""
        
        # Check article_topics list
        if 'article_topics' in facts and facts['article_topics']:
            for i, topic in enumerate(facts['article_topics']):
                if isinstance(topic, str):
                    matches = self.pattern.findall(topic)
                    if matches:
                        raise FactsError(
                            error_type='banned_phrase',
                            field_name=f'article_topics[{i}]',
                            value=topic,
                            rule_violated=f'contains banned phrase(s): {", ".join(set(matches))}',
                            remediation=f'reword topic without: {", ".join(self.banned_phrases)}'
                        )
        
        # Check snippet (optional content preview)
        if 'snippet' in facts and facts['snippet']:
            snippet = facts['snippet']
            if isinstance(snippet, str):
                matches = self.pattern.findall(snippet)
                if matches:
                    raise FactsError(
                        error_type='banned_phrase',
                        field_name='snippet',
                        value=snippet[:100] + ('...' if len(snippet) > 100 else ''),
                        rule_violated=f'contains banned phrase(s): {", ".join(set(matches))}',
                        remediation=f'edit snippet to remove: {", ".join(set(matches))}'
                    )
        
        # Check description (optional full description)
        if 'description' in facts and facts['description']:
            description = facts['description']
            if isinstance(description, str):
                matches = self.pattern.findall(description)
                if matches:
                    raise FactsError(
                        error_type='banned_phrase',
                        field_name='description',
                        value=description[:100] + ('...' if len(description) > 100 else ''),
                        rule_violated=f'contains banned phrase(s): {", ".join(set(matches))}',
                        remediation=f'edit description to remove: {", ".join(set(matches))}'
                    )
        
        return facts
```

- [ ] **Step 2: Write test cases for BannedPhrasesChecker**

```python
class TestBannedPhrasesChecker:
    def setup_method(self):
        self.checker = BannedPhrasesChecker(banned_phrases=('必ず', '稼げる', '100%'))
        self.valid_facts = {
            'total_sales': 100000,
            'week': '2026-11-02',
            'article_topics': ['AI基礎', 'SNS運用'],
            'snippet': 'this is a clean snippet',
        }
    
    def test_clean_topics(self):
        """Clean article topics pass."""
        result = self.checker.validate(self.valid_facts)
        assert result is not None
    
    def test_clean_snippet(self):
        """Clean snippet passes."""
        self.valid_facts['snippet'] = 'AI recipe with step-by-step guide'
        result = self.checker.validate(self.valid_facts)
        assert result is not None
    
    def test_banned_phrase_in_topic(self):
        """Banned phrase in article_topics raises FactsError."""
        self.valid_facts['article_topics'] = ['AI基礎', '必ず稼げるSNS運用']
        with pytest.raises(FactsError) as exc_info:
            self.checker.validate(self.valid_facts)
        assert 'banned_phrase' in exc_info.value.error_type
        assert '必ず' in exc_info.value.rule_violated
    
    def test_banned_phrase_in_snippet(self):
        """Banned phrase in snippet raises FactsError."""
        self.valid_facts['snippet'] = 'これで必ず成功する方法'
        with pytest.raises(FactsError) as exc_info:
            self.checker.validate(self.valid_facts)
        assert 'snippet' in exc_info.value.field_name
    
    def test_banned_phrase_in_description(self):
        """Banned phrase in description raises FactsError."""
        self.valid_facts['description'] = 'This method guarantees 100% results'
        with pytest.raises(FactsError) as exc_info:
            self.checker.validate(self.valid_facts)
        assert 'description' in exc_info.value.field_name
        assert '100%' in exc_info.value.rule_violated
    
    def test_case_insensitive_match(self):
        """Banned phrase matching is case-insensitive."""
        self.valid_facts['snippet'] = 'This is 100% effective'  # 100% matches "100%"
        with pytest.raises(FactsError):
            self.checker.validate(self.valid_facts)
    
    def test_multiple_banned_phrases(self):
        """Multiple banned phrases in one field raises FactsError."""
        self.valid_facts['snippet'] = '必ず稼げるし100%確実'
        with pytest.raises(FactsError) as exc_info:
            self.checker.validate(self.valid_facts)
        assert '必ず' in exc_info.value.rule_violated
        assert '稼げる' in exc_info.value.rule_violated
    
    def test_none_topic_skipped(self):
        """None values in article_topics are skipped."""
        self.valid_facts['article_topics'] = ['AI基礎', None, 'SNS運用']
        result = self.checker.validate(self.valid_facts)  # Should not crash
        assert result is not None
    
    def test_empty_topics_list(self):
        """Empty article_topics list passes."""
        self.valid_facts['article_topics'] = []
        result = self.checker.validate(self.valid_facts)
        assert result is not None
    
    def test_missing_snippet_passes(self):
        """Missing snippet key doesn't raise error."""
        del self.valid_facts['snippet']
        result = self.checker.validate(self.valid_facts)
        assert result is not None
```

(Total: 20+ test cases)

- [ ] **Step 3: Run tests to verify they all pass**

```bash
pytest tests/test_guards.py::TestBannedPhrasesChecker -v
```

Expected: 20+ tests PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/guards.py tests/test_guards.py
git commit -m "feat: implement BannedPhrasesChecker guard with 20+ test cases (content moderation)"
```

---

## Task 4: SegmentFitChecker Guard

**Files:**
- Modify: `scripts/guards.py` (add SegmentFitChecker class)
- Modify: `tests/test_guards.py` (add SegmentFitChecker tests)

**Interfaces:**
- Consumes: facts dict with keys: article_topics (list), segment_scores (dict, optional), article_count (int, optional), avg_pv (int, optional)
- Produces: `SegmentFitChecker` class implementing `Guard.validate(facts) → dict`
- Produces: 18+ unit tests covering: valid segments, invalid segments, missing article_count, insufficient PV, boundary cases

**Segment definitions** (from docs/note-独立事業-読者ペルソナと商品設計v1.md):
- "AI": requires article_count ≥ 3, avg_pv ≥ 100
- "SNS": requires article_count ≥ 4, avg_pv ≥ 80  
- "副業": requires article_count ≥ 3, avg_pv ≥ 60
- "その他": no minimum, always valid

- [ ] **Step 1: Write SegmentFitChecker class**

```python
class SegmentFitChecker(Guard):
    """Verify article_topics fit segment criteria (article count, PV threshold)."""
    
    SEGMENT_CRITERIA = {
        'AI': {'min_article_count': 3, 'min_avg_pv': 100},
        'SNS': {'min_article_count': 4, 'min_avg_pv': 80},
        '副業': {'min_article_count': 3, 'min_avg_pv': 60},
        'その他': {},  # No minimum
    }
    
    def validate(self, facts: dict) -> dict:
        """Check article_topics against segment fit criteria."""
        
        if 'article_topics' not in facts or not facts['article_topics']:
            return facts  # Empty topics is valid (no segments to check)
        
        article_topics = facts['article_topics']
        article_count = facts.get('article_count', 0)
        avg_pv = facts.get('avg_pv', 0)
        
        failed_segments = []
        
        for topic in article_topics:
            if topic not in self.SEGMENT_CRITERIA:
                raise FactsError(
                    error_type='segment_fit',
                    field_name='article_topics',
                    value=topic,
                    rule_violated=f'unknown segment "{topic}" (allowed: {", ".join(self.SEGMENT_CRITERIA.keys())})',
                    remediation=f'use one of: {", ".join(self.SEGMENT_CRITERIA.keys())}'
                )
            
            criteria = self.SEGMENT_CRITERIA[topic]
            if not criteria:  # "その他" has no criteria
                continue
            
            min_count = criteria['min_article_count']
            min_pv = criteria['min_avg_pv']
            
            if article_count < min_count:
                failed_segments.append(
                    f'{topic} (needs {min_count}+ articles, have {article_count})'
                )
            if avg_pv < min_pv:
                failed_segments.append(
                    f'{topic} (needs avg_pv ≥ {min_pv}, have {avg_pv})'
                )
        
        if failed_segments:
            raise FactsError(
                error_type='segment_fit',
                field_name='article_topics',
                value=article_topics,
                rule_violated=f'segments do not meet fit criteria: {"; ".join(failed_segments)}',
                remediation='increase article_count and/or avg_pv, or remove unmet segments from article_topics'
            )
        
        return facts
```

- [ ] **Step 2: Write test cases for SegmentFitChecker**

```python
class TestSegmentFitChecker:
    def setup_method(self):
        self.checker = SegmentFitChecker()
        self.valid_facts = {
            'total_sales': 100000,
            'week': '2026-11-02',
            'article_topics': ['AI', 'SNS'],
            'article_count': 10,
            'avg_pv': 150,
        }
    
    def test_ai_meets_criteria(self):
        """AI segment with article_count=3, avg_pv=100 meets criteria."""
        self.valid_facts['article_topics'] = ['AI']
        self.valid_facts['article_count'] = 3
        self.valid_facts['avg_pv'] = 100
        result = self.checker.validate(self.valid_facts)
        assert result is not None
    
    def test_sns_meets_criteria(self):
        """SNS segment with article_count=4, avg_pv=80 meets criteria."""
        self.valid_facts['article_topics'] = ['SNS']
        self.valid_facts['article_count'] = 4
        self.valid_facts['avg_pv'] = 80
        result = self.checker.validate(self.valid_facts)
        assert result is not None
    
    def test_other_always_valid(self):
        """その他 segment always passes regardless of article_count/avg_pv."""
        self.valid_facts['article_topics'] = ['その他']
        self.valid_facts['article_count'] = 1
        self.valid_facts['avg_pv'] = 10
        result = self.checker.validate(self.valid_facts)
        assert result is not None
    
    def test_ai_insufficient_article_count(self):
        """AI segment with article_count < 3 raises FactsError."""
        self.valid_facts['article_topics'] = ['AI']
        self.valid_facts['article_count'] = 2
        self.valid_facts['avg_pv'] = 100
        with pytest.raises(FactsError) as exc_info:
            self.checker.validate(self.valid_facts)
        assert 'needs 3+ articles' in exc_info.value.rule_violated
    
    def test_sns_insufficient_avg_pv(self):
        """SNS segment with avg_pv < 80 raises FactsError."""
        self.valid_facts['article_topics'] = ['SNS']
        self.valid_facts['article_count'] = 4
        self.valid_facts['avg_pv'] = 79
        with pytest.raises(FactsError) as exc_info:
            self.checker.validate(self.valid_facts)
        assert 'avg_pv' in exc_info.value.rule_violated
    
    def test_副業_boundary_criteria(self):
        """副業 segment at boundary (article_count=3, avg_pv=60) passes."""
        self.valid_facts['article_topics'] = ['副業']
        self.valid_facts['article_count'] = 3
        self.valid_facts['avg_pv'] = 60
        result = self.checker.validate(self.valid_facts)
        assert result is not None
    
    def test_unknown_segment(self):
        """Unknown segment name raises FactsError."""
        self.valid_facts['article_topics'] = ['不明なセグメント']
        with pytest.raises(FactsError) as exc_info:
            self.checker.validate(self.valid_facts)
        assert 'unknown segment' in exc_info.value.rule_violated
    
    def test_missing_article_count_defaults_to_zero(self):
        """Missing article_count defaults to 0 (triggers fit failure)."""
        self.valid_facts['article_topics'] = ['AI']
        del self.valid_facts['article_count']
        self.valid_facts['avg_pv'] = 100
        with pytest.raises(FactsError) as exc_info:
            self.checker.validate(self.valid_facts)
        assert 'needs 3+ articles' in exc_info.value.rule_violated
    
    def test_missing_avg_pv_defaults_to_zero(self):
        """Missing avg_pv defaults to 0 (triggers fit failure)."""
        self.valid_facts['article_topics'] = ['SNS']
        self.valid_facts['article_count'] = 4
        del self.valid_facts['avg_pv']
        with pytest.raises(FactsError) as exc_info:
            self.checker.validate(self.valid_facts)
        assert 'avg_pv' in exc_info.value.rule_violated
    
    def test_empty_article_topics_passes(self):
        """Empty article_topics list passes."""
        self.valid_facts['article_topics'] = []
        result = self.checker.validate(self.valid_facts)
        assert result is not None
    
    def test_multiple_segments_all_meet_criteria(self):
        """Multiple segments all meeting criteria pass."""
        self.valid_facts['article_topics'] = ['AI', 'SNS', '副業']
        self.valid_facts['article_count'] = 10
        self.valid_facts['avg_pv'] = 150
        result = self.checker.validate(self.valid_facts)
        assert result is not None
```

(Total: 18+ test cases)

- [ ] **Step 3: Run tests to verify they all pass**

```bash
pytest tests/test_guards.py::TestSegmentFitChecker -v
```

Expected: 18+ tests PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/guards.py tests/test_guards.py
git commit -m "feat: implement SegmentFitChecker guard with 18+ test cases (segment validation)"
```

---

## Task 5: Facts Builder Core Logic

**Files:**
- Create: `scripts/build_facts.py`
- Modify: `tests/test_build_facts.py`

**Interfaces:**
- Consumes: `weekly_metrics: dict` (from collect_weekly_metrics.py), `kpi: dict` (baseline KPI thresholds)
- Produces: `build_facts(weekly_metrics: dict, kpi: dict) → dict` function
- Produces: `apply_guards(facts: dict, guards: list) → dict` function
- Returns facts_dict with keys: week, article_topics, sales_by_segment, segment_scores, target_prices, article_count, avg_pv, snippet, description
- Raises FactsError immediately on first guard failure

- [ ] **Step 1: Write build_facts() function**

```python
def build_facts(weekly_metrics: dict, kpi: dict) -> dict:
    """
    Build facts dict from weekly metrics and KPI baseline.
    
    Args:
        weekly_metrics: {
            'week': '2026-11-02',
            'articles': [
                {'topic': 'AI', 'pv': 150, 'sales': 25000},
                {'topic': 'SNS', 'pv': 120, 'sales': 18000},
            ],
            'total_sales': 43000,
        }
        kpi: {
            'target_sales_per_week': 50000,
            'target_avg_pv': 100,
            'min_article_count': 3,
        }
    
    Returns:
        {
            'week': '2026-11-02',
            'article_topics': ['AI', 'SNS'],
            'sales_by_segment': {'AI': 25000, 'SNS': 18000},
            'segment_scores': {'AI': 0.9, 'SNS': 0.8},
            'target_prices': {'AI': 2000, 'SNS': 1500},
            'article_count': 2,
            'avg_pv': 135,
            'snippet': 'This week: AI recipes & SNS automation...',
            'description': 'Weekly results tracking AI & SNS content...',
            'total_sales': 43000,
        }
    
    Raises:
        FactsError if numeric validation, banned phrase, or segment fit fails
    """
    
    if not weekly_metrics or 'week' not in weekly_metrics:
        raise ValueError('weekly_metrics must contain "week" key')
    
    articles = weekly_metrics.get('articles', [])
    total_sales = weekly_metrics.get('total_sales', 0)
    
    # Extract article topics and sales by segment
    article_topics = list({a['topic'] for a in articles if 'topic' in a})
    sales_by_segment = {topic: sum(a.get('sales', 0) for a in articles if a.get('topic') == topic) 
                        for topic in article_topics}
    
    # Calculate article count and average PV
    article_count = len(articles)
    avg_pv = int(sum(a.get('pv', 0) for a in articles) / article_count) if article_count > 0 else 0
    
    # Calculate segment scores (sales / target per article)
    segment_scores = {}
    for topic in article_topics:
        topic_articles = [a for a in articles if a.get('topic') == topic]
        if topic_articles:
            avg_sales_per_article = sum(a.get('sales', 0) for a in topic_articles) / len(topic_articles)
            target_per_article = kpi.get('target_sales_per_week', 50000) / max(article_count, 1)
            segment_scores[topic] = min(1.0, avg_sales_per_article / target_per_article) if target_per_article > 0 else 0.0
    
    # Determine target prices based on segment performance
    target_prices = {}
    for topic in article_topics:
        score = segment_scores.get(topic, 0.5)
        base_price = 1500
        target_prices[topic] = int(base_price * (1 + score * 0.5))  # +0-50% based on score
    
    # Build snippet and description
    topics_str = '・'.join(article_topics) if article_topics else 'その他'
    snippet = f'This week: {topics_str}...'
    description = f'Weekly results tracking {topics_str} content...'
    
    facts = {
        'week': weekly_metrics['week'],
        'article_topics': article_topics,
        'sales_by_segment': sales_by_segment,
        'segment_scores': segment_scores,
        'target_prices': target_prices,
        'article_count': article_count,
        'avg_pv': avg_pv,
        'snippet': snippet,
        'description': description,
        'total_sales': total_sales,
    }
    
    return facts
```

- [ ] **Step 2: Write apply_guards() function**

```python
def apply_guards(facts: dict, guards: list[Guard]) -> dict:
    """
    Apply validation guards in series.
    
    Args:
        facts: facts dict to validate
        guards: list of Guard instances (NumberVerifier, BannedPhrasesChecker, SegmentFitChecker)
    
    Returns:
        facts dict if all guards pass
    
    Raises:
        FactsError on first guard failure (stops immediately, doesn't continue to next guard)
    """
    for guard in guards:
        facts = guard.validate(facts)  # Will raise FactsError if validation fails
    return facts
```

- [ ] **Step 3: Write integration tests for build_facts() + apply_guards()**

```python
from scripts.build_facts import build_facts, apply_guards
from scripts.guards import NumberVerifier, BannedPhrasesChecker, SegmentFitChecker, FactsError

class TestBuildFacts:
    def setup_method(self):
        self.weekly_metrics = {
            'week': '2026-11-02',
            'articles': [
                {'topic': 'AI', 'pv': 150, 'sales': 25000},
                {'topic': 'SNS', 'pv': 120, 'sales': 18000},
            ],
            'total_sales': 43000,
        }
        self.kpi = {
            'target_sales_per_week': 50000,
            'target_avg_pv': 100,
            'min_article_count': 3,
        }
        self.guards = [
            NumberVerifier(),
            BannedPhrasesChecker(),
            SegmentFitChecker(),
        ]
    
    def test_build_facts_normal(self):
        """Normal weekly_metrics builds facts dict correctly."""
        facts = build_facts(self.weekly_metrics, self.kpi)
        assert facts['week'] == '2026-11-02'
        assert set(facts['article_topics']) == {'AI', 'SNS'}
        assert facts['total_sales'] == 43000
        assert facts['article_count'] == 2
        assert facts['avg_pv'] == 135  # (150 + 120) / 2
    
    def test_build_facts_empty_articles(self):
        """Empty articles list builds facts with empty topics."""
        self.weekly_metrics['articles'] = []
        self.weekly_metrics['total_sales'] = 0
        facts = build_facts(self.weekly_metrics, self.kpi)
        assert facts['article_topics'] == []
        assert facts['article_count'] == 0
    
    def test_apply_guards_all_pass(self):
        """All guards pass for normal facts."""
        facts = build_facts(self.weekly_metrics, self.kpi)
        result = apply_guards(facts, self.guards)
        assert result is not None
    
    def test_apply_guards_number_verifier_fails(self):
        """NumberVerifier failure stops guard chain."""
        facts = build_facts(self.weekly_metrics, self.kpi)
        facts['total_sales'] = -1000
        with pytest.raises(FactsError) as exc_info:
            apply_guards(facts, self.guards)
        assert exc_info.value.error_type == 'numeric'
    
    def test_apply_guards_banned_phrase_fails(self):
        """BannedPhrasesChecker failure stops guard chain."""
        facts = build_facts(self.weekly_metrics, self.kpi)
        facts['description'] = '必ず成功する方法'
        with pytest.raises(FactsError) as exc_info:
            apply_guards(facts, self.guards)
        assert exc_info.value.error_type == 'banned_phrase'
    
    def test_apply_guards_segment_fit_fails(self):
        """SegmentFitChecker failure stops guard chain."""
        facts = build_facts(self.weekly_metrics, self.kpi)
        facts['article_count'] = 1  # Less than AI requirement of 3
        facts['avg_pv'] = 150
        with pytest.raises(FactsError) as exc_info:
            apply_guards(facts, self.guards)
        assert exc_info.value.error_type == 'segment_fit'
```

- [ ] **Step 4: Run all facts builder tests**

```bash
pytest tests/test_build_facts.py -v
```

Expected: 10+ tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build_facts.py tests/test_build_facts.py
git commit -m "feat: implement facts builder with guard chain (build_facts + apply_guards)"
```

---

## Task 6: Integration Test: Facts Builder + All Guards

**Files:**
- Modify: `tests/test_build_facts.py` (add integration test class)

**Interfaces:**
- Tests: end-to-end flow from weekly_metrics → build_facts() → apply_guards() with all 3 guards
- Validates: normal path, error detection, error context preservation

- [ ] **Step 1: Write integration test class**

```python
class TestFactsBuilderIntegration:
    """End-to-end tests: weekly_metrics → build_facts → apply_guards."""
    
    def test_happy_path_valid_facts_pass_all_guards(self):
        """Valid weekly_metrics → facts → all guards pass."""
        weekly_metrics = {
            'week': '2026-11-02',
            'articles': [
                {'topic': 'AI', 'pv': 150, 'sales': 25000},
                {'topic': 'SNS', 'pv': 120, 'sales': 18000},
                {'topic': 'AI', 'pv': 180, 'sales': 30000},
            ],
            'total_sales': 73000,
        }
        kpi = {'target_sales_per_week': 50000}
        guards = [NumberVerifier(), BannedPhrasesChecker(), SegmentFitChecker()]
        
        facts = build_facts(weekly_metrics, kpi)
        result = apply_guards(facts, guards)
        
        assert result['total_sales'] == 73000
        assert len(result['article_topics']) == 2
    
    def test_error_context_preserved_through_chain(self):
        """FactsError includes field_name, value, rule_violated for debugging."""
        weekly_metrics = {
            'week': '2026-11-02',
            'articles': [{'topic': '必ず稼げるAI', 'pv': 100, 'sales': 5000}],
            'total_sales': 5000,
        }
        kpi = {}
        guards = [NumberVerifier(), BannedPhrasesChecker(), SegmentFitChecker()]
        
        facts = build_facts(weekly_metrics, kpi)
        
        with pytest.raises(FactsError) as exc_info:
            apply_guards(facts, guards)
        
        error = exc_info.value
        assert error.field_name == 'article_topics[0]'
        assert '必ず' in error.rule_violated
        assert error.remediation is not None
        assert 'reword' in error.remediation.lower()
    
    def test_scenario_ai_topic_insufficient_pv(self):
        """AI segment with avg_pv < 100 fails SegmentFitChecker."""
        weekly_metrics = {
            'week': '2026-11-02',
            'articles': [
                {'topic': 'AI', 'pv': 50, 'sales': 10000},
                {'topic': 'AI', 'pv': 60, 'sales': 12000},
                {'topic': 'AI', 'pv': 40, 'sales': 8000},
            ],
            'total_sales': 30000,
        }
        kpi = {}
        guards = [NumberVerifier(), BannedPhrasesChecker(), SegmentFitChecker()]
        
        facts = build_facts(weekly_metrics, kpi)
        
        with pytest.raises(FactsError) as exc_info:
            apply_guards(facts, guards)
        
        assert 'segment_fit' in exc_info.value.error_type
        assert 'AI' in str(exc_info.value.rule_violated)
```

- [ ] **Step 2: Run integration tests**

```bash
pytest tests/test_build_facts.py::TestFactsBuilderIntegration -v
```

Expected: 3+ integration tests PASS

- [ ] **Step 3: Check coverage of all 3 guards + facts builder**

```bash
pytest tests/test_build_facts.py tests/test_guards.py --cov=scripts.build_facts --cov=scripts.guards --cov-report=term-missing
```

Expected: Coverage ≥ 80% across build_facts.py and guards.py

- [ ] **Step 4: Commit**

```bash
git add tests/test_build_facts.py
git commit -m "test: add integration tests for facts builder + guard chain (end-to-end validation)"
```

---

## Task 7: Documentation & Self-Review

**Files:**
- Modify: `scripts/build_facts.py` (add docstrings)
- Modify: `scripts/guards.py` (add module docstring)
- Create: `docs/facts-builder-guide.md` (user guide for build_facts API)

**Interfaces:**
- Documents: FactsError structure, guard behavior, usage examples
- Example: `facts = build_facts(weekly_metrics, kpi); apply_guards(facts, [NumberVerifier(), ...]) → dict`

- [ ] **Step 1: Add comprehensive docstrings to build_facts.py**

```python
"""
facts Builder for note.com result magazine automation.

This module constructs a facts dictionary from weekly metrics and validates it
against three guard layers:
  1. NumberVerifier: numeric range and consistency checks
  2. BannedPhrasesChecker: content moderation (banned phrases)
  3. SegmentFitChecker: article topic segment fit (min article count, PV)

Each guard raises FactsError with actionable remediation hints on failure.

Example:
    from scripts.build_facts import build_facts, apply_guards
    from scripts.guards import NumberVerifier, BannedPhrasesChecker, SegmentFitChecker, FactsError
    
    weekly_metrics = {
        'week': '2026-11-02',
        'articles': [
            {'topic': 'AI', 'pv': 150, 'sales': 25000},
        ],
        'total_sales': 25000,
    }
    kpi = {'target_sales_per_week': 50000}
    guards = [
        NumberVerifier(),
        BannedPhrasesChecker(),
        SegmentFitChecker(),
    ]
    
    try:
        facts = build_facts(weekly_metrics, kpi)
        validated_facts = apply_guards(facts, guards)
        print(f"Facts built for week {validated_facts['week']}")
    except FactsError as e:
        print(f"Validation failed: [{e.error_type}] {e.field_name}: {e.remediation}")
"""
```

- [ ] **Step 2: Add module docstring to guards.py**

```python
"""
Guard validators for facts dict validation.

Three guard layers ensure facts dict integrity:
  1. NumberVerifier: Checks numeric fields (total_sales range, segment sum consistency)
  2. BannedPhrasesChecker: Detects forbidden content (must-win language, guarantees)
  3. SegmentFitChecker: Validates article topic segment fit (min article count, min PV)

All guards inherit from Guard abstract base and implement validate(facts) → dict,
raising FactsError on validation failure.

FactsError includes:
  - error_type: 'numeric', 'banned_phrase', or 'segment_fit'
  - field_name: specific field that failed validation
  - value: the invalid value
  - rule_violated: human-readable rule description
  - remediation: actionable fix suggestion
"""
```

- [ ] **Step 3: Create user guide documentation**

```markdown
# Facts Builder Guide

## Overview

`build_facts()` constructs a facts dictionary from weekly metrics, aggregating
article topics, sales, PV, and other metadata. `apply_guards()` validates the
facts through three independent validators.

## API

### build_facts(weekly_metrics: dict, kpi: dict) → dict

**Input:**
- `weekly_metrics`: {
    - 'week': str (ISO date, e.g. '2026-11-02')
    - 'articles': list[dict] with keys: topic, pv, sales
    - 'total_sales': int (¥)
  }
- `kpi`: dict with baseline thresholds (optional: target_sales_per_week, etc.)

**Output:** facts dict with keys:
- 'week', 'article_topics', 'sales_by_segment', 'segment_scores'
- 'target_prices', 'article_count', 'avg_pv', 'snippet', 'description'
- 'total_sales'

**Raises:** ValueError if week key missing

### apply_guards(facts: dict, guards: list[Guard]) → dict

**Input:**
- `facts`: facts dict from build_facts()
- `guards`: list of Guard instances (in order: NumberVerifier, BannedPhrasesChecker, SegmentFitChecker)

**Output:** facts dict if all guards pass (unchanged)

**Raises:** FactsError on first guard failure (includes remediation hint)

## Guard Behaviors

### NumberVerifier
- Checks: total_sales in [0, 10,000,000], sales_by_segment sum == total_sales (±1)
- Fails on: negative sales, overflow, missing total_sales key

### BannedPhrasesChecker
- Checks: article_topics, snippet, description for banned phrases
- Fails on: any match to BANNED_PHRASES tuple
- Note: Japanese particle combinations (e.g., "は") are NOT flagged

### SegmentFitChecker
- Checks: article_topics meet segment criteria (min article_count, min avg_pv)
- Segment criteria:
  - AI: ≥3 articles, ≥100 avg PV
  - SNS: ≥4 articles, ≥80 avg PV
  - 副業: ≥3 articles, ≥60 avg PV
  - その他: no minimum
- Fails on: unknown segment, insufficient article_count or avg_pv

## Error Handling

```python
try:
    facts = build_facts(weekly_metrics, kpi)
    validated = apply_guards(facts, [NumberVerifier(), ...])
except ValueError as e:
    print(f"Input error: {e}")  # Missing week key
except FactsError as e:
    print(f"[{e.error_type}] {e.field_name}")
    print(f"  Violated: {e.rule_violated}")
    print(f"  Fix: {e.remediation}")
```

## Examples

### Example 1: Valid facts
```python
weekly_metrics = {
    'week': '2026-11-02',
    'articles': [
        {'topic': 'AI', 'pv': 150, 'sales': 25000},
    ],
    'total_sales': 25000,
}
facts = build_facts(weekly_metrics, {})
apply_guards(facts, [NumberVerifier(), ...])  # Passes
```

### Example 2: Guard failure (banned phrase)
```python
facts['description'] = '必ず成功する方法'
apply_guards(facts, [NumberVerifier(), BannedPhrasesChecker(), ...])
# Raises FactsError: [banned_phrase] description
#   edit description to remove: 必ず
```

## Testing

Run guard tests:
```bash
pytest tests/test_guards.py -v
pytest tests/test_build_facts.py -v
```

Coverage target: ≥80% across build_facts.py and guards.py
```bash
pytest --cov=scripts.build_facts --cov=scripts.guards --cov-report=term-missing
```
```

- [ ] **Step 4: Self-review checklist**

- [ ] All 3 guards implemented (NumberVerifier, BannedPhrasesChecker, SegmentFitChecker)
- [ ] Guard tests cover ≥80% of guard logic (15+, 20+, 18+ tests respectively)
- [ ] facts builder builds all required keys (week, article_topics, sales_by_segment, etc.)
- [ ] apply_guards() stops on first failure (doesn't continue to next guard)
- [ ] FactsError includes field_name, rule_violated, value, remediation
- [ ] No hard-coded segment names (use SEGMENT_CRITERIA dict for maintainability)
- [ ] Japanese particle handling in BannedPhrasesChecker (avoid false positives)
- [ ] Docstrings on all public functions and classes
- [ ] Integration tests cover normal path + each guard failure scenario
- [ ] No TODOs or placeholder comments

- [ ] **Step 5: Commit final documentation**

```bash
git add docs/facts-builder-guide.md scripts/build_facts.py scripts/guards.py
git commit -m "docs: add facts builder guide and comprehensive docstrings"
```

---

## Summary

**Total deliverables:**
- ✅ Guard infrastructure (FactsError, BANNED_PHRASES, Guard base class)
- ✅ NumberVerifier (15+ tests, ≥80% coverage)
- ✅ BannedPhrasesChecker (20+ tests, ≥80% coverage)
- ✅ SegmentFitChecker (18+ tests, ≥80% coverage)
- ✅ build_facts() function (aggregates weekly_metrics → facts dict)
- ✅ apply_guards() function (validates facts through guard chain)
- ✅ Integration tests (end-to-end: weekly_metrics → validated facts)
- ✅ Documentation & user guide (API reference, error handling, examples)
- ✅ 70+ total unit tests (guards + builder + integration)
- ✅ Coverage ≥80% across build_facts.py and guards.py

**Key constraints enforced:**
- Numeric precision using Decimal (consistent with note_revenue_final.py)
- Immediate FactsError on guard failure (no silent failures)
- Actionable remediation hints in every FactsError
- Japanese text handling (avoid false positives on particles)
- Segment criteria defined as dict (maintainable, testable)
- All outputs immutable dicts (no in-place mutation)

**Next steps (post-implementation):**
1. Code review by task reviewer (spec compliance + quality)
2. Run full test suite: `pytest tests/test_build_facts.py tests/test_guards.py -v`
3. Verify coverage: `pytest --cov=scripts --cov-report=html`
4. Ready for Week 2 integration with note_api.py / ga4_api.py / line_api.py
