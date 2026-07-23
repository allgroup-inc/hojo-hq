/* フクギイロ 計測ラッパー(プロバイダ非依存・Cookieなし)
 * 設計: docs/フクギイロ_計測レポート設計.md / 比較・審査: docs/フクギイロ_計測ツール比較.md
 * - window.FG_ANALYTICS が未設定なら何もしない(外部送信ゼロ)
 * - 送るのはイベント名と件数のみ。回答内容・個人識別子は送らない
 */
(function () {
  "use strict";
  var cfg = window.FG_ANALYTICS;
  var queue = [];

  function noop() {}
  window.fgTrack = function (name, props) { queue.push([name, props]); };

  if (!cfg || !cfg.provider) {
    window.fgTrack = noop;
    return;
  }

  if (cfg.provider === "plausible") {
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
    for (var i = 0; i < queue.length; i++) window.fgTrack(queue[i][0], queue[i][1]);
  } else {
    window.fgTrack = noop;
  }
})();
