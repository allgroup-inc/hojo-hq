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

test("連続登録: 「保存して続けて登録」ボタンがあり、save(true)に配線されている", () => {
  assert.ok(html.includes("保存して続けて登録"));
  assert.ok(html.includes("modalSaveNext"));
  assert.ok(html.includes("save(true)"));
  assert.ok(html.includes("save(false)"));
  assert.ok(html.includes("続けて登録できます"), "保存後にフォームが開いたままの案内");
});

test("ホーム画面追加: apple-touch-icon(PNG)とアプリ名が設定されている", () => {
  assert.ok(html.includes('rel="apple-touch-icon"'));
  assert.ok(html.includes("data:image/png;base64,"));
  assert.ok(html.includes('name="apple-mobile-web-app-title"'));
});

test("色ルール: ブランド色#F6C83Eと文字#1A1A1A/#6B6B6B、ロゴ画像が入っている", () => {
  assert.ok(html.includes("--brand:#F6C83E"));
  assert.ok(html.includes("#1A1A1A"));
  assert.ok(html.includes("#6B6B6B"));
  assert.ok(html.includes("data:image/svg+xml;base64,"));
  assert.ok(html.includes('alt="家計の見直しやさん"'));
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

test("0件表示: 絞り込み中の0件と、本当に予定なしを区別する", () => {
  assert.ok(html.includes("絞り込み中"));
  assert.ok(html.includes("絞り込みを解除すると全員分が見られます"));
  assert.ok(html.includes("本日のアポはありません"));
});

test("ダブルブッキング警告の表示領域がある", () => {
  assert.ok(html.includes("overlap"));
  assert.ok(html.includes("時間帯が重なって"));
});

test("v2設計方針: 900px中央固定・グラデーション全廃・部分ローディング・reduced motion", () => {
  assert.ok(html.includes("max-width:900px"));
  assert.ok(!html.includes("linear-gradient"), "グラデーションは禁止");
  assert.ok(html.includes("dim"), "読み込み中は部分薄表示");
  assert.ok(html.includes("prefers-reduced-motion"));
});

test("v2フォーム(Stripe式): 必須タグ・ラベル上置き・エラー欄下・44px・フォーカスはブランド色のみ", () => {
  assert.ok(html.includes(">必須<"));
  assert.ok(!html.includes("※"), "※印は使わない");
  assert.ok(html.includes("min-height:44px"));
  assert.ok(html.includes("顧客名を入力してください。"));
  assert.ok(html.includes(":focus"));
  assert.ok(html.includes("border-color:var(--brand)"));
});

test("XSS対策: 画面側にエスケープ関数があり、innerHTMLへの生値挿入をしない前提が明示されている", () => {
  assert.ok(html.includes("function esc("));
});
