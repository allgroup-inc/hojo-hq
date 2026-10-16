/* GLOW企業リレーション台帳 法人番号バックフィル 候補選定ロジック
 * ブラウザ相当のGAS(global.GlowCorporateNumberBackfill)とNode(module.exports)の
 * 両方で動くUMD形式。Node側は tests/glow_ma_corporateNumberBackfill.test.mjs で検証される。
 *
 * 背景(❸事業構成&ゆんたく 2026-08-26連携メモ「1. 法人番号バッチ」への対応):
 * 実データ3,210社を集計すると、会社名が完全同一の企業が18件、法人格を除くと同名の企業が
 * 93件、実在する(例:「有限会社比嘉組」が沖縄に実在で3社)。国税庁法人番号API(名称検索)に
 * 会社名だけを投げると複数ヒットし、どれが台帳のどの企業IDかはAPIの応答だけでは判定できない。
 * ここで機械的に「1件目を採用」等をすると、別会社に同じ法人番号を書き込み、
 * GlowDedupe.findDuplicateGroups が「別会社を統合すべき重複」と誤認する事故になりうる
 * (CLAUDE.md絶対ルール1「不明時は要確認・断定しない」に反する)。
 *
 * このファイルは「会社名(完全一致)→ 1件に絞れなければ所在地(市区町村レベル)で絞り込み」の
 * 判定ロジックのみを持つ、API呼び出しを含まない純粋関数群。実際の国税庁Web-API呼び出しと
 * この判定結果の書き込みは、別途 CorporateNumberRunner.gs(GAS専用、Node非対応)で行う。
 *
 * candidates の形は、API応答をどう解釈するかに依存させないため、呼び出し側(GAS Runner)で
 * 次の形に正規化してから渡すことを前提にする:
 *   { corporateNumber: "13桁の法人番号文字列", name: "法人名", address: "所在地(フル文字列)" }
 */
(function (global) {
  "use strict";

  // 全角スペース・半角スペースの表記ゆれを吸収したうえで完全一致判定するための正規化。
  // 法人格(株式会社/有限会社等)は意図的に取り除かない。取り除いた同名93件の集計は
  // 「リスクの大きさを示す統計」であり、判定キー自体を法人格抜きにすると、
  // 「株式会社共和」と「有限会社共和」のような別法人まで同一視してしまうため。
  function normalizeCompanyName_(name) {
    if (name === null || name === undefined) return "";
    return String(name).replace(/[\s　]+/g, "");
  }

  // 所在地の自由記述から市区町村レベルの文字列を抽出する(例: "沖縄県島尻郡八重瀬町字X" →
  // "島尻郡八重瀬町")。都道府県名を除去したうえで、市・区・町・村のいずれかで終わる
  // 最短の先頭部分を取り出す。抽出できない場合は null を返し、呼び出し側は
  // 「所在地では絞り込めない」ものとして扱う(断定しない)。
  function extractMunicipality(address) {
    if (!address) return null;
    var text = String(address).trim();
    if (!text) return null;
    var withoutPrefecture = text.replace(/^.{1,3}?[都道府県]/, "");
    var match = withoutPrefecture.match(/^.+?[市区町村]/);
    return match ? match[0] : null;
  }

  /**
   * 1社分の法人番号候補から、自動採用してよい候補を1件に絞れるか判定する。
   *
   * @param {Object} company - { "会社名": string, "所在地": string }
   * @param {Array}  candidates - [{ corporateNumber, name, address }, ...]
   *   (会社名の部分一致等でAPIから返ってきた候補一覧。呼び出し側で正規化済みのもの)
   * @return {Object} {
   *   status: "matched" | "ambiguous" | "no_candidate",
   *   corporateNumber: string|null,  // matched の場合のみ値が入る
   *   candidates: Array              // ambiguous/matched の判定に使った候補(要確認列表示用)
   * }
   */
  function selectCorporateNumberMatch(company, candidates) {
    candidates = candidates || [];
    var companyNameKey = normalizeCompanyName_(company && company["会社名"]);

    var exactNameMatches = candidates.filter(function (candidate) {
      return normalizeCompanyName_(candidate.name) === companyNameKey;
    });

    if (exactNameMatches.length === 0) {
      return { status: "no_candidate", corporateNumber: null, candidates: [] };
    }
    if (exactNameMatches.length === 1) {
      return {
        status: "matched",
        corporateNumber: exactNameMatches[0].corporateNumber,
        candidates: exactNameMatches
      };
    }

    var companyMunicipality = extractMunicipality(company && company["所在地"]);
    if (companyMunicipality) {
      var municipalityMatches = exactNameMatches.filter(function (candidate) {
        return extractMunicipality(candidate.address) === companyMunicipality;
      });
      if (municipalityMatches.length === 1) {
        return {
          status: "matched",
          corporateNumber: municipalityMatches[0].corporateNumber,
          candidates: municipalityMatches
        };
      }
    }

    // 所在地でも1件に絞れない(0件・複数件どちらの場合も)は、誤った断定を避けるため
    // 「要確認」として人間の判断に回す。会社名一致の候補全件を残し、レビューできるようにする。
    return { status: "ambiguous", corporateNumber: null, candidates: exactNameMatches };
  }

  var api = {
    normalizeCompanyName_: normalizeCompanyName_,
    extractMunicipality: extractMunicipality,
    selectCorporateNumberMatch: selectCorporateNumberMatch
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowCorporateNumberBackfill = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
