/* GLOW企業リレーション台帳 レター発送日の記録・発送業者連携用CSV出力ロジック
 * ブラウザ相当のGAS(global.GlowShippingContent)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_shippingContent.test.mjs で検証される。
 *
 * 日付パースは glow-ma/src/alerting.js の GlowAlerting.toDate をそのまま利用し、
 * このファイルで重複定義しない。
 */
(function (global) {
  "use strict";

  function getGlowAlerting_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./alerting.js");
    }
    return global.GlowAlerting;
  }

  var DEFAULT_CONFIG = {
    followUpDays: 10,
    followUpAction: "手紙フォロー架電"
  };

  function formatDate_(date) {
    var year = date.getFullYear();
    var month = String(date.getMonth() + 1).padStart(2, "0");
    var day = String(date.getDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
  }

  function computeFollowUpDate(sentDateValue, days) {
    var date = getGlowAlerting_().toDate(sentDateValue);
    if (!date) return null;
    var result = new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
    return formatDate_(result);
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    computeFollowUpDate: computeFollowUpDate
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowShippingContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
