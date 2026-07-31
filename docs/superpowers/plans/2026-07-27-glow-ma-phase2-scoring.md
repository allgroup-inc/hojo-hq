# GLOW M&A台帳 Phase 2(スコアリング・ランク自動計算)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 企業マスタの各企業について、属性(業種・規模・代表者年齢)・流入ルート・対応履歴ログの反応イベントからスコア(初期スコア/反応スコア/総合スコア)とランク(A〜D)を自動計算し、企業マスタに書き戻す。

**Architecture:** スコア計算ロジック(業種分類・規模/年齢の帯判定・流入ルートボーナス・反応スコア集計・ランク判定)はGAS/Node両対応のUMD形式プレーンJSとして`glow-ma/src/scoring.js`に実装し、`node --test`でユニットテストする。GAS専用の`ScoringRunner.gs`は企業マスタ・対応履歴ログを読み、`scoring.js`の関数を呼び出して結果を書き戻すだけの薄いグルーコードとする。既存のPhase 1で作った`readCompanyRecords_`/`writeCompanyRecords_`(`ImportRunner.gs`で定義済み、GASのグローバルスコープ上で再利用可能)をそのまま使い、重複実装しない。

**Tech Stack:** Google Apps Script(V8ランタイム)、Node.js組み込み`node:test`/`node:assert`(追加npm依存なし)。

**このPlanの範囲について:** 設計書(`docs/superpowers/specs/2026-07-26-glow-ma-relation-system-design.md`)の6章(スコアリング・ランク判定)と5.2節(対応履歴ログの種別確定)を実装する。7章(提案順序ガイドライン)・8章(掘り起こしアラート・紹介ルートの常時Aサイクル適用)・9章より後(名寄せは実装済み)・10〜12章(レター生成・ナーチャリング・ダッシュボード)は対象外。特に8章の「紹介ルートは総合スコアに関わらず常にAランク相当のサイクルを適用する」という例外は**アラート機能(Phase 3)側で扱う**— 本Planではスコア・ランクを設計書6章の計算式どおり素直に算出するところまでとし、アラートのサイクル判定ロジックには踏み込まない。

**スコープ上の意図的な単純化:** 設計書は「スコア重みは`設定`シートで調整可能」としているが、本Planでは`glow-ma/src/scoring.js`にエクスポートする`DEFAULT_CONFIG`定数として重み・閾値を一元管理し、`設定`シートからの動的読み込みは実装しない(値を変えたい場合は`DEFAULT_CONFIG`を編集して`clasp push`し直す運用)。動的な`設定`シート連携は将来のPhaseで検討する。業種のM&A流動性「高」分類の初期キーワードリストは、たかしくん・GLOWチームの実際の業務知見に基づくレビューがまだ済んでいない**たたき台**であることをコード内コメントとREADMEに明記する。

## Global Constraints

- 公開リポジトリ(hojo-hq)に実データを一切コミットしない(設計書4.2節。本Planは実データを一切扱わない)
- GASとNode両方で動くファイルはUMD形式(`typeof module !== "undefined" && module.exports`で分岐)を踏襲する(`glow-ma/src/schema.js`・`dedupe.js`・`csvImport.js`と同じパターン)
- 追加のnpm依存を増やさない。テストは`node --test` + `node:assert/strict`を使う
- 企業マスタ・対応履歴ログの列名は設計書5章/`glow-ma/src/schema.js`の定義に厳密に従う。列を追加・変更しない
- 反応スコアの対象となる「種別」は設計書5.2節で確定した15種のみ。表記ゆれを防ぐため`対応履歴ログ`の「種別」列には入力規則(プルダウン)を設定する
- スコア計算式は設計書6章(2026-07-27 glow-ma-triangle-review確定版)の通りに実装する: 総合スコア = 属性スコア(業種+規模+年齢) + 流入ルートボーナス(初期スコアに含む) + 反応スコア。ランク閾値はA:70以上/B:40〜69/C:15〜39/D:14以下
- GAS専用ファイル(`.gs`)は`node --test`で検証できないため、静的チェック(`node --check`)と手書きトレースで代替し、実運用前の手動検証が必要であることをレポートに明記する(Phase 1と同じ扱い)

---

## File Structure

```
glow-ma/src/
  schema.js          — 既存ファイルを修正: INTERACTION_TYPES(種別の確定15値)を追加(Task 1)
  scoring.js          — 新規: スコア計算ロジック(GlowScoring)(Task 2, 3)
  SheetSetup.gs        — 既存ファイルを修正: 対応履歴ログの「種別」列に入力規則を追加(Task 4)
  ScoringRunner.gs      — 新規: 企業マスタ全件のスコア・ランク再計算(Task 5、GAS専用)
tests/
  glow_ma_schema.test.mjs   — 既存ファイルに追記(Task 1)
  glow_ma_scoring.test.mjs   — 新規(Task 2, 3)
glow-ma/README.md      — Phase 2の使い方を追記(Task 6)
```

---

### Task 1: `schema.js` に対応履歴ログの種別リストを追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Modify: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowSchema.INTERACTION_TYPES`(string[]、15要素)。Task 4(`SheetSetup.gs`のプルダウン設定)とTask 5(反応スコア判定時の参考)が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs` の末尾に追記:

```js
test("対応履歴ログの種別(INTERACTION_TYPES)が設計書5.2節の15種と一致する", () => {
  const expected = [
    "手紙送付", "電話", "ゆんたく相談実施", "面談実施", "紹介受領", "ミカタ接点確認",
    "レターURLアクセス", "返信", "資料請求",
    "提案(M&A)", "提案(不動産)", "提案(法人保険)",
    "成約", "見送り", "ナーチャリング配信"
  ];
  assert.deepEqual(schema.INTERACTION_TYPES, expected);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(`schema.INTERACTION_TYPES` が `undefined` のため `assert.deepEqual` が失敗)

- [ ] **Step 3: `glow-ma/src/schema.js` に `INTERACTION_TYPES` を追加**

`INTERACTION_LOG_HEADERS` の定義の直後に追加する:

```js
  var INTERACTION_TYPES = [
    "手紙送付", "電話", "ゆんたく相談実施", "面談実施", "紹介受領", "ミカタ接点確認",
    "レターURLアクセス", "返信", "資料請求",
    "提案(M&A)", "提案(不動産)", "提案(法人保険)",
    "成約", "見送り", "ナーチャリング配信"
  ];
```

`api`オブジェクトに追加する(既存のプロパティはそのまま残し、以下を追記):

```js
  var api = {
    COMPANY_MASTER_SHEET_NAME: COMPANY_MASTER_SHEET_NAME,
    COMPANY_MASTER_HEADERS: COMPANY_MASTER_HEADERS,
    INTERACTION_LOG_SHEET_NAME: INTERACTION_LOG_SHEET_NAME,
    INTERACTION_LOG_HEADERS: INTERACTION_LOG_HEADERS,
    INTERACTION_TYPES: INTERACTION_TYPES,
    PARTNER_MASTER_SHEET_NAME: PARTNER_MASTER_SHEET_NAME,
    PARTNER_MASTER_HEADERS: PARTNER_MASTER_HEADERS,
    SETTINGS_SHEET_NAME: SETTINGS_SHEET_NAME,
    SETTINGS_HEADERS: SETTINGS_HEADERS
  };
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(既存5テスト + 新規1テスト = 6テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): 対応履歴ログの種別(INTERACTION_TYPES)をスキーマに追加"
```

---

### Task 2: `scoring.js` — 属性スコア(業種・規模・代表者年齢)

**Files:**
- Create: `glow-ma/src/scoring.js`
- Test: `tests/glow_ma_scoring.test.mjs`

**Interfaces:**
- Consumes: なし(企業レコードはプレーンオブジェクト。`業種`/`規模`/`代表者年齢`はstring)
- Produces: `GlowScoring`オブジェクト。`DEFAULT_CONFIG`(object、以降のTaskとGAS側が参照する既定設定)、`classifyIndustryTier(industryText, config)`: "high"|"mid"|"low"、`calculateSizeBandPoints(sizeText, config)`: number、`calculateAgeBandPoints(ageText, config)`: number、`calculateAttributeScore(company, config)`: number(configは省略可、省略時は`DEFAULT_CONFIG`を使う)

#### 2-1. `DEFAULT_CONFIG` と `classifyIndustryTier`

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_scoring.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const scoring = require("../glow-ma/src/scoring.js");

test("DEFAULT_CONFIG にランク閾値A:70/B:40/C:15が設定されている(2026-07-27 triangle-review確定値)", () => {
  assert.deepEqual(scoring.DEFAULT_CONFIG.rankThresholds, { A: 70, B: 40, C: 15 });
});

test("classifyIndustryTier: 高流動性業種のキーワードを含むとhigh", () => {
  assert.equal(scoring.classifyIndustryTier("建設業", scoring.DEFAULT_CONFIG), "high");
  assert.equal(scoring.classifyIndustryTier("一般貨物自動車運送業", scoring.DEFAULT_CONFIG), "high");
});

test("classifyIndustryTier: 未一致の業種はmid(中立)扱い", () => {
  assert.equal(scoring.classifyIndustryTier("情報通信業", scoring.DEFAULT_CONFIG), "mid");
  assert.equal(scoring.classifyIndustryTier("", scoring.DEFAULT_CONFIG), "mid");
  assert.equal(scoring.classifyIndustryTier(null, scoring.DEFAULT_CONFIG), "mid");
});

test("classifyIndustryTier: configを省略した場合はDEFAULT_CONFIGが使われる", () => {
  assert.equal(scoring.classifyIndustryTier("建設業"), "high");
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: FAIL(`glow-ma/src/scoring.js`が存在しない)

- [ ] **Step 3: `glow-ma/src/scoring.js` を作成し `DEFAULT_CONFIG` と `classifyIndustryTier` を実装**

```js
/* GLOW企業リレーション台帳 スコアリング・ランク判定ロジック
 * ブラウザ相当のGAS(global.GlowScoring)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_scoring.test.mjs で検証される。
 *
 * 数値の根拠: docs/superpowers/specs/2026-07-27-glow-ma-scoring-triangle-review.md
 * (2026-07-27 glow-ma-triangle-review確定、見直し期限2026-10-27)。
 *
 * industryTiers.high は「事業承継ニーズが相対的に高いとされる業種」のたたき台キーワード
 * リストであり、GLOWチームの実務レビューを経た確定版ではない。運用しながら見直すこと。
 */
(function (global) {
  "use strict";

  var DEFAULT_CONFIG = {
    industryTiers: {
      high: ["建設", "運送", "介護", "美容", "理容", "飲食", "小売"],
      low: []
    },
    industryTierPoints: { high: 20, mid: 10, low: 0 },
    sizeBands: [
      { min: 10, max: 50, points: 10 },
      { min: 5, max: 9, points: 5 },
      { min: 51, max: 100, points: 5 }
    ],
    ageBands: [
      { min: 70, max: Infinity, points: 15 },
      { min: 60, max: 69, points: 10 },
      { min: 50, max: 59, points: 5 }
    ],
    routeBonus: { "①紹介": 30, "②手紙DM": 0, "③ミカタ経由": 20 },
    reactionPointsByType: {
      "レターURLアクセス": 5,
      "返信": 15,
      "ゆんたく相談実施": 25,
      "面談実施": 25,
      "資料請求": 10
    },
    decisionMakerBonus: 15,
    rankThresholds: { A: 70, B: 40, C: 15 }
  };

  function classifyIndustryTier(industryText, config) {
    config = config || DEFAULT_CONFIG;
    var text = String(industryText || "");
    var matchesAny = function (keywords) {
      return (keywords || []).some(function (keyword) {
        return text.indexOf(keyword) !== -1;
      });
    };
    if (matchesAny(config.industryTiers.high)) return "high";
    if (matchesAny(config.industryTiers.low)) return "low";
    return "mid";
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    classifyIndustryTier: classifyIndustryTier
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowScoring = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: PASS(4 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/scoring.js tests/glow_ma_scoring.test.mjs
git commit -m "feat(glow-ma): スコアリング設定と業種分類ロジックを追加"
```

#### 2-2. `calculateSizeBandPoints` / `calculateAgeBandPoints`

- [ ] **Step 6: 失敗するテストを追記**

`tests/glow_ma_scoring.test.mjs` に追記:

```js
test("calculateSizeBandPoints: 10〜50名は10点", () => {
  assert.equal(scoring.calculateSizeBandPoints("30名", scoring.DEFAULT_CONFIG), 10);
  assert.equal(scoring.calculateSizeBandPoints("10名", scoring.DEFAULT_CONFIG), 10);
  assert.equal(scoring.calculateSizeBandPoints("50名", scoring.DEFAULT_CONFIG), 10);
});

test("calculateSizeBandPoints: 5〜9名・51〜100名は5点", () => {
  assert.equal(scoring.calculateSizeBandPoints("7名", scoring.DEFAULT_CONFIG), 5);
  assert.equal(scoring.calculateSizeBandPoints("80名", scoring.DEFAULT_CONFIG), 5);
});

test("calculateSizeBandPoints: 範囲外・空・数字なしは0点", () => {
  assert.equal(scoring.calculateSizeBandPoints("2名", scoring.DEFAULT_CONFIG), 0);
  assert.equal(scoring.calculateSizeBandPoints("", scoring.DEFAULT_CONFIG), 0);
  assert.equal(scoring.calculateSizeBandPoints(null, scoring.DEFAULT_CONFIG), 0);
});

test("calculateAgeBandPoints: 年齢帯ごとの加点", () => {
  assert.equal(scoring.calculateAgeBandPoints("72歳", scoring.DEFAULT_CONFIG), 15);
  assert.equal(scoring.calculateAgeBandPoints("65", scoring.DEFAULT_CONFIG), 10);
  assert.equal(scoring.calculateAgeBandPoints("55歳", scoring.DEFAULT_CONFIG), 5);
  assert.equal(scoring.calculateAgeBandPoints("40歳", scoring.DEFAULT_CONFIG), 0);
});

test("calculateAgeBandPoints: データ欠損時は0点(任意加点、モデルを歪ませない)", () => {
  assert.equal(scoring.calculateAgeBandPoints("", scoring.DEFAULT_CONFIG), 0);
  assert.equal(scoring.calculateAgeBandPoints(undefined, scoring.DEFAULT_CONFIG), 0);
});
```

- [ ] **Step 7: テストが失敗することを確認**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: FAIL(`scoring.calculateSizeBandPoints is not a function`)

- [ ] **Step 8: `calculateSizeBandPoints` / `calculateAgeBandPoints` を実装**

`glow-ma/src/scoring.js` の `classifyIndustryTier` 関数の直後に追加する:

```js
  function extractNumber(text) {
    var match = String(text || "").match(/\d+/);
    return match ? parseInt(match[0], 10) : null;
  }

  function findBandPoints(numericValue, bands) {
    for (var i = 0; i < bands.length; i++) {
      var band = bands[i];
      if (numericValue >= band.min && numericValue <= band.max) return band.points;
    }
    return 0;
  }

  function calculateSizeBandPoints(sizeText, config) {
    config = config || DEFAULT_CONFIG;
    var n = extractNumber(sizeText);
    if (n === null) return 0;
    return findBandPoints(n, config.sizeBands);
  }

  function calculateAgeBandPoints(ageText, config) {
    config = config || DEFAULT_CONFIG;
    var n = extractNumber(ageText);
    if (n === null) return 0;
    return findBandPoints(n, config.ageBands);
  }
```

`api`オブジェクトを次のように更新する:

```js
  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    classifyIndustryTier: classifyIndustryTier,
    calculateSizeBandPoints: calculateSizeBandPoints,
    calculateAgeBandPoints: calculateAgeBandPoints
  };
```

- [ ] **Step 9: テストが通ることを確認**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: PASS(9 tests)

- [ ] **Step 10: Commit**

```bash
git add glow-ma/src/scoring.js tests/glow_ma_scoring.test.mjs
git commit -m "feat(glow-ma): 規模・代表者年齢の帯判定ロジックを追加"
```

#### 2-3. `calculateAttributeScore`

- [ ] **Step 11: 失敗するテストを追記**

`tests/glow_ma_scoring.test.mjs` に追記:

```js
test("calculateAttributeScore: 業種・規模・年齢の加点を合算する", () => {
  const company = { 業種: "建設業", 規模: "30名", 代表者年齢: "72歳" };
  // 業種high(20) + 規模30名(10) + 年齢72歳(15) = 45
  assert.equal(scoring.calculateAttributeScore(company, scoring.DEFAULT_CONFIG), 45);
});

test("calculateAttributeScore: 代表者年齢が空でも他の加点は計算される", () => {
  const company = { 業種: "情報通信業", 規模: "200名", 代表者年齢: "" };
  // 業種mid(10) + 規模200名は範囲外(0) + 年齢なし(0) = 10
  assert.equal(scoring.calculateAttributeScore(company, scoring.DEFAULT_CONFIG), 10);
});
```

- [ ] **Step 12: テストが失敗することを確認**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: FAIL(`scoring.calculateAttributeScore is not a function`)

- [ ] **Step 13: `calculateAttributeScore` を実装**

`glow-ma/src/scoring.js` の `calculateAgeBandPoints` 関数の直後に追加する:

```js
  function calculateAttributeScore(company, config) {
    config = config || DEFAULT_CONFIG;
    var tier = classifyIndustryTier(company["業種"], config);
    var industryPoints = config.industryTierPoints[tier] || 0;
    var sizePoints = calculateSizeBandPoints(company["規模"], config);
    var agePoints = calculateAgeBandPoints(company["代表者年齢"], config);
    return industryPoints + sizePoints + agePoints;
  }
```

`api`オブジェクトを次のように更新する:

```js
  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    classifyIndustryTier: classifyIndustryTier,
    calculateSizeBandPoints: calculateSizeBandPoints,
    calculateAgeBandPoints: calculateAgeBandPoints,
    calculateAttributeScore: calculateAttributeScore
  };
```

- [ ] **Step 14: テストが通ることを確認**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: PASS(11 tests)

- [ ] **Step 15: Commit**

```bash
git add glow-ma/src/scoring.js tests/glow_ma_scoring.test.mjs
git commit -m "feat(glow-ma): 属性スコア(業種+規模+年齢)の合算ロジックを追加"
```

---

### Task 3: `scoring.js` — 流入ルートボーナス・反応スコア・ランク判定

**Files:**
- Modify: `glow-ma/src/scoring.js`
- Modify: `tests/glow_ma_scoring.test.mjs`

**Interfaces:**
- Consumes: Task 2の`DEFAULT_CONFIG`
- Produces: `calculateRouteBonus(routes, config)`: number(routesはstring[])、`calculateReactionScore(interactionRows, config)`: number(interactionRowsは`{種別, 対応相手}`形状のオブジェクト配列)、`calculateRank(totalScore, config)`: "A"|"B"|"C"|"D"。Task 5の`ScoringRunner.gs`がこれらと Task 2の関数をすべて呼び出す

#### 3-1. `calculateRouteBonus`

- [ ] **Step 1: 失敗するテストを追記**

`tests/glow_ma_scoring.test.mjs` に追記:

```js
test("calculateRouteBonus: 複数ルートがある場合は最大値を採用する", () => {
  assert.equal(scoring.calculateRouteBonus(["②手紙DM", "①紹介"], scoring.DEFAULT_CONFIG), 30);
  assert.equal(scoring.calculateRouteBonus(["③ミカタ経由"], scoring.DEFAULT_CONFIG), 20);
  assert.equal(scoring.calculateRouteBonus(["②手紙DM"], scoring.DEFAULT_CONFIG), 0);
});

test("calculateRouteBonus: ルートが空配列なら0", () => {
  assert.equal(scoring.calculateRouteBonus([], scoring.DEFAULT_CONFIG), 0);
  assert.equal(scoring.calculateRouteBonus(undefined, scoring.DEFAULT_CONFIG), 0);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: FAIL(`scoring.calculateRouteBonus is not a function`)

- [ ] **Step 3: `calculateRouteBonus` を実装**

`glow-ma/src/scoring.js` の `calculateAttributeScore` 関数の直後に追加する:

```js
  function calculateRouteBonus(routes, config) {
    config = config || DEFAULT_CONFIG;
    var max = 0;
    (routes || []).forEach(function (route) {
      var points = config.routeBonus[route];
      if (typeof points === "number" && points > max) max = points;
    });
    return max;
  }
```

`api`オブジェクトに `calculateRouteBonus: calculateRouteBonus` を追加する。

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: PASS(13 tests)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/scoring.js tests/glow_ma_scoring.test.mjs
git commit -m "feat(glow-ma): 流入ルートボーナス(最大値採用)ロジックを追加"
```

#### 3-2. `calculateReactionScore`

- [ ] **Step 6: 失敗するテストを追記**

`tests/glow_ma_scoring.test.mjs` に追記:

```js
test("calculateReactionScore: 種別ごとの加点を合算する", () => {
  const rows = [
    { 種別: "レターURLアクセス", 対応相手: "未接触" },
    { 種別: "ゆんたく相談実施", 対応相手: "経理・総務等の窓口担当" }
  ];
  // レターURLアクセス(5) + ゆんたく相談実施(25) = 30
  assert.equal(scoring.calculateReactionScore(rows, scoring.DEFAULT_CONFIG), 30);
});

test("calculateReactionScore: 対応相手がオーナー社長本人なら種別を問わず+15", () => {
  const rows = [{ 種別: "電話", 対応相手: "オーナー社長本人" }];
  // 電話は反応イベント対象外(0) + 意思決定者ボーナス(15) = 15
  assert.equal(scoring.calculateReactionScore(rows, scoring.DEFAULT_CONFIG), 15);
});

test("calculateReactionScore: 反応イベント対象外の種別(手紙送付・電話等)は加点しない", () => {
  const rows = [
    { 種別: "手紙送付", 対応相手: "未接触" },
    { 種別: "ミカタ接点確認", 対応相手: "未接触" }
  ];
  assert.equal(scoring.calculateReactionScore(rows, scoring.DEFAULT_CONFIG), 0);
});

test("calculateReactionScore: 履歴が空なら0", () => {
  assert.equal(scoring.calculateReactionScore([], scoring.DEFAULT_CONFIG), 0);
  assert.equal(scoring.calculateReactionScore(undefined, scoring.DEFAULT_CONFIG), 0);
});
```

- [ ] **Step 7: テストが失敗することを確認**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: FAIL(`scoring.calculateReactionScore is not a function`)

- [ ] **Step 8: `calculateReactionScore` を実装**

`glow-ma/src/scoring.js` の `calculateRouteBonus` 関数の直後に追加する:

```js
  function calculateReactionScore(interactionRows, config) {
    config = config || DEFAULT_CONFIG;
    var total = 0;
    (interactionRows || []).forEach(function (row) {
      var typePoints = config.reactionPointsByType[row["種別"]];
      if (typeof typePoints === "number") total += typePoints;
      if (row["対応相手"] === "オーナー社長本人") total += config.decisionMakerBonus;
    });
    return total;
  }
```

`api`オブジェクトに `calculateReactionScore: calculateReactionScore` を追加する。

- [ ] **Step 9: テストが通ることを確認**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: PASS(17 tests)

- [ ] **Step 10: Commit**

```bash
git add glow-ma/src/scoring.js tests/glow_ma_scoring.test.mjs
git commit -m "feat(glow-ma): 対応履歴ログからの反応スコア集計ロジックを追加"
```

#### 3-3. `calculateRank`

- [ ] **Step 11: 失敗するテストを追記**

`tests/glow_ma_scoring.test.mjs` に追記:

```js
test("calculateRank: 閾値どおりにA〜Dへ分類する", () => {
  assert.equal(scoring.calculateRank(70, scoring.DEFAULT_CONFIG), "A");
  assert.equal(scoring.calculateRank(100, scoring.DEFAULT_CONFIG), "A");
  assert.equal(scoring.calculateRank(69, scoring.DEFAULT_CONFIG), "B");
  assert.equal(scoring.calculateRank(40, scoring.DEFAULT_CONFIG), "B");
  assert.equal(scoring.calculateRank(39, scoring.DEFAULT_CONFIG), "C");
  assert.equal(scoring.calculateRank(15, scoring.DEFAULT_CONFIG), "C");
  assert.equal(scoring.calculateRank(14, scoring.DEFAULT_CONFIG), "D");
  assert.equal(scoring.calculateRank(0, scoring.DEFAULT_CONFIG), "D");
});
```

- [ ] **Step 12: テストが失敗することを確認**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: FAIL(`scoring.calculateRank is not a function`)

- [ ] **Step 13: `calculateRank` を実装**

`glow-ma/src/scoring.js` の `calculateReactionScore` 関数の直後に追加する:

```js
  function calculateRank(totalScore, config) {
    config = config || DEFAULT_CONFIG;
    var t = config.rankThresholds;
    if (totalScore >= t.A) return "A";
    if (totalScore >= t.B) return "B";
    if (totalScore >= t.C) return "C";
    return "D";
  }
```

`api`オブジェクトを次のように更新する(最終形):

```js
  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    classifyIndustryTier: classifyIndustryTier,
    calculateSizeBandPoints: calculateSizeBandPoints,
    calculateAgeBandPoints: calculateAgeBandPoints,
    calculateAttributeScore: calculateAttributeScore,
    calculateRouteBonus: calculateRouteBonus,
    calculateReactionScore: calculateReactionScore,
    calculateRank: calculateRank
  };
```

- [ ] **Step 14: テストが通ることを確認**

Run: `node --test tests/glow_ma_scoring.test.mjs`
Expected: PASS(25 tests)

- [ ] **Step 15: Commit**

```bash
git add glow-ma/src/scoring.js tests/glow_ma_scoring.test.mjs
git commit -m "feat(glow-ma): ランク判定ロジックを追加"
```

---

### Task 4: `SheetSetup.gs` — 対応履歴ログの種別にプルダウンを設定(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/SheetSetup.gs`

**Interfaces:**
- Consumes: `GlowSchema.INTERACTION_TYPES`(Task 1)
- Produces: `ensureLedgerTabs()`が実行されると、対応履歴ログの「種別」列(2行目以降)にプルダウン入力規則が設定される

- [ ] **Step 1: `glow-ma/src/SheetSetup.gs` を修正**

現在のファイル全体を次の内容に置き換える:

```js
/**
 * GLOW企業リレーション台帳: シート初期化
 * Apps Scriptエディタの関数選択で ensureLedgerTabs を選び、実行ボタンで手動実行する。
 * 実行すると「企業マスタ」「対応履歴ログ」「紹介パートナーマスタ」「設定」の
 * 4タブが(存在しなければ)作成され、1行目に見出しが設定される。
 * 対応履歴ログの「種別」列には、表記ゆれによる反応スコア集計漏れを防ぐため
 * プルダウン入力規則(GlowSchema.INTERACTION_TYPES)を設定する。
 */
function ensureLedgerTabs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ensureTab_(ss, GlowSchema.COMPANY_MASTER_SHEET_NAME, GlowSchema.COMPANY_MASTER_HEADERS);
  var logSheet = ensureTab_(ss, GlowSchema.INTERACTION_LOG_SHEET_NAME, GlowSchema.INTERACTION_LOG_HEADERS);
  applyInteractionTypeValidation_(logSheet);
  ensureTab_(ss, GlowSchema.PARTNER_MASTER_SHEET_NAME, GlowSchema.PARTNER_MASTER_HEADERS);
  ensureTab_(ss, GlowSchema.SETTINGS_SHEET_NAME, GlowSchema.SETTINGS_HEADERS);
}

function ensureTab_(spreadsheet, sheetName, headers) {
  var sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.setFrozenRows(1);
  return sheet;
}

function applyInteractionTypeValidation_(sheet) {
  var typeColumnIndex = GlowSchema.INTERACTION_LOG_HEADERS.indexOf("種別") + 1;
  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(GlowSchema.INTERACTION_TYPES, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(2, typeColumnIndex, Math.max(sheet.getMaxRows() - 1, 1), 1).setDataValidation(rule);
}
```

- [ ] **Step 2: 静的チェック**

Run: `node --check glow-ma/src/SheetSetup.gs`(拡張子が`.gs`のためNodeが直接解釈できない場合は、一時的に`.js`拡張子でコピーしてチェックする。例: `cp glow-ma/src/SheetSetup.gs /tmp/SheetSetup_check.js && node --check /tmp/SheetSetup_check.js && rm /tmp/SheetSetup_check.js`)
Expected: 構文エラーなし

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境(SpreadsheetApp)が必要なため、この環境では実行できない。以下は人間がGoogleスプレッドシート上で確認する手順:

1. `clasp push` で反映
2. `ensureLedgerTabs` を実行
3. 「対応履歴ログ」タブを開き、「種別」列(2行目以降)のセルをクリックしてプルダウンが表示され、`GlowSchema.INTERACTION_TYPES`の15項目が選択肢に出ることを確認する
4. リストにない値を手入力しようとするとエラーになることを確認する(`setAllowInvalid(false)`)

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/SheetSetup.gs
git commit -m "feat(glow-ma): 対応履歴ログの種別にプルダウン入力規則を追加"
```

---

### Task 5: `ScoringRunner.gs` — 企業マスタ全件のスコア・ランク再計算(GAS専用・手動検証)

**Files:**
- Create: `glow-ma/src/ScoringRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema`(Task 1)、`GlowScoring.calculateAttributeScore`/`calculateRouteBonus`/`calculateReactionScore`/`calculateRank`(Task 2, 3)、`readCompanyRecords_`/`writeCompanyRecords_`(`glow-ma/src/ImportRunner.gs`で定義済み。**再定義しないこと** — GASは1プロジェクト内の全ファイルが同じグローバルスコープを共有するため、そのまま呼び出せる)
- Produces: `recalculateAllScores()`関数(引数なし)。企業マスタの「初期スコア」「反応スコア」「総合スコア」「ランク」列を全行分再計算して書き戻す

- [ ] **Step 1: `glow-ma/src/ScoringRunner.gs` を実装**

```js
/**
 * GLOW企業リレーション台帳: スコア・ランクの一括再計算
 * Apps Scriptエディタの関数選択で recalculateAllScores を選び、実行ボタンで手動実行する。
 * (将来的には日次の時間主導トリガーに登録して自動実行することを想定しているが、
 *  トリガー登録自体は本Planの範囲外。)
 *
 * 企業マスタの「初期スコア」= 属性スコア(業種+規模+代表者年齢) + 流入ルートボーナス
 * 「反応スコア」= 対応履歴ログの反応イベントの合算(GlowScoring.calculateReactionScore)
 * 「総合スコア」= 初期スコア + 反応スコア、「ランク」= 総合スコアからA〜Dを判定
 *
 * readCompanyRecords_ / writeCompanyRecords_ は glow-ma/src/ImportRunner.gs で
 * 定義済みのため、ここでは再定義せずそのまま呼び出す。
 */
function recalculateAllScores() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }

  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  var interactionsByCompanyId = readInteractionsByCompanyId_(logSheet);

  var records = readCompanyRecords_(companySheet);
  records.forEach(function (record) {
    var interactionRows = interactionsByCompanyId[record["企業ID"]] || [];
    var initialScore = GlowScoring.calculateAttributeScore(record) + GlowScoring.calculateRouteBonus(record["流入ルート"]);
    var reactionScore = GlowScoring.calculateReactionScore(interactionRows);
    var totalScore = initialScore + reactionScore;

    record["初期スコア"] = initialScore;
    record["反応スコア"] = reactionScore;
    record["総合スコア"] = totalScore;
    record["ランク"] = GlowScoring.calculateRank(totalScore);
  });

  writeCompanyRecords_(companySheet, records);
  Logger.log("スコア再計算完了: " + records.length + "件");
}

function readInteractionsByCompanyId_(sheet) {
  var result = {};
  if (!sheet) return result;
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return result;
  var headers = GlowSchema.INTERACTION_LOG_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  values.forEach(function (row) {
    var record = {};
    headers.forEach(function (header, i) {
      record[header] = row[i];
    });
    var companyId = record["企業ID"];
    if (!companyId) return;
    if (!result[companyId]) result[companyId] = [];
    result[companyId].push(record);
  });
  return result;
}
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `node --check`相当の構文チェックを行う(`.gs`を一時的に`.js`としてコピーして`node --check`、または注意深く目視で確認)
2. 手書きトレース: 企業マスタに以下2件がある想定で、期待される最終値を計算して報告する
   - 企業A: `業種="建設業"`, `規模="30名"`, `代表者年齢="72歳"`, `流入ルート=["②手紙DM"]`。対応履歴ログに`種別="ゆんたく相談実施"`, `対応相手="オーナー社長本人"`が1件。
     - 属性スコア = 20(建設=high)+10(30名)+15(72歳) = 45、流入ルートボーナス = 0、初期スコア = 45
     - 反応スコア = 25(ゆんたく相談実施)+15(オーナー社長本人) = 40
     - 総合スコア = 45+40 = 85 → ランクA
   - 企業B: `業種="情報通信業"`, `規模="200名"`, `代表者年齢=""`, `流入ルート=["①紹介"]`。対応履歴ログなし。
     - 属性スコア = 10(mid)+0(範囲外)+0(年齢なし) = 10、流入ルートボーナス = 30、初期スコア = 40
     - 反応スコア = 0
     - 総合スコア = 40 → ランクB
   - 上記の期待値と、コードを実際に手でたどった結果が一致することをレポートに記録する

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。以下は人間がGoogleスプレッドシート上で確認する手順:

1. `clasp push` で反映
2. Task 2の手書きトレースと同じ2社分のデータを企業マスタ・対応履歴ログに手入力する
3. `recalculateAllScores` を実行し、企業マスタの初期スコア/反応スコア/総合スコア/ランクが手書きトレースの期待値と一致することを確認する

レポートには「この手動検証はサンドボックス環境のGoogle認証情報がないため未実施」と明記すること。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/ScoringRunner.gs
git commit -m "feat(glow-ma): 企業マスタ全件のスコア・ランク再計算機能を追加"
```

---

### Task 6: READMEにPhase 2の使い方を追記

**Files:**
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: Task 1〜5の全成果物
- Produces: GLOWチームがスコア再計算を実行できるようになるドキュメント

- [ ] **Step 1: `glow-ma/README.md` の末尾(「## 次のフェーズ」の直前)に以下を追記**

```markdown
## スコア・ランクの再計算(Phase 2)

企業マスタの各社について、業種・規模・代表者年齢・流入ルート・対応履歴ログの
反応イベントからスコアとランク(A〜D)を自動計算する。

1. `clasp push` で最新コードを反映する
2. Apps Scriptエディタで `recalculateAllScores` を実行する
3. 企業マスタの「初期スコア」「反応スコア」「総合スコア」「ランク」列が更新される

**現時点の制約:**
- スコアの重み・閾値は `glow-ma/src/scoring.js` の `DEFAULT_CONFIG` にハードコードされており、
  `設定` シートからの動的な読み込みはまだ実装していない。値を調整したい場合は
  `DEFAULT_CONFIG` を編集して `clasp push` し直す
- 業種のM&A流動性「高」判定に使っているキーワードリスト(建設・運送・介護・美容・理容・
  飲食・小売)は、GLOWチームの実務レビューを経た確定版ではない**たたき台**。
  実データを見ながら見直すこと(見直し期限: 2026-10-27、
  `docs/superpowers/specs/2026-07-27-glow-ma-scoring-triangle-review.md` 参照)
- 対応履歴ログの「種別」は、反応スコアの集計対象になるかどうかが値によって決まる。
  必ずプルダウンから選択すること(自由入力の表記ゆれは集計に反映されない)
```

- [ ] **Step 2: Commit**

```bash
git add glow-ma/README.md
git commit -m "docs(glow-ma): スコア再計算(Phase 2)の使い方をREADMEに追記"
```

---

## Self-Review

**Spec coverage(設計書との対応)**

- 5.2節(対応履歴ログの種別確定・プルダウン化)→ Task 1, 4
- 6章(スコアリング・ランク判定、2026-07-27確定値)→ Task 2, 3, 5
- 6章「月次の重み見直し」の運用は、`DEFAULT_CONFIG`を単一の編集箇所として一元化することで対応可能な形にした(実際の見直し運用はコード変更を伴うため、月次レビュー時に人間が対応する)
- 7章(提案順序)・8章(アラート・紹介ルートの常時Aサイクル)・10〜12章(レター生成・ナーチャリング・ダッシュボード)は本Planの範囲外(冒頭に明記済み)。8章の紹介ルート例外は次のPhase 3 Planで対応する

**Placeholder scan:** TBD/TODO等の記述なし。`DEFAULT_CONFIG`の業種キーワードリストは実データ未検証の「たたき台」だが、動作するデフォルト値・根拠(triangle-review記録へのリンク)・見直し期限を明記しており、プレースホルダーではなく運用可能な実装。

**Type consistency:** `GlowScoring`の関数名・引数・戻り値は各Taskの Interfaces と実装コードで一致させた。`ScoringRunner.gs`(Task 5)はTask 2・3で定義した関数シグネチャ(`calculateAttributeScore(company, config)`等、configは省略可能)をそのまま呼び出しており、名前・引数の食い違いはない。`readCompanyRecords_`/`writeCompanyRecords_`は新規定義せず、Phase 1の`ImportRunner.gs`の実装をそのまま再利用する設計とした(DRY)。
