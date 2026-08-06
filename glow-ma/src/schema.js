/* GLOW企業リレーション台帳 シート構成の定義(スキーマ)
 * ブラウザ相当のGAS(global.GlowSchema)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_schema.test.mjs で検証される。
 */
(function (global) {
  "use strict";

  var COMPANY_MASTER_SHEET_NAME = "企業マスタ";
  // 列を追加する場合は必ず配列の末尾に追加すること(既存データの列位置がズレて破損するため、
  // 途中への挿入は禁止)。読み書きはヘッダー名ではなく配列の並び順(位置)に依存する実装のため。
  var COMPANY_MASTER_HEADERS = [
    "企業ID", "法人番号", "会社名", "業種", "規模", "代表者名", "代表者年齢", "所在地",
    "流入ルート", "起点担当者_紹介元", "現在ステージ", "提案商品",
    "初期スコア", "反応スコア", "総合スコア", "ランク",
    "最終接触日", "次回アクション予定日", "次回アクション内容",
    "担当者", "登録日", "備考",
    "電話番号", "連絡不要", "後継者状況", "関係メモ"
  ];

  var INTERACTION_LOG_SHEET_NAME = "対応履歴ログ";
  var INTERACTION_LOG_HEADERS = [
    "履歴ID", "企業ID", "日付", "担当者", "種別", "対応相手", "内容メモ", "次回アクション"
  ];

  var INTERACTION_TYPES = [
    "手紙送付", "電話", "入電", "ゆんたく相談実施", "面談実施", "紹介受領", "ミカタ接点確認",
    "レターURLアクセス", "返信", "資料請求",
    "提案(M&A)", "提案(不動産)", "提案(法人保険)",
    "成約", "見送り", "ナーチャリング配信", "連絡不要受領",
    "NDA締結", "意向表明受領", "DD開始"
  ];

  var RESPONDENT_TYPES = ["オーナー社長本人", "経理・総務等の窓口担当", "未接触"];

  var SUCCESSOR_STATUS_TYPES = ["あり", "なし", "不明"];

  var PARTNER_MASTER_SHEET_NAME = "紹介パートナーマスタ";
  var PARTNER_MASTER_HEADERS = [
    "パートナーID", "名称", "種別", "担当者名", "関係性ランク", "累計紹介数", "成約数",
    "提供済み情報ログ", "紹介料率", "逆紹介履歴", "最終接触日", "次回アクション予定日"
  ];

  var SETTINGS_SHEET_NAME = "設定";
  var SETTINGS_HEADERS = ["キー", "値", "説明"];

  var LETTER_DRAFT_SHEET_NAME = "レター下書き";
  var LETTER_DRAFT_HEADERS = [
    "下書きID", "企業ID", "種別", "生成日時", "本文", "ステータス"
  ];
  var LETTER_DRAFT_TYPES = ["初回DM", "ナーチャリング配信"];
  var LETTER_DRAFT_STATUSES = ["下書き", "送付済み", "見送り"];

  var DASHBOARD_SHEET_NAME = "ダッシュボード";
  var DASHBOARD_PLACEHOLDER_HEADERS = ["ダッシュボード(updateDashboardを実行すると内容が生成されます)"];

  var DASHBOARD_HISTORY_SHEET_NAME = "ダッシュボード履歴";
  var DASHBOARD_HISTORY_HEADERS = [
    "記録日時", "対象企業数",
    "ランクA_滞留企業数", "ランクB_滞留企業数", "ランクC_滞留企業数", "ランクD_滞留企業数",
    "掘り起こし待ち件数合計", "成約企業数", "連絡不要企業数"
  ];

  var api = {
    COMPANY_MASTER_SHEET_NAME: COMPANY_MASTER_SHEET_NAME,
    COMPANY_MASTER_HEADERS: COMPANY_MASTER_HEADERS,
    INTERACTION_LOG_SHEET_NAME: INTERACTION_LOG_SHEET_NAME,
    INTERACTION_LOG_HEADERS: INTERACTION_LOG_HEADERS,
    INTERACTION_TYPES: INTERACTION_TYPES,
    RESPONDENT_TYPES: RESPONDENT_TYPES,
    SUCCESSOR_STATUS_TYPES: SUCCESSOR_STATUS_TYPES,
    PARTNER_MASTER_SHEET_NAME: PARTNER_MASTER_SHEET_NAME,
    PARTNER_MASTER_HEADERS: PARTNER_MASTER_HEADERS,
    SETTINGS_SHEET_NAME: SETTINGS_SHEET_NAME,
    SETTINGS_HEADERS: SETTINGS_HEADERS,
    LETTER_DRAFT_SHEET_NAME: LETTER_DRAFT_SHEET_NAME,
    LETTER_DRAFT_HEADERS: LETTER_DRAFT_HEADERS,
    LETTER_DRAFT_TYPES: LETTER_DRAFT_TYPES,
    LETTER_DRAFT_STATUSES: LETTER_DRAFT_STATUSES,
    DASHBOARD_SHEET_NAME: DASHBOARD_SHEET_NAME,
    DASHBOARD_PLACEHOLDER_HEADERS: DASHBOARD_PLACEHOLDER_HEADERS,
    DASHBOARD_HISTORY_SHEET_NAME: DASHBOARD_HISTORY_SHEET_NAME,
    DASHBOARD_HISTORY_HEADERS: DASHBOARD_HISTORY_HEADERS
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowSchema = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
