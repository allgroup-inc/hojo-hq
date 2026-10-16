/* GLOW企業リレーション台帳 レターURLアクセス時に表示する中継ページのHTML組み立て
 * ブラウザ相当のGAS(global.GlowTrackingPage)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_trackingPage.test.mjs で検証される。
 *
 * 設計方針(taste-skill / 2026-08-07):
 * このページは手紙を受け取った企業側の担当者が一瞬だけ目にする中継画面であり、
 * 訪問して回遊する着地ページではない。そのため作り込んだマーケティングページではなく、
 * 「壊れていない・怪しくない」と一目で伝わる、静かで簡潔な画面にする(テンプレ感のある
 * 紫系グラデーションのヒーローや絵文字は使わない)。外部フォント・CDNには依存せず、
 * OS標準フォント(日本語対応)のみで完結させる。
 *
 * GASのHtmlServiceはサンドボックス化されたiframe内で出力を描画するため、
 * <meta http-equiv="refresh"> はこのiframeしか遷移させず訪問者のブラウザ全体は
 * 遷移しない(TrackingWebApp.gsの元コメント参照)。そのため自動遷移は
 * window.top.location.href のみに頼り、JSが無効な場合の代替として
 * 目に見えるリンクボタンを必ず用意する(meta refreshでは代替にならない)。
 */
(function (global) {
  "use strict";

  function escapeHtmlAttribute(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  var BASE_STYLE = [
    "*{box-sizing:border-box}",
    "body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;",
    "background:#f7f7f5;color:#1f2933;",
    "font-family:-apple-system,BlinkMacSystemFont,\"Hiragino Sans\",\"Hiragino Kaku Gothic ProN\",\"Noto Sans JP\",Meiryo,sans-serif}",
    ".card{max-width:22rem;padding:2.5rem 2rem;text-align:center}",
    ".spinner{width:2rem;height:2rem;margin:0 auto 1.25rem;border-radius:50%;",
    "border:3px solid #d8dbe0;border-top-color:#33475b;animation:spin 0.8s linear infinite}",
    "@keyframes spin{to{transform:rotate(360deg)}}",
    "@media (prefers-reduced-motion: reduce){.spinner{animation:none}}",
    "p{margin:0 0 0.5rem;font-size:0.95rem;line-height:1.7}",
    ".muted{color:#5c6773;font-size:0.85rem}",
    ".btn{display:inline-block;margin-top:1rem;padding:0.6rem 1.5rem;border-radius:0.4rem;",
    "background:#33475b;color:#fff;text-decoration:none;font-size:0.9rem}",
    "@media (prefers-color-scheme: dark){",
    "body{background:#15181c;color:#e4e7eb}",
    ".spinner{border-color:#3a3f47;border-top-color:#7c93ac}",
    ".muted{color:#9aa4b1}",
    ".btn{background:#7c93ac;color:#0e1013}",
    "}"
  ].join("");

  /**
   * 正常系: redirectUrl(TRACKING_REDIRECT_URL)へ自動遷移しつつ、
   * JS無効時の代替として明示的なボタンリンクを表示するページ。
   */
  function buildRedirectHtml(redirectUrl) {
    var safeUrl = escapeHtmlAttribute(redirectUrl);
    var jsUrl = JSON.stringify(String(redirectUrl));
    return "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">" +
      "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" +
      "<title>ご案内 - 株式会社GLOW</title><style>" + BASE_STYLE + "</style></head>" +
      "<body><div class=\"card\">" +
      "<div class=\"spinner\" role=\"status\" aria-label=\"読み込み中\"></div>" +
      "<p>ご案内ページに移動しています。</p>" +
      "<p class=\"muted\">自動で切り替わらない場合は、下のボタンからお進みください。</p>" +
      "<a class=\"btn\" target=\"_top\" href=\"" + safeUrl + "\">ページへ進む</a>" +
      "</div>" +
      "<script>window.top.location.href = " + jsUrl + ";</script>" +
      "</body></html>";
  }

  /**
   * 異常系: TRACKING_REDIRECT_URL が未設定の場合に表示するページ。
   * 設定不備であり訪問者側の問題ではないため、不安を煽らない簡潔な文言にする。
   */
  function buildNotFoundHtml() {
    return "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">" +
      "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" +
      "<title>ご案内 - 株式会社GLOW</title><style>" + BASE_STYLE + "</style></head>" +
      "<body><div class=\"card\">" +
      "<p>ページを表示できませんでした。</p>" +
      "<p class=\"muted\">お手数ですが、お送りしたお手紙記載のお電話番号までご連絡ください。</p>" +
      "</div></body></html>";
  }

  var api = {
    buildRedirectHtml: buildRedirectHtml,
    buildNotFoundHtml: buildNotFoundHtml
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowTrackingPage = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
