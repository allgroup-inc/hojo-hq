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
    "登録日時", "最終更新日時",
    "アポ種別", "紹介元",
    // 共通認識(1つのアプリ・5つの入口)への対応。列は末尾のみ追加すること。
    // 顧客ID: 顧客台帳(kakei-crm)の KM-000001 形式への参照。氏名・住所の正はあちら側。
    // 差し戻し理由: 旧「キャンセル(顧客都合/自社都合)」の区別をステータスから理由列へ移した。
    "顧客ID", "差し戻し理由"
  ];
  // 再訪と新規では決まり方がまったく違うため、混ぜた平均値は改善判断に使えない。
  // 種別ごとに申込率を出せるようにする(2026-08-19 小柳さん決裁)。
  var APPOINTMENT_KINDS = [
    "再訪(既存)", "新規(紹介)", "新規(ご家族)", "新規(その他)"
  ];
  var APPOINTMENT_FORMATS = ["訪問", "来店", "オンライン"];
  var TEMPERATURES = ["高", "中", "低"];
  // 共通語彙(軸の共通認識)に準拠。言い換えないこと。
  // ❷が持つ: スケジュール調整中 / アポ確定 ・ ❸: 訪問済 ・ ❹: 申込 ・ ❶へ返却: 差し戻し
  // 旧「再調整中」は「スケジュール調整中 + 日時なし」で表現する(議事_20260821)。
  var APPOINTMENT_STATUSES = [
    "スケジュール調整中", "アポ確定", "訪問済", "申込", "差し戻し"
  ];
  var CANCEL_REASONS = ["顧客都合", "自社都合"];

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
    APPOINTMENT_KINDS: APPOINTMENT_KINDS,
    TEMPERATURES: TEMPERATURES,
    APPOINTMENT_STATUSES: APPOINTMENT_STATUSES,
    CANCEL_REASONS: CANCEL_REASONS,
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
