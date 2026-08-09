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
