# アポ管理コンソール(apo-kanri)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** アポ入れ係と対面営業7名以上が、アポ連携・申込み連携・急な変更・遅れ連絡を1つのスマホ画面とSlack通知で共有できる専用コンソールを作る。

**Architecture:** glow-ma と同じ「純ロジックはUMD形式 .js(Nodeテスト対象)/ GAS依存は薄い .gs ランナー」構成。専用スプレッドシート「アポ管理台帳」にデータを持ち、GAS Web App(スタッフ許可リスト認証)+Slack Incoming Webhook で運用する。glow-ma のシート・コードは一切参照しない。

**Tech Stack:** Google Apps Script(clasp)/ Vanilla JS(UMD)/ node:test / Slack Incoming Webhook

## Global Constraints

- 設計書: `docs/superpowers/specs/2026-08-14-apo-kanri-console-design.md`(スコープ・データ設計・裁定はここが正)
- `apo-kanri/` から `glow-ma/` への参照禁止。`SpreadsheetApp.getActiveSpreadsheet()` のみ使用(シートIDハードコード禁止)
- 実データ・実URL・Webhook URLをコミットしない。列追加は末尾のみ
- 公開GAS関数(末尾 `_` なし)は冒頭で必ず `requireApoAccess_()` を呼ぶ
- テストは `node --test tests/apo_kanri_*.test.mjs`。既存テストを壊さない
- 主要操作2タップ以内・時刻の自動変更禁止(遅延は通知のみ)・通知5種限定

---

### Task 1: スキーマ定義(schema.js)

**Files:** Create `apo-kanri/src/schema.js` / Test `tests/apo_kanri_schema.test.mjs`

**Produces:** `ApoSchema`(UMD, module.exports 兼 global):
`STAFF_SHEET_NAME`「スタッフ」, `STAFF_HEADERS`[氏名, Slack User ID, 有効, メールアドレス, 役割],
`STAFF_ROLES`[アポ入れ, 営業, 両方],
`APPOINTMENT_SHEET_NAME`「アポ予定」, `APPOINTMENT_HEADERS`[アポID, 日付, 開始時刻, 所要分, 顧客名, 形式, 場所またはURL, 担当営業, アポ入れ担当, 温度感, ステータス, メモ, 登録日時, 最終更新日時],
`APPOINTMENT_FORMATS`[訪問, 来店, オンライン], `TEMPERATURES`[高, 中, 低],
`APPOINTMENT_STATUSES`[予定, 確定, 実施済, 申込み, キャンセル(顧客都合), キャンセル(自社都合), 再調整中],
`HISTORY_SHEET_NAME`「変更履歴」, `HISTORY_HEADERS`[履歴ID, アポID, 日時, 操作者, 操作, 変更内容],
`HISTORY_OPERATIONS`[新規, 変更, 遅延連絡],
`SETTINGS_SHEET_NAME`「設定」, `SETTINGS_HEADERS`[キー, 値, 説明]

- [ ] テスト作成(ヘッダー配列の存在・重複列名なし・ステータス7種・アポIDが先頭列)→ 失敗確認 → 実装 → パス確認 → コミット

### Task 2: 認証・スタッフ絞り込み(apoAccess.js)

**Files:** Create `apo-kanri/src/apoAccess.js` / Test `tests/apo_kanri_access.test.mjs`

**Produces:** `ApoAccess`:
- `isAllowedEmail(email, staffRows)` — staffRows: `[{email, name, role, slackUserId}]`。大文字小文字・空白を正規化して照合
- `resolveStaffName(email, staffRows)` — 未登録は「不明」
- `listSalesStaff(staffRows)` — 役割が「営業」or「両方」の氏名配列(フォームの担当営業選択肢)
- `listSetterStaff(staffRows)` — 「アポ入れ」or「両方」
- `buildAccessDeniedHtml()` — glow-ma と同文面

- [ ] テスト(照合の正規化 / 役割絞り込み / 空配列) → 実装 → パス → コミット

### Task 3: コアロジック(apoCore.js)

**Files:** Create `apo-kanri/src/apoCore.js` / Test `tests/apo_kanri_core.test.mjs`

**Produces:** `ApoCore`(すべて純関数。現在時刻・乱数は引数で注入):
- `generateApoId(now, randomFn)` → `"APO-20260814-XXXX"` 形式
- `normalizeDateString(value)` / `normalizeTimeString(value)` — Date/文字列どちらでも "yyyy-MM-dd"/"HH:mm" に正規化(glow-ma normalizeDateForDisplay と同種の問題対策)
- `sortAppointments(list)` — 日付→開始時刻→顧客名の昇順
- `buildDayView(appointments, dateString, ownerFilter)` — 指定日のアポをソートし、`summary: {total, unconfirmed}` 付きで返す。壊れた行(日付なし等)はスキップ
- `buildWeekView(appointments, startDateString)` — 7日分を `[{date, items}]` で返す
- `detectOverlap(appointments, candidate)` — 同一担当営業・同一日付・時間帯重複([開始, 開始+所要分) の交差)のアポ配列を返す。キャンセル系・再調整中は対象外。candidate自身のアポIDは除外(編集時)
- `buildDelayTargets(appointments, salesOwner, dateString, fromTimeString)` — 当該営業の同日・fromTime以降のアポ(キャンセル系除く)を時刻順で返す
- `buildChangeDiff(oldRecord, newRecord)` — 変更列のみ `"日付: 8/20→8/21 / 開始時刻: 10:00→14:00"` 形式の文字列。差分なしは空文字

- [ ] テスト(ID形式 / 正規化 / 日・週ビューの抽出とサマリー / 重複判定の境界値=隣接は非重複 / 遅延対象抽出 / 差分文字列 / 壊れ行スキップ)→ 実装 → パス → コミット

### Task 4: Slack通知文面(apoNotify.js)

**Files:** Create `apo-kanri/src/apoNotify.js` / Test `tests/apo_kanri_notify.test.mjs`

**Produces:** `ApoNotify`:
- `buildNewAppointmentMessage(apo, mention)` — 「📅 新規アポ」+日時・顧客名・形式・場所・温度感+担当メンション
- `buildChangeMessage(apo, diff, mention)` — 「🔁 アポ変更」+差分
- `buildCancelMessage(apo, status, mention)` — 「❌ キャンセル(顧客都合/自社都合)」
- `buildSignupMessage(apo, mention)` — 「🎉 申込み」
- `buildDelayMessage(salesName, minutes, targets, mentionResolver)` — 「⏰ ◯◯さん +30分遅れ見込み」+影響しうる後続アポ一覧(各行にアポ入れ担当メンション)
- `formatMention(slackUserId, fallbackName)` — IDあれば `<@U...>`、なければ氏名
すべて1〜3行+箇条書きで、Slack通知一覧で読み切れる長さにする。

- [ ] テスト(5種の文面に必須要素が含まれる / メンションのフォールバック / 遅延対象0件時の文面)→ 実装 → パス → コミット

### Task 5: Web App画面(apoPage.js)

**Files:** Create `apo-kanri/src/apoPage.js` / Test `tests/apo_kanri_page.test.mjs`

**Produces:** `ApoPage.buildApoAppHtml()` — 完結した1ページHTML文字列。
- モバイルファースト。配色はGLOWコーポレート(ネイビー#00335c×#F88800)、ダークモード両対応、`prefers-reduced-motion` 対応(glow-maコンソールv2の方針踏襲)
- 構成: ヘッダー(タイトル+本日/週切替+「自分のアポ」トグル+担当者チップ)/ 本日サマリー行 / アポカードリスト(時刻・顧客名・形式・場所・担当営業・温度感バッジ・ステータス色)/ FAB「+新規アポ」/ カードタップでアクションシート(確定・実施済・申込み・再調整中・キャンセル2種・遅れそう+15/30/60・編集)/ 登録・編集モーダル(重複警告表示領域付き)
- サーバ呼び出しは `google.script.run` で `getBoard` / `saveAppointment` / `updateStatus` / `reportDelay` / `getFormOptions`
- スモークテスト: HTMLに viewport meta・5つの google.script.run 呼び出し名・ステータス7種・「遅れそう」ボタンが含まれること

- [ ] テスト → 実装 → パス → コミット

### Task 6: GAS層(SheetSetup.gs / ApoRunner.gs / 設定ファイル)

**Files:** Create `apo-kanri/src/SheetSetup.gs`, `apo-kanri/src/ApoRunner.gs`, `apo-kanri/src/resilience.js`(glow-ma版と同内容・ApoResilience名), `apo-kanri/src/appsscript.json`, `apo-kanri/.clasp.json.example`

**Consumes:** Task 1〜5 の全API。
**Produces(GAS公開関数):**
- `ensureApoTabs()` — 4タブをヘッダー付きで冪等作成+ステータス・形式・温度感・役割のプルダウン(入力規則)設定
- `doGet()` — 許可リスト照合→ `ApoPage.buildApoAppHtml()`
- `getBoard(params)` — `{view:"day"|"week", date, owner}` → ビュー+スタッフ一覧
- `saveAppointment(payload)` — LockService直列化。新規はID採番、編集は差分生成→変更履歴追記→Slack通知(新規/変更/キャンセル/申込みを自動判別)。戻り値に `overlapWarning`(detectOverlap結果)を含める。保存前チェックとして `payload.confirmedOverlap` が false で重複ありなら保存せず警告のみ返す(2度目の保存で確定=警告するが止めない)
- `updateStatus(apoId, status)` — ステータスのみ変更の近道(カード2タップ操作用)。履歴+通知は saveAppointment と同経路
- `reportDelay(minutes)` — 操作者(メール→スタッフ氏名)の本日以降アポから `buildDelayTargets` で対象抽出→履歴「遅延連絡」追記→Slack遅延通知。時刻は変更しない
- `getFormOptions()` — 営業/アポ入れ担当の選択肢・ステータス等
- Slack送信 `postToApoSlack_(message)` — Script Property `SLACK_WEBHOOK_URL`。未設定はログのみでスキップ。`ApoResilience.withRetry`(最大3回・429/5xxのみ・Utilities.sleep)
- 全公開関数の冒頭で `requireApoAccess_()`(スタッフタブ照合)。通知失敗は保存成功扱い+履歴に記録

- [ ] resilience.js を写経(名前空間のみ ApoResilience に変更)+ 既存 `tests/glow_ma_resilience.test.mjs` を参考に `tests/apo_kanri_resilience.test.mjs` を作成 → GAS層実装(Nodeテスト対象外・ロジックは持たせない)→ コミット

### Task 7: CI・README・記録・出荷

**Files:** Create `.github/workflows/apo-kanri-ci.yml`(glow-ma-ci.yml を雛形に `node --test tests/apo_kanri_*.test.mjs`), `apo-kanri/README.md` / Modify `docs/決裁キュー.md`, `docs/アポ管理アプリ_指示プロンプト設計ガイド_2026-08-14.md`

- [ ] README: これは何か / セットアップ(スプレッドシート新規作成→clasp→ensureApoTabs→スタッフ登録→Webhook設定→デプロイ→URL共有)/ 運用ルール(シート直接編集禁止・履歴はWeb App操作の記録・glow-ma非参照)/ 制約
- [ ] 全テスト実行(`node --test tests/apo_kanri_*.test.mjs` と既存 glow_ma テスト)
- [ ] 決裁キュー消し込み(方針2点は決裁済みとして✅ログへ)+指示ガイドに「実装済み・場所」追記
- [ ] コミット・プッシュ(claude/sales-appointment-management-app-5fuo4y)
