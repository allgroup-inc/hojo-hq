# Instagram Test Posts Approval Log

**Date:** 2026-09-28 → 2026-10-04
**Test Posts:** 3 (Template1, Template2, Template3)
**Overall result (Task 12 re-run, 2026-09-29, after revision commit ba09b9733):** READY FOR SIGN-OFF as reviewed drafts. All three pass the humanizer check. Post 1 and Post 3 pass accuracy; Post 2 is 要確認 by design (deadline and amount unpublished in the DB), so it cannot be posted until the official page is checked. History of the first run (2026-09-28) is kept below each post.

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

**Re-run (2026-09-29):** same method. `check_humanizer.check_one()` on each `## Instagram Caption` section returned `[]` for all three.
`check_batch()` returned only the repeated template labels 「【1行フック】」「【ハッシュタグ】」 (false positive, as before).
Accuracy was re-checked against `data/subsidies.json` for ids a0WJ200000CDYDCMA5, okinawa_ric-3, a0WJ200000CDNDnMAP. 出典ページ were still NOT re-fetched online.
The revised images/HTML were also checked (Post 3 p1 PNG, Post 2 PNG, Post 1 p2/p4 HTML): they match the revised captions.

## Test Post 1: 【農林水産省】中山間地域所得確保推進事業 (Template1)

**Subsidy ID:** a0WJ200000CDYDCMA5  **Captions File:** `test_post_1_caption.md`  **Image:** `test_post_1_p1.html` to `p4.html`

### Re-run result (2026-09-29)
- **Humanizer:** PASS. No findings; 絵文字 (✓) now 3, below the threshold of 6 (previous Low note resolved).
- **Accuracy:** PASS (with 要確認 labels in place)
  - 上限500万円 = DB max_amount 5,000,000. OK.
  - Deadline 2026-12-01 = 63 days from 2026-09-29; satisfies the 30+ day SNS rule.
  - 「補助率最大3/4（要確認）」: not in DB (subsidy_rate null), now marked 要確認 in caption and in p4 HTML. Acceptable under 絶対ルール1.
  - Hook and p2 example (400万円→100万円, 実質負担約25%) are labeled 試算例 in caption, p2 and metadata.
  - target_area 全国: caption does not claim Okinawa-only eligibility. OK.
- **Non-blocking notes:** (a) the 400万→100万 example implies a 3/4 rate, which is itself unverified; it is labeled 試算例 but confirm the rate on the jGrants page before posting. (b) Hook wording 「農業経営の課題、※試算例: …」 reads a little clumsy; optional polish.
- **Ready for sign-off:** YES

<details><summary>First run (2026-09-28)</summary>

Humanizer PASS (Low: 絵文字6個). Accuracy CONDITIONAL: 補助率3/4 not in DB; hook example unlabeled; target_area 全国. Ready: NO.
</details>

---

## Test Post 2: 事業承継推進事業（沖縄県産業振興公社） (Template2)

**Subsidy ID:** okinawa_ric-3  **Captions File:** `test_post_2_caption.md`  **Image:** `test_post_2.png`

### Re-run result (2026-09-29)
- **Humanizer:** PASS. No findings.
- **Accuracy:** 要確認 (acceptable for sign-off, NOT postable)
  - Program now exists in DB: name 事業承継推進事業, target_area 沖縄県, source_url https://okinawa-ric.jp/service/post-3.html. Caption program name and issuer match.
  - DB max_amount null, deadline 「要確認」, status 要確認. Caption and image no longer state any amount, deadline, cost or phone number; all are shown as 要確認. Earlier unsourced claims (100万円, 相談無料, 電話番号) are removed.
  - The 3-layer deadline rule cannot be evaluated (no deadline). Metadata says posting is blocked until the official page is checked.
- **Blockers before posting (not before sign-off):** (1) confirm eligibility, cost and deadline on the official page and update the DB; (2) `/go/` link is not yet implemented (Task 13); the caption says the link is in the profile.
- **Ready for sign-off:** YES as a 要確認 format sample. **Ready for posting:** NO.

<details><summary>First run (2026-09-28)</summary>

Humanizer PASS. Accuracy FAIL: no DB record, unsourced claims, placeholder phone/lin.ee. Ready: NO.
</details>

---

## Test Post 3: Scope3排出量削減 省CO2設備投資促進事業 (Template3)

**Subsidy ID:** a0WJ200000CDNDnMAP  **Captions File:** `test_post_3_caption.md`  **Image:** `ig_test_3_p1.png` to `ig_test_3_p6.png`

### Re-run result (2026-09-29)
- **Humanizer:** PASS. No findings. The pressure line 「この機会を逃さないでください」 is gone.
- **Accuracy:** PASS
  - Program name in caption/hashtags is now the Scope3 program; matches DB 「令和８年度_Scope3排出量削減のための企業間連携による省CO2設備投資促進事業」 (shortened form).
  - 最大15億円 = DB max_amount 1,500,000,000. Caption, title and metadata are now consistent (the 1.5億 / 150億 mismatches are fixed). Image ig_test_3_p1.png shows 15億円.
  - Deadline 2026-11-13 = 45 days from 2026-09-29; satisfies the 30+ day rule.
  - 「採択企業の声」 removed; caption says it is a general image, not a case study. 準備期間約6ヶ月 and the Before/After are labeled 試算例.
- **Non-blocking notes:** (a) image p1 headline says 「事業転換を検討していますか?」 while the caption title says 「設備投資を検討していますか?」; the program supports equipment investment, so align the wording. (b) Metadata slide 6 still holds `https://lin.ee/...` as a placeholder QR URL; replace with the `/go/` link (Task 13) and do not ship lin.ee directly.
- **Ready for sign-off:** YES

<details><summary>First run (2026-09-28)</summary>

Humanizer PASS. Accuracy FAIL: wrong program name; amount off by 10x; 採択企業の声 unsupported. Ready: NO.
</details>

---

## Summary

| Post | Template | Humanizer | Accuracy | Sign-off | Postable now |
|---|---|---|---|---|---|
| Post 1 | Template1 | PASS | PASS (補助率 marked 要確認) | YES | YES, after confirming 補助率 on jGrants |
| Post 2 | Template2 | PASS | 要確認 (deadline/amount unpublished) | YES (format sample) | NO |
| Post 3 | Template3 | PASS | PASS | YES | YES, after replacing placeholder QR URL |

Batch check note: 「【1行フック】」「【ハッシュタグ】」 repeated across 3 posts is a template label, not a prose repetition (false positive).

## Final Approval (小柳さん Sign-Off)

- **Reviewer:** 小柳さん
- **Decision:** PENDING (recommend APPROVE Posts 1 and 3 with the notes above; APPROVE Post 2 only as a 要確認 sample)
- **Date:** YYYY-MM-DD (planned: 2026-10-04)
- **Notes:**

---
