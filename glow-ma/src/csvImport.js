/* GLOW企業リレーション台帳 CSV行→企業マスタレコード変換
 * ブラウザ相当のGAS(global.GlowCsvImport)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_csv_import.test.mjs で検証される。
 */
(function (global) {
  "use strict";

  function buildCompanyId(sequenceNumber) {
    return "C" + String(sequenceNumber).padStart(6, "0");
  }

  function parseCompanyCsvRow(headerRow, dataRow, columnMap, sequenceNumber, todayString) {
    var record = {
      企業ID: buildCompanyId(sequenceNumber),
      法人番号: "", 会社名: "", 業種: "", 規模: "", 代表者名: "", 代表者年齢: "", 所在地: "",
      流入ルート: ["②手紙DM"],
      起点担当者_紹介元: "", 現在ステージ: "未接触", 提案商品: [],
      初期スコア: "", 反応スコア: "", 総合スコア: "", ランク: "",
      最終接触日: "", 次回アクション予定日: "", 次回アクション内容: "",
      担当者: "", 登録日: todayString, 備考: ""
    };

    Object.keys(columnMap).forEach(function (targetField) {
      var sourceHeader = columnMap[targetField];
      var columnIndex = headerRow.indexOf(sourceHeader);
      if (columnIndex === -1) return;
      var value = dataRow[columnIndex];
      record[targetField] = value === undefined || value === null ? "" : String(value);
    });

    return record;
  }

  var api = {
    buildCompanyId: buildCompanyId,
    parseCompanyCsvRow: parseCompanyCsvRow
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowCsvImport = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
