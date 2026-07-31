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

  function buildLetterPrompt(record, trackingUrl, config) {
    config = config || DEFAULT_CONFIG;
    var leadProduct = determineLeadProduct(record, config);
    var lines = [
      "あなたは沖縄の中小企業向けM&A・不動産・法人保険を扱う株式会社GLOWの営業担当です。",
      "以下の企業宛てに送る手紙の文面を、丁寧で押しつけがましくない経営相談ベースのトーンで下書きしてください。",
      "",
      "企業名: " + (record["会社名"] || ""),
      "業種: " + (record["業種"] || "不明"),
      "最初にご案内する内容: " + leadProduct,
      "",
      "条件:",
      "- 「売り込み」ではなく「無料の経営相談・情報提供」という体裁にすること",
      "- いきなりM&Aの話から入らないこと(紹介ルートの場合を除く)",
      "- 文末に次のURLへの案内を自然に含めること: " + (trackingUrl || ""),
      "- 断定的な成果保証をしないこと",
      "",
      "300〜500字程度の手紙文面のみを出力してください。"
    ];
    return lines.join("\n");
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    determineLeadProduct: determineLeadProduct,
    buildTrackingUrl: buildTrackingUrl,
    buildLetterPrompt: buildLetterPrompt
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowLetterContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
