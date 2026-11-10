/* フクギイロ 計測ラッパー(プロバイダ非依存)
 * 設計: docs/フクギイロ_計測レポート設計.md / 比較・審査: docs/フクギイロ_計測ツール比較.md
 * GA4切替: 2026-08-24 小柳さん決裁(Plausible 402ロックのため)。議事: docs/議事_20260824_計測GA4切替.md
 * - window.FG_ANALYTICS が未設定なら何もしない(外部送信ゼロ)
 * - provider "ga4" でも measurementId が空なら何もしない(外部送信ゼロ)
 * - 送るのはイベント名と件数のみ。回答内容・個人識別子は送らない
 */
(function () {
  "use strict";
  var cfg = window.FG_ANALYTICS;
  var queue = [];

  function noop() {}

  /* 自動巡回(おもてなし総点検・Lighthouse等の自動ブラウザ)は計測しない。
   * 2026-09-04: GA4に9/1の総点検分とみられる山が混ざり実訪問と区別できなくなったため。
   * navigator.webdriver は自動操縦ブラウザで true になる標準フラグ(実利用者では false) */
  if (typeof navigator !== "undefined" && navigator.webdriver) {
    window.fgTrack = noop;
    return;
  }
  window.fgTrack = function (name, props) { queue.push([name, props]); };

  /* 画面の版の印(2026-11-09 小柳さん承認・診断改善の第1段階)。
   * 各ページが window.FG_VERSIONS = {top_v|ui_v|support_v: 数} を持ち、すべての計測に自動で添える。
   * 既存の計測の名前と意味は変えない。トップを通った人は、同じタブの間 top_v を他のページの計測にも添える
   * (入口の変化を、診断などの数字から切り分けるため)。送るのは版の数字だけ(個人を見分ける情報は送らない)。 */
  function versions() {
    var src = window.FG_VERSIONS || {}, v = {}, k;
    for (k in src) { if (Object.prototype.hasOwnProperty.call(src, k)) v[k] = src[k]; }
    try {
      if (src.top_v != null) window.sessionStorage.setItem("fg_top_v", String(src.top_v));
      else {
        var t = window.sessionStorage.getItem("fg_top_v");
        if (t && /^[0-9]+$/.test(t)) v.top_v = Number(t);
      }
    } catch (e) {}
    return v;
  }
  function withVersions(props) {
    var out = {}, k, v = versions();
    if (props) { for (k in props) { if (Object.prototype.hasOwnProperty.call(props, k)) out[k] = props[k]; } }
    for (k in v) out[k] = v[k];
    return out;
  }

  function flush() {
    for (var i = 0; i < queue.length; i++) window.fgTrack(queue[i][0], queue[i][1]);
    queue = [];
  }

  if (!cfg || !cfg.provider) {
    window.fgTrack = noop;
    return;
  }

  if (cfg.provider === "ga4" && cfg.measurementId) {
    var g = document.createElement("script");
    g.async = true;
    g.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(cfg.measurementId);
    document.head.appendChild(g);
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
    window.gtag("js", new Date());
    /* beacon送信でページ遷移をまたいでも計測が残る。IPは仕様上そのまま保存されない(GA4既定) */
    window.gtag("config", cfg.measurementId, { transport_type: "beacon" });
    window.fgTrack = function (name, props) {
      try { window.gtag("event", name, withVersions(props)); } catch (e) {}
    };
    flush();
  } else if (cfg.provider === "plausible") {
    var s = document.createElement("script");
    s.defer = true;
    s.setAttribute("data-domain", cfg.domain);
    s.src = "https://plausible.io/js/script.manual.js";
    document.head.appendChild(s);
    window.plausible = window.plausible || function () {
      (window.plausible.q = window.plausible.q || []).push(arguments);
    };
    window.plausible("pageview");
    window.fgTrack = function (name, props) {
      try { window.plausible(name, { props: withVersions(props) }); } catch (e) {}
    };
    flush();
  } else {
    window.fgTrack = noop;
  }
})();
