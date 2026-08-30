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

  var CSV_HEADER_ROW = ["発送日", "企業ID", "会社名", "所在地", "窓口担当者名"];

  function buildShippingCsvRows(letterDrafts, companies, targetDate) {
    var glowAlerting = getGlowAlerting_();
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
      rows.push([
        targetDate,
        draft["企業ID"],
        company["会社名"] || "",
        company["所在地"] || "",
        company["窓口担当者名"] || ""
      ]);
    });
    return [CSV_HEADER_ROW].concat(rows);
  }

  /**
   * 管理画面の企業一覧でチェックした企業ID一覧から、make_qr_cards.py入力用のCSV行を作る。
   * 「発送日でCSV出力」(buildShippingCsvRows)と違い、レター下書きの発送日記録を経由せず、
   * 選んだ企業をそのままCSV化する(まとめて印刷したい企業を都度選ぶ運用のため)。
   * targetDateは印刷物の管理用に付与するラベルであり、実際の発送記録(レター下書きの
   * 発送日列)には影響しない。
   */
  function buildRowsForCompanyIds(companies, companyIds, targetDate) {
    var companyById = {};
    (companies || []).forEach(function (company) {
      companyById[company["企業ID"]] = company;
    });
    var rows = (companyIds || [])
      .map(function (id) { return companyById[id]; })
      .filter(Boolean)
      .map(function (company) {
        return [
          targetDate,
          company["企業ID"],
          company["会社名"] || "",
          company["所在地"] || "",
          company["窓口担当者名"] || ""
        ];
      });
    return [CSV_HEADER_ROW].concat(rows);
  }

  function escapeCsvField_(value) {
    var stringValue = value === null || value === undefined ? "" : String(value);
    if (/[",\r\n]/.test(stringValue)) {
      return "\"" + stringValue.replace(/"/g, "\"\"") + "\"";
    }
    return stringValue;
  }

  function toCsvString(rows) {
    return (rows || []).map(function (row) {
      return row.map(escapeCsvField_).join(",");
    }).join("\r\n");
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    computeFollowUpDate: computeFollowUpDate,
    buildShippingCsvRows: buildShippingCsvRows,
    buildRowsForCompanyIds: buildRowsForCompanyIds,
    toCsvString: toCsvString
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowShippingContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
