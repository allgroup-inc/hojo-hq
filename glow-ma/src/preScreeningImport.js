/* GLOW企業リレーション台帳 事前選定スコア・ランクの取り込みロジック(会社名の正規化・突き合わせ)
 * ブラウザ相当のGAS(global.GlowPreScreeningImport)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_pre_screening_import.test.mjs で検証される。
 *
 * 設計書: docs/superpowers/specs/2026-08-11-glow-ma-pre-screening-score-import-design.md
 */
(function (global) {
  "use strict";

  var FULLWIDTH_ALNUM_START = 0xFF10; // 全角"0"
  var FULLWIDTH_ALNUM_END = 0xFF5A;   // 全角"z"

  /**
   * 会社名を正規化する: 前後の空白除去、文中の半角・全角スペース除去、
   * 全角英数字(0-9, A-Z, a-z相当)を半角に変換する。
   * あいまい一致(表記ゆれ吸収)は行わない(設計書1章、スコープ外)。
   */
  function normalizeCompanyName(name) {
    var text = String(name || "").trim();
    text = text.replace(/[\s　]/g, "");
    text = text.replace(/[０-９Ａ-Ｚａ-ｚ]/g, function (ch) {
      var code = ch.charCodeAt(0);
      if (code < FULLWIDTH_ALNUM_START || code > FULLWIDTH_ALNUM_END) return ch;
      return String.fromCharCode(code - 0xFEE0);
    });
    return text;
  }

  /**
   * 事前選定リストの各行を、企業マスタの会社名(正規化して比較)と突き合わせる。
   * 一致したものはmatches、一致しなかったものはunmatchedNames(元の会社名、正規化前)に振り分ける。
   */
  function matchPreScreeningRows(stagingRows, companyRecords) {
    var companyIdByNormalizedName = {};
    (companyRecords || []).forEach(function (record) {
      var normalized = normalizeCompanyName(record["会社名"]);
      if (normalized) companyIdByNormalizedName[normalized] = record["企業ID"];
    });

    var matches = [];
    var unmatchedNames = [];
    (stagingRows || []).forEach(function (row) {
      var normalized = normalizeCompanyName(row["会社名"]);
      var companyId = companyIdByNormalizedName[normalized];
      if (companyId) {
        matches.push({
          "企業ID": companyId,
          "事前選定ランク": row["事前選定ランク"],
          "事前選定スコア": row["事前選定スコア"]
        });
      } else {
        unmatchedNames.push(row["会社名"]);
      }
    });

    return { matches: matches, unmatchedNames: unmatchedNames };
  }

  /**
   * 企業マスタのレコード配列に、matchesの内容(事前選定ランク・事前選定スコア)を反映した
   * 新しい配列を返す。入力配列・要素は変更しない。一致しなかった企業のレコードはそのまま返す。
   */
  function applyMatchesToCompanyRecords(companyRecords, matches) {
    var matchByCompanyId = {};
    (matches || []).forEach(function (match) {
      matchByCompanyId[match["企業ID"]] = match;
    });
    return (companyRecords || []).map(function (record) {
      var match = matchByCompanyId[record["企業ID"]];
      if (!match) return record;
      var updated = {};
      Object.keys(record).forEach(function (key) {
        updated[key] = record[key];
      });
      updated["事前選定ランク"] = match["事前選定ランク"];
      updated["事前選定スコア"] = match["事前選定スコア"];
      return updated;
    });
  }

  var api = {
    normalizeCompanyName: normalizeCompanyName,
    matchPreScreeningRows: matchPreScreeningRows,
    applyMatchesToCompanyRecords: applyMatchesToCompanyRecords
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowPreScreeningImport = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
