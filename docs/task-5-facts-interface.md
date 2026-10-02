# Task 5 Output Interface — Facts Dictionary

**Document Purpose:** Specify the `FactsDict` output interface for downstream consumers (Task 6+). This guide is normative for any code using the output of `build_facts()`.

**Revision:** 2026-10-02 · Task 7 (Integration & Documentation)

---

## Overview

Task 5 (`scripts/build_facts.py`) takes weekly metrics and KPI configuration, applies three guards (Number, BannedPhrase, SegmentFit), and produces a `FactsDict` object. The output is JSON-serializable and used as input for:

- **Task 6:** Claude prompt generation (facts embedding in multi-turn conversations)
- **Task 7:** Pricing/segment analysis (via segment_scores)
- **Task 8:** Segment classification refinement (score evaluation & thresholding)

This document defines the structure, types, validation contract, and error handling.

---

## FactsDict Structure

```python
@dataclass
class FactsDict:
    week: str                                      # ISO 8601 format: YYYY-Www (e.g., '2026-W40')
    article_topics: List[Dict[str, Any]]          # Articles in this week with views & optional sales
    sales_by_segment: Dict[str, float]            # Segment-wise sales allocation (JPY)
    segment_scores: Dict[str, int]                # Segment performance scores (0-100)
```

### JSON Output Format (via `.to_dict()`)

```json
{
  "week": "2026-W40",
  "article_topics": [
    {
      "article_id": "05",
      "views": 13,
      "sales_jpy": 3000
    },
    {
      "article_id": "12",
      "views": 5,
      "sales_jpy": 2000
    }
  ],
  "sales_by_segment": {
    "enterprise": 3000,
    "sme": 2000
  },
  "segment_scores": {
    "enterprise": 60,
    "sme": 60,
    "startup": 60,
    "other": 60
  }
}
```

---

## Field Specifications

### `week: str`

- **Format:** ISO 8601 week format `YYYY-Www` (e.g., `2026-W40`, `2026-W01`, `2026-W52`)
- **Validation:** Regex pattern `^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$`
- **Source:** From `weekly_metrics['week']` or `weekly_metrics['note']['week']`
- **Conflict Handling:** If both top-level and note-level `week` exist and differ, `build_facts()` raises `FactsError` (no silent fallback)

**Example:** `"2026-W40"` represents week 40 of year 2026 (Mon–Sun, starting Mon 2026-09-28)

---

### `article_topics: List[Dict[str, Any]]`

Each element represents one article published in the week.

#### Element Schema

```python
{
    'article_id': str,        # Article identifier from KPI[articles]
    'views': int,             # Page views (> 0 or = 0, never negative)
    'sales_jpy': int | float  # (optional) Sales attributed to this article (JPY). Omitted if no sales data.
}
```

#### Rules

1. **article_id must exist in KPI:** Every `article_id` must match a key in `kpi['articles']` (validated by `NumberVerifier`)
2. **views source:** Copied from `weekly_metrics['note']['views_by_article'][article_id]` (no reordering or transformation)
3. **sales_jpy source & constraints:**
   - Copied from `weekly_metrics['note']['sales_by_article'][article_id]` if present
   - If `sales_by_article` dict is absent or empty, `sales_jpy` key is not added
   - When present, must be non-negative (`>= 0`), including floats like `2500.5`
   - Sum of all `article_topics[*].sales_jpy` must be `<= weekly_metrics['note']['total_sales_jpy']` (articles may be partially featured)
4. **Ordering:** Same as `views_by_article` iteration order (Python 3.7+ preserves insertion order in dicts)
5. **No synthetic fields:** Only `article_id`, `views`, and `sales_jpy` are set; no titles, descriptions, or other fields from KPI are added here (enforce in Task 6 input validation)

#### Example

```json
[
  {"article_id": "05", "views": 13, "sales_jpy": 3000},
  {"article_id": "12", "views": 5}
]
```

Article `12` has no `sales_jpy` because it was not included in the sales report.

---

### `sales_by_segment: Dict[str, float]`

Segment-wise breakdown of total sales, allocated proportionally to segment customer counts (if available).

#### Schema

```python
{
    'segment_name': float  # Total sales attributed to this segment (JPY, can be 0.0)
}
```

#### Rules

1. **Keys must match KPI:** Each segment name must exist in `kpi['segment_thresholds']`
2. **Values are non-negative floats:** `>= 0.0`, never negative (validated by `NumberVerifier`)
3. **Sum must match total:** Sum of all values must exactly equal `weekly_metrics['note']['total_sales_jpy']` (rounded float comparison is NOT performed; exact equality required)
4. **Absent if no segment data:** If `weekly_metrics` has no `sales_by_segment` or it is `None` or empty dict, output is empty dict `{}`
5. **Preserve insertion order:** Maintain key order from input (important for reproducible JSON output)
6. **No modifications:** Dict is copied from input (not shared) but values are not reordered or aggregated

#### Examples

```json
{
  "enterprise": 3000,
  "sme": 2000
}
```

or (when no segment data available):

```json
{}
```

---

### `segment_scores: Dict[str, int]`

Performance scores for each segment, used by Task 6 (embedding context) and Task 8 (classification refinement).

#### Schema

```python
{
    'segment_name': int  # Score in range [min, max], integer only
}
```

#### Rules

1. **Keys must exist in KPI:** Each segment name must be defined in `kpi['segment_thresholds']`
2. **Values are integers in [min, max]:**
   - Integer type (bool excluded, `isinstance(score, int) and not isinstance(score, bool)`)
   - Range: `kpi['segment_thresholds'][segment_name]['min'] <= score <= max` (typically 0–100)
   - Out-of-range values are rejected by `SegmentFitChecker`
3. **Task 5 Placeholder Values:** All scores are set to `kpi['segment_thresholds'][segment_name]['threshold']` (default 60 for all segments in current KPI)
   - This is a **placeholder** pending Task 8 refinement (score calculation from engagement metrics)
   - Current value matches the threshold; intentionally not attempting to compute actual engagement-based scores (Absolute Rule 1: no estimation)
4. **Must have an entry for every segment:** If `kpi['segment_thresholds']` defines segments, all must appear in output (no omissions)
5. **Every segment appears even if sales are zero:** segment_scores[name] = threshold for all defined segments

#### Thresholds (typical, from current KPI)

| Segment | min | max | threshold |
|---------|-----|-----|-----------|
| enterprise | 0 | 100 | 60 |
| sme | 0 | 100 | 60 |
| startup | 0 | 100 | 60 |
| other | 0 | 100 | 60 |

See `data/kekka_kpi.json` → `segment_thresholds` for authoritative values.

#### Example

```json
{
  "enterprise": 60,
  "sme": 60,
  "startup": 60,
  "other": 60
}
```

All segments receive the default threshold (60) as placeholder. Task 8 will replace these with actual scores.

---

## Error Contract

All validation failures raise `FactsError(Exception)` with detailed, actionable error messages.

### FactsError Class

```python
class FactsError(Exception):
    """Raised by build_facts() or any Guard when validation fails."""
    pass
```

### Error Message Format

**Pattern:** `<guard_name>: <field_path> <violation> — <remediation>`

**Examples:**

```
NumberVerifier: article '05' not found in weekly_metrics.note.views_by_article. Valid articles: ['05', '12']

BannedPhrasesChecker: banned phrase '無料で' found in article_topics[0].title: 'フォロワーが無料でゲット'

SegmentFitChecker: segment 'xyz' not defined in kpi.segment_thresholds. Valid segments: ['enterprise', 'sme', 'startup', 'other']

SegmentFitChecker: segment 'enterprise' score 101 out of range [0, 100]

FactsError: week must be ISO 8601 'YYYY-Www' (e.g. '2026-W40'), got '2026-40'
```

### Guard Details

#### 1. NumberVerifier

**Responsibility:** Verify all numeric fields (views, sales_jpy, sales_by_segment values) match source data in `weekly_metrics`.

**Validates:**

- Every `article_id` in `article_topics` exists in `weekly_metrics.note.views_by_article`
- Views value (if present) equals source
- Article sales_jpy is non-negative and does not exceed total
- Segment sales sum exactly equals `total_sales_jpy`
- NaN, infinity, and boolean types are rejected

**Raises FactsError on:**

- `article_id` not found
- Views mismatch (source vs facts)
- Negative or non-numeric sales
- Segment sum ≠ total
- Article sales sum > total
- Missing `total_sales_jpy` when sales data is present

#### 2. BannedPhrasesChecker

**Responsibility:** Prevent problematic phrases (誇大表現 etc.) from appearing in facts output.

**Validates:**

- No phrase in `kpi['banned_phrases']` appears in:
  - `article_topics[*].title`, `.description`, `.topic`, or any nested text field (except `article_id`)
  - `sales_by_segment` keys (segment names)
  - `segment_scores` keys

**Comparison:** NFKC-normalized, case-folded (全角/半角・大文字/小文字を区別しない)

**Raises FactsError on:**

- Any banned phrase found (first occurrence only; stops after first match)
- `kpi['banned_phrases']` missing, empty, or malformed (fails closed)

**Remediation:** Check `data/kekka_kpi.json` → `banned_phrases` for the authoritative list.

#### 3. SegmentFitChecker

**Responsibility:** Validate segment_scores comply with Task 8 rules (0–100 scale, threshold 60).

**Validates:**

- Every segment name in `segment_scores` is defined in `kpi['segment_thresholds']`
- Score is an integer (bool excluded)
- Score is in range `[min, max]` (typically [0, 100])
- Threshold definition is valid (if custom min/max/threshold provided in future)

**Raises FactsError on:**

- Undefined segment (not in `kpi['segment_thresholds']`)
- Non-integer score (float, string, bool rejected)
- Score out of range
- Invalid threshold definition (min > max, etc.)
- `kpi['segment_thresholds']` missing or empty (fails closed)

---

## Call Contract & Usage

### Signature

```python
def build_facts(weekly_metrics: Dict[str, Any], kpi: Dict[str, Any]) -> Dict[str, Any]:
    """
    Args:
        weekly_metrics: Single week record from kekka_weekly_metrics.json['weeks'][i]
                        (NOT the whole file; caller must pass weeks[-1] or similar)
        kpi: Contents of data/kekka_kpi.json (full dict with segment_thresholds & banned_phrases)

    Returns:
        FactsDict.to_dict() — JSON-serializable dict with keys
        {week, article_topics, sales_by_segment, segment_scores}

    Raises:
        FactsError: If input is invalid, malformed, or fails any guard check
    """
```

### Typical Usage (Task 6)

```python
import json
from scripts.build_facts import build_facts, FactsError
from scripts.guards import NumberVerifier, BannedPhrasesChecker, SegmentFitChecker

# Load data
with open('data/kekka_weekly_metrics.json') as f:
    metrics_file = json.load(f)
with open('data/kekka_kpi.json') as f:
    kpi = json.load(f)

# Build facts for the latest week
try:
    facts = build_facts(metrics_file['weeks'][-1], kpi)
except FactsError as e:
    print(f"Facts build failed: {e}")
    exit(1)

# Use facts as input for Claude prompt
prompt_context = json.dumps(facts, ensure_ascii=False)
# ... send to Claude API
```

---

## Circular Import Caveat

**Important for Task 5 usage:**

- `scripts/build_facts.py` imports guards lazily (inside `build_facts()` function) to avoid circular imports
- `scripts/guards.py` imports `FactsError` from `build_facts` at module level
- **Consequence:** Do NOT import all guards at the top level of `build_facts.py`; always use delayed import inside functions that call guards

**Pattern (correct):**

```python
# Inside build_facts() function:
from guards import NumberVerifier, BannedPhrasesChecker, SegmentFitChecker
for guard in (...):
    guard.verify(...)
```

---

## Input Schema Reference

### weekly_metrics (single week, from kekka_weekly_metrics.json['weeks'][i])

```json
{
  "week": "2026-W40",
  "note": {
    "week": "2026-W40",
    "views_by_article": {"05": 13, "12": 5, ...},
    "sales_by_article": {"05": 3000, ...},
    "sales_by_segment": {"enterprise": 3000, "sme": 2000, ...},
    "total_sales_jpy": 5000,
    "total_likes": 3,
    "buyer_count": 2
  },
  "ga4": {...},
  "line": {...},
  "collected_at": "2026-10-02T09:00:00+09:00"
}
```

Only `week` and `note` (with `views_by_article`) are required for `build_facts()`. Other keys are silently ignored.

### kpi (from data/kekka_kpi.json)

```json
{
  "targets": {...},
  "articles": {"05": {"title": "...", "url": "..."}, ...},
  "segment_thresholds": {
    "enterprise": {"min": 0, "max": 100, "threshold": 60},
    ...
  },
  "banned_phrases": ["無料で", "申請代行", ...]
}
```

`segment_thresholds` and `banned_phrases` are required; others are optional for `build_facts()`.

---

## Testing & Validation

### Integration Test Template

```python
import json
from scripts.build_facts import build_facts, FactsError

def test_facts_end_to_end():
    # Load fixtures
    weekly_metrics = {"week": "2026-W40", "note": {...}}
    kpi = {"segment_thresholds": {...}, "banned_phrases": [...]}
    
    # Call
    facts = build_facts(weekly_metrics, kpi)
    
    # Verify output is JSON-serializable
    facts_json = json.dumps(facts, ensure_ascii=False)
    restored = json.loads(facts_json)
    
    # Verify structure
    assert "week" in restored
    assert isinstance(restored["article_topics"], list)
    assert isinstance(restored["sales_by_segment"], dict)
    assert isinstance(restored["segment_scores"], dict)
    assert len(restored["segment_scores"]) > 0
```

### Running Tests

```bash
cd /home/user/hojo-hq
python3 -m pytest tests/test_guards.py -v
# Expected: 162+ passing tests
```

See `tests/test_guards.py` for 80+ existing integration tests covering:

- JSON serialization round-trips
- Guard failures (NumberVerifier, BannedPhrasesChecker, SegmentFitChecker)
- Edge cases (zero sales, empty articles, NaN/inf)
- Error message quality
- Real KPI data validation

---

## Downstream Contract (Task 6+)

### Consumption Rules

1. **Never modify facts after receipt:** Use as read-only input
2. **Assume all numbers are verified:** No re-validation needed (guards were run)
3. **Assume no banned phrases:** Text is already validated
4. **Rely on segment_scores for embedding context:** Current placeholder (60) is valid for prompting; do not attempt to override

### What NOT to Assume

- `segment_scores` values are NOT engagement-derived (Task 5 placeholder; Task 8 will refine)
- `sales_by_segment` may be empty (if no segment data in source)
- `article_topics` may be empty (if no articles published that week)
- `segment_scores` values may all be identical (current KPI: all threshold = 60)

---

## Revision History

| Date | Version | Change |
|------|---------|--------|
| 2026-10-02 | 1.0 | Task 7: Initial specification for Facts Dictionary output interface |

---

## Related Documents

- **Task 5 Implementation:** `scripts/build_facts.py`, `scripts/guards.py`
- **KPI Reference:** `data/kekka_kpi.json`
- **Test Suite:** `tests/test_guards.py` (162+ tests)
- **Weekly Metrics Schema:** `data/kekka_weekly_metrics.json` (schema reference)
- **Superpower Plan:** `docs/superpowers/plans/2026-10-02-kekka-facts-builder.md`
