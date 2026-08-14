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

test("サーバ呼び出し6関数がすべて配線されている", () => {
  ["getBoard", "saveAppointment", "updateStatus", "reportDelay", "getFormOptions", "getStats"]
    .forEach((fn) => {
      assert.ok(html.includes(fn), fn + " の呼び出しが必要");
    });
  assert.ok(html.includes("google.script.run"));
});

test("分析タブ: 埋まり状況・転換ファネル・評価非利用の注記・少件数の参考値注記がある", () => {
  assert.ok(html.includes("分析"));
  assert.ok(html.includes("埋まり状況"));
  assert.ok(html.includes("転換ファネル"));
  assert.ok(html.includes("評価目的では使いません"));
  assert.ok(html.includes("件数が少ないため参考値"));
});

test("分析タブ: 温度感別の申込み率パネルがある(母数併記・参考値注記)", () => {
  assert.ok(html.includes("温度感別の申込み率"));
  assert.ok(html.includes("byTemperature"));
  assert.ok(html.includes("母数10件未満の行は参考値"));
});

test("家計のポっ: システム名(正式表記=小さいひらがな『っ』)とブランド表記・ロゴ枠がある", () => {
  assert.ok(html.includes("<title>家計のポっ</title>"));
  assert.ok(html.includes("家計の<span>ポっ</span>"));
  assert.ok(html.includes("家計の見直しやさん アポ管理"));
  assert.ok(html.includes("logomark") || html.includes("logoimg"));
});

test("家計の見直しやさんカラー(仮): グラデーション変数と暖色パレットが定義されている", () => {
  assert.ok(html.includes("--grad:linear-gradient"));
  assert.ok(html.includes("--pop1:#2E8B57"));
  assert.ok(html.includes("--pop6:#F57C00"));
  assert.ok(html.includes("正式な色コード受領後はこの2行だけ差し替える"));
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
