# 議事：Plan A LP 最終review及びTask 4-9準備完了

**日時:** 2026-09-27（自動review結果に基づく記録）
**対象:** Plan A LP サイト実装（Task 1-3 complete, final review verdict）
**参加者:** Claude Code (implementer/reviewer dispatch) → Final whole-branch reviewer

---

## 最終review結果概要

**Verdict: ✅ BLOCKED for merge — 技術的には完成、**
**デプロイは政策ゲート（事実検証・承認・議事）を通してから。**

### コード品質: ✅ PASS
- Task 1（assets）✅ APPROVED
- Task 2（HTML）✅ APPROVED
- Task 3（CSS）✅ APPROVED
- 技術的な一貫性・responsive性・contrast検証すべてOK
- ただし**scripts.js欠落**のためCTA全4個非稼働（Task 4で作成）

### デプロイ安全性: ⚠️ BLOCKED

GitHub Pagesへの自動deploy (`update.yml` "Prepare Pages artifact"ステップ)が、
`.github/workflows/update.yml`で`/go/plan-a`を除外していないため、
マージ→デプロイ→**未検証のクレーム・不正確なバッジをパブリックURL下で公開される危険**。

**対応完了:** update.yml行145に`rm -rf /tmp/pages-deploy/go/plan-a`を追加
→ 承認までデプロイから除外、safe side が確保された。

---

## ブロッキング項目（小柳さん判定待ち）

### ❶ 事実検証（CLAUDE.md rule 1）

| 記述 | HTML位置 | 状態 | 必須判定 |
|-----|--------|------|--------|
| 30年の公庫経験 | section-4:248 | 未検証（個人の経歴か会社か不明） | ✋ 明確化必須 |
| 200社支援 | section-4:255 | 未検証 | ✋ 出所確認 |
| 100億円融資実績 | section-4:256 | 未検証 | ✋ 出所確認 |
| 年間115万円コスト | section-5:276 | 未検証 | ✋ 出所確認 |
| 97% 利益率 | section-5:298 | 未検証 | ✋ 出所確認 |

**決定:** 出所付きで事実と確認するか、削除/修正するか。

### ❷ バッジ・提携承認（CLAUDE.md rule 5）

| バッジ | HTML位置 | 問題 | 必須判定 |
|-------|--------|------|--------|
| 沖縄県支援事業 | section-4 trust badge | 県の公式推奨と誤解される。根拠なし | ✋ 根拠取得 or 削除 |
| Alibaba公式パートナー | logos/alibaba-partner.png | 商標・提携未確認 | ✋ 確認 or 削除 |
| Trade Assurance認定 | logos/trade-assurance.png | 認定根拠未確認 | ✋ 確認 or 削除 |

**決定:** 各バッジの法的根拠を取得または削除。

### ❸ CV方針確認（CLAUDE.md rule 4）

**現状:** HTML内に2つのCV導線が存在
- `#modal-resource` : メール (資料請求)
- `#modal-meeting` : 説明会申し込み (電話・date入力)

**CLAUDE.md rule 4:** 「CVはLINE登録の1点のみ」が基本。
メール・電話form追加は小柳さん承認が必須。

**決定:** 
- [ ] LINE-only方針を維持するか、email/phone CVを認めるか
- [ ] 認める場合、フォーム送信後のデータ取り扱いをGlow-maへどう連携するか

### ❹ 議事・決裁記録

**要件:** 公開 + 個人情報収集 = 不可逆な変更。三名体制（スイシン/ウタガイ/ベッカイ）の議事が必須。

**現状:** この議事は本ドキュメントが初。正式な三名体制議事を別途作成し、反対意見があれば記録。

**決定:** 小柳さんの判定を受けたうえで、正式議事を作成。

---

## 技術的な警告項目（waivable か fixed）

### 後回しでOKなもの
- **Dark-mode colors:** Brand colors（朱・黄・GLOW orange）は保持。紺/灰のみ補色。ブランド毀損なし → 承認は任意
- **Calligraphy font:** Spec指定がMeiryo/Noto。brushfontは非必須 → 削除で OK
- **Lighthouse:** Performance測定は公開前に実施。マージblockerではない

### 後回しでは不可（Task 4以前に fix 必須）
- **Hero text in CSS `::before`:** SEO/a11y問題。HTMLの`<p aria-hidden="false">`に移動 → 簡単 → Task 4 or before
- **scripts.js missing:** Task 4で新規作成（すべてのCTA生死に関わる）

---

## Task 4-9 準備完了報告

**ファイル:** `docs/superpowers/plans/2026-09-26-plan-a-lp-implementation-task4-9.md`

### Task 4（critical path）

**依存:** LINE_CHANNEL_ID, FORMSPREE_ID, GA_MEASUREMENT_ID の3つのsecret値
→ なければプレースホルダー値でOK（deploy時に注入）

**成果物:**
- `scripts.js` 完成（フォーム送信・GA events）
- CTA 4個稼働（LINE DL, resource form, meeting form, hero button）
- GA4 events収集開始

**Ready to dispatch:** 小柳さん判定が下りたら即日dispatch可

### Tasks 5-9

- Task 5: 画像最適化・lazy loading（Task 4と並行可）
- Task 6: WCAG 2.1 AA accessibility
- Task 7: Lighthouse Performance実測
- Task 8: 全device QA testing
- Task 9: 最終deploy準備（content sign-off + pre-launch checklist）

**実行順:** Task 4 完全稼働後、5-8は並行実行。9は最終gate。

---

## 次のステップ

### 小柳さんへの上申内容
1. **事実検証:** 表記クレーム5件の出所確認（表示/削除を判定）
2. **バッジ承認:** Alibaba/Okinawa/Trade Assurance の法的根拠取得
3. **CV方針:** email/phone form追加をLINE-only rule例外として認めるか判定
4. **正式議事:** 三名体制で「Plan A LP公開・個人情報収集」の決裁記録

### 小柳さん判定後の流れ
1. ✅ 承認 → Task 4 implementer dispatch（同日）
2. ✅ 部分承認 → HTML修正（該当箇所削除/修正） → Task 4 dispatch
3. ❌ 却下 → プロジェクト保留（小柳さんから再指示待ち）

### Deploy unlock タイミング
- 全content承認 + Task 1-9 pass → `update.yml`から `rm -rf /tmp/pages-deploy/go/plan-a` を削除
- merge to main → Pages自動deploy → public

---

## 添付資料

| ファイル | 役割 |
|--------|------|
| `.superpowers/sdd/2026-09-26-plan-a-lp-implementation/progress.md` | 工程ledger（Task 1-3 verdict + 最終review rulings） |
| `docs/superpowers/specs/2026-09-26-plan-a-lp-design.md` | Design spec（authority） |
| `docs/superpowers/plans/2026-09-26-plan-a-lp-implementation.md` | Tasks 1-3完了（code例付き） |
| `docs/superpowers/plans/2026-09-26-plan-a-lp-implementation-task4-9.md` | Tasks 4-9実装brief（ready to dispatch） |
| `site/go/plan-a/index.html` | 1-3完成（scripts.js未実装） |
| `site/go/plan-a/styles.css` | responsive完成 |
| `site/go/plan-a/assets/manifest.json` | asset一覧（placeholders） |

---

## 判定ポイント（小柳さん向け）

🔴 **MUST:** 事実検証・バッジ根拠・CV方針（rule 4解釈） → これなしでは絶対公開不可
🟡 **SHOULD:** 正式議事の作成 → 決定後に記録でOK
🟢 **NICE:** Hero text位置修正（Task 4の簡単fix）、dark-mode colors承認

**判定期限:** 制度限定なし、ただし Task 4 dispatchまでは待機

---

**Created by:** Claude Code Final Whole-Branch Review
**Ledger:** `.superpowers/sdd/2026-09-26-plan-a-lp-implementation/progress.md` (git-ignored, reference only)
