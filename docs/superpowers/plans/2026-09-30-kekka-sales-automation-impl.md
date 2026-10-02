# 結果マガ売上自動化システム 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete automation system that generates, prices, and distributes paid content weekly, with AI-driven decision-making and natural (non-AI-feeling) user-facing output.

**Architecture:** 4-phase rollout starting with data pipelines, then content generation with multi-layer guards, then segment-based distribution with dynamic pricing, then weekly improvement loops powered by Claude API analysis.

**Tech Stack:** Python 3.12, Claude API (sonnet-5), note API, Google Analytics 4 API, LINE Messaging API, GitHub Actions, JSON data files

**Spec:** `docs/superpowers/specs/2026-09-30-kekka-sales-automation-design.md`

## Global Constraints

- All numbers in generated content must exist in facts/KPI data (zero fabrication tolerance)
- Segment predictions scored 0-100; only 60+ triggers paid distribution
- Generated text must read human-natural, not AI-polished (include hesitations, specifics, trial-and-error)
- Safety check failures block publication; no override mode
- Weekly cadence: Monday data collection → Wednesday strategy decision → Thursday-Saturday distribution
- All APIs use credentials from environment; no hardcoding
- Test coverage minimum 80% for guard logic; 60% for generation

## Review Focus

1. **Segment misclassification:** A user scoring 25 (discovery-seeker) gets offered ¥3000 premium → purchase unlikely, revenue wasted. Tests must verify segment boundary scoring.
2. **Fabricated numbers in output:** Claude generates "月5件の相談実績" but KPI shows 3. Shipping gate must reject; verify against facts dict in every generated snippet.
3. **Natural language degradation:** After 8 weeks, generated content starts sounding templated ("この週も〜"). Quality samples (random 3 per month) must human-review and trigger re-tuning if scored <7/10.
4. **API integration failure silent-fail:** GA4 API times out, but script reports success. Data gaps ripple through prediction. Each API call must explicitly log request/response, timeout must retry 3x before failing loud.
5. **Cumulative AI degradation:** Each Claude generation refines "human tone" rules, but over time becomes a feedback loop of its own output. Monthly reset of system prompt to spec baseline + human feedback from review focus #3.

---

## Phase 1: Data Pipeline (Oct 1-7)

### Task 1: Note API Client & Data Models

**Files:**
- Create: `scripts/note_api.py`
- Create: `data/kekka_weekly_metrics.json` (schema)
- Create: `tests/test_note_api.py`

**Interfaces:**
- Produces: `NoteMetrics(week: str, views_by_article: dict[str, int], total_likes: int, total_sales_jpy: int, buyer_ids: list[str], buyer_profiles: list[dict])`

**Steps:**

- [ ] Create `scripts/note_api.py` with function `fetch_note_metrics(api_token: str, week: str) -> NoteMetrics`
  - Authenticate using Bearer token from env `NOTE_API_TOKEN`
  - Fetch `/v1/articles?published_after=<week_start>&published_before=<week_end>`
  - Sum views, likes, extract sales/buyer data
  - Return NoteMetrics object
  - On 503/timeout: retry 3x with 5s exponential backoff, then raise NoteAPIError

- [ ] Write test `tests/test_note_api.py::test_fetch_note_metrics_success`
  - Mock note API response with 3 articles, 2 with sales
  - Assert returned NoteMetrics has correct totals
  - Assert buyer_profiles is non-empty

- [ ] Write test `tests/test_note_api.py::test_fetch_note_metrics_api_timeout_retries`
  - Mock API to timeout twice then succeed on 3rd
  - Assert function returns data (not raises after retries)

- [ ] Commit: `feat: add note API client with retry logic`

---

### Task 2: Google Analytics 4 Client

**Files:**
- Create: `scripts/ga4_api.py`
- Create: `tests/test_ga4_api.py`

**Interfaces:**
- Produces: `GA4Metrics(week: str, sessions: int, pageviews: int, ctr_by_article: dict[str, float], user_segment_counts: dict[str, int])`

**Steps:**

- [ ] Create `scripts/ga4_api.py` with function `fetch_ga4_metrics(property_id: str, week: str) -> GA4Metrics`
  - Authenticate via `GOOGLE_APPLICATION_CREDENTIALS` env
  - Query GA4 for sessions, pageviews, event `page_view` filtered by date range
  - Extract event `article_click` grouped by article ID (CTR = clicks / pageviews)
  - Return GA4Metrics
  - Log request/response for debugging

- [ ] Write test mocking GA4 response, verify CTR calculation

- [ ] Commit: `feat: add GA4 metrics client`

---

### Task 3: LINE API Client & Segment Data

**Files:**
- Create: `scripts/line_api.py`
- Create: `tests/test_line_api.py`

**Interfaces:**
- Produces: `LINEMetrics(week: str, registered_count: int, open_rate_by_segment: dict[str, float], click_rate_by_segment: dict[str, float])`

**Steps:**

- [ ] Create `scripts/line_api.py` with function `fetch_line_metrics(channel_id: str, week: str) -> LINEMetrics`
  - Use LINE Messaging API to query message send stats (if available) or Power Automate logged data
  - Fallback: read pre-aggregated CSV from `data/line_segment_stats_<week>.csv` if real-time API unavailable
  - Return LINEMetrics with segment-wise engagement

- [ ] Write test for both API and CSV fallback paths

- [ ] Commit: `feat: add LINE metrics (API + fallback CSV)`

---

### Task 4: Weekly Data Aggregation Script

**Files:**
- Create: `scripts/collect_weekly_metrics.py`
- Create: `data/kekka_weekly_metrics.json` (initial empty)
- Modify: `.github/workflows/kekka-weekly-collect.yml` (new)

**Interfaces:**
- Consumes: `NoteMetrics`, `GA4Metrics`, `LINEMetrics`
- Produces: `data/kekka_weekly_metrics.json` appended with new week entry

**Steps:**

- [ ] Create `scripts/collect_weekly_metrics.py` with function `collect_and_save_weekly_metrics(week: str) -> dict`
  - Call fetch_note_metrics, fetch_ga4_metrics, fetch_line_metrics
  - Combine into single dict with timestamp
  - Append to `data/kekka_weekly_metrics.json` (not overwrite)
  - Return aggregated data

- [ ] Create GitHub Actions workflow `.github/workflows/kekka-weekly-collect.yml`
  - Schedule: Monday 09:00 JST (cron: `0 0 * * 1` UTC)
  - Step: Python collect_weekly_metrics.py
  - Step: git add, commit, push (if data changed)
  - On error: send LINE notification to admin

- [ ] Write test: `test_collect_weekly_metrics_appends_to_json`
  - Create test JSON with 1 week
  - Call collect_and_save
  - Assert file now has 2 weeks
  - Assert chronological order preserved

- [ ] Commit: `feat: add weekly metrics collection workflow`

---

## Phase 2: Content Generation (Oct 8-15)

### Task 5: Facts Builder & Guard Checks

**Files:**
- Create: `scripts/build_facts.py`
- Create: `tests/test_build_facts.py`

**Interfaces:**
- Consumes: `data/kekka_kpi.json`, `data/kekka_weekly_metrics.json`
- Produces: `facts_dict: dict[str, Any]` with all allowed numbers, dates, segment info

**Steps:**

- [ ] Create `scripts/build_facts.py::build_facts() -> dict`
  - Read latest KPI week from `data/kekka_kpi.json`
  - Read latest metrics from `data/kekka_weekly_metrics.json`
  - Construct facts dict with: views, likes, sales, sales_or_fallback, article_count, days_since_first_publish, week_number, segment_counts
  - Handle missing sales data: fallback to last reported non-null sales (per spec 3.1)
  - Return facts dict

- [ ] Create `scripts/shipping_gate.py::check_numbers(text: str, facts_dict: dict) -> list[str]`
  - Extract all digit sequences from text (incl. full-width digits ０１２３４５６７８９)
  - For each token with unit (万/千/億): require exact match in facts_dict
  - For standalone digits 1/2/3: allow (common in prose)
  - Return list of bad_numbers; empty = pass

- [ ] Write tests for check_numbers with various inputs (valid, fabricated, edge cases)

- [ ] Commit: `feat: add facts builder and number guard`

---

### Task 6: AI Natural-Tone Content Generation

**Files:**
- Create: `scripts/generate_paid_content.py`
- Create: `data/claude_generation_rules.md` (prompt engineering rules)
- Create: `tests/test_generate_paid_content.py`

**Interfaces:**
- Consumes: `facts_dict` from build_facts, last week's free log content (string)
- Produces: `PaidArticleCandidate(title: str, body: str, price_suggestion_jpy: int, target_segment: str, confidence_score: float)`

**Steps:**

- [ ] Create `data/claude_generation_rules.md` with system prompt sections:
  - Tone: "You are a solo founder sharing real operational logs. Write like you're telling a trusted friend about this week's experiments. Include moments where you weren't sure, where something surprised you, or where you had to pivot. No AI polish—natural Japanese that sounds like you thinking out loud."
  - Constraints: "Only numbers in the facts dict. No made-up anecdotes. If you're unsure, say 'I'm not sure yet' rather than guess."
  - Target segments: Describe the 4 segments; generate differently for each
  - Forbidden: "必ず", "確実に稼", "誰でも", "楽して" (per spec 7.1)
  - Length: "200-400 words max"

- [ ] Create `scripts/generate_paid_content.py::generate_article_candidate(facts_dict: dict, free_log_excerpt: str, target_segment: str, attempt: int = 1) -> PaidArticleCandidate`
  - Build Claude prompt from rules + facts + excerpt + segment
  - Call Claude Sonnet with max_tokens=1500
  - Extract title (first line), body (rest)
  - Run check_numbers on body + title
  - Run check_banned_words on body
  - If fail: retry up to 2x with feedback in prompt ("再生成指示: 禁止語を使わずに書き直してください")
  - If still fail: return None
  - Else: calculate price_suggestion and confidence_score (see Task 7)
  - Return PaidArticleCandidate

- [ ] Write test: generate_article_candidate succeeds with valid facts, fails with fabricated numbers

- [ ] Commit: `feat: add paid article generation with guards`

---

### Task 7: Price Recommendation Engine

**Files:**
- Create: `scripts/price_strategy.py`
- Create: `tests/test_price_strategy.py`

**Interfaces:**
- Consumes: `facts_dict`, article metrics from previous weeks, target_segment string
- Produces: `(base_price_jpy: int, price_up_factors: list[str], price_down_factors: list[str])`

**Steps:**

- [ ] Create `scripts/price_strategy.py::recommend_price(facts_dict: dict, article_topic: str, target_segment: str) -> (int, list, list)`
  - Base: 1000 yen per spec 4.2
  - Price UP: if similar topic in prev weeks has 5+ purchases → +500; if segment_score ≥ 60 → +300
  - Price DOWN: if new topic (first time) → -300; special seasonal discount (Dec) → -320 (resulting in 680)
  - Return (final_price, up_factors, down_factors) for logging
  - Log decision to `data/price_decisions.json` with date, topic, segment, reasoning

- [ ] Write test: base 1000, add 500 if high sales history, verify final price

- [ ] Commit: `feat: add dynamic price recommendation`

---

## Phase 3: Segment-Based Distribution (Oct 16-23)

### Task 8: Segment Classification Engine

**Files:**
- Create: `scripts/classify_segments.py`
- Create: `tests/test_classify_segments.py`

**Interfaces:**
- Consumes: `GA4Metrics`, `LINEMetrics`, user engagement history
- Produces: `SegmentClassification(user_id: str, segment: str, confidence_score: float, reasoning: dict)`

**Steps:**

- [ ] Create `scripts/classify_segments.py::classify_user_segment(user_ga_events: list[dict], user_line_opens: int, user_purchases: list[dict]) -> (segment: str, score: float)`
  - High Engagement: weekly opens + skis ≥ 75th percentile (score 80+)
  - Active Reader: weekly opens 50-75th (score 60-79)
  - Discovery Seeker: monthly opens or search traffic (score 40-59)
  - LINE-Only: registered but no site visits (score 0-39)
  - Return segment name, score (0-100), reasoning dict

- [ ] Write test classifying mock users into each segment based on mock engagement data

- [ ] Create `scripts/bulk_classify.py` to run classify_user_segment on all users from GA4 + LINE
  - Output: `data/user_segments_<week>.json` with all users and scores
  - Log: summary stats (count per segment)

- [ ] Commit: `feat: add user segment classification`

---

### Task 9: Segment-Targeted Distribution Script

**Files:**
- Create: `scripts/distribute_to_segments.py`
- Create: `tests/test_distribute_to_segments.py`

**Interfaces:**
- Consumes: `PaidArticleCandidate`, `user_segments_<week>.json`, `price_strategy` output
- Produces: Distribution plan (which users get what messaging, when, via which channel)

**Steps:**

- [ ] Create `scripts/distribute_to_segments.py::plan_distribution(article: PaidArticleCandidate, users_by_segment: dict) -> dict`
  - High Engagement (score 60-100, 30% predicted purchase): Same day, direct note link + "新しい有料記事が出ました"
  - Active Reader (score 60-79, 15% predicted): Day 2, softer tone "詳しくはこちら"
  - Discovery Seeker (score 40-59, 10% predicted): Day 4, educational framing "この話題を理解する記事"
  - LINE-Only (score 0-39, 3% predicted): Day 7, digest + archive link
  - Return dict with timing, channel (note/LINE/X), message variant, segment

- [ ] Create `scripts/execute_distribution.py` to send notifications via Power Automate webhook or LINE API
  - Load plan from above
  - For each segment: construct message (with target_segment baked into Power Automate payload)
  - Call POST to Power Automate webhook (URL from env `POWER_AUTOMATE_WEBHOOK`)
  - Log result to `data/distribution_log_<week>.json`

- [ ] Write test: verify distribution plan assigns high-engagement users to immediate delivery

- [ ] Commit: `feat: add segment-targeted distribution`

---

## Phase 4: Continuous Improvement (Oct 24-Nov 30)

### Task 10: Weekly Performance Analysis

**Files:**
- Create: `scripts/analyze_weekly_performance.py`
- Create: `data/sales_feedback.json` (append-only log)
- Create: `tests/test_analyze_weekly_performance.py`

**Interfaces:**
- Consumes: sales data, segment data, distribution logs
- Produces: `WeeklyAnalysis(week: str, revenue: int, segment_performance: dict, price_accuracy: float, content_quality_score: float, next_week_recommendations: list[str])`

**Steps:**

- [ ] Create `scripts/analyze_weekly_performance.py::analyze_week(week: str) -> WeeklyAnalysis`
  - Aggregate sales by segment: revenue, conversion rate, avg purchase value
  - Calculate price_accuracy: (actual_sales / predicted_sales * segment_score)
  - Extract 3-5 actionable insights (highest-selling article type, lowest-performing segment, timing impact)
  - Return WeeklyAnalysis
  - Append to `data/sales_feedback.json` for historical learning

- [ ] Create `scripts/generate_claude_improvement_prompt.py`
  - Read last 4 weeks of WeeklyAnalysis
  - Build prompt: "Based on these 4 weeks of real sales data [insert data], propose 3 strategies to improve conversion next week. Only suggest changes we can implement (segment targeting, pricing, content type, timing). Be specific about what failed and why."
  - Call Claude Sonnet
  - Parse response into 3 recommendations
  - Save to `data/improvement_recommendations_<week>.json`

- [ ] Write test: analyze_week returns correct revenue sum and segment breakdown

- [ ] Commit: `feat: add weekly performance analysis and Claude-driven recommendations`

---

### Task 11: Weekly Automation Workflow

**Files:**
- Modify: `.github/workflows/kekka-weekly-full.yml` (new)
- Create: `scripts/run_weekly_cycle.sh`

**Steps:**

- [ ] Create `.github/workflows/kekka-weekly-full.yml`
  - Trigger: Monday 10:00 JST (after data collection from Task 4)
  - Steps:
    1. Checkout repo
    2. Set up Python 3.12
    3. `python scripts/collect_weekly_metrics.py` (or skip if already run)
    4. `python scripts/build_facts.py` → facts.json
    5. `python scripts/generate_paid_content.py` → candidates.json (3-4 articles)
    6. `python scripts/analyze_weekly_performance.py` → analysis.json
    7. `python scripts/generate_claude_improvement_prompt.py` → recommendations.json
    8. `git add data/*.json && git commit -m "weekly: <week> analysis and candidates" && git push`
    9. On error: LINE notify admin with error log

- [ ] Write bash wrapper `scripts/run_weekly_cycle.sh` for local testing

- [ ] Test locally: run workflow steps manually, verify all JSON files created

- [ ] Commit: `ci: add weekly full-cycle automation workflow`

---

### Task 12: AI-Natural Quality Assurance & Monthly Review

**Files:**
- Create: `scripts/sample_quality_review.py`
- Create: `data/quality_reviews_log.json` (append-only)
- Create: `tests/test_quality_gates.py`

**Steps:**

- [ ] Create `scripts/sample_quality_review.py::flag_for_review(week: str) -> list[dict]`
  - Randomly select 3 articles from generated candidates (or past month if few generated)
  - Extract 150-char preview of each
  - Flag: "AI-sounding phrases detected" if text contains "重要です" "〜することが大切です" "いくつかの〜" (template phrases)
  - Flag: "tone mismatch" if text length differs by >20% from reference corpus (previous natural articles)
  - Return list of flagged articles for human review
  - Log to `data/quality_reviews_log.json` with human rating (optional, filled in manually)

- [ ] Create monthly check: if quality_reviews_log shows 3+ articles with score <7/10, trigger Claude system prompt reset
  - Revert to spec baseline prompt (from data/claude_generation_rules.md)
  - Inject human feedback: "Recent articles felt too polished. Rebalance toward: concrete examples, hesitations, trial-and-error narrative."

- [ ] Write test: verify template-phrase detection triggers flag

- [ ] Commit: `feat: add monthly quality review and system prompt reset mechanism`

---

### Task 13: Safety & Audit Logging

**Files:**
- Create: `scripts/shipping_gate_full.py`
- Create: `data/shipping_audit.json` (immutable log)
- Modify: all generation/distribution scripts to call gate checks

**Steps:**

- [ ] Create `scripts/shipping_gate_full.py::audit_before_publish(article_text: str, price: int, target_segment: str, facts_dict: dict) -> (passed: bool, failures: list[str])`
  - Call check_numbers(text, facts_dict)
  - Call check_banned_words(text)
  - Verify price in expected range (500-3000)
  - Verify target_segment in valid set
  - Log all checks (passed/failed) to `data/shipping_audit.json` immutably
  - Return (all_passed, failure_reasons)
  - If any failure: block publication, log to stderr + LINE admin notification

- [ ] Integrate gate into distribution workflow:
  - After generate_paid_content.py: call audit_before_publish
  - If failed: do NOT call distribute_to_segments
  - Report to admin with reason

- [ ] Write test: gate passes valid article, rejects fabricated numbers and banned words

- [ ] Commit: `feat: add shipping gate audit logging`

---

## Success Criteria (End of Phase 4)

- [ ] Week 1 (Oct 1-7): Data pipeline stable, all 3 APIs collecting successfully
- [ ] Week 2 (Oct 8-15): Content generation producing 3-4 candidates/week with 0 failed guards
- [ ] Week 3 (Oct 16-23): Distribution reaching all 4 segments with segment-correct messaging
- [ ] Week 4+ (Oct 24+): Weekly cycle automated, improvement recommendations appearing in recommendations.json
- [ ] Nov 30: Revenue ≥ 5万円/month, AI-natural quality ≥ 8/10 average human review score
- [ ] Dec 31: Revenue ≥ 10万円/month (goal achieved)

