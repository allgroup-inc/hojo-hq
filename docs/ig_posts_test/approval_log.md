# Instagram Test Posts Approval Log

**Date:** 2026-09-28 → 2026-10-04
**Test Posts:** 3 (Template1, Template2, Template3)
**Overall result:** NOT READY. Post 1 is conditional, Posts 2 and 3 FAIL the accuracy check (絶対ルール1). Do not present for sign-off until fixed.

## How the checks were actually run (deviation from the brief)

The commands in the brief do not work as written. Both scripts take no file argument
(`unrecognized arguments`, exit 2).

- `scripts/check_humanizer.py` scans only `posts/launch/*.md` and `posts/carousel/caption.md`.
  Substitute: imported its `check_one()` / `check_batch()` and ran them on the
  `## Instagram Caption` section of each test caption (the built-in extractor looks for `## キャプション`, which these files lack).
- `scripts/check_ig_neta.py --online` validates only `data/fukugiiro/ig_neta.json` (もらいわすれ堂 pipeline).
  Run as-is: NG 0 / WARN 0 / 取得できず 0, but it does not look at these captions, so it proves nothing about them.
  Substitute: manual cross-check of each caption and metadata against `data/subsidies.json` (jGrants-derived, fetched 2026-09-28 21:41).
- The 出典ページ (jGrants) were NOT re-fetched online in this run. The comparison is against the DB values only.

## Test Post 1: 【農林水産省】中山間地域所得確保推進事業 (Template1)

**Subsidy ID:** a0WJ200000CDYDCMA5
**Created:** 2026-09-28
**Captions File:** `test_post_1_caption.md`
**Image:** `test_post_1_p1.html` through `test_post_1_p4.html` (4-page carousel)

### Humanizer Check
- **Status:** PASS (with note)
- **Severity:** Low
- **Issues Found:** 絵文字6個 (✓ x6) hits the script's "excessive" threshold (6+). Suggest merging the two ✓ lists or using 「・」 for one.
- **Run Date:** 2026-09-28
- **Command:** `check_humanizer.check_one()` on the caption section (see above)

### Accuracy Check
- **Status:** CONDITIONAL (amount and deadline match; two items unverified)
- **Verified vs DB:** max_amount 5,000,000 = 「500万円」 OK. deadline 2026-12-01 = 64 days remaining, satisfies the 30+ day SNS rule.
- **Issues Found:**
  1. 「補助率最大3/4」 is not in `subsidies.json`. Verify on the source page or change to 「要確認」.
  2. Hook 「400万円の投資が補助金で実質100万円に」 is an illustrative example, not sourced. Add 「例」 or 「※試算例」 so it is not read as a guaranteed outcome.
  3. DB target_area is 全国 (not Okinawa-specific); check the caption/hashtags do not imply Okinawa-only eligibility.
- **Source URLs Checked (DB record only):** https://www.jgrants-portal.go.jp/subsidy/a0WJ200000CDYDCMA5
- **Run Date:** 2026-09-28

### Approval
- **Humanizer Approval:** PASS
- **Accuracy Approval:** PENDING (items 1-2)
- **Ready for Posting:** NO (after fixes 1-2: YES)

---

## Test Post 2: 小規模事業者等デジタル化支援事業 (Template2)

**Subsidy ID:** okinawa_ric_dx_support (not a DB id)
**Captions File:** `test_post_2_caption.md`  **Image:** `test_post_2.png`

### Humanizer Check
- **Status:** PASS
- **Severity:** None
- **Issues Found:** none (絵文字3個)
- **Run Date:** 2026-09-28

### Accuracy Check
- **Status:** FAIL (unverifiable)
- **Issues Found:**
  1. No record with this ID or name exists in `data/subsidies.json`. No 原文URL, no deadline, no amount, so the 3-layer deadline rule cannot be applied at all.
  2. Claims 「沖縄県が用意」「相談・診断が無料」「沖縄県産業振興公社の担当者から連絡」 have no source recorded.
  3. Hook 「100万円は必要？」 has no basis.
  4. Metadata `contact_phone` is the placeholder `0570-XXXXXX` and QR url is `https://lin.ee/...`; must not ship. Note: lin.ee direct links are also restricted by 出荷ゲート/`/go/` rules.
  5. Caption ends 「詳細は公式ページで」 but gives no page.
- **Remediation:** Find the official page, add the entry to the DB with source_url and deadline, then re-check. Otherwise publish as 「要確認」 or drop this post.
- **Run Date:** 2026-09-28

### Approval
- **Humanizer Approval:** PASS
- **Accuracy Approval:** FAIL
- **Ready for Posting:** NO

---

## Test Post 3: 事業再構築補助金GX・DX型 (Template3)

**Subsidy ID:** a0WJ200000CDNDnMAP
**Captions File:** `test_post_3_caption.md`  **Image:** `ig_test_3_p1.png` to `ig_test_3_p6.png`

### Humanizer Check
- **Status:** PASS
- **Severity:** Low
- **Issues Found:** none from the script. Manual note: 「この機会を逃さないでください」 is pressure copy inconsistent with the site tone; consider removing.
- **Run Date:** 2026-09-28

### Accuracy Check
- **Status:** FAIL (two blocking errors)
- **Issues Found:**
  1. **Program name mismatch.** DB record for this ID is 「令和８年度_Scope3排出量削減のための企業間連携による省CO2設備投資促進事業」 (issuer 脱炭素成長型経済構造移行推進対策費補助金). The caption, title and hashtags call it 「事業再構築補助金 GX・DX型」, which is a different program.
  2. **Amount off by 10x.** DB max_amount = 1,500,000,000 = **15億円**. Caption/hook say 「最大1.5億円」. Metadata says 15,000,000,000 (150億) and caption Metadata says 150億. Three different values; only 15億 matches the DB.
  3. 「採択企業の声」 is promised but no such content exists in the carousel. 「準備期間は約6ヶ月」 and the 40%/30%/50% benefits are unsourced examples; mark as 例.
  4. target_area is 全国 (deadline 2026-11-13, 46 days, passes the 30+ day rule).
- **Source URL (DB):** https://www.jgrants-portal.go.jp/subsidy/a0WJ200000CDNDnMAP
- **Remediation:** Rename to the real program, correct amount to 最大15億円 (after confirming on the source page), fix metadata, drop or replace 「採択企業の声」, regenerate images if they show 1.5億 or the old name.
- **Run Date:** 2026-09-28

### Approval
- **Humanizer Approval:** PASS
- **Accuracy Approval:** FAIL
- **Ready for Posting:** NO

---

## Summary

| Post | Template | Humanizer | Accuracy | Ready |
|---|---|---|---|---|
| Post 1 | Template1 | PASS (Low) | CONDITIONAL | NO (after 2 fixes: YES) |
| Post 2 | Template2 | PASS | FAIL | NO |
| Post 3 | Template3 | PASS | FAIL | NO |

Batch check note: 「【1行フック】」「【ハッシュタグ】」 repeated across 3 posts is a template label, not a prose repetition (false positive).

## Final Approval (小柳さん Sign-Off)

- **Reviewer:** 小柳さん
- **Decision:** PENDING (recommend REJECT for Posts 2 and 3 until fixed)
- **Date:** YYYY-MM-DD
- **Notes:**

---
