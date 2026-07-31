/* GLOW企業リレーション台帳 レター文面組み立て・ナーチャリング対象選定ロジック
 * ブラウザ相当のGAS(global.GlowLetterContent)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_letterContent.test.mjs で検証される。
 *
 * daysBetween は glow-ma/src/alerting.js の GlowAlerting をそのまま利用し、
 * 日付計算ロジックをこのファイルで重複定義しない。
 */
(function (global) {
  "use strict";

  var GlowAlerting = (typeof module !== "undefined" && module.exports)
    ? require("./alerting.js")
    : global.GlowAlerting;

  var DEFAULT_CONFIG = {
    referralRoute: "①紹介",
    leadProductForReferral: "M&A",
    leadProductDefault: "法人保険・経営相談"
  };

  function determineLeadProduct(record, config) {
    config = config || DEFAULT_CONFIG;
    var routes = record["流入ルート"] || [];
    if (routes.indexOf(config.referralRoute) !== -1) {
      return config.leadProductForReferral;
    }
    return config.leadProductDefault;
  }

  function buildTrackingUrl(companyId, baseUrl) {
    if (!companyId || !baseUrl) return "";
    var separator = baseUrl.indexOf("?") === -1 ? "?" : "&";
    return baseUrl + separator + "id=" + encodeURIComponent(companyId);
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    determineLeadProduct: determineLeadProduct,
    buildTrackingUrl: buildTrackingUrl
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowLetterContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
