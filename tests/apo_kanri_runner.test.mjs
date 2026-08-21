/* ApoRunner.gs(GAS層)の統合テスト。
 * SpreadsheetApp等のGASグローバルをモックし、実物の ApoRunner.gs を vm で評価して
 * 「保存→変更履歴→Slack通知」のフロー全体を検証する。
 * 2026-08-17のレビューで「純ロジックのテスト全パスでもGAS層の結線バグは素通り」と
 * 判明したため追加(点検記録: docs/家計のポっ_スキル点検_2026-08-17.md)。
 */
import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const require = createRequire(import.meta.url);
const ApoSchema = require("../apo-kanri/src/schema.js");
const ApoCore = require("../apo-kanri/src/apoCore.js");
const ApoNotify = require("../apo-kanri/src/apoNotify.js");
const ApoAccess = require("../apo-kanri/src/apoAccess.js");
const ApoResilience = require("../apo-kanri/src/resilience.js");

const runnerSource = readFileSync(new URL("../apo-kanri/src/ApoRunner.gs", import.meta.url), "utf8");

class MockSheet {
  constructor(headers) {
    this.data = [headers.slice()];
  }
  getLastRow() { return this.data.length; }
  appendRow(row) { this.data.push(row.slice()); }
  getRange(row, col, numRows, numCols) {
    const sheet = this;
    return {
      getValues() {
        const out = [];
        for (let r = 0; r < numRows; r++) {
          const src = sheet.data[row - 1 + r] || [];
          const line = [];
          for (let c = 0; c < numCols; c++) line.push(src[col - 1 + c] ?? "");
          out.push(line);
        }
        return out;
      },
      setValues(values) {
        values.forEach((line, r) => {
          const target = sheet.data[row - 1 + r] || (sheet.data[row - 1 + r] = []);
          line.forEach((value, c) => { target[col - 1 + c] = value; });
        });
      }
    };
  }
}

function staffRow({ name, slackId = "", active = true, email, role }) {
  const row = [];
  row[ApoSchema.STAFF_HEADERS.indexOf("氏名")] = name;
  row[ApoSchema.STAFF_HEADERS.indexOf("Slack User ID")] = slackId;
  row[ApoSchema.STAFF_HEADERS.indexOf("有効")] = active;
  row[ApoSchema.STAFF_HEADERS.indexOf("メールアドレス")] = email;
  row[ApoSchema.STAFF_HEADERS.indexOf("役割")] = role;
  return row;
}

function apoRow(record) {
  return ApoSchema.APPOINTMENT_HEADERS.map((h) => record[h] ?? "");
}

function baseApo(overrides) {
  return Object.assign({
    "アポID": "APO-20260817-AAAA", "日付": "2026-08-17", "開始時刻": "10:00", "所要分": 60,
    "顧客名": "テスト商店", "形式": "訪問", "場所またはURL": "那覇市", "担当営業": "営業一郎",
    "アポ入れ担当": "アポ花子", "温度感": "高", "ステータス": "アポ確定", "メモ": "",
    "登録日時": "2026-08-16 09:00:00", "最終更新日時": "2026-08-16 09:00:00"
  }, overrides || {});
}

let env;
function buildEnv({ webhookUrl = "https://hooks.slack.example/x", activeEmail = "apo@example.com" } = {}) {
  const sheets = {
    [ApoSchema.STAFF_SHEET_NAME]: new MockSheet(ApoSchema.STAFF_HEADERS),
    [ApoSchema.APPOINTMENT_SHEET_NAME]: new MockSheet(ApoSchema.APPOINTMENT_HEADERS),
    [ApoSchema.HISTORY_SHEET_NAME]: new MockSheet(ApoSchema.HISTORY_HEADERS),
    [ApoSchema.SETTINGS_SHEET_NAME]: new MockSheet(ApoSchema.SETTINGS_HEADERS)
  };
  sheets[ApoSchema.STAFF_SHEET_NAME].appendRow(staffRow({ name: "アポ花子", email: "apo@example.com", role: "アポ入れ", slackId: "U002" }));
  sheets[ApoSchema.STAFF_SHEET_NAME].appendRow(staffRow({ name: "営業一郎", email: "eigyo1@example.com", role: "営業", slackId: "U001" }));
  sheets[ApoSchema.STAFF_SHEET_NAME].appendRow(staffRow({ name: "営業二郎", email: "eigyo2@example.com", role: "営業" }));

  const slackPosts = [];
  const context = {
    ApoSchema, ApoCore, ApoNotify, ApoAccess, ApoResilience,
    ApoPage: { buildApoAppHtml: () => "<html></html>" },
    SpreadsheetApp: { getActiveSpreadsheet: () => ({ getSheetByName: (name) => sheets[name] || null }) },
    Session: { getActiveUser: () => ({ getEmail: () => activeEmail }) },
    PropertiesService: { getScriptProperties: () => ({ getProperty: (key) => (key === "SLACK_WEBHOOK_URL" ? webhookUrl : null) }) },
    LockService: { getScriptLock: () => ({ tryLock: () => true, releaseLock: () => {} }) },
    Utilities: {
      sleep: () => {},
      formatDate(date, tz, pattern) {
        const p2 = (n) => String(n).padStart(2, "0");
        return pattern
          .replace("yyyy", date.getFullYear()).replace("MM", p2(date.getMonth() + 1))
          .replace("dd", p2(date.getDate())).replace("HH", p2(date.getHours()))
          .replace("mm", p2(date.getMinutes())).replace("ss", p2(date.getSeconds()));
      }
    },
    UrlFetchApp: { fetch: (url, opts) => { slackPosts.push(JSON.parse(opts.payload).text); return { getResponseCode: () => 200 }; } },
    Logger: { log: () => {} },
    HtmlService: { createHtmlOutput: (html) => ({ setTitle: function () { return this; }, addMetaTag: function () { return this; }, html }) }
  };
  vm.createContext(context);
  vm.runInContext(runnerSource, context);
  return { context, sheets, slackPosts };
}

beforeEach(() => { env = buildEnv(); });

test("新規保存: 行追加+履歴「新規」+担当営業メンション付きSlack通知+notified=true", () => {
  const result = env.context.saveAppointment(baseApo({ "アポID": null, confirmedOverlap: false }));
  assert.equal(result.ok, true);
  assert.equal(result.notified, true);
  assert.match(result.apoId, /^APO-/);
  assert.equal(env.sheets[ApoSchema.APPOINTMENT_SHEET_NAME].data.length, 2);
  const history = env.sheets[ApoSchema.HISTORY_SHEET_NAME].data;
  assert.equal(history[1][ApoSchema.HISTORY_HEADERS.indexOf("操作")], "新規");
  assert.equal(history[1][ApoSchema.HISTORY_HEADERS.indexOf("操作者")], "アポ花子");
  assert.equal(env.slackPosts.length, 1);
  assert.ok(env.slackPosts[0].includes("テスト商店"));
  assert.ok(env.slackPosts[0].includes("<@U001>"));
});

test("編集: 差分に内部フラグが漏れず、履歴「変更」とSlack変更通知が出る", () => {
  env.sheets[ApoSchema.APPOINTMENT_SHEET_NAME].appendRow(apoRow(baseApo()));
  const result = env.context.saveAppointment(baseApo({ "開始時刻": "14:00", confirmedOverlap: true }));
  assert.equal(result.ok, true);
  const detail = env.sheets[ApoSchema.HISTORY_SHEET_NAME].data[1][ApoSchema.HISTORY_HEADERS.indexOf("変更内容")];
  assert.ok(detail.includes("開始時刻: 10:00→14:00"));
  assert.ok(!detail.includes("confirmedOverlap"));
  assert.ok(!env.slackPosts[0].includes("confirmedOverlap"));
});

test("無変更の保存: 履歴もSlackも増えず notified=false", () => {
  env.sheets[ApoSchema.APPOINTMENT_SHEET_NAME].appendRow(apoRow(baseApo()));
  const result = env.context.saveAppointment(baseApo({ confirmedOverlap: true }));
  assert.equal(result.ok, true);
  assert.equal(result.notified, false);
  assert.equal(env.sheets[ApoSchema.HISTORY_SHEET_NAME].data.length, 1);
  assert.equal(env.slackPosts.length, 0);
});

test("ダブルブッキング: confirmedOverlapなしなら保存されず警告が返る", () => {
  env.sheets[ApoSchema.APPOINTMENT_SHEET_NAME].appendRow(apoRow(baseApo()));
  const result = env.context.saveAppointment(baseApo({ "アポID": null, "開始時刻": "10:30", "顧客名": "別件", confirmedOverlap: false }));
  assert.equal(result.ok, false);
  assert.equal(result.overlapWarning.length, 1);
  assert.equal(env.sheets[ApoSchema.APPOINTMENT_SHEET_NAME].data.length, 2, "行は増えない");
  assert.equal(env.slackPosts.length, 0);
});

test("キャンセル操作: 通知に代打候補(空いている営業)が付く", () => {
  env.sheets[ApoSchema.APPOINTMENT_SHEET_NAME].appendRow(apoRow(baseApo()));
  const result = env.context.updateStatus("APO-20260817-AAAA", "差し戻し");
  assert.equal(result.ok, true);
  assert.equal(env.slackPosts.length, 1);
  assert.ok(env.slackPosts[0].includes("差し戻し"));
  assert.ok(env.slackPosts[0].includes("代打候補"));
  assert.ok(env.slackPosts[0].includes("営業二郎"));
});

test("キャンセルからの復帰: 空いた枠が埋まっていたら重複警告で止まる(素通りしない)", () => {
  env.sheets[ApoSchema.APPOINTMENT_SHEET_NAME].appendRow(apoRow(baseApo({ "ステータス": "差し戻し" })));
  env.sheets[ApoSchema.APPOINTMENT_SHEET_NAME].appendRow(apoRow(baseApo({ "アポID": "APO-20260817-BBBB", "顧客名": "後から入れた件" })));
  const result = env.context.updateStatus("APO-20260817-AAAA", "アポ確定");
  assert.equal(result.ok, false);
  assert.ok(result.overlapWarning.length >= 1);
});

test("遅れそう: 遅れる人=そのアポの担当営業として通知し、当該アポ自身も対象に含む", () => {
  env.sheets[ApoSchema.APPOINTMENT_SHEET_NAME].appendRow(apoRow(baseApo()));
  env.sheets[ApoSchema.APPOINTMENT_SHEET_NAME].appendRow(apoRow(baseApo({ "アポID": "APO-20260817-CCCC", "開始時刻": "13:00", "顧客名": "後続商事" })));
  const result = env.context.reportDelay(30, "APO-20260817-AAAA");
  assert.equal(result.ok, true);
  assert.equal(result.targetCount, 2, "タップしたアポ自身+後続");
  assert.ok(env.slackPosts[0].includes("営業一郎さん +30分"), "操作者(アポ花子)ではなく担当営業に帰属する");
  assert.ok(env.slackPosts[0].includes("テスト商店"));
  assert.ok(env.slackPosts[0].includes("後続商事"));
});

test("Webhook未設定: 保存は成功するが notified=false(トーストが偽らないための実績フラグ)", () => {
  env = buildEnv({ webhookUrl: null });
  const result = env.context.saveAppointment(baseApo({ "アポID": null, confirmedOverlap: false }));
  assert.equal(result.ok, true);
  assert.equal(result.notified, false);
  assert.equal(env.slackPosts.length, 0);
});

test("未登録メールのアクセスは全公開関数で拒否される", () => {
  env = buildEnv({ activeEmail: "stranger@example.com" });
  assert.throws(() => env.context.getBoard({}), /権限/);
  assert.throws(() => env.context.saveAppointment(baseApo()), /権限/);
  assert.throws(() => env.context.reportDelay(15, null), /権限/);
});

test("getBoard: 本日ビューとスタッフ一覧・本人名が返る", () => {
  env.sheets[ApoSchema.APPOINTMENT_SHEET_NAME].appendRow(apoRow(baseApo()));
  const board = env.context.getBoard({ view: "day", date: "2026-08-17", owner: null });
  assert.equal(board.dayView.items.length, 1);
  assert.deepEqual(board.salesStaff, ["営業一郎", "営業二郎"]);
  assert.equal(board.meName, "アポ花子");
});
