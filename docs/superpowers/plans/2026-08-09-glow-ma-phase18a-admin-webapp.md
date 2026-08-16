# glow-ma Phase 18a(管理画面Web App化・企業一覧/詳細の閲覧)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 既存の「GLOW企業リレーション台帳(glow-ma) 管理画面デモ」(クライアントサイドのみのモック)を、実際に稼働中のGoogleスプレッドシートと接続した本物のWeb管理画面にする第一段階として、小柳・福田・嶺井の3名が企業一覧を検索・絞り込みし、企業詳細(概要・対応履歴)を閲覧できる読み取り専用画面を作る。

**Architecture:** 既存GASプロジェクト内で完結させる(方式A、設計書1章)。既存`TrackingWebApp.gs`の`doGet(e)`に`page=admin`の分岐を追加し、許可リスト(スタッフタブのメールアドレス)に一致する場合のみ管理画面のHTMLを返す。データ取得は`google.script.run`経由で`AdminRunner.gs`のサーバー関数を呼ぶ。許可リスト照合・企業一覧の絞り込み/並び替え/最小フィールド抽出といった純粋ロジックは`glow-ma/src/adminAccess.js`にUMD形式で切り出し、`node --test`でテストする。画面のHTML/JSは、既存の`shareDialog.js`(Slack共有ダイアログ)と同じ慣習に従い、独立した`.html`アセットではなく`glow-ma/src/adminApp.js`(UMD)内で文字列として組み立てる。

**Tech Stack:** Google Apps Script(V8ランタイム、`HtmlService`、`google.script.run`、Web Appデプロイ)、Node.js組み込み`node:test`/`node:assert`(追加npm依存なし)。

**このPlanの背景:** 三名体制レビュー(`docs/superpowers/specs/2026-08-09-glow-ma-admin-webapp-phase18a-design.md`8章)で「採用(条件付き)」の裁定を得た設計を実装する。デモの全機能のうち、本Planは「企業一覧・詳細の閲覧(読み取り専用)」のみを対象とする(書き込み系・スタッフ共有・KPI集計は後続のPhase 18b/18c/18dで別途計画する)。

## Global Constraints

- 認証は`Session.getActiveUser().getEmail()`を使う(`Session.getEffectiveUser()`は実行ユーザー=常に自分を返すため誤り。三名体制レビュー裁定1)
- `getActiveUser().getEmail()`が空文字を返す場合は「未認証」として拒否する(裁定1)
- 許可リストチェックは`doGet`の初回だけでなく、`getCompanyList_`・`getCompanyDetail_`など公開される各サーバー関数の冒頭でも個別に行う(多層防御、裁定2)。デプロイを分けたこと自体を安全性の根拠にしない
- `doGet`はルーティングと許可リストチェックのみとし、実処理は`AdminRunner.gs`へ完全委譲する(裁定3)
- 一覧取得(`getCompanyList_`)が返すフィールドは企業ID・会社名・ランク・現在ステージ・次回アクション予定日・担当者の6つに限定する。携帯番号・関係メモ・所在地などの機微情報は詳細取得(`getCompanyDetail_`)でのみ返す(裁定4)
- 一覧は絞り込み条件(検索語・ランク・現在ステージ・担当者のいずれか)を1つも指定していない場合、`次回アクション予定日`降順の上位100件のみ返す。全7000件の一括返却はしない(設計書3章)
- 本機能は読み取り専用。企業マスタ・対応履歴ログへの書き込みは一切行わない(書き込みはPhase 18b以降)
- GASとNode両方で動くファイルはUMD形式(`typeof module !== "undefined" && module.exports`で分岐)を踏襲する
- HTML画面は独立した`.html`アセットではなく、UMD形式のJSファイル内で文字列として組み立てる(`shareDialog.js`と同じ慣習)
- 追加のnpm依存を増やさない。テストは`node --test` + `node:assert/strict`を使う
- GAS専用ファイル(`.gs`)は`node --test`で検証できないため、静的チェック(`node --check`)と手書きトレースで代替し、実運用前の手動検証が必要であることをレポートに明記する(Phase 1〜16と同じ扱い)

---

## File Structure

```
glow-ma/src/
  schema.js          — 既存修正: STAFF_HEADERSの末尾に「メールアドレス」を追加(Task 1)
  adminAccess.js      — 新規: 許可リスト照合・企業一覧の絞り込み/並び替え/最小フィールド抽出・
                         対応履歴の並び替え・アクセス拒否画面(GlowAdminAccess)(Task 2, 3)
  adminApp.js         — 新規: 管理画面のHTML/JS文字列組み立て(GlowAdminApp)(Task 6)
  AdminRunner.gs      — 新規: 許可リスト読取・認証チェック・企業一覧/詳細/フィルタ選択肢の
                         サーバー関数(GAS専用)(Task 4, 5)
  TrackingWebApp.gs   — 既存修正: doGetに管理画面ルーティングを追加(Task 7)
tests/
  glow_ma_schema.test.mjs       — 既存修正(Task 1)
  glow_ma_adminAccess.test.mjs  — 新規(Task 2, 3)
  glow_ma_adminApp.test.mjs     — 新規(Task 6)
docs/glow-ma_本番投入手順書_統合版.md — Phase 18aのデプロイ手順を追記(Task 8)
glow-ma/README.md               — Phase 18aのセットアップ・使い方を追記(Task 8)
```

---

### Task 1: `schema.js` — スタッフタブに「メールアドレス」列を追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Modify: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `GlowSchema.STAFF_HEADERS`が`["氏名", "Slack User ID", "有効", "メールアドレス"]`になる(末尾に追加)。Task 4(`AdminRunner.gs`の許可リスト読取)が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_schema.test.mjs`の末尾(ファイル最後の`});`の直後)に追記する:

```js
test("スタッフタブに管理画面Web App用のメールアドレス列が末尾に追加されている(Phase 18a)", () => {
  assert.ok(schema.STAFF_HEADERS.indexOf("メールアドレス") !== -1);
  assert.deepEqual(
    schema.STAFF_HEADERS.slice(-1),
    ["メールアドレス"]
  );
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: FAIL(`STAFF_HEADERS`にまだ`"メールアドレス"`が無いため)

- [ ] **Step 3: `glow-ma/src/schema.js`の`STAFF_HEADERS`を修正**

```js
  var STAFF_HEADERS = ["氏名", "Slack User ID", "有効", "メールアドレス"];
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: PASS(既存テスト全件 + 新規1テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): スタッフタブに管理画面Web App用のメールアドレス列を追加"
```

---

### Task 2: `adminAccess.js` — 許可リスト照合・アクセス拒否画面

**Files:**
- Create: `glow-ma/src/adminAccess.js`
- Test: `tests/glow_ma_adminAccess.test.mjs`

**Interfaces:**
- Consumes: なし(純粋ロジック)
- Produces: `GlowAdminAccess.isAllowedEmail(email, staffRows)`: boolean(`staffRows`は`{email: string}`の配列。大文字小文字・前後空白を無視して一致判定する)、`GlowAdminAccess.buildAccessDeniedHtml()`: string(アクセス拒否画面のHTML)。Task 4(`AdminRunner.gs`)が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_adminAccess.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const adminAccess = require("../glow-ma/src/adminAccess.js");

test("isAllowedEmail: スタッフ一覧にメールアドレスが一致すればtrue", () => {
  const staffRows = [{ email: "koyanagi@example.com" }, { email: "fukuda@example.com" }];
  assert.equal(adminAccess.isAllowedEmail("koyanagi@example.com", staffRows), true);
});

test("isAllowedEmail: 一致しなければfalse", () => {
  const staffRows = [{ email: "koyanagi@example.com" }];
  assert.equal(adminAccess.isAllowedEmail("other@example.com", staffRows), false);
});

test("isAllowedEmail: 大文字小文字・前後空白の違いを無視して一致判定する", () => {
  const staffRows = [{ email: " Koyanagi@Example.com " }];
  assert.equal(adminAccess.isAllowedEmail("koyanagi@example.com", staffRows), true);
});

test("isAllowedEmail: 空文字・未認証はfalse(空リストでも許可されない)", () => {
  assert.equal(adminAccess.isAllowedEmail("", [{ email: "koyanagi@example.com" }]), false);
  assert.equal(adminAccess.isAllowedEmail(null, [{ email: "koyanagi@example.com" }]), false);
});

test("isAllowedEmail: スタッフ一覧が空なら常にfalse", () => {
  assert.equal(adminAccess.isAllowedEmail("koyanagi@example.com", []), false);
});

test("buildAccessDeniedHtml: アクセス権がない旨のHTMLを返す", () => {
  const html = adminAccess.buildAccessDeniedHtml();
  assert.ok(html.indexOf("アクセス権がありません") !== -1);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: FAIL(`../glow-ma/src/adminAccess.js`が存在しないためモジュール読み込みエラー)

- [ ] **Step 3: `glow-ma/src/adminAccess.js`を新規作成**

```js
/* GLOW企業リレーション台帳 管理画面Web Appの許可リスト照合・企業一覧の絞り込みロジック
 * ブラウザ相当のGAS(global.GlowAdminAccess)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_adminAccess.test.mjs で検証される。
 *
 * 個人Gmail運用(Workspaceドメインなし)のため、Web Appのアクセス設定だけでは
 * 利用者を限定できない。AdminRunner.gs が Session.getActiveUser().getEmail() で
 * 取得した実際のアクセス者のメールアドレスを、ここで「スタッフ」タブの登録
 * メールアドレスと照合する(三名体制レビュー2026-08-09裁定1・2)。
 */
(function (global) {
  "use strict";

  function normalizeEmail_(email) {
    return String(email || "").trim().toLowerCase();
  }

  function isAllowedEmail(email, staffRows) {
    var target = normalizeEmail_(email);
    if (!target) return false;
    return (staffRows || []).some(function (staff) {
      return normalizeEmail_(staff.email) === target;
    });
  }

  function buildAccessDeniedHtml() {
    return "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">" +
      "<style>body{font-family:-apple-system,BlinkMacSystemFont,\"Hiragino Sans\"," +
      "\"Noto Sans JP\",Meiryo,sans-serif;padding:3rem 2rem;text-align:center;color:#11202c}" +
      "h1{font-size:1.15rem;margin:0 0 0.75rem}p{color:#4a5a66;line-height:1.7}</style></head>" +
      "<body><h1>アクセス権がありません</h1>" +
      "<p>このページを利用できるのは許可されたスタッフのみです。<br>" +
      "心当たりがある場合は管理者に確認してください。</p></body></html>";
  }

  var api = {
    isAllowedEmail: isAllowedEmail,
    buildAccessDeniedHtml: buildAccessDeniedHtml
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowAdminAccess = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: PASS(6テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/adminAccess.js tests/glow_ma_adminAccess.test.mjs
git commit -m "feat(glow-ma): 管理画面Web Appの許可リスト照合ロジックを追加"
```

---

### Task 3: `adminAccess.js` — 企業一覧の絞り込み・並び替え・最小フィールド抽出

**Files:**
- Modify: `glow-ma/src/adminAccess.js`
- Modify: `tests/glow_ma_adminAccess.test.mjs`

**Interfaces:**
- Consumes: なし(純粋ロジック)
- Produces: `GlowAdminAccess.COMPANY_LIST_FIELDS`(配列、`["企業ID", "会社名", "ランク", "現在ステージ", "次回アクション予定日", "担当者"]`)、`GlowAdminAccess.DEFAULT_LIST_LIMIT`(number、100)、`GlowAdminAccess.hasAnyFilter(filters)`: boolean、`GlowAdminAccess.applyCompanyFilters(companies, filters)`: array、`GlowAdminAccess.buildCompanyListResult(companies, filters)`: array(絞り込み→(未絞り込み時のみ)次回アクション予定日降順で上位100件に制限→最小フィールド抽出、の順で適用した結果)、`GlowAdminAccess.sortInteractionsByDateDesc(records)`: array(対応履歴を日付降順に並び替える)。Task 5(`AdminRunner.gs`のサーバー関数)が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_adminAccess.test.mjs`の末尾に追記:

```js
const SAMPLE_COMPANIES = [
  { 企業ID: "C000001", 会社名: "テスト商事株式会社", ランク: "A", 現在ステージ: "提案中", 次回アクション予定日: "2026-08-20", 担当者: "たかし", 携帯番号: "090-0000-0001", 関係メモ: "極秘メモ1" },
  { 企業ID: "C000002", 会社名: "サンプル建設株式会社", ランク: "B", 現在ステージ: "未接触", 次回アクション予定日: "2026-08-10", 担当者: "嶺井さん", 携帯番号: "090-0000-0002", 関係メモ: "極秘メモ2" },
  { 企業ID: "C000003", 会社名: "デモ工業株式会社", ランク: "A", 現在ステージ: "成約", 次回アクション予定日: "", 担当者: "たかし", 携帯番号: "090-0000-0003", 関係メモ: "極秘メモ3" }
];

test("COMPANY_LIST_FIELDS: 一覧に必要な最小限のフィールドのみを定義する(機微情報を含まない)", () => {
  assert.deepEqual(adminAccess.COMPANY_LIST_FIELDS, [
    "企業ID", "会社名", "ランク", "現在ステージ", "次回アクション予定日", "担当者"
  ]);
});

test("hasAnyFilter: 検索語・ランク・ステージ・担当者のいずれかが指定されていればtrue", () => {
  assert.equal(adminAccess.hasAnyFilter({}), false);
  assert.equal(adminAccess.hasAnyFilter({ search: "" }), false);
  assert.equal(adminAccess.hasAnyFilter({ search: "テスト" }), true);
  assert.equal(adminAccess.hasAnyFilter({ rank: "A" }), true);
  assert.equal(adminAccess.hasAnyFilter({ stage: "未接触" }), true);
  assert.equal(adminAccess.hasAnyFilter({ owner: "たかし" }), true);
});

test("applyCompanyFilters: 会社名の部分一致で絞り込む", () => {
  const result = adminAccess.applyCompanyFilters(SAMPLE_COMPANIES, { search: "サンプル" });
  assert.deepEqual(result.map(c => c["企業ID"]), ["C000002"]);
});

test("applyCompanyFilters: ランク・ステージ・担当者の完全一致で絞り込む", () => {
  assert.deepEqual(
    adminAccess.applyCompanyFilters(SAMPLE_COMPANIES, { rank: "A" }).map(c => c["企業ID"]),
    ["C000001", "C000003"]
  );
  assert.deepEqual(
    adminAccess.applyCompanyFilters(SAMPLE_COMPANIES, { stage: "未接触" }).map(c => c["企業ID"]),
    ["C000002"]
  );
  assert.deepEqual(
    adminAccess.applyCompanyFilters(SAMPLE_COMPANIES, { owner: "たかし" }).map(c => c["企業ID"]),
    ["C000001", "C000003"]
  );
});

test("buildCompanyListResult: 絞り込み指定時は上位100件制限をかけず、最小フィールドのみ返す(機微情報を含まない)", () => {
  const result = adminAccess.buildCompanyListResult(SAMPLE_COMPANIES, { rank: "A" });
  assert.deepEqual(result, [
    { 企業ID: "C000001", 会社名: "テスト商事株式会社", ランク: "A", 現在ステージ: "提案中", 次回アクション予定日: "2026-08-20", 担当者: "たかし" },
    { 企業ID: "C000003", 会社名: "デモ工業株式会社", ランク: "A", 現在ステージ: "成約", 次回アクション予定日: "", 担当者: "たかし" }
  ]);
});

test("buildCompanyListResult: 未絞り込み時は次回アクション予定日の降順で上位DEFAULT_LIST_LIMIT件のみ返す", () => {
  const result = adminAccess.buildCompanyListResult(SAMPLE_COMPANIES, {});
  assert.deepEqual(result.map(c => c["企業ID"]), ["C000001", "C000002", "C000003"]);
  assert.ok(result.length <= adminAccess.DEFAULT_LIST_LIMIT);
});

test("sortInteractionsByDateDesc: 対応履歴を日付の新しい順に並び替える", () => {
  const records = [
    { 履歴ID: "H-1", 日付: "2026-08-01" },
    { 履歴ID: "H-2", 日付: "2026-08-10" },
    { 履歴ID: "H-3", 日付: "2026-08-05" }
  ];
  assert.deepEqual(
    adminAccess.sortInteractionsByDateDesc(records).map(r => r["履歴ID"]),
    ["H-2", "H-3", "H-1"]
  );
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: FAIL(`COMPANY_LIST_FIELDS`/`hasAnyFilter`/`applyCompanyFilters`/`buildCompanyListResult`/`sortInteractionsByDateDesc`が`undefined`)

- [ ] **Step 3: `glow-ma/src/adminAccess.js`に実装を追加**

`buildAccessDeniedHtml`関数の直後、`var api = {`の直前に追加する:

```js
  var COMPANY_LIST_FIELDS = ["企業ID", "会社名", "ランク", "現在ステージ", "次回アクション予定日", "担当者"];
  var DEFAULT_LIST_LIMIT = 100;

  function pickCompanyListFields_(company) {
    var picked = {};
    COMPANY_LIST_FIELDS.forEach(function (field) {
      picked[field] = company[field] !== undefined ? company[field] : "";
    });
    return picked;
  }

  function hasAnyFilter(filters) {
    var f = filters || {};
    return !!(String(f.search || "").trim() || f.rank || f.stage || f.owner);
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
      return true;
    });
  }

  function sortByNextActionDateDesc_(companies) {
    return companies.slice().sort(function (a, b) {
      var da = String(a["次回アクション予定日"] || "");
      var db = String(b["次回アクション予定日"] || "");
      if (da === db) return 0;
      return da < db ? 1 : -1;
    });
  }

  function buildCompanyListResult(companies, filters) {
    var filtered = applyCompanyFilters(companies, filters);
    var limited = hasAnyFilter(filters)
      ? filtered
      : sortByNextActionDateDesc_(filtered).slice(0, DEFAULT_LIST_LIMIT);
    return limited.map(pickCompanyListFields_);
  }

  function sortInteractionsByDateDesc(records) {
    return (records || []).slice().sort(function (a, b) {
      var da = String(a["日付"] || "");
      var db = String(b["日付"] || "");
      if (da === db) return 0;
      return da < db ? 1 : -1;
    });
  }
```

`api`オブジェクトに追加する(既存のプロパティはそのまま残し、以下を追記):

```js
    COMPANY_LIST_FIELDS: COMPANY_LIST_FIELDS,
    DEFAULT_LIST_LIMIT: DEFAULT_LIST_LIMIT,
    hasAnyFilter: hasAnyFilter,
    applyCompanyFilters: applyCompanyFilters,
    buildCompanyListResult: buildCompanyListResult,
    sortInteractionsByDateDesc: sortInteractionsByDateDesc
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_adminAccess.test.mjs`
Expected: PASS(既存6テスト + 新規9テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/adminAccess.js tests/glow_ma_adminAccess.test.mjs
git commit -m "feat(glow-ma): 管理画面Web Appの企業一覧絞り込み・並び替えロジックを追加"
```

---

### Task 4: `AdminRunner.gs` — 許可リスト読取・認証チェック(GAS専用・手動検証)

**Files:**
- Create: `glow-ma/src/AdminRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema.STAFF_SHEET_NAME`/`STAFF_HEADERS`(Task 1)、`GlowAdminAccess.isAllowedEmail`/`buildAccessDeniedHtml`(Task 2)
- Produces: `isAdminUser_()`: boolean、`requireAdminAccess_()`(許可されていなければ例外を投げる)、`renderAdminPage_()`: `HtmlOutput`(Task 7の`doGet`が呼ぶ契約)

- [ ] **Step 1: `glow-ma/src/AdminRunner.gs`を新規作成**

```js
/**
 * GLOW企業リレーション台帳: 管理画面Web App(Phase 18a: 企業一覧・詳細の閲覧)
 *
 * 既存の TrackingWebApp.gs の doGet に ?page=admin での分岐が追加されており、
 * この分岐先が本ファイルの renderAdminPage_ を呼ぶ。実処理はすべてこのファイルに
 * 委譲し、doGet 自体はルーティングのみを行う(三名体制レビュー2026-08-09裁定3)。
 *
 * セットアップ(人間が一度だけ行う):
 * 1. 「スタッフ」タブに、管理画面へのアクセスを許可する人の「氏名」「メールアドレス」を
 *    入力し、「有効」列にチェックを入れる(Slack User IDは対面連携機能専用で、
 *    本機能の利用には不要)
 * 2. `clasp push` で最新コードを反映する
 * 3. Apps Scriptエディタの「デプロイ」→「新しいデプロイ」→種類「ウェブアプリ」で、
 *    トラッキング用(Phase 4)とは別に新規デプロイを作成する。実行ユーザー: 自分。
 *    アクセスできるユーザー: 「Googleアカウントを持つ全員」
 * 4. デプロイ後に発行されるURLの末尾に `?page=admin` を付けたものを、
 *    「スタッフ」タブに登録した人へ共有する
 *
 * 認証は Session.getActiveUser().getEmail()(実際のアクセス者のメールアドレス)を
 * 「スタッフ」タブの登録メールアドレスと照合する方式。個人Gmail運用(Workspace
 * ドメインなし)のため、Web Appのアクセス設定(「Googleアカウントを持つ全員」)だけでは
 * 利用者を限定できず、この許可リスト照合が唯一の防御線になる。そのため
 * getCompanyList_・getCompanyDetail_ など公開される関数それぞれの冒頭でも
 * requireAdminAccess_ を呼ぶ(doGetでの一度きりのチェックに依存しない多層防御。
 * 三名体制レビュー2026-08-09裁定1・2)。
 */
function isAdminUser_() {
  var email = Session.getActiveUser().getEmail();
  var staffRows = readStaffAllowlistEmails_();
  return GlowAdminAccess.isAllowedEmail(email, staffRows);
}

function requireAdminAccess_() {
  if (!isAdminUser_()) {
    throw new Error("この操作を行う権限がありません。");
  }
}

function readStaffAllowlistEmails_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(GlowSchema.STAFF_SHEET_NAME);
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.STAFF_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var emailIndex = headers.indexOf("メールアドレス");
  var activeIndex = headers.indexOf("有効");
  return values
    .filter(function (row) { return row[activeIndex] === true && row[emailIndex]; })
    .map(function (row) { return { email: row[emailIndex] }; });
}

function renderAdminPage_() {
  if (!isAdminUser_()) {
    return HtmlService.createHtmlOutput(GlowAdminAccess.buildAccessDeniedHtml());
  }
  return HtmlService.createHtmlOutput(GlowAdminApp.buildAdminAppHtml())
    .setTitle("GLOW企業リレーション台帳");
}
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/AdminRunner.gs /tmp/AdminRunner_check.js && node --check /tmp/AdminRunner_check.js && rm /tmp/AdminRunner_check.js` で構文チェック
2. `GlowSchema.STAFF_HEADERS`(Task 1で`["氏名", "Slack User ID", "有効", "メールアドレス"]`)と、`readStaffAllowlistEmails_`が参照する`"メールアドレス"`/`"有効"`のインデックス取得が一致していることを確認する
3. `GlowAdminAccess.isAllowedEmail`(Task 2)のシグネチャ(`email, staffRows`、`staffRows`は`{email}`の配列)と、`isAdminUser_`が渡す`readStaffAllowlistEmails_()`の戻り値の形が一致していることを確認する
4. `renderAdminPage_`が、認可されていない場合に`GlowAdminApp.buildAdminAppHtml()`(Task 6でまだ存在しないため、この時点では参照エラーになる。Task 6完了後に解消される想定であることをメモしておく)を呼ばないことを確認する

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Google Apps Script実行環境が必要なため、この環境では実行できない。Task 5・6・7完了後にまとめて検証する(最終レビューのStep参照)。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/AdminRunner.gs
git commit -m "feat(glow-ma): 管理画面Web Appの許可リスト認証を追加"
```

---

### Task 5: `AdminRunner.gs` — 企業一覧・詳細・フィルタ選択肢の取得(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/AdminRunner.gs`

**Interfaces:**
- Consumes: `requireAdminAccess_()`(Task 4)、`readCompanyRecords_`(`glow-ma/src/ImportRunner.gs`。**再定義しないこと**)、`readInteractionsByCompanyId_`(`glow-ma/src/ScoringRunner.gs`。**再定義しないこと**)、`GlowAdminAccess.buildCompanyListResult`/`sortInteractionsByDateDesc`(Task 3)、`GlowSchema.COMPANY_MASTER_SHEET_NAME`/`COMPANY_MASTER_HEADERS`/`INTERACTION_LOG_SHEET_NAME`(既存)
- Produces: `getCompanyList_(filters)`: array(Task 6の画面が`google.script.run`で呼ぶ契約)、`getCompanyDetail_(companyId)`: `{company, history}` または `null`(同上)、`getFilterOptions_()`: `{stages: string[], owners: string[]}`(同上)

- [ ] **Step 1: `glow-ma/src/AdminRunner.gs`の末尾に追記**

```js
/**
 * 企業一覧(絞り込み・並び替え済み、最小フィールドのみ)を返す。
 * google.script.run 経由で adminApp.js の画面から呼ばれる。
 */
function getCompanyList_(filters) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  return GlowAdminAccess.buildCompanyListResult(companies, filters || {});
}

/**
 * 企業1社分の全項目(機微情報を含む)と、対応履歴ログ(日付降順)を返す。
 * 該当企業が見つからない場合はnullを返す。
 */
function getCompanyDetail_(companyId) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  var company = companies.filter(function (c) { return c["企業ID"] === companyId; })[0];
  if (!company) return null;

  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  var interactionsByCompany = logSheet ? readInteractionsByCompanyId_(logSheet) : {};
  var history = GlowAdminAccess.sortInteractionsByDateDesc(interactionsByCompany[companyId] || []);

  return { company: company, history: history };
}

/**
 * 一覧画面の「現在ステージ」「担当者」フィルタの選択肢を、企業マスタに実在する
 * 値から重複なく作る(ランクはA/B/C/Dで固定のため画面側にハードコードする)。
 */
function getFilterOptions_() {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];

  var stageSet = {};
  var ownerSet = {};
  companies.forEach(function (company) {
    if (company["現在ステージ"]) stageSet[company["現在ステージ"]] = true;
    if (company["担当者"]) ownerSet[company["担当者"]] = true;
  });

  return {
    stages: Object.keys(stageSet).sort(),
    owners: Object.keys(ownerSet).sort()
  };
}
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/AdminRunner.gs /tmp/AdminRunner_check.js && node --check /tmp/AdminRunner_check.js && rm /tmp/AdminRunner_check.js` で構文チェック
2. `getCompanyList_`・`getCompanyDetail_`・`getFilterOptions_`の3関数すべてが、冒頭で`requireAdminAccess_()`を呼んでいることを確認する(多層防御。三名体制レビュー裁定2)
3. `getCompanyDetail_`が返す`company`オブジェクトに携帯番号・関係メモ・所在地が**含まれる**こと(詳細取得では機微情報を返す設計)、一方`getCompanyList_`が`GlowAdminAccess.buildCompanyListResult`(Task 3で機微情報を除外する実装)を経由していることを、両関数を読み比べて確認する
4. `readCompanyRecords_`(`ImportRunner.gs`)・`readInteractionsByCompanyId_`(`ScoringRunner.gs`)を再定義せずrequireしていることを確認する(GASではグローバル関数として自動的に参照できるため、Node側と異なりimport文は不要。この2関数が実際に存在することを`grep -n "^function readCompanyRecords_\|^function readInteractionsByCompanyId_" glow-ma/src/*.gs`で再確認する)

- [ ] **Step 3: 手動検証(このサンドボックス環境では実行できない)**

Task 7完了後にまとめて検証する(最終レビューのStep参照)。

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/AdminRunner.gs
git commit -m "feat(glow-ma): 管理画面Web Appの企業一覧・詳細・フィルタ選択肢の取得を追加"
```

---

### Task 6: `adminApp.js` — 管理画面のHTML/JS組み立て

**Files:**
- Create: `glow-ma/src/adminApp.js`
- Test: `tests/glow_ma_adminApp.test.mjs`

**Interfaces:**
- Consumes: `getCompanyList_`/`getCompanyDetail_`/`getFilterOptions_`(Task 5。画面内の`google.script.run`呼び出し先として名前が一致している必要がある)
- Produces: `GlowAdminApp.buildAdminAppHtml()`: string(画面全体のHTML)。Task 4の`renderAdminPage_`が参照する契約

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_adminApp.test.mjs`:

```js
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const adminApp = require("../glow-ma/src/adminApp.js");

test("buildAdminAppHtml: 検索・絞り込み・一覧テーブル・詳細ドロワーの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["searchInput", "filterRank", "filterStage", "filterOwner", "companyTableBody", "drawer", "paneOverview", "paneHistory"]
    .forEach((id) => {
      assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
    });
});

test("buildAdminAppHtml: ランクの選択肢はA/B/C/Dの4つ(固定)", () => {
  const html = adminApp.buildAdminAppHtml();
  ["A", "B", "C", "D"].forEach((rank) => {
    assert.ok(html.indexOf('<option value="' + rank + '">') !== -1, "ランク" + rank + "の選択肢がない");
  });
});

test("buildAdminAppHtml: google.script.runでgetCompanyList_・getCompanyDetail_・getFilterOptions_を呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getCompanyList_(") !== -1);
  assert.ok(html.indexOf(".getCompanyDetail_(") !== -1);
  assert.ok(html.indexOf(".getFilterOptions_(") !== -1);
});

test("buildAdminAppHtml: 書き込み系のgoogle.script.run呼び出しを一切含まない(読み取り専用の担保)", () => {
  const html = adminApp.buildAdminAppHtml();
  ["shareCompanyWithStaff", "saveRelationMemo", "appendInteractionLog"].forEach((forbidden) => {
    assert.equal(html.indexOf(forbidden), -1, forbidden + " への呼び出しが含まれてはいけない(Phase 18b以降の機能)");
  });
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: FAIL(`../glow-ma/src/adminApp.js`が存在しないためモジュール読み込みエラー)

- [ ] **Step 3: `glow-ma/src/adminApp.js`を新規作成**

```js
/* GLOW企業リレーション台帳 管理画面Web AppのHTML/JS組み立て(Phase 18a: 企業一覧・詳細の閲覧)
 * ブラウザ相当のGAS(global.GlowAdminApp)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_adminApp.test.mjs で構造面のみ検証される
 * (google.script.run の実際の往復はGAS実行環境が必要なためNodeでは検証できない)。
 *
 * AdminRunner.gs の renderAdminPage_ がこの関数の戻り値を HtmlService.createHtmlOutput
 * に渡してWeb Appのページとして表示する。読み取り専用(Phase 18a)のため、
 * データを変更する google.script.run 呼び出しは一切含まない。
 */
(function (global) {
  "use strict";

  var STYLE = [
    "*{box-sizing:border-box}",
    "body{margin:0;font-family:-apple-system,BlinkMacSystemFont,\"Hiragino Sans\",",
    "\"Noto Sans JP\",Meiryo,sans-serif;color:#11202c;background:#f3f4f0}",
    "header{background:#00335c;color:#fff;padding:0.9rem 1.25rem}",
    "header h1{margin:0;font-size:1.05rem;font-weight:600}",
    ".filters{display:flex;gap:0.6rem;flex-wrap:wrap;padding:0.9rem 1.25rem;background:#fff;",
    "border-bottom:1px solid #d8dee1}",
    ".filters input,.filters select{padding:0.4rem 0.6rem;border:1px solid #d8dee1;",
    "border-radius:0.35rem;font:inherit}",
    "table{width:100%;border-collapse:collapse;background:#fff}",
    "th,td{text-align:left;padding:0.55rem 1rem;border-bottom:1px solid #e5e9eb;font-size:0.88rem}",
    "th{color:#4a5a66;font-weight:600;background:#f7f8f6}",
    "tbody tr{cursor:pointer}",
    "tbody tr:hover{background:#fdf2e2}",
    ".rank{display:inline-block;min-width:1.4rem;text-align:center;border-radius:0.3rem;",
    "padding:0.05rem 0.4rem;font-weight:700;color:#fff;background:#f88800}",
    "#drawer{position:fixed;top:0;right:0;bottom:0;width:min(420px,100%);background:#fff;",
    "box-shadow:-4px 0 16px rgba(17,32,44,0.18);transform:translateX(100%);",
    "transition:transform 0.2s ease;display:flex;flex-direction:column}",
    "#drawer.open{transform:translateX(0)}",
    "#drawerHeader{padding:1rem 1.25rem;border-bottom:1px solid #e5e9eb;display:flex;",
    "justify-content:space-between;align-items:flex-start}",
    "#drawerClose{border:0;background:none;font-size:1.1rem;cursor:pointer;color:#4a5a66}",
    ".tabs{display:flex;border-bottom:1px solid #e5e9eb}",
    ".tabs button{flex:1;padding:0.6rem;border:0;background:none;cursor:pointer;font:inherit;",
    "color:#4a5a66;border-bottom:2px solid transparent}",
    ".tabs button.active{color:#00335c;border-bottom-color:#f88800;font-weight:600}",
    "#drawerBody{overflow-y:auto;padding:1rem 1.25rem;flex:1}",
    ".field{margin-bottom:0.7rem}",
    ".field .label{font-size:0.76rem;color:#7a828a;text-transform:uppercase;letter-spacing:0.03em}",
    ".field .value{font-size:0.92rem;white-space:pre-wrap}",
    ".empty{color:#7a828a;padding:1.5rem;text-align:center}",
    "#overlay{position:fixed;inset:0;background:rgba(17,32,44,0.25);display:none}",
    "#overlay.open{display:block}"
  ].join("");

  var HEADER_AND_FILTERS = [
    "<header><h1>GLOW企業リレーション台帳</h1></header>",
    "<div class=\"filters\">",
    "<input type=\"text\" id=\"searchInput\" placeholder=\"会社名・代表者名で検索\">",
    "<select id=\"filterRank\"><option value=\"\">ランク(すべて)</option>",
    "<option value=\"A\">A</option><option value=\"B\">B</option>",
    "<option value=\"C\">C</option><option value=\"D\">D</option></select>",
    "<select id=\"filterStage\"><option value=\"\">現在ステージ(すべて)</option></select>",
    "<select id=\"filterOwner\"><option value=\"\">担当者(すべて)</option></select>",
    "</div>"
  ].join("");

  var TABLE = [
    "<table><thead><tr><th>会社名</th><th>ランク</th><th>現在ステージ</th>",
    "<th>次回アクション予定日</th><th>担当者</th></tr></thead>",
    "<tbody id=\"companyTableBody\"></tbody></table>",
    "<div class=\"empty\" id=\"emptyState\" style=\"display:none\">該当する企業が見つかりません</div>"
  ].join("");

  var DRAWER = [
    "<div id=\"overlay\"></div>",
    "<div id=\"drawer\">",
    "<div id=\"drawerHeader\"><div><div id=\"drawerCompanyName\" style=\"font-weight:700\"></div>",
    "<div id=\"drawerCompanyId\" style=\"font-size:0.8rem;color:#7a828a\"></div></div>",
    "<button id=\"drawerClose\">&times;</button></div>",
    "<div class=\"tabs\"><button id=\"tabOverviewBtn\" class=\"active\">概要</button>",
    "<button id=\"tabHistoryBtn\">対応履歴</button></div>",
    "<div id=\"drawerBody\">",
    "<div id=\"paneOverview\"></div>",
    "<div id=\"paneHistory\" style=\"display:none\"></div>",
    "</div></div>"
  ].join("");

  var SCRIPT = [
    "var currentFilters = { search: '', rank: '', stage: '', owner: '' };",
    "function escapeHtml(value){return String(value===undefined||value===null?'':value)",
    ".replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}",

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
    "}).withFailureHandler(function(){}).getFilterOptions_();",
    "}",

    "function loadList(){",
    "google.script.run.withSuccessHandler(renderTable).withFailureHandler(function(error){",
    "document.getElementById('companyTableBody').innerHTML = '';",
    "var empty = document.getElementById('emptyState');",
    "empty.style.display = 'block'; empty.textContent = '読み込みに失敗しました。再読み込みしてください。';",
    "}).getCompanyList_(currentFilters);",
    "}",

    "function renderTable(rows){",
    "var tbody = document.getElementById('companyTableBody'); tbody.innerHTML = '';",
    "var empty = document.getElementById('emptyState');",
    "if (!rows || rows.length === 0){ empty.style.display = 'block';",
    "empty.textContent = '該当する企業が見つかりません'; return; }",
    "empty.style.display = 'none';",
    "rows.forEach(function(row){",
    "var tr = document.createElement('tr');",
    "tr.innerHTML = '<td>' + escapeHtml(row['会社名']) + '</td>' +",
    "'<td><span class=\"rank\">' + escapeHtml(row['ランク']) + '</span></td>' +",
    "'<td>' + escapeHtml(row['現在ステージ']) + '</td>' +",
    "'<td>' + escapeHtml(row['次回アクション予定日']) + '</td>' +",
    "'<td>' + escapeHtml(row['担当者']) + '</td>';",
    "tr.addEventListener('click', function(){ openDrawer(row['企業ID']); });",
    "tbody.appendChild(tr);});",
    "}",

    "function openDrawer(companyId){",
    "document.getElementById('drawer').classList.add('open');",
    "document.getElementById('overlay').classList.add('open');",
    "document.getElementById('drawerCompanyName').textContent = '読み込み中…';",
    "document.getElementById('drawerCompanyId').textContent = companyId;",
    "google.script.run.withSuccessHandler(renderDrawer).withFailureHandler(function(){",
    "document.getElementById('drawerCompanyName').textContent = '読み込みに失敗しました。再読み込みしてください。';",
    "}).getCompanyDetail_(companyId);",
    "}",

    "function renderDrawer(detail){",
    "if (!detail){ document.getElementById('drawerCompanyName').textContent = '該当する企業が見つかりません';",
    "document.getElementById('paneOverview').innerHTML = ''; document.getElementById('paneHistory').innerHTML = ''; return; }",
    "var c = detail.company;",
    "document.getElementById('drawerCompanyName').textContent = c['会社名'] || '(社名未登録)';",
    "document.getElementById('drawerCompanyId').textContent = c['企業ID'];",
    "var fields = [",
    "['業種', c['業種']], ['代表者名', c['代表者名']], ['所在地', c['所在地']],",
    "['電話番号', c['電話番号']], ['窓口担当者名', c['窓口担当者名']], ['携帯番号', c['携帯番号']],",
    "['ランク', c['ランク']], ['総合スコア', c['総合スコア']], ['現在ステージ', c['現在ステージ']],",
    "['後継者状況', c['後継者状況']], ['関係メモ', c['関係メモ']]",
    "];",
    "document.getElementById('paneOverview').innerHTML = fields.map(function(f){",
    "return '<div class=\"field\"><div class=\"label\">' + escapeHtml(f[0]) + '</div>' +",
    "'<div class=\"value\">' + (escapeHtml(f[1]) || '—') + '</div></div>';",
    "}).join('');",
    "var history = detail.history || [];",
    "document.getElementById('paneHistory').innerHTML = history.length === 0",
    "? '<div class=\"empty\">対応履歴がありません</div>'",
    ": history.map(function(h){",
    "return '<div class=\"field\"><div class=\"label\">' + escapeHtml(h['日付']) + '・' + escapeHtml(h['種別']) + '</div>' +",
    "'<div class=\"value\">' + escapeHtml(h['内容メモ']) + '</div></div>';",
    "}).join('');",
    "}",

    "function closeDrawer(){",
    "document.getElementById('drawer').classList.remove('open');",
    "document.getElementById('overlay').classList.remove('open');",
    "}",

    "function switchTab(target){",
    "var isOverview = target === 'overview';",
    "document.getElementById('tabOverviewBtn').classList.toggle('active', isOverview);",
    "document.getElementById('tabHistoryBtn').classList.toggle('active', !isOverview);",
    "document.getElementById('paneOverview').style.display = isOverview ? 'block' : 'none';",
    "document.getElementById('paneHistory').style.display = isOverview ? 'none' : 'block';",
    "}",

    "document.getElementById('searchInput').addEventListener('input', function(e){",
    "currentFilters.search = e.target.value; loadList(); });",
    "document.getElementById('filterRank').addEventListener('change', function(e){",
    "currentFilters.rank = e.target.value; loadList(); });",
    "document.getElementById('filterStage').addEventListener('change', function(e){",
    "currentFilters.stage = e.target.value; loadList(); });",
    "document.getElementById('filterOwner').addEventListener('change', function(e){",
    "currentFilters.owner = e.target.value; loadList(); });",
    "document.getElementById('drawerClose').addEventListener('click', closeDrawer);",
    "document.getElementById('overlay').addEventListener('click', closeDrawer);",
    "document.getElementById('tabOverviewBtn').addEventListener('click', function(){ switchTab('overview'); });",
    "document.getElementById('tabHistoryBtn').addEventListener('click', function(){ switchTab('history'); });",

    "loadFilterOptions();",
    "loadList();"
  ].join("");

  function buildAdminAppHtml() {
    return "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">" +
      "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" +
      "<style>" + STYLE + "</style></head><body>" +
      HEADER_AND_FILTERS + TABLE + DRAWER +
      "<script>" + SCRIPT + "<\/script>" +
      "</body></html>";
  }

  var api = {
    buildAdminAppHtml: buildAdminAppHtml
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowAdminApp = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_adminApp.test.mjs`
Expected: PASS(4テスト)

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/adminApp.js tests/glow_ma_adminApp.test.mjs
git commit -m "feat(glow-ma): 管理画面Web Appの企業一覧・詳細ドロワー画面を追加"
```

---

### Task 7: `TrackingWebApp.gs` — `doGet`に管理画面ルーティングを追加(GAS専用・手動検証)

**Files:**
- Modify: `glow-ma/src/TrackingWebApp.gs`

**Interfaces:**
- Consumes: `renderAdminPage_`(Task 4)
- Produces: `doGet(e)`が`e.parameter.page === "admin"`のとき`renderAdminPage_()`を返す(既存のトラッキング処理は変更しない)

- [ ] **Step 1: `glow-ma/src/TrackingWebApp.gs`の`doGet`を修正**

既存の`doGet(e)`(32〜42行目)を以下に置き換える(**冒頭に管理画面への分岐を追加するのみで、既存のトラッキング処理の行は一切変更しない**):

```js
function doGet(e) {
  var page = e && e.parameter && e.parameter.page;
  if (page === "admin") {
    return renderAdminPage_();
  }

  var companyId = e && e.parameter && e.parameter.id;
  if (companyId && /^C\d{6}$/.test(companyId)) {
    logTrackingAccess_(companyId);
  }
  var redirectUrl = PropertiesService.getScriptProperties().getProperty("TRACKING_REDIRECT_URL");
  if (!redirectUrl) {
    return HtmlService.createHtmlOutput(GlowTrackingPage.buildNotFoundHtml());
  }
  return HtmlService.createHtmlOutput(GlowTrackingPage.buildRedirectHtml(redirectUrl));
}
```

このファイル冒頭のコメント(1〜31行目)に、以下を追記する(既存のコメントはそのまま残し、末尾に追加):

```
 *
 * 管理画面Web App(Phase 18a、AdminRunner.gs)への分岐もこの doGet が担うが、
 * この関数自体はルーティングのみで、実処理は renderAdminPage_(AdminRunner.gs)に
 * 完全に委譲する(三名体制レビュー2026-08-09裁定3。doGet を将来も薄いルーターの
 * ままに保つ)。
 */
```

- [ ] **Step 2: 静的チェック + 手書きトレース**

1. `cp glow-ma/src/TrackingWebApp.gs /tmp/TrackingWebApp_check.js && node --check /tmp/TrackingWebApp_check.js && rm /tmp/TrackingWebApp_check.js` で構文チェック
2. 既存のトラッキング処理(`companyId`の正規表現チェック・`logTrackingAccess_`呼び出し・リダイレクト処理)の行が、修正前と一字一句変わっていないことを`git diff glow-ma/src/TrackingWebApp.gs`で確認する(意図しない副作用を防ぐ)
3. `page=admin`のとき、`companyId`関連の処理に一切到達せず`renderAdminPage_()`の戻り値をそのまま返して関数が終了する(`return`で抜けている)ことを確認する

- [ ] **Step 3: Commit**

```bash
git add glow-ma/src/TrackingWebApp.gs
git commit -m "feat(glow-ma): doGetに管理画面Web Appへのルーティングを追加"
```

---

### Task 8: 本番投入手順書・READMEにPhase 18aを追記

**Files:**
- Modify: `docs/glow-ma_本番投入手順書_統合版.md`
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: Task 1〜7の全成果物

- [ ] **Step 1: `docs/glow-ma_本番投入手順書_統合版.md`の「## Phase 16 動作確認チェックリスト」セクションの直後に新セクションを追加**

```markdown
## Phase 18a セットアップ・動作確認チェックリスト(管理画面Web App・企業一覧/詳細の閲覧)

**セットアップ**

- [ ] 「スタッフ」タブに、管理画面へのアクセスを許可する人(小柳・福田・嶺井)の
      「氏名」「メールアドレス」を入力し、「有効」列にチェックを入れる
      (`ensureLedgerTabs`を再実行済みで「メールアドレス」列が追加されていること)
- [ ] `clasp push` で最新コードを反映する
- [ ] Apps Scriptエディタの「デプロイ」→「新しいデプロイ」→種類「ウェブアプリ」で、
      トラッキング用(Phase 4)とは別に新規デプロイを作成する。実行ユーザー: 自分。
      アクセスできるユーザー: 「Googleアカウントを持つ全員」
- [ ] 発行されたURLの末尾に `?page=admin` を付けたものを、許可対象者へ共有する

**動作確認**

- [ ] 「スタッフ」タブに登録済みのGoogleアカウントで管理画面URLにアクセスし、
      企業一覧が表示されることを確認する
- [ ] 「スタッフ」タブに登録**していない**Googleアカウントで同じURLにアクセスし、
      「アクセス権がありません」という案内が表示され、企業一覧が表示されないことを確認する
      (`Session.getActiveUser().getEmail()`が意図通り取得できていることの実機確認。
      三名体制レビュー2026-08-09裁定1)
- [ ] 検索・ランク・現在ステージ・担当者の絞り込みがそれぞれ機能することを確認する
- [ ] 何も絞り込まない状態で一覧を開き、表示件数が100件以下であることを確認する
- [ ] 企業の行をクリックし、詳細ドロワーに概要(携帯番号・関係メモを含む)と
      対応履歴が表示されることを確認する
- [ ] 詳細ドロワーの表示・編集ボタンが存在しないこと(読み取り専用であること)を確認する

**現時点の制約:**
- Web管理画面での個人情報相当データ(携帯番号・関係メモ・所在地)閲覧範囲の拡大について、
  委託契約や社内規程上の扱いを守り部に確認することが未完了(本機能の実装はブロックしていないが、
  実運用開始前に確認すること。三名体制レビュー2026-08-09裁定5)
- 書き込み系(関係メモ編集・対応履歴ログ入力)・スタッフ共有・KPI集計はPhase 18b以降で対応
```

- [ ] **Step 2: `glow-ma/README.md`に新セクションを追加**

`glow-ma/README.md`の「## レター発送日の記録・発送業者連携用CSV出力(Phase 16)」セクションの直後、「## 次のフェーズ」の直前に追加する:

```markdown
## 管理画面Web App: 企業一覧・詳細の閲覧(Phase 18a)

既存の「GLOW企業リレーション台帳 管理画面デモ」(クライアントサイドのみのモック)を、
実際のスプレッドシートと接続した本物のWeb管理画面にする最初の段階。企業一覧の検索・
絞り込みと、企業詳細(概要・対応履歴)の閲覧ができる(読み取り専用)。CLAUDE.mdの
三名体制ルールに基づき、glow-ma-triangle-reviewで議事を確定してから実装した
(`docs/superpowers/specs/2026-08-09-glow-ma-admin-webapp-phase18a-design.md`。
見直し期限: 2026-11-09)。

書き込み系(関係メモ編集・対応履歴ログ入力)・スタッフ共有(Slack DM)・手紙URL
モーダル・KPIカードは、それぞれPhase 18b・18c・18dとして別途実装する(区切り・順序は
暫定案)。

**セットアップ・動作確認**

`docs/glow-ma_本番投入手順書_統合版.md`の「Phase 18a セットアップ・動作確認
チェックリスト」を参照。

**安全設計(glow-ma-triangle-review確定事項)**

- 認証は`Session.getActiveUser().getEmail()`を「スタッフ」タブの登録メールアドレスと
  照合する方式(個人Gmail運用のためドメイン制限は使えない)
- 許可リストチェックは`doGet`だけでなく、公開される各サーバー関数の冒頭でも
  個別に行う(多層防御)
- 一覧取得が返すフィールドは企業ID・会社名・ランク・現在ステージ・次回アクション予定日・
  担当者のみ。携帯番号・関係メモ・所在地などの機微情報は詳細取得でのみ返す

**現時点の制約:**
- Web管理画面での個人情報相当データ閲覧範囲の拡大について、守り部への確認が未完了
  (実運用開始前に確認すること)
```

- [ ] **Step 3: 「## 次のフェーズ」セクションを更新**

`glow-ma/README.md`の「## 次のフェーズ」セクションを以下に置き換える:

```markdown
## 次のフェーズ

Phase 1〜16、およびPhase 18a(管理画面Web App: 企業一覧・詳細の閲覧)が完了しました。
書き込み系(関係メモ編集・対応履歴ログ入力)・スタッフ共有(Slack DM)・手紙URL
モーダル・KPIカードは、それぞれPhase 18b・18c・18dとして計画中(区切り・順序は暫定案。
`docs/superpowers/specs/2026-08-09-glow-ma-admin-webapp-phase18a-design.md`参照)。
今後の改善点は各セクションの「現時点の制約」、および「本番投入前チェックリスト」を参照。
```

- [ ] **Step 4: Commit**

```bash
git add docs/glow-ma_本番投入手順書_統合版.md glow-ma/README.md
git commit -m "docs(glow-ma): Phase 18aのセットアップ・使い方を追記"
```

---

### 最終レビュー

- [ ] **Step 1: 全テストを実行**

Run: `node --test tests/glow_ma_*.test.mjs`
Expected: PASS(全ファイル、既存テスト+Task 1・2・3・6で追加したテストすべて)

- [ ] **Step 2: 三名体制レビューの裁定事項が実装に反映されていることを確認**

`docs/superpowers/specs/2026-08-09-glow-ma-admin-webapp-phase18a-design.md`8章の
6条件それぞれについて、対応するファイルを読んで再確認する:
1. `AdminRunner.gs`が`Session.getActiveUser()`を使い、`Session.getEffectiveUser()`を
   使っていないこと(`grep -n "getEffectiveUser\|getActiveUser" glow-ma/src/AdminRunner.gs`)
2. `getCompanyList_`・`getCompanyDetail_`・`getFilterOptions_`のすべてが冒頭で
   `requireAdminAccess_()`を呼んでいること
3. `TrackingWebApp.gs`の`doGet`が`renderAdminPage_()`を呼ぶだけで、管理画面の実処理を
   直接書いていないこと
4. `adminAccess.js`の`COMPANY_LIST_FIELDS`に携帯番号・関係メモ・所在地が含まれず、
   `getCompanyDetail_`側にのみそれらが含まれること
5. `docs/glow-ma_本番投入手順書_統合版.md`に守り部への申し送り項目が追加されていること
6. `glow-ma/README.md`のPhase 18a節がPhase 18b以降を「暫定案」と明記していること

- [ ] **Step 3: GAS専用ファイルの静的チェックを再実行**

```bash
cp glow-ma/src/AdminRunner.gs /tmp/AdminRunner_check.js && node --check /tmp/AdminRunner_check.js && rm /tmp/AdminRunner_check.js
cp glow-ma/src/TrackingWebApp.gs /tmp/TrackingWebApp_check.js && node --check /tmp/TrackingWebApp_check.js && rm /tmp/TrackingWebApp_check.js
```

Expected: どちらも構文エラーなし

- [ ] **Step 4: `doGet`の一意性を確認**

`grep -rn "^function doGet" glow-ma/src/*.gs` を実行し、`doGet`が`TrackingWebApp.gs`の
1箇所にのみ定義されていることを確認する(GASは同名関数が複数ファイルにあると後勝ちで
上書きされ、意図しない実行結果になるため)。

- [ ] **Step 5: 未実施の手動検証をレポートにまとめる**

Task 4・5・7の手動検証(このサンドボックス環境では実行できない)と、
`docs/glow-ma_本番投入手順書_統合版.md`の「Phase 18a セットアップ・動作確認
チェックリスト」の内容をまとめ、Google Apps Script実行環境で人間が確認すべき手順として
レポートに明記する。

- [ ] **Step 6: 最終Commit(必要な場合のみ)**

レビューで修正が発生した場合のみ、修正内容をコミットする。修正がなければこのステップは
スキップする。
