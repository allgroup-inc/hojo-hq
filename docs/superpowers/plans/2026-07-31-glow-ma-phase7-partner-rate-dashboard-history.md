# GLOW M&A台帳 Phase 7(紹介パートナー成約率・ダッシュボード履歴)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/superpowers/specs/2026-07-31-glow-ma-feature-brainstorm-triangle-review.md` のうち、既に「採用」と結論が出ている論点3(紹介パートナーの成約率をダッシュボードに表示。スコアへの自動反映はしない)・論点5(ダッシュボードの主要指標を「ダッシュボード履歴」タブに1行ずつ追記し、時系列の推移を追えるようにする)を実装する。論点1・2・4は小柳さんの採否判断が保留中のため本Planの範囲外。

**Architecture:** 成約率の計算・履歴スナップショットの組み立てはNode/GAS両対応のUMD形式プレーンJSとして`glow-ma/src/dashboard.js`に追加し、`node --test`でユニットテストする。GAS専用の`DashboardRunner.gs`は、`updateDashboard()`実行の最後に「ダッシュボード履歴」タブへ1行`appendRow`するだけの薄い追加とする。**「ダッシュボード」タブ(Phase 5)は既存どおり`clearContents()`して作り直す方式のまま変更しない。「ダッシュボード履歴」タブは追記専用の別タブとして新設する**(三名体制レビューのウタガイ指摘どおり、既存のダッシュボード集計・書き込みロジックを壊さないための設計)。

**このPlanの範囲について:** 沖縄企業のミカタ側で既に稼働している「週次レポート自動配信(毎週月曜8:00 JST・小柳さんのLINEへ)」への統合は、技術スタックが別(Python/GitHub Actions vs. Google Apps Script/Spreadsheet)であり、本Planの範囲外とする。glow-ma側は「ダッシュボード履歴」タブにデータを蓄積するところまでを実装し、既存の週次配信への実際の統合方法(データ受け渡し方式等)は人間側の運用検討課題として`glow-ma/README.md`に明記する。

## Global Constraints

- 公開リポジトリ(hojo-hq)に実データを一切コミットしない(本Planは実データを一切扱わない)
- GASとNode両方で動くファイルはUMD形式(`typeof module !== "undefined" && module.exports`で分岐)を踏襲する
- `dashboard.js`が`GlowAlerting`を参照する箇所(`buildHistorySnapshot`が`buildRankSummary`経由で間接的に使う)は、既存の`getGlowAlerting_()`遅延解決ヘルパーをそのまま利用する(新しい遅延解決ヘルパーを重複定義しない)
- `schema.js`への列・タブ追加は、Phase 6最終レビューで確立した「配列の末尾に追加する(既存データの位置ズレを防ぐ)」の原則に従う
- 「ダッシュボード履歴」タブは追記専用(`clearContents()`しない)。`ensureTab_`は1行目の見出しのみ上書きする既存の設計のため、再実行してもデータ行(2行目以降の履歴)は消えないことを確認する
- 追加のnpm依存を増やさない。テストは`node --test` + `node:assert/strict`を使う
- GAS専用ファイル(`.gs`)は`node --test`で検証できないため、静的チェック(`node --check`)と手書きトレースで代替し、実運用前の手動検証が必要であることをレポートに明記する

---

## File Structure

```
glow-ma/src/
  schema.js       — 既存ファイルを修正: DASHBOARD_HISTORY_SHEET_NAME/HEADERSを追加(Task 1)
  dashboard.js      — 既存ファイルを修正: formatPartnerSummaryに成約率を追加(Task 2)、
                buildHistorySnapshotを追加(Task 3)
  SheetSetup.gs      — 既存ファイルを修正: ダッシュボード履歴タブの作成を追加(Task 4)
  DashboardRunner.gs   — 既存ファイルを修正: 成約率列の書き込み・履歴の追記(Task 5)
tests/
  glow_ma_dashboard.test.mjs — 既存ファイルを修正(Task 2, 3)
glow-ma/README.md    — Phase 7の使い方を追記(Task 6)
```

---

### Task 1: `schema.js` — ダッシュボード履歴タブの定義を追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Modify: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowSchema.DASHBOARD_HISTORY_SHEET_NAME`(string、`"ダッシュボード履歴"`)、`GlowSchema.DASHBOARD_HISTORY_HEADERS`(string[])。Task 4(タブ作成)・Task 5(書き込み)が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs` の末尾に追記:

```js
test("ダッシュボード履歴タブの名称・見出しが定義されている", () => {
  assert.equal(schema.DASHBOARD_HISTORY_SHEET_NAME, "ダッシュボード履歴");
  assert.deepEqual(schema.DASHBOARD_HISTORY_HEADERS, [
    "記録日時", "対象企業数",
    "ランクA_滞留企業数", "ランクB_滞留企業数", "ランクC_滞留企業数", "ランクD_滞留企業数",
    "掘り起こし待ち件数合計", "連絡不要企業数"
  ]);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(`schema.DASHBOARD_HISTORY_SHEET_NAME`が`undefined`)

- [ ] **Step 3: `glow-ma/src/schema.js` に定義を追加**

`DASHBOARD_PLACEHOLDER_HEADERS`の定義の直後に追加する(**既存の`COMPANY_MASTER_HEADERS`等は一切変更しないこと**):

```js
  var DASHBOARD_HISTORY_SHEET_NAME = "ダッシュボード履歴";
  var DASHBOARD_HISTORY_HEADERS = [
    "記録日時", "対象企業数",
    "ランクA_滞留企業数", "ランクB_滞留企業数", "ランクC_滞留企業数", "ランクD_滞留企業数",
    "掘り起こし待ち件数合計", "連絡不要企業数"
  ];
```

`api`オブジェクトに追加する(既存のプロパティはそのまま残し、以下を追記):

```js
    DASHBOARD_HISTORY_SHEET_NAME: DASHBOARD_HISTORY_SHEET_NAME,
    DASHBOARD_HISTORY_HEADERS: DASHBOARD_HISTORY_HEADERS
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(既存テスト + 新規1テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): ダッシュボード履歴タブのスキーマ定義を追加"
```

---

### Task 2: `dashboard.js` — 紹介パートナー別サマリーに成約率を追加

**Files:**
- Modify: `glow-ma/src/dashboard.js`
- Modify: `tests/glow_ma_dashboard.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `formatPartnerSummary(partnerRecords)`の戻り値に`"成約率"`(string、例:`"20.0%"`。累計紹介数が0または非数値なら`""`)を追加。Task 5(書き込み)が参照する契約

- [ ] **Step 1: 失敗するテストを追記**

`tests/glow_ma_dashboard.test.mjs` の既存の`formatPartnerSummary`テストを次のように更新し、新規テストを追加する(**既存の2テストは`成約率`を含む期待値に更新すること**):

```js
test("formatPartnerSummary: パートナーマスタの表示用フィールドを整形する", () => {
  const partners = [
    { 名称: "テスト税理士法人", 累計紹介数: 5, 成約数: 1, 関係性ランク: "高", 提供済み情報ログ: "建設業向け資料を提供", 逆紹介履歴: "サンプル建設を紹介" }
  ];
  const summary = dashboard.formatPartnerSummary(partners);
  assert.deepEqual(summary, [
    { "名称": "テスト税理士法人", "累計紹介数": 5, "成約数": 1, "関係性ランク": "高", "提供済み情報ログ": "建設業向け資料を提供", "逆紹介履歴": "サンプル建設を紹介", "成約率": "20.0%" }
  ]);
});

test("formatPartnerSummary: 欠損フィールドは空文字で埋める(成約率は累計紹介数0のため空文字)", () => {
  const summary = dashboard.formatPartnerSummary([{ 名称: "テスト銀行" }]);
  assert.deepEqual(summary[0], { "名称": "テスト銀行", "累計紹介数": "", "成約数": "", "関係性ランク": "", "提供済み情報ログ": "", "逆紹介履歴": "", "成約率": "" });
});

test("formatPartnerSummary: 空配列なら空配列", () => {
  assert.deepEqual(dashboard.formatPartnerSummary([]), []);
});

test("formatPartnerSummary: 成約率は成約数/累計紹介数を百分率(小数点1桁)で返す", () => {
  const partners = [{ 名称: "A", 累計紹介数: 3, 成約数: 1 }];
  const summary = dashboard.formatPartnerSummary(partners);
  assert.equal(summary[0]["成約率"], "33.3%");
});

test("formatPartnerSummary: 累計紹介数が0なら成約率は空文字(ゼロ除算しない)", () => {
  const partners = [{ 名称: "A", 累計紹介数: 0, 成約数: 0 }];
  const summary = dashboard.formatPartnerSummary(partners);
  assert.equal(summary[0]["成約率"], "");
});
```

(既存ファイルの3テストのうち、`formatPartnerSummary`の1つ目・2つ目のテストが上記の更新対象。3つ目「空配列なら空配列」はそのまま。)

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_dashboard.test.mjs`
Expected: FAIL(既存2テストの期待値に`成約率`がなく不一致、新規2テストは`undefined`)

- [ ] **Step 3: `glow-ma/src/dashboard.js` を修正**

`formatPartnerSummary`関数を次のように修正する:

```js
  function calculateConversionRate_(referralCountValue, dealCountValue) {
    var referrals = Number(referralCountValue);
    var deals = Number(dealCountValue);
    if (!referrals || isNaN(referrals) || referrals <= 0 || isNaN(deals)) return "";
    return (deals / referrals * 100).toFixed(1) + "%";
  }

  function formatPartnerSummary(partnerRecords) {
    return (partnerRecords || []).map(function (partner) {
      var summary = {};
      PARTNER_SUMMARY_FIELDS.forEach(function (field) {
        var value = partner[field];
        summary[field] = value === undefined || value === null ? "" : value;
      });
      summary["成約率"] = calculateConversionRate_(partner["累計紹介数"], partner["成約数"]);
      return summary;
    });
  }
```

**注意:** `calculateConversionRate_`は元の`partner`引数(整形前の生データ)から計算すること。`summary`側の値は空文字埋め後のため数値計算に使うと`Number("")`が`0`になり、欠損と実際の0件を区別できなくなる。

`PARTNER_SUMMARY_FIELDS`配列自体(`["名称", "累計紹介数", "成約数", "関係性ランク", "提供済み情報ログ", "逆紹介履歴"]`)は変更しないこと(Task 5で使う既存の書き込みヘッダーの並びに影響するため)。

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_dashboard.test.mjs`
Expected: PASS(既存テスト更新分 + 新規2テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/dashboard.js tests/glow_ma_dashboard.test.mjs
git commit -m "feat(glow-ma): 紹介パートナー別サマリーに成約率を追加(スコアには反映しない)"
```

---

### Task 3: `dashboard.js` — ダッシュボード履歴スナップショットの組み立て

**Files:**
- Modify: `glow-ma/src/dashboard.js`
- Modify: `tests/glow_ma_dashboard.test.mjs`

**Interfaces:**
- Consumes: `buildRankSummary`(同ファイル内、Phase 5)
- Produces: `buildHistorySnapshot(records, todayValue, config)`: `{対象企業数, ランクA_滞留企業数, ランクB_滞留企業数, ランクC_滞留企業数, ランクD_滞留企業数, 掘り起こし待ち件数合計, 連絡不要企業数}`。Task 5の`DashboardRunner.gs`が呼び出す(`記録日時`はGAS側でタイムスタンプを付与するため、この関数の戻り値には含めない)

- [ ] **Step 1: 失敗するテストを追記**

`tests/glow_ma_dashboard.test.mjs` に追記:

```js
test("buildHistorySnapshot: ランク別滞留企業数・掘り起こし待ち件数合計・連絡不要企業数を集計する", () => {
  const records = [
    { 企業ID: "C1", ランク: "A", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2020-01-01", 連絡不要: false },
    { 企業ID: "C2", ランク: "B", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2026-07-27", 連絡不要: false },
    { 企業ID: "C3", ランク: "D", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2020-01-01", 連絡不要: true }
  ];
  const snapshot = dashboard.buildHistorySnapshot(records, "2026-07-27", dashboard.DEFAULT_CONFIG);
  assert.equal(snapshot["対象企業数"], 3);
  assert.equal(snapshot["ランクA_滞留企業数"], 1);
  assert.equal(snapshot["ランクB_滞留企業数"], 1);
  assert.equal(snapshot["ランクD_滞留企業数"], 1);
  // C1は掘り起こし対象(30日サイクル超過)。C3は連絡不要のためisOverdueがfalseを返し対象外
  assert.equal(snapshot["掘り起こし待ち件数合計"], 1);
  assert.equal(snapshot["連絡不要企業数"], 1);
});

test("buildHistorySnapshot: 対象企業がなければ全項目0", () => {
  const snapshot = dashboard.buildHistorySnapshot([], "2026-07-27", dashboard.DEFAULT_CONFIG);
  assert.equal(snapshot["対象企業数"], 0);
  assert.equal(snapshot["掘り起こし待ち件数合計"], 0);
  assert.equal(snapshot["連絡不要企業数"], 0);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_dashboard.test.mjs`
Expected: FAIL(`dashboard.buildHistorySnapshot is not a function`)

- [ ] **Step 3: `buildHistorySnapshot` を実装**

`glow-ma/src/dashboard.js` の `buildRankSummary` 関数の直後(`formatPartnerSummary`より前)に追加する:

```js
  function buildHistorySnapshot(records, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var list = records || [];
    var rankSummary = buildRankSummary(list, todayValue, config);
    var findRank_ = function (rank) {
      var found = rankSummary.filter(function (r) { return r["ランク"] === rank; })[0];
      return found || { "滞留企業数": 0, "掘り起こし待ち件数": 0 };
    };
    var totalOverdue = rankSummary.reduce(function (sum, r) {
      return sum + r["掘り起こし待ち件数"];
    }, 0);
    var doNotContactCount = list.filter(function (record) {
      return record["連絡不要"] === true;
    }).length;
    return {
      "対象企業数": list.length,
      "ランクA_滞留企業数": findRank_("A")["滞留企業数"],
      "ランクB_滞留企業数": findRank_("B")["滞留企業数"],
      "ランクC_滞留企業数": findRank_("C")["滞留企業数"],
      "ランクD_滞留企業数": findRank_("D")["滞留企業数"],
      "掘り起こし待ち件数合計": totalOverdue,
      "連絡不要企業数": doNotContactCount
    };
  }
```

`api`オブジェクトに追加する:

```js
    buildHistorySnapshot: buildHistorySnapshot,
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_dashboard.test.mjs`
Expected: PASS(既存テスト + 新規2テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/dashboard.js tests/glow_ma_dashboard.test.mjs
git commit -m "feat(glow-ma): ダッシュボード履歴スナップショットの集計ロジックを追加"
```

---

### Task 4: `SheetSetup.gs` — ダッシュボード履歴タブの作成(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/SheetSetup.gs`

**Interfaces:**
- Consumes: `GlowSchema.DASHBOARD_HISTORY_SHEET_NAME`/`DASHBOARD_HISTORY_HEADERS`(Task 1)
- Produces: `ensureLedgerTabs()`実行時に「ダッシュボード履歴」タブが(存在しなければ)作成される

- [ ] **Step 1: `glow-ma/src/SheetSetup.gs` を修正**

`ensureLedgerTabs()`関数の末尾(`ensureTab_(ss, GlowSchema.DASHBOARD_SHEET_NAME, GlowSchema.DASHBOARD_PLACEHOLDER_HEADERS);`の直後)に以下を追加する:

```js
  ensureTab_(ss, GlowSchema.DASHBOARD_HISTORY_SHEET_NAME, GlowSchema.DASHBOARD_HISTORY_HEADERS);
```

ファイル冒頭のコメントも、タブが7個になったことがわかるように更新する(「6タブ」を「7タブ」に、タブ名の列挙に「ダッシュボード履歴」を追加)。**既存の`ensureTab_`・各種`apply*Validation_`関数と、それらの呼び出しは変更・削除しないこと。** `ensureTab_`は1行目の見出しのみを上書きする実装のため、「ダッシュボード履歴」タブを再実行しても2行目以降の蓄積済み履歴データは消えないことを確認する(Phase 5の「ダッシュボード」タブのようにdata部分を書き換える処理はここでは行わないため、Phase 5の note-only findingsで指摘された「タイトル行の上書き」問題はこのタブには当てはまらない)。

- [ ] **Step 2: 静的チェック**

Run: `cp glow-ma/src/SheetSetup.gs /tmp/SheetSetup_check.js && node --check /tmp/SheetSetup_check.js && rm /tmp/SheetSetup_check.js`
Expected: 構文エラーなし

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間がGoogleスプレッドシート上で確認する手順:

1. `clasp push` で反映
2. `ensureLedgerTabs` を実行
3. 「ダッシュボード履歴」タブが作成され、1行目に見出しが入っていることを確認する
4. 既存の6タブが壊れていないことも確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/SheetSetup.gs
git commit -m "feat(glow-ma): ダッシュボード履歴タブの作成を追加"
```

---

### Task 5: `DashboardRunner.gs` — 成約率列の書き込み・履歴の追記(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/DashboardRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema.DASHBOARD_HISTORY_SHEET_NAME`(Task 1)、`GlowDashboard.buildHistorySnapshot`(Task 3)、`formatPartnerSummary`の`成約率`追加分(Task 2)
- Produces: `updateDashboard()`実行時、紹介パートナー別サマリーに成約率列が追加され、「ダッシュボード履歴」タブに1行が追記される(既存の「ダッシュボード」タブの5セクションはそのまま)

- [ ] **Step 1: `glow-ma/src/DashboardRunner.gs` を修正**

紹介パートナー別サマリーの書き込み箇所を次のように修正する(`GlowDashboard.PARTNER_SUMMARY_FIELDS`に`"成約率"`を追加した見出し・行データにする):

```js
    row = writeDashboardSection_(dashboardSheet, row, "紹介パートナー別サマリー",
      GlowDashboard.PARTNER_SUMMARY_FIELDS.concat(["成約率"]),
      partnerSummary.map(function (p) {
        return GlowDashboard.PARTNER_SUMMARY_FIELDS.concat(["成約率"]).map(function (field) { return p[field]; });
      }));
```

`updateDashboard()`関数の末尾、既存の「データ品質チェック」セクション書き込みの後・`Logger.log("ダッシュボード更新完了");`の前に、履歴タブへの追記を追加する。まず関数冒頭のシート取得部分(`var partnerSheet = ss.getSheetByName(...)`の直後)に履歴シートの取得も追加する:

```js
  var historySheet = ss.getSheetByName(GlowSchema.DASHBOARD_HISTORY_SHEET_NAME);
  if (!historySheet) {
    throw new Error("ダッシュボード履歴タブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
```

`var qualitySummary = GlowDashboard.countUnclassifiedCompanies(...)`の直後に履歴スナップショットの算出を追加する:

```js
  var historySnapshot = GlowDashboard.buildHistorySnapshot(records, todayString, GlowDashboard.DEFAULT_CONFIG);
```

`try`ブロック内、既存の5セクション書き込み(データ品質チェックの`row++;`の直後、最終更新時刻の`setValue`より前)の後に、履歴タブへの追記を追加する(**「ダッシュボード」タブの`dashboardSheet`ではなく、別タブの`historySheet`に対して`appendRow`する。`clearContents()`は呼ばない**):

```js
    historySheet.appendRow([
      Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm"),
      historySnapshot["対象企業数"],
      historySnapshot["ランクA_滞留企業数"], historySnapshot["ランクB_滞留企業数"],
      historySnapshot["ランクC_滞留企業数"], historySnapshot["ランクD_滞留企業数"],
      historySnapshot["掘り起こし待ち件数合計"], historySnapshot["連絡不要企業数"]
    ]);
```

(この`appendRow`は既存の`LockService`ロック(`updateDashboard`全体を保護している`lock`)の`try`ブロック内で実行されるため、追加のロック取得は不要。)

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/DashboardRunner.gs /tmp/DashboardRunner_check2.js && node --check /tmp/DashboardRunner_check2.js && rm /tmp/DashboardRunner_check2.js` で構文チェック
2. `GlowDashboard.buildHistorySnapshot`・`GlowSchema.DASHBOARD_HISTORY_SHEET_NAME`の参照が、実際の`dashboard.js`/`schema.js`の定義と一致していることを確認する
3. `historySheet.appendRow(...)`が`dashboardSheet.clearContents()`とは別のシート変数に対する呼び出しであることを再確認し、「ダッシュボード」タブ(Phase 5の5セクション)の既存の書き込みロジック・row変数の計算に影響しないことを確認する
4. 企業マスタ・紹介パートナーマスタが共に空(0件)の場合でも、`historySnapshot`の全項目が0になり、`appendRow`が例外を投げずに1行(すべて0の行+タイムスタンプ)を追記することをコードを目でたどって確認する

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間がGoogleスプレッドシート上で確認する手順:

1. `clasp push` で反映
2. `updateDashboard` を実行する
3. 「ダッシュボード」タブの紹介パートナー別サマリーに「成約率」列が追加されていることを確認する
4. 「ダッシュボード履歴」タブに1行(記録日時+各指標)が追記されることを確認する
5. 再度 `updateDashboard` を実行し、「ダッシュボード履歴」タブに前回の行が残ったまま新しい行が追記される(上書きされない)ことを確認する。「ダッシュボード」タブ本体は従来どおり作り直されることも確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/DashboardRunner.gs
git commit -m "feat(glow-ma): 紹介パートナー成約率の書き込みとダッシュボード履歴の追記を追加"
```

---

### Task 6: READMEにPhase 7の使い方を追記

**Files:**
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: Task 1〜5の全成果物
- Produces: GLOWチームが成約率・ダッシュボード履歴を運用できるようになるドキュメント

- [ ] **Step 1: `glow-ma/README.md` の「## 電話番号・連絡不要(DNC)フラグ(Phase 6)」の直後・「## 次のフェーズ」の直前に以下を追記**

```markdown
## 紹介パートナー成約率・ダッシュボード履歴(Phase 7)

三名体制レビュー(`docs/superpowers/specs/2026-07-31-glow-ma-feature-brainstorm-triangle-review.md`)
論点3・論点5への対応。

**紹介パートナー成約率(論点3)**: 「ダッシュボード」タブの紹介パートナー別サマリーに
成約率(成約数/累計紹介数)の列を追加した。**スコアリングへの自動反映はしない**
(母数が少ない新規パートナーを不当に低評価しないため、あくまで人間の判断材料として表示のみ)。

**ダッシュボード履歴(論点5)**: `updateDashboard`を実行するたびに、主要指標
(対象企業数・ランク別滞留企業数・掘り起こし待ち件数合計・連絡不要企業数)を
「ダッシュボード履歴」タブへ1行追記する。既存の「ダッシュボード」タブとは異なり、
このタブは追記専用で内容を消さない(実行のたびに履歴が積み上がる)。

**使い方**

1. `clasp push` で最新コードを反映する
2. Apps Scriptエディタで `updateDashboard` を実行する(手順はPhase 5と同じ)
3. 「ダッシュボード」タブの紹介パートナー別サマリーに成約率列が追加される
4. 「ダッシュボード履歴」タブに実行時点のスナップショットが1行追記される

**現時点の制約:**
- 沖縄企業のミカタ側で稼働中の週次レポート自動配信(毎週月曜8:00 JST・小柳さんのLINEへ)への
  統合は本Phaseの範囲外(技術スタックが別のため)。「ダッシュボード履歴」タブのデータを
  どう既存の週次配信と繋ぐか(手動確認/別途連携の実装等)は今後の運用検討課題
- ダッシュボード履歴のグラフ化・可視化の装飾は行っていない。生データの蓄積のみ
- 成約率は小数点1桁の百分率表示。累計紹介数が0件のパートナーは空欄になる(ゼロ除算回避)
```

- [ ] **Step 2: `glow-ma/README.md` の「## 次のフェーズ」の内容を、Phase 7が実装済みになったことを反映して更新する**

- [ ] **Step 3: Commit**

```bash
git add glow-ma/README.md
git commit -m "docs(glow-ma): 紹介パートナー成約率・ダッシュボード履歴(Phase 7)の使い方をREADMEに追記"
```

---

## Self-Review

**Spec coverage(三名体制レビューとの対応)**

- `docs/superpowers/specs/2026-07-31-glow-ma-feature-brainstorm-triangle-review.md` 論点3(採用・ベッカイ案)→ Task 2, 5
- 同 論点5(採用・ベッカイ案)→ Task 1, 3, 4, 5

**Placeholder scan:** TBD/TODO等の記述なし。

**Type consistency:** `GlowDashboard.buildHistorySnapshot`は`buildRankSummary`(Phase 5で確定済みのシグネチャ)をそのまま呼び出しており、名前・引数の食い違いはない。`formatPartnerSummary`の`成約率`追加は、既存の`PARTNER_SUMMARY_FIELDS`配列(Phase 6で確定済み)を変更せず追加のキーとして载せるため、Phase 6で追加された`GlowDashboard.PARTNER_SUMMARY_FIELDS`の外部参照(`DashboardRunner.gs`)との整合を`.concat(["成約率"])`という非破壊の形で保つ。「ダッシュボード履歴」タブは既存の「ダッシュボード」タブとは独立した別シートであり、Phase 5で確立した`clearContents()`方式の書き込みには一切影響しない設計であることを、Task 5の実装・レビューの両方で確認する。
