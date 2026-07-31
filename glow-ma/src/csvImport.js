/* GLOW企業リレーション台帳 CSV行→企業マスタレコード変換
 * ブラウザ相当のGAS(global.GlowCsvImport)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_csv_import.test.mjs で検証される。
 */
(function (global) {
  "use strict";

  function buildCompanyId(sequenceNumber) {
    return "C" + String(sequenceNumber).padStart(6, "0");
  }

  var api = {
    buildCompanyId: buildCompanyId
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowCsvImport = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
