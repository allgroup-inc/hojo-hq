# ノビシロ セルフサーブ診断商品(Plan 2)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `site/nobishiro/` に診断フォーム→決済(Stripe Checkout)→AIレポート生成(Claude API)→メール配信、というセルフサーブ診断商品を実装する。バックエンドはGAS(Google Apps Script)+ Google Sheetsで構築する。

**Architecture:** フロントは静的HTML(`site/nobishiro/shindan/`)。バックエンドはGAS Web App(`gas/nobishiro-shindan/`)1本で、`doPost`のクエリパラメータ`type`によって「フォーム送信受付」と「Stripe webhook受付」を振り分ける。GAS固有API(UrlFetchApp/MailApp/SpreadsheetApp/PropertiesService)に依存するグルーコード(`Code.gs`)と、依存しない純粋ロジック(`Logic.gs`)を分離し、後者はNode側で直接テストする(フクギイロの`shindan/logic.js`と同じUMDパターン)。

**Tech Stack:** GAS(V8ランタイム)、Stripe API(REST、SDKなしで`UrlFetchApp`から直接呼ぶ)、Claude API(Messages API)、Google Sheets、Node.js組み込みテストランナー(`node --test`)。

## 重要な設計上の決定: Stripe Webhookの検証方式

**GASの`doPost(e)`は、リクエストのHTTPヘッダーを一切公開しない。** これはGoogle Apps Script Web Appの既知の制約であり、Stripeが送る`Stripe-Signature`ヘッダーを読み取る手段がない。そのため、一般的なStripe連携で使われる「HMAC署名検証」はGAS上では実装できない。

代わりに、**Stripeの Webhook登録URLにクエリパラメータで長いランダムトークンを埋め込み**、`e.parameter.token`で照合する方式を採る(例: `https://script.google.com/macros/s/XXX/exec?type=webhook&token=<32文字以上のランダム文字列>`)。Stripeは登録したURLをクエリ文字列も含めてそのまま毎回POSTするため、この方式が成立する。HMAC署名検証より厳密さは劣るが、トークンが十分に長く非公開である限り実用上安全であり、GASという基盤を選んだ以上の妥当なトレードオフとして設計書に明記する。

## Global Constraints

- 価格: ¥14,800固定(design spec準拠、Stripeは日本円=0桁通貨のため`unit_amount`はそのまま`14800`)
- ブランド名: ノビシロ(仮称)。人物名は「カチカクくん」(経営伴走者)、AIエージェント人格は「ガジュマルくん」(診断商品の人格)
- レポート形式: HTMLメールのみ(PDF生成は行わない)
- 禁止表現(既存の`scripts/check_lp_nobishiro.py`が検査): `業界最安`, `絶対`, `100%削減`, `必ず成功`, `誰でも儲かる`, `確実に安くなる`, `保証します`
- 新規ページは相対パスで内部リンクを書く(絶対パス`/nobishiro/...`は使わない — Plan 1の最終レビューで判明した既知の欠陥のため)
- 新規ページには`<meta name="robots" content="noindex">`を入れる(ブランド未確定のため、既存6ページと同じ扱い)
- Stripe/Claude/GASの秘密情報(APIキー・Webhookトークン・SheetID)は`PropertiesService.getScriptProperties()`から読む。コード中にハードコードしない
- 決済が絡む処理(`handleStripeWebhook`)は、レポート生成が失敗してもSheetsの行を`決済済み・未送信`のまま残し、人手フォローできるようにする(自動リトライはv1では実装しない)

---

## File Structure

```
site/nobishiro/shindan/
  index.html                    # 診断フォームUI
  logic.js                      # フォームバリデーション+GAS呼び出し(UMD、Node側テスト可能)
  complete/index.html           # 決済完了の着地ページ

gas/nobishiro-shindan/
  Logic.gs                      # 純粋ロジック(バリデーション・価格・プロンプト生成・メールHTML・トークン照合)
  Code.gs                       # GASグルーコード(doPost・Stripe/Claude API呼び出し・Sheets・MailApp)

tests/
  nobishiro-shindan-logic.test.mjs     # site/nobishiro/shindan/logic.js のテスト
  nobishiro-shindan-backend.test.mjs   # gas/nobishiro-shindan/Logic.gs のテスト

.github/workflows/
  nobishiro-ci.yml              # (修正)Nodeテストの実行ステップを追加

site/nobishiro/index.html       # (修正)「近日公開」バッジを外し、診断ページへリンク
```

`gas/nobishiro-shindan/Logic.gs`は、フクギイロの`site/fukugiiro/shindan/logic.js`と同じUMD形式(`typeof module !== "undefined" && module.exports`分岐)で書く。GAS(V8ランタイム)では`module`がundefinedになるため`globalThis`に`NBBackendLogic`として登録され、同一GASプロジェクト内の`Code.gs`から関数名でそのまま呼び出せる。Node側では`require()`でそのままテストできる。

---

### Task 1: バックエンド純粋ロジック — 入力バリデーション+価格

**Files:**
- Create: `gas/nobishiro-shindan/Logic.gs`
- Test: `tests/nobishiro-shindan-backend.test.mjs`

**Interfaces:**
- Consumes: なし
- Produces: `NBBackendLogic.validateSubmission(answers)` → `{valid: boolean, errors: string[]}`。`NBBackendLogic.PRICE_YEN`(定数、`14800`)。`NBBackendLogic.VALID_INDUSTRIES`等の許容値配列(Task 6のフロント側バリデーションと値を一致させる)

- [ ] **Step 1: 失敗するテストを書く**

```javascript
// tests/nobishiro-shindan-backend.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import backend from "../gas/nobishiro-shindan/Logic.gs";

const validAnswers = {
  email: "owner@example.com",
  industry: "飲食業",
  employeeCount: "6〜20人",
  monthlyRevenue: "300〜1000万円",
  costFeeling: "やや負担",
  salesChallenge: "追客",
  priority: "コスト削減",
};

test("validateSubmission: 正しい回答はvalid:true", () => {
  const result = backend.validateSubmission(validAnswers);
  assert.equal(result.valid, true);
  assert.deepEqual(result.errors, []);
});

test("validateSubmission: メール不正はエラー", () => {
  const result = backend.validateSubmission({ ...validAnswers, email: "not-an-email" });
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("メール")));
});

test("validateSubmission: 業種が許容値外はエラー", () => {
  const result = backend.validateSubmission({ ...validAnswers, industry: "宇宙業" });
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.includes("業種")));
});

test("validateSubmission: answersがnullなら単一エラーで即返す", () => {
  const result = backend.validateSubmission(null);
  assert.equal(result.valid, false);
  assert.equal(result.errors.length, 1);
});

test("PRICE_YEN は14800", () => {
  assert.equal(backend.PRICE_YEN, 14800);
});
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `node --test tests/nobishiro-shindan-backend.test.mjs`
Expected: `gas/nobishiro-shindan/Logic.gs` が存在しないため `ERR_MODULE_NOT_FOUND` で失敗

- [ ] **Step 3: `gas/nobishiro-shindan/Logic.gs` を作成**

```javascript
/* ノビシロ 診断商品バックエンド 純粋ロジック(ケンショウ/守り部ゲート対象)
 * GAS固有API(UrlFetchApp/MailApp/SpreadsheetApp/PropertiesService)には一切依存しない。
 * ブラウザ(window)/GAS(globalThis)/Node(module.exports)のいずれでも動くUMD形式。
 * Node側は tests/nobishiro-shindan-backend.test.mjs で検証される(CI必須)。
 */
(function (global) {
  "use strict";

  var PRICE_YEN = 14800;

  var VALID_INDUSTRIES = ["建設業", "飲食業", "小売業", "サービス業", "製造業", "その他"];
  var VALID_EMPLOYEE_COUNTS = ["1〜5人", "6〜20人", "21〜50人", "51人以上"];
  var VALID_REVENUE_RANGES = ["〜300万円", "300〜1000万円", "1000〜3000万円", "3000万円以上"];
  var VALID_COST_FEELINGS = ["かなり負担", "やや負担", "あまり気にならない"];
  var VALID_SALES_CHALLENGES = ["リード獲得", "追客", "提案書作成", "その他"];
  var VALID_PRIORITIES = ["コスト削減", "営業効率"];

  function validateSubmission(answers) {
    if (!answers || typeof answers !== "object") {
      return { valid: false, errors: ["回答データがありません"] };
    }
    var errors = [];
    if (!answers.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(answers.email)) {
      errors.push("メールアドレスを正しく入力してください");
    }
    if (VALID_INDUSTRIES.indexOf(answers.industry) === -1) errors.push("業種を選択してください");
    if (VALID_EMPLOYEE_COUNTS.indexOf(answers.employeeCount) === -1) errors.push("従業員数を選択してください");
    if (VALID_REVENUE_RANGES.indexOf(answers.monthlyRevenue) === -1) errors.push("月商規模を選択してください");
    if (VALID_COST_FEELINGS.indexOf(answers.costFeeling) === -1) errors.push("管理コストの実感を選択してください");
    if (VALID_SALES_CHALLENGES.indexOf(answers.salesChallenge) === -1) errors.push("営業効率の課題を選択してください");
    if (VALID_PRIORITIES.indexOf(answers.priority) === -1) errors.push("最優先課題を選択してください");
    return { valid: errors.length === 0, errors: errors };
  }

  var api = {
    PRICE_YEN: PRICE_YEN,
    VALID_INDUSTRIES: VALID_INDUSTRIES,
    VALID_EMPLOYEE_COUNTS: VALID_EMPLOYEE_COUNTS,
    VALID_REVENUE_RANGES: VALID_REVENUE_RANGES,
    VALID_COST_FEELINGS: VALID_COST_FEELINGS,
    VALID_SALES_CHALLENGES: VALID_SALES_CHALLENGES,
    VALID_PRIORITIES: VALID_PRIORITIES,
    validateSubmission: validateSubmission,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.NBBackendLogic = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `node --test tests/nobishiro-shindan-backend.test.mjs`
Expected: 5 tests, 全てPASS

- [ ] **Step 5: コミット**

```bash
git add gas/nobishiro-shindan/Logic.gs tests/nobishiro-shindan-backend.test.mjs
git commit -m "feat(nobishiro-shindan): 診断バックエンドの入力バリデーション+価格定数を追加"
```

---

### Task 2: バックエンド純粋ロジック — Claudeプロンプト生成+メールHTML組み立て

**Files:**
- Modify: `gas/nobishiro-shindan/Logic.gs`(Task 1で作成したファイルに追記)
- Test: `tests/nobishiro-shindan-backend.test.mjs`(追記)

**Interfaces:**
- Consumes: なし
- Produces: `NBBackendLogic.buildReportPrompt(answers)` → string。`NBBackendLogic.escapeHtml(text)` → string。`NBBackendLogic.buildReportEmailHtml(reportText, answers)` → string(HTML)。Task 5(`Code.gs`のwebhook処理)がこの3関数を呼び出す

- [ ] **Step 1: 失敗するテストを追記**

```javascript
// tests/nobishiro-shindan-backend.test.mjs に追記

test("buildReportPrompt: 回答内容が全てプロンプトに含まれる", () => {
  const prompt = backend.buildReportPrompt(validAnswers);
  assert.ok(prompt.includes("飲食業"));
  assert.ok(prompt.includes("6〜20人"));
  assert.ok(prompt.includes("ガジュマルくん"));
});

test("escapeHtml: HTML特殊文字をエスケープする", () => {
  const result = backend.escapeHtml('<script>alert("x")</script>&');
  assert.equal(result, "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;&amp;");
});

test("buildReportEmailHtml: レポート本文がエスケープされ改行がbrになる", () => {
  const html = backend.buildReportEmailHtml("1行目\n2行目<b>太字</b>", validAnswers);
  assert.ok(html.includes("1行目<br>2行目&lt;b&gt;太字&lt;/b&gt;"));
  assert.ok(html.includes("ガジュマルくん"));
});
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `node --test tests/nobishiro-shindan-backend.test.mjs`
Expected: 新規3件が `backend.buildReportPrompt is not a function` 等でFAIL、既存5件はPASS

- [ ] **Step 3: `gas/nobishiro-shindan/Logic.gs` に追記**

`api = {...}` の直前に以下を追加し、`api`オブジェクトに3つのキーを追加する:

```javascript
  function buildReportPrompt(answers) {
    return [
      "あなたは「ガジュマルくん」という、沖縄の中小企業のバックオフィス業務をAIで自動化・改善提案するアシスタントです。",
      "以下の企業の回答をもとに、やさしい言葉で、断定的な表現を避けた診断レポートを作成してください。",
      "",
      "# 回答内容",
      "業種: " + answers.industry,
      "従業員数: " + answers.employeeCount,
      "月商規模: " + answers.monthlyRevenue,
      "管理コストの実感: " + answers.costFeeling,
      "営業効率の課題: " + answers.salesChallenge,
      "最優先課題: " + answers.priority,
      "",
      "# レポートの構成(この順番で、見出し記号なしの日本語プレーンテキストで)",
      "1. 現状分析(2〜3文、回答内容の要約と課題の言語化)",
      "2. コスト構造の推定(一般的な傾向として、断定を避けた表現で。金額を断定しない)",
      "3. おすすめプラン(ライト/スタンダード/プロのいずれかを、理由とともに1つ提案)",
      "4. 次の一歩(無料相談への誘導を1文)",
      "",
      "文字数は600〜800字程度。専門用語は使わず、経営者にやさしく語りかけるトーンで。",
    ].join("\n");
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function buildReportEmailHtml(reportText, answers) {
    var body = escapeHtml(reportText).replace(/\n/g, "<br>");
    return [
      '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px;color:#1F2A2E;">',
      '<h1 style="color:#2F6B4F;font-size:1.3rem;">ガジュマルくんからの診断レポート</h1>',
      "<p>お待たせしました。あなたの会社向けのAI活用診断レポートです。</p>",
      '<div style="background:#FAF7F0;border:1px solid #E4DCC9;border-radius:12px;padding:20px;">',
      body,
      "</div>",
      '<p style="margin-top:24px;">より詳しいご相談は<a href="https://allgroup-inc.github.io/hojo-hq/nobishiro/contact/">無料相談予約ページ</a>からどうぞ。</p>',
      '<p style="font-size:.85rem;color:#5C6B70;">本レポートはAIが自動生成したものであり、内容の詳細は改めてご相談の上ご確認ください。</p>',
      "</div>",
    ].join("");
  }
```

`api`オブジェクトに追加:
```javascript
    buildReportPrompt: buildReportPrompt,
    escapeHtml: escapeHtml,
    buildReportEmailHtml: buildReportEmailHtml,
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `node --test tests/nobishiro-shindan-backend.test.mjs`
Expected: 8 tests, 全てPASS

- [ ] **Step 5: コミット**

```bash
git add gas/nobishiro-shindan/Logic.gs tests/nobishiro-shindan-backend.test.mjs
git commit -m "feat(nobishiro-shindan): Claudeプロンプト生成とメールHTML組み立てを追加"
```

---

### Task 3: バックエンド純粋ロジック — Webhookトークン照合

**Files:**
- Modify: `gas/nobishiro-shindan/Logic.gs`
- Test: `tests/nobishiro-shindan-backend.test.mjs`(追記)

**Interfaces:**
- Consumes: なし
- Produces: `NBBackendLogic.isValidWebhookToken(providedToken, expectedToken)` → boolean。Task 5の`Code.gs`がStripe webhookリクエストの認証に使う

- [ ] **Step 1: 失敗するテストを追記**

```javascript
// tests/nobishiro-shindan-backend.test.mjs に追記

test("isValidWebhookToken: 一致すればtrue", () => {
  assert.equal(backend.isValidWebhookToken("abc123", "abc123"), true);
});

test("isValidWebhookToken: 不一致はfalse", () => {
  assert.equal(backend.isValidWebhookToken("abc123", "xyz999"), false);
});

test("isValidWebhookToken: expectedが空文字ならfalse(未設定のトークンでの誤通過防止)", () => {
  assert.equal(backend.isValidWebhookToken("", ""), false);
  assert.equal(backend.isValidWebhookToken(undefined, ""), false);
});

test("isValidWebhookToken: 型が文字列でなければfalse", () => {
  assert.equal(backend.isValidWebhookToken(null, "abc123"), false);
  assert.equal(backend.isValidWebhookToken(123, "abc123"), false);
});
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `node --test tests/nobishiro-shindan-backend.test.mjs`
Expected: 新規4件が `backend.isValidWebhookToken is not a function` でFAIL、既存8件はPASS

- [ ] **Step 3: `gas/nobishiro-shindan/Logic.gs` に追記**

```javascript
  function isValidWebhookToken(providedToken, expectedToken) {
    return (
      typeof providedToken === "string" &&
      typeof expectedToken === "string" &&
      expectedToken.length > 0 &&
      providedToken === expectedToken
    );
  }
```

`api`オブジェクトに追加:
```javascript
    isValidWebhookToken: isValidWebhookToken,
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `node --test tests/nobishiro-shindan-backend.test.mjs`
Expected: 12 tests, 全てPASS

- [ ] **Step 5: コミット**

```bash
git add gas/nobishiro-shindan/Logic.gs tests/nobishiro-shindan-backend.test.mjs
git commit -m "feat(nobishiro-shindan): Webhookトークン照合ロジックを追加"
```

---

### Task 4: GASグルーコード — doPostルーター+フォーム送信受付

**Files:**
- Create: `gas/nobishiro-shindan/Code.gs`

**Interfaces:**
- Consumes: `NBBackendLogic.validateSubmission`, `NBBackendLogic.PRICE_YEN`(Task 1)
- Produces: `doPost(e)`, `handleSubmit(e)`, `createStripeCheckoutSession(diagnosisId, email)`, `getLeadSheet()`, `jsonResponse(obj)`。Task 5がこのファイルに`handleStripeWebhook`等を追記する

このファイルはGAS固有API(`UrlFetchApp`/`SpreadsheetApp`/`PropertiesService`/`Utilities`)に依存するため、Node環境では実行できない。Node側のテストはなし。作成後は`node --check`で構文のみ検証する。

- [ ] **Step 1: `gas/nobishiro-shindan/Code.gs` を作成**

```javascript
/* ノビシロ 診断商品バックエンド GASグルーコード
 * GAS固有API(UrlFetchApp/SpreadsheetApp/PropertiesService/MailApp/Utilities)に依存する。
 * Node環境では実行できないため、ユニットテストはない(node --checkで構文のみ検証)。
 * 純粋ロジックは Logic.gs(NBBackendLogic)を参照。
 *
 * デプロイ後のWeb App URLは2つの用途で使う(クエリパラメータtypeで振り分け):
 *   ?type=submit  … このサイトのフロントからのフォーム送信
 *   ?type=webhook&token=<秘密トークン> … StripeのWebhook登録先
 * GASのdoPost(e)はHTTPヘッダーを公開しないため、Stripeの署名検証(Stripe-Signature
 * ヘッダー)は実装できない。代わりにWebhook登録URLに埋め込んだ秘密トークンで認証する。
 */

var COLUMN = {
  diagnosisId: 1,
  timestamp: 2,
  answersJson: 3,
  email: 4,
  paymentStatus: 5,
  stripeSessionId: 6,
  reportStatus: 7,
  sentAt: 8,
};

function doPost(e) {
  var type = e.parameter.type;
  if (type === "submit") {
    return handleSubmit(e);
  }
  if (type === "webhook") {
    return handleStripeWebhook(e);
  }
  return jsonResponse({ error: "unknown_type" });
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function getLeadSheet() {
  var sheetId = PropertiesService.getScriptProperties().getProperty("SHEET_ID");
  return SpreadsheetApp.openById(sheetId).getSheetByName("リード台帳");
}

function handleSubmit(e) {
  var body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonResponse({ error: "invalid_json" });
  }

  var validation = NBBackendLogic.validateSubmission(body.answers);
  if (!validation.valid) {
    return jsonResponse({ error: "validation_failed", details: validation.errors });
  }

  var diagnosisId = Utilities.getUuid();
  var sheet = getLeadSheet();
  sheet.appendRow([
    diagnosisId,
    new Date().toISOString(),
    JSON.stringify(body.answers),
    body.answers.email,
    "pending",
    "",
    "not_sent",
    "",
  ]);

  var session = createStripeCheckoutSession(diagnosisId, body.answers.email);
  if (!session || !session.url) {
    return jsonResponse({ error: "stripe_session_failed" });
  }
  return jsonResponse({ url: session.url });
}

function createStripeCheckoutSession(diagnosisId, email) {
  var props = PropertiesService.getScriptProperties();
  var secretKey = props.getProperty("STRIPE_SECRET_KEY");
  var baseUrl = props.getProperty("SITE_BASE_URL");

  var payload = {
    "payment_method_types[0]": "card",
    "line_items[0][price_data][currency]": "jpy",
    "line_items[0][price_data][product_data][name]": "ノビシロ AI活用診断レポート",
    "line_items[0][price_data][unit_amount]": String(NBBackendLogic.PRICE_YEN),
    "line_items[0][quantity]": "1",
    mode: "payment",
    success_url: baseUrl + "/shindan/complete/?session_id={CHECKOUT_SESSION_ID}",
    cancel_url: baseUrl + "/shindan/",
    client_reference_id: diagnosisId,
    customer_email: email,
  };

  var response = UrlFetchApp.fetch("https://api.stripe.com/v1/checkout/sessions", {
    method: "post",
    headers: { Authorization: "Bearer " + secretKey },
    payload: payload,
    muteHttpExceptions: true,
  });
  return JSON.parse(response.getContentText());
}
```

- [ ] **Step 2: 構文チェック**

Run: `node --check gas/nobishiro-shindan/Code.gs`
Expected: エラーなし、終了コード0(`UrlFetchApp`等のGAS専用グローバルは未定義エラーにならず、構文だけがチェックされる)

- [ ] **Step 3: コミット**

```bash
git add gas/nobishiro-shindan/Code.gs
git commit -m "feat(nobishiro-shindan): doPostルーターとフォーム送信受付(Stripe Checkout作成)を追加"
```

---

### Task 5: GASグルーコード — Stripe Webhook受付+レポート生成+メール送信

**Files:**
- Modify: `gas/nobishiro-shindan/Code.gs`(Task 4のファイルに追記)

**Interfaces:**
- Consumes: `NBBackendLogic.isValidWebhookToken`(Task 3)、`NBBackendLogic.buildReportPrompt`・`NBBackendLogic.buildReportEmailHtml`(Task 2)、`COLUMN`・`jsonResponse`・`getLeadSheet`(Task 4)
- Produces: `handleStripeWebhook(e)`, `findRowByDiagnosisId(diagnosisId)`, `updateRowField(rowIndex, column, value)`, `generateReport(answers)`

- [ ] **Step 1: `gas/nobishiro-shindan/Code.gs` の末尾に追記**

```javascript

function handleStripeWebhook(e) {
  var expectedToken = PropertiesService.getScriptProperties().getProperty("WEBHOOK_TOKEN");
  if (!NBBackendLogic.isValidWebhookToken(e.parameter.token, expectedToken)) {
    return jsonResponse({ error: "invalid_token" });
  }

  var stripeEvent;
  try {
    stripeEvent = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonResponse({ error: "invalid_json" });
  }

  if (stripeEvent.type !== "checkout.session.completed") {
    return jsonResponse({ ok: true, ignored: true });
  }

  var session = stripeEvent.data.object;
  var diagnosisId = session.client_reference_id;
  var row = findRowByDiagnosisId(diagnosisId);
  if (!row) {
    return jsonResponse({ error: "diagnosis_not_found" });
  }

  updateRowField(row.rowIndex, COLUMN.paymentStatus, "paid");
  updateRowField(row.rowIndex, COLUMN.stripeSessionId, session.id);

  try {
    var answers = JSON.parse(row.values[COLUMN.answersJson - 1]);
    var reportText = generateReport(answers);
    var html = NBBackendLogic.buildReportEmailHtml(reportText, answers);
    MailApp.sendEmail({
      to: row.values[COLUMN.email - 1],
      subject: "【ノビシロ】AI活用診断レポートが届きました",
      htmlBody: html,
    });
    updateRowField(row.rowIndex, COLUMN.reportStatus, "sent");
    updateRowField(row.rowIndex, COLUMN.sentAt, new Date().toISOString());
  } catch (err) {
    // 決済は完了しているので行は残す。カチカクくんが日次で "paid_pending_report" 相当を確認し手動フォローする
    updateRowField(row.rowIndex, COLUMN.reportStatus, "failed: " + err.message);
  }

  return jsonResponse({ ok: true });
}

function findRowByDiagnosisId(diagnosisId) {
  var sheet = getLeadSheet();
  var values = sheet.getDataRange().getValues();
  for (var i = 0; i < values.length; i++) {
    if (values[i][COLUMN.diagnosisId - 1] === diagnosisId) {
      return { rowIndex: i + 1, values: values[i] };
    }
  }
  return null;
}

function updateRowField(rowIndex, column, value) {
  getLeadSheet().getRange(rowIndex, column).setValue(value);
}

function generateReport(answers) {
  var apiKey = PropertiesService.getScriptProperties().getProperty("ANTHROPIC_API_KEY");
  var prompt = NBBackendLogic.buildReportPrompt(answers);
  var response = UrlFetchApp.fetch("https://api.anthropic.com/v1/messages", {
    method: "post",
    contentType: "application/json",
    headers: { "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
    payload: JSON.stringify({
      model: "claude-sonnet-5",
      max_tokens: 2048,
      messages: [{ role: "user", content: prompt }],
    }),
    muteHttpExceptions: true,
  });
  var data = JSON.parse(response.getContentText());
  return data.content[0].text;
}
```

- [ ] **Step 2: 構文チェック**

Run: `node --check gas/nobishiro-shindan/Code.gs`
Expected: エラーなし、終了コード0

- [ ] **Step 3: コミット**

```bash
git add gas/nobishiro-shindan/Code.gs
git commit -m "feat(nobishiro-shindan): Stripe Webhook受付・レポート生成・メール送信を追加"
```

---

### Task 6: フロントエンド純粋ロジック — フォームバリデーション+送信

**Files:**
- Create: `site/nobishiro/shindan/logic.js`
- Test: `tests/nobishiro-shindan-logic.test.mjs`

**Interfaces:**
- Consumes: なし(fetch実装は呼び出し側から注入される)
- Produces: `NBShindan.validateForm(answers)` → `{valid, errors}`(Task 1の`validateSubmission`と同じ許容値・同じエラーメッセージ文言)。`NBShindan.submitDiagnosis(answers, endpointUrl, fetchFn)` → `Promise<string>`(成功時はStripe Checkout URL、失敗時はreject)。Task 7の`shindan/index.html`がこれを呼ぶ

- [ ] **Step 1: 失敗するテストを書く**

```javascript
// tests/nobishiro-shindan-logic.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import shindan from "../site/nobishiro/shindan/logic.js";

const validAnswers = {
  email: "owner@example.com",
  industry: "飲食業",
  employeeCount: "6〜20人",
  monthlyRevenue: "300〜1000万円",
  costFeeling: "やや負担",
  salesChallenge: "追客",
  priority: "コスト削減",
};

test("validateForm: 正しい回答はvalid:true", () => {
  const result = shindan.validateForm(validAnswers);
  assert.equal(result.valid, true);
});

test("validateForm: メール未入力はエラー", () => {
  const result = shindan.validateForm({ ...validAnswers, email: "" });
  assert.equal(result.valid, false);
});

test("submitDiagnosis: バリデーション失敗ならfetchを呼ばずreject", async () => {
  let called = false;
  const fakeFetch = async () => {
    called = true;
    return { json: async () => ({}) };
  };
  await assert.rejects(
    shindan.submitDiagnosis({ ...validAnswers, email: "" }, "https://example.com/exec", fakeFetch)
  );
  assert.equal(called, false);
});

test("submitDiagnosis: 成功時はCheckout URLを返す", async () => {
  const fakeFetch = async (url, opts) => {
    assert.ok(url.includes("?type=submit"));
    assert.equal(opts.method, "POST");
    const body = JSON.parse(opts.body);
    assert.deepEqual(body.answers, validAnswers);
    return { json: async () => ({ url: "https://checkout.stripe.com/xyz" }) };
  };
  const url = await shindan.submitDiagnosis(validAnswers, "https://example.com/exec", fakeFetch);
  assert.equal(url, "https://checkout.stripe.com/xyz");
});

test("submitDiagnosis: サーバーがerrorを返したらreject", async () => {
  const fakeFetch = async () => ({ json: async () => ({ error: "validation_failed" }) });
  await assert.rejects(shindan.submitDiagnosis(validAnswers, "https://example.com/exec", fakeFetch));
});
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `node --test tests/nobishiro-shindan-logic.test.mjs`
Expected: `site/nobishiro/shindan/logic.js` が存在しないため `ERR_MODULE_NOT_FOUND` で失敗

- [ ] **Step 3: `site/nobishiro/shindan/logic.js` を作成**

```javascript
/* ノビシロ 診断フォーム ロジック(ケンショウ対象)
 * ブラウザ(window)/Node(module.exports)の両方で動くUMD形式。
 * Node側は tests/nobishiro-shindan-logic.test.mjs で検証される(CI必須)。
 * バリデーション許容値は gas/nobishiro-shindan/Logic.gs (NBBackendLogic)側と一致させる
 * (デプロイ先が別々のためコード自体は複製だが、値の一致はテストで担保する)。
 */
(function (global) {
  "use strict";

  var VALID_INDUSTRIES = ["建設業", "飲食業", "小売業", "サービス業", "製造業", "その他"];
  var VALID_EMPLOYEE_COUNTS = ["1〜5人", "6〜20人", "21〜50人", "51人以上"];
  var VALID_REVENUE_RANGES = ["〜300万円", "300〜1000万円", "1000〜3000万円", "3000万円以上"];
  var VALID_COST_FEELINGS = ["かなり負担", "やや負担", "あまり気にならない"];
  var VALID_SALES_CHALLENGES = ["リード獲得", "追客", "提案書作成", "その他"];
  var VALID_PRIORITIES = ["コスト削減", "営業効率"];

  function validateForm(answers) {
    if (!answers || typeof answers !== "object") {
      return { valid: false, errors: ["回答データがありません"] };
    }
    var errors = [];
    if (!answers.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(answers.email)) {
      errors.push("メールアドレスを正しく入力してください");
    }
    if (VALID_INDUSTRIES.indexOf(answers.industry) === -1) errors.push("業種を選択してください");
    if (VALID_EMPLOYEE_COUNTS.indexOf(answers.employeeCount) === -1) errors.push("従業員数を選択してください");
    if (VALID_REVENUE_RANGES.indexOf(answers.monthlyRevenue) === -1) errors.push("月商規模を選択してください");
    if (VALID_COST_FEELINGS.indexOf(answers.costFeeling) === -1) errors.push("管理コストの実感を選択してください");
    if (VALID_SALES_CHALLENGES.indexOf(answers.salesChallenge) === -1) errors.push("営業効率の課題を選択してください");
    if (VALID_PRIORITIES.indexOf(answers.priority) === -1) errors.push("最優先課題を選択してください");
    return { valid: errors.length === 0, errors: errors };
  }

  function submitDiagnosis(answers, endpointUrl, fetchFn) {
    var validation = validateForm(answers);
    if (!validation.valid) {
      return Promise.reject(new Error(validation.errors.join(" / ")));
    }
    // Content-Type: text/plain にするとブラウザのCORSプリフライト(OPTIONS)が発生せず、
    // GAS Web Appへの直接POSTが成功する(GAS側はcontent-typeに関わらずe.postData.contentsを読める)。
    return fetchFn(endpointUrl + "?type=submit", {
      method: "POST",
      headers: { "Content-Type": "text/plain" },
      body: JSON.stringify({ answers: answers }),
    })
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (data.error) {
          throw new Error(data.error);
        }
        return data.url;
      });
  }

  var api = {
    validateForm: validateForm,
    submitDiagnosis: submitDiagnosis,
    VALID_INDUSTRIES: VALID_INDUSTRIES,
    VALID_EMPLOYEE_COUNTS: VALID_EMPLOYEE_COUNTS,
    VALID_REVENUE_RANGES: VALID_REVENUE_RANGES,
    VALID_COST_FEELINGS: VALID_COST_FEELINGS,
    VALID_SALES_CHALLENGES: VALID_SALES_CHALLENGES,
    VALID_PRIORITIES: VALID_PRIORITIES,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.NBShindan = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストを実行して成功を確認**

Run: `node --test tests/nobishiro-shindan-logic.test.mjs`
Expected: 5 tests, 全てPASS

- [ ] **Step 5: コミット**

```bash
git add site/nobishiro/shindan/logic.js tests/nobishiro-shindan-logic.test.mjs
git commit -m "feat(nobishiro-shindan): 診断フォームのバリデーション+送信ロジックを追加"
```

---

### Task 7: 診断フォームページ

**Files:**
- Create: `site/nobishiro/shindan/index.html`

**Interfaces:**
- Consumes: `site/nobishiro/shindan/logic.js`(`NBShindan.submitDiagnosis`)、`../analytics-config.js`
- Produces: フォーム送信成功時に`window.location.href`をStripe Checkout URLへ遷移させる

GAS Web AppのURLはデプロイ後に発行されるため、この時点ではプレースホルダー`GAS_WEB_APP_URL_PLACEHOLDER`を使う(末尾の「デプロイ前の手動セットアップ手順」で実際のURLに差し替える)。

- [ ] **Step 1: `site/nobishiro/shindan/index.html` を作成**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>AI活用診断 | ノビシロ</title>
<meta name="description" content="6つの質問に答えるだけで、ガジュマルくんがあなたの会社向けのAI活用診断レポートを作成します(¥14,800)。">
<style>
:root{--nb-primary:#2F6B4F;--nb-accent:#D98E2B;--nb-ink:#1F2A2E;--nb-bg:#FAF7F0;
  --nb-card:#ffffff;--nb-muted:#5C6B70;--nb-line:#E4DCC9}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;
  font-size:18px;line-height:1.8;color:var(--nb-ink);background:var(--nb-bg)}
.wrap{max-width:640px;margin:0 auto;padding:0 20px}
h1{font-size:1.5rem;margin-bottom:.4em}
section{padding:36px 0}
.card{background:var(--nb-card);border:1px solid var(--nb-line);border-radius:12px;padding:22px}
label{display:block;font-weight:700;margin:16px 0 6px}
label:first-of-type{margin-top:0}
select,input[type="email"]{width:100%;padding:10px;border:1px solid var(--nb-line);border-radius:8px;font-size:1rem}
.btn{display:block;width:100%;padding:16px;background:var(--nb-primary);color:#fff;border:none;
  border-radius:999px;font-weight:700;font-size:1.05rem;margin-top:24px;cursor:pointer}
.btn:disabled{opacity:.6;cursor:default}
.error{color:#b3261e;font-size:.9rem;margin-top:12px;white-space:pre-line}
.note{font-size:.85rem;color:var(--nb-muted)}
.siteheader{position:sticky;top:0;background:rgba(250,247,240,.96);border-bottom:1px solid var(--nb-line);
  padding:10px 16px}
.siteheader a{margin-right:14px;font-size:.85rem;text-decoration:none;color:var(--nb-ink)}
.siteheader .hlogo{font-weight:800;color:var(--nb-primary)}
footer{background:var(--nb-ink);color:#e6e6e0;padding:28px 0;font-size:.85rem}
</style>
</head>
<body>
<header class="siteheader">
  <a class="hlogo" href="../">ノビシロ</a>
  <a href="../about/">代表者紹介</a>
  <a href="../pricing/">料金</a>
  <a href="../blog/">お役立ち情報</a>
  <a href="../contact/">無料相談</a>
</header>
<main>
<section>
  <div class="wrap">
    <h1>AI活用診断</h1>
    <p class="note">6つの質問に答えて決済(¥14,800)いただくと、ガジュマルくんがあなたの会社向けの診断レポートをメールでお届けします。</p>
    <div class="card">
      <form id="shindanForm">
        <label for="industry">業種</label>
        <select id="industry" required>
          <option value="">選択してください</option>
          <option>建設業</option><option>飲食業</option><option>小売業</option>
          <option>サービス業</option><option>製造業</option><option>その他</option>
        </select>

        <label for="employeeCount">従業員数</label>
        <select id="employeeCount" required>
          <option value="">選択してください</option>
          <option>1〜5人</option><option>6〜20人</option><option>21〜50人</option><option>51人以上</option>
        </select>

        <label for="monthlyRevenue">月商規模</label>
        <select id="monthlyRevenue" required>
          <option value="">選択してください</option>
          <option>〜300万円</option><option>300〜1000万円</option>
          <option>1000〜3000万円</option><option>3000万円以上</option>
        </select>

        <label for="costFeeling">管理コストの実感</label>
        <select id="costFeeling" required>
          <option value="">選択してください</option>
          <option>かなり負担</option><option>やや負担</option><option>あまり気にならない</option>
        </select>

        <label for="salesChallenge">営業効率の課題</label>
        <select id="salesChallenge" required>
          <option value="">選択してください</option>
          <option>リード獲得</option><option>追客</option><option>提案書作成</option><option>その他</option>
        </select>

        <label for="priority">最優先課題</label>
        <select id="priority" required>
          <option value="">選択してください</option>
          <option>コスト削減</option><option>営業効率</option>
        </select>

        <label for="email">メールアドレス(レポートの送付先)</label>
        <input type="email" id="email" required>

        <button type="submit" class="btn" id="submitBtn">¥14,800で診断を申し込む</button>
        <p class="error" id="errorMsg" role="alert"></p>
      </form>
    </div>
  </div>
</section>
</main>
<footer><div class="wrap">&copy; 2026 ノビシロ — ブランド名は検討中です。</div></footer>
<script src="../analytics-config.js"></script>
<script src="logic.js"></script>
<script>
(function () {
  var GAS_WEB_APP_URL = "GAS_WEB_APP_URL_PLACEHOLDER";
  var form = document.getElementById("shindanForm");
  var errorMsg = document.getElementById("errorMsg");
  var submitBtn = document.getElementById("submitBtn");

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    errorMsg.textContent = "";
    var answers = {
      industry: document.getElementById("industry").value,
      employeeCount: document.getElementById("employeeCount").value,
      monthlyRevenue: document.getElementById("monthlyRevenue").value,
      costFeeling: document.getElementById("costFeeling").value,
      salesChallenge: document.getElementById("salesChallenge").value,
      priority: document.getElementById("priority").value,
      email: document.getElementById("email").value,
    };
    submitBtn.disabled = true;
    submitBtn.textContent = "処理中…";
    window.NBShindan.submitDiagnosis(answers, GAS_WEB_APP_URL, window.fetch.bind(window))
      .then(function (checkoutUrl) {
        window.location.href = checkoutUrl;
      })
      .catch(function (err) {
        errorMsg.textContent = err.message;
        submitBtn.disabled = false;
        submitBtn.textContent = "¥14,800で診断を申し込む";
      });
  });
})();
</script>
</body>
</html>
```

- [ ] **Step 2: LP検査スクリプトを実行して合格することを確認**

Run: `python3 scripts/check_lp_nobishiro.py`
Expected: `サイト検査完了: 7ページ / エラー 0`

- [ ] **Step 3: コミット**

```bash
git add site/nobishiro/shindan/index.html
git commit -m "feat(nobishiro-shindan): 診断フォームページを追加"
```

---

### Task 8: 決済完了ページ

**Files:**
- Create: `site/nobishiro/shindan/complete/index.html`

**Interfaces:**
- Consumes: `../../analytics-config.js`
- Produces: なし(末端ページ)。実際のレポート生成・送信は裏側のStripe webhookが非同期に行うため、このページは「お届けします」の案内のみで完結する(フェイクの完了処理をしない)

- [ ] **Step 1: `site/nobishiro/shindan/complete/index.html` を作成**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>お申し込みありがとうございます | ノビシロ</title>
<meta name="description" content="AI活用診断のお申し込みありがとうございます。レポートはメールでお届けします。">
<style>
:root{--nb-primary:#2F6B4F;--nb-accent:#D98E2B;--nb-ink:#1F2A2E;--nb-bg:#FAF7F0;
  --nb-card:#ffffff;--nb-muted:#5C6B70;--nb-line:#E4DCC9}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;
  font-size:18px;line-height:1.8;color:var(--nb-ink);background:var(--nb-bg)}
.wrap{max-width:560px;margin:0 auto;padding:0 20px}
h1{font-size:1.4rem;margin-bottom:.6em}
section{padding:48px 0;text-align:center}
.card{background:var(--nb-card);border:1px solid var(--nb-line);border-radius:12px;padding:28px}
.btn{display:inline-block;margin-top:20px;padding:14px 24px;background:var(--nb-primary);color:#fff;
  text-decoration:none;border-radius:999px;font-weight:700}
.siteheader{position:sticky;top:0;background:rgba(250,247,240,.96);border-bottom:1px solid var(--nb-line);
  padding:10px 16px}
.siteheader a{margin-right:14px;font-size:.85rem;text-decoration:none;color:var(--nb-ink)}
.siteheader .hlogo{font-weight:800;color:var(--nb-primary)}
footer{background:var(--nb-ink);color:#e6e6e0;padding:28px 0;font-size:.85rem}
</style>
</head>
<body>
<header class="siteheader">
  <a class="hlogo" href="../../">ノビシロ</a>
  <a href="../../about/">代表者紹介</a>
  <a href="../../pricing/">料金</a>
  <a href="../../contact/">無料相談</a>
</header>
<main>
<section>
  <div class="wrap">
    <div class="card">
      <h1>お申し込みありがとうございます</h1>
      <p>決済が完了しました。ガジュマルくんが診断レポートを作成中です。準備でき次第、ご入力いただいたメールアドレスにお届けします(通常数分以内)。</p>
      <p style="margin-top:12px" class="note">メールが届かない場合は、迷惑メールフォルダをご確認いただくか、お問い合わせください。</p>
      <a class="btn" href="../../contact/">相談したいことがある方はこちら</a>
    </div>
  </div>
</section>
</main>
<footer><div class="wrap">&copy; 2026 ノビシロ — ブランド名は検討中です。</div></footer>
<script src="../../analytics-config.js"></script>
</body>
</html>
```

- [ ] **Step 2: LP検査スクリプトを実行して合格することを確認**

Run: `python3 scripts/check_lp_nobishiro.py`
Expected: `サイト検査完了: 8ページ / エラー 0`

- [ ] **Step 3: コミット**

```bash
git add site/nobishiro/shindan/complete/index.html
git commit -m "feat(nobishiro-shindan): 決済完了ページを追加"
```

---

### Task 9: ハブLPの「近日公開」を実際の診断ページへのリンクに差し替え

**Files:**
- Modify: `site/nobishiro/index.html:113-117`

**Interfaces:**
- Consumes: `site/nobishiro/shindan/index.html`(Task 7で作成済み)
- Produces: なし

- [ ] **Step 1: 該当セクションを置き換える**

`site/nobishiro/index.html` の以下の部分(113〜117行目):

```html
      <h2>まずは無料の自己診断から <span class="soon">近日公開</span></h2>
      <p>AIエージェント「ガジュマルくん」が、あなたの会社の管理コストと営業効率の課題を診断するオンラインツールを準備中です。公開まで、まずは無料相談をご利用ください。</p>
      <div class="ctarow" style="margin-top:16px">
        <a class="btn" href="contact/">無料相談を予約する</a>
      </div>
```

を、次の内容に置き換える:

```html
      <h2>まずは無料の自己診断から</h2>
      <p>AIエージェント「ガジュマルくん」が、あなたの会社の管理コストと営業効率の課題を診断します。回答後、¥14,800でカスタムレポートをメールでお届けします。</p>
      <div class="ctarow" style="margin-top:16px">
        <a class="btn" href="shindan/">AI活用診断を受ける(¥14,800)</a>
        <a class="btn ghost" href="contact/">無料相談を予約する</a>
      </div>
```

`.soon`のCSSルール(45行目付近)は他ページで使っていないため削除してよいが、削除は必須ではない(未使用でもLP検査は失敗しない)。**削除しない**(YAGNI — 動作に影響がなく、削除する積極的理由がないため)。

- [ ] **Step 2: LP検査スクリプトを実行して合格することを確認**

Run: `python3 scripts/check_lp_nobishiro.py`
Expected: `サイト検査完了: 8ページ / エラー 0`

- [ ] **Step 3: ブラウザ相当の手動確認**

`site/nobishiro/index.html` を開き、「AI活用診断を受ける」リンクの`href`が`shindan/`になっていること、「近日公開」バッジが表示されなくなっていることを確認する。

- [ ] **Step 4: コミット**

```bash
git add site/nobishiro/index.html
git commit -m "feat(nobishiro-shindan): ハブLPから診断ページへの導線を有効化(近日公開バッジを撤去)"
```

---

### Task 10: CI — 新しいNodeテストを実行対象に追加

**Files:**
- Modify: `.github/workflows/nobishiro-ci.yml`

**Interfaces:**
- Consumes: `tests/nobishiro-shindan-logic.test.mjs`(Task 6)、`tests/nobishiro-shindan-backend.test.mjs`(Task 1〜3)
- Produces: なし

- [ ] **Step 1: `.github/workflows/nobishiro-ci.yml` の末尾(24〜25行目の後)に以下を追記**

現在の内容:
```yaml
      - name: LP検査(サイズ予算・禁止表現・基本要件)
        run: python scripts/check_lp_nobishiro.py
```

を、次の内容に置き換える(Node実行ステップを追加):

```yaml
      - name: LP検査(サイズ予算・禁止表現・基本要件)
        run: python scripts/check_lp_nobishiro.py

      - uses: actions/setup-node@v6
        with:
          node-version: "22"

      - name: 診断ロジック テスト(フロント+バックエンド純粋ロジック)
        run: node --test tests/nobishiro-shindan-logic.test.mjs tests/nobishiro-shindan-backend.test.mjs
```

また、`on.push.paths` / `on.pull_request.paths`(6〜7行目、9〜10行目)に以下2行を追加し、これらのファイルの変更でもCIが起動するようにする:

```yaml
      - "gas/nobishiro-shindan/**"
      - "tests/nobishiro-shindan-*.test.mjs"
```

(それぞれ`site/nobishiro/**`の直後に追加する)

- [ ] **Step 2: ローカルでテストコマンドを実行し、CIと同じ結果になることを確認**

Run: `node --test tests/nobishiro-shindan-logic.test.mjs tests/nobishiro-shindan-backend.test.mjs`
Expected: 全テストPASS(Task 1〜3で12件、Task 6で5件、計17件)

- [ ] **Step 3: コミットしてプッシュし、CIが緑になることを確認**

```bash
git add .github/workflows/nobishiro-ci.yml
git commit -m "ci(nobishiro): 診断バックエンド/フロントの純粋ロジックテストを実行対象に追加"
git push -u origin claude/claude-code-monetization-models-gsl932
```

Expected: GitHub Actionsでnobishiro-ciが実行され成功する

---

## Self-Review Summary

- **Spec coverage**: 設計書のデータフロー(フォーム送信→Sheets記録→Stripe Checkout作成→webhook受付→Claude APIレポート生成→メール送信→Sheets更新)を全タスクでカバー。価格¥14,800固定、HTMLメールのみ、GAS+Sheetsという簡略化方針も反映。設計書execution時に判明した「GASはHTTPヘッダーを読めないためHMAC署名検証が使えない」という制約は、トークンベースの認証方式に置き換えて全タスクに反映済み
- **Placeholder scan**: `GAS_WEB_APP_URL_PLACEHOLDER`と`STRIPE_SECRET_KEY`等のScript Properties参照はあるが、これらは実アカウント作成後に埋める値として意図的に切り出したもので、コード自体は完全に動作する(Plan 1の`contact@example.com`と同じ設計判断)
- **Type consistency**: `NBBackendLogic`(Logic.gs)と`NBShindan`(logic.js)の許容値配列(業種・従業員数等)は同一の値を使用。Sheetsの列インデックス(`COLUMN`定数)はTask 4で定義しTask 5で一貫して参照

## デプロイ前の手動セットアップ手順(タスクではなく、人間が行う準備作業)

このプランのタスクはすべてコードの実装であり、以下の外部アカウント作成・設定はユーザー側で行う必要がある。

1. **Stripeアカウント作成**(テストモードでまず動作確認、本番は小柳さんの掲載決裁後)
   - 商品は都度Checkout Session作成時に動的に定義する設計のため、事前の商品登録は不要
   - シークレットキー(`sk_test_...` または `sk_live_...`)を控える

2. **Google側のGASプロジェクト作成**
   - `gas/nobishiro-shindan/Logic.gs`と`Code.gs`の内容を、[clasp](https://github.com/google/clasp)で新規GASプロジェクトにpushする(`clasp create`→`clasp push`)。どのGoogleアカウントで作成するか(ALLGROUP既存アカウント/新規)を決める
   - 新規のGoogle Sheetsを1つ作成し、シート名を`リード台帳`にする。ヘッダー行は必須ではない(コードは列位置で読み書きするため)
   - GASエディタの「プロジェクトの設定」→「スクリプト プロパティ」に以下を設定する:
     - `STRIPE_SECRET_KEY`
     - `SITE_BASE_URL`(例: `https://allgroup-inc.github.io/hojo-hq/nobishiro`。ただし現在`site/nobishiro/`は公開パイプラインから除外中のため、掲載承認後の実URLを設定する)
     - `SHEET_ID`(作成したSheetsのID)
     - `ANTHROPIC_API_KEY`(既存キーを流用するか新規発行するか要判断)
     - `WEBHOOK_TOKEN`(32文字以上のランダム文字列を生成して設定。例: `openssl rand -hex 32`)
   - 「デプロイ」→「新しいデプロイ」→種類「ウェブアプリ」、アクセスできるユーザーを「全員」にしてデプロイし、発行されたWeb App URLを控える

3. **StripeのWebhook設定**
   - Stripeダッシュボードで、Webhookエンドポイントとして `<GAS Web App URL>?type=webhook&token=<WEBHOOK_TOKENと同じ値>` を登録
   - 購読するイベントは `checkout.session.completed` のみ

4. **フロント側のURL差し替え**
   - `site/nobishiro/shindan/index.html` の `GAS_WEB_APP_URL_PLACEHOLDER` を、実際のGAS Web App URLに差し替える

5. **手動E2E確認**(Stripeテストモードで)
   - 診断フォームに回答→テストカード番号で決済→completeページに遷移することを確認
   - Stripeダッシュボードでwebhookが200を返していることを確認
   - Sheetsの該当行が`paid`・`sent`に更新されていることを確認
   - 入力したメールアドレスにレポートメールが届くことを確認

6. **本番化**
   - 小柳さんの掲載決裁が出たら、`.github/workflows/update.yml`の除外ステップを外し、Stripeを本番モード(`sk_live_...`)に切り替える
