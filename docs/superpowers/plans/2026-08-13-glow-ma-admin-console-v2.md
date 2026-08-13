# glow-ma 管理画面リッチ化(コンソールv2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GLOW企業リレーション台帳の管理画面(Web App、`glow-ma/src/adminApp.js`)を、過去に作成したデモ
(`glow-ma-console.html`)相当のリッチな見た目・機能(KPIサマリー・流入ルート表示・ネクストアクション優先順位・
担当者別ワークロード・Slack連携・レター下書きプレビュー)へ刷新する。

**Architecture:** 既存のUMD構成(`adminAccess.js`が純粋ロジック・Node/GASの両対応、`AdminRunner.gs`が薄い
GASラッパー、`adminApp.js`がHTML/JS文字列組み立て)をそのまま踏襲する。新規ロジックは可能な限り
`adminAccess.js`に置き、Nodeでテストする。既存の`alerting.js`(`isStale`等)・`ShareRunner.gs`
(`shareCompanyWithStaff`)は変更せずそのまま呼び出す。

**Tech Stack:** Google Apps Script (GAS) / Node.js(テストのみ)/ プレーンJS(フレームワークなし)/
`node --test`

## Global Constraints

- 企業マスタの読み取りは既存の`readCompanyRecords_`(`ImportRunner.gs`)をそのまま使う。新しい読み取り関数は作らない。
- `google.script.run`から呼ばれる公開関数は名前の末尾に`_`を付けない(付けるとApps Scriptが非公開扱いにし、
  エラーにもならず単に呼び出せなくなる。既存の`getCompanyList`等と同じ規約)。
- 各公開関数の冒頭で必ず`requireAdminAccess_()`を呼ぶ(多層防御、既存規約)。
- 純粋ロジック(日付計算・集計・フィルタ)は`adminAccess.js`に置き、UMD形式
  (`(function(global){...})(typeof window!=="undefined"?window:globalThis)`、
  `module.exports`/`global.GlowAdminAccess`)を守る。Node側テストは`tests/glow_ma_adminAccess.test.mjs`に追加する。
- `adminApp.js`のHTML/JS組み立ては既存の「文字列配列を`.join("")`で結合する」規約を踏襲する
  (改行のたびに配列要素を追加。既存コードと混在させない)。
- スコアリング(`scoring.js`)・アラート発報(`AlertRunner.gs`)・提案順序ロジックには一切手を触れない
  (設計書スコープ外)。
- 緊急度閾値(overdue=次回アクション予定日が本日以前、soon=3日以内、次回アクション予定日未設定=untouched)は
  三名体制レビュー2026-08-13で確定済み。変更しない。
- ワークロードパネルに「要偏り確認」等のフラグ表示は追加しない(三名体制レビュー2026-08-13論点2で見送り)。
- デモファイルの参照パス: `/tmp/claude-0/-home-user-hojo-hq/231f8613-ac8a-580b-9ce3-6dfd62ca2cdc/scratchpad/glow-ma-console.html`
  (このセッションのスクラッチパッドに実在する。見た目・マークアップを移植する際の一次情報源として使う)。
- 設計書: `docs/superpowers/specs/2026-08-13-glow-ma-admin-console-v2-design.md`

---

### Task 1: adminAccess.js — 企業一覧の列拡張・絞り込み拡張(流入ルート・提案商品)

**Files:**
- Modify: `glow-ma/src/adminAccess.js`
- Test: `tests/glow_ma_adminAccess.test.mjs`

**Interfaces:**
- Consumes: なし(既存の`company`レコード形式。`company["業種"]`, `company["所在地"]`,
  `company["流入ルート"]`(配列), `company["提案商品"]`(配列)は企業マスタに既存のフィールド)
- Produces: `COMPANY_LIST_FIELDS`(拡張済み配列)、`applyCompanyFilters(companies, filters)`
  (`filters.route`, `filters.product`に対応)。以降のタスクはこの拡張済み`COMPANY_LIST_FIELDS`と
  `applyCompanyFilters`のシグネチャをそのまま使う。

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_adminAccess.test.mjs`の末尾に追加:

```javascript
test("buildCompanyListResult: 業種・所在地・流入ルート・提案商品を含む", () => {
  const companies = [{
    "企業ID": "C000001", "会社名": "テスト建設", "ランク": "B", "現在ステージ": "未接触",
    "次回アクション予定日": "", "担当者": "", "業種": "建設業", "所在地": "沖縄県那覇市",
    "流入ルート": ["②手紙DM"], "提案商品": ["法人保険"]
  }];
  const result = adminAccess.buildCompanyListResult(companies, {});
  assert.equal(result[0]["業種"], "建設業");
  assert.equal(result[0]["所在地"], "沖縄県那覇市");
  assert.deepEqual(result[0]["流入ルート"], ["②手紙DM"]);
  assert.deepEqual(result[0]["提案商品"], ["法人保険"]);
});

test("applyCompanyFilters: 流入ルートで絞り込める", () => {
  const companies = [
    { "企業ID": "C1", "会社名": "A社", "流入ルート": ["①紹介"] },
    { "企業ID": "C2", "会社名": "B社", "流入ルート": ["②手紙DM"] }
  ];
  const result = adminAccess.applyCompanyFilters(companies, { route: "①紹介" });
  assert.equal(result.length, 1);
  assert.equal(result[0]["企業ID"], "C1");
});

test("applyCompanyFilters: 提案商品で絞り込める", () => {
  const companies = [
    { "企業ID": "C1", "会社名": "A社", "提案商品": ["M&A"] },
    { "企業ID": "C2", "会社名": "B社", "提案商品": ["法人保険"] }
  ];
  const result = adminAccess.applyCompanyFilters(companies, { product: "M&A" });
  assert.equal(result.length, 1);
  assert.equal(result[0]["企業ID"], "C1");
});

test("applyCompanyFilters: route/productとも未指定なら全件通す", () => {
  const companies = [
    { "企業ID": "C1", "会社名": "A社", "流入ルート": ["①紹介"], "提案商品": ["M&A"] }
  ];
  const result = adminAccess.applyCompanyFilters(companies, {});
  assert.equal(result.length, 1);
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: 上記4件のテストがFAIL(`業種`等が`undefined`、または`route`/`product`絞り込みが効かない)

- [ ] **Step 3: 実装する**

`glow-ma/src/adminAccess.js`の`COMPANY_LIST_FIELDS`と`pickCompanyListFields_`、`applyCompanyFilters`、
`hasAnyFilter`を以下のように変更する(既存の該当行を置き換え):

```javascript
  var COMPANY_LIST_FIELDS = [
    "企業ID", "会社名", "ランク", "現在ステージ", "次回アクション予定日", "担当者",
    "業種", "所在地", "流入ルート", "提案商品"
  ];
  var DEFAULT_LIST_LIMIT = 100;

  function pickCompanyListFields_(company) {
    var picked = {};
    COMPANY_LIST_FIELDS.forEach(function (field) {
      picked[field] = company[field] !== undefined ? company[field] : "";
    });
    picked["次回アクション予定日"] = normalizeDateForDisplay(company["次回アクション予定日"]);
    picked["流入ルート"] = company["流入ルート"] || [];
    picked["提案商品"] = company["提案商品"] || [];
    return picked;
  }

  function hasAnyFilter(filters) {
    var f = filters || {};
    return !!(String(f.search || "").trim() || f.rank || f.stage || f.owner || f.route || f.product);
  }

  function applyCompanyFilters(companies, filters) {
    var f = filters || {};
    var searchTerm = String(f.search || "").trim().toLowerCase();
    return (companies || []).filter(function (company) {
      if (searchTerm) {
        var name = String(company["会社名"] || "").toLowerCase();
        var rep = String(company["代表者名"] || "").toLowerCase();
        if (name.indexOf(searchTerm) === -1 && rep.indexOf(searchTerm) === -1) return false;
      }
      if (f.rank && company["ランク"] !== f.rank) return false;
      if (f.stage && company["現在ステージ"] !== f.stage) return false;
      if (f.owner && company["担当者"] !== f.owner) return false;
      if (f.route && (company["流入ルート"] || []).indexOf(f.route) === -1) return false;
      if (f.product && (company["提案商品"] || []).indexOf(f.product) === -1) return false;
      return true;
    });
  }
```

`var api = {...}`の中の`COMPANY_LIST_FIELDS`はそのまま(参照が変わるだけで、key自体は変更不要)。

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/adminAccess.js tests/glow_ma_adminAccess.test.mjs
git commit -m "feat(glow-ma): 企業一覧に業種・所在地・流入ルート・提案商品を追加し絞り込みを拡張"
```

---

### Task 2: adminAccess.js — 緊急度判定(computeUrgency)

**Files:**
- Modify: `glow-ma/src/adminAccess.js`
- Test: `tests/glow_ma_adminAccess.test.mjs`

**Interfaces:**
- Consumes: `glow-ma/src/alerting.js`の`GlowAlerting.toDate(value)` / `GlowAlerting.daysBetween(fromValue, toValue)`
  (既存、変更しない)
- Produces: `computeUrgency(company, todayString)` → `"none" | "untouched" | "overdue" | "soon" | "ok"`。
  Task 3・5がこの関数を使う。

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_adminAccess.test.mjs`に追加:

```javascript
test("computeUrgency: 連絡不要企業はnone", () => {
  const company = { "連絡不要": true, "次回アクション予定日": "2026-08-01" };
  assert.equal(adminAccess.computeUrgency(company, "2026-08-13"), "none");
});

test("computeUrgency: 次回アクション予定日が未設定ならuntouched", () => {
  const company = { "連絡不要": false, "次回アクション予定日": "" };
  assert.equal(adminAccess.computeUrgency(company, "2026-08-13"), "untouched");
});

test("computeUrgency: 次回アクション予定日が本日以前ならoverdue", () => {
  const company = { "次回アクション予定日": "2026-08-13" };
  assert.equal(adminAccess.computeUrgency(company, "2026-08-13"), "overdue");
  const past = { "次回アクション予定日": "2026-08-01" };
  assert.equal(adminAccess.computeUrgency(past, "2026-08-13"), "overdue");
});

test("computeUrgency: 3日以内ならsoon", () => {
  const company = { "次回アクション予定日": "2026-08-16" };
  assert.equal(adminAccess.computeUrgency(company, "2026-08-13"), "soon");
});

test("computeUrgency: 4日以上先ならok", () => {
  const company = { "次回アクション予定日": "2026-08-20" };
  assert.equal(adminAccess.computeUrgency(company, "2026-08-13"), "ok");
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: `adminAccess.computeUrgency is not a function` でFAIL

- [ ] **Step 3: 実装する**

`glow-ma/src/adminAccess.js`の`getGlowAlerting_()`定義の直後に追加:

```javascript
  function computeUrgency(company, todayString) {
    if (company["連絡不要"] === true) return "none";
    var nextDate = company["次回アクション予定日"];
    if (!nextDate) return "untouched";
    var diffDays = getGlowAlerting_().daysBetween(todayString, nextDate);
    if (diffDays === null) return "untouched";
    if (diffDays <= 0) return "overdue";
    if (diffDays <= 3) return "soon";
    return "ok";
  }
```

`var api = {...}`に`computeUrgency: computeUrgency,`を追加する。

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/adminAccess.js tests/glow_ma_adminAccess.test.mjs
git commit -m "feat(glow-ma): 管理画面の緊急度判定computeUrgencyを追加(三名体制レビュー2026-08-13)"
```

---

### Task 3: adminAccess.js — KPIサマリー集計(buildKpiSummary)

**Files:**
- Modify: `glow-ma/src/adminAccess.js`
- Test: `tests/glow_ma_adminAccess.test.mjs`

**Interfaces:**
- Consumes: `computeUrgency(company, todayString)`(Task 2)、`getGlowAlerting_().buildStaleList(companies, todayString)`(既存)
- Produces: `buildKpiSummary(companies, todayString)` →
  `{ total, overdueOrUntouched, hot, byRank: {A,B,C,D}, deal, stale }`。Task 6のAdminRunner.gsラッパーが
  この戻り値をそのまま`getKpiSummary()`のレスポンスにする。`hot`判定は`company["本日反応あり"]`という
  真偽値フィールドを引数レコードが持っている前提とする(この値の算出はTask 6でAdminRunner.gs側が
  対応履歴ログと突き合わせて付与する。adminAccess.js側はこのフィールドを読むだけで対応履歴ログ自体は読まない)。

- [ ] **Step 1: 失敗するテストを書く**

```javascript
test("buildKpiSummary: 各項目を正しく集計する", () => {
  const today = "2026-08-13";
  const companies = [
    { "企業ID": "C1", "ランク": "A", "現在ステージ": "提案中", "次回アクション予定日": "2026-08-01",
      "連絡不要": false, "本日反応あり": false, "最終接触日": "2026-01-01", "登録日": "2026-01-01" },
    { "企業ID": "C2", "ランク": "B", "現在ステージ": "未接触", "次回アクション予定日": "",
      "連絡不要": false, "本日反応あり": true, "最終接触日": "", "登録日": "2026-08-10" },
    { "企業ID": "C3", "ランク": "D", "現在ステージ": "案件化", "次回アクション予定日": "2026-08-20",
      "連絡不要": false, "本日反応あり": false, "最終接触日": "2020-01-01", "登録日": "2020-01-01" }
  ];
  const summary = adminAccess.buildKpiSummary(companies, today);
  assert.equal(summary.total, 3);
  assert.equal(summary.overdueOrUntouched, 2); // C1(overdue) + C2(untouched)
  assert.equal(summary.hot, 1); // C2
  assert.deepEqual(summary.byRank, { A: 1, B: 1, C: 0, D: 1 });
  assert.equal(summary.deal, 2); // C1(提案中) + C3(案件化)
  assert.equal(summary.stale, 1); // C3: 最終接触2020年、標準サイクル(D=365日)の2倍以上経過
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: `adminAccess.buildKpiSummary is not a function` でFAIL

- [ ] **Step 3: 実装する**

`computeUrgency`の直後に追加:

```javascript
  function buildKpiSummary(companies, todayString) {
    var list = companies || [];
    var byRank = { A: 0, B: 0, C: 0, D: 0 };
    var overdueOrUntouched = 0;
    var hot = 0;
    var deal = 0;
    var dealStages = ["提案中", "案件化"];
    list.forEach(function (company) {
      var rank = company["ランク"];
      if (byRank[rank] !== undefined) byRank[rank]++;
      var urgency = computeUrgency(company, todayString);
      if (urgency === "overdue" || urgency === "untouched") overdueOrUntouched++;
      if (company["本日反応あり"]) hot++;
      if (dealStages.indexOf(company["現在ステージ"]) !== -1) deal++;
    });
    var stale = getGlowAlerting_().buildStaleList(list, todayString).length;
    return {
      total: list.length,
      overdueOrUntouched: overdueOrUntouched,
      hot: hot,
      byRank: byRank,
      deal: deal,
      stale: stale
    };
  }
```

`var api = {...}`に`buildKpiSummary: buildKpiSummary,`を追加する。

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/adminAccess.js tests/glow_ma_adminAccess.test.mjs
git commit -m "feat(glow-ma): KPIサマリー集計buildKpiSummaryを追加"
```

---

### Task 4: adminAccess.js — 担当者別ワークロード集計(buildOwnerWorkload)

**Files:**
- Modify: `glow-ma/src/adminAccess.js`
- Test: `tests/glow_ma_adminAccess.test.mjs`

**Interfaces:**
- Consumes: `computeUrgency(company, todayString)`(Task 2)
- Produces: `buildOwnerWorkload(companies, todayString)` → 配列
  `[{ owner: string, total: number, overdueOrUntouched: number }]`(担当者ごと、`total`降順)。
  担当者が空文字の企業は除外する。フラグ表示(要偏り確認等)は含めない
  (三名体制レビュー2026-08-13論点2により見送り)。

- [ ] **Step 1: 失敗するテストを書く**

```javascript
test("buildOwnerWorkload: 担当者ごとに集計し、担当数の多い順に並べる", () => {
  const today = "2026-08-13";
  const companies = [
    { "企業ID": "C1", "担当者": "福田", "次回アクション予定日": "2026-08-01", "連絡不要": false },
    { "企業ID": "C2", "担当者": "福田", "次回アクション予定日": "2026-08-20", "連絡不要": false },
    { "企業ID": "C3", "担当者": "宮城", "次回アクション予定日": "", "連絡不要": false },
    { "企業ID": "C4", "担当者": "", "次回アクション予定日": "2026-08-01", "連絡不要": false }
  ];
  const result = adminAccess.buildOwnerWorkload(companies, today);
  assert.equal(result.length, 2); // 担当者未設定(C4)は除外
  assert.equal(result[0].owner, "福田");
  assert.equal(result[0].total, 2);
  assert.equal(result[0].overdueOrUntouched, 1); // C1のみoverdue
  assert.equal(result[1].owner, "宮城");
  assert.equal(result[1].total, 1);
  assert.equal(result[1].overdueOrUntouched, 1); // C3はuntouched
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: `adminAccess.buildOwnerWorkload is not a function` でFAIL

- [ ] **Step 3: 実装する**

`buildKpiSummary`の直後に追加:

```javascript
  function buildOwnerWorkload(companies, todayString) {
    var counts = {};
    var order = [];
    (companies || []).forEach(function (company) {
      var owner = company["担当者"];
      if (!owner) return;
      if (!counts[owner]) {
        counts[owner] = { owner: owner, total: 0, overdueOrUntouched: 0 };
        order.push(owner);
      }
      counts[owner].total++;
      var urgency = computeUrgency(company, todayString);
      if (urgency === "overdue" || urgency === "untouched") counts[owner].overdueOrUntouched++;
    });
    return order.map(function (owner) { return counts[owner]; })
      .sort(function (a, b) { return b.total - a.total; });
  }
```

`var api = {...}`に`buildOwnerWorkload: buildOwnerWorkload,`を追加する。

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/adminAccess.js tests/glow_ma_adminAccess.test.mjs
git commit -m "feat(glow-ma): 担当者別ワークロード集計buildOwnerWorkloadを追加"
```

---

### Task 5: adminAccess.js — 本日のネクストアクション一覧(buildNextActionQueue)

**Files:**
- Modify: `glow-ma/src/adminAccess.js`
- Test: `tests/glow_ma_adminAccess.test.mjs`

**Interfaces:**
- Consumes: `computeUrgency(company, todayString)`(Task 2)
- Produces: `buildNextActionQueue(companies, todayString, limit)` → `company`オブジェクトの配列
  (`limit`件まで、`本日反応あり`→`untouched`→`overdue`→`soon`の優先順)。`limit`省略時は8。
  各要素は元の`company`オブジェクトに`urgency`キーを追加したもの(呼び出し元でそのまま表示に使えるように)。

- [ ] **Step 1: 失敗するテストを書く**

```javascript
test("buildNextActionQueue: 反応あり→未着手→期限超過→まもなくの順に並べ、上限件数で切る", () => {
  const today = "2026-08-13";
  const companies = [
    { "企業ID": "C_ok", "次回アクション予定日": "2026-09-01", "連絡不要": false, "本日反応あり": false },
    { "企業ID": "C_soon", "次回アクション予定日": "2026-08-15", "連絡不要": false, "本日反応あり": false },
    { "企業ID": "C_overdue", "次回アクション予定日": "2026-08-01", "連絡不要": false, "本日反応あり": false },
    { "企業ID": "C_untouched", "次回アクション予定日": "", "連絡不要": false, "本日反応あり": false },
    { "企業ID": "C_hot", "次回アクション予定日": "2026-09-01", "連絡不要": false, "本日反応あり": true }
  ];
  const result = adminAccess.buildNextActionQueue(companies, today, 8);
  const ids = result.map(function (c) { return c["企業ID"]; });
  assert.deepEqual(ids, ["C_hot", "C_untouched", "C_overdue", "C_soon"]); // C_okは対象外
  assert.equal(result[0].urgency, "ok"); // C_hotは次回アクション予定日自体はok
  assert.equal(result[1].urgency, "untouched");
});

test("buildNextActionQueue: limitで件数を絞る", () => {
  const today = "2026-08-13";
  const companies = [
    { "企業ID": "C1", "次回アクション予定日": "", "連絡不要": false },
    { "企業ID": "C2", "次回アクション予定日": "", "連絡不要": false },
    { "企業ID": "C3", "次回アクション予定日": "", "連絡不要": false }
  ];
  const result = adminAccess.buildNextActionQueue(companies, today, 2);
  assert.equal(result.length, 2);
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: `adminAccess.buildNextActionQueue is not a function` でFAIL

- [ ] **Step 3: 実装する**

`buildOwnerWorkload`の直後に追加:

```javascript
  var URGENCY_ORDER_ = { overdue: 0, untouched: 0, soon: 1, ok: 2, none: 3 };

  function buildNextActionQueue(companies, todayString, limit) {
    var max = typeof limit === "number" ? limit : 8;
    var candidates = (companies || [])
      .map(function (company) {
        var urgency = computeUrgency(company, todayString);
        var withUrgency = {};
        Object.keys(company).forEach(function (key) { withUrgency[key] = company[key]; });
        withUrgency.urgency = urgency;
        return withUrgency;
      })
      .filter(function (company) {
        return company["本日反応あり"] || company.urgency === "overdue" ||
          company.urgency === "untouched" || company.urgency === "soon";
      });
    candidates.sort(function (a, b) {
      if (!!a["本日反応あり"] !== !!b["本日反応あり"]) return a["本日反応あり"] ? -1 : 1;
      return URGENCY_ORDER_[a.urgency] - URGENCY_ORDER_[b.urgency];
    });
    return candidates.slice(0, max);
  }
```

`var api = {...}`に`buildNextActionQueue: buildNextActionQueue,`を追加する。

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/adminAccess.js tests/glow_ma_adminAccess.test.mjs
git commit -m "feat(glow-ma): 本日のネクストアクション一覧buildNextActionQueueを追加"
```

---

### Task 6: AdminRunner.gs — getKpiSummary/getOwnerWorkload/getNextActionQueue + getFilterOptions拡張

**Files:**
- Modify: `glow-ma/src/AdminRunner.gs`

**Interfaces:**
- Consumes: `readCompanyRecords_`(既存)、`GlowAdminAccess.buildKpiSummary/buildOwnerWorkload/buildNextActionQueue`
  (Task 3〜5)、`GlowSchema.INTERACTION_LOG_SHEET_NAME`(既存)
- Produces: `getKpiSummary()` / `getOwnerWorkload()` / `getNextActionQueue()` (すべて`google.script.run`から
  呼べる公開関数)。`getFilterOptions()`が`routes`/`products`を追加で返す。Task 10〜11のadminApp.jsが
  これらをそのまま呼ぶ。

Node環境ではGAS依存(`SpreadsheetApp`等)のため実行できない。この関数群はNode側テスト対象外
(既存の`AdminRunner.gs`内の他関数と同じ扱い)。本番投入前の目視確認で担保する。

- [ ] **Step 1: 実装する(テストなし。GAS依存のため)**

`glow-ma/src/AdminRunner.gs`の`getFilterOptions()`関数を以下に置き換える:

```javascript
function getFilterOptions() {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];

  var stageSet = {};
  var ownerSet = {};
  var routeSet = {};
  var productSet = {};
  companies.forEach(function (company) {
    if (company["現在ステージ"]) stageSet[company["現在ステージ"]] = true;
    if (company["担当者"]) ownerSet[company["担当者"]] = true;
    (company["流入ルート"] || []).forEach(function (route) { routeSet[route] = true; });
    (company["提案商品"] || []).forEach(function (product) { productSet[product] = true; });
  });

  return {
    stages: Object.keys(stageSet).sort(),
    owners: Object.keys(ownerSet).sort(),
    routes: Object.keys(routeSet).sort(),
    products: Object.keys(productSet).sort()
  };
}
```

同ファイルに、`getFilterOptions()`の直後、次の3関数を新規追加する。「本日反応あり」の判定は
対応履歴ログを読み、本日日付の行がある企業IDの集合を作って付与する:

```javascript
/**
 * 対応履歴ログから、本日日付の行がある企業IDの集合を返す(即時アラート/KPIの「hot」判定用)。
 */
function buildTodayReactedCompanyIdSet_(logSheet, todayString) {
  var result = {};
  if (!logSheet) return result;
  var lastRow = logSheet.getLastRow();
  if (lastRow < 2) return result;
  var headers = GlowSchema.INTERACTION_LOG_HEADERS;
  var dateIndex = headers.indexOf("日付");
  var idIndex = headers.indexOf("企業ID");
  var values = logSheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  values.forEach(function (row) {
    var companyId = row[idIndex];
    if (!companyId) return;
    var dateValue = row[dateIndex];
    var dateString = dateValue instanceof Date
      ? Utilities.formatDate(dateValue, "Asia/Tokyo", "yyyy-MM-dd")
      : String(dateValue || "");
    if (dateString === todayString) result[companyId] = true;
  });
  return result;
}

function loadCompaniesWithReactionFlag_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var reactedSet = buildTodayReactedCompanyIdSet_(logSheet, todayString);
  companies.forEach(function (company) {
    company["本日反応あり"] = !!reactedSet[company["企業ID"]];
  });
  return { companies: companies, todayString: todayString };
}

function getKpiSummary() {
  requireAdminAccess_();
  var loaded = loadCompaniesWithReactionFlag_();
  return GlowAdminAccess.buildKpiSummary(loaded.companies, loaded.todayString);
}

function getOwnerWorkload() {
  requireAdminAccess_();
  var loaded = loadCompaniesWithReactionFlag_();
  return GlowAdminAccess.buildOwnerWorkload(loaded.companies, loaded.todayString);
}

function getNextActionQueue() {
  requireAdminAccess_();
  var loaded = loadCompaniesWithReactionFlag_();
  return GlowAdminAccess.buildNextActionQueue(loaded.companies, loaded.todayString, 8);
}
```

- [ ] **Step 2: 構文チェック**

Apps Scriptエディタへの反映は本番投入時に行うため、ここではNode上で構文エラーがないことだけを
簡易確認する。

Run: `node --check glow-ma/src/AdminRunner.gs 2>&1 || echo "GAS構文のためnode --checkはfalse positiveの可能性あり。目視確認する"`

(`SpreadsheetApp`等のGASグローバルが未定義のため`node --check`は構文レベルのチェックのみ有効。
`{`/`}`の対応、セミコロン漏れ等がないか目視でも確認すること。)

- [ ] **Step 3: コミット**

```bash
git add glow-ma/src/AdminRunner.gs
git commit -m "feat(glow-ma): getKpiSummary/getOwnerWorkload/getNextActionQueueを追加、getFilterOptionsに流入ルート・商品を追加"
```

---

### Task 7: AdminRunner.gs — getShareableStaffList + getLatestLetterDraft

**Files:**
- Modify: `glow-ma/src/AdminRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema.STAFF_HEADERS` / `GlowSchema.STAFF_SHEET_NAME`(既存)、
  `GlowSchema.LETTER_DRAFT_HEADERS` / `GlowSchema.LETTER_DRAFT_SHEET_NAME`(既存)
- Produces: `getShareableStaffList()` → `[{name, slackUserId}]`、
  `getLatestLetterDraft(companyId)` → `{生成日時, 本文, ステータス} | null`。Task 12・13のadminApp.jsが呼ぶ。

- [ ] **Step 1: 実装する(テストなし。GAS依存のため)**

`glow-ma/src/AdminRunner.gs`の`getNextActionQueue()`の直後に追加:

```javascript
/**
 * ドロワーの🤝連携ボタン用。ShareRunner.gsのreadActiveStaff_と同じロジックだが、
 * 呼び出し元(スプレッドシートメニュー vs Web App)が異なるため、末尾に`_`を付けない
 * 公開関数として別途用意する(google.script.runから呼ぶため)。
 */
function getShareableStaffList() {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(GlowSchema.STAFF_SHEET_NAME);
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.STAFF_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var nameIndex = headers.indexOf("氏名");
  var slackIdIndex = headers.indexOf("Slack User ID");
  var activeIndex = headers.indexOf("有効");
  return values
    .filter(function (row) { return row[activeIndex] === true && row[nameIndex] && row[slackIdIndex]; })
    .map(function (row) { return { name: row[nameIndex], slackUserId: row[slackIdIndex] }; });
}

/**
 * 企業1社分の最新レター下書き(生成日時が最も新しい行)を返す。存在しなければnull。
 */
function getLatestLetterDraft(companyId) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(GlowSchema.LETTER_DRAFT_SHEET_NAME);
  if (!sheet) return null;
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return null;
  var headers = GlowSchema.LETTER_DRAFT_HEADERS;
  var idIndex = headers.indexOf("企業ID");
  var dateIndex = headers.indexOf("生成日時");
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var latest = null;
  values.forEach(function (row) {
    if (row[idIndex] !== companyId) return;
    var record = {};
    headers.forEach(function (header, i) { record[header] = row[i]; });
    if (!latest) { latest = record; return; }
    var currentDate = row[dateIndex] instanceof Date ? row[dateIndex] : new Date(row[dateIndex]);
    var latestDate = latest["生成日時"] instanceof Date ? latest["生成日時"] : new Date(latest["生成日時"]);
    if (currentDate > latestDate) latest = record;
  });
  return latest;
}
```

- [ ] **Step 2: 構文の目視確認**

`{`/`}`の対応、既存関数との名前衝突がないことを確認する(`getShareableStaffList`・
`getLatestLetterDraft`という名前が既存コードに存在しないことを`grep -rn "function getShareableStaffList\|function getLatestLetterDraft" glow-ma/src/`で確認する)。

- [ ] **Step 3: コミット**

```bash
git add glow-ma/src/AdminRunner.gs
git commit -m "feat(glow-ma): getShareableStaffList・getLatestLetterDraftを追加"
```

---

### Task 8: adminApp.js — ビジュアル刷新(コーポレートカラー・光るロゴ・カード型KPI等のCSS移植)

**Files:**
- Modify: `glow-ma/src/adminApp.js`
- Test: `tests/glow_ma_adminApp.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `STYLE`定数(デモ相当のCSS)。以降のタスクが使うCSSクラス名
  (`.kpi`, `.rank-A`〜`.rank-D`, `.dot.overdue`/`.soon`/`.ok`/`.none`, `.queue-item`, `.workload-row`,
  `.drawer`, `.km-*`(KPIモーダル), `.topbar-logo`)はこのタスクで定義される。

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_adminApp.test.mjs`に追加:

```javascript
test("buildAdminAppHtml: コーポレートカラーの変数とロゴのアニメーションを含む", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf("--kin:#F88800") !== -1 || html.indexOf("--kin: #F88800") !== -1,
    "コーポレートカラー(金)が定義されていない");
  assert.ok(html.indexOf("logoGlow") !== -1, "ロゴの光るアニメーションが定義されていない");
  assert.ok(html.indexOf("prefers-reduced-motion") !== -1, "reduced-motion対応がない");
});

test("buildAdminAppHtml: KPIカード・緊急度ドット・ランクバッジ用のCSSクラスを含む", () => {
  const html = adminApp.buildAdminAppHtml();
  [".kpi{", ".rank-A{", ".rank-B{", ".rank-C{", ".rank-D{", ".dot.overdue{", ".dot.soon{", ".dot.ok{"]
    .forEach((selector) => {
      assert.ok(html.indexOf(selector) !== -1, selector + " が定義されていない");
    });
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: 上記2件がFAIL(現在のSTYLEにこれらのクラス・変数がないため)

- [ ] **Step 3: 実装する**

デモファイル(`/tmp/claude-0/-home-user-hojo-hq/231f8613-ac8a-580b-9ce3-6dfd62ca2cdc/scratchpad/glow-ma-console.html`)
の1〜434行目(`<title>`直後の`<style>`から`</style>`まで)を読み、その内容を`glow-ma/src/adminApp.js`の
`STYLE`配列の内容として移植する。移植手順:

1. デモファイルの2〜434行目(`<style>`の中身、`<title>`と`<style>`タグ自体は除く)を読む
2. 各CSS行を`adminApp.js`の`STYLE = [...]`配列の1要素(ダブルクォートで囲んだ文字列、末尾カンマ)に変換する
   (既存の`STYLE`配列と同じ形式。1行が長い場合はデモ通りの改行位置で複数のJS文字列に分割してよい)
3. `glow-ma/src/adminApp.js`の現在の`var STYLE = [...].join("");`(14〜65行目)を、変換したCSS全体で置き換える
4. デモのCSSは`.filters`, `.kpi`, `.rank-A`等、既存の`adminApp.js`のクラス名(`.filters`, `.rank`等)と
   重複するセレクタがある。デモ側の定義で完全に置き換える(既存の簡素なCSSは破棄する)
5. `.topbar`, `.brand`, `.demo-badge`(「UIデモ(モックデータ)」の表示)はデモ固有の要素なので、
   `.demo-badge`関連のCSSクラス定義自体は残してよいが、本番のHTML(Task 9で書き換える`HEADER_AND_FILTERS`)
   では`.demo-badge`要素そのものを使わない(本番データを扱うため「デモ」表示は不要)

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: 全件PASS(既存テストも含め、STYLEの変更でHTML構造自体は壊れていないため他のテストも通ること)

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/adminApp.js tests/glow_ma_adminApp.test.mjs
git commit -m "style(glow-ma): 管理画面にコーポレートカラー・光るロゴ・カード型KPI用CSSを移植"
```

---

### Task 9: adminApp.js — 企業一覧テーブルの列拡張・ソート・絞り込みUI

**Files:**
- Modify: `glow-ma/src/adminApp.js`
- Test: `tests/glow_ma_adminApp.test.mjs`

**Interfaces:**
- Consumes: `getCompanyList(filters)`(既存、Task 1でサーバー側の返り値が拡張済み)、
  `getFilterOptions()`(Task 6で`routes`/`products`が追加済み)
- Produces: 絞り込みUI要素`id="filterRoute"` / `id="filterProduct"`、テーブル列見出し
  `data-sort="name|biz|route|stage|products|rank|next"`。Task 10〜13はこのテーブル構造を変更しない。

- [ ] **Step 1: 失敗するテストを書く**

```javascript
test("buildAdminAppHtml: 流入ルート・提案商品の絞り込みと、列ソート用の見出しを含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["filterRoute", "filterProduct"].forEach((id) => {
    assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
  });
  ["data-sort=\"name\"", "data-sort=\"biz\"", "data-sort=\"route\"", "data-sort=\"stage\"",
   "data-sort=\"products\"", "data-sort=\"rank\"", "data-sort=\"next\""]
    .forEach((attr) => {
      assert.ok(html.indexOf(attr) !== -1, attr + " が含まれていない");
    });
});

test("buildAdminAppHtml: google.script.runでgetFilterOptionsの結果からroute/product選択肢を組み立てる", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf("options.routes") !== -1, "流入ルート選択肢の組み立てがない");
  assert.ok(html.indexOf("options.products") !== -1, "提案商品選択肢の組み立てがない");
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: FAIL(`filterRoute`等が存在しない)

- [ ] **Step 3: 実装する**

`glow-ma/src/adminApp.js`の`HEADER_AND_FILTERS`定数を以下に置き換える:

```javascript
  var HEADER_AND_FILTERS = [
    "<header><h1>GLOW企業リレーション台帳</h1></header>",
    "<div id=\"viewSwitcher\"><button id=\"viewCompanyBtn\" class=\"active\">企業一覧</button>",
    "<button id=\"viewPartnerBtn\">紹介パートナー開拓状況</button></div>",
    "<div class=\"filters\" id=\"companyFiltersBar\">",
    "<input type=\"text\" id=\"searchInput\" placeholder=\"会社名・代表者名で検索\">",
    "<select id=\"filterRank\"><option value=\"\">ランク(すべて)</option>",
    "<option value=\"A\">A</option><option value=\"B\">B</option>",
    "<option value=\"C\">C</option><option value=\"D\">D</option></select>",
    "<select id=\"filterStage\"><option value=\"\">現在ステージ(すべて)</option></select>",
    "<select id=\"filterOwner\"><option value=\"\">担当者(すべて)</option></select>",
    "<select id=\"filterRoute\"><option value=\"\">流入ルート(すべて)</option></select>",
    "<select id=\"filterProduct\"><option value=\"\">提案商品(すべて)</option></select>",
    "</div>"
  ].join("");
```

`TABLE`定数を以下に置き換える:

```javascript
  var TABLE = [
    "<div id=\"companyView\" class=\"viewPane active\">",
    "<table><thead><tr>",
    "<th data-sort=\"name\">会社名/代表者</th>",
    "<th data-sort=\"biz\">業種・所在地</th>",
    "<th data-sort=\"route\">流入ルート</th>",
    "<th data-sort=\"stage\">現在ステージ</th>",
    "<th data-sort=\"products\">提案商品</th>",
    "<th data-sort=\"rank\">ランク</th>",
    "<th data-sort=\"next\">次回アクション</th>",
    "</tr></thead>",
    "<tbody id=\"companyTableBody\"></tbody></table>",
    "<div class=\"empty\" id=\"emptyState\" style=\"display:none\">該当する企業が見つかりません</div>",
    "</div>"
  ].join("");
```

`SCRIPT`定数内、`loadFilterOptions()`関数を以下に置き換える:

```javascript
    "function loadFilterOptions(){",
    "google.script.run.withSuccessHandler(function(options){",
    "var stageSelect = document.getElementById('filterStage');",
    "(options.stages||[]).forEach(function(stage){",
    "var opt = document.createElement('option'); opt.value = stage; opt.textContent = stage;",
    "stageSelect.appendChild(opt);});",
    "var ownerSelect = document.getElementById('filterOwner');",
    "(options.owners||[]).forEach(function(owner){",
    "var opt = document.createElement('option'); opt.value = owner; opt.textContent = owner;",
    "ownerSelect.appendChild(opt);});",
    "var routeSelect = document.getElementById('filterRoute');",
    "(options.routes||[]).forEach(function(route){",
    "var opt = document.createElement('option'); opt.value = route; opt.textContent = route;",
    "routeSelect.appendChild(opt);});",
    "var productSelect = document.getElementById('filterProduct');",
    "(options.products||[]).forEach(function(product){",
    "var opt = document.createElement('option'); opt.value = product; opt.textContent = product;",
    "productSelect.appendChild(opt);});",
    "}).withFailureHandler(function(){}).getFilterOptions();",
    "}",
```

`renderTable(rows)`関数を以下に置き換える(バッジ表示・列追加):

```javascript
    "function renderTable(rows){",
    "var tbody = document.getElementById('companyTableBody'); tbody.innerHTML = '';",
    "var empty = document.getElementById('emptyState');",
    "if (!rows || rows.length === 0){ empty.style.display = 'block';",
    "empty.textContent = '該当する企業が見つかりません'; return; }",
    "empty.style.display = 'none';",
    "rows.forEach(function(row){",
    "var tr = document.createElement('tr');",
    "var routeBadges = (row['流入ルート']||[]).map(function(r){ return '<span class=\"badge route-1\">'+escapeHtml(r)+'</span>'; }).join('');",
    "var productBadges = (row['提案商品']||[]).map(function(p){ return '<span class=\"badge prod\">'+escapeHtml(p)+'</span>'; }).join('');",
    "tr.innerHTML = '<td><div class=\"co-name\">' + escapeHtml(row['会社名']) + '</div></td>' +",
    "'<td>' + escapeHtml(row['業種']) + '<div class=\"co-sub\">' + escapeHtml(row['所在地']) + '</div></td>' +",
    "'<td><div class=\"badge-row\">' + routeBadges + '</div></td>' +",
    "'<td>' + escapeHtml(row['現在ステージ']) + '</td>' +",
    "'<td><div class=\"badge-row\">' + productBadges + '</div></td>' +",
    "'<td><span class=\"rank rank-' + escapeHtml(row['ランク']) + '\">' + escapeHtml(row['ランク']) + '</span></td>' +",
    "'<td>' + escapeHtml(row['次回アクション予定日']) + '</td>';",
    "tr.addEventListener('click', function(){ openDrawer(row['企業ID']); });",
    "tbody.appendChild(tr);});",
    "}",
```

`currentFilters`の初期値を絞り込み項目追加に合わせて拡張し、フィルタ変更イベントも追加する(ファイル末尾の
イベントリスナー登録部分に、既存の`filterOwner`のリスナー登録の直後へ追加):

```javascript
    "document.getElementById('filterRoute').addEventListener('change', function(e){",
    "currentFilters.route = e.target.value; loadList(); });",
    "document.getElementById('filterProduct').addEventListener('change', function(e){",
    "currentFilters.product = e.target.value; loadList(); });",
```

`var currentFilters = { search: '', rank: '', stage: '', owner: '' };`を
`var currentFilters = { search: '', rank: '', stage: '', owner: '', route: '', product: '' };`に変更する。

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/adminApp.js tests/glow_ma_adminApp.test.mjs
git commit -m "feat(glow-ma): 企業一覧テーブルに流入ルート・提案商品列と絞り込みを追加"
```

---

### Task 10: adminApp.js — KPI行 + 内訳モーダル

**Files:**
- Modify: `glow-ma/src/adminApp.js`
- Test: `tests/glow_ma_adminApp.test.mjs`

**Interfaces:**
- Consumes: `getKpiSummary()`(Task 6)
- Produces: `id="kpiRow"`, `id="kpiModal"`。行内の各カードクリックでモーダルを開く。

- [ ] **Step 1: 失敗するテストを書く**

```javascript
test("buildAdminAppHtml: KPI行とKPIモーダルの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["kpiRow", "kpiModal", "kmTitle", "kmSub", "kmBody"].forEach((id) => {
    assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
  });
});

test("buildAdminAppHtml: google.script.runでgetKpiSummaryを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getKpiSummary(") !== -1);
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: FAIL

- [ ] **Step 3: 実装する**

`glow-ma/src/adminApp.js`に新しい定数`KPI_ROW`を`TABLE`定数の直前に追加する:

```javascript
  var KPI_ROW = [
    "<div class=\"kpi-row\" id=\"kpiRow\"></div>"
  ].join("");
```

`buildAdminAppHtml()`関数内、`HEADER_AND_FILTERS + TABLE`の部分を`HEADER_AND_FILTERS + KPI_ROW + TABLE`に変更する。

`DRAWER`定数の直後(`buildAdminAppHtml`関数の前)に新しい定数`KPI_MODAL`を追加する:

```javascript
  var KPI_MODAL = [
    "<div class=\"scrim\" id=\"kpiScrim\"></div>",
    "<div class=\"kpi-modal\" id=\"kpiModal\">",
    "<div class=\"km-head\"><div class=\"km-head-row\">",
    "<div><h3 id=\"kmTitle\"></h3><div class=\"km-sub\" id=\"kmSub\"></div></div>",
    "<button class=\"close-btn\" id=\"kpiModalClose\">&times;</button>",
    "</div></div>",
    "<div class=\"km-body\" id=\"kmBody\"></div>",
    "</div>"
  ].join("");
```

`buildAdminAppHtml()`関数の返り値組み立て部分に`KPI_MODAL`を追加する(`DRAWER + PARTNER_DRAWER`の後):

```javascript
      HEADER_AND_FILTERS + KPI_ROW + TABLE + PARTNER_VIEW + DRAWER + PARTNER_DRAWER + KPI_MODAL +
```

`SCRIPT`定数の`loadList();`の直前に、KPI読み込み・描画関数を追加する:

```javascript
    "function loadKpiSummary(){",
    "google.script.run.withSuccessHandler(renderKpiRow).withFailureHandler(function(){",
    "document.getElementById('kpiRow').innerHTML = '';",
    "}).getKpiSummary();",
    "}",

    "var LAST_KPI_SUMMARY = null;",
    "function renderKpiRow(summary){",
    "LAST_KPI_SUMMARY = summary;",
    "var byRank = summary.byRank || {A:0,B:0,C:0,D:0};",
    "var kpis = [",
    "{key:'total', label:'パイプライン企業数', value:summary.total, sub:'絞り込みなしの全企業数'},",
    "{key:'overdueOrUntouched', label:'本日の掘り起こし対象', value:summary.overdueOrUntouched, sub:'未着手・対応期限超過', cls:'alert'},",
    "{key:'hot', label:'即時アラート', value:summary.hot, sub:'本日、企業側から反応あり', cls:'hot'},",
    "{key:'rank', label:'ランク内訳', value:'A'+byRank.A+'/B'+byRank.B+'/C'+byRank.C+'/D'+byRank.D, sub:'ランク別企業数'},",
    "{key:'deal', label:'提案中・案件化', value:summary.deal, sub:'商談が進行中の企業数'},",
    "{key:'stale', label:'長期検討企業', value:summary.stale, sub:'標準サイクルの2倍以上、未接触', cls:'stale'}",
    "];",
    "var row = document.getElementById('kpiRow');",
    "row.innerHTML = kpis.map(function(k){",
    "return '<div class=\"kpi ' + (k.cls||'') + '\" data-kpi=\"' + k.key + '\" role=\"button\" tabindex=\"0\">' +",
    "'<div class=\"label\">' + escapeHtml(k.label) + '</div>' +",
    "'<div class=\"value\">' + escapeHtml(k.value) + '</div>' +",
    "'<div class=\"sub\">' + escapeHtml(k.sub) + '</div></div>';",
    "}).join('');",
    "row.querySelectorAll('.kpi').forEach(function(el){",
    "el.addEventListener('click', function(){ openKpiModal(el.dataset.kpi); });",
    "});",
    "}",

    "function openKpiModal(key){",
    "document.getElementById('kmTitle').textContent = key;",
    "document.getElementById('kmSub').textContent = 'クリックした企業の詳細を開けます';",
    "document.getElementById('kmBody').innerHTML = '<p class=\"km-empty\">一覧側の絞り込みで詳細な内訳を確認してください。</p>';",
    "document.getElementById('kpiScrim').classList.add('open');",
    "document.getElementById('kpiModal').classList.add('open');",
    "}",

    "function closeKpiModal(){",
    "document.getElementById('kpiModal').classList.remove('open');",
    "document.getElementById('kpiScrim').classList.remove('open');",
    "}",
```

（内訳一覧の行クリック連動はデモではKPIごとに企業配列を再フィルタしていたが、本番では
`getKpiSummary()`が集計値のみを返す設計のため、モーダルは「絞り込みは一覧側で行う」という
簡易案内に留める。件数の内訳表示のみをスコープとする。）

ファイル末尾のイベントリスナー登録部分に追加:

```javascript
    "document.getElementById('kpiModalClose').addEventListener('click', closeKpiModal);",
    "document.getElementById('kpiScrim').addEventListener('click', closeKpiModal);",
```

`loadFilterOptions();`, `loadList();`, `loadPartnerList();`の並びに`loadKpiSummary();`を追加する:

```javascript
    "loadFilterOptions();",
    "loadKpiSummary();",
    "loadList();",
    "loadPartnerList();"
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/adminApp.js tests/glow_ma_adminApp.test.mjs
git commit -m "feat(glow-ma): KPIサマリー行と内訳モーダルを追加"
```

---

### Task 11: adminApp.js — 「本日のネクストアクション」+「担当者別ワークロード」パネル

**Files:**
- Modify: `glow-ma/src/adminApp.js`
- Test: `tests/glow_ma_adminApp.test.mjs`

**Interfaces:**
- Consumes: `getNextActionQueue()` / `getOwnerWorkload()`(Task 6)
- Produces: `id="queue"`, `id="workloadList"`(サイドパネル)。

- [ ] **Step 1: 失敗するテストを書く**

```javascript
test("buildAdminAppHtml: ネクストアクション・ワークロードパネルの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["queue", "workloadList"].forEach((id) => {
    assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
  });
});

test("buildAdminAppHtml: google.script.runでgetNextActionQueue・getOwnerWorkloadを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getNextActionQueue(") !== -1);
  assert.ok(html.indexOf(".getOwnerWorkload(") !== -1);
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: FAIL

- [ ] **Step 3: 実装する**

`glow-ma/src/adminApp.js`に新しい定数`SIDE_PANEL`を`PARTNER_VIEW`定数の直後に追加する:

```javascript
  var SIDE_PANEL = [
    "<div class=\"side\">",
    "<div class=\"panel\"><div class=\"panel-head\"><h2>本日のネクストアクション</h2></div>",
    "<div class=\"panel-body-pad\" id=\"queue\"></div></div>",
    "<div class=\"panel\"><div class=\"panel-head\"><h2>担当者別ワークロード</h2></div>",
    "<div class=\"panel-body-pad\" id=\"workloadList\"></div></div>",
    "</div>"
  ].join("");
```

`buildAdminAppHtml()`関数内の返り値組み立てを
`HEADER_AND_FILTERS + KPI_ROW + TABLE + PARTNER_VIEW + DRAWER + PARTNER_DRAWER + KPI_MODAL +`から
`HEADER_AND_FILTERS + KPI_ROW + TABLE + SIDE_PANEL + PARTNER_VIEW + DRAWER + PARTNER_DRAWER + KPI_MODAL +`に変更する。

`SCRIPT`定数の`loadKpiSummary`関数群の直後に追加する:

```javascript
    "function loadQueue(){",
    "google.script.run.withSuccessHandler(renderQueue).withFailureHandler(function(){",
    "document.getElementById('queue').innerHTML = '';",
    "}).getNextActionQueue();",
    "}",

    "function renderQueue(items){",
    "var el = document.getElementById('queue');",
    "if (!items || items.length===0){ el.innerHTML = '<p class=\"empty-note\">本日、優先度の高い企業はありません。</p>'; return; }",
    "el.innerHTML = items.map(function(c){",
    "var flag = c['本日反応あり'] ? '<span class=\"hot-flag\">反応あり</span>' : '<span class=\"rank rank-'+escapeHtml(c['ランク'])+'\">'+escapeHtml(c['ランク'])+'</span>';",
    "return '<div class=\"queue-item\" data-id=\"'+escapeHtml(c['企業ID'])+'\">' +",
    "'<div class=\"qtop\"><span class=\"qname\">'+escapeHtml(c['会社名'])+'</span>'+flag+'</div>' +",
    "'<div class=\"qmeta\">'+escapeHtml(c['担当者']||'未割当')+' 担当 ・ 次回アクション予定日: '+escapeHtml(c['次回アクション予定日']||'未設定')+'</div>' +",
    "'</div>';",
    "}).join('');",
    "el.querySelectorAll('.queue-item').forEach(function(item){",
    "item.addEventListener('click', function(){ openDrawer(item.dataset.id); });",
    "});",
    "}",

    "function loadWorkload(){",
    "google.script.run.withSuccessHandler(renderWorkload).withFailureHandler(function(){",
    "document.getElementById('workloadList').innerHTML = '';",
    "}).getOwnerWorkload();",
    "}",

    "function renderWorkload(rows){",
    "var el = document.getElementById('workloadList');",
    "if (!rows || rows.length===0){ el.innerHTML = '<p class=\"empty-note\">担当者が設定された企業がありません。</p>'; return; }",
    "el.innerHTML = rows.map(function(r){",
    "return '<div class=\"workload-row\"><div class=\"w-top\"><span class=\"w-name\">'+escapeHtml(r.owner)+'</span></div>' +",
    "'<div class=\"w-stats\"><span><b>'+r.total+'</b>件担当</span><span><b>'+r.overdueOrUntouched+'</b>件 未着手/期限超過</span></div>' +",
    "'</div>';",
    "}).join('');",
    "}",
```

`loadKpiSummary();`の直後に`loadQueue(); loadWorkload();`を追加する:

```javascript
    "loadFilterOptions();",
    "loadKpiSummary();",
    "loadQueue();",
    "loadWorkload();",
    "loadList();",
    "loadPartnerList();"
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/adminApp.js tests/glow_ma_adminApp.test.mjs
git commit -m "feat(glow-ma): 本日のネクストアクション・担当者別ワークロードパネルを追加"
```

---

### Task 12: adminApp.js — ドロワーの🤝連携ボタン(Slack共有モーダル)

**Files:**
- Modify: `glow-ma/src/adminApp.js`
- Test: `tests/glow_ma_adminApp.test.mjs`

**Interfaces:**
- Consumes: `getShareableStaffList()`(Task 7)、`shareCompanyWithStaff(companyId, staffIds, note)`
  (既存、`ShareRunner.gs`、変更なし)
- Produces: `id="shareBtn"`, `id="shareModal"`。

**重要**: 既存テスト`tests/glow_ma_adminApp.test.mjs`の
`"buildAdminAppHtml: 関係メモ編集以外の書き込み系google.script.run呼び出しを含まない(Phase 18b範囲の担保)"`
が、禁止リストに`"shareCompanyWithStaff"`を含んでいる。このタスクで意図的にこの呼び出しを追加するため、
このテストを更新する必要がある(Step 1に含める)。

- [ ] **Step 1: 既存テストを更新し、新規テストを書く**

`tests/glow_ma_adminApp.test.mjs`の該当テストを以下に置き換える(`shareCompanyWithStaff`を禁止リストから除外し、
テスト名をPhase 18b限定の記述から更新する):

```javascript
test("buildAdminAppHtml: 想定外の書き込み系google.script.run呼び出しを含まない", () => {
  const html = adminApp.buildAdminAppHtml();
  ["appendInteractionLog", "addPartner", "logPartnerInteraction", "recordReferral"].forEach((forbidden) => {
    assert.equal(html.indexOf(forbidden), -1, forbidden + " への呼び出しが含まれてはいけない(未実装の機能)");
  });
});
```

同ファイルに新規テストを追加:

```javascript
test("buildAdminAppHtml: ドロワーに🤝連携ボタンと共有モーダルの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["shareBtn", "shareModal", "shareTitle", "shareStaffList", "shareNote", "sharePreview", "shareSendBtn"]
    .forEach((id) => {
      assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
    });
});

test("buildAdminAppHtml: google.script.runでgetShareableStaffList・shareCompanyWithStaffを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getShareableStaffList(") !== -1);
  assert.ok(html.indexOf(".shareCompanyWithStaff(") !== -1);
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: 新規2件がFAIL(shareBtn等が存在しない)。既存の禁止リストテストは更新済みのためPASSするはず

- [ ] **Step 3: 実装する**

`DRAWER`定数を以下に置き換える(共有ボタンを追加):

```javascript
  var DRAWER = [
    "<div id=\"overlay\"></div>",
    "<div id=\"drawer\">",
    "<div id=\"drawerHeader\"><div><div id=\"drawerCompanyName\" style=\"font-weight:700\"></div>",
    "<div id=\"drawerCompanyId\" style=\"font-size:0.8rem;color:#7a828a\"></div></div>",
    "<div class=\"row1-actions\">",
    "<button class=\"share-btn\" id=\"shareBtn\">🤝 連携</button>",
    "<button id=\"drawerClose\">&times;</button>",
    "</div></div>",
    "<div class=\"tabs\"><button id=\"tabOverviewBtn\" class=\"active\">概要</button>",
    "<button id=\"tabHistoryBtn\">対応履歴</button></div>",
    "<div id=\"drawerBody\">",
    "<div id=\"paneOverview\"></div>",
    "<div id=\"paneHistory\" style=\"display:none\"></div>",
    "</div></div>"
  ].join("");
```

新しい定数`SHARE_MODAL`を`KPI_MODAL`定数の直後に追加する:

```javascript
  var SHARE_MODAL = [
    "<div class=\"kpi-modal\" id=\"shareModal\">",
    "<div class=\"km-head\"><div class=\"km-head-row\">",
    "<div><h3 id=\"shareTitle\"></h3></div>",
    "<button class=\"close-btn\" id=\"shareModalClose\">&times;</button>",
    "</div></div>",
    "<div class=\"km-body\">",
    "<div id=\"shareDncWarn\" class=\"share-warn\" style=\"display:none\">この企業は連絡不要(DNC)登録されています。共有内容にご注意ください。</div>",
    "<div id=\"shareStaffList\" class=\"share-staff\"></div>",
    "<textarea id=\"shareNote\" placeholder=\"一言メモ(任意)\"></textarea>",
    "<div class=\"share-preview\" id=\"sharePreview\"></div>",
    "<button class=\"btn share-send\" id=\"shareSendBtn\">連携する</button>",
    "<div id=\"shareStatus\" style=\"margin-top:8px;font-size:0.78rem;\"></div>",
    "</div></div>"
  ].join("");
```

`buildAdminAppHtml()`関数の返り値組み立てに`SHARE_MODAL`を追加する:

```javascript
      HEADER_AND_FILTERS + KPI_ROW + TABLE + SIDE_PANEL + PARTNER_VIEW + DRAWER + PARTNER_DRAWER + KPI_MODAL + SHARE_MODAL +
```

`SCRIPT`定数の`closeDrawer()`関数の直後に共有モーダルのロジックを追加する:

```javascript
    "var shareTargetCompanyId = null;",
    "var shareTargetCompanyName = null;",
    "var shareTargetDnc = false;",

    "function openShareModal(){",
    "shareTargetCompanyId = document.getElementById('drawerCompanyId').textContent;",
    "shareTargetCompanyName = document.getElementById('drawerCompanyName').textContent;",
    "document.getElementById('shareTitle').textContent = shareTargetCompanyName + ' を連携';",
    "document.getElementById('shareDncWarn').style.display = shareTargetDnc ? 'block' : 'none';",
    "document.getElementById('shareStatus').textContent = '';",
    "google.script.run.withSuccessHandler(function(staffList){",
    "document.getElementById('shareStaffList').innerHTML = staffList.map(function(s){",
    "return '<label><input type=\"checkbox\" value=\"'+escapeHtml(s.slackUserId)+'\"> '+escapeHtml(s.name)+'</label>';",
    "}).join('');",
    "document.getElementById('shareNote').value = '';",
    "updateSharePreview();",
    "document.querySelectorAll('#shareStaffList input').forEach(function(el){",
    "el.addEventListener('change', updateSharePreview);",
    "});",
    "}).withFailureHandler(function(){",
    "document.getElementById('shareStaffList').innerHTML = '<p class=\"empty-note\">スタッフ一覧の読み込みに失敗しました。</p>';",
    "}).getShareableStaffList();",
    "document.getElementById('shareModal').classList.add('open');",
    "document.getElementById('overlay').classList.add('open');",
    "}",

    "function updateSharePreview(){",
    "var checked = Array.prototype.slice.call(document.querySelectorAll('#shareStaffList input:checked')).map(function(el){ return el.value; });",
    "var note = document.getElementById('shareNote').value;",
    "document.getElementById('sharePreview').textContent = shareTargetCompanyName + ' の情報を連携します。宛先: ' + checked.length + '名' + (note ? ' / メモ: ' + note : '');",
    "}",

    "function closeShareModal(){",
    "document.getElementById('shareModal').classList.remove('open');",
    "document.getElementById('overlay').classList.remove('open');",
    "}",

    "function sendShare(){",
    "var checked = Array.prototype.slice.call(document.querySelectorAll('#shareStaffList input:checked')).map(function(el){ return el.value; });",
    "if (checked.length===0){ document.getElementById('shareStatus').textContent = '連携先を選択してください。'; return; }",
    "var note = document.getElementById('shareNote').value;",
    "document.getElementById('shareSendBtn').disabled = true;",
    "document.getElementById('shareStatus').textContent = '送信中...';",
    "google.script.run.withSuccessHandler(function(resultText){",
    "document.getElementById('shareSendBtn').disabled = false;",
    "document.getElementById('shareStatus').textContent = resultText;",
    "}).withFailureHandler(function(){",
    "document.getElementById('shareSendBtn').disabled = false;",
    "document.getElementById('shareStatus').textContent = '連携に失敗しました。もう一度お試しください。';",
    "}).shareCompanyWithStaff(shareTargetCompanyId, checked, note);",
    "}",
```

ファイル末尾のイベントリスナー登録部分に追加:

```javascript
    "document.getElementById('shareBtn').addEventListener('click', openShareModal);",
    "document.getElementById('shareModalClose').addEventListener('click', closeShareModal);",
    "document.getElementById('shareSendBtn').addEventListener('click', sendShare);",
    "document.getElementById('shareNote').addEventListener('input', updateSharePreview);",
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: コミット**

```bash
git add glow-ma/src/adminApp.js tests/glow_ma_adminApp.test.mjs
git commit -m "feat(glow-ma): ドロワーに🤝連携ボタン(Slack共有モーダル)を追加"
```

---

### Task 13: adminApp.js — レター下書きプレビューモーダル

**Files:**
- Modify: `glow-ma/src/adminApp.js`
- Test: `tests/glow_ma_adminApp.test.mjs`

**Interfaces:**
- Consumes: `getLatestLetterDraft(companyId)`(Task 7)
- Produces: `id="letterPreviewBtn"`, `id="letterPreviewModal"`。

- [ ] **Step 1: 失敗するテストを書く**

```javascript
test("buildAdminAppHtml: レター下書きプレビューボタン・モーダルの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["letterPreviewBtn", "letterPreviewModal", "letterPreviewBody"].forEach((id) => {
    assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
  });
});

test("buildAdminAppHtml: google.script.runでgetLatestLetterDraftを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getLatestLetterDraft(") !== -1);
});
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: FAIL

- [ ] **Step 3: 実装する**

`DRAWER`定数の`row1-actions`内、`shareBtn`ボタンの直後にレター下書きボタンを追加する:

```javascript
  var DRAWER = [
    "<div id=\"overlay\"></div>",
    "<div id=\"drawer\">",
    "<div id=\"drawerHeader\"><div><div id=\"drawerCompanyName\" style=\"font-weight:700\"></div>",
    "<div id=\"drawerCompanyId\" style=\"font-size:0.8rem;color:#7a828a\"></div></div>",
    "<div class=\"row1-actions\">",
    "<button class=\"share-btn\" id=\"shareBtn\">🤝 連携</button>",
    "<button class=\"btn-small\" id=\"letterPreviewBtn\">下書きを見る</button>",
    "<button id=\"drawerClose\">&times;</button>",
    "</div></div>",
    "<div class=\"tabs\"><button id=\"tabOverviewBtn\" class=\"active\">概要</button>",
    "<button id=\"tabHistoryBtn\">対応履歴</button></div>",
    "<div id=\"drawerBody\">",
    "<div id=\"paneOverview\"></div>",
    "<div id=\"paneHistory\" style=\"display:none\"></div>",
    "</div></div>"
  ].join("");
```

新しい定数`LETTER_PREVIEW_MODAL`を`SHARE_MODAL`定数の直後に追加する:

```javascript
  var LETTER_PREVIEW_MODAL = [
    "<div class=\"kpi-modal\" id=\"letterPreviewModal\">",
    "<div class=\"km-head\"><div class=\"km-head-row\">",
    "<div><h3>レター下書き</h3></div>",
    "<button class=\"close-btn\" id=\"letterPreviewModalClose\">&times;</button>",
    "</div></div>",
    "<div class=\"km-body\" id=\"letterPreviewBody\"></div>",
    "</div>"
  ].join("");
```

`buildAdminAppHtml()`関数の返り値組み立てに`LETTER_PREVIEW_MODAL`を追加する:

```javascript
      HEADER_AND_FILTERS + KPI_ROW + TABLE + SIDE_PANEL + PARTNER_VIEW + DRAWER + PARTNER_DRAWER + KPI_MODAL + SHARE_MODAL + LETTER_PREVIEW_MODAL +
```

`SCRIPT`定数の`sendShare()`関数の直後にレター下書きプレビューのロジックを追加する:

```javascript
    "function openLetterPreview(){",
    "var companyId = document.getElementById('drawerCompanyId').textContent;",
    "document.getElementById('letterPreviewBody').innerHTML = '<p class=\"empty-note\">読み込み中…</p>';",
    "document.getElementById('letterPreviewModal').classList.add('open');",
    "document.getElementById('overlay').classList.add('open');",
    "google.script.run.withSuccessHandler(function(draft){",
    "if (!draft){ document.getElementById('letterPreviewBody').innerHTML = '<p class=\"empty-note\">下書きなし</p>'; return; }",
    "document.getElementById('letterPreviewBody').innerHTML =",
    "'<div class=\"field\"><div class=\"label\">生成日時</div><div class=\"value\">'+escapeHtml(draft['生成日時'])+'</div></div>' +",
    "'<div class=\"field\"><div class=\"label\">ステータス</div><div class=\"value\">'+escapeHtml(draft['ステータス'])+'</div></div>' +",
    "'<div class=\"field\"><div class=\"label\">本文</div><div class=\"value\">'+escapeHtml(draft['本文'])+'</div></div>';",
    "}).withFailureHandler(function(){",
    "document.getElementById('letterPreviewBody').innerHTML = '<p class=\"empty-note\">読み込みに失敗しました。</p>';",
    "}).getLatestLetterDraft(companyId);",
    "}",

    "function closeLetterPreview(){",
    "document.getElementById('letterPreviewModal').classList.remove('open');",
    "document.getElementById('overlay').classList.remove('open');",
    "}",
```

ファイル末尾のイベントリスナー登録部分に追加:

```javascript
    "document.getElementById('letterPreviewBtn').addEventListener('click', openLetterPreview);",
    "document.getElementById('letterPreviewModalClose').addEventListener('click', closeLetterPreview);",
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: 全体のテストスイートを実行して回帰がないことを確認する**

Run: `node --test tests/glow_ma_*.test.mjs`
Expected: 全件PASS(件数は既存 + 本Planで追加した分)

- [ ] **Step 6: コミット**

```bash
git add glow-ma/src/adminApp.js tests/glow_ma_adminApp.test.mjs
git commit -m "feat(glow-ma): レター下書きプレビューモーダルを追加"
```

---

### Task 14: ドキュメント更新(README・本番投入手順書)

**Files:**
- Modify: `glow-ma/README.md`
- Modify: `docs/glow-ma_本番投入手順書_統合版.md`

**Interfaces:**
- Consumes: なし(ドキュメントのみ)

- [ ] **Step 1: README.mdに新機能の説明を追記する**

`glow-ma/README.md`の管理画面(Phase 18a)に関する既存セクションを探し、その直後に追記する:

```markdown
### 管理画面コンソールv2(2026-08-13)

企業一覧の管理画面に以下を追加した:
- KPIサマリー行(パイプライン企業数・本日の掘り起こし対象・即時アラート・ランク内訳・提案中案件数・長期検討企業数)
- 企業一覧に流入ルート・提案商品列と、それぞれの絞り込みを追加
- サイドパネルに「本日のネクストアクション」(優先度順、最大8件)と「担当者別ワークロード」
- ドロワーに🤝連携ボタン(既存のSlack共有機能`shareCompanyWithStaff`をそのまま呼び出す)
- ドロワーに「下書きを見る」ボタン(その企業への最新レター下書き本文を表示)

緊急度(掘り起こし対象・まもなく等)の判定基準は
`docs/superpowers/specs/2026-08-13-glow-ma-admin-console-v2-design.md`の三名体制レビューを参照。
既存のアラート発報(AlertRunner.gs)ロジックとは独立した、画面表示専用の優先順位付けである。

新しいシートタブは不要(既存の企業マスタ・対応履歴ログ・スタッフ・レター下書きタブのみ使用)。
```

- [ ] **Step 2: 本番投入手順書に再デプロイ手順を追記する**

`docs/glow-ma_本番投入手順書_統合版.md`のPhase 18a/18bのデプロイ手順セクションの末尾に追記する:

```markdown
### 管理画面コンソールv2 反映手順(2026-08-13)

1. `clasp push`で最新コードを反映する(schema.js・adminAccess.js・AdminRunner.gs・adminApp.jsが対象)
2. Apps Scriptエディタの「デプロイ」→「デプロイを管理」→鉛筆アイコン→「新バージョン」→「デプロイ」を実行する
   (コードを保存しただけでは既存デプロイのWeb Appには反映されない。必ず新バージョンとしてデプロイし直すこと)
3. 管理画面URL(`.../exec?page=admin`)を開き、以下を確認する:
   - KPI行が6項目とも数値付きで表示される
   - 企業一覧に流入ルート・提案商品のバッジが表示される
   - サイドパネルに本日のネクストアクション・担当者別ワークロードが表示される
   - 企業をクリックしてドロワーが開き、🤝連携ボタン・下書きを見るボタンが機能する
```

- [ ] **Step 3: コミット**

```bash
git add glow-ma/README.md docs/glow-ma_本番投入手順書_統合版.md
git commit -m "docs(glow-ma): 管理画面コンソールv2の使い方・再デプロイ手順を追記"
```

---

## 最終レビュー後の想定作業(本Planの範囲外、SDD完了後に別途実施)

- 全タスク完了後、`node --test tests/glow_ma_*.test.mjs`で全体テストを実行し、最終コードレビューを行う
- `finishing-a-development-branch`スキルでmainへマージする
- 本番環境で`clasp push`→再デプロイ→動作確認(本プランTask 14に記載の手順)を、ユーザーと一緒にスクリーンショットベースで行う
