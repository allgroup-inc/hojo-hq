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
  window.fgTrack = function (name, props) { queue.push([name, props]); };

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
      try { window.gtag("event", name, props || {}); } catch (e) {}
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
      try { window.plausible(name, props ? { props: props } : undefined); } catch (e) {}
    };
    flush();
  } else {
    window.fgTrack = noop;
  }
})();
