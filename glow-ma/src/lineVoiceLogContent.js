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

  var RESPONDENT_UNCERTAIN_VALUE = "不明";

  /**
   * Geminiが対応相手を「不明」(音声だけではオーナー社長本人か窓口担当か判別できない)と
   * 返したかどうかを判定する。「対応相手」は反応スコアに直結する項目(オーナー社長本人は
   * +15点)のため、判定が曖昧なまま既定値へ静かにフォールバックさせず、最終確認メッセージで
   * 人に注意喚起する(2026-08-26 ❸事業構成&ゆんたくからの指摘。実例: 録音だけでは
   * 社長本人か窓口担当か判別しきれないケースがある)。
   */
  function isRespondentUncertain(candidateRespondent) {
    return candidateRespondent === RESPONDENT_UNCERTAIN_VALUE;
  }

  var FORMULA_PREFIX_PATTERN = /^[=+\-@]/;

  /**
   * スプレッドシートのセルに書き込む自由記述テキストを無害化する。
   * Googleスプレッドシートは "=" "+" "-" "@" で始まる値を数式として解釈するため、
   * 文字起こし結果や会社名がそのまま数式になって内容が壊れる(あるいは意図しない
   * 参照が入る)ことを防ぐ。該当する場合のみ先頭にアポストロフィを付けて文字列扱いにする。
   * 既にサニタイズ済みの値("'"始まり)を再度通しても何も起きない(冪等)。
   */
  function sanitizeSheetText(value) {
    if (value === null || value === undefined) return "";
    var text = String(value);
    if (FORMULA_PREFIX_PATTERN.test(text)) return "'" + text;
    return text;
  }

  /**
   * 対応履歴ログへ書き込む1行分の配列を、INTERACTION_LOG_HEADERSの並び順で組み立てる。
   * logIdはGAS側でUtilities.getUuid()を使って生成し、"H-"を付けて渡すこと(Node側では
   * UUID生成手段がないため、この関数はID生成の責務を持たない)。
   * 自由記述の内容メモ・次回アクションは数式として解釈されないようサニタイズする。
   */
  function buildInteractionLogRow(logId, companyId, todayString, staffName, interactionType, respondentType, contentMemo, nextAction) {
    return [
      logId, companyId, todayString, staffName,
      normalizeInteractionType(interactionType),
      normalizeRespondentType(respondentType),
      sanitizeSheetText(contentMemo), sanitizeSheetText(nextAction)
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
      if (index === nameIndex) return sanitizeSheetText(companyName);
      if (index === dncIndex) return false;
      return "";
    });
  }

  var ACK_MESSAGE_TEXT = "録音、届きました。少々お待ちください。";
  var MAX_LABEL_LENGTH = 20;

  var POSTBACK_ACTIONS = {
    SELECT_COMPANY: "selectCompany",
    NEW_COMPANY_CONFIRM: "newCompanyConfirm",
    FINAL_CONFIRM: "finalConfirm"
  };

  var NOT_FOUND_VALUE = "NOT_FOUND";
  var YES_VALUE = "YES";
  var NO_VALUE = "NO";
  var CONFIRM_VALUE = "CONFIRM";
  var DISCARD_VALUE = "DISCARD";

  function truncateLabel_(label) {
    var text = String(label || "");
    if (text.length <= MAX_LABEL_LENGTH) return text;
    return text.slice(0, MAX_LABEL_LENGTH - 1) + "…";
  }

  /**
   * buildPostbackDataで組み立てたdata文字列を{action, processId, value}に戻す。
   * 形式が壊れている場合は該当キーがundefinedのオブジェクトを返す(呼び出し元が
   * 必須キーの有無を見て不正なpostbackとして扱う)。
   */
  function parsePostbackData(dataString) {
    var result = {};
    String(dataString || "").split("&").forEach(function (pair) {
      var parts = pair.split("=");
      if (parts.length !== 2) return;
      result[decodeURIComponent(parts[0])] = decodeURIComponent(parts[1]);
    });
    return result;
  }

  /**
   * ボタン(postback)に埋め込むdata文字列を組み立てる。
   * 形式: "action=<action>&processId=<processId>&value=<value>"
   */
  function buildPostbackData(action, processId, value) {
    return "action=" + encodeURIComponent(action) +
      "&processId=" + encodeURIComponent(processId) +
      "&value=" + encodeURIComponent(value);
  }

  /**
   * 候補企業が複数ある場合の選択プロンプトを組み立てる(純粋なデータ構造。実際の
   * LINE Quick Reply JSON形式への変換はGAS側(LineVoiceLogRunner.gs)で行う)。
   */
  function buildCompanySelectionPrompt(processId, candidates) {
    var options = candidates.map(function (candidate) {
      return {
        label: truncateLabel_(candidate["会社名"]),
        data: buildPostbackData(POSTBACK_ACTIONS.SELECT_COMPANY, processId, candidate["企業ID"])
      };
    });
    options.push({
      label: "見つからない",
      data: buildPostbackData(POSTBACK_ACTIONS.SELECT_COMPANY, processId, NOT_FOUND_VALUE)
    });
    return {
      text: "話された会社名に近い企業が複数見つかりました。どの企業ですか?",
      options: options
    };
  }

  /**
   * 一致する企業が見つからなかった場合の、新規登録確認プロンプトを組み立てる。
   */
  function buildNewCompanyConfirmPrompt(processId, spokenName) {
    return {
      text: "「" + spokenName + "」は企業マスタに見つかりませんでした。新規企業として登録しますか?",
      options: [
        { label: "はい、登録する", data: buildPostbackData(POSTBACK_ACTIONS.NEW_COMPANY_CONFIRM, processId, YES_VALUE) },
        { label: "いいえ", data: buildPostbackData(POSTBACK_ACTIONS.NEW_COMPANY_CONFIRM, processId, NO_VALUE) }
      ]
    };
  }

  /**
   * 対応履歴ログへ書き込む直前の最終確認プロンプトを組み立てる。
   * 種別・対応相手は、buildInteractionLogRowが書き込み時に行うのと同じ正規化を
   * ここでも通す。正規化しないまま表示すると、担当者は「雑談」と表示された内容を
   * 確認したのに、実際には既定値の「面談実施」が記録される、という食い違いが起きる
   * (正確性最優先。CLAUDE.md絶対ルール1)。正規化は冪等なので二重適用しても問題ない。
   */
  function buildFinalConfirmPrompt(processId, companyName, interactionType, respondentType, contentMemo, nextAction) {
    var respondentLine = "対応相手: " + normalizeRespondentType(respondentType);
    if (isRespondentUncertain(respondentType)) {
      respondentLine += "(⚠️音声だけでは判定できませんでした。オーナー社長ご本人だった場合は" +
        "対応履歴ログのスコアに影響するため、確定後にスプレッドシートで訂正してください)";
    }
    var text = [
      "以下の内容で記録します。よろしいですか?",
      "会社名: " + companyName,
      "種別: " + normalizeInteractionType(interactionType),
      respondentLine,
      "内容メモ: " + contentMemo,
      "次回アクション: " + (nextAction || "(なし)")
    ].join("\n");
    return {
      text: text,
      options: [
        { label: "この内容で記録する", data: buildPostbackData(POSTBACK_ACTIONS.FINAL_CONFIRM, processId, CONFIRM_VALUE) },
        { label: "取り消す(録音し直す)", data: buildPostbackData(POSTBACK_ACTIONS.FINAL_CONFIRM, processId, DISCARD_VALUE) }
      ]
    };
  }

  function buildCompletionMessage(companyName) {
    return companyName + "の対応履歴として記録しました。";
  }

  function buildDiscardMessage() {
    return "取り消しました。もう一度録音してください。";
  }

  function buildProcessingErrorMessage() {
    return "うまく処理できませんでした。もう一度録音してください。";
  }

  function buildStaffNotFoundMessage() {
    return "担当者が特定できませんでした。管理者に「スタッフ」タブへの登録を依頼してください。";
  }

  function buildAlreadyProcessingMessage() {
    return "前の記録がまだ完了していません。LINE上のボタンで確定または取り消しをしてから、次の録音を送ってください。";
  }

  /**
   * 二重タップ・Webhookの再送などで、既に処理済み(または取り消し済み)の記録に対する
   * ボタン操作が届いたときの案内。重複書き込みを防いだうえで、無言にしないために返す。
   */
  function buildAlreadyHandledMessage() {
    return "この記録はすでに処理済みか、無効になっています。";
  }

  var api = {
    matchCompanyCandidates: matchCompanyCandidates,
    normalizeInteractionType: normalizeInteractionType,
    normalizeRespondentType: normalizeRespondentType,
    isRespondentUncertain: isRespondentUncertain,
    sanitizeSheetText: sanitizeSheetText,
    buildInteractionLogRow: buildInteractionLogRow,
    buildNewCompanyRow: buildNewCompanyRow,
    ACK_MESSAGE_TEXT: ACK_MESSAGE_TEXT,
    POSTBACK_ACTIONS: POSTBACK_ACTIONS,
    NOT_FOUND_VALUE: NOT_FOUND_VALUE,
    YES_VALUE: YES_VALUE,
    NO_VALUE: NO_VALUE,
    CONFIRM_VALUE: CONFIRM_VALUE,
    DISCARD_VALUE: DISCARD_VALUE,
    buildPostbackData: buildPostbackData,
    parsePostbackData: parsePostbackData,
    buildCompanySelectionPrompt: buildCompanySelectionPrompt,
    buildNewCompanyConfirmPrompt: buildNewCompanyConfirmPrompt,
    buildFinalConfirmPrompt: buildFinalConfirmPrompt,
    buildCompletionMessage: buildCompletionMessage,
    buildDiscardMessage: buildDiscardMessage,
    buildProcessingErrorMessage: buildProcessingErrorMessage,
    buildStaffNotFoundMessage: buildStaffNotFoundMessage,
    buildAlreadyProcessingMessage: buildAlreadyProcessingMessage,
    buildAlreadyHandledMessage: buildAlreadyHandledMessage
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowLineVoiceLogContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
