/* GLOW企業リレーション台帳 シート構成の定義(スキーマ)
 * ブラウザ相当のGAS(global.GlowSchema)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_schema.test.mjs で検証される。
 */
(function (global) {
  "use strict";

  var COMPANY_MASTER_SHEET_NAME = "企業マスタ";
  var COMPANY_MASTER_HEADERS = [
    "企業ID", "法人番号", "会社名", "業種", "規模", "代表者名", "代表者年齢", "所在地",
    "流入ルート", "起点担当者_紹介元", "現在ステージ", "提案商品",
    "初期スコア", "反応スコア", "総合スコア", "ランク",
    "最終接触日", "次回アクション予定日", "次回アクション内容",
    "担当者", "登録日", "備考"
  ];

  var INTERACTION_LOG_SHEET_NAME = "対応履歴ログ";
  var INTERACTION_LOG_HEADERS = [
    "履歴ID", "企業ID", "日付", "担当者", "種別", "対応相手", "内容メモ", "次回アクション"
  ];

  var PARTNER_MASTER_SHEET_NAME = "紹介パートナーマスタ";
  var PARTNER_MASTER_HEADERS = [
    "パートナーID", "名称", "種別", "担当者名", "関係性ランク", "累計紹介数", "成約数",
    "提供済み情報ログ", "紹介料率", "逆紹介履歴", "最終接触日", "次回アクション予定日"
  ];

  var SETTINGS_SHEET_NAME = "設定";
  var SETTINGS_HEADERS = ["キー", "値", "説明"];

  var api = {
    COMPANY_MASTER_SHEET_NAME: COMPANY_MASTER_SHEET_NAME,
    COMPANY_MASTER_HEADERS: COMPANY_MASTER_HEADERS,
    INTERACTION_LOG_SHEET_NAME: INTERACTION_LOG_SHEET_NAME,
    INTERACTION_LOG_HEADERS: INTERACTION_LOG_HEADERS,
    PARTNER_MASTER_SHEET_NAME: PARTNER_MASTER_SHEET_NAME,
    PARTNER_MASTER_HEADERS: PARTNER_MASTER_HEADERS,
    SETTINGS_SHEET_NAME: SETTINGS_SHEET_NAME,
    SETTINGS_HEADERS: SETTINGS_HEADERS
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowSchema = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
