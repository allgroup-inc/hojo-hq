/* GLOW企業リレーション台帳: 現場訪問ログLINE音声記録 対象抽出・データ整形ロジック
 * ブラウザ相当のGAS(global.GlowLineVoiceLogContent)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_lineVoiceLogContent.test.mjs で検証される。
 */
(function (global) {
  "use strict";

  function getGlowSchema_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./schema.js");
    }
    return global.GlowSchema;
  }

  var DEFAULT_INTERACTION_TYPE = "面談実施";
  var DEFAULT_RESPONDENT_TYPE = "経理・総務等の窓口担当";
  var MAX_COMPANY_CANDIDATES = 5;

  /**
   * 音声から抽出した会社名(spokenName)を企業マスタと照合し、候補を最大5件返す。
   * 完全一致(スコア2)を部分一致(スコア1、どちらかがどちらかを含む)より優先する。
   * spokenNameが空、または一致する企業が無い場合は空配列を返す(新規企業扱いの判定は
   * 呼び出し元がこの空配列を見て行う)。
   */
  function matchCompanyCandidates(companies, spokenName) {
    var trimmed = String(spokenName || "").trim();
    if (!trimmed) return [];
    var scored = (companies || [])
      .map(function (company) {
        var name = company["会社名"] || "";
        var score = 0;
        if (name && name === trimmed) {
          score = 2;
        } else if (name && (name.indexOf(trimmed) !== -1 || trimmed.indexOf(name) !== -1)) {
          score = 1;
        }
        return { company: company, score: score };
      })
      .filter(function (entry) { return entry.score > 0; })
      .sort(function (a, b) { return b.score - a.score; });
    return scored.slice(0, MAX_COMPANY_CANDIDATES).map(function (entry) {
      return { "企業ID": entry.company["企業ID"], "会社名": entry.company["会社名"] };
    });
  }

  /**
   * Geminiが返した種別候補を、対応履歴ログの「種別」プルダウンで許容される値に正規化する。
   * 一致しない場合は既定値(面談実施)にフォールバックする(表記ゆれで集計から漏れないため)。
   */
  function normalizeInteractionType(candidateType) {
    var glowSchema = getGlowSchema_();
    if (glowSchema.INTERACTION_TYPES.indexOf(candidateType) !== -1) return candidateType;
    return DEFAULT_INTERACTION_TYPE;
  }

  /**
   * Geminiが返した対応相手候補を、対応履歴ログの「対応相手」プルダウンで許容される値に
   * 正規化する。一致しない場合は既定値(経理・総務等の窓口担当)にフォールバックする。
   */
  function normalizeRespondentType(candidateRespondent) {
    var glowSchema = getGlowSchema_();
    if (glowSchema.RESPONDENT_TYPES.indexOf(candidateRespondent) !== -1) return candidateRespondent;
    return DEFAULT_RESPONDENT_TYPE;
  }

  /**
   * 対応履歴ログへ書き込む1行分の配列を、INTERACTION_LOG_HEADERSの並び順で組み立てる。
   * logIdはGAS側でUtilities.getUuid()を使って生成し、"H-"を付けて渡すこと(Node側では
   * UUID生成手段がないため、この関数はID生成の責務を持たない)。
   */
  function buildInteractionLogRow(logId, companyId, todayString, staffName, interactionType, respondentType, contentMemo, nextAction) {
    return [
      logId, companyId, todayString, staffName,
      normalizeInteractionType(interactionType),
      normalizeRespondentType(respondentType),
      contentMemo || "", nextAction || ""
    ];
  }

  /**
   * 企業マスタへ新規企業として追加する1行分の配列を、COMPANY_MASTER_HEADERSの並び順で
   * 組み立てる。企業ID・会社名以外は空欄とする(設計書4章のとおり、詳細は後で通常の
   * 編集フローで補完する)。「連絡不要」列はチェックボックス列のため空文字ではなくfalseにする。
   */
  function buildNewCompanyRow(companyId, companyName) {
    var glowSchema = getGlowSchema_();
    var headers = glowSchema.COMPANY_MASTER_HEADERS;
    var dncIndex = headers.indexOf("連絡不要");
    var idIndex = headers.indexOf("企業ID");
    var nameIndex = headers.indexOf("会社名");
    return headers.map(function (header, index) {
      if (index === idIndex) return companyId;
      if (index === nameIndex) return companyName;
      if (index === dncIndex) return false;
      return "";
    });
  }

  var api = {
    matchCompanyCandidates: matchCompanyCandidates,
    normalizeInteractionType: normalizeInteractionType,
    normalizeRespondentType: normalizeRespondentType,
    buildInteractionLogRow: buildInteractionLogRow,
    buildNewCompanyRow: buildNewCompanyRow
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowLineVoiceLogContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
