import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const schema = require("../apo-kanri/src/schema.js");

test("4タブすべてのシート名とヘッダー定義が存在する", () => {
  assert.equal(schema.STAFF_SHEET_NAME, "スタッフ");
  assert.equal(schema.APPOINTMENT_SHEET_NAME, "アポ予定");
  assert.equal(schema.HISTORY_SHEET_NAME, "変更履歴");
  assert.equal(schema.SETTINGS_SHEET_NAME, "設定");
  [
    schema.STAFF_HEADERS,
    schema.APPOINTMENT_HEADERS,
    schema.HISTORY_HEADERS,
    schema.SETTINGS_HEADERS
  ].forEach((headers) => {
    assert.ok(Array.isArray(headers));
    assert.ok(headers.length > 0);
  });
});

test("各タブのヘッダーに重複列名がない", () => {
  [
    schema.STAFF_HEADERS,
    schema.APPOINTMENT_HEADERS,
    schema.HISTORY_HEADERS,
    schema.SETTINGS_HEADERS
  ].forEach((headers) => {
    assert.equal(new Set(headers).size, headers.length);
  });
});

test("アポ予定はアポIDが先頭列で、必須列がそろっている", () => {
  assert.equal(schema.APPOINTMENT_HEADERS[0], "アポID");
  ["日付", "開始時刻", "所要分", "顧客名", "形式", "場所またはURL",
    "担当営業", "アポ入れ担当", "温度感", "ステータス", "メモ",
    "登録日時", "最終更新日時"].forEach((name) => {
    assert.ok(schema.APPOINTMENT_HEADERS.includes(name), name + " が必要");
  });
});

test("ステータスは軸の共通語彙どおり5種(言い換えない)", () => {
  assert.deepEqual(schema.APPOINTMENT_STATUSES, [
    "スケジュール調整中", "アポ確定", "訪問済", "申込", "差し戻し"
  ]);
});

test("差し戻し理由は2種(旧キャンセル2種をステータスから理由列へ移した)", () => {
  assert.deepEqual(schema.CANCEL_REASONS, ["顧客都合", "自社都合"]);
});

test("顧客IDと差し戻し理由が列の末尾にある(途中挿入は既存データを壊す)", () => {
  const h = schema.APPOINTMENT_HEADERS;
  assert.deepEqual(h.slice(-2), ["顧客ID", "差し戻し理由"]);
});

test("スタッフの役割・形式・温度感・履歴操作の選択肢が定義されている", () => {
  assert.deepEqual(schema.STAFF_ROLES, ["アポ入れ", "営業", "両方"]);
  assert.deepEqual(schema.APPOINTMENT_FORMATS, ["訪問", "来店", "オンライン"]);
  assert.deepEqual(schema.TEMPERATURES, ["高", "中", "低"]);
  assert.deepEqual(schema.HISTORY_OPERATIONS, ["新規", "変更", "遅延連絡"]);
});

test("スタッフタブに役割列とメールアドレス列がある(認証と選択肢生成に必須)", () => {
  assert.ok(schema.STAFF_HEADERS.includes("役割"));
  assert.ok(schema.STAFF_HEADERS.includes("メールアドレス"));
  assert.ok(schema.STAFF_HEADERS.includes("Slack User ID"));
});
