# Plan A LP 判定返却時・アクション・マニュアル

**日時:** 2026-09-27  
**対象:** 小柳さんからの判定が返ってきた時点で実行

---

## 判定返却フロー

### Step 1: 判定チェックリストを確認（3分）
`docs/Plan A LP判定チェックリスト_20260927.md` の「総合判定結果」セクションを確認

- Check 1（事実検証）: ✅ / 📝 / ❌
- Check 2（バッジ承認）: ✅ / 📝 / ❌
- Check 3（CV方針）: ✅ / ⚠️ / ❌
- Check 4（議事決裁）: ✅ / ⏳

---

### Step 2: HTML 修正が必要か判定（5分）

**修正不要な場合 (✅✅✅)**
```
→ Step 3 へスキップ
```

**修正が必要な場合 (📝 or ❌)**

| 判定 | 対象 | アクション |
|------|------|----------|
| Check 1-1: 削除 | "30年の公庫経験" | `index.html:248-249` から2行削除 |
| Check 1-2: 削除 | "200社支援" | `index.html:255` の `<li>` タグ削除 |
| Check 1-3: 削除 | "100億円融資" | `index.html:256` の `<li>` タグ削除 |
| Check 1-4: 削除 | "年間115万円" | `index.html:276-277` を削除 |
| Check 1-5: 削除 | "97%利益" | `index.html:298` の内容を修正 |
| Check 2-1: 削除 | 沖縄県バッジ | 信頼バッジセクションから削除 |
| Check 2-2: 削除 | Alibaba バッジ | 信頼バッジセクションから削除 |
| Check 2-3: 削除 | Trade Assurance | 信頼バッジセクションから削除 |
| Check 3: 削除 | メール/電話form | `#modal-resource`, `#modal-meeting` 削除 |

---

### Step 3: HTML 修正を実行（10-20分、必要な場合のみ）

**修正テンプレート例：**

#### A. 削除系（事実検証 Check 1-1/1-2 など）
```bash
# 修正対象をリスト化
git diff origin/main site/go/plan-a/index.html | head -20

# 修正を実行（Edit tool または Bash）
# 不要な行/セクションを削除してコミット
git add site/go/plan-a/index.html
git commit -m "fix: remove unverified claims per content approval (Check 1-X)"
git push origin claude/cool-bell-ugyalg
```

#### B. フォーム削除系（Check 3: LINE-only 堅持）
```bash
# modal-resource, modal-meeting のセクション全削除
# CTA ボタンの対応箇所も修正（LINE のみ残す）
git add site/go/plan-a/index.html
git commit -m "fix: remove email/phone forms per LINE-only policy (Check 3)"
git push origin claude/cool-bell-ugyalg
```

**修正完了後:**
```
✅ HTML 修正: 完了
→ Step 4 へ進む
```

---

### Step 4: Privacy Policy 追加（必要な場合）

**判定内容確認:**
- Check 3: ⚠️ 条件付き認定 → email/phone form を 条件付きで認める場合

**実施内容:**
```
privacy policy を site/go/plan-a/privacy-policy.html に作成
index.html の footer にリンク追加
```

**修正テンプレート:**
```html
<!-- index.html の footer に追加 -->
<a href="privacy-policy.html" target="_blank">プライバシーポリシー</a>
```

**修正完了後:**
```
✅ Privacy Policy: 完了（または不要）
→ Step 5 へ進む
```

---

### Step 5: Task 4 Implementer Dispatch（判定返却 + 60分以内）

**前提条件確認:**
- ✅ HTML 修正完了（必要な場合）
- ✅ Privacy Policy 完了（必要な場合）
- ⏳ GitHub Secrets 設定確認: LINE_CHANNEL_ID, FORMSPREE_ID, GA_MEASUREMENT_ID

**Dispatch 内容:**

```markdown
---
DISPATCH: Task 4 - JavaScript フォーム連携・GA4 計測

## Context
Plan A LP サイト (site/go/plan-a/) の3つの CTA を動作させる JavaScript 実装。
- 判定内容に基づいて HTML が修正済み（該当セクション削除または修正）
- 次のステップ: scripts.js 作成 + GA4 ワイアリング

## Brief
Read: docs/superpowers/plans/2026-09-26-plan-a-lp-implementation-task4-9.md (Task 4 セクション)

## Key Dependencies
- HTML button IDs: #cta-line, #cta-resource, #cta-meeting
- Modal IDs: #modal-resource, #modal-meeting
- Form IDs: #form-resource, #form-meeting
- Secrets (GitHub): LINE_CHANNEL_ID, FORMSPREE_ID, GA_MEASUREMENT_ID

## Event Naming (重要: line_redirect を再利用しない)
- plan_a_cta_line_click
- plan_a_resource_form_submit
- plan_a_meeting_form_submit

## Deliverable
- site/go/plan-a/scripts.js 完成
- index.html に GA gtag script 追加
- 3つの CTA すべて動作確認
- GA4 Real-time で イベント発火確認

---
```

**Dispatch 実行:**
```bash
# Subagent-driven-development のフロー開始
# Task 4 implementer subagent (model: sonnet) に dispatch
```

---

### Step 6: Task 4 完了待機・Task 5-9 並行準備（～2時間）

**Task 4 implementer からの報告を待機:**
- Report file: `.superpowers/sdd/.../task-4-report.md`
- 期待: scripts.js 完成、GA4 確認完了

**その間に実行（Task 5-9 implementers の並行準備）:**
```bash
# Task 5 implementer (画像最適化)
# Task 6 implementer (a11y)
# Task 7 implementer (Lighthouse)
# Task 8 implementer (QA)
# を同時に dispatch

# Tasks 5-8 は独立しているので並行実行可
```

---

### Step 7: Task 4 Review & Approve（30分）

**Task 4 reviewer からの review 結果を確認:**
- Spec ✅ + Quality approved → 次へ
- Findings → fix dispatch → re-review

---

### Step 8: Tasks 5-9 並行実行・最終 review（～4時間）

- Task 5: 画像最適化（picture タグ、lazy loading）
- Task 6: a11y 検証（WCAG 2.1 AA）
- Task 7: Lighthouse 測定（Performance ≥ 80）
- Task 8: QA テスト（全device）

Tasks 5-8 の結果が揃い次第、Task 9 へ→

---

### Step 9: Final Deploy Gate & Merge（1時間）

**Task 9: 最終デプロイ準備**

```
前提: Tasks 1-8 すべて APPROVED

実施:
1. Content sign-off 確認
2. Pre-launch checklist 確認
3. update.yml から /go/plan-a 除外を削除
4. Main branch へ merge
5. GitHub Pages auto-deploy 開始
6. Smoke test: allgroup-inc.github.io/hojo-hq/go/plan-a/ で確認
```

---

## タイムライン目安

| Phase | 時間 | 内容 |
|-------|------|------|
| 判定受け取り | 5分 | チェックリスト確認 |
| HTML 修正 | 10-20分 | 必要な削除/修正を実行 |
| Task 4 dispatch | 30分 | Implementer subagent 起動 |
| Task 4 実装・Review | 60-90分 | scripts.js 完成・承認 |
| Tasks 5-8 並行実行 | 120-180分 | 画像・a11y・Lighthouse・QA |
| Task 9・Merge | 60分 | 最終チェック・deploy |
| **合計** | **~5時間** | 判定 → 本番公開 |

---

## トラブルシューティング

### HTML 修正で迷った場合
- 判定チェックリストの「HTML位置」を参照
- 該当セクションの全文を git diff で確認
- 不確かな場合は削除ではなく「要確認」コメント付きで進める

### Task 4 で Secrets 不足の場合
- LINE_CHANNEL_ID: 小柳さんに確認（LINE OA アカウント設定）
- FORMSPREE_ID: Formspree アカウントで新規フォーム作成
- GA_MEASUREMENT_ID: Google Analytics 4 プロパティID

### Task 5-8 の review で blocking finding が出た場合
- Fix dispatch → re-review のループ（最大5ラウンド）
- 3ラウンド以上で stuck → より capable model で re-dispatch

---

## 完了チェックリスト

- [ ] 判定チェックリスト確認
- [ ] HTML 修正（必要な場合）
- [ ] Privacy Policy（必要な場合）
- [ ] Task 4 Implementer dispatch
- [ ] Task 4 Review APPROVED
- [ ] Tasks 5-8 並行実行
- [ ] Task 9 最終チェック
- [ ] Main へ merge
- [ ] GitHub Pages 自動 deploy
- [ ] 本番サイト確認 ✅

**Status: 待機中** → **判定返却で即実行**

