import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const shareDialog = require("../glow-ma/src/shareDialog.js");

test("buildStaffSelectionHtml: スタッフが0人なら登録を促す文言のみでチェックボックスを出さない", () => {
  const html = shareDialog.buildStaffSelectionHtml("テスト商事株式会社", "C000001", []);
  assert.match(html, /登録されていません/);
  assert.doesNotMatch(html, /<input type="checkbox"/);
});

test("buildStaffSelectionHtml: スタッフごとにチェックボックス(value=Slack User ID)を1つずつ出す", () => {
  const staffList = [
    { name: "たかし", slackUserId: "U0001" },
    { name: "嶺井さん", slackUserId: "U0002" }
  ];
  const html = shareDialog.buildStaffSelectionHtml("テスト商事株式会社", "C000001", staffList);
  assert.match(html, /<input type="checkbox" value="U0001">たかし/);
  assert.match(html, /<input type="checkbox" value="U0002">嶺井さん/);
});

test("buildStaffSelectionHtml: 会社名・スタッフ名のHTML特殊文字をエスケープする", () => {
  const staffList = [{ name: "<script>alert(1)</script>", slackUserId: "U0001" }];
  const html = shareDialog.buildStaffSelectionHtml("テスト<b>商事</b>&会社", "C000001", staffList);
  assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/);
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.match(html, /テスト&lt;b&gt;商事&lt;\/b&gt;&amp;会社/);
});

test("buildStaffSelectionHtml: companyIdをJSでエスケープした形でscript内に埋め込む", () => {
  const html = shareDialog.buildStaffSelectionHtml("テスト商事株式会社", "C000001", [{ name: "たかし", slackUserId: "U0001" }]);
  assert.match(html, /var COMPANY_ID = "C000001";/);
});

test("buildStaffSelectionHtml: google.script.run経由でshareCompanyWithStaffを呼ぶ呼び出しを含む", () => {
  const html = shareDialog.buildStaffSelectionHtml("テスト商事株式会社", "C000001", [{ name: "たかし", slackUserId: "U0001" }]);
  assert.match(html, /google\.script\.run/);
  assert.match(html, /\.shareCompanyWithStaff\(COMPANY_ID, ids, note\)/);
});

test("buildStaffSelectionHtml: 外部リソース(フォント・CDN等)を読み込まない", () => {
  const html = shareDialog.buildStaffSelectionHtml("テスト商事株式会社", "C000001", [{ name: "たかし", slackUserId: "U0001" }]);
  assert.doesNotMatch(html, /<link/i);
  assert.doesNotMatch(html, /fonts\.googleapis|cdn\./i);
});
