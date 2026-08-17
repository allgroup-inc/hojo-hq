# glow-ma 現場訪問ログ LINE音声記録システム Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 現場担当者がLINEに音声メッセージを送るだけで、Gemini APIによる文字起こし・構造化データ抽出とLINE上のボタン確認を経て、対応履歴ログ(必要なら企業マスタ)に反映される仕組みを構築する。

**Architecture:** LINE公式アカウント(新規)→GAS Web App(`doPost`)がWebhookを受信し即座にACK返信→時間主導トリガーが非同期でGemini APIによる文字起こし・抽出と企業マスタ照合を行い、LINEの postback ボタンで担当者が確認・確定する。対応履歴ログへの書き込みはpostback確定時に行う。

**Tech Stack:** Google Apps Script(GAS)、Google スプレッドシート、LINE Messaging API、Gemini API、Node.js(`node --test`によるロジック層のテスト)

**Spec:** `docs/superpowers/specs/2026-08-17-glow-ma-line-voice-log-design.md`

## Global Constraints

- 新規`.js`ファイルは既存と同じUMD形式(`(function(global){...})(typeof window!=="undefined"?window:globalThis)`、`module.exports`/`global.GlowXxx`)で書き、`var`のみ使用しES6構文(let/const/アロー関数/テンプレートリテラル/クラス)は使わない(既存ファイル全ての慣例)
- GAS実行層(`.gs`ファイル)はNode側でテストしない。純粋ロジック(`.js`ファイル)のみ`tests/glow_ma_*.test.mjs`でNode側テストする(設計書7章)
- スプレッドシートへの書き込みは既存パターンどおり`LockService.getDocumentLock()`を使う
- 新規スクリプトプロパティ: `LINE_CHANNEL_ACCESS_TOKEN`(LINE Messaging APIのチャネルアクセストークン)、`LINE_CHANNEL_ID`(Webhookのdestination形式チェック用)、`GEMINI_API_KEY`
- 既存の`TRACKING_BASE_URL`用Web AppデプロイのURLを、LINE公式アカウントのWebhook URLとしてそのまま使う(GASの`doGet`と`doPost`は同一デプロイのURLを共有するため、新しいデプロイは不要)
- Apps Scriptの`doPost`はHTTPヘッダーを読み取れないため、LINEの署名(`X-Line-Signature`)による暗号学的な検証は実装できない。代わりにWebhook本文の`destination`フィールドが`LINE_CHANNEL_ID`と一致するかの形式チェックのみで防御する(設計書5章、2026-08-17 小柳さん承認済み)
- 1件の処理失敗が他の処理を止めない障害隔離を徹底する(既存のLetterRunner.gs等と同じ方針)
- 企業マスタ(`GlowSchema.COMPANY_MASTER_HEADERS`)・対応履歴ログ(`GlowSchema.INTERACTION_LOG_HEADERS`)・スタッフ(`GlowSchema.STAFF_HEADERS`)の既存列順は変更しない。列を追加する場合は必ず末尾に追加する

---

### Task 1: schema.js にスキーマを追加

**Files:**
- Modify: `glow-ma/src/schema.js`
- Test: `tests/glow_ma_schema.test.mjs`

**Interfaces:**
- Produces: `GlowSchema.LINE_VOICE_LOG_SHEET_NAME`(string)、`GlowSchema.LINE_VOICE_LOG_HEADERS`(string[]、12列)、`GlowSchema.LINE_VOICE_LOG_STATUSES`(string[]、8種)、`GlowSchema.STAFF_HEADERS`(string[]、5列に拡張)

- [ ] **Step 1: 「スタッフ」タブのヘッダーに「LINE User ID」列を追加**

`glow-ma/src/schema.js`の`STAFF_HEADERS`定義を以下に置き換える(直前の`STAFF_SHEET_NAME`のコメントも更新する):

```javascript
  var STAFF_SHEET_NAME = "スタッフ";
  // Slack User ID の調べ方: Slackで対象社員のプロフィールを開き「その他」→
  // 「メンバーIDをコピー」(U から始まる文字列)。メールアドレスではない。
  // LINE User ID の調べ方: LINE公式アカウントの管理画面から事前に一覧取得する方法が
  // ないため、対象社員が最初に音声を送った際にGAS側の実行ログへ出力されたIDを
  // 人間が転記する(glow-ma/src/LineVoiceLogRunner.gs参照)。
  var STAFF_HEADERS = ["氏名", "Slack User ID", "有効", "メールアドレス", "LINE User ID"];
```

- [ ] **Step 2: 「音声ログ処理状況」タブの定義を追加**

同ファイルの`QR_RESULT_HEADERS`定義の直後、`var api = {`の直前に以下を追加する:

```javascript
  var LINE_VOICE_LOG_SHEET_NAME = "音声ログ処理状況";
  var LINE_VOICE_LOG_HEADERS = [
    "処理ID", "LINEユーザーID", "LINEメッセージID", "ステータス",
    "受信日時", "会社名候補", "企業ID",
    "種別候補", "対応相手候補", "内容メモ", "次回アクション", "エラー内容"
  ];
  var LINE_VOICE_LOG_STATUSES = [
    "受信済み", "文字起こし済み", "企業選択待ち", "新規企業確認待ち",
    "最終確認待ち", "確定", "破棄", "エラー"
  ];
```

- [ ] **Step 3: `api`エクスポートに追加**

`var api = {...}`オブジェクトの末尾(`QR_RESULT_HEADERS: QR_RESULT_HEADERS`の行の直後)に以下を追加する:

```javascript
    LINE_VOICE_LOG_SHEET_NAME: LINE_VOICE_LOG_SHEET_NAME,
    LINE_VOICE_LOG_HEADERS: LINE_VOICE_LOG_HEADERS,
    LINE_VOICE_LOG_STATUSES: LINE_VOICE_LOG_STATUSES
```

(既存の`QR_RESULT_HEADERS: QR_RESULT_HEADERS`行の末尾にカンマを追加するのを忘れないこと)

- [ ] **Step 4: テストを追加**

`tests/glow_ma_schema.test.mjs`の末尾に以下を追加する:

```javascript
test("音声ログ処理状況のシート名・ヘッダー・ステータス一覧が定義されている", () => {
  assert.equal(schema.LINE_VOICE_LOG_SHEET_NAME, "音声ログ処理状況");
  assert.ok(Array.isArray(schema.LINE_VOICE_LOG_HEADERS));
  assert.equal(schema.LINE_VOICE_LOG_HEADERS.length, 12);
  assert.ok(schema.LINE_VOICE_LOG_HEADERS.includes("処理ID"));
  assert.ok(schema.LINE_VOICE_LOG_HEADERS.includes("LINEユーザーID"));
  assert.ok(Array.isArray(schema.LINE_VOICE_LOG_STATUSES));
  assert.ok(schema.LINE_VOICE_LOG_STATUSES.includes("受信済み"));
  assert.ok(schema.LINE_VOICE_LOG_STATUSES.includes("確定"));
});

test("スタッフのヘッダーにLINE User ID列が追加されている", () => {
  assert.deepEqual(schema.STAFF_HEADERS, ["氏名", "Slack User ID", "有効", "メールアドレス", "LINE User ID"]);
});
```

- [ ] **Step 5: テスト実行**

Run: `node --test tests/glow_ma_schema.test.mjs`
Expected: 全件PASS

- [ ] **Step 6: Commit**

```bash
git add glow-ma/src/schema.js tests/glow_ma_schema.test.mjs
git commit -m "feat(glow-ma): 音声ログ処理状況タブとスタッフのLINE User ID列を定義"
```

---

### Task 2: lineVoiceLogContent.js — 企業照合・データ整形ロジック

**Files:**
- Create: `glow-ma/src/lineVoiceLogContent.js`
- Test: `tests/glow_ma_lineVoiceLogContent.test.mjs`

**Interfaces:**
- Consumes: `GlowSchema.INTERACTION_TYPES`、`GlowSchema.RESPONDENT_TYPES`、`GlowSchema.COMPANY_MASTER_HEADERS`(Task 1で確定済み)
- Produces: `GlowLineVoiceLogContent.matchCompanyCandidates(companies, spokenName)` → `[{企業ID, 会社名}]`(最大5件)、`GlowLineVoiceLogContent.normalizeInteractionType(candidateType)` → string、`GlowLineVoiceLogContent.normalizeRespondentType(candidateRespondent)` → string、`GlowLineVoiceLogContent.buildInteractionLogRow(logId, companyId, todayString, staffName, interactionType, respondentType, contentMemo, nextAction)` → array(`INTERACTION_LOG_HEADERS`順)、`GlowLineVoiceLogContent.buildNewCompanyRow(companyId, companyName)` → array(`COMPANY_MASTER_HEADERS`順)。以降のタスクがこれらをそのまま呼び出す

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_lineVoiceLogContent.test.mjs`を新規作成する:

```javascript
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const lineVoiceLogContent = require("../glow-ma/src/lineVoiceLogContent.js");
const schema = require("../glow-ma/src/schema.js");

test("matchCompanyCandidates: 完全一致は部分一致より先頭に来る", () => {
  const companies = [
    { "企業ID": "C000001", "会社名": "沖縄建設" },
    { "企業ID": "C000002", "会社名": "沖縄建設工業" }
  ];
  const result = lineVoiceLogContent.matchCompanyCandidates(companies, "沖縄建設");
  assert.equal(result.length, 2);
  assert.equal(result[0]["企業ID"], "C000001");
});

test("matchCompanyCandidates: 一致する企業が無ければ空配列", () => {
  const companies = [{ "企業ID": "C000001", "会社名": "沖縄建設" }];
  const result = lineVoiceLogContent.matchCompanyCandidates(companies, "存在しない商事");
  assert.deepEqual(result, []);
});

test("matchCompanyCandidates: spokenNameが空なら空配列", () => {
  const companies = [{ "企業ID": "C000001", "会社名": "沖縄建設" }];
  assert.deepEqual(lineVoiceLogContent.matchCompanyCandidates(companies, ""), []);
  assert.deepEqual(lineVoiceLogContent.matchCompanyCandidates(companies, null), []);
});

test("matchCompanyCandidates: 最大5件までに絞られる", () => {
  const companies = [];
  for (let i = 1; i <= 8; i++) {
    companies.push({ "企業ID": "C00000" + i, "会社名": "沖縄商事" + i });
  }
  const result = lineVoiceLogContent.matchCompanyCandidates(companies, "沖縄商事");
  assert.equal(result.length, 5);
});

test("normalizeInteractionType: 既知の種別はそのまま返す", () => {
  assert.equal(lineVoiceLogContent.normalizeInteractionType("電話"), "電話");
});

test("normalizeInteractionType: 未知の値は既定値(面談実施)にフォールバックする", () => {
  assert.equal(lineVoiceLogContent.normalizeInteractionType("雑談"), "面談実施");
  assert.equal(lineVoiceLogContent.normalizeInteractionType(""), "面談実施");
});

test("normalizeRespondentType: 既知の対応相手はそのまま返す", () => {
  assert.equal(lineVoiceLogContent.normalizeRespondentType("オーナー社長本人"), "オーナー社長本人");
});

test("normalizeRespondentType: 未知の値は既定値(経理・総務等の窓口担当)にフォールバックする", () => {
  assert.equal(lineVoiceLogContent.normalizeRespondentType("不明な人物"), "経理・総務等の窓口担当");
});

test("buildInteractionLogRow: INTERACTION_LOG_HEADERSの並び順で配列を返す", () => {
  const row = lineVoiceLogContent.buildInteractionLogRow(
    "H-test-1", "C000001", "2026-08-17", "嶺井忍", "電話", "オーナー社長本人", "内容メモ本文", "次回訪問"
  );
  assert.deepEqual(row, [
    "H-test-1", "C000001", "2026-08-17", "嶺井忍", "電話", "オーナー社長本人", "内容メモ本文", "次回訪問"
  ]);
  assert.equal(row.length, schema.INTERACTION_LOG_HEADERS.length);
});

test("buildInteractionLogRow: 種別・対応相手は正規化される", () => {
  const row = lineVoiceLogContent.buildInteractionLogRow(
    "H-test-2", "C000001", "2026-08-17", "嶺井忍", "雑談", "不明", "メモ", ""
  );
  const typeIndex = schema.INTERACTION_LOG_HEADERS.indexOf("種別");
  const respondentIndex = schema.INTERACTION_LOG_HEADERS.indexOf("対応相手");
  assert.equal(row[typeIndex], "面談実施");
  assert.equal(row[respondentIndex], "経理・総務等の窓口担当");
});

test("buildNewCompanyRow: 企業ID・会社名以外は空欄、連絡不要はfalse", () => {
  const row = lineVoiceLogContent.buildNewCompanyRow("C009999", "テスト新規企業");
  assert.equal(row.length, schema.COMPANY_MASTER_HEADERS.length);
  const idIndex = schema.COMPANY_MASTER_HEADERS.indexOf("企業ID");
  const nameIndex = schema.COMPANY_MASTER_HEADERS.indexOf("会社名");
  const dncIndex = schema.COMPANY_MASTER_HEADERS.indexOf("連絡不要");
  assert.equal(row[idIndex], "C009999");
  assert.equal(row[nameIndex], "テスト新規企業");
  assert.equal(row[dncIndex], false);
  row.forEach((value, index) => {
    if (index === idIndex || index === nameIndex || index === dncIndex) return;
    assert.equal(value, "");
  });
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_lineVoiceLogContent.test.mjs`
Expected: FAIL(`Cannot find module '../glow-ma/src/lineVoiceLogContent.js'`)

- [ ] **Step 3: 実装を書く**

`glow-ma/src/lineVoiceLogContent.js`を新規作成する:

```javascript
/* GLOW企業リレーション台帳: 現場訪問ログLINE音声記録 対象抽出・データ整形ロジック
 * ブラウザ相当のGAS(global.GlowLineVoiceLogContent)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_lineVoiceLogContent.test.mjs で検証される。
 */
(function (global) {
  "use strict";

  function getGlowSchema_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./schema.js");
    }
    return global.GlowSchema;
  }

  var DEFAULT_INTERACTION_TYPE = "面談実施";
  var DEFAULT_RESPONDENT_TYPE = "経理・総務等の窓口担当";
  var MAX_COMPANY_CANDIDATES = 5;

  /**
   * 音声から抽出した会社名(spokenName)を企業マスタと照合し、候補を最大5件返す。
   * 完全一致(スコア2)を部分一致(スコア1、どちらかがどちらかを含む)より優先する。
   * spokenNameが空、または一致する企業が無い場合は空配列を返す(新規企業扱いの判定は
   * 呼び出し元がこの空配列を見て行う)。
   */
  function matchCompanyCandidates(companies, spokenName) {
    var trimmed = String(spokenName || "").trim();
    if (!trimmed) return [];
    var scored = (companies || [])
      .map(function (company) {
        var name = company["会社名"] || "";
        var score = 0;
        if (name && name === trimmed) {
          score = 2;
        } else if (name && (name.indexOf(trimmed) !== -1 || trimmed.indexOf(name) !== -1)) {
          score = 1;
        }
        return { company: company, score: score };
      })
      .filter(function (entry) { return entry.score > 0; })
      .sort(function (a, b) { return b.score - a.score; });
    return scored.slice(0, MAX_COMPANY_CANDIDATES).map(function (entry) {
      return { "企業ID": entry.company["企業ID"], "会社名": entry.company["会社名"] };
    });
  }

  /**
   * Geminiが返した種別候補を、対応履歴ログの「種別」プルダウンで許容される値に正規化する。
   * 一致しない場合は既定値(面談実施)にフォールバックする(表記ゆれで集計から漏れないため)。
   */
  function normalizeInteractionType(candidateType) {
    var glowSchema = getGlowSchema_();
    if (glowSchema.INTERACTION_TYPES.indexOf(candidateType) !== -1) return candidateType;
    return DEFAULT_INTERACTION_TYPE;
  }

  /**
   * Geminiが返した対応相手候補を、対応履歴ログの「対応相手」プルダウンで許容される値に
   * 正規化する。一致しない場合は既定値(経理・総務等の窓口担当)にフォールバックする。
   */
  function normalizeRespondentType(candidateRespondent) {
    var glowSchema = getGlowSchema_();
    if (glowSchema.RESPONDENT_TYPES.indexOf(candidateRespondent) !== -1) return candidateRespondent;
    return DEFAULT_RESPONDENT_TYPE;
  }

  /**
   * 対応履歴ログへ書き込む1行分の配列を、INTERACTION_LOG_HEADERSの並び順で組み立てる。
   * logIdはGAS側でUtilities.getUuid()を使って生成し、"H-"を付けて渡すこと(Node側では
   * UUID生成手段がないため、この関数はID生成の責務を持たない)。
   */
  function buildInteractionLogRow(logId, companyId, todayString, staffName, interactionType, respondentType, contentMemo, nextAction) {
    return [
      logId, companyId, todayString, staffName,
      normalizeInteractionType(interactionType),
      normalizeRespondentType(respondentType),
      contentMemo || "", nextAction || ""
    ];
  }

  /**
   * 企業マスタへ新規企業として追加する1行分の配列を、COMPANY_MASTER_HEADERSの並び順で
   * 組み立てる。企業ID・会社名以外は空欄とする(設計書4章のとおり、詳細は後で通常の
   * 編集フローで補完する)。「連絡不要」列はチェックボックス列のため空文字ではなくfalseにする。
   */
  function buildNewCompanyRow(companyId, companyName) {
    var glowSchema = getGlowSchema_();
    var headers = glowSchema.COMPANY_MASTER_HEADERS;
    var dncIndex = headers.indexOf("連絡不要");
    var idIndex = headers.indexOf("企業ID");
    var nameIndex = headers.indexOf("会社名");
    return headers.map(function (header, index) {
      if (index === idIndex) return companyId;
      if (index === nameIndex) return companyName;
      if (index === dncIndex) return false;
      return "";
    });
  }

  var api = {
    matchCompanyCandidates: matchCompanyCandidates,
    normalizeInteractionType: normalizeInteractionType,
    normalizeRespondentType: normalizeRespondentType,
    buildInteractionLogRow: buildInteractionLogRow,
    buildNewCompanyRow: buildNewCompanyRow
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowLineVoiceLogContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_lineVoiceLogContent.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/lineVoiceLogContent.js tests/glow_ma_lineVoiceLogContent.test.mjs
git commit -m "feat(glow-ma): 音声ログの企業照合・データ整形ロジックを追加"
```

---

### Task 3: lineVoiceLogContent.js — LINE会話メッセージ・postbackデータ組み立て

**Files:**
- Modify: `glow-ma/src/lineVoiceLogContent.js`(Task 2で作成)
- Test: `tests/glow_ma_lineVoiceLogContent.test.mjs`(Task 2で作成)

**Interfaces:**
- Consumes: Task 2で定義した`api`オブジェクト構造(同じファイル内)
- Produces: `GlowLineVoiceLogContent.ACK_MESSAGE_TEXT`(string定数)、`GlowLineVoiceLogContent.POSTBACK_ACTIONS`({SELECT_COMPANY, NEW_COMPANY_CONFIRM, FINAL_CONFIRM})、`GlowLineVoiceLogContent.NOT_FOUND_VALUE`/`YES_VALUE`/`NO_VALUE`/`CONFIRM_VALUE`/`DISCARD_VALUE`(string定数)、`GlowLineVoiceLogContent.buildCompanySelectionPrompt(processId, candidates)` → `{text, options:[{label, data}]}`、`GlowLineVoiceLogContent.buildNewCompanyConfirmPrompt(processId, spokenName)` → 同構造、`GlowLineVoiceLogContent.buildFinalConfirmPrompt(processId, companyName, interactionType, respondentType, contentMemo, nextAction)` → 同構造、`GlowLineVoiceLogContent.buildCompletionMessage(companyName)`/`buildDiscardMessage()`/`buildProcessingErrorMessage()`/`buildStaffNotFoundMessage()`/`buildAlreadyProcessingMessage()` → string、`GlowLineVoiceLogContent.buildPostbackData(action, processId, value)` → string、`GlowLineVoiceLogContent.parsePostbackData(dataString)` → `{action, processId, value}`。Task 5〜7のGASランナーがこれらをそのまま呼び出し、`options`をLINEのquickReply JSON形式に変換する

- [ ] **Step 1: 失敗するテストを書く**

`tests/glow_ma_lineVoiceLogContent.test.mjs`の末尾に以下を追加する:

```javascript
test("buildPostbackData / parsePostbackData: 往復できる", () => {
  const data = lineVoiceLogContent.buildPostbackData("selectCompany", "P-123", "C000001");
  const parsed = lineVoiceLogContent.parsePostbackData(data);
  assert.deepEqual(parsed, { action: "selectCompany", processId: "P-123", value: "C000001" });
});

test("buildPostbackData: 値に&や=が含まれてもエンコードされ壊れない", () => {
  const data = lineVoiceLogContent.buildPostbackData("selectCompany", "P-1", "A&B=C");
  const parsed = lineVoiceLogContent.parsePostbackData(data);
  assert.equal(parsed.value, "A&B=C");
});

test("buildCompanySelectionPrompt: 候補+見つからないボタンを含む", () => {
  const candidates = [
    { "企業ID": "C000001", "会社名": "沖縄建設" },
    { "企業ID": "C000002", "会社名": "沖縄建設工業" }
  ];
  const prompt = lineVoiceLogContent.buildCompanySelectionPrompt("P-1", candidates);
  assert.equal(prompt.options.length, 3);
  assert.equal(prompt.options[2].label, "見つからない");
  const parsed = lineVoiceLogContent.parsePostbackData(prompt.options[0].data);
  assert.equal(parsed.value, "C000001");
  assert.equal(parsed.action, lineVoiceLogContent.POSTBACK_ACTIONS.SELECT_COMPANY);
});

test("buildCompanySelectionPrompt: 会社名が長い場合はボタンのラベルを20文字以内に切り詰める", () => {
  const longName = "とてもとても長い名前の株式会社沖縄総合建設不動産開発コンサルティング";
  const prompt = lineVoiceLogContent.buildCompanySelectionPrompt("P-1", [{ "企業ID": "C000001", "会社名": longName }]);
  assert.ok(prompt.options[0].label.length <= 20);
});

test("buildNewCompanyConfirmPrompt: Yes/Noボタンを含む", () => {
  const prompt = lineVoiceLogContent.buildNewCompanyConfirmPrompt("P-1", "テスト商事");
  assert.equal(prompt.options.length, 2);
  assert.ok(prompt.text.includes("テスト商事"));
});

test("buildFinalConfirmPrompt: 入力内容がテキストに含まれる", () => {
  const prompt = lineVoiceLogContent.buildFinalConfirmPrompt(
    "P-1", "沖縄建設", "電話", "オーナー社長本人", "見積の話", "来週再訪問"
  );
  assert.ok(prompt.text.includes("沖縄建設"));
  assert.ok(prompt.text.includes("見積の話"));
  assert.equal(prompt.options.length, 2);
});

test("buildCompletionMessage / buildDiscardMessage: 固定文言を返す", () => {
  assert.ok(lineVoiceLogContent.buildCompletionMessage("沖縄建設").includes("沖縄建設"));
  assert.ok(lineVoiceLogContent.buildDiscardMessage().length > 0);
  assert.ok(lineVoiceLogContent.buildProcessingErrorMessage().length > 0);
  assert.ok(lineVoiceLogContent.buildStaffNotFoundMessage().length > 0);
  assert.ok(lineVoiceLogContent.buildAlreadyProcessingMessage().length > 0);
});
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `node --test tests/glow_ma_lineVoiceLogContent.test.mjs`
Expected: FAIL(`lineVoiceLogContent.buildPostbackData is not a function` 等)

- [ ] **Step 3: 実装を追加する**

`glow-ma/src/lineVoiceLogContent.js`の`var api = {`の直前に、以下を追加する:

```javascript
  var ACK_MESSAGE_TEXT = "録音、届きました。少々お待ちください。";
  var MAX_LABEL_LENGTH = 20;

  var POSTBACK_ACTIONS = {
    SELECT_COMPANY: "selectCompany",
    NEW_COMPANY_CONFIRM: "newCompanyConfirm",
    FINAL_CONFIRM: "finalConfirm"
  };

  var NOT_FOUND_VALUE = "NOT_FOUND";
  var YES_VALUE = "YES";
  var NO_VALUE = "NO";
  var CONFIRM_VALUE = "CONFIRM";
  var DISCARD_VALUE = "DISCARD";

  function truncateLabel_(label) {
    var text = String(label || "");
    if (text.length <= MAX_LABEL_LENGTH) return text;
    return text.slice(0, MAX_LABEL_LENGTH - 1) + "…";
  }

  /**
   * buildPostbackDataで組み立てたdata文字列を{action, processId, value}に戻す。
   * 形式が壊れている場合は該当キーがundefinedのオブジェクトを返す(呼び出し元が
   * 必須キーの有無を見て不正なpostbackとして扱う)。
   */
  function parsePostbackData(dataString) {
    var result = {};
    String(dataString || "").split("&").forEach(function (pair) {
      var parts = pair.split("=");
      if (parts.length !== 2) return;
      result[decodeURIComponent(parts[0])] = decodeURIComponent(parts[1]);
    });
    return result;
  }

  /**
   * ボタン(postback)に埋め込むdata文字列を組み立てる。
   * 形式: "action=<action>&processId=<processId>&value=<value>"
   */
  function buildPostbackData(action, processId, value) {
    return "action=" + encodeURIComponent(action) +
      "&processId=" + encodeURIComponent(processId) +
      "&value=" + encodeURIComponent(value);
  }

  /**
   * 候補企業が複数ある場合の選択プロンプトを組み立てる(純粋なデータ構造。実際の
   * LINE Quick Reply JSON形式への変換はGAS側(LineVoiceLogRunner.gs)で行う)。
   */
  function buildCompanySelectionPrompt(processId, candidates) {
    var options = candidates.map(function (candidate) {
      return {
        label: truncateLabel_(candidate["会社名"]),
        data: buildPostbackData(POSTBACK_ACTIONS.SELECT_COMPANY, processId, candidate["企業ID"])
      };
    });
    options.push({
      label: "見つからない",
      data: buildPostbackData(POSTBACK_ACTIONS.SELECT_COMPANY, processId, NOT_FOUND_VALUE)
    });
    return {
      text: "話された会社名に近い企業が複数見つかりました。どの企業ですか?",
      options: options
    };
  }

  /**
   * 一致する企業が見つからなかった場合の、新規登録確認プロンプトを組み立てる。
   */
  function buildNewCompanyConfirmPrompt(processId, spokenName) {
    return {
      text: "「" + spokenName + "」は企業マスタに見つかりませんでした。新規企業として登録しますか?",
      options: [
        { label: "はい、登録する", data: buildPostbackData(POSTBACK_ACTIONS.NEW_COMPANY_CONFIRM, processId, YES_VALUE) },
        { label: "いいえ", data: buildPostbackData(POSTBACK_ACTIONS.NEW_COMPANY_CONFIRM, processId, NO_VALUE) }
      ]
    };
  }

  /**
   * 対応履歴ログへ書き込む直前の最終確認プロンプトを組み立てる。
   */
  function buildFinalConfirmPrompt(processId, companyName, interactionType, respondentType, contentMemo, nextAction) {
    var text = [
      "以下の内容で記録します。よろしいですか?",
      "会社名: " + companyName,
      "種別: " + interactionType,
      "対応相手: " + respondentType,
      "内容メモ: " + contentMemo,
      "次回アクション: " + (nextAction || "(なし)")
    ].join("\n");
    return {
      text: text,
      options: [
        { label: "この内容で記録する", data: buildPostbackData(POSTBACK_ACTIONS.FINAL_CONFIRM, processId, CONFIRM_VALUE) },
        { label: "取り消す(録音し直す)", data: buildPostbackData(POSTBACK_ACTIONS.FINAL_CONFIRM, processId, DISCARD_VALUE) }
      ]
    };
  }

  function buildCompletionMessage(companyName) {
    return companyName + "の対応履歴として記録しました。";
  }

  function buildDiscardMessage() {
    return "取り消しました。もう一度録音してください。";
  }

  function buildProcessingErrorMessage() {
    return "うまく処理できませんでした。もう一度録音してください。";
  }

  function buildStaffNotFoundMessage() {
    return "担当者が特定できませんでした。管理者に「スタッフ」タブへの登録を依頼してください。";
  }

  function buildAlreadyProcessingMessage() {
    return "前の記録がまだ完了していません。LINE上のボタンで確定または取り消しをしてから、次の録音を送ってください。";
  }
```

そして`var api = {`オブジェクトを以下に置き換える(Task 2で定義した5項目に追加する形):

```javascript
  var api = {
    matchCompanyCandidates: matchCompanyCandidates,
    normalizeInteractionType: normalizeInteractionType,
    normalizeRespondentType: normalizeRespondentType,
    buildInteractionLogRow: buildInteractionLogRow,
    buildNewCompanyRow: buildNewCompanyRow,
    ACK_MESSAGE_TEXT: ACK_MESSAGE_TEXT,
    POSTBACK_ACTIONS: POSTBACK_ACTIONS,
    NOT_FOUND_VALUE: NOT_FOUND_VALUE,
    YES_VALUE: YES_VALUE,
    NO_VALUE: NO_VALUE,
    CONFIRM_VALUE: CONFIRM_VALUE,
    DISCARD_VALUE: DISCARD_VALUE,
    buildPostbackData: buildPostbackData,
    parsePostbackData: parsePostbackData,
    buildCompanySelectionPrompt: buildCompanySelectionPrompt,
    buildNewCompanyConfirmPrompt: buildNewCompanyConfirmPrompt,
    buildFinalConfirmPrompt: buildFinalConfirmPrompt,
    buildCompletionMessage: buildCompletionMessage,
    buildDiscardMessage: buildDiscardMessage,
    buildProcessingErrorMessage: buildProcessingErrorMessage,
    buildStaffNotFoundMessage: buildStaffNotFoundMessage,
    buildAlreadyProcessingMessage: buildAlreadyProcessingMessage
  };
```

- [ ] **Step 4: テストが通ることを確認**

Run: `node --test tests/glow_ma_lineVoiceLogContent.test.mjs`
Expected: 全件PASS

- [ ] **Step 5: Commit**

```bash
git add glow-ma/src/lineVoiceLogContent.js tests/glow_ma_lineVoiceLogContent.test.mjs
git commit -m "feat(glow-ma): LINE会話メッセージ・postbackデータの組み立てロジックを追加"
```

---

### Task 4: SheetSetup.gs に「音声ログ処理状況」タブ作成を追加

**Files:**
- Modify: `glow-ma/src/SheetSetup.gs`

**Interfaces:**
- Consumes: `GlowSchema.LINE_VOICE_LOG_SHEET_NAME`、`GlowSchema.LINE_VOICE_LOG_HEADERS`(Task 1)

- [ ] **Step 1: `ensureLedgerTabs`にタブ作成呼び出しを追加**

`glow-ma/src/SheetSetup.gs`の`ensureLedgerTabs`関数内、`ensureTab_(ss, GlowSchema.QR_RESULT_SHEET_NAME, GlowSchema.QR_RESULT_HEADERS);`の直後に以下を追加する:

```javascript
  ensureTab_(ss, GlowSchema.LINE_VOICE_LOG_SHEET_NAME, GlowSchema.LINE_VOICE_LOG_HEADERS);
```

- [ ] **Step 2: 冒頭のJSDocコメントを更新**

ファイル冒頭のコメント(1〜15行目付近)の「11タブ」を「12タブ」に、タブ一覧の文言に「「音声ログ処理状況」」を追加する。該当箇所を以下に置き換える:

```javascript
/**
 * GLOW企業リレーション台帳: シート初期化
 * Apps Scriptエディタの関数選択で ensureLedgerTabs を選び、実行ボタンで手動実行する。
 * 実行すると「企業マスタ」「対応履歴ログ」「紹介パートナーマスタ」「設定」
 * 「レター下書き」「ダッシュボード」「ダッシュボード履歴」「スタッフ」
 * 「パートナー対応履歴ログ」「紹介実績ログ」「QR生成結果」「音声ログ処理状況」の
 * 12タブが(存在しなければ)作成され、1行目に見出しが設定される。
 * 対応履歴ログの「種別」「対応相手」列、レター下書きの「ステータス」列には、
 * 表記ゆれによる集計漏れを防ぐためプルダウン入力規則を設定する。
 * 企業マスタの「電話番号」列は先頭ゼロ落ちを防ぐためプレーンテキスト形式を強制し、
 * 「連絡不要」列にはチェックボックスの入力規則を設定する。
 * 企業マスタの「後継者状況」列には、あり/なし/不明のプルダウン入力規則を設定する(空欄可)。
 * スタッフの「有効」列にはチェックボックスの入力規則を設定する(対面連携機能の連携先候補の
 * on/off切り替え用。ShareRunner.gs参照)。
 */
```

- [ ] **Step 3: テスト実行(既存の回帰確認)**

Run: `node --test tests/*.mjs`
Expected: 全件PASS(このファイルはGAS依存のためNode側の直接テスト対象ではないが、schema.js等の既存テストに影響がないことを確認する)

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/SheetSetup.gs
git commit -m "feat(glow-ma): ensureLedgerTabsに音声ログ処理状況タブの作成を追加"
```

---

### Task 5: LineVoiceLogRunner.gs — Webhook受信・音声メッセージの受付

**Files:**
- Create: `glow-ma/src/LineVoiceLogRunner.gs`

**Interfaces:**
- Consumes: `GlowSchema.LINE_VOICE_LOG_SHEET_NAME`/`LINE_VOICE_LOG_HEADERS`/`STAFF_SHEET_NAME`/`STAFF_HEADERS`(Task 1)、`GlowLineVoiceLogContent.ACK_MESSAGE_TEXT`/`buildStaffNotFoundMessage`/`buildAlreadyProcessingMessage`(Task 3)
- Produces: グローバル関数`doPost(e)`(GAS Web Appのエントリポイント。プロジェクト内に他の`doPost`定義が無いことは既に確認済み)。`readVoiceLogRows_(ss)`・`hasInFlightProcess_(ss, lineUserId)`・`appendVoiceLogRow_(ss, rowValues)`・`updateVoiceLogRow_(ss, sheetRow, updates)`・`resolveStaffNameByLineUserId_(ss, lineUserId)`・`lineReply_(replyToken, specs)`・`buildLineMessagePayload_(spec)`は、Task 6・7がそのまま呼び出す共有ヘルパーとしてこのファイルに定義する

- [ ] **Step 1: 実装を書く**

`glow-ma/src/LineVoiceLogRunner.gs`を新規作成する:

```javascript
/**
 * GLOW企業リレーション台帳: 現場訪問ログ LINE音声記録
 *
 * LINE公式アカウント(GLOW実務チーム専用、新規開設)に音声メッセージを送ると、
 * Gemini APIで文字起こし・構造化データ抽出を行い、LINE上のボタン操作で確認・確定
 * したうえで対応履歴ログ(必要なら企業マスタ)に反映する。設計書:
 * docs/superpowers/specs/2026-08-17-glow-ma-line-voice-log-design.md
 *
 * セットアップ(人間が一度だけ行う):
 * 1. LINE Developersコンソールで新規のMessaging APIチャネル(GLOW実務チーム専用)を作成する
 * 2. 発行されたチャネルアクセストークンを、スクリプト プロパティ LINE_CHANNEL_ACCESS_TOKEN に設定する
 * 3. チャネルID(Basic settingsページのChannel ID)を、スクリプト プロパティ LINE_CHANNEL_ID に設定する
 * 4. Gemini APIキーを、スクリプト プロパティ GEMINI_API_KEY に設定する
 * 5. `clasp push` した後、既存のWeb Appデプロイ(TRACKING_BASE_URLに設定済みのURL)を、
 *    LINE DevelopersコンソールのWebhook URLに設定し、Webhookを有効化する
 *    (doGetとdoPostは同じWeb AppのURLを共有するため、新しいデプロイは不要)
 * 6. スタッフがLINE公式アカウントに最初の音声を送ると、「担当者が特定できませんでした」
 *    と返信される。その時点の実行ログ(Apps Scriptエディタの「実行数」画面)から
 *    LINEユーザーIDを確認し、「スタッフ」タブの該当行の「LINE User ID」列へ手動で転記する
 * 7. installVoiceLogProcessingTrigger を1度だけ実行し、1分おきの処理トリガーを登録する
 *    (Task 6で追加)
 *
 * セキュリティ上の注意: Apps ScriptのdoPostはHTTPヘッダーを読み取れないため、
 * LINEの署名(X-Line-Signature)による暗号学的な検証はできない。代わりに、
 * Webhookリクエスト本文のdestinationフィールドが自チャネルID(LINE_CHANNEL_ID)と
 * 一致するかを確認する形式チェックのみで防御する(設計書5章参照)。
 */
function doPost(e) {
  var body = parseLineWebhookBody_(e);
  if (!body) return ContentService.createTextOutput("");

  var expectedChannelId = PropertiesService.getScriptProperties().getProperty("LINE_CHANNEL_ID");
  if (!expectedChannelId || body.destination !== expectedChannelId) {
    Logger.log("LINE Webhookの形式チェックに失敗しました(destination不一致)。リクエストを破棄します。");
    return ContentService.createTextOutput("");
  }

  (body.events || []).forEach(function (event) {
    try {
      handleLineEvent_(event);
    } catch (error) {
      Logger.log("LINEイベントの処理に失敗しました: " + error);
    }
  });
  return ContentService.createTextOutput("");
}

function parseLineWebhookBody_(e) {
  if (!e || !e.postData || !e.postData.contents) return null;
  try {
    return JSON.parse(e.postData.contents);
  } catch (error) {
    Logger.log("LINE Webhookの本文をJSONとして解析できませんでした: " + error);
    return null;
  }
}

/**
 * 音声メッセージのみをこの時点で処理する。postback(ボタン操作)の処理はTask 7で
 * この関数に分岐を追加する。
 */
function handleLineEvent_(event) {
  if (event.type === "message" && event.message && event.message.type === "audio") {
    handleAudioMessage_(event);
  }
}

/**
 * 音声メッセージ受信時の処理。担当者の特定・多重処理の防止までをこの場で行い、
 * 実際の文字起こし・要約は時間主導トリガー(processQueuedVoiceLogs、Task 6)に委ねる
 * (LINEの応答時間制限に対応するため、doPost内では重い処理をしない)。
 */
function handleAudioMessage_(event) {
  var lineUserId = event.source && event.source.userId;
  var replyToken = event.replyToken;
  if (!lineUserId || !replyToken) return;

  var ss = SpreadsheetApp.getActiveSpreadsheet();

  if (hasInFlightProcess_(ss, lineUserId)) {
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildAlreadyProcessingMessage()]);
    return;
  }

  var staffName = resolveStaffNameByLineUserId_(ss, lineUserId);
  if (!staffName) {
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildStaffNotFoundMessage()]);
    return;
  }

  var processId = "P-" + Utilities.getUuid();
  var receivedAt = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm");
  appendVoiceLogRow_(ss, [
    processId, lineUserId, event.message.id, "受信済み",
    receivedAt, "", "", "", "", "", "", ""
  ]);
  lineReply_(replyToken, [GlowLineVoiceLogContent.ACK_MESSAGE_TEXT]);
}

/**
 * 「スタッフ」タブのLINE User ID列から、有効な担当者の氏名を逆引きする。
 * 見つからない場合(未登録・無効化済み)はnullを返す。
 */
function resolveStaffNameByLineUserId_(ss, lineUserId) {
  var sheet = ss.getSheetByName(GlowSchema.STAFF_SHEET_NAME);
  if (!sheet) return null;
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return null;
  var headers = GlowSchema.STAFF_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var nameIndex = headers.indexOf("氏名");
  var activeIndex = headers.indexOf("有効");
  var lineIdIndex = headers.indexOf("LINE User ID");
  for (var i = 0; i < values.length; i++) {
    var row = values[i];
    if (row[activeIndex] === true && row[lineIdIndex] === lineUserId && row[nameIndex]) {
      return row[nameIndex];
    }
  }
  return null;
}

/**
 * 「音声ログ処理状況」タブの全行を、ヘッダー名をキーとしたオブジェクトの配列として読む。
 * 各オブジェクトにはスプレッドシート上の実際の行番号(1始まり)をsheetRowとして含める
 * (Task 6・7の更新処理で使う)。
 */
function readVoiceLogRows_(ss) {
  var sheet = ss.getSheetByName(GlowSchema.LINE_VOICE_LOG_SHEET_NAME);
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.LINE_VOICE_LOG_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  return values.map(function (row, index) {
    var record = { sheetRow: index + 2 };
    headers.forEach(function (header, colIndex) { record[header] = row[colIndex]; });
    return record;
  });
}

/**
 * 指定したLINEユーザーIDについて、まだ確定・破棄・エラーになっていない
 * (=処理中の)音声ログが既にあるかを判定する。
 */
function hasInFlightProcess_(ss, lineUserId) {
  var inProgressStatuses = ["受信済み", "文字起こし済み", "企業選択待ち", "新規企業確認待ち", "最終確認待ち"];
  return readVoiceLogRows_(ss).some(function (record) {
    return record["LINEユーザーID"] === lineUserId && inProgressStatuses.indexOf(record["ステータス"]) !== -1;
  });
}

function appendVoiceLogRow_(ss, rowValues) {
  var sheet = ss.getSheetByName(GlowSchema.LINE_VOICE_LOG_SHEET_NAME);
  if (!sheet) {
    throw new Error("「" + GlowSchema.LINE_VOICE_LOG_SHEET_NAME + "」タブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    throw new Error("音声ログ処理状況タブのロック取得に失敗しました。");
  }
  try {
    var nextRow = sheet.getLastRow() + 1;
    sheet.getRange(nextRow, 1, 1, GlowSchema.LINE_VOICE_LOG_HEADERS.length).setValues([rowValues]);
  } finally {
    lock.releaseLock();
  }
}

/**
 * 「音声ログ処理状況」タブの指定行を部分更新する。updatesは{列名: 値}のオブジェクト。
 * ロック取得に失敗した場合は、例外を投げず警告ログのみ出す(呼び出し元の処理を
 * 止めないため。更新できなかった行は次回のprocessQueuedVoiceLogs実行で再度拾われうる)。
 */
function updateVoiceLogRow_(ss, sheetRow, updates) {
  var sheet = ss.getSheetByName(GlowSchema.LINE_VOICE_LOG_SHEET_NAME);
  if (!sheet) return;
  var headers = GlowSchema.LINE_VOICE_LOG_HEADERS;
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    Logger.log("音声ログ処理状況タブのロック取得に失敗したため更新をスキップしました(行" + sheetRow + ")。");
    return;
  }
  try {
    Object.keys(updates).forEach(function (key) {
      var colIndex = headers.indexOf(key);
      if (colIndex === -1) return;
      sheet.getRange(sheetRow, colIndex + 1).setValue(updates[key]);
    });
  } finally {
    lock.releaseLock();
  }
}

/**
 * GlowLineVoiceLogContentが返す{text}または{text, options}構造を、LINEの
 * メッセージJSON形式(テキスト、必要ならquickReply付き)に変換する。
 */
function buildLineMessagePayload_(spec) {
  if (typeof spec === "string") {
    return { type: "text", text: spec };
  }
  var message = { type: "text", text: spec.text };
  if (spec.options && spec.options.length > 0) {
    message.quickReply = {
      items: spec.options.map(function (option) {
        return {
          type: "action",
          action: { type: "postback", label: option.label, data: option.data, displayText: option.label }
        };
      })
    };
  }
  return message;
}

function lineReply_(replyToken, specs) {
  var token = PropertiesService.getScriptProperties().getProperty("LINE_CHANNEL_ACCESS_TOKEN");
  if (!token) {
    Logger.log("LINE_CHANNEL_ACCESS_TOKEN が未設定のため、LINEへの返信を送れませんでした。");
    return;
  }
  var messages = specs.map(buildLineMessagePayload_);
  var response = UrlFetchApp.fetch("https://api.line.me/v2/bot/message/reply", {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "Bearer " + token },
    payload: JSON.stringify({ replyToken: replyToken, messages: messages }),
    muteHttpExceptions: true
  });
  var responseCode = response.getResponseCode();
  if (responseCode < 200 || responseCode >= 300) {
    Logger.log("LINEへの返信送信に失敗しました(HTTP " + responseCode + "): " + response.getContentText());
  }
}
```

- [ ] **Step 2: 既存テストへの回帰がないことを確認**

Run: `node --test tests/*.mjs`
Expected: 全件PASS(このファイル自体はGAS依存のためNode側テスト対象外)

- [ ] **Step 3: Commit**

```bash
git add glow-ma/src/LineVoiceLogRunner.gs
git commit -m "feat(glow-ma): LINE Webhook受信・音声メッセージ受付を追加"
```

---

### Task 6: LineVoiceLogRunner.gs — Gemini呼び出し・企業照合・非同期処理トリガー

**Files:**
- Modify: `glow-ma/src/LineVoiceLogRunner.gs`(Task 5で作成)

**Interfaces:**
- Consumes: Task 5の`readVoiceLogRows_`/`updateVoiceLogRow_`/`buildLineMessagePayload_`、`readCompanyRecords_`(`ImportRunner.gs`)、`GlowLineVoiceLogContent.matchCompanyCandidates`/`buildFinalConfirmPrompt`/`buildCompanySelectionPrompt`/`buildNewCompanyConfirmPrompt`/`buildProcessingErrorMessage`(Task 2・3)、`GlowResilience.withRetry`/`isRetryableHttpStatus`(既存`resilience.js`)、`GlowSchema.INTERACTION_TYPES`/`RESPONDENT_TYPES`(既存`schema.js`)
- Produces: グローバル関数`processQueuedVoiceLogs()`(時間主導トリガーのハンドラ)、`installVoiceLogProcessingTrigger()`、`linePush_(lineUserId, specs)`。Task 7が`linePush_`をそのまま利用できる

- [ ] **Step 1: 実装を追加する**

`glow-ma/src/LineVoiceLogRunner.gs`の末尾に以下を追加する:

```javascript
/**
 * processQueuedVoiceLogs をインストール型の時間主導トリガーとして1分間隔で登録する。
 * 冪等: 実行時にまず同じハンドラ関数を指す既存トリガーをすべて削除してから
 * 新規登録するため、重複登録を心配せずに安全に再実行できる(ShippingRunner.gsの
 * installLetterDraftEditTriggerと同じパターン)。
 */
function installVoiceLogProcessingTrigger() {
  var existingTriggers = ScriptApp.getProjectTriggers();
  existingTriggers.forEach(function (trigger) {
    if (trigger.getHandlerFunction() === "processQueuedVoiceLogs") {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  ScriptApp.newTrigger("processQueuedVoiceLogs")
    .timeBased()
    .everyMinutes(1)
    .create();
  Logger.log("音声ログ処理用の1分間隔トリガーを登録しました。");
}

/**
 * 「受信済み」ステータスの音声ログを1件ずつ処理する。1件の失敗が他の未処理分を
 * 止めないよう、失敗した行は「エラー」ステータスに更新し、次の行の処理を続ける
 * (LetterRunner.gs等と同じ障害隔離の方針)。
 */
function processQueuedVoiceLogs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var pending = readVoiceLogRows_(ss).filter(function (record) { return record["ステータス"] === "受信済み"; });
  pending.forEach(function (record) {
    try {
      processOneVoiceLog_(ss, record);
    } catch (error) {
      Logger.log("音声ログの処理に失敗しました(処理ID " + record["処理ID"] + "): " + error);
      updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "エラー", "エラー内容": String(error) });
      linePush_(record["LINEユーザーID"], [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    }
  });
}

function processOneVoiceLog_(ss, record) {
  var audioBlob = fetchLineAudioContent_(record["LINEメッセージID"]);
  var extracted = callGeminiForVoiceLog_(audioBlob);
  updateVoiceLogRow_(ss, record.sheetRow, {
    "ステータス": "文字起こし済み",
    "会社名候補": extracted.companyName || "",
    "種別候補": extracted.interactionType || "",
    "対応相手候補": extracted.respondentType || "",
    "内容メモ": extracted.contentMemo || "",
    "次回アクション": extracted.nextAction || ""
  });

  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  var candidates = GlowLineVoiceLogContent.matchCompanyCandidates(companies, extracted.companyName);

  var lineUserId = record["LINEユーザーID"];
  var pushSpecs;
  if (candidates.length === 1) {
    updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "最終確認待ち", "企業ID": candidates[0]["企業ID"] });
    pushSpecs = [GlowLineVoiceLogContent.buildFinalConfirmPrompt(
      record["処理ID"], candidates[0]["会社名"], extracted.interactionType, extracted.respondentType,
      extracted.contentMemo, extracted.nextAction
    )];
  } else if (candidates.length > 1) {
    updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "企業選択待ち" });
    pushSpecs = [GlowLineVoiceLogContent.buildCompanySelectionPrompt(record["処理ID"], candidates)];
  } else {
    updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "新規企業確認待ち" });
    pushSpecs = [GlowLineVoiceLogContent.buildNewCompanyConfirmPrompt(record["処理ID"], extracted.companyName || "(不明)")];
  }
  linePush_(lineUserId, pushSpecs);
}

function fetchLineAudioContent_(messageId) {
  var token = PropertiesService.getScriptProperties().getProperty("LINE_CHANNEL_ACCESS_TOKEN");
  if (!token) {
    throw new Error("LINE_CHANNEL_ACCESS_TOKEN が未設定です。スクリプト プロパティで設定してください。");
  }
  var response = UrlFetchApp.fetch("https://api-data.line.me/v2/bot/message/" + messageId + "/content", {
    headers: { Authorization: "Bearer " + token },
    muteHttpExceptions: true
  });
  if (response.getResponseCode() !== 200) {
    throw new Error("LINEから音声データの取得に失敗しました(HTTP " + response.getResponseCode() + ")");
  }
  return response.getBlob();
}

function callGeminiForVoiceLog_(audioBlob) {
  return GlowResilience.withRetry(
    function () { return callGeminiForVoiceLogOnce_(audioBlob); },
    {
      maxAttempts: 3,
      backoffMs: [2000, 10000],
      sleepFn: Utilities.sleep,
      isRetryable: function (error) {
        return !!error.statusCode && GlowResilience.isRetryableHttpStatus(error.statusCode);
      },
      onRetry: function (error, attempt) {
        Logger.log("Gemini API呼び出しを再試行します(" + attempt + "回目失敗): " + error);
      }
    }
  );
}

function callGeminiForVoiceLogOnce_(audioBlob) {
  var apiKey = PropertiesService.getScriptProperties().getProperty("GEMINI_API_KEY");
  if (!apiKey) {
    throw new Error("GEMINI_API_KEY が未設定です。スクリプト プロパティで設定してください。");
  }
  var payload = {
    contents: [{
      parts: [
        { text: buildGeminiPrompt_() },
        { inline_data: { mime_type: audioBlob.getContentType() || "audio/m4a", data: Utilities.base64Encode(audioBlob.getBytes()) } }
      ]
    }]
  };
  var response = UrlFetchApp.fetch(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=" + apiKey,
    {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    }
  );
  var responseCode = response.getResponseCode();
  if (responseCode < 200 || responseCode >= 300) {
    var error = new Error("Gemini APIの呼び出しに失敗しました(ステータスコード " + responseCode + "): " + response.getContentText());
    error.statusCode = responseCode;
    throw error;
  }
  var body = JSON.parse(response.getContentText());
  var text = body.candidates && body.candidates[0] && body.candidates[0].content &&
    body.candidates[0].content.parts && body.candidates[0].content.parts[0] &&
    body.candidates[0].content.parts[0].text;
  if (!text) {
    throw new Error("Gemini APIのレスポンスからテキストを取得できませんでした。");
  }
  return parseGeminiExtractionResult_(text);
}

function buildGeminiPrompt_() {
  return "この音声は、営業担当者が企業訪問後に残した口頭のメモです。以下のJSON形式のみを出力してください" +
    "(説明文やコードブロックの記号は付けないこと):\n" +
    "{\"companyName\": \"話された会社名\", " +
    "\"interactionType\": \"" + GlowSchema.INTERACTION_TYPES.join("/") + "のいずれか\", " +
    "\"respondentType\": \"" + GlowSchema.RESPONDENT_TYPES.join("/") + "のいずれか\", " +
    "\"contentMemo\": \"話の内容の要約(2〜3文程度)\", " +
    "\"nextAction\": \"次にやるべきこと(無ければ空文字)\"}";
}

function parseGeminiExtractionResult_(text) {
  var cleaned = text.replace(/```json/g, "").replace(/```/g, "").trim();
  var parsed = JSON.parse(cleaned);
  return {
    companyName: parsed.companyName || "",
    interactionType: parsed.interactionType || "",
    respondentType: parsed.respondentType || "",
    contentMemo: parsed.contentMemo || "",
    nextAction: parsed.nextAction || ""
  };
}

function linePush_(lineUserId, specs) {
  var token = PropertiesService.getScriptProperties().getProperty("LINE_CHANNEL_ACCESS_TOKEN");
  if (!token) {
    Logger.log("LINE_CHANNEL_ACCESS_TOKEN が未設定のため、LINEへのプッシュ送信を送れませんでした。");
    return;
  }
  var messages = specs.map(buildLineMessagePayload_);
  var response = UrlFetchApp.fetch("https://api.line.me/v2/bot/message/push", {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "Bearer " + token },
    payload: JSON.stringify({ to: lineUserId, messages: messages }),
    muteHttpExceptions: true
  });
  var responseCode = response.getResponseCode();
  if (responseCode < 200 || responseCode >= 300) {
    Logger.log("LINEへのプッシュ送信に失敗しました(HTTP " + responseCode + "): " + response.getContentText());
  }
}
```

- [ ] **Step 2: 既存テストへの回帰がないことを確認**

Run: `node --test tests/*.mjs`
Expected: 全件PASS

- [ ] **Step 3: Commit**

```bash
git add glow-ma/src/LineVoiceLogRunner.gs
git commit -m "feat(glow-ma): Gemini APIによる文字起こし・企業照合と非同期処理トリガーを追加"
```

---

### Task 7: LineVoiceLogRunner.gs — postback処理・対応履歴ログ/企業マスタへの書き込み

**Files:**
- Modify: `glow-ma/src/LineVoiceLogRunner.gs`(Task 5・6で作成)

**Interfaces:**
- Consumes: Task 5の`readVoiceLogRows_`/`updateVoiceLogRow_`/`resolveStaffNameByLineUserId_`/`lineReply_`、Task 2・3の`GlowLineVoiceLogContent`一式、`readCompanyRecords_`(`ImportRunner.gs`)、`GlowCsvImport.buildCompanyId`、`GlowDedupe.nextSequenceNumber`
- Produces: グローバル関数`handleLinePostback_(event)`(Task 5の`handleLineEvent_`から呼ばれる)

- [ ] **Step 1: `handleLineEvent_`にpostback分岐を追加する**

`glow-ma/src/LineVoiceLogRunner.gs`内の`handleLineEvent_`関数(Task 5で作成)を、以下に置き換える:

```javascript
/**
 * 音声メッセージとpostback(ボタン操作)の両方をここで振り分ける。
 */
function handleLineEvent_(event) {
  if (event.type === "message" && event.message && event.message.type === "audio") {
    handleAudioMessage_(event);
    return;
  }
  if (event.type === "postback") {
    handleLinePostback_(event);
    return;
  }
  // テキストメッセージ・フォロー等、音声・postback以外のイベントは今回のスコープ外のため無視する
}
```

- [ ] **Step 2: postback処理の実装を追加する**

同ファイルの末尾に以下を追加する:

```javascript
/**
 * postback(ボタン操作)イベントの処理。data文字列からaction/processId/valueを取り出し、
 * 対応する処理へ振り分ける。processIdに一致する「音声ログ処理状況」の行が無い場合
 * (二重タップ・古いボタン操作等)はエラーメッセージのみ返す。
 */
function handleLinePostback_(event) {
  var lineUserId = event.source && event.source.userId;
  var replyToken = event.replyToken;
  var parsed = GlowLineVoiceLogContent.parsePostbackData(event.postback && event.postback.data);
  if (!lineUserId || !replyToken || !parsed.action || !parsed.processId) return;

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var record = readVoiceLogRows_(ss).filter(function (r) { return r["処理ID"] === parsed.processId; })[0];
  if (!record) {
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }

  if (parsed.action === GlowLineVoiceLogContent.POSTBACK_ACTIONS.SELECT_COMPANY) {
    handleCompanySelectionPostback_(ss, replyToken, record, parsed.value);
    return;
  }
  if (parsed.action === GlowLineVoiceLogContent.POSTBACK_ACTIONS.NEW_COMPANY_CONFIRM) {
    handleNewCompanyConfirmPostback_(ss, replyToken, record, parsed.value);
    return;
  }
  if (parsed.action === GlowLineVoiceLogContent.POSTBACK_ACTIONS.FINAL_CONFIRM) {
    handleFinalConfirmPostback_(ss, replyToken, record, parsed.value);
    return;
  }
}

function handleCompanySelectionPostback_(ss, replyToken, record, selectedValue) {
  if (selectedValue === GlowLineVoiceLogContent.NOT_FOUND_VALUE) {
    updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "新規企業確認待ち" });
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildNewCompanyConfirmPrompt(record["処理ID"], record["会社名候補"] || "(不明)")]);
    return;
  }
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  var company = companies.filter(function (c) { return c["企業ID"] === selectedValue; })[0];
  var companyName = company ? company["会社名"] : selectedValue;
  updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "最終確認待ち", "企業ID": selectedValue });
  lineReply_(replyToken, [GlowLineVoiceLogContent.buildFinalConfirmPrompt(
    record["処理ID"], companyName, record["種別候補"], record["対応相手候補"], record["内容メモ"], record["次回アクション"]
  )]);
}

function handleNewCompanyConfirmPostback_(ss, replyToken, record, answer) {
  if (answer !== GlowLineVoiceLogContent.YES_VALUE) {
    updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "破棄" });
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildDiscardMessage()]);
    return;
  }
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "エラー", "エラー内容": "企業マスタタブが見つかりません" });
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }
  var companies = readCompanyRecords_(companySheet);
  var newCompanyId = GlowCsvImport.buildCompanyId(GlowDedupe.nextSequenceNumber(companies));
  var companyName = record["会社名候補"] || "(社名不明)";
  var newRow = GlowLineVoiceLogContent.buildNewCompanyRow(newCompanyId, companyName);

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "エラー", "エラー内容": "企業マスタのロック取得に失敗しました" });
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }
  try {
    var nextRow = companySheet.getLastRow() + 1;
    companySheet.getRange(nextRow, 1, 1, GlowSchema.COMPANY_MASTER_HEADERS.length).setValues([newRow]);
  } finally {
    lock.releaseLock();
  }

  updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "最終確認待ち", "企業ID": newCompanyId });
  lineReply_(replyToken, [GlowLineVoiceLogContent.buildFinalConfirmPrompt(
    record["処理ID"], companyName, record["種別候補"], record["対応相手候補"], record["内容メモ"], record["次回アクション"]
  )]);
}

function handleFinalConfirmPostback_(ss, replyToken, record, answer) {
  if (answer !== GlowLineVoiceLogContent.CONFIRM_VALUE) {
    updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "破棄" });
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildDiscardMessage()]);
    return;
  }

  var staffName = resolveStaffNameByLineUserId_(ss, record["LINEユーザーID"]);
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  if (!logSheet || !staffName) {
    updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "エラー", "エラー内容": "対応履歴ログタブまたは担当者が見つかりません" });
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }

  var logId = "H-" + Utilities.getUuid();
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var row = GlowLineVoiceLogContent.buildInteractionLogRow(
    logId, record["企業ID"], todayString, staffName,
    record["種別候補"], record["対応相手候補"], record["内容メモ"], record["次回アクション"]
  );

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "エラー", "エラー内容": "対応履歴ログのロック取得に失敗しました" });
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }
  try {
    var nextRow = logSheet.getLastRow() + 1;
    logSheet.getRange(nextRow, 1, 1, GlowSchema.INTERACTION_LOG_HEADERS.length).setValues([row]);
  } finally {
    lock.releaseLock();
  }

  updateVoiceLogRow_(ss, record.sheetRow, { "ステータス": "確定" });
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  var company = companies.filter(function (c) { return c["企業ID"] === record["企業ID"]; })[0];
  var companyName = company ? company["会社名"] : (record["会社名候補"] || "");
  lineReply_(replyToken, [GlowLineVoiceLogContent.buildCompletionMessage(companyName)]);
}
```

- [ ] **Step 3: 既存テストへの回帰がないことを確認**

Run: `node --test tests/*.mjs`
Expected: 全件PASS

- [ ] **Step 4: Commit**

```bash
git add glow-ma/src/LineVoiceLogRunner.gs
git commit -m "feat(glow-ma): postback処理(企業選択・新規企業登録・最終確認)と対応履歴ログへの書き込みを追加"
```

---

### Task 8: README.md にセットアップ・使い方・注意事項を追記

**Files:**
- Modify: `glow-ma/README.md`

**Interfaces:**
- Consumes: なし(ドキュメントのみ)

- [ ] **Step 1: README.mdに新セクションを追加する**

`glow-ma/README.md`の末尾(既存の最後のセクションの直後)に以下を追加する:

```markdown
## 現場訪問ログ LINE音声記録(2026-08-17)

現場担当者がLINE公式アカウント(GLOW実務チーム専用)に訪問後の音声メモを送ると、
Gemini APIで文字起こし・構造化データ抽出を行い、LINE上のボタン操作で確認・確定した
うえで対応履歴ログ(必要なら企業マスタ)に反映する。設計書:
`docs/superpowers/specs/2026-08-17-glow-ma-line-voice-log-design.md`

**使い方:**
1. LINE公式アカウントに、訪問直後の音声メモを送る(会社名を最初に話すと、企業マスタとの
   照合がスムーズになる)
2. 「録音、届きました」と即時返信が来る(実際の処理は数分以内に完了する)
3. Geminiによる文字起こし完了後、LINEから確認メッセージ(ボタン付き)が届く。
   会社名の選択・新規企業登録の要否・最終内容の確認をボタン操作で行う
4. 「この内容で記録する」を押すと、対応履歴ログ(必要なら企業マスタにも)に反映される

**セットアップ:**
1. LINE Developersコンソールで、GLOW実務チーム専用のMessaging APIチャネルを新規作成する
2. スクリプトプロパティに以下を設定する:
   - `LINE_CHANNEL_ACCESS_TOKEN`(チャネルアクセストークン)
   - `LINE_CHANNEL_ID`(Basic settingsページのChannel ID。Webhookのdestination形式チェックに使う)
   - `GEMINI_API_KEY`
3. `clasp push` した後、既存のWeb Appデプロイ(スクリプトプロパティ`TRACKING_BASE_URL`に
   設定済みのURL)を、LINE DevelopersコンソールのWebhook URLに設定して有効化する
   (新しいWeb Appデプロイは不要。`doGet`と`doPost`は同一デプロイのURLを共有する)
4. `ensureLedgerTabs`を再実行し、「音声ログ処理状況」タブと「スタッフ」タブの
   「LINE User ID」列を反映する
5. スタッフが最初にLINE公式アカウントへ音声を送ると「担当者が特定できませんでした」と
   返信される。その時点の実行ログ(Apps Scriptエディタの「実行数」画面)からLINEユーザー
   IDを確認し、「スタッフ」タブの該当行の「LINE User ID」列へ手動で転記する
6. `installVoiceLogProcessingTrigger`を1度だけ実行し、1分間隔の処理トリガーを登録する

**注意事項:**
- Apps ScriptのWeb App(`doPost`)はHTTPヘッダーを読み取れないため、LINEの署名
  (`X-Line-Signature`)による暗号学的な検証は実装していない。Webhook URL自体の
  推測困難性と、リクエスト本文の`destination`フィールドの形式チェックのみで防御する
  (既存のTrackingWebApp.gsの`doGet`が「全員」アクセス可でURL自体が唯一の防御である
  設計と同水準のリスク受容)
- 1人につき同時に1件のみ処理中とする。前の音声ログが確定・破棄されるまで、次の音声は
  受け付けても処理が進まず「前の記録が完了していません」と案内される
- 個人情報の自動マスキングは行わない(社内CRMとして正しく企業情報を記録することが
  目的のため)
- 新規企業として登録する場合、企業マスタには企業ID・会社名のみが書き込まれる。他の項目は
  従来どおり手動で編集フローから補完すること
- LINE公式アカウントの新規開設・Gemini APIの利用料など、新たに発生する費用の契約・予算は
  小柳さんの決裁事項(CLAUDE.md絶対ルール5)
```

- [ ] **Step 2: 本番投入前チェックリストに動作確認項目を追加する**

`glow-ma/README.md`の「本番投入(実データ運用開始)前チェックリスト」セクションに、以下の1行を追加する(既存の3項目の末尾、`- [ ] ブレインストーミング論点4...`の直後):

```markdown
- [ ] 現場訪問ログLINE音声記録機能(2026-08-17)の実機動作確認(LINE公式アカウントでの
      音声送信→Gemini文字起こし→ボタン確認→対応履歴ログへの反映まで、実際のLINEアプリで
      一連の流れを確認する)
```

- [ ] **Step 3: 全体テスト実行**

Run: `node --test tests/*.mjs`
Expected: 全件PASS

- [ ] **Step 4: Commit**

```bash
git add glow-ma/README.md
git commit -m "docs(glow-ma): 現場訪問ログLINE音声記録のセットアップ・使い方を追記"
```
