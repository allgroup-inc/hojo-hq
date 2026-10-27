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
   * 企業マスタを「正規化した電話番号 → 企業の一覧」の索引にする(2026-10-27 追加)。
   * 通話1件ごとに3,000社の番号を正規化し直すと、30日分の取り込みが6分の上限を超えたため。
   */
  function buildPhoneIndex(companies) {
    var normalizePhoneNumber = getGlowDedupe_().normalizePhoneNumber;
    var index = {};
    (companies || []).forEach(function (company) {
      var seen = {};
      ["電話番号", "携帯番号"].forEach(function (key) {
        var n = company[key] ? normalizePhoneNumber(company[key]) : "";
        if (!n || seen[n]) return;
        seen[n] = true;
        (index[n] = index[n] || []).push(company);
      });
    });
    return index;
  }

  /** buildPhoneIndex の索引で突合する。結果は matchCompanyByPhone と同じ(複数企業ヒットは null) */
  function matchCompanyByPhoneIndex(index, phone) {
    var target = getGlowDedupe_().normalizePhoneNumber(phone);
    if (!target) return null;
    var hits = (index || {})[target] || [];
    return hits.length === 1 ? hits[0] : null;
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

  /** RFC4180 相当のCSVを2次元配列にする(引用符・改行入りの項目に対応。文字起こし・要約は改行を含みうる) */
  function parseCsv(text) {
    var rows = [], row = [], field = "", inQuotes = false;
    var s = String(text || "").replace(/^\uFEFF/, "");
    for (var i = 0; i < s.length; i++) {
      var c = s.charAt(i);
      if (inQuotes) {
        if (c === '"') {
          if (s.charAt(i + 1) === '"') { field += '"'; i++; } else { inQuotes = false; }
        } else {
          field += c;
        }
      } else if (c === '"') {
        inQuotes = true;
      } else if (c === ",") {
        row.push(field); field = "";
      } else if (c === "\n" || c === "\r") {
        if (c === "\r" && s.charAt(i + 1) === "\n") i++;
        row.push(field); field = "";
        if (row.length > 1 || row[0] !== "") rows.push(row);
        row = [];
      } else {
        field += c;
      }
    }
    if (field !== "" || row.length) { row.push(field); if (row.length > 1 || row[0] !== "") rows.push(row); }
    return rows;
  }

  function cdrCallType_(value) {
    var v = String(value || "").trim();
    if (/^[0-3]$/.test(v)) return v;
    if (/内線/.test(v)) return CALL_TYPE_INTERNAL;
    if (/着信/.test(v)) return CALL_TYPE_INBOUND;
    if (/PD/i.test(v)) return CALL_TYPE_OUTBOUND_PD;
    if (/PV|発信/i.test(v)) return CALL_TYPE_OUTBOUND_PV;
    return v;
  }

  function cdrCallStatus_(value) {
    var v = String(value || "").trim();
    if (/^SUCCESS$/i.test(v) || v === COMPLETED_CALL_STATUS) return COMPLETED_CALL_STATUS;
    if (/^CANCEL$/i.test(v)) return "キャンセル";
    if (/^DIALING$/i.test(v)) return "発着信中";
    if (/^TALKING$/i.test(v)) return "通話中";
    return v;
  }

  /**
   * BlueBean「発着信履歴ダウンロードAPI(CDRダウンロードAPI)」のCSVを、通話の配列に変換する(2026-10-27 追加)。
   * 顧客発着信履歴出力APIは顧客データに紐づく通話しか返さず、番号を貼り付けて発信した通話が取れなかった
   * (ソフツー回答 2026-10-27)。CDRはすべての発着信を返す。
   * - V10.19.0以降: Group_CallId,種類,発信元,着信先,外線番号,総時間,通話時間,状態,発着信時間,オペレータ,オプション,録音ファイル名,文字起こし,要約
   * - V8.5.2以降 : 種類,発信元,着信先,外線番号,総時間,通話時間,状態,発着信時間,オペレータ,オプション,録音ファイル名
   * 見出し行があれば読み飛ばす。内線は除く。返す形は flattenBlueBeanCalls と同じ
   * {group_callid, call_type, phone, start_date, operator_name, call_status, note}。
   */
  function parseCdrCsv(text) {
    var calls = [];
    parseCsv(text).forEach(function (cols) {
      var first = String(cols[0] || "").trim();
      if (/Group_CallId|種類/i.test(first)) return;
      var v10 = cols.length >= 14;
      if (!v10 && cols.length < 9) return;
      var o = v10 ? 1 : 0;
      var callType = cdrCallType_(cols[o]);
      if (callType === CALL_TYPE_INTERNAL) return;
      var src = String(cols[o + 1] || "").trim();
      var dst = String(cols[o + 2] || "").trim();
      var startDate = String(cols[o + 7] || "").trim();
      var phone = callType === CALL_TYPE_INBOUND ? src : dst;
      var talkSeconds = String(cols[o + 5] || "").trim();
      var summary = v10 ? String(cols[13] || "").trim() : "";
      var note = (talkSeconds ? "通話時間 " + talkSeconds : "") +
        (summary ? (talkSeconds ? " / " : "") + "要約: " + summary.replace(/\s+/g, " ").slice(0, 400) : "");
      calls.push({
        group_callid: v10 && first ? first : "CDR-" + startDate.replace(/\D/g, "") + "-" + phone.replace(/\D/g, ""),
        call_type: callType,
        phone: phone,
        start_date: startDate,
        operator_name: String(cols[o + 8] || "").trim(),
        call_status: cdrCallStatus_(cols[o + 6]),
        note: note
      });
    });
    return calls;
  }

  /** "山田　花子(ext001)" のようなオペレーター表記から、空白を除いた氏名部分を取り出す */
  function operatorPersonName(operator) {
    return String(operator || "").replace(/[（(].*$/, "").replace(/[\s　]+/g, "");
  }

  /**
   * CDR(全発着信)には、同じBlueBeanを使う他の組織のオペレーターの通話も含まれる(2026-10-27 判明・1日数千件)。
   * GLOWのスタッフ(スタッフタブの氏名)の通話だけを残す。氏名は空白を無視して完全一致で照合する。
   * allowedNames が空なら、何も残さない(取り違えを防ぐため、許可した人の通話だけを台帳に入れる)。
   */
  function filterCallsByOperators(calls, allowedNames) {
    var allowed = {};
    (allowedNames || []).forEach(function (n) {
      var key = operatorPersonName(n);
      if (key) allowed[key] = true;
    });
    return (calls || []).filter(function (call) {
      return !!allowed[operatorPersonName(call.operator_name)];
    });
  }

  var api = {
    operatorPersonName: operatorPersonName,
    filterCallsByOperators: filterCallsByOperators,
    parseCsv: parseCsv,
    parseCdrCsv: parseCdrCsv,
    mapCallTypeToInteractionType: mapCallTypeToInteractionType,
    flattenBlueBeanCalls: flattenBlueBeanCalls,
    matchCompanyByPhone: matchCompanyByPhone,
    buildPhoneIndex: buildPhoneIndex,
    matchCompanyByPhoneIndex: matchCompanyByPhoneIndex,
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
