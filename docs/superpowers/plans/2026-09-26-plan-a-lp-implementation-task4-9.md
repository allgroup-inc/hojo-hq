# Plan A LP サイト実装計画 — Task 4-9

> **Status:** TASK BRIEFS FOR EXECUTION
> **Baseline:** After Task 3 (CSS complete, bc601d5). Dependencies: index.html + styles.css already wired.
> **Final review finding:** Blocker on Task 4 start: scripts.js missing, all CTAs non-functional. Forms/GA design incomplete.

---

## Task 4: JavaScript フォーム連携・GA4 計測

**Objective:** All 3 CTAs working end-to-end: LINE deep link, email resource form, meeting signup form. GA4 events recorded for each CTA stage.

**Spec Reference:** 
- HTML skeleton: `index.html` (sections 1-9, modals, button IDs)
- Modal hooks: `#cta-line`, `#cta-resource`, `#cta-meeting` (buttons); `#modal-resource`, `#modal-meeting` (modals); `#form-resource`, `#form-meeting` (forms)

**Key Decisions (blocking for execution):**
1. **LINE CTA:** Deep link to LINE OA or URL? (Spec says "LINE 公式友だち追加ボタン". Recommend: `line://ti/p/@<channel-id>` or go-link channel. Requires LINE_CHANNEL_ID from小柳さん or OA config.)
2. **Resource request endpoint:** Formspree form ID or custom endpoint? (Spec: "Formspree でメール送信". Requires FORMSPREE_ID secret.)
3. **Meeting signup endpoint:** Google Form URL or Webhook? (Spec: "Google Form または カスタムフォーム". Recommend: POST to `/api/meeting-signup` or Google Form pre-fill URL.)
4. **GA4 Measurement ID:** Not in HTML `<meta>` tags yet. Requires GA_MEASUREMENT_ID secret.
5. **Event naming:** Create new names (do NOT reuse `line_redirect`). Recommend:
   - `plan_a_cta_line_click` (button)
   - `plan_a_cta_resource_click` → `plan_a_resource_form_submit` 
   - `plan_a_cta_meeting_click` → `plan_a_meeting_form_submit`
   - Include `url_path: "/go/plan-a"` in event params

**Files to create/modify:**
- Create: `site/go/plan-a/scripts.js` (form handlers, GA events)
- Modify: `site/go/plan-a/index.html` (add GA gtag script, fix scripts.js src)

**Deliverables:**
- All 4 CTA buttons clickable and route to correct handlers
- Modal open/close on button click
- Email form POSTs to endpoint, returns success/error message
- Meeting form POSTs to endpoint, returns success/error message
- GA4 events fire for: cta click, form submit, form success
- Error handling (network, validation) shows user-facing message

**Testing requirements:**
- Browser DevTools: 4 buttons clickable, modals open/close
- Network tab: form POST succeeds (200 or expected status)
- GA4 Real-time: events appear within 5 seconds of action
- Mobile: buttons/forms functional at 390px width

---

## Task 5: 画像最適化・Lazy Loading 実装

**Objective:** WebP delivery, lazy loading, and fallback ensure fast load and SEO compliance.

**Current state:** 
- Assets exist in manifest (JPG + WebP pairs)
- HTML uses plain `<img src="jpg">` (no lazy load, no WebP)

**Changes:**
- Wrap images in `<picture>` with WebP source + JPG fallback
- Add `loading="lazy"` to all below-fold images (producers, products, cases, sections 3-9)
- Add `width`, `height` attributes (from manifest.json) to prevent layout shift
- Test: Lighthouse Performance > 80

**Files:**
- Modify: `site/go/plan-a/index.html` (img tags → picture tags)

**Example:**
```html
<picture>
  <source srcset="assets/images/hero-bg.webp" type="image/webp">
  <img src="assets/images/hero-bg.jpg" alt="..." width="1920" height="1080">
</picture>

<!-- below-fold images -->
<picture>
  <source srcset="assets/images/producer-1.webp" type="image/webp">
  <img src="assets/images/producer-1.jpg" alt="..." width="400" height="400" loading="lazy">
</picture>
```

---

## Task 6: アクセシビリティ検証 (WCAG 2.1 AA)

**Objective:** Verify WCAG 2.1 AA compliance (color contrast, keyboard nav, screen reader).

**Checks:**
- Contrast ratios: all text ≥ 4.5:1 (normal) or 3:1 (large). Use axe DevTools or WebAIM.
- Keyboard navigation: all CTAs/forms reachable via Tab, Enter submits forms
- Screen reader: all images have `alt`, form labels linked via `<label for="">`, modal has `role="dialog"` and `aria-modal="true"`
- Form validation: error messages announce via `aria-live="polite"`
- Heading hierarchy: h1 only in hero, h2 for sections, no skips
- Landmark regions: `<main>`, `<nav>`, `<footer>` (if present)

**Tools:** 
- axe DevTools Chrome extension
- WAVE browser extension
- Lighthouse (Accessibility audit)
- NVDA screen reader (Windows) or VoiceOver (Mac)

**Report:** Document any failures (WCAG criterion violated), remediation plan.

---

## Task 7: Lighthouse Performance 検証

**Objective:** Baseline Lighthouse scores before publishing (Performance ≥ 80, Accessibility ≥ 95).

**Run:** 
```bash
# Local (file://) simulation
npx lighthouse https://localhost:8000/site/go/plan-a/index.html --chrome-flags="--headless" --output=json
# or
open DevTools → Lighthouse → Analyze page load

# Production URL (after deploy)
npx lighthouse https://allgroup-inc.github.io/hojo-hq/go/plan-a/
```

**Metrics to track:**
- Largest Contentful Paint (LCP): ≤ 2.5s (aim < 1.5s)
- First Input Delay (FID): ≤ 100ms
- Cumulative Layout Shift (CLS): ≤ 0.1
- Total Blocking Time (TBT): ≤ 300ms

**Optimizations (if needed):**
- Defer non-critical JS (GA gtag can load async)
- Compress images further (WebP already 80 quality)
- Remove unused CSS (if any bloat detected)
- Add `preconnect` to GA domain

**Parked from earlier:** Dark-mode CSS and Lighthouse not run together. Performance rule is "headings-only", so test with h1-h3 only (no `text-wrap:balance` on body).

---

## Task 8: 全デバイス・ブラウザ検証 (QA)

**Objective:** End-to-end testing: all sections render, all CTAs functional, no errors.

**Test Matrix:**

| Device | OS | Browser | Version | Viewport | Action |
|--------|----|---------|---------|----|--------|
| Desktop | Windows 11 | Chrome | latest | 1280×800 | Click all CTAs, submit forms, check GA |
| Tablet | iPadOS | Safari | latest | 810×1080 | Same |
| Mobile | iOS 17 | Safari | latest | 390×844 | Same |
| Mobile | Android 14 | Chrome | latest | 390×844 | Same |

**Checklist (for each device):**
- [ ] Page loads without console errors
- [ ] Hero section visible and button clickable
- [ ] All 9 sections scroll smoothly, images load
- [ ] CTA buttons respond (color change, modal opens)
- [ ] Modal forms display correctly, text inputs focusable
- [ ] Form submit returns success/error message
- [ ] No horizontal scroll at any width
- [ ] GA events fire (check Network tab for `/collect` requests)

**Tools:**
- BrowserStack or Chrome DevTools remote debugging
- ngrok or local server for testing

---

## Task 9: 最終 QA・デプロイ準備

**Objective:** Pre-launch checklist, content final review, deploy sign-off.

**Pre-launch Checklist:**

- [ ] All content fact-checked by 守り部 (rule 1: sources verified)
- [ ] 小柳さん sign-off: facts, badges, CV forms, 議事 decision record in place
- [ ] All placeholder images replaced with real photos OR marked "※イメージです"
- [ ] og:url, og:image corrected to final domain
- [ ] `support@glow-plan-a.com` email address verified (or replaced with real contact)
- [ ] LINE channel ID and Formspree ID injected via GitHub Secrets (not in code)
- [ ] GA Measurement ID set
- [ ] Session dates (10/5, 10/12) replaced with dynamic values or next scheduled dates
- [ ] Privacy policy link added (required for form data collection)
- [ ] 議事 decision record filed: `docs/議事_YYYYMMDD_Plan A LP publish decision.md`

**Deploy Steps:**

1. **Remove `/go/plan-a` from GitHub Pages exclusion** in `.github/workflows/update.yml`
   - Delete line: `rm -rf /tmp/pages-deploy/go/plan-a`
   - This allows Plan A to go public on next auto-deploy or manual trigger

2. **Merge to main:**
   ```bash
   git checkout main
   git pull origin main
   git merge --no-ff claude/cool-bell-ugyalg
   git push origin main
   ```

3. **Trigger deploy workflow:** GitHub Actions auto-runs on push, or manual dispatch

4. **Verify live:** Open `https://allgroup-inc.github.io/hojo-hq/go/plan-a/`, test CTAs, check GA events

5. **Post-launch monitoring:**
   - Monitor 404s, JS errors (Sentry integration if set up)
   - Check GA daily: CTA click rate, form submission rate
   - Update progress ledger with launch date and KPI baseline

---

## Execution Order

- **Task 4 is critical path.** All forms/GA depend on it. No Task 5-9 testing can proceed without Task 4 complete.
- **Task 5** can run in parallel with Task 4 (image optimization doesn't block forms).
- **Tasks 6-8** run in parallel (testing dimensions).
- **Task 9** is final gate (merge blocker until sign-off).

---

## Parked Issues from Final Review (decision required before Task 4 start)

| Issue | Status | Decision |
|-------|--------|----------|
| Hero text in CSS `::before` | Fix before deploy | Move to HTML `<p>` with aria-hidden. Task 4 or earlier. |
| Missing scripts.js | Blocker | Task 4 creates it. |
| Wrong `/go/` folder location | Architectural | Recommend move to `/site/plan-a/` (blocks SEO, triggers moradou). Needs 小柳さん call. |
| Dark-mode colors | Waived | Brand colors intact. Can approve separately. |
| Calligraphy font | Dropped | Spec says Meiryo/Noto; performance rule applies. Remove from CSS. |
| Session dates hard-coded | Task 4/9 | Make dynamic in JS or configure in secrets. |
| LINE channel ID/Formspree ID/GA ID missing | Task 4 | Requires secret configuration. |
| Facts & badges unapproved | Blocker for Task 9 | Not Task 4 work; policy gate before publish. |

---

## Notes for Implementer

- **Never block on secrets.** Use placeholder IDs in HTML (e.g., `GA_MEASUREMENT_ID = "G-XXXXXXXXXX"` as example), inject real values at deploy via GitHub Secrets.
- **Test locally first.** Start a local server (`python3 -m http.server 8000`), test all CTAs in browser DevTools before pushing.
- **Form handling library:** No jQuery. Use vanilla JS (Fetch API for POST, form validation with HTML5 `required` + JS custom messages).
- **Error handling:** Catch network errors, timeouts, validation errors. Show user-friendly message in modal's `#form-*-message` span.
- **GA debug mode:** Add `gtag('config', 'GA_ID', { debug_mode: true })` during testing, remove before merge.
