/* アポ管理台帳 シート構成の定義(スキーマ)
 * ブラウザ相当のGAS(global.ApoSchema)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/apo_kanri_schema.test.mjs で検証される。
 *
 * glow-ma(M&A台帳)とは完全に別のシステム。glow-ma のシート・コードを参照してはならない
 * (設計書 2026-08-14 三名体制裁定②)。
 */
(function (global) {
  "use strict";

  var STAFF_SHEET_NAME = "スタッフ";
  // Slack User ID の調べ方: Slackで対象社員のプロフィールを開き「その他」→
  // 「メンバーIDをコピー」(U から始まる文字列)。メールアドレスではない。
  var STAFF_HEADERS = ["氏名", "Slack User ID", "有効", "メールアドレス", "役割"];
  var STAFF_ROLES = ["アポ入れ", "営業", "両方"];

  var APPOINTMENT_SHEET_NAME = "アポ予定";
  // 列を追加する場合は必ず配列の末尾に追加すること(既存データの列位置がズレて破損するため、
  // 途中への挿入は禁止)。読み書きはヘッダー名ではなく配列の並び順(位置)に依存する。
  var APPOINTMENT_HEADERS = [
    "アポID", "日付", "開始時刻", "所要分", "顧客名", "形式", "場所またはURL",
    "担当営業", "アポ入れ担当", "温度感", "ステータス", "メモ",
    "登録日時", "最終更新日時"
  ];
  // ※アポ種別(再訪/新規紹介/新規ご家族)と紹介元は、リードがどこから来たかの属性であり
  //   「対面営業マン物件管理システム」の領分。本システムは予定を回すことに専念する
  //   (2026-08-19 小柳さん指摘で撤去。引き渡し: docs/連携メモ_20260819_対面営業マン物件管理システム.md)
  var APPOINTMENT_FORMATS = ["訪問", "来店", "オンライン"];
  var TEMPERATURES = ["高", "中", "低"];
  var APPOINTMENT_STATUSES = [
    "予定", "確定", "実施済", "申込み",
    "キャンセル(顧客都合)", "キャンセル(自社都合)", "再調整中"
  ];

  var HISTORY_SHEET_NAME = "変更履歴";
  var HISTORY_HEADERS = ["履歴ID", "アポID", "日時", "操作者", "操作", "変更内容"];
  var HISTORY_OPERATIONS = ["新規", "変更", "遅延連絡"];

  var SETTINGS_SHEET_NAME = "設定";
  var SETTINGS_HEADERS = ["キー", "値", "説明"];

  var api = {
    STAFF_SHEET_NAME: STAFF_SHEET_NAME,
    STAFF_HEADERS: STAFF_HEADERS,
    STAFF_ROLES: STAFF_ROLES,
    APPOINTMENT_SHEET_NAME: APPOINTMENT_SHEET_NAME,
    APPOINTMENT_HEADERS: APPOINTMENT_HEADERS,
    APPOINTMENT_FORMATS: APPOINTMENT_FORMATS,
    TEMPERATURES: TEMPERATURES,
    APPOINTMENT_STATUSES: APPOINTMENT_STATUSES,
    HISTORY_SHEET_NAME: HISTORY_SHEET_NAME,
    HISTORY_HEADERS: HISTORY_HEADERS,
    HISTORY_OPERATIONS: HISTORY_OPERATIONS,
    SETTINGS_SHEET_NAME: SETTINGS_SHEET_NAME,
    SETTINGS_HEADERS: SETTINGS_HEADERS
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.ApoSchema = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
