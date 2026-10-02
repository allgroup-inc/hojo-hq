# 沖縄企業のミカタ Instagram自動化実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize 沖縄企業のミカタ Instagram posts into 3 visual templates and build an automated generation + verification pipeline, delivering Week 5+ full automation with Mon/Wed/Fri approval gates throughout.

**Architecture:** 
- Week 1-2: Canva templates (11 pages × 3 templates) + initial test posts for 3 subsidies
- Week 3-4: Python scripts for auto-generation (`generate_ig_posts_mikata.py`) and verification (`verify_mikata_seido.py`), GitHub Actions workflow
- Week 5+: Full automation with continued approval gates
- Data modeling: Extend `subsidies.json` with 6 new fields (`ig_template`, `ig_priority`, `ig_example_industry`, `ig_before_amount`, `ig_after_amount`, `ig_exclude`)

**Tech Stack:** 
- Canva (template design)
- Python 3.11+ (scripts/generate_ig_posts_mikata.py, scripts/verify_mikata_seido.py)
- GitHub Actions (ig-posts-mikata.yml, Sunday 18:00 JST trigger)
- Claude API + Gemini API (multi-AI verification)
- JSON (subsidies.json, ig_posts_mikata_draft.json)

**Spec:** `/home/user/hojo-hq/docs/superpowers/specs/2026-09-28-mikata-ig-redesign.md`

---

## Global Constraints

- **Deadline rule**: Only SNS posts for subsidies with deadline ≥30 days (3-layer rule from CLAUDE.md)
- **Accuracy mandate**: All asserted amounts/dates must be verified against source URLs (絶対ルール1)
- **Approval gates**: Mon/Wed/Fri 10:00 humanizer + hojo-accuracy-check, throughout all phases including Week 5+ automation
- **Data freshness**: Verify data must be ≤30 days old; detect and flag stale records
- **Template IDs**: Scatter by seido ID to prevent pattern transparency (reference: `generate_ig_neta.py`)
- **Multi-AI verify**: For priority-1 subsidies (>¥100M + >30 days), use Claude + Gemini dual-check; both must agree
- **Enterprise focus**: Captions target business owner psychology (ROI/feasibility), not household needs
- **Okinawa scope**: Template 2 (Triage) limited to Okinawa-based or free-support programs only

---

## Review Focus

**Five high-impact failure modes not exercised by individual task tests:**

1. **Stale verify data** — A subsidy's source URL was moved/archived 45 days ago; verify script marks it ✓, but the field is out of date. Result: post with false info. Test: Mock a 40-day-old verify timestamp, expect flag in `data/subsidies.json` and skip from draft queue.

2. **Dual-AI disagreement** — Claude says deadline is 2026-12-31, Gemini says 2027-01-15. Current plan defaults to Claude. Result: one AI's output silently ignored, debugging opaque. Test: Inject conflicting verify responses, expect explicit `["claude_verified": true, "gemini_verified": false, "conflict": true]` in output JSON and comment in audit log.

3. **Template mismatch edge case** — A subsidy is both ≥¥100M (template 1 candidate) AND Okinawa-limited (template 2 candidate). Script picks template 1 silently. Result: wrong caption tone (ROI vs. triage). Test: Create test subsidy with both flags, verify `ig_template` field in JSON explicitly states which rule won (priority order), expect audit trail.

4. **Infinite loop in deadline rotation** — Week 1 posts use IDs [A, B, C]; Week 2 re-generates, tries to pick 5 new ones from 40-item pool, but 35 are already posted. Script selects duplicates or hangs. Result: no fresh content. Test: Mock full weeks of posting history, verify script detects "X days since last rotation" and adjusts template selection or flags alert.

5. **Caption assertion leakage** — Humanizer detects phrase "最大¥450万円" in caption, but `ig_before_amount` and `ig_after_amount` don't support it (schema flaw). Result: humanizer rejects post that spec considers valid. Test: Run template captions through assertion checker before humanizer; all amounts must come from `ig_example_industry` fields, not free text.

---

## File Structure

**New files created:**
- `scripts/generate_ig_posts_mikata.py` — Subsidy → caption/template mapper, outputs `ig_posts_mikata_draft.json`
- `scripts/verify_mikata_seido.py` — Multi-AI accuracy checker (Claude + Gemini), updates `data/subsidies.json` verify fields
- `.github/workflows/ig-posts-mikata.yml` — Sunday 18:00 JST auto-trigger
- `tests/scripts/test_generate_ig_posts_mikata.py` — Unit tests for generation logic
- `tests/scripts/test_verify_mikata_seido.py` — Unit tests for verification logic
- `docs/ig_posts_mikata_draft.json` (runtime artifact, .gitignore'd initially, committed to repo after Week 3)

**Modified files:**
- `data/subsidies.json` — Add 6 fields: `ig_template` (str: "template1"|"template2"|"template3"|null), `ig_priority` (int: 1-3), `ig_example_industry` (str), `ig_before_amount` (int), `ig_after_amount` (int), `ig_exclude` (bool)
- `.gitignore` — Add `data/ig_posts_mikata_draft.json` (until Week 4)
- `docs/Instagram投稿依頼_運用.md` — Extend with auto-generation workflow notes

---

## Task Breakdown

### Task 1: Extend `subsidies.json` schema

**Files:**
- Modify: `data/subsidies.json:1-20` (header + first entry example)
- Modify: `docs/data-schema.md` (if exists; else create reference)
- Test: `tests/data/test_subsidies_schema.py`

**Interfaces:**
- Consumes: Current `subsidies.json` structure (155 items)
- Produces: All 155 items with new fields added (nulls for unset values); schema docs clarifying types and rules

- [ ] **Step 1: Write test for schema validation**

```python
def test_subsidies_schema_has_ig_fields():
    subsidies = json.load(open('data/subsidies.json'))
    for item in subsidies:
        assert 'ig_template' in item, f"Missing ig_template in {item['id']}"
        assert 'ig_priority' in item
        assert 'ig_example_industry' in item
        assert 'ig_before_amount' in item
        assert 'ig_after_amount' in item
        assert 'ig_exclude' in item
        # Type checks
        assert item['ig_template'] in [None, "template1", "template2", "template3"]
        assert isinstance(item['ig_priority'], (int, type(None)))
        assert isinstance(item['ig_example_industry'], (str, type(None)))
        assert isinstance(item['ig_before_amount'], (int, type(None)))
        assert isinstance(item['ig_after_amount'], (int, type(None)))
        assert isinstance(item['ig_exclude'], bool)
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/data/test_subsidies_schema.py::test_subsidies_schema_has_ig_fields -v
```

Expected: FAIL with "KeyError: 'ig_template'" (field not yet added)

- [ ] **Step 3: Add 6 new fields to `data/subsidies.json`**

For each of the 155 items in subsidies.json, add:
- `"ig_template": null` (to be filled in Task 2)
- `"ig_priority": null`
- `"ig_example_industry": null` 
- `"ig_before_amount": null`
- `"ig_after_amount": null`
- `"ig_exclude": false`

Approach: Use Python script to parse, add fields, re-serialize (maintain field order: id, name, ..., ig_*).

- [ ] **Step 4: Run test again, verify it passes**

```bash
pytest tests/data/test_subsidies_schema.py::test_subsidies_schema_has_ig_fields -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/subsidies.json tests/data/test_subsidies_schema.py
git commit -m "refactor: extend subsidies.json with ig_* fields (schema prep for IG automation)"
```

---

### Task 2: Map 40 high-priority subsidies to template1 + assign ig_priority

**Files:**
- Modify: `data/subsidies.json` (populate ig_template, ig_priority for ~40 items matching Template 1 rule)
- Reference: `.claude/commands/README.md` (for context on data values)
- Test: `tests/data/test_ig_template_mapping.py`

**Interfaces:**
- Consumes: `data/subsidies.json` with new fields (from Task 1)
- Produces: 40 items with `ig_template="template1"`, `ig_priority` in range [1..40]

- [ ] **Step 1: Write test for Template 1 mapping rule**

```python
def test_template1_mapping_rule():
    subsidies = json.load(open('data/subsidies.json'))
    template1_items = [s for s in subsidies if s.get('ig_template') == 'template1']
    
    # Template 1 rule: 金額 >= 100万円 AND 締切 >= 30日
    for item in template1_items:
        max_amount = item.get('max_amount_yen')
        deadline_days = item.get('days_to_deadline')
        
        assert max_amount is not None and max_amount >= 1_000_000, \
            f"{item['id']} has max_amount {max_amount}, should be >= ¥1M for template1"
        assert deadline_days is not None and deadline_days >= 30, \
            f"{item['id']} has deadline in {deadline_days} days, should be >= 30 for template1"
        assert item.get('ig_priority') is not None and 1 <= item['ig_priority'] <= 40
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/data/test_ig_template_mapping.py::test_template1_mapping_rule -v
```

Expected: FAIL (ig_template not yet assigned)

- [ ] **Step 3: Manually identify and populate 40 Template 1 items in `data/subsidies.json`**

Filter subsidies where:
- `max_amount_yen >= 1_000_000` 
- `days_to_deadline >= 30` (or no deadline / always-open)

For each matching item, set:
- `ig_template: "template1"`
- `ig_priority: <rank 1-40 by amount descending, then by days_to_deadline descending>`
- `ig_example_industry: <representative industry, e.g., "製造業", "飲食業", "小売業">`

Data source to validate: `data/subsidies.json` directly. Suggested approach:
1. Export to CSV or script review
2. Find all items with `max_amount_yen >= 1_000_000` (should be ~40-50)
3. Filter further for `days_to_deadline >= 30`
4. Assign ig_priority rank, then update JSON

- [ ] **Step 4: Run test, verify it passes**

```bash
pytest tests/data/test_ig_template_mapping.py::test_template1_mapping_rule -v
```

Expected: PASS (40 items with valid template1 mapping)

- [ ] **Step 5: Commit**

```bash
git add data/subsidies.json tests/data/test_ig_template_mapping.py
git commit -m "data: map 40 subsidies to template1 (ig_priority 1-40) based on ¥1M+ / 30-day rule"
```

---

### Task 3: Map 5-10 Okinawa/free-support subsidies to template2 + assign ig_priority

**Files:**
- Modify: `data/subsidies.json` (populate ig_template, ig_priority for ~5-10 items matching Template 2 rule)
- Test: `tests/data/test_ig_template_mapping.py` (extend)

**Interfaces:**
- Consumes: `data/subsidies.json` with template1 mappings (from Task 2)
- Produces: 5-10 items with `ig_template="template2"`, `ig_priority` in range [1..10]

- [ ] **Step 1: Extend test for Template 2 mapping rule**

```python
def test_template2_mapping_rule():
    subsidies = json.load(open('data/subsidies.json'))
    template2_items = [s for s in subsidies if s.get('ig_template') == 'template2']
    
    # Template 2 rule: 沖縄県限定 OR 無料支援
    for item in template2_items:
        is_okinawa_only = 'okinawa' in (item.get('target_region') or '').lower()
        is_free = (item.get('max_amount_yen') or 0) == 0
        
        assert is_okinawa_only or is_free, \
            f"{item['id']} should be Okinawa-only or free for template2"
        assert item.get('ig_priority') is not None and 1 <= item['ig_priority'] <= 10
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/data/test_ig_template_mapping.py::test_template2_mapping_rule -v
```

Expected: FAIL

- [ ] **Step 3: Identify and populate 5-10 Template 2 items in `data/subsidies.json`**

Filter subsidies where:
- `target_region` contains "沖縄" OR `max_amount_yen == 0` (free support)
- Exclude already-assigned template1 items

Set for each:
- `ig_template: "template2"`
- `ig_priority: <rank 1-10 by relevance (free support + Okinawa-specific > general Okinawa)>`
- `ig_example_industry: <e.g., "全業種可", "小規模事業者等">`

Test examples from spec: "小規模事業者等デジタル化支援事業" should be template2.

- [ ] **Step 4: Run test, verify it passes**

```bash
pytest tests/data/test_ig_template_mapping.py::test_template2_mapping_rule -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/subsidies.json
git commit -m "data: map 5-10 subsidies to template2 (Okinawa-only / free support, priority 1-10)"
```

---

### Task 4: Map 3-5 large transformation subsidies to template3

**Files:**
- Modify: `data/subsidies.json` (populate ig_template, ig_priority for 3-5 items matching Template 3 rule)
- Test: `tests/data/test_ig_template_mapping.py` (extend)

**Interfaces:**
- Consumes: `data/subsidies.json` with template1 + template2 mappings
- Produces: 3-5 items with `ig_template="template3"`, `ig_priority` in range [1..5]

- [ ] **Step 1: Extend test for Template 3 mapping rule**

```python
def test_template3_mapping_rule():
    subsidies = json.load(open('data/subsidies.json'))
    template3_items = [s for s in subsidies if s.get('ig_template') == 'template3']
    
    # Template 3 rule: 事業転換 OR 大型補助 (>= 500万円) AND 年度内単発
    for item in template3_items:
        max_amount = item.get('max_amount_yen') or 0
        is_transformation = '転換' in (item.get('name') or '')
        is_large = max_amount >= 50_000_000  # 5000万円 = 事業再構築補助金等の規模
        
        assert is_transformation or is_large, \
            f"{item['id']} should be transformation-focused or >=¥500M for template3"
        assert item.get('ig_priority') is not None and 1 <= item['ig_priority'] <= 5
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/data/test_ig_template_mapping.py::test_template3_mapping_rule -v
```

Expected: FAIL

- [ ] **Step 3: Identify and populate 3-5 Template 3 items in `data/subsidies.json`**

Filter subsidies where:
- `max_amount_yen >= 50_000_000` (¥5000万 = large transformation scale) OR
- Keyword match: "事業再構築", "GX", "DX" in name AND single-year program

Set for each:
- `ig_template: "template3"`
- `ig_priority: <1-5 by size and applicability>`
- `ig_example_industry: <e.g., "製造業", "小売業", "飲食業">`

Spec example: "事業再構築補助金GX・DX型" (max ¥1.5B) → template3, priority 1.

- [ ] **Step 4: Run test, verify it passes**

```bash
pytest tests/data/test_ig_template_mapping.py::test_template3_mapping_rule -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add data/subsidies.json
git commit -m "data: map 3-5 subsidies to template3 (large transformation, priority 1-5)"
```

---

### Task 5: Create Canva Template 1 (Numbers & Scarcity, 4 pages)

**Files:**
- Artifact: Canva project "IG Template 1 - Numbers & Scarcity" (shared link saved to docs/)
- Reference: `docs/superpowers/specs/2026-09-28-mikata-ig-redesign.md` §1
- Output: Save template link + exportable PDFs to `docs/ig_templates/template1_canva_link.md`

**Interfaces:**
- Consumes: Spec design guidelines (colors #00335C, #F88800, fonts, sizes)
- Produces: Canva template with 4 editable pages (P1: number, P2-P3: Before/After, P4: table)

- [ ] **Step 1: Create Canva project structure**

Create blank Canva design with 1080×1350px, 4 pages named:
- P1: "Large Number + Industry"
- P2: "Before/After Example 1"
- P3: "Before/After Example 2"
- P4: "Quick Reference Table"

Set brand kit: Navy #00335C, Orange #F88800, fonts Meiryo Bold (headings) / Meiryo Regular (body).

- [ ] **Step 2: Design P1 (Large Number + Industry)**

- Navy background #00335C
- Orange text for number (150pt bold): "〇〇万円" (placeholder, editable)
- White subtitle (40pt): subsidy name
- Small text (24pt): target industry
- Bottom: date stamp + "沖縄企業のミカタ" logo
- Test with mock data: "450万円", "デジタル化・AI導入補助金", "製造業"

- [ ] **Step 3: Design P2 (Before/After Example 1)**

- White background
- Left side (30%): "Before" label + cost (e.g., "300万円")
- Right side (30%): "After" label + cost (e.g., "100万円")
- Center (40%): Industry example (e.g., "飲食業") + short use case
- Arrow or visual divider between Before/After
- Test: Verify "300万円" and "100万円" fit without overflow

- [ ] **Step 4: Design P3 (Before/After Example 2)**

Mirror P2 structure with different industry/amounts.

- [ ] **Step 5: Design P4 (Quick Reference Table)**

- Header: "補助率・条件・締切"
- 3 columns: 補助率 (e.g., 最大3/4) | 対象条件 (e.g., 中小企業) | 締切 (e.g., 2026-12-31)
- Editable cells, clear borders, orange header row
- Test: Verify 3 rows of data fit on 1 page

- [ ] **Step 6: Test with real subsidy data**

Use "デジタル化・AI導入補助金2026" (Task 7 test subsidy) data:
- P1: "450万円" (max_amount)
- P2: "300万円 → 100万円" (ig_before_amount / ig_after_amount)
- P3: Alternative industry example
- P4: Actual補助率, deadline

Visual check: Text readability, color contrast, layout balance.

- [ ] **Step 7: Export template**

Save as:
- PDF (archival)
- Canva link (for future edits)
- Describe in `docs/ig_templates/template1_canva_link.md`

Example link: `https://www.canva.com/design/[PROJECT-ID]/...`

---

### Task 6: Create Canva Template 2 (Triage, 1 page)

**Files:**
- Artifact: Canva project "IG Template 2 - Triage"
- Output: `docs/ig_templates/template2_canva_link.md`

**Interfaces:**
- Consumes: Spec design guidelines (gradient navy→orange, 3-step icons, QR)
- Produces: Single 1080×1350px page with QR/phone editable areas

- [ ] **Step 1: Create Canva page**

1080×1350px, gradient background navy #00335C (top) → orange #F88800 (bottom).

- [ ] **Step 2: Design layout**

- Top 40%: Title "沖縄県の中小企業へ 無料デジタル化サポート" (white, 80pt bold)
- Middle 40%: 3-step icons (相談 → 診断 → 実装) with connecting arrows, white icons/text
- Bottom 20%: Freephone "0570-XXXXXX" (editable) + QRコード (right, 150×150px, editable)

- [ ] **Step 3: Test with Template 2 test subsidy data**

Use "小規模事業者等デジタル化支援事業" (Okinawa-based free support):
- Title: "沖縄県デジタル化支援事業" (adjust per subsidy)
- QR code: Mock QR → LINE friend-add endpoint
- Phone: "0570-..." (from subsidy contact info)

Verify QR size and phone text readability.

- [ ] **Step 4: Export**

Save PDF + Canva link to `docs/ig_templates/template2_canva_link.md`.

---

### Task 7: Create Canva Template 3 (Seasonal Campaign, 6 pages)

**Files:**
- Artifact: Canva project "IG Template 3 - Seasonal Campaign"
- Output: `docs/ig_templates/template3_canva_link.md`

**Interfaces:**
- Consumes: Spec design guidelines (navy + orange, checklist stages, transformation examples)
- Produces: 6-page carousel with editable example/checklist slots

- [ ] **Step 1: Create 6-page Canva project**

Each page 1080×1350px. Pages:
1. "事業転換を検討していますか?" (hook)
2-4. Industry transformation examples
5. Preparation checklist (6mo / 3mo / 1mo / 直前)
6. Call-to-action → LINE consultation

- [ ] **Step 2: Design P1 (Hook)**

Navy background, orange large text: "事業転換を検討していますか？"
Subtext (white, 40pt): "国が最大1.5億円サポートします。"

- [ ] **Step 3: Design P2-P4 (Example transformation 1-3)**

Example 1: 製造業 → IoT活用製造
- "Before": Traditional process (icon/image)
- "After": Automated/IoT process (icon/image)
- Benefit text (white, 28pt)

Repeat for P3-P4 with different industries (小売→EC, 飲食→宅配).

- [ ] **Step 4: Design P5 (Checklist)**

Navy background, white text. Vertical timeline:
- 6ヶ月前: ☐ 経営課題の整理
- 3ヶ月前: ☐ 事業計画ドラフト
- 1ヶ月前: ☐ 書類準備
- 申請直前: ☐ 提出準備

Checkbox icons change from ☐ to ☑ (can be templated via text replacement).

- [ ] **Step 5: Design P6 (CTA)**

Orange background, white text: "詳しくはプロフィールのLINEから相談できます。"
Include QR code (editable) for LINE friend-add.

- [ ] **Step 6: Test with Template 3 test subsidy**

Use "事業再構築補助金GX・DX型":
- P1: "事業転換を検討していますか？" ✓
- P2-P4: Industry examples (3 different sectors) ✓
- P5: 6ヶ月 checklist (appropriate for large subsidy) ✓
- P6: QR → LINE consultation ✓

- [ ] **Step 7: Export**

Save PDF + Canva link to `docs/ig_templates/template3_canva_link.md`.

---

### Task 8: Populate `ig_before_amount`, `ig_after_amount`, `ig_example_industry` for test subsidies

**Files:**
- Modify: `data/subsidies.json` (3 entries: デジタル化・AI導入, 小規模事業者等デジタル化, 事業再構築補助金GX・DX)
- Test: `tests/data/test_ig_example_data.py`

**Interfaces:**
- Consumes: `data/subsidies.json` with template mappings (from Tasks 2-4)
- Produces: 3 test subsidies with complete Before/After amounts and example industries

- [ ] **Step 1: Write test for test subsidy data completeness**

```python
def test_example_subsidies_have_complete_data():
    subsidies = json.load(open('data/subsidies.json'))
    test_ids = [
        "seido_id_for_denshi_ai",  # デジタル化・AI導入補助金2026
        "seido_id_for_okinawa_support",  # 小規模事業者等デジタル化支援事業
        "seido_id_for_jigyou_saikouchiku"  # 事業再構築補助金GX・DX型
    ]
    
    for seido_id in test_ids:
        item = next((s for s in subsidies if s['id'] == seido_id), None)
        assert item is not None, f"Test subsidy {seido_id} not found"
        assert item.get('ig_before_amount') is not None and item['ig_before_amount'] > 0
        assert item.get('ig_after_amount') is not None and item['ig_after_amount'] > 0
        assert item.get('ig_example_industry') is not None and len(item['ig_example_industry']) > 0
        assert item['ig_before_amount'] > item['ig_after_amount'], \
            f"{seido_id}: Before ({item['ig_before_amount']}) should be > After ({item['ig_after_amount']})"
```

- [ ] **Step 2: Find exact seido_id for each test subsidy in `data/subsidies.json`**

Search for keywords in subsidy names:
- "デジタル化・AI導入補助金2026" → locate seido_id (e.g., "a0WJ200000ABC123")
- "小規模事業者等デジタル化支援事業" → locate
- "事業再構築補助金" + "GX" or "DX" → locate

- [ ] **Step 3: Populate Before/After amounts for test subsidy 1 (デジタル化・AI導入)**

From spec example: max_amount ¥450万円.
- `ig_before_amount`: 400万円 (realistic investment without subsidy)
- `ig_after_amount`: 100万円 (after subsidy, remaining self-fund)
- `ig_example_industry`: "飲食業"

- [ ] **Step 4: Populate Before/After for test subsidy 2 (小規模事業者等デジタル化)**

Free support (max_amount = 0).
- `ig_before_amount`: 150万円 (cost of DX without support)
- `ig_after_amount`: 0 (free support)
- `ig_example_industry`: "小規模事業者" or "小売業"

- [ ] **Step 5: Populate Before/After for test subsidy 3 (事業再構築補助金)**

Max ¥1.5B (large subsidy).
- `ig_before_amount`: 5000万円 (business transformation cost)
- `ig_after_amount`: 1500万円 (after subsidy at hypothetical 70% rate)
- `ig_example_industry`: "製造業"

- [ ] **Step 6: Run test, verify it passes**

```bash
pytest tests/data/test_ig_example_data.py::test_example_subsidies_have_complete_data -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add data/subsidies.json tests/data/test_ig_example_data.py
git commit -m "data: populate ig_before_amount/after_amount/example_industry for 3 test subsidies (Week 1 Canva refs)"
```

---

### Task 9: Create test post 1 (Template 1 + デジタル化・AI導入補助金)

**Files:**
- Artifact: Canva export "IG Post Test 1 - AI導入補助金" (1080×1350px PNG)
- Create: `docs/ig_posts_test/test_post_1_caption.md` (caption + hashtags)
- Create: `docs/ig_posts_test/test_post_1_metadata.json` (approval tracking)

**Interfaces:**
- Consumes: Canva Template 1, test subsidy 1 data (デジタル化・AI導入補助金)
- Produces: 4-page carousel image, caption, metadata ready for humanizer review

- [ ] **Step 1: Use Canva Template 1 to create test post**

Fill in:
- P1: "450万円" (max_amount), "デジタル化・AI導入補助金", "飲食業"
- P2: "Before 400万円" → "After 100万円" + "飲食業"
- P3: Same Before/After with different industry (e.g., "製造業": "300万円" → "120万円")
- P4: Quick table with補助率, 対象条件, 締切 (from subsidy data)

- [ ] **Step 2: Export as PNG (4 pages)**

Generate image files:
- `ig_test_1_p1.png`
- `ig_test_1_p2.png`
- `ig_test_1_p3.png`
- `ig_test_1_p4.png`

Or: Export as single 4-page carousel (Canva carousel export).

- [ ] **Step 3: Create caption from spec template**

Use spec §1 caption template, customize with subsidy name and amounts:

```
【1行フック】
「うちの業務、自動化に400万円かけてたのが、補助金で実質100万円。」

【本文】
AI導入は「高い」と思ってませんか？
実は、国の補助金なら【上限450万円・補助率最大3/4】で支援されます。

このカルーセルでは、
✓ 実際の活用例（業種別）
✓ 補助率・対象条件
✓ 申請スケジュール

を紹介します。

「うちの業種でも対象かな?」と思ったら、プロフィールのLINEから無料相談できます。

【ハッシュタグ】
#沖縄企業のミカタ #DX補助金 #中小企業支援 #AI導入 #業務効率化
```

Save to `docs/ig_posts_test/test_post_1_caption.md`.

- [ ] **Step 4: Create metadata JSON**

```json
{
  "post_id": "test_1",
  "template": "template1",
  "seido_id": "seido_id_for_denshi_ai",
  "seido_name": "デジタル化・AI導入補助金2026",
  "created_at": "2026-09-28",
  "status": "draft",
  "approval_history": [
    {
      "date": null,
      "reviewer": null,
      "status": "awaiting_humanizer",
      "notes": null
    }
  ]
}
```

Save to `docs/ig_posts_test/test_post_1_metadata.json`.

- [ ] **Step 5: Prepare for approval gate (Mon humanizer check)**

Bundle: PNG + caption + metadata.json.
Ready to pass to humanizer on Monday (Task 10).

---

### Task 10: Create test post 2 (Template 2 + 小規模事業者等デジタル化支援事業)

**Files:**
- Artifact: Canva export "IG Post Test 2 - デジタル化支援" (1080×1350px PNG)
- Create: `docs/ig_posts_test/test_post_2_caption.md`
- Create: `docs/ig_posts_test/test_post_2_metadata.json`

**Interfaces:**
- Consumes: Canva Template 2, test subsidy 2 data (小規模事業者等デジタル化支援事業)
- Produces: Single-page image, caption, metadata

- [ ] **Step 1: Use Canva Template 2 to create test post**

Fill in:
- Title: "沖縄県の中小企業へ 無料デジタル化サポート" (or adjust per subsidy name)
- 3 steps: 相談 → 診断 → 実装支援
- Phone: Contact number from subsidy (e.g., "0570-XXXXXX")
- QR code: Link to LINE friend-add

- [ ] **Step 2: Export as PNG**

`ig_test_2.png` (single page)

- [ ] **Step 3: Create caption from spec template**

```
【1行フック】
「デジタル化に100万円は必要？いいえ、沖縄県なら無料です。」

【本文】
DX導入したいけど、費用が心配。そんな企業向けに、沖縄県が用意しているのが【小規模事業者等デジタル化支援事業】。

✓ 相談・診断が無料
✓ 専門家による実装サポート付き
✓ 対象は沖縄県内の全業種

「どんなことができるのか」を知りたいだけでも、相談できます。

プロフィールのLINEから「デジタル化相談」とメッセージをもらえば、沖縄県産業振興公社の担当者から連絡があります。

詳細は公式ページで。

【ハッシュタグ】
#沖縄県 #デジタル化支援 #中小企業 #無料相談 #企業のミカタ
```

Save to `docs/ig_posts_test/test_post_2_caption.md`.

- [ ] **Step 4: Create metadata JSON**

Similar to test_post_1, update seido_id and status.

- [ ] **Step 5: Prepare for approval**

Ready for humanizer check.

---

### Task 11: Create test post 3 (Template 3 + 事業再構築補助金GX・DX型)

**Files:**
- Artifact: Canva export "IG Post Test 3 - 事業再構築" (6 pages, 1080×1350px each)
- Create: `docs/ig_posts_test/test_post_3_caption.md`
- Create: `docs/ig_posts_test/test_post_3_metadata.json`

**Interfaces:**
- Consumes: Canva Template 3, test subsidy 3 data (事業再構築補助金GX・DX型)
- Produces: 6-page carousel images, caption, metadata

- [ ] **Step 1: Use Canva Template 3 to create test post**

Fill in:
- P1: "事業転換を検討していますか？ 国が最大1.5億円サポートします。"
- P2-P4: Transformation examples (製造→IoT, 小売→EC, 飲食→宅配) with before/after indicators
- P5: 6-month preparation checklist
- P6: CTA + QR → LINE consultation

- [ ] **Step 2: Export as PNG (6 pages)**

`ig_test_3_p1.png` through `ig_test_3_p6.png`, or carousel export.

- [ ] **Step 3: Create caption from spec template**

```
【1行フック】
「事業転換は『大きなリスク』と思ってませんか？国が最大1.5億円サポートします。」

【本文】
経営環境が大きく変わる時代。
「今のままじゃ5年後が不安」と感じている経営者へ。

国の【事業再構築補助金 GX・DX型】は、
✓ 事業の根本的な転換を支援
✓ 最大1.5億円の補助
✓ 準備期間は約6ヶ月が目安

このカルーセルでは、
▶ 実際の転換事例（業種別）
▶ 採択企業の声
▶ 準備スケジュール（逆算チェックリスト）

を紹介します。

「うちはどの転換パターン?」と迷ったら、プロフィールのLINEで無料相談できます。

国が応援する事業転換。この機会を逃さないでください。

【ハッシュタグ】
#事業再構築補助金 #GX #DX #沖縄企業 #事業転換支援
```

Save to `docs/ig_posts_test/test_post_3_caption.md`.

- [ ] **Step 4: Create metadata JSON**

Update seido_id → 事業再構築補助金.

- [ ] **Step 5: Prepare for approval**

Ready for humanizer check on Monday.

---

### Task 12: Run test posts 1-3 through humanizer + hojo-accuracy-check (Week 2 Mon/Wed/Fri)

**Files:**
- Reference: `scripts/humanizer.py` (existing skill)
- Reference: `scripts/check_ig_neta.py` (adaptation for Mikata posts)
- Artifact: Approval/rejection logs in `docs/ig_posts_test/approval_log.md`

**Interfaces:**
- Consumes: Test posts 1-3 (captions + images) from Tasks 9-11
- Produces: Approval status, modification notes, humanizer/accuracy-check sign-off

- [ ] **Step 1: Monday (Week 2 Mon 10:00) - Humanizer pass**

Run humanizer script on captions from test_post_1, 2, 3:

```bash
python scripts/humanizer.py docs/ig_posts_test/test_post_1_caption.md
python scripts/humanizer.py docs/ig_posts_test/test_post_2_caption.md
python scripts/humanizer.py docs/ig_posts_test/test_post_3_caption.md
```

Expected output: Pass/Fail on "AI deflection" (AI-detected phrasing like "いかがでしょうか", "ぜひ", excessive emoji).

Acceptance: 0 high-severity AI deflections per spec (Section 1 caption template shows humanizer-approved style).

- [ ] **Step 2: Monday (Week 2 Mon) - hojo-accuracy-check pass**

Validate amounts and deadlines:

```bash
python scripts/check_ig_neta.py --online docs/ig_posts_test/test_post_1_caption.md
python scripts/check_ig_neta.py --online docs/ig_posts_test/test_post_2_caption.md
python scripts/check_ig_neta.py --online docs/ig_posts_test/test_post_3_caption.md
```

Expected output: All asserted amounts/deadlines match source URLs (verify_status: true).

- [ ] **Step 3: Wednesday (Week 2 Wed 10:00) - Re-approve post 1 if needed**

If Monday feedback requires edits:
- Update caption in `test_post_1_caption.md`
- Re-run humanizer + accuracy-check
- Confirm pass

- [ ] **Step 4: Friday (Week 2 Fri 10:00) - Final approval by 小柳さん**

小柳さん reviews all 3 test posts' approval logs and OKs them for posting.

Sign-off in `approval_log.md`:

```markdown
### Test Post 1 - デジタル化・AI導入補助金
- Humanizer: PASS (2026-10-02)
- Accuracy-check: PASS (2026-10-02)
- 小柳さん approval: APPROVED (2026-10-04)

### Test Post 2 - デジタル化支援
- Humanizer: PASS
- Accuracy-check: PASS
- 小柳さん approval: APPROVED

### Test Post 3 - 事業再構築補助金
- Humanizer: PASS
- Accuracy-check: PASS
- 小柳さん approval: APPROVED
```

- [ ] **Step 5: Post to Instagram (if approval given)**

Upload test_post_1, 2, 3 to Instagram (manually or via IG Insights, with UTM tags for LINE CTR tracking).

Expected: Collect engagement data (saves, shares, CTR) for 1 week.

---

### Task 13: Write `generate_ig_posts_mikata.py` (auto-generation logic)

**Files:**
- Create: `scripts/generate_ig_posts_mikata.py` (405+ lines, reference `generate_ig_neta.py`)
- Create: `tests/scripts/test_generate_ig_posts_mikata.py` (unit tests)
- Modify: `.gitignore` (add `data/ig_posts_mikata_draft.json` until Week 4)

**Interfaces:**
- Consumes: `data/subsidies.json` (155 items with ig_template, ig_priority, ig_before_amount, etc. from Tasks 1-4)
- Produces: `data/ig_posts_mikata_draft.json` (JSON array of 5 draft posts per week, each with: seido_id, caption, template_id, hashtags, approval_needed)

- [ ] **Step 1: Write unit test for template selection logic**

```python
def test_generate_selects_template1_high_priority():
    """Template 1 items (ig_priority 1-40) chosen first, ranked by priority."""
    drafts = generate_ig_posts(subsidies_json="data/subsidies.json", max_posts=5)
    
    template1_drafts = [d for d in drafts if d['template'] == 'template1']
    assert len(template1_drafts) >= 3, "At least 3 of 5 weekly posts should be template1"
    
    priorities = [d['ig_priority'] for d in template1_drafts]
    assert all(p <= 40 for p in priorities), "Template1 priorities must be ≤ 40"
    # Verify no repeats from last 5 weeks (stored in ig_posts_history.json)
    historical_ids = load_historical_post_ids()
    for draft in template1_drafts:
        assert draft['seido_id'] not in historical_ids, \
            f"Seido {draft['seido_id']} already posted in recent weeks"
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/scripts/test_generate_ig_posts_mikata.py::test_generate_selects_template1_high_priority -v
```

Expected: FAIL (function not defined)

- [ ] **Step 3: Implement `generate_ig_posts_mikata.py`**

Signature:

```python
def generate_ig_posts(
    subsidies_json: str = "data/subsidies.json",
    max_posts: int = 5,
    history_json: str = "data/ig_posts_history.json"
) -> list[dict]:
    """
    Generate 5 weekly IG draft posts from subsidies.json, ranked by ig_priority.
    
    Returns: List of dicts with keys:
    - seido_id: str
    - template: str ("template1" | "template2" | "template3")
    - ig_priority: int
    - caption: str (spec-templated)
    - hashtags: list[str]
    - ig_before_amount: int
    - ig_after_amount: int
    - image_placeholders: dict (for Canva/image API)
    - approval_needed: bool
    """
```

Logic:
1. Load subsidies.json, filter by `ig_exclude: false`
2. Load historical post IDs (from `ig_posts_history.json`); exclude recent 5-week posts
3. Sort by `ig_template` (template1 > template2 > template3), then by `ig_priority` (ascending)
4. Select up to 5 items; generate caption from spec template + data
5. Populate hashtags from spec (customize per template/subsidy)
6. Return as JSON

Reference: `scripts/generate_ig_neta.py` for caption templating approach (use seido_id scattering to avoid transparency).

- [ ] **Step 4: Run test, verify it passes**

```bash
pytest tests/scripts/test_generate_ig_posts_mikata.py::test_generate_selects_template1_high_priority -v
```

Expected: PASS (5 posts generated with correct template distribution)

- [ ] **Step 5: Add test for caption generation**

```python
def test_caption_no_unsupported_assertions():
    """Captions must not assert amounts/dates directly; only reference template."""
    drafts = generate_ig_posts(subsidies_json="data/subsidies.json", max_posts=5)
    
    for draft in drafts:
        caption = draft['caption']
        # Verify no direct amount assertions like "450万円" unless templated
        # (spec allows only "{max_amount_placeholder}" or actual amounts via before_amount/after_amount)
        import re
        # Pattern: digit+ 万円 NOT preceded by { (free-text number)
        pattern = r'(?<!\{)\d+万円(?!\})'
        matches = re.findall(pattern, caption)
        if matches:
            # Verify all matches are in ig_before_amount or ig_after_amount values
            before_str = f"{draft.get('ig_before_amount', 0)}万円".replace("万円万円", "万円")
            after_str = f"{draft.get('ig_after_amount', 0)}万円".replace("万円万円", "万円")
            for m in matches:
                assert m in [before_str, after_str, f"{draft.get('max_amount_yen', 0)//10000}万円"], \
                    f"Caption has unsupported amount assertion: {m}"
```

- [ ] **Step 6: Run extended tests**

```bash
pytest tests/scripts/test_generate_ig_posts_mikata.py -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/generate_ig_posts_mikata.py tests/scripts/test_generate_ig_posts_mikata.py
git commit -m "feat: implement generate_ig_posts_mikata.py (auto-caption + template mapper)"
```

---

### Task 14: Write `verify_mikata_seido.py` (multi-AI accuracy checking)

**Files:**
- Create: `scripts/verify_mikata_seido.py` (350+ lines)
- Create: `tests/scripts/test_verify_mikata_seido.py` (unit tests)

**Interfaces:**
- Consumes: `data/subsidies.json` (155 items, prioritized by Task 2-4)
- Produces: Updated `data/subsidies.json` with new field `verified: {"claude": bool, "gemini": bool, "timestamp": str, "conflict": bool}`

- [ ] **Step 1: Write test for verification priority logic**

```python
def test_verify_priority_1_first():
    """Priority-1 subsidies (>¥100M + >30 days) verified first with dual-check."""
    subsidies = json.load(open('data/subsidies.json'))
    
    priority_1 = [s for s in subsidies 
                  if s.get('ig_priority') and s['ig_priority'] <= 5 
                  and s.get('max_amount_yen', 0) >= 100_000_000
                  and s.get('days_to_deadline', 0) >= 30]
    
    # Mock: run verify on 1 subsidy from priority_1
    result = verify_subsidy_dual_check(priority_1[0])
    
    assert result['claude_verified'] in [True, False, None]
    assert result['gemini_verified'] in [True, False, None]
    assert 'timestamp' in result
    assert 'conflict' in result
    
    # If both are True, conflict must be False
    if result['claude_verified'] and result['gemini_verified']:
        assert result['conflict'] == False
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/scripts/test_verify_mikata_seido.py::test_verify_priority_1_first -v
```

Expected: FAIL (function not defined)

- [ ] **Step 3: Implement `verify_mikata_seido.py`**

Signature:

```python
def verify_subsidy_dual_check(subsidy: dict) -> dict:
    """
    Verify subsidy via Claude + Gemini dual-check (multi-AI連携 per CLAUDE.md).
    
    Returns:
    {
        "claude_verified": bool | None,
        "gemini_verified": bool | None,
        "timestamp": str (ISO8601),
        "conflict": bool,
        "details": {
            "amount_match": bool,
            "deadline_match": bool,
            "source_reachable": bool,
            "error_msg": str | None
        }
    }
    """
```

Logic:
1. Extract source_url from subsidy
2. Fetch source URL content (with robot.txt/Terms check from 守り部)
3. Call Claude API: extract deadline, max_amount, target conditions
4. Call Gemini API: same extraction (independent)
5. Compare Claude output vs. Gemini output
6. If both agree: verified = true
7. If one fails: verified = None, conflict = false
8. If both succeed but differ: conflict = true, verified = false
9. Update subsidy JSON field `verified` with result

Reference: `check_ig_neta.py` for source-fetching pattern.

- [ ] **Step 4: Add test for conflict detection**

```python
def test_conflict_detection():
    """When Claude and Gemini disagree on deadline, mark conflict=true."""
    mock_subsidy = {
        "id": "test_conflict",
        "source_url": "https://example.com/seido",
        "max_amount_yen": 450_000_000
    }
    
    # Mock Claude response: deadline 2026-12-31
    # Mock Gemini response: deadline 2027-01-15
    
    result = verify_subsidy_dual_check(mock_subsidy)
    
    assert result['claude_verified'] == True
    assert result['gemini_verified'] == True
    assert result['conflict'] == True  # Dates disagree
    assert result['details']['deadline_match'] == False
```

- [ ] **Step 5: Run extended tests**

```bash
pytest tests/scripts/test_verify_mikata_seido.py -v
```

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/verify_mikata_seido.py tests/scripts/test_verify_mikata_seido.py
git commit -m "feat: implement verify_mikata_seido.py (Claude + Gemini dual-check for accuracy)"
```

---

### Task 15: Create `.github/workflows/ig-posts-mikata.yml` (auto-trigger on Sunday 18:00 JST)

**Files:**
- Create: `.github/workflows/ig-posts-mikata.yml` (45+ lines)
- Reference: Spec §4, existing workflow patterns in `.github/workflows/`

**Interfaces:**
- Consumes: `scripts/generate_ig_posts_mikata.py`, `scripts/verify_mikata_seido.py`
- Produces: Weekly draft JSON, push to branch, notify approvers

- [ ] **Step 1: Write test for workflow trigger schedule**

```python
def test_workflow_schedule_is_correct():
    """Workflow must trigger Sunday 18:00 JST (Sunday 09:00 UTC)."""
    import yaml
    with open('.github/workflows/ig-posts-mikata.yml') as f:
        workflow = yaml.safe_load(f)
    
    schedule = workflow['on']['schedule']
    assert '0 9 * * 0' in [s['cron'] for s in schedule], \
        "Schedule must include '0 9 * * 0' (Sun 09:00 UTC = Sun 18:00 JST)"
```

- [ ] **Step 2: Run test, verify it fails**

```bash
pytest tests/.../test_workflow_schedule -v
```

Expected: FAIL (file doesn't exist)

- [ ] **Step 3: Create `.github/workflows/ig-posts-mikata.yml`**

```yaml
name: Generate IG Posts (Mikata)

on:
  schedule:
    - cron: '0 9 * * 0'  # Every Sunday 09:00 UTC = 18:00 JST

jobs:
  generate:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          # Ensure Claude SDK + Gemini SDK available
      
      - name: Generate draft posts
        env:
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python scripts/generate_ig_posts_mikata.py
      
      - name: Verify accuracy (Claude + Gemini dual-check)
        env:
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python scripts/verify_mikata_seido.py --online
      
      - name: Commit & push drafts
        run: |
          git config user.name "Claude Code IG Bot"
          git config user.email "noreply@anthropic.com"
          git add data/subsidies.json data/ig_posts_mikata_draft.json
          git commit -m "auto: IG投稿案生成・検証 $(date +%Y-W%V)" || true
          git push
      
      - name: Notify approvers
        env:
          SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK_IG_APPROVALS }}
        run: |
          # POST to Slack: "5 draft posts ready for Mon approval"
          curl -X POST $SLACK_WEBHOOK \
            -H 'Content-Type: application/json' \
            -d '{"text":"IG投稿案5件 (月曜承認待ち): ...", "link": "https://github.com/..."}'
```

- [ ] **Step 4: Verify workflow syntax**

```bash
# Check YAML syntax (if available)
yamllint .github/workflows/ig-posts-mikata.yml
```

Expected: No syntax errors

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ig-posts-mikata.yml
git commit -m "ci: add ig-posts-mikata workflow (Sun 18:00 JST auto-trigger + dual-verify)"
```

---

### Task 16: Run full Week 3-4 integration test (end-to-end)

**Files:**
- Test: `tests/integration/test_ig_automation_e2e.py` (new)
- Artifact: Integration test report in `docs/integration_test_report.md`

**Interfaces:**
- Consumes: All code from Tasks 1-15 (schema, data, scripts, workflow)
- Produces: End-to-end test results, approval gates verified

- [ ] **Step 1: Write end-to-end test**

```python
def test_full_pipeline_end_to_end():
    """
    1. Load subsidies.json (155 items, 40+5+3 mapped to templates)
    2. Generate 5 draft posts via generate_ig_posts_mikata.py
    3. Verify each post via verify_mikata_seido.py
    4. Check all captions pass humanizer + accuracy-check
    5. Confirm no duplicate posts from recent 5 weeks
    """
    
    # Step 1: Load and validate schema
    subsidies = json.load(open('data/subsidies.json'))
    assert len(subsidies) == 155
    template1_count = len([s for s in subsidies if s.get('ig_template') == 'template1'])
    assert template1_count >= 40, f"Expected ≥40 template1 items, got {template1_count}"
    
    # Step 2: Generate drafts
    drafts = generate_ig_posts(subsidies_json="data/subsidies.json", max_posts=5)
    assert len(drafts) == 5
    
    # Step 3: Verify each draft
    for draft in drafts:
        verify_result = verify_subsidy_dual_check(subsidies[draft['seido_id']])
        assert verify_result['claude_verified'] is not None, \
            f"Draft {draft['seido_id']} failed Claude verification"
    
    # Step 4: Humanizer check
    for draft in drafts:
        assert humanizer_check(draft['caption']) == 'PASS', \
            f"Draft {draft['seido_id']} failed humanizer check"
    
    # Step 5: No duplicates
    historical_ids = load_historical_post_ids()
    for draft in drafts:
        assert draft['seido_id'] not in historical_ids, \
            f"Duplicate post: {draft['seido_id']}"
```

- [ ] **Step 2: Run integration test**

```bash
pytest tests/integration/test_ig_automation_e2e.py -v
```

Expected: PASS (full pipeline works)

- [ ] **Step 3: Commit test**

```bash
git add tests/integration/test_ig_automation_e2e.py
git commit -m "test: add end-to-end integration test for IG automation pipeline"
```

---

### Task 17: Document transition to full automation (Week 5+)

**Files:**
- Create: `docs/ig_automation_runbook.md` (operator manual for Week 5+ automation)
- Modify: `docs/Instagram投稿依頼_運用.md` (add automation workflow notes)

**Interfaces:**
- Consumes: All prior tasks' outputs
- Produces: Operator guide for Mon/Wed/Fri approval gates + automated Sunday generation

- [ ] **Step 1: Write runbook outline**

```markdown
# IG投稿自動化 運用ガイド (Week 5+)

## 自動生成の流れ

毎週日曜 18:00 JST:
1. GitHub Actions自動実行 → `generate_ig_posts_mikata.py`
2. 5投稿案生成 + Claude+Gemini双チェック
3. git push → `data/ig_posts_mikata_draft.json` 更新
4. Slackで承認者に通知

## 月曜 10:00 - Humanizer確認

1. ヒロメさん: Slack通知から `ig_posts_mikata_draft.json` 確認
2. 各投稿の内容チェック (humanizer + accuracy-check already done)
3. 修正が必要な場合: コメント in GitHub
4. 承認: Slack返信 "Monday check: OK"

## 水曜 10:00 - 再確認

修正がある場合のみ再チェック。なければスキップ。

## 金曜 10:00 - 最終承認

小柳さん最終確認 → Slack OK → 投稿スケジュール設定

## インシデント対応

- Verify conflicts (Claude ≠ Gemini): 手動確認 → 原文URL確認
- 期限切れ制度: 自動除外 (ig_exclude: true)
- 新しい制度追加: 定期データ更新のタイミングで ig_priority 付与
```

- [ ] **Step 2: Draft runbook**

Create `docs/ig_automation_runbook.md` with full workflow details, troubleshooting section, and links to prior phases.

- [ ] **Step 3: Commit**

```bash
git add docs/ig_automation_runbook.md
git commit -m "docs: add IG automation runbook for Week 5+ operations"
```

---

## Summary of Dependencies & Phasing

### Week 1-2 Parallel Paths:

**Path A (Data & Schema):**
- Task 1: Extend schema
- Task 2-4: Map templates to subsidies
- Task 8: Populate example data

**Path B (Canva Templates):**
- Task 5-7: Create 3 Canva templates (can run in parallel)

**Path C (Test Posts):**
- Task 9-11: Create 3 test posts (depends on Path A data + Path B templates)

**Week 2 Gate (Mon/Wed/Fri):**
- Task 12: Humanizer + accuracy-check test posts 1-3
- Approval sign-off before proceeding to Task 13+

### Week 3-4 Sequential:

- Task 13: Write `generate_ig_posts_mikata.py` (depends on Task 8 data)
- Task 14: Write `verify_mikata_seido.py` (depends on Task 8 + API keys)
- Task 15: Create workflow YAML (depends on Tasks 13-14)
- Task 16: Integration test (depends on all prior)

### Week 5+:

- Task 17: Runbook + cutover to automation
- Continued Mon/Wed/Fri approval gates

---

## Critical Review Focus Areas (Verification Checklist)

Before each phase handoff, verify:

1. **No unsupported amount assertions in captions** — All numbers must come from `ig_before_amount`, `ig_after_amount`, or templated placeholders. Free-text assertions get humanizer reject.

2. **Dual-AI conflicts logged explicitly** — When Claude and Gemini disagree on deadline/amount, `conflict: true` must appear in `subsidies.json` and be flagged for manual review. Silent defaults are unacceptable.

3. **Deadline ≥30 days enforced** — Any post with `days_to_deadline < 30` must be excluded from draft queue, even if ig_template is assigned. This is non-negotiable per 3-layer rule.

4. **No repeats in rolling 5-week window** — Each weekly draft checks `ig_posts_history.json` for recent posts. A seido_id appearing in current draft must not appear in historical records for the past 5 weeks.

5. **Humanizer assertions verified before approval** — Test posts 1-3 (Task 12) must complete humanizer + accuracy-check gates successfully before proceeding to script development (Task 13). If any test post fails, do not proceed—rework the caption template.

---

## Execution Method

Plan complete and saved to `docs/superpowers/plans/2026-09-28-mikata-ig-automation.md`. 

**Please review the plan. Which execution approach would you prefer?**

- **Subagent-driven** — A fresh subagent implements each task sequentially with independent review before the next one starts, then whole-branch review at the end. Most thorough; costs a fresh context per task.
- **Native** — I implement every task myself in this session, then one fresh reviewer checks the whole branch at the end. Fastest; runs well with plan-guided development.

**For this plan I recommend Subagent-driven because:**
- 17 tasks with interdependencies (Tasks 1-8 must complete before approval gate in Task 12; Phase 2 scripts depend on approved data)
- Test gate (Task 12 humanizer approval) blocks progression to Phase 3, requiring independent verification
- Integration test (Task 16) needs fresh review to validate end-to-end correctness before Week 5 automation
- Subagent-per-task parallelization on Week 1-2 paths (A/B/C) saves wall-clock time

**Does the plan capture what you want, and which approach should we use?**