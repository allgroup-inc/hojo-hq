# GLOW M&A台帳 Phase 3(掘り起こしアラート・ネクストベストアクション)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 企業マスタの各企業について「掘り起こし対象かどうか」をランク別接触サイクル(紹介ルートは常にA相当30日を強制)+次回アクション予定日から判定し、ステージ×ランクに応じたネクストベストアクションを提示して、日次でSlackに通知する。加えて、対応履歴ログに反応イベント(レターURLアクセス等)が記録された瞬間に即時Slack通知する(Speed to Lead)。

**Architecture:** 判定ロジック(サイクル超過判定・紹介ルート例外・ネクストベストアクション決定)はGAS/Node両対応のUMD形式プレーンJSとして`glow-ma/src/alerting.js`に実装し、`node --test`でユニットテストする。GAS専用の`AlertRunner.gs`は日次バッチ(`runDailyAlerts`)と即時アラート(`onEdit`シンプルトリガー)の両方を持つ薄いグルーコードとし、Phase 1/2で作った`readCompanyRecords_`(`ImportRunner.gs`)と`GlowScoring.DEFAULT_CONFIG.reactionPointsByType`(`scoring.js`)をそのまま再利用する(反応イベントの種別リストを`alerting.js`側で重複定義しない)。Slack通知はGoogle Apps Scriptの「スクリプト プロパティ」に保存したWebhook URLを使い、コードにURLを直接書かない。

**Tech Stack:** Google Apps Script(V8ランタイム、`onEdit`シンプルトリガー、`PropertiesService`、`UrlFetchApp`)、Node.js組み込み`node:test`/`node:assert`(追加npm依存なし)。

**このPlanの範囲について:** 設計書8章(掘り起こしアラート・ネクストベストアクション・即時アラート)を実装する。7章(提案順序ガイドライン)はドキュメントレベルの運用指針であり本Planでは扱わない。10〜12章(レター生成・ナーチャリング・ダッシュボード)は対象外。日次トリガー(`ScriptApp.newTrigger`によるスケジュール登録)自体はApps Scriptエディタから人間が手動で行う運用とし、トリガー登録コードは本Planに含めない(`runDailyAlerts`という実行可能な関数を用意するところまでが本Planの責務)。

> **実装時の訂正(2026-07-27):** Task 5は当初「`onEdit`という名前の関数はGASが自動的にシンプルトリガーとして認識するため登録不要」という前提で書かれていたが、これは誤りだった。GASのシンプルトリガーは`UrlFetchApp.fetch`のような認可が必要なサービスを呼び出せない制約があり、Slack通知が例外で失敗する。実装時のタスクレビューでこれを検出し、`handleInteractionLogEdit`という名前に変更した上で、`installInteractionLogEditTrigger()`が登録するインストール型トリガー方式に修正した。以降、本文中の「onEdit」「トリガー登録は不要」という記述は誤りとして読み替えること。

## Global Constraints

- 公開リポジトリ(hojo-hq)に実データ・Slack Webhook URLを一切コミットしない。Webhook URLはGASの「スクリプト プロパティ」(`PropertiesService`)で管理し、コードに直接書かない
- GASとNode両方で動くファイルはUMD形式(`typeof module !== "undefined" && module.exports`で分岐)を踏襲する
- 追加のnpm依存を増やさない。テストは`node --test` + `node:assert/strict`を使う
- ランク別標準接触サイクル日数(2026-07-27 glow-ma-triangle-review確定・設計書8章): A=30日/B=90日/C=180日/D=365日
- 紹介ルート(①紹介)の企業は、企業マスタの`ランク`列の値に関わらず、常にA相当(30日サイクル)で判定する。ただしこれは掘り起こし判定・ネクストベストアクションの計算にのみ影響し、企業マスタの`ランク`列自体(Phase 2の`ScoringRunner.gs`が書き込む値)は書き換えない
- 次回アクション予定日が設定されている場合は、ランク別サイクルより常に優先する(設計書8章)
- 即時アラート対象の反応イベント種別は、`glow-ma/src/scoring.js`の`GlowScoring.DEFAULT_CONFIG.reactionPointsByType`のキー一覧をそのまま使う。`alerting.js`側で別のリストを重複定義しない(Phase 2最終レビューで指摘された「キーリストの重複によるドリフト」を再発させない)
- GAS専用ファイル(`.gs`)は`node --test`で検証できないため、静的チェック(`node --check`)と手書きトレースで代替し、実運用前の手動検証が必要であることをレポートに明記する(Phase 1・2と同じ扱い)

---

## File Structure

```
glow-ma/src/
  alerting.js       — 新規: 掘り起こし判定・ネクストベストアクション決定ロジック(GlowAlerting)(Task 1, 2, 3)
  AlertRunner.gs      — 新規: 日次バッチアラート + 即時アラート(onEdit)(Task 4, 5、GAS専用)
tests/
  glow_ma_alerting.test.mjs   — 新規(Task 1, 2, 3)
glow-ma/README.md      — Slack設定手順・Phase 3の使い方を追記(Task 6)
```

---

### Task 1: `alerting.js` — 日付ユーティリティと紹介ルート例外

**Files:**
- Create: `glow-ma/src/alerting.js`
- Test: `tests/glow_ma_alerting.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowAlerting`オブジェクト。`DEFAULT_CONFIG`(object)、`toDate(value)`: Date|null(文字列"yyyy-MM-dd"またはDateオブジェクトを受け付け、どちらでもないか空なら`null`)、`daysBetween(fromValue, toValue)`: number|null(fromからtoまでの日数。どちらかが`toDate`できなければ`null`)、`resolveEffectiveRank(record, config)`: "A"|"B"|"C"|"D"|undefined(`流入ルート`に`config.referralRoute`が含まれていれば常に"A"、それ以外は`record["ランク"]`をそのまま返す)

#### 1-1. `toDate` / `daysBetween`

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_alerting.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const alerting = require("../glow-ma/src/alerting.js");

test("toDate: yyyy-MM-dd形式の文字列をDateに変換する", () => {
  const d = alerting.toDate("2026-07-27");
  assert.equal(d.getFullYear(), 2026);
  assert.equal(d.getMonth(), 6);
  assert.equal(d.getDate(), 27);
});

test("toDate: Dateオブジェクトはそのまま返す(GASがセルを日付型として読む場合に対応)", () => {
  const original = new Date(2026, 6, 27);
  assert.equal(alerting.toDate(original), original);
});

test("toDate: 空文字・null・不正な形式はnull", () => {
  assert.equal(alerting.toDate(""), null);
  assert.equal(alerting.toDate(null), null);
  assert.equal(alerting.toDate(undefined), null);
  assert.equal(alerting.toDate("不正な値"), null);
});

test("daysBetween: 日数差を正しく計算する", () => {
  assert.equal(alerting.daysBetween("2026-07-01", "2026-07-27"), 26);
});

test("daysBetween: 文字列とDateオブジェクトが混在していても計算できる", () => {
  assert.equal(alerting.daysBetween(new Date(2026, 6, 1), "2026-07-27"), 26);
});

test("daysBetween: どちらかが不正な日付ならnull", () => {
  assert.equal(alerting.daysBetween("", "2026-07-27"), null);
  assert.equal(alerting.daysBetween("2026-07-01", null), null);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_alerting.test.mjs`
Expected: FAIL(`glow-ma/src/alerting.js`が存在しない)

- [ ] **Step 3: `glow-ma/src/alerting.js` を作成し `toDate` / `daysBetween` を実装**

```js
/* GLOW企業リレーション台帳 掘り起こしアラート・ネクストベストアクション判定ロジック
 * ブラウザ相当のGAS(global.GlowAlerting)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_alerting.test.mjs で検証される。
 *
 * ランク別接触サイクル・紹介ルートの例外は
 * docs/superpowers/specs/2026-07-26-glow-ma-relation-system-design.md 8章
 * (2026-07-27 glow-ma-triangle-review確定)に基づく。
 */
(function (global) {
  "use strict";

  var DEFAULT_CONFIG = {
    cycleDaysByRank: { A: 30, B: 90, C: 180, D: 365 },
    referralRoute: "①紹介"
  };

  function toDate(value) {
    if (value instanceof Date) return value;
    if (typeof value === "string" && value) {
      var parts = value.split("-");
      if (parts.length === 3) {
        var year = Number(parts[0]);
        var month = Number(parts[1]);
        var day = Number(parts[2]);
        if (!isNaN(year) && !isNaN(month) && !isNaN(day)) {
          return new Date(year, month - 1, day);
        }
      }
    }
    return null;
  }

  function daysBetween(fromValue, toValue) {
    var from = toDate(fromValue);
    var to = toDate(toValue);
    if (!from || !to) return null;
    var msPerDay = 24 * 60 * 60 * 1000;
    return Math.floor((to.getTime() - from.getTime()) / msPerDay);
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    toDate: toDate,
    daysBetween: daysBetween
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowAlerting = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_alerting.test.mjs`
Expected: PASS(7 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/alerting.js tests/glow_ma_alerting.test.mjs
git commit -m "feat(glow-ma): 日付ユーティリティ(toDate/daysBetween)を追加"
```

#### 1-2. `resolveEffectiveRank`

- [ ] **Step 6: 失敗するテストを追記**

`tests/glow_ma_alerting.test.mjs` に追記:

```js
test("resolveEffectiveRank: 紹介ルートを含む企業は常にAランク相当を返す", () => {
  const record = { 流入ルート: ["①紹介"], ランク: "D" };
  assert.equal(alerting.resolveEffectiveRank(record, alerting.DEFAULT_CONFIG), "A");
});

test("resolveEffectiveRank: 紹介ルートを含まない企業はランクをそのまま返す", () => {
  const record = { 流入ルート: ["②手紙DM"], ランク: "C" };
  assert.equal(alerting.resolveEffectiveRank(record, alerting.DEFAULT_CONFIG), "C");
});

test("resolveEffectiveRank: 流入ルートが未設定でもエラーにならない", () => {
  const record = { ランク: "B" };
  assert.equal(alerting.resolveEffectiveRank(record, alerting.DEFAULT_CONFIG), "B");
});
```

- [ ] **Step 7: テストが失敗することを確認**

Run: `node --test tests/glow_ma_alerting.test.mjs`
Expected: FAIL(`alerting.resolveEffectiveRank is not a function`)

- [ ] **Step 8: `resolveEffectiveRank` を実装**

`glow-ma/src/alerting.js` の `daysBetween` 関数の直後に追加する:

```js
  function resolveEffectiveRank(record, config) {
    config = config || DEFAULT_CONFIG;
    var routes = record["流入ルート"] || [];
    if (routes.indexOf(config.referralRoute) !== -1) return "A";
    return record["ランク"];
  }
```

`api`オブジェクトを次のように更新する:

```js
  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    toDate: toDate,
    daysBetween: daysBetween,
    resolveEffectiveRank: resolveEffectiveRank
  };
```

- [ ] **Step 9: テストが通ることを確認**

Run: `node --test tests/glow_ma_alerting.test.mjs`
Expected: PASS(10 tests)

- [ ] **Step 10: Commit**

```bash
git add glow-ma/src/alerting.js tests/glow_ma_alerting.test.mjs
git commit -m "feat(glow-ma): 紹介ルート例外(resolveEffectiveRank)を追加"
```

---

### Task 2: `alerting.js` — 掘り起こし対象の判定(`isOverdue`)

**Files:**
- Modify: `glow-ma/src/alerting.js`
- Modify: `tests/glow_ma_alerting.test.mjs`

**Interfaces:**
- Consumes: Task 1の`toDate`/`daysBetween`/`resolveEffectiveRank`/`DEFAULT_CONFIG`
- Produces: `isOverdue(record, todayValue, config)`: boolean。企業マスタの1レコードと「今日の日付」を受け取り、掘り起こし対象かどうかを返す。Task 3の`buildDailyAlertList`が呼び出す

- [ ] **Step 1: 失敗するテストを追記**

`tests/glow_ma_alerting.test.mjs` に追記:

```js
test("isOverdue: 次回アクション予定日が今日以前なら掘り起こし対象(サイクルより優先)", () => {
  const record = { ランク: "D", 流入ルート: [], 次回アクション予定日: "2026-07-26", 最終接触日: "2026-07-26" };
  assert.equal(alerting.isOverdue(record, "2026-07-27", alerting.DEFAULT_CONFIG), true);
});

test("isOverdue: 次回アクション予定日が未来ならサイクルを超過していても対象外", () => {
  const record = { ランク: "A", 流入ルート: [], 次回アクション予定日: "2026-08-01", 最終接触日: "2026-01-01" };
  assert.equal(alerting.isOverdue(record, "2026-07-27", alerting.DEFAULT_CONFIG), false);
});

test("isOverdue: 次回アクション予定日が未設定ならランク別サイクルで判定する", () => {
  const overdue = { ランク: "B", 流入ルート: [], 次回アクション予定日: "", 最終接触日: "2026-04-01" };
  // Bランクは90日サイクル。2026-04-01→2026-07-27は117日経過 → 対象
  assert.equal(alerting.isOverdue(overdue, "2026-07-27", alerting.DEFAULT_CONFIG), true);

  const notYet = { ランク: "B", 流入ルート: [], 次回アクション予定日: "", 最終接触日: "2026-07-01" };
  // 26日しか経過していない → 対象外
  assert.equal(alerting.isOverdue(notYet, "2026-07-27", alerting.DEFAULT_CONFIG), false);
});

test("isOverdue: 紹介ルートの企業はランクに関わらず30日サイクルで判定する", () => {
  const record = { ランク: "D", 流入ルート: ["①紹介"], 次回アクション予定日: "", 最終接触日: "2026-06-01" };
  // Dランクなら365日サイクルだが、紹介ルートなので30日サイクルを適用 → 56日経過で対象
  assert.equal(alerting.isOverdue(record, "2026-07-27", alerting.DEFAULT_CONFIG), true);
});

test("isOverdue: 最終接触日が未設定なら登録日を代わりに使う", () => {
  const record = { ランク: "B", 流入ルート: [], 次回アクション予定日: "", 最終接触日: "", 登録日: "2026-04-01" };
  assert.equal(alerting.isOverdue(record, "2026-07-27", alerting.DEFAULT_CONFIG), true);
});

test("isOverdue: 日付を一切計算できない場合は対象外(誤検知を避ける)", () => {
  const record = { ランク: "B", 流入ルート: [], 次回アクション予定日: "", 最終接触日: "", 登録日: "" };
  assert.equal(alerting.isOverdue(record, "2026-07-27", alerting.DEFAULT_CONFIG), false);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_alerting.test.mjs`
Expected: FAIL(`alerting.isOverdue is not a function`)

- [ ] **Step 3: `isOverdue` を実装**

`glow-ma/src/alerting.js` の `resolveEffectiveRank` 関数の直後に追加する:

```js
  function isOverdue(record, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var dueDate = record["次回アクション予定日"];
    if (dueDate) {
      var daysUntilDue = daysBetween(todayValue, dueDate);
      if (daysUntilDue !== null) return daysUntilDue <= 0;
    }
    var effectiveRank = resolveEffectiveRank(record, config);
    var cycleDays = config.cycleDaysByRank[effectiveRank];
    if (typeof cycleDays !== "number") return false;
    var lastTouch = record["最終接触日"] || record["登録日"];
    var daysSinceTouch = daysBetween(lastTouch, todayValue);
    if (daysSinceTouch === null) return false;
    return daysSinceTouch >= cycleDays;
  }
```

`api`オブジェクトを次のように更新する:

```js
  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    toDate: toDate,
    daysBetween: daysBetween,
    resolveEffectiveRank: resolveEffectiveRank,
    isOverdue: isOverdue
  };
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_alerting.test.mjs`
Expected: PASS(16 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/alerting.js tests/glow_ma_alerting.test.mjs
git commit -m "feat(glow-ma): 掘り起こし対象の判定(isOverdue)ロジックを追加"
```

---

### Task 3: `alerting.js` — ネクストベストアクションと日次アラート一覧

**Files:**
- Modify: `glow-ma/src/alerting.js`
- Modify: `tests/glow_ma_alerting.test.mjs`

**Interfaces:**
- Consumes: Task 1, 2の全関数
- Produces: `determineNextBestAction(record, config)`: string、`buildDailyAlertList(records, todayValue, config)`: `{企業ID, 会社名, ランク, ネクストベストアクション}[]`(掘り起こし対象のみ、ランクA→Dの順にソート)。Task 4の`AlertRunner.gs`が`buildDailyAlertList`を呼び出す

- [ ] **Step 1: 失敗するテストを追記**

`tests/glow_ma_alerting.test.mjs` に追記:

```js
test("determineNextBestAction: Aランク×未接触系ステージは至急電話推奨", () => {
  const record = { ランク: "A", 流入ルート: [], 現在ステージ: "未接触" };
  assert.equal(alerting.determineNextBestAction(record, alerting.DEFAULT_CONFIG), "至急電話推奨(最優先ランク)");
});

test("determineNextBestAction: Bランク×未接触は電話推奨", () => {
  const record = { ランク: "B", 流入ルート: [], 現在ステージ: "未接触" };
  assert.equal(alerting.determineNextBestAction(record, alerting.DEFAULT_CONFIG), "電話推奨");
});

test("determineNextBestAction: Cランク×電話済みはゆんたく相談室の再案内", () => {
  const record = { ランク: "C", 流入ルート: [], 現在ステージ: "電話済み" };
  assert.equal(alerting.determineNextBestAction(record, alerting.DEFAULT_CONFIG), "ゆんたく相談室の再案内");
});

test("determineNextBestAction: Dランクはステージによらずナーチャリング配信の対象", () => {
  const record = { ランク: "D", 流入ルート: [], 現在ステージ: "関係構築中" };
  assert.equal(alerting.determineNextBestAction(record, alerting.DEFAULT_CONFIG), "ナーチャリング配信の対象に追加");
});

test("determineNextBestAction: どのルールにも一致しない場合は汎用アクションを返す", () => {
  const record = { ランク: "B", 流入ルート: [], 現在ステージ: "案件化" };
  assert.equal(alerting.determineNextBestAction(record, alerting.DEFAULT_CONFIG), "対応履歴を確認し次のアクションを検討");
});

test("buildDailyAlertList: 掘り起こし対象のみ抽出し、ランクA→Dの順に並べる", () => {
  const records = [
    { 企業ID: "C1", 会社名: "D社", ランク: "D", 流入ルート: [], 現在ステージ: "関係構築中", 次回アクション予定日: "", 最終接触日: "2020-01-01" },
    { 企業ID: "C2", 会社名: "A社", ランク: "A", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2020-01-01" },
    { 企業ID: "C3", 会社名: "対象外社", ランク: "A", 流入ルート: [], 現在ステージ: "未接触", 次回アクション予定日: "", 最終接触日: "2026-07-27" }
  ];
  const alerts = alerting.buildDailyAlertList(records, "2026-07-27", alerting.DEFAULT_CONFIG);
  assert.equal(alerts.length, 2);
  assert.deepEqual(alerts.map((a) => a["企業ID"]), ["C2", "C1"]);
  assert.equal(alerts[0]["ネクストベストアクション"], "至急電話推奨(最優先ランク)");
});

test("buildDailyAlertList: 対象企業がなければ空配列", () => {
  assert.deepEqual(alerting.buildDailyAlertList([], "2026-07-27", alerting.DEFAULT_CONFIG), []);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_alerting.test.mjs`
Expected: FAIL(`alerting.determineNextBestAction is not a function`)

- [ ] **Step 3: `determineNextBestAction` / `buildDailyAlertList` を実装**

`glow-ma/src/alerting.js` の `DEFAULT_CONFIG` 定義を、ネクストベストアクションのルールを含む形に置き換える(ファイル冒頭付近):

```js
  var NEXT_BEST_ACTION_RULES = [
    { rank: "A", stages: ["未接触", "アプローチ実施", "電話済み"], action: "至急電話推奨(最優先ランク)" },
    { rank: "B", stages: ["未接触", "アプローチ実施"], action: "電話推奨" },
    { rank: "C", stages: ["アプローチ実施", "電話済み"], action: "ゆんたく相談室の再案内" },
    { rank: "D", stages: null, action: "ナーチャリング配信の対象に追加" }
  ];
  var DEFAULT_NEXT_BEST_ACTION = "対応履歴を確認し次のアクションを検討";

  var DEFAULT_CONFIG = {
    cycleDaysByRank: { A: 30, B: 90, C: 180, D: 365 },
    referralRoute: "①紹介",
    nextBestActionRules: NEXT_BEST_ACTION_RULES,
    defaultNextBestAction: DEFAULT_NEXT_BEST_ACTION
  };
```

`isOverdue` 関数の直後に追加する:

```js
  function determineNextBestAction(record, config) {
    config = config || DEFAULT_CONFIG;
    var rank = resolveEffectiveRank(record, config);
    var stage = record["現在ステージ"];
    var rules = config.nextBestActionRules || NEXT_BEST_ACTION_RULES;
    for (var i = 0; i < rules.length; i++) {
      var rule = rules[i];
      if (rule.rank !== rank) continue;
      if (rule.stages && rule.stages.indexOf(stage) === -1) continue;
      return rule.action;
    }
    return config.defaultNextBestAction || DEFAULT_NEXT_BEST_ACTION;
  }

  function buildDailyAlertList(records, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var rankOrder = { A: 0, B: 1, C: 2, D: 3 };
    var alerts = [];
    (records || []).forEach(function (record) {
      if (!isOverdue(record, todayValue, config)) return;
      alerts.push({
        "企業ID": record["企業ID"],
        "会社名": record["会社名"],
        "ランク": resolveEffectiveRank(record, config),
        "ネクストベストアクション": determineNextBestAction(record, config)
      });
    });
    alerts.sort(function (a, b) {
      var aOrder = rankOrder[a["ランク"]];
      var bOrder = rankOrder[b["ランク"]];
      aOrder = typeof aOrder === "number" ? aOrder : 99;
      bOrder = typeof bOrder === "number" ? bOrder : 99;
      return aOrder - bOrder;
    });
    return alerts;
  }
```

`api`オブジェクトを次のように更新する(最終形):

```js
  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    toDate: toDate,
    daysBetween: daysBetween,
    resolveEffectiveRank: resolveEffectiveRank,
    isOverdue: isOverdue,
    determineNextBestAction: determineNextBestAction,
    buildDailyAlertList: buildDailyAlertList
  };
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_alerting.test.mjs`
Expected: PASS(22 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/alerting.js tests/glow_ma_alerting.test.mjs
git commit -m "feat(glow-ma): ネクストベストアクション決定と日次アラート一覧生成を追加"
```

---

### Task 4: `AlertRunner.gs` — 日次バッチアラート(GAS専用・手動検証)

**Files:**
- Create: `glow-ma/src/AlertRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema.COMPANY_MASTER_SHEET_NAME`(Task 1〜Phase1)、`GlowAlerting.buildDailyAlertList`(Task 3)、`readCompanyRecords_`(`glow-ma/src/ImportRunner.gs`で定義済み。**再定義しないこと**)
- Produces: `runDailyAlerts()`関数(引数なし)。企業マスタ全件から掘り起こし対象を抽出し、Slackへ通知する。`postToSlack_(message)`関数(Task 5の即時アラートからも呼び出される共通ヘルパー)

- [ ] **Step 1: `glow-ma/src/AlertRunner.gs` を実装**

```js
/**
 * GLOW企業リレーション台帳: 掘り起こしアラート(日次バッチ)
 *
 * 使い方:
 * 1. Apps Scriptエディタの「プロジェクトの設定」→「スクリプト プロパティ」で
 *    SLACK_WEBHOOK_URL を設定する(コードにWebhook URLを直接書かない)
 * 2. Apps Scriptエディタの「トリガー」画面で runDailyAlerts を時間主導トリガー
 *    (毎日 朝など)に手動登録する(トリガー登録自体は本ファイルでは行わない)
 *
 * 実行すると、企業マスタ全件から GlowAlerting.buildDailyAlertList で
 * 掘り起こし対象を抽出し、ランク・ネクストベストアクションとともにSlackへ通知する。
 */
function runDailyAlerts() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }

  var records = readCompanyRecords_(companySheet);
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var alerts = GlowAlerting.buildDailyAlertList(records, todayString);

  if (alerts.length === 0) {
    Logger.log("本日の掘り起こし対象はありません。");
    return;
  }

  var lines = alerts.map(function (alert) {
    return "・" + alert["会社名"] + "(" + alert["ランク"] + "ランク) — " + alert["ネクストベストアクション"];
  });
  var message = "【本日の掘り起こし対象】" + alerts.length + "件\n" + lines.join("\n");
  postToSlack_(message);
  Logger.log("掘り起こしアラート送信完了: " + alerts.length + "件");
}

function postToSlack_(message) {
  var webhookUrl = PropertiesService.getScriptProperties().getProperty("SLACK_WEBHOOK_URL");
  if (!webhookUrl) {
    Logger.log("SLACK_WEBHOOK_URL が未設定のため通知をスキップしました: " + message);
    return;
  }
  UrlFetchApp.fetch(webhookUrl, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({ text: message })
  });
}
```

- [ ] **Step 2: 静的チェック**

Run: `cp glow-ma/src/AlertRunner.gs /tmp/AlertRunner_check.js && node --check /tmp/AlertRunner_check.js && rm /tmp/AlertRunner_check.js`
Expected: 構文エラーなし

- [ ] **Step 3: 手書きトレース**

`glow-ma/src/alerting.js`の実際のロジックを使い、以下の想定データで`runDailyAlerts`が生成するメッセージを手でたどって記録する:
- 企業X: `ランク="A"`, `流入ルート=["②手紙DM"]`, `現在ステージ="未接触"`, `次回アクション予定日=""`, `最終接触日="2026-06-01"`(実行日2026-07-27との差は56日、Aランクのサイクル30日を超過 → 対象)
- 期待されるメッセージの一部: 「至急電話推奨(最優先ランク)」という文言が含まれること

- [ ] **Step 4: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間がGoogleスプレッドシート・Slack上で確認する手順:

1. Slack側で Incoming Webhook を発行し、URLを控える
2. `clasp push` で反映
3. Apps Scriptエディタの「プロジェクトの設定」→「スクリプト プロパティ」で `SLACK_WEBHOOK_URL` にそのURLを設定する
4. Step 3の想定データを企業マスタに手入力する
5. `runDailyAlerts` を実行し、Slackの対象チャンネルに通知が届くこと、内容がStep 3の期待値と一致することを確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報・Slack Webhookがないため未実施」と明記すること。

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/AlertRunner.gs
git commit -m "feat(glow-ma): 掘り起こしアラートの日次バッチ通知機能を追加"
```

---

### Task 5: `AlertRunner.gs` — 即時アラート(Speed to Lead、GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/AlertRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema.INTERACTION_LOG_SHEET_NAME`/`INTERACTION_LOG_HEADERS`/`COMPANY_MASTER_SHEET_NAME`、`GlowScoring.DEFAULT_CONFIG.reactionPointsByType`(`glow-ma/src/scoring.js`で定義済み。**反応イベント種別の一覧をここで重複定義しないこと**)、`readCompanyRecords_`(`ImportRunner.gs`)、`postToSlack_`(Task 4で本ファイルに定義済み)
- Produces: `onEdit(e)`(GASのシンプルトリガー。この名前の関数はスプレッドシートが編集されるたびにGASが自動的に呼び出す。手動でのトリガー登録は不要)

- [ ] **Step 1: `glow-ma/src/AlertRunner.gs` の末尾に追記**

```js
/**
 * 即時アラート(Speed to Lead)
 * 対応履歴ログの「種別」列に、反応イベント(GlowScoring.DEFAULT_CONFIG.reactionPointsByType
 * に定義されている種別)が入力された瞬間に、シンプルトリガーとして自動実行され、
 * 即座にSlack通知する。関数名 onEdit はGASの予約された名前で、手動登録は不要。
 */
function onEdit(e) {
  if (!e || !e.range) return;
  var sheet = e.range.getSheet();
  if (sheet.getName() !== GlowSchema.INTERACTION_LOG_SHEET_NAME) return;
  if (e.range.getNumRows() !== 1 || e.range.getNumColumns() !== 1) return;

  var typeColumnIndex = GlowSchema.INTERACTION_LOG_HEADERS.indexOf("種別") + 1;
  if (e.range.getColumn() !== typeColumnIndex) return;

  var row = e.range.getRow();
  if (row < 2) return;

  var newType = e.value;
  if (typeof GlowScoring.DEFAULT_CONFIG.reactionPointsByType[newType] !== "number") return;

  var headers = GlowSchema.INTERACTION_LOG_HEADERS;
  var rowValues = sheet.getRange(row, 1, 1, headers.length).getValues()[0];
  var companyId = rowValues[headers.indexOf("企業ID")];

  var companyName = lookupCompanyName_(companyId);
  postToSlack_(
    "【即時アラート】" + companyName + "(" + companyId + ") が反応しました(" + newType + ")。至急対応してください。"
  );
}

function lookupCompanyName_(companyId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) return companyId;
  var records = readCompanyRecords_(companySheet);
  var match = records.filter(function (r) { return r["企業ID"] === companyId; })[0];
  return match ? match["会社名"] : companyId;
}
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/AlertRunner.gs /tmp/AlertRunner_check.js && node --check /tmp/AlertRunner_check.js && rm /tmp/AlertRunner_check.js` で構文チェック
2. 手書きトレース: 対応履歴ログの2行目・「種別」列(`GlowSchema.INTERACTION_LOG_HEADERS`の5列目)に`"レターURLアクセス"`と入力された想定で、`onEdit`が最後まで到達し(早期returnされず)、`postToSlack_`が呼ばれることをコードを目でたどって確認する。逆に、「種別」以外の列の編集や、`"手紙送付"`のような反応イベント対象外の値が入力された場合は、`postToSlack_`が呼ばれずに早期returnすることも確認する
3. `GlowScoring.DEFAULT_CONFIG.reactionPointsByType`のキー(`glow-ma/src/scoring.js`を実際に読んで確認)と、この関数が参照する種別が一致していることを確認する

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間がGoogleスプレッドシート・Slack上で確認する手順:

1. `clasp push` で反映(`onEdit`という名前の関数はシンプルトリガーとして自動的に有効になる)
2. 対応履歴ログに、企業マスタに実在する企業IDを持つ行を追加し、「種別」列で`"レターURLアクセス"`をプルダウンから選択する
3. Slackの対象チャンネルに即時アラートが届くことを確認する
4. 「種別」以外の列を編集した場合や、`"手紙送付"`のような対象外の値を選んだ場合には通知が来ないことを確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報・Slack Webhookがないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/AlertRunner.gs
git commit -m "feat(glow-ma): 反応イベントの即時アラート(onEdit)を追加"
```

---

### Task 6: READMEにPhase 3の使い方を追記

**Files:**
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: Task 1〜5の全成果物
- Produces: GLOWチームがSlack通知を設定・運用できるようになるドキュメント

- [ ] **Step 1: `glow-ma/README.md` の「## 次のフェーズ」の直前に以下を追記**

```markdown
## 掘り起こしアラート・即時アラート(Phase 3)

企業マスタの各社について、ランク別接触サイクル(A=30日/B=90日/C=180日/D=365日。
紹介ルートの企業は常にA相当の30日サイクル)と次回アクション予定日から掘り起こし
対象を判定し、Slackへ通知する。

**セットアップ**

1. Slackで対象チャンネル用の Incoming Webhook を発行する
2. Apps Scriptエディタの「プロジェクトの設定」→「スクリプト プロパティ」で
   `SLACK_WEBHOOK_URL` にWebhook URLを設定する(**コードには書かない**)
3. `clasp push` で最新コードを反映する

**日次バッチ**: Apps Scriptエディタの「トリガー」画面から `runDailyAlerts` を
時間主導トリガー(毎日)として手動登録する。実行すると、掘り起こし対象の企業を
ランク・ネクストベストアクション付きでSlackに通知する。

**即時アラート(Speed to Lead)**: 対応履歴ログの「種別」列に反応イベント
(レターURLアクセス・返信・ゆんたく相談実施・面談実施・資料請求)が入力されると、
`onEdit` トリガーが自動的に反応し、即座にSlackへ通知する。トリガー登録は不要
(関数名 `onEdit` はGASが自動的に認識する)。

**現時点の制約:**
- ネクストベストアクションのルール(`glow-ma/src/alerting.js`の
  `NEXT_BEST_ACTION_RULES`)は設計書8章の例をもとにした初版であり、
  GLOWチームの実務レビューを経た確定版ではない
```

- [ ] **Step 2: Commit**

```bash
git add glow-ma/README.md
git commit -m "docs(glow-ma): 掘り起こしアラート・即時アラート(Phase 3)の使い方をREADMEに追記"
```

---

## Self-Review

**Spec coverage(設計書との対応)**

- 8章(掘り起こしアラート・ネクストベストアクション・紹介ルートの常時Aサイクル例外・即時アラート)→ Task 1〜5
- 7章(提案順序ガイドライン)はドキュメントレベルの運用指針であり、コード実装対象外(冒頭に明記済み)
- 10〜12章(レター生成・ナーチャリング・ダッシュボード)は本Planの範囲外(冒頭に明記済み)

**Placeholder scan:** TBD/TODO等の記述なし。`NEXT_BEST_ACTION_RULES`は設計書8章の例をもとにした初版だが、動作するデフォルト値と、README・設計書双方への「初版である」旨の明記があり、プレースホルダーではなく運用可能な実装。

**Type consistency:** `GlowAlerting`の関数名・引数・戻り値は各Taskの Interfaces と実装コードで一致させた。`AlertRunner.gs`(Task 4, 5)はTask 1〜3で定義した関数シグネチャをそのまま呼び出しており、名前・引数の食い違いはない。即時アラートの反応イベント種別は`GlowScoring.DEFAULT_CONFIG.reactionPointsByType`を直接参照し、`alerting.js`側で重複定義しない設計とした(Phase 2最終レビューで指摘されたキーリスト重複ドリフトの再発防止)。`readCompanyRecords_`/`postToSlack_`は必要な箇所で再利用し、重複実装しない。
