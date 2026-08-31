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

  var RESPONDENT_REVIEW_MARK = "【対応相手 要確認】";

  /**
   * 対応相手が判別できなかった場合に、内容メモの先頭へ目印を付ける。
   *
   * 対応履歴ログの「対応相手」列は RESPONDENT_TYPES の3値しか取れず(プルダウンと
   * スコアリングがこの3値を前提にしている)、buildInteractionLogRow が
   * normalizeRespondentType で既定値「経理・総務等の窓口担当」に丸める。
   * そのため「判別できなかった」という事実が台帳のどこにも残らず、
   * オーナー社長本人と話せていても decisionMakerBonus(+15点)が付かないまま
   * 埋もれる。内容メモに目印を残せば、台帳を「要確認」で検索するだけで
   * 訂正対象を拾える。
   *
   * 列を増やさないため既存データ・ダッシュボード集計には影響しない。
   */
  function markMemoIfRespondentUncertain(contentMemo, rawRespondent) {
    var memo = String(contentMemo == null ? "" : contentMemo);
    if (!isRespondentUncertain(rawRespondent)) return memo;
    if (memo.indexOf(RESPONDENT_REVIEW_MARK) === 0) return memo;
    return memo ? RESPONDENT_REVIEW_MARK + " " + memo : RESPONDENT_REVIEW_MARK;
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

  /**
   * 未登録の担当者へ返す案内。LINE User IDを本文に含めて、本人が管理者へ
   * そのまま転送するだけで登録が済むようにする。
   *
   * 背景: LINE User IDは公式アカウントの管理画面から一覧取得できないため、
   * 従来は一時デバッグ用のスクリプトプロパティ(LAST_LINE_USER_ID)から人間が
   * 転記していた。その暫定コードは2026-08-22に削除され(コミット433fee372)、
   * 以後は新しい担当者を登録する手段が存在しない状態だった。実行ログを掘る運用に
   * 戻すのではなく、本人に見せて転送してもらう方が早く、確実に届く。
   * 自分自身のIDを本人に返すだけなので、他人の情報は漏れない。
   */
  function buildStaffNotFoundMessage(lineUserId) {
    var base = "担当者が特定できませんでした。管理者に「スタッフ」タブへの登録を依頼してください。";
    if (!lineUserId) return base;
    return base + "\n\n----------\nこのメッセージをそのまま管理者に転送してください。\nLINE User ID: " + lineUserId;
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

  // 音声から拾う「興味あり商品」の許可リスト。企業マスタ「提案商品」の値と揃える
  var INTERESTED_PRODUCT_TYPES_ = ["M&A", "不動産", "法人保険"];
  var MEMO_MAX_LENGTH_ = 6000;
  var MEMO_TRUNCATE_SUFFIX_ = "\n…(古いメモは省略)";

  /**
   * Gemini抽出結果のうち見込みシグナル(後継者状況・興味商品・次回予定日)を
   * 検証済みの値に正規化する。不正・不明な値は空にする(決めつけ禁止。
   * CLAUDE.md絶対ルール1「不明時は断定しない」をここでも適用する)。
   */
  function normalizeProspectSignals(parsed) {
    var source = parsed || {};
    var schema = getGlowSchema_();
    var successor = String(source.successorStatus || "").trim();
    if (schema.SUCCESSOR_STATUS_TYPES.indexOf(successor) === -1) successor = "";
    var products = Array.isArray(source.interestedProducts) ? source.interestedProducts : [];
    var seen = {};
    products = products
      .map(function (product) { return String(product || "").trim(); })
      .filter(function (product) {
        if (INTERESTED_PRODUCT_TYPES_.indexOf(product) === -1) return false;
        if (seen[product]) return false;
        seen[product] = true;
        return true;
      });
    var nextDate = String(source.nextActionDate || "").trim();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(nextDate)) nextDate = "";
    return { successorStatus: successor, interestedProducts: products, nextActionDate: nextDate };
  }

  /**
   * 音声ログの確定時に企業マスタへ反映する更新セット {列名: 新値} を組み立てる。
   * recordは音声ログ行(種別候補・内容メモ・次回アクション・後継者状況候補・
   * 興味商品候補・次回予定日候補)、companyは企業マスタの現レコード。
   *
   * - 最終接触日は常に当日へ更新(ログ確定=接触があった事実)
   * - 関係メモは「【日付 種別(LINE音声)】要約 ▶次: …」を先頭に追記して蓄積する
   *   (見込みコメント。上限6000文字で古い側から省略)
   * - 後継者状況は「あり/なし」のときだけ、現在値と異なる場合に更新
   *   (「不明」で既知の値を上書きしない)
   * - 提案商品は既存とマージし、新しい関心があったときだけ更新
   * - 変わらない項目はupdatesに含めない(シート書き込みを最小にする)
   */
  function buildProspectUpdates(record, company, todayString) {
    var source = record || {};
    var target = company || {};
    var updates = {};
    updates["最終接触日"] = todayString;

    var nextDate = String(source["次回予定日候補"] || "").trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(nextDate)) {
      updates["次回アクション予定日"] = nextDate;
    }
    var nextAction = String(source["次回アクション"] || "").trim();
    if (nextAction) {
      updates["次回アクション内容"] = nextAction;
    }

    var successor = String(source["後継者状況候補"] || "").trim();
    if ((successor === "あり" || successor === "なし") && successor !== String(target["後継者状況"] || "").trim()) {
      updates["後継者状況"] = successor;
    }

    var existingProducts = target["提案商品"];
    if (!Array.isArray(existingProducts)) {
      existingProducts = existingProducts ? String(existingProducts).split("、") : [];
    }
    var merged = existingProducts.slice();
    String(source["興味商品候補"] || "").split("、").forEach(function (product) {
      var trimmed = product.trim();
      if (!trimmed) return;
      if (INTERESTED_PRODUCT_TYPES_.indexOf(trimmed) === -1) return;
      if (merged.indexOf(trimmed) !== -1) return;
      merged.push(trimmed);
    });
    if (merged.length > existingProducts.length) {
      updates["提案商品"] = merged.join("、");
    }

    var contentMemo = String(source["内容メモ"] || "").trim();
    if (contentMemo) {
      var digest = "【" + todayString + " " + (String(source["種別候補"] || "").trim() || "対応") + "(LINE音声)】" +
        contentMemo + (nextAction ? " ▶次: " + nextAction : "");
      var existingMemo = String(target["関係メモ"] || "");
      var combined = existingMemo ? digest + "\n" + existingMemo : digest;
      if (combined.length > MEMO_MAX_LENGTH_) {
        combined = combined.slice(0, MEMO_MAX_LENGTH_ - MEMO_TRUNCATE_SUFFIX_.length) + MEMO_TRUNCATE_SUFFIX_;
      }
      updates["関係メモ"] = combined;
    }
    return { updates: updates };
  }

  /**
   * 確定後にLINEへ返す「台帳へ何を反映したか」の1通。担当者がその場で
   * 反映結果を確認でき、誤反映(日付の聞き間違い等)にすぐ気づける。
   */
  function buildProspectUpdateSummaryMessage(updates) {
    var source = updates || {};
    var parts = [];
    if (source["最終接触日"]) parts.push("最終接触日: " + source["最終接触日"]);
    if (source["次回アクション予定日"]) parts.push("次回予定: " + source["次回アクション予定日"]);
    if (source["次回アクション内容"]) parts.push("次回内容: " + source["次回アクション内容"]);
    if (source["関係メモ"]) parts.push("関係メモに要約を追記");
    if (source["後継者状況"]) parts.push("後継者状況: " + source["後継者状況"]);
    if (source["提案商品"]) parts.push("興味あり商品: " + source["提案商品"]);
    return "台帳にも反映しました:\n・" + parts.join("\n・");
  }

  var api = {
    matchCompanyCandidates: matchCompanyCandidates,
    normalizeInteractionType: normalizeInteractionType,
    normalizeRespondentType: normalizeRespondentType,
    isRespondentUncertain: isRespondentUncertain,
    markMemoIfRespondentUncertain: markMemoIfRespondentUncertain,
    RESPONDENT_REVIEW_MARK: RESPONDENT_REVIEW_MARK,
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
    buildAlreadyHandledMessage: buildAlreadyHandledMessage,
    normalizeProspectSignals: normalizeProspectSignals,
    buildProspectUpdates: buildProspectUpdates,
    buildProspectUpdateSummaryMessage: buildProspectUpdateSummaryMessage
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowLineVoiceLogContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
