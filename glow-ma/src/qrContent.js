/* GLOW企業リレーション台帳 レター発送 個別QRコード生成対象の抽出ロジック
 * ブラウザ相当のGAS(global.GlowQrContent)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_qrContent.test.mjs で検証される。
 *
 * 発送日ベースの絞り込みは glow-ma/src/shippingContent.js の buildShippingCsvRows と
 * 同じ考え方(発送日一致・企業マスタとの突合)だが、出力の形(QR生成対象一覧)が異なるため
 * 独立した実装として持つ(将来的な共通化は本ファイルのスコープ外)。
 *
 * 日付パースは glow-ma/src/alerting.js の GlowAlerting.toDate を、トラッキングURLの組み立ては
 * glow-ma/src/letterContent.js の GlowLetterContent.buildTrackingUrl をそのまま利用し、
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

  function getGlowLetterContent_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./letterContent.js");
    }
    return global.GlowLetterContent;
  }

  function formatDate_(date) {
    var year = date.getFullYear();
    var month = String(date.getMonth() + 1).padStart(2, "0");
    var day = String(date.getDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
  }

  function buildQrManifestRows(letterDrafts, companies, targetDate, baseUrl) {
    var glowAlerting = getGlowAlerting_();
    var glowLetterContent = getGlowLetterContent_();
    var companyById = {};
    (companies || []).forEach(function (company) {
      companyById[company["企業ID"]] = company;
    });

    var rows = [];
    (letterDrafts || []).forEach(function (draft) {
      var sentDateValue = draft["発送日"];
      if (!sentDateValue) return;
      var sentDate = glowAlerting.toDate(sentDateValue);
      if (!sentDate) return;
      if (formatDate_(sentDate) !== targetDate) return;
      var company = companyById[draft["企業ID"]];
      if (!company) return;
      var trackingUrl = glowLetterContent.buildTrackingUrl(draft["企業ID"], baseUrl);
      if (!trackingUrl) return;
      rows.push({
        "企業ID": draft["企業ID"],
        "会社名": company["会社名"] || "",
        trackingUrl: trackingUrl
      });
    });
    return rows;
  }

  var api = {
    buildQrManifestRows: buildQrManifestRows
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowQrContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
