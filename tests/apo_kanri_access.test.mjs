import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const access = require("../apo-kanri/src/apoAccess.js");

const STAFF = [
  { email: "eigyo1@example.com", name: "営業一郎", role: "営業", slackUserId: "U001" },
  { email: "Apo1@Example.com", name: "アポ花子", role: "アポ入れ", slackUserId: "U002" },
  { email: "ryoho@example.com", name: "両方次郎", role: "両方", slackUserId: "" }
];

test("isAllowedEmail: 大文字小文字・前後空白を無視して照合する", () => {
  assert.equal(access.isAllowedEmail("EIGYO1@example.com", STAFF), true);
  assert.equal(access.isAllowedEmail("  apo1@example.com  ", STAFF), true);
  assert.equal(access.isAllowedEmail("unknown@example.com", STAFF), false);
});

test("isAllowedEmail: 空メール・空リストは拒否する", () => {
  assert.equal(access.isAllowedEmail("", STAFF), false);
  assert.equal(access.isAllowedEmail(null, STAFF), false);
  assert.equal(access.isAllowedEmail("eigyo1@example.com", []), false);
  assert.equal(access.isAllowedEmail("eigyo1@example.com", null), false);
});

test("resolveStaffName: 登録者は氏名、未登録は「不明」", () => {
  assert.equal(access.resolveStaffName("apo1@example.com", STAFF), "アポ花子");
  assert.equal(access.resolveStaffName("unknown@example.com", STAFF), "不明");
});

test("listSalesStaff: 役割が営業・両方の氏名だけを返す", () => {
  assert.deepEqual(access.listSalesStaff(STAFF), ["営業一郎", "両方次郎"]);
});

test("listSetterStaff: 役割がアポ入れ・両方の氏名だけを返す", () => {
  assert.deepEqual(access.listSetterStaff(STAFF), ["アポ花子", "両方次郎"]);
});

test("役割絞り込み: 空・null入力で空配列を返す", () => {
  assert.deepEqual(access.listSalesStaff([]), []);
  assert.deepEqual(access.listSalesStaff(null), []);
  assert.deepEqual(access.listSetterStaff(null), []);
});

test("buildAccessDeniedHtml: 拒否ページに案内文が含まれる", () => {
  const html = access.buildAccessDeniedHtml();
  assert.ok(html.includes("アクセス権がありません"));
  assert.ok(html.includes("<!doctype html>"));
});

test("findStaffByName: 氏名からSlack User ID付きでスタッフを引ける", () => {
  assert.deepEqual(access.findStaffByName("アポ花子", STAFF), STAFF[1]);
  assert.equal(access.findStaffByName("いない人", STAFF), null);
});
