# GLOW M&A台帳 Phase 8(ディールステージ細分化・工程別滞留状況)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `docs/superpowers/specs/2026-07-31-glow-ma-feature-brainstorm-triangle-review.md` 論点1(ディールステージの細分化)に対応する。裁定はベッカイ案(現在ステージ列は増やさず、対応履歴ログの「種別」に工程遷移を表す新種別を追加し、詳細な工程進捗は対応履歴ログを時系列で追う)を優先案として採用。2026-08-01の三名体制再検証で小柳さんの承認を得た。

**背景**: M&Aは初期打診→NDA→資料開示→意向表明(LOI)→DD→最終契約という長い工程を辿るが、現状の「現在ステージ」列は「案件化」で一段階にまとまっており、工程ごとの滞留が見えない。工程を増やすと現場の入力負担・ダッシュボード集計の複雑化を招くため、「現在ステージ」列自体は変更せず、対応履歴ログの「種別」に工程遷移イベントを追加し、ダッシュボード側で企業ごとに最新の工程遷移イベントを追跡して滞留日数を可視化する。

**Architecture:** 追加する3つの新種別(NDA締結/意向表明受領/DD開始)は`glow-ma/src/schema.js`の`INTERACTION_TYPES`配列に**追加**するだけでよい。`SheetSetup.gs`の種別プルダウン(`applyInteractionTypeValidation_`)は既に`GlowSchema.INTERACTION_TYPES`を動的に参照しているため、コード変更は不要(スキーマ変更が自動的にプルダウンへ反映される)。工程別滞留状況の集計ロジックは、Node/GAS両対応のUMD形式プレーンJSとして`glow-ma/src/dashboard.js`に追加し、`node --test`でユニットテストする。日付計算は既存の`glow-ma/src/alerting.js`の`daysBetween`を`getGlowAlerting_()`遅延解決ヘルパー経由で再利用し、重複定義しない。GAS専用の`DashboardRunner.gs`は、対応履歴ログを読み取り、新しい集計結果を「ダッシュボード」タブの新規セクション(6番目)として追記するだけの薄い追加とする。

**このPlanの範囲について:** 論点1の裁定は「対応履歴ログの種別追加+工程別滞留日数を出す新規集計関数」までを実装コスト小の優先案として明記している。「現在ステージ」列の追加・変更、対応履歴ログの入力UIの変更(プルダウン以外)は範囲外。

## Global Constraints

- 公開リポジトリ(hojo-hq)に実データを一切コミットしない(本Planは実データを一切扱わない)
- GASとNode両方で動くファイルはUMD形式を踏襲する
- `dashboard.js`が`GlowAlerting`の`daysBetween`を使う箇所は、既存の`getGlowAlerting_()`遅延解決ヘルパーをそのまま利用する(新しい遅延解決ヘルパーを重複定義しない、`daysBetween`のロジックを再実装しない)
- `INTERACTION_TYPES`配列への追加は末尾に追加する(既存の値の位置を変えない。ただしこの配列自体はプルダウンの選択肢リストであり順序に業務的な意味はないため、末尾追加は「差分を最小化する」ためのプロジェクト内の一般的な慣習に従うもの)
- 対応履歴ログの読み取りは、`ScoringRunner.gs`に既存の`readInteractionsByCompanyId_`(GAS共有グローバル)をそのまま再利用する。同種の読み取り関数を`DashboardRunner.gs`内に重複定義しない
- 追加のnpm依存を増やさない。テストは`node --test` + `node:assert/strict`を使う
- GAS専用ファイル(`.gs`)は`node --test`で検証できないため、静的チェック(`node --check`)と手書きトレースで代替し、実運用前の手動検証が必要であることをレポートに明記する

---

## File Structure

```
glow-ma/src/
  schema.js       — 既存ファイルを修正: INTERACTION_TYPESに3種別を追加(Task 1)
  dashboard.js      — 既存ファイルを修正: buildDealStageProgressSummaryを追加(Task 2)
  DashboardRunner.gs   — 既存ファイルを修正: 対応履歴ログの読み取り・新セクション書き込み(Task 3)
tests/
  glow_ma_schema.test.mjs    — 既存ファイルを修正(Task 1)
  glow_ma_dashboard.test.mjs   — 既存ファイルを修正(Task 2)
glow-ma/README.md    — Phase 8の使い方を追記(Task 4)
```

---

### Task 1: `schema.js` — 対応履歴ログの種別に工程遷移イベントを追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Modify: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowSchema.INTERACTION_TYPES`に`"NDA締結"`・`"意向表明受領"`・`"DD開始"`が追加される。Task 2(集計ロジック)が参照する契約。`SheetSetup.gs`の`applyInteractionTypeValidation_`は`GlowSchema.INTERACTION_TYPES`を動的参照しているため、コード変更なしにプルダウンへ反映される

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs` の既存テスト「対応履歴ログの種別(INTERACTION_TYPES)が設計書5.2節の15種+連絡不要受領と一致する」を次のように更新する(**既存の`expected`配列の末尾に3種別を追加するだけ。それ以外の要素・順序は変更しない**):

```js
test("対応履歴ログの種別(INTERACTION_TYPES)が設計書5.2節の15種+連絡不要受領+工程遷移イベントと一致する", () => {
  const expected = [
    "手紙送付", "電話", "ゆんたく相談実施", "面談実施", "紹介受領", "ミカタ接点確認",
    "レターURLアクセス", "返信", "資料請求",
    "提案(M&A)", "提案(不動産)", "提案(法人保険)",
    "成約", "見送り", "ナーチャリング配信", "連絡不要受領",
    "NDA締結", "意向表明受領", "DD開始"
  ];
  assert.deepEqual(schema.INTERACTION_TYPES, expected);
});
```

(既存テストの正確な現在の実装を`tests/glow_ma_schema.test.mjs`から確認し、`expected`配列の中身が元の16要素と完全一致した上で末尾に3要素を追加した形になっているか確認すること。)

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(`schema.INTERACTION_TYPES`に3種別がまだ含まれていない)

- [ ] **Step 3: `glow-ma/src/schema.js` を修正**

`INTERACTION_TYPES`配列の末尾に3種別を追加する(既存の16要素はそのまま、追加するだけ):

```js
  var INTERACTION_TYPES = [
    "手紙送付", "電話", "ゆんたく相談実施", "面談実施", "紹介受領", "ミカタ接点確認",
    "レターURLアクセス", "返信", "資料請求",
    "提案(M&A)", "提案(不動産)", "提案(法人保険)",
    "成約", "見送り", "ナーチャリング配信", "連絡不要受領",
    "NDA締結", "意向表明受領", "DD開始"
  ];
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(既存テスト + 更新した1テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): 対応履歴ログの種別に工程遷移イベント(NDA締結/意向表明受領/DD開始)を追加"
```

---

### Task 2: `dashboard.js` — 工程別滞留状況の集計ロジック

**Files:**
- Modify: `glow-ma/src/dashboard.js`
- Modify: `tests/glow_ma_dashboard.test.mjs`

**Interfaces:**
- Consumes: `getGlowAlerting_().daysBetween(fromValue, toValue)`(既存、Phase 3)
- Produces: `buildDealStageProgressSummary(interactionRecords, todayValue, config)`: `[{工程, 滞留企業数, 平均滞留日数}, ...]`(工程は`DEAL_STAGE_TYPES`の順)。Task 3の`DashboardRunner.gs`が呼び出す

**ロジック仕様:**
- `interactionRecords`は対応履歴ログの生レコード配列(各要素が`{企業ID, 日付, 種別, ...}`)。フラットな配列であり、企業IDでグループ化された形式ではない
- `種別`が`DEAL_STAGE_TYPES`(`["NDA締結", "意向表明受領", "DD開始"]`)のいずれかであるレコードのみを対象にする
- 企業ごとに、対象レコードのうち**日付が最も新しいもの1件**を「その企業が現在いる工程」とみなす(工程は進む一方という前提。同じ企業が複数の工程遷移イベントを持つ場合、最新の日付のイベントの種別が「現在の工程」)
- 「現在の工程」の日付から`todayValue`までの日数を`daysBetween`で計算し、その工程の「滞留日数」とする
- 出力は`DEAL_STAGE_TYPES`の順で3行。各行は、その工程が「現在の工程」である企業の**滞留企業数**と、それらの**平均滞留日数**(四捨五入した整数)。対象企業がいない工程は`滞留企業数: 0, 平均滞留日数: 0`
- 対象となる工程遷移イベントを一つも持たない企業は、集計から除外する(どの工程にも計上しない)

- [ ] **Step 1: 失敗するテストを追記**

`tests/glow_ma_dashboard.test.mjs` に追記:

```js
test("buildDealStageProgressSummary: 企業ごとに最新の工程遷移イベントを現在の工程とみなし、工程別に滞留企業数・平均滞留日数を集計する", () => {
  const interactionRecords = [
    { 企業ID: "C1", 日付: "2026-07-01", 種別: "NDA締結" },
    { 企業ID: "C2", 日付: "2026-06-01", 種別: "NDA締結" },
    { 企業ID: "C2", 日付: "2026-07-11", 種別: "意向表明受領" },
    { 企業ID: "C3", 日付: "2026-06-21", 種別: "DD開始" },
    { 企業ID: "C4", 日付: "2026-07-01", 種別: "電話" }
  ];
  const summary = dashboard.buildDealStageProgressSummary(interactionRecords, "2026-07-31", dashboard.DEFAULT_CONFIG);
  assert.deepEqual(summary, [
    { "工程": "NDA締結", "滞留企業数": 1, "平均滞留日数": 30 },
    { "工程": "意向表明受領", "滞留企業数": 1, "平均滞留日数": 20 },
    { "工程": "DD開始", "滞留企業数": 1, "平均滞留日数": 40 }
  ]);
});

test("buildDealStageProgressSummary: 同じ工程に複数企業がいる場合は平均滞留日数を四捨五入して返す", () => {
  const interactionRecords = [
    { 企業ID: "C1", 日付: "2026-07-21", 種別: "NDA締結" }, // 10日
    { 企業ID: "C2", 日付: "2026-07-11", 種別: "NDA締結" }  // 20日
  ];
  const summary = dashboard.buildDealStageProgressSummary(interactionRecords, "2026-07-31", dashboard.DEFAULT_CONFIG);
  assert.equal(summary[0]["滞留企業数"], 2);
  assert.equal(summary[0]["平均滞留日数"], 15);
});

test("buildDealStageProgressSummary: 対象工程のイベントがない企業は集計から除外される", () => {
  const interactionRecords = [
    { 企業ID: "C1", 日付: "2026-07-01", 種別: "電話" },
    { 企業ID: "C1", 日付: "2026-07-05", 種別: "面談実施" }
  ];
  const summary = dashboard.buildDealStageProgressSummary(interactionRecords, "2026-07-31", dashboard.DEFAULT_CONFIG);
  summary.forEach(function (row) { assert.equal(row["滞留企業数"], 0); });
});

test("buildDealStageProgressSummary: 対応履歴が空配列なら全工程0件", () => {
  const summary = dashboard.buildDealStageProgressSummary([], "2026-07-31", dashboard.DEFAULT_CONFIG);
  assert.deepEqual(summary, [
    { "工程": "NDA締結", "滞留企業数": 0, "平均滞留日数": 0 },
    { "工程": "意向表明受領", "滞留企業数": 0, "平均滞留日数": 0 },
    { "工程": "DD開始", "滞留企業数": 0, "平均滞留日数": 0 }
  ]);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_dashboard.test.mjs`
Expected: FAIL(`dashboard.buildDealStageProgressSummary is not a function`)

- [ ] **Step 3: `buildDealStageProgressSummary` を実装**

`glow-ma/src/dashboard.js` の`buildHistorySnapshot`の直後(`PARTNER_SUMMARY_FIELDS`定義より前)に追加する:

```js
  var DEAL_STAGE_TYPES = ["NDA締結", "意向表明受領", "DD開始"];

  function buildDealStageProgressSummary(interactionRecords, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var alerting = getGlowAlerting_();
    var latestByCompany = {};
    (interactionRecords || []).forEach(function (record) {
      if (DEAL_STAGE_TYPES.indexOf(record["種別"]) === -1) return;
      var companyId = record["企業ID"];
      if (!companyId) return;
      var current = latestByCompany[companyId];
      if (!current || record["日付"] > current["日付"]) {
        latestByCompany[companyId] = { "種別": record["種別"], "日付": record["日付"] };
      }
    });
    var daysListByStage = {};
    DEAL_STAGE_TYPES.forEach(function (type) { daysListByStage[type] = []; });
    Object.keys(latestByCompany).forEach(function (companyId) {
      var entry = latestByCompany[companyId];
      var days = alerting.daysBetween(entry["日付"], todayValue);
      daysListByStage[entry["種別"]].push(days || 0);
    });
    return DEAL_STAGE_TYPES.map(function (type) {
      var daysList = daysListByStage[type];
      var count = daysList.length;
      var avgDays = count > 0 ? Math.round(daysList.reduce(function (a, b) { return a + b; }, 0) / count) : 0;
      return { "工程": type, "滞留企業数": count, "平均滞留日数": avgDays };
    });
  }
```

**注意:** 日付の大小比較(`record["日付"] > current["日付"]`)は文字列比較になるが、対応履歴ログの「日付」は`YYYY-MM-DD`形式(既存の`alerting.js`の`toDate`と同じ前提)であるため、文字列比較でも日付の前後関係と一致する。この前提は既存コード(`ImportRunner.gs`等)全体で踏襲されているものであり、本Taskで新たに導入するものではない。

`api`オブジェクトに追加する:

```js
    buildDealStageProgressSummary: buildDealStageProgressSummary,
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_dashboard.test.mjs`
Expected: PASS(既存テスト + 新規4テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/dashboard.js tests/glow_ma_dashboard.test.mjs
git commit -m "feat(glow-ma): 工程別滞留状況(NDA締結/意向表明受領/DD開始)の集計ロジックを追加"
```

---

### Task 3: `DashboardRunner.gs` — 工程別滞留状況をダッシュボードに追加(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/DashboardRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema.INTERACTION_LOG_SHEET_NAME`(既存)、`readInteractionsByCompanyId_`(`ScoringRunner.gs`、GAS共有グローバル、既存)、`GlowDashboard.buildDealStageProgressSummary`(Task 2)
- Produces: `updateDashboard()`実行時、「ダッシュボード」タブに6番目のセクション「工程別滞留状況」が追加される

- [ ] **Step 1: `glow-ma/src/DashboardRunner.gs` を修正**

`updateDashboard()`関数冒頭のシート取得部分(`var historySheet = ...`の直後)に、対応履歴ログシートの取得を追加する:

```js
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  if (!logSheet) {
    throw new Error("対応履歴ログタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
```

`try`ブロック内、`var partnerRecords = readPartnerRecords_(partnerSheet);`の直後に、対応履歴ログの読み取りと集計を追加する(**`readInteractionsByCompanyId_`は`ScoringRunner.gs`で定義済みのGAS共有グローバル関数であり、ここで再定義しない**):

```js
    var interactionsByCompanyId = readInteractionsByCompanyId_(logSheet);
    var interactionRecords = [];
    Object.keys(interactionsByCompanyId).forEach(function (companyId) {
      interactionRecords = interactionRecords.concat(interactionsByCompanyId[companyId]);
    });
    var dealStageProgress = GlowDashboard.buildDealStageProgressSummary(interactionRecords, todayString, GlowDashboard.DEFAULT_CONFIG);
```

(`todayString`は既存の`var todayString = Utilities.formatDate(...)`をそのまま使う。新たに変数を作らない。)

既存の6セクション目である「データ品質チェック」の書き込み(`row++;`まで)の直後、`historySheet.appendRow([...]);`より前に、新しい7番目のセクション(通番としては6番目の業務セクション。ダッシュボード履歴タブへの追記は別カウント)を追加する:

```js
    row = writeDashboardSection_(dashboardSheet, row, "工程別滞留状況(NDA締結/意向表明受領/DD開始)",
      ["工程", "滞留企業数", "平均滞留日数"],
      dealStageProgress.map(function (d) { return [d["工程"], d["滞留企業数"], d["平均滞留日数"]]; }));
    row++;
```

ファイル冒頭のコメント(セクション一覧の箇条書き)に「工程別滞留状況」を追記する。

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/DashboardRunner.gs /tmp/DashboardRunner_p8_check.js && node --check /tmp/DashboardRunner_p8_check.js && rm /tmp/DashboardRunner_p8_check.js` で構文チェック
2. `readInteractionsByCompanyId_`が`ScoringRunner.gs`で定義されているシグネチャ(`readInteractionsByCompanyId_(sheet)`、企業IDをキーとしたレコード配列のマップを返す)と、ここでの呼び出しが一致していることを確認する
3. `GlowDashboard.buildDealStageProgressSummary`の引数順序(`interactionRecords, todayValue, config`)が呼び出しと一致していることを確認する
4. 新しいセクションの挿入位置が、既存の5セクション(ファネル・商品別・ランク別・パートナー別・データ品質チェック)の`row`計算や、`historySheet.appendRow(...)`・最終更新時刻の書き込みに影響しないことを確認する(`writeDashboardSection_`の戻り値を`row`に代入し`row++`する既存パターンをそのまま踏襲しているだけであることを確認)
5. 対応履歴ログが0件(新規セットアップ直後等)の場合、`readInteractionsByCompanyId_`は空オブジェクトを返し、`interactionRecords`は空配列になり、`buildDealStageProgressSummary([], ...)`は例外を投げずに3工程とも0件を返すことをコードを目でたどって確認する

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間がGoogleスプレッドシート上で確認する手順:

1. `clasp push` で反映
2. Apps Scriptエディタで `ensureLedgerTabs` を再実行し、対応履歴ログの「種別」プルダウンに「NDA締結」「意向表明受領」「DD開始」が追加されていることを確認する(**この再実行はダッシュボードタブの見出し行を一時的にプレースホルダーに戻すが、データ行・ダッシュボード履歴の蓄積データは消えない**。再度`updateDashboard`を実行すれば表示は元に戻る)
3. テスト用に数社分、対応履歴ログへ「NDA締結」等の種別で行を追加する
4. `updateDashboard` を実行する
5. 「ダッシュボード」タブに「工程別滞留状況」セクションが追加され、追加したテストデータに応じた滞留企業数・平均滞留日数が表示されることを確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/DashboardRunner.gs
git commit -m "feat(glow-ma): ダッシュボードに工程別滞留状況セクションを追加"
```

---

### Task 4: READMEにPhase 8の使い方を追記

**Files:**
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: Task 1〜3の全成果物
- Produces: GLOWチームが工程別滞留状況を運用できるようになるドキュメント

- [ ] **Step 1: `glow-ma/README.md` の「## 紹介パートナー成約率・ダッシュボード履歴(Phase 7)」の直後・「## 本番投入(実データ運用開始)前チェックリスト」の直前に以下を追記**

```markdown
## ディールステージ細分化・工程別滞留状況(Phase 8)

三名体制レビュー(`docs/superpowers/specs/2026-07-31-glow-ma-feature-brainstorm-triangle-review.md`)
論点1への対応。「現在ステージ」列(未接触/関係構築中/案件化/成約/見送り等の大分類)は
そのままに、M&Aの詳細な工程進捗(NDA→資料開示→意向表明(LOI)→DD→最終契約)を
対応履歴ログの「種別」で記録できるようにした。

**追加した種別**: 「NDA締結」「意向表明受領」「DD開始」を対応履歴ログの「種別」プルダウンに追加した。
案件が該当の工程に進んだ時点で、この種別で対応履歴ログに1行記録する。

**工程別滞留状況**: 「ダッシュボード」タブに新しいセクションを追加した。企業ごとに
最新の工程遷移イベント(3種別のうち日付が最も新しいもの)を「現在の工程」とみなし、
工程ごとに滞留企業数・平均滞留日数を集計する。

**使い方**

1. `clasp push` で最新コードを反映する
2. Apps Scriptエディタで `ensureLedgerTabs` を再実行し、種別プルダウンに新しい3種別を反映する
   (ダッシュボードタブの見出し行が一時的にプレースホルダーに戻るが、データは消えない)
3. 案件がNDA締結・意向表明受領・DD開始のいずれかの工程に進んだら、対応履歴ログにその種別で記録する
4. `updateDashboard` を実行すると、「ダッシュボード」タブに「工程別滞留状況」セクションが表示される

**現時点の制約:**
- 「現在の工程」は3種別のうち日付が最も新しいイベントで判定するため、工程が後戻りした場合
  (例: DD開始後に意向表明前の条件に差し戻された場合)、対応履歴ログにその旨を新しい日付で
  記録し直さない限り、見かけ上は最も進んだ工程のまま表示され続ける
- 不動産の工程(査定→媒介契約→販売活動→申込→契約→決済)は対象外。M&Aの3工程のみ
</markdown>
```

- [ ] **Step 2: `glow-ma/README.md` の「## 次のフェーズ」の内容を、Phase 8が実装済みになったことを反映して更新する**

- [ ] **Step 3: Commit**

```bash
git add glow-ma/README.md
git commit -m "docs(glow-ma): ディールステージ細分化・工程別滞留状況(Phase 8)の使い方をREADMEに追記"
```

---

## Self-Review

**Spec coverage:** `docs/superpowers/specs/2026-07-31-glow-ma-feature-brainstorm-triangle-review.md` 論点1(採用・ベッカイ案)→ Task 1, 2, 3

**Placeholder scan:** TBD/TODO等の記述なし。

**Type consistency:** `buildDealStageProgressSummary`は`getGlowAlerting_().daysBetween`(Phase 3で確定済みのシグネチャ)をそのまま呼び出しており、名前・引数の食い違いはない。`DashboardRunner.gs`での`readInteractionsByCompanyId_`の再利用は、`ScoringRunner.gs`で確定済みの実装をそのまま呼び出すのみで、フィールド名(企業ID/日付/種別)の不一致がないことをTask 3のレビューで確認する。`INTERACTION_TYPES`への追加は末尾追加であり、既存の`SheetSetup.gs`の`applyInteractionTypeValidation_`・`AlertRunner.gs`の反応イベント判定(`reactionPointsByType`)双方に影響しないことを確認する(新種別はどちらのキーにも含まれないため、既存の反応スコア集計・即時アラートの対象にはならない。これは意図した挙動であり、工程遷移イベントは反応スコアではなく滞留状況の可視化のみを目的とする)。
