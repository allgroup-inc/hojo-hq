/* GLOW企業リレーション台帳 法人番号による名寄せロジック
 * ブラウザ相当のGAS(global.GlowDedupe)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_dedupe.test.mjs で検証される。
 */
(function (global) {
  "use strict";

  function normalizeCorporateNumber(raw) {
    if (raw === null || raw === undefined) return null;
    var digits = String(raw).replace(/[^0-9]/g, "");
    if (digits.length !== 13) return null;
    return digits;
  }

  var api = {
    normalizeCorporateNumber: normalizeCorporateNumber
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowDedupe = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
