/* GLOW企業リレーション台帳 BlueBean CTI通話履歴 取得結果の整形・突合ロジック
 * ブラウザ相当のGAS(global.GlowCtiContent)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_ctiContent.test.mjs で検証される。
 *
 * 電話番号での企業マスタ突合には glow-ma/src/dedupe.js の GlowDedupe.normalizePhoneNumber を
 * そのまま利用し、正規化ロジックを重複定義しない。GASのファイル読み込み順序に依存しないよう、
 * モジュール読み込み時ではなく関数呼び出し時に遅延解決する(dashboard.js と同じパターン)。
 *
 * 対応履歴ログへの自動記録範囲は docs/議事_20260819_BlueBean CTI連携.md の裁定に従う:
 * 「電話番号が企業マスタと一意にマッチ」かつ「通話ステータスが完了」の場合のみ自動記録する。
 * call_type=0(内線)は取得対象外。それ以外(未マッチ・キャンセル等)はCTI通話履歴タブに
 * 記録は残すが、対応履歴ログへは書き込まず人間のレビュー対象とする。
 */
(function (global) {
  "use strict";

  function getGlowDedupe_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./dedupe.js");
    }
    return global.GlowDedupe;
  }

  var CALL_TYPE_INTERNAL = "0";
  var CALL_TYPE_INBOUND = "1";
  var CALL_TYPE_OUTBOUND_PV = "2";
  var CALL_TYPE_OUTBOUND_PD = "3";
  var COMPLETED_CALL_STATUS = "完了";

  /**
   * BlueBeanのcall_type(0内線/1着信/2PV発信/3PD発信、数値または文字列で渡り得る)を
   * 対応履歴ログの「種別」プルダウン値に変換する。内線(0)や未知の値はnullを返し、
   * 呼び出し元が取得・記録の対象外として扱う。
   */
  function mapCallTypeToInteractionType(callType) {
    var value = String(callType);
    if (value === CALL_TYPE_OUTBOUND_PV || value === CALL_TYPE_OUTBOUND_PD) return "電話";
    if (value === CALL_TYPE_INBOUND) return "入電";
    return null;
  }

  /**
   * BlueBean APIのレスポンス({"result":"OK","data":[{"master":{...},"calls":[...]}]})から、
   * 内線(call_type=0)を除いた通話(calls)エントリだけを1次元配列に展開する。
   * result が "OK" 以外、または data が無い場合は空配列を返す。
   */
  function flattenBlueBeanCalls(apiResponse) {
    if (!apiResponse || apiResponse.result !== "OK") return [];
    var data = apiResponse.data || [];
    var calls = [];
    data.forEach(function (entry) {
      (entry.calls || []).forEach(function (call) {
        if (String(call.call_type) === CALL_TYPE_INTERNAL) return;
        calls.push(call);
      });
    });
    return calls;
  }

  /**
   * 電話番号(BlueBeanの通話ログのphone)を企業マスタと突合する。
   * 「電話番号」「携帯番号」いずれかが一致する企業を対象とするが、正規化後の番号で
   * 複数企業がヒットする場合(代表電話の共用等)は誤記載を避けるため意図的にnullを返す
   * (docs/議事_20260819_BlueBean CTI連携.md ベッカイ案の採用箇所)。
   */
  function matchCompanyByPhone(companies, phone) {
    var normalizePhoneNumber = getGlowDedupe_().normalizePhoneNumber;
    var target = normalizePhoneNumber(phone);
    if (!target) return null;
    var matches = (companies || []).filter(function (company) {
      return (
        (company["電話番号"] && normalizePhoneNumber(company["電話番号"]) === target) ||
        (company["携帯番号"] && normalizePhoneNumber(company["携帯番号"]) === target)
      );
    });
    return matches.length === 1 ? matches[0] : null;
  }

  /**
   * 対応履歴ログへ自動記録してよい通話かどうかを判定する。
   * 一意マッチ かつ 通話ステータスが完了 かつ 取得対象の種別(内線以外)であることが条件。
   */
  function shouldRecordInteractionLog(call, matchedCompany) {
    if (!matchedCompany) return false;
    if (call.call_status !== COMPLETED_CALL_STATUS) return false;
    return mapCallTypeToInteractionType(call.call_type) !== null;
  }

  /**
   * CTI通話履歴タブへ書き込む1行分の配列を、CTI_CALL_LOG_HEADERSの並び順で組み立てる。
   * callLogIdはGAS側で "CTI-" + group_callid のように衝突しない値を渡すこと(この関数は
   * ID生成の責務を持たない)。
   */
  function buildCallLogRow(callLogId, call, matchedCompany) {
    var recorded = shouldRecordInteractionLog(call, matchedCompany);
    return [
      callLogId,
      call.group_callid,
      call.start_date,
      mapCallTypeToInteractionType(call.call_type) || "対象外",
      call.phone,
      matchedCompany ? matchedCompany["企業ID"] : "",
      matchedCompany ? matchedCompany["会社名"] : "",
      call.operator_name || "",
      call.call_status || "",
      call.note || "",
      recorded ? "記録済み" : "未記録"
    ];
  }

  /**
   * 対応履歴ログへ書き込む1行分の配列を、INTERACTION_LOG_HEADERSの並び順で組み立てる。
   * shouldRecordInteractionLog が false の通話に対して呼ぶとnullを返す(自動記録対象外)。
   * logIdはGAS側でUtilities.getUuid()を使って生成し、"H-"を付けて渡すこと。
   */
  function buildInteractionLogRowForCall(logId, call, matchedCompany) {
    if (!shouldRecordInteractionLog(call, matchedCompany)) return null;
    var dateOnly = String(call.start_date || "").split(" ")[0];
    var memo = "CTI自動記録(BlueBean、担当: " + (call.operator_name || "不明") + ")" +
      (call.note ? ": " + call.note : "");
    return [
      logId, matchedCompany["企業ID"], dateOnly, "システム(CTI自動記録)",
      mapCallTypeToInteractionType(call.call_type), "未接触",
      memo, ""
    ];
  }

  var api = {
    mapCallTypeToInteractionType: mapCallTypeToInteractionType,
    flattenBlueBeanCalls: flattenBlueBeanCalls,
    matchCompanyByPhone: matchCompanyByPhone,
    shouldRecordInteractionLog: shouldRecordInteractionLog,
    buildCallLogRow: buildCallLogRow,
    buildInteractionLogRowForCall: buildInteractionLogRowForCall
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowCtiContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
