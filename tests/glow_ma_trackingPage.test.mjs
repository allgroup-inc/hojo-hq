import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const trackingPage = require("../glow-ma/src/trackingPage.js");

test("buildRedirectHtml: JS自動遷移とJS無効時の代替ボタンの両方を含む", () => {
  const html = trackingPage.buildRedirectHtml("https://example.com/next");
  assert.match(html, /window\.top\.location\.href = "https:\/\/example\.com\/next";/);
  assert.match(html, /<a class="btn" target="_top" href="https:\/\/example\.com\/next">/);
});

test("buildRedirectHtml: URLの二重引用符・特殊文字をHTML属性内で正しくエスケープする", () => {
  const html = trackingPage.buildRedirectHtml('https://example.com/next?a=1&b="x"<y>');
  assert.match(html, /href="https:\/\/example\.com\/next\?a=1&amp;b=&quot;x&quot;&lt;y&gt;"/);
  // JS側(script内)はJSON.stringifyで別途エスケープされるため元の文字列のまま安全に埋め込まれる
  assert.match(html, /window\.top\.location\.href = "https:\/\/example\.com\/next\?a=1&b=\\"x\\"<y>";/);
});

test("buildRedirectHtml: meta refreshを使わない(iframeサンドボックスでは機能しないため)", () => {
  const html = trackingPage.buildRedirectHtml("https://example.com/next");
  assert.doesNotMatch(html, /http-equiv="refresh"/i);
});

test("buildNotFoundHtml: 設定不備を示す簡潔な文言を返す", () => {
  const html = trackingPage.buildNotFoundHtml();
  assert.match(html, /ページを表示できませんでした/);
  assert.doesNotMatch(html, /window\.top\.location/);
});

test("両方のページとも外部リソース(フォント・CDN等)を読み込まない", () => {
  [trackingPage.buildRedirectHtml("https://example.com/x"), trackingPage.buildNotFoundHtml()].forEach((html) => {
    assert.doesNotMatch(html, /<link/i);
    assert.doesNotMatch(html, /fonts\.googleapis|cdn\./i);
  });
});
