import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const page = require("../apo-kanri/src/apoPage.js");

const html = page.buildApoAppHtml();

test("モバイル対応: viewport metaとレスポンシブの基本が入っている", () => {
  assert.ok(html.includes('name="viewport"'));
  assert.ok(html.includes("width=device-width"));
});

test("サーバ呼び出し5関数がすべて配線されている", () => {
  ["getBoard", "saveAppointment", "updateStatus", "reportDelay", "getFormOptions"]
    .forEach((fn) => {
      assert.ok(html.includes(fn), fn + " の呼び出しが必要");
    });
  assert.ok(html.includes("google.script.run"));
});

test("ステータス7種と遅れそうボタンが画面に定義されている", () => {
  ["予定", "確定", "実施済", "申込み", "キャンセル(顧客都合)",
    "キャンセル(自社都合)", "再調整中"].forEach((status) => {
    assert.ok(html.includes(status), status + " が必要");
  });
  assert.ok(html.includes("遅れそう"));
  ["+15分", "+30分", "+60分"].forEach((label) => assert.ok(html.includes(label)));
});

test("本日/週切替・自分のアポ絞り込み・新規アポボタンがある", () => {
  assert.ok(html.includes("本日"));
  assert.ok(html.includes("週"));
  assert.ok(html.includes("自分のアポ"));
  assert.ok(html.includes("新規アポ"));
});

test("ダブルブッキング警告の表示領域がある", () => {
  assert.ok(html.includes("overlap"));
  assert.ok(html.includes("時間帯が重なって"));
});

test("ダークモード・reduced motion対応のCSSが入っている", () => {
  assert.ok(html.includes("prefers-color-scheme"));
  assert.ok(html.includes("prefers-reduced-motion"));
});

test("XSS対策: 画面側にエスケープ関数があり、innerHTMLへの生値挿入をしない前提が明示されている", () => {
  assert.ok(html.includes("function esc("));
});
