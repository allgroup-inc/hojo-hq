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
    "電話番号", "連絡不要", "後継者状況", "関係メモ", "窓口担当者名", "携帯番号",
    "事前選定ランク", "事前選定スコア"
  ];

  var INTERACTION_LOG_SHEET_NAME = "対応履歴ログ";
  var INTERACTION_LOG_HEADERS = [
    "履歴ID", "企業ID", "日付", "担当者", "種別", "対応相手", "内容メモ", "次回アクション"
  ];

  var INTERACTION_TYPES = [
    "手紙送付", "電話", "入電", "アポ獲得", "ゆんたく相談実施", "面談実施", "紹介受領", "ミカタ接点確認",
    "レターURLアクセス", "返信", "資料請求",
    "提案(M&A)", "提案(不動産)", "提案(法人保険)",
    "成約", "見送り", "ナーチャリング配信", "連絡不要受領",
    "NDA締結", "意向表明受領", "DD開始", "関係メモ更新"
  ];

  var RESPONDENT_TYPES = ["オーナー社長本人", "経理・総務等の窓口担当", "未接触"];

  var SUCCESSOR_STATUS_TYPES = ["あり", "なし", "不明"];

  var PARTNER_MASTER_SHEET_NAME = "紹介パートナーマスタ";
  var PARTNER_MASTER_HEADERS = [
    "パートナーID", "名称", "種別", "担当者名", "関係性ランク", "累計紹介数", "成約数",
    "提供済み情報ログ", "紹介料率", "逆紹介履歴", "最終接触日", "次回アクション予定日"
  ];
  // 新規パートナー登録フォーム(管理画面)の選択肢。開拓先の実態に合わせて追加してよいが、
  // 既存行の種別と表記を揃えること(絞り込み・集計で別物扱いになるため)
  var PARTNER_TYPES = [
    "銀行", "信用金庫", "税理士", "公認会計士", "行政書士", "社会保険労務士",
    "弁護士", "商工会・商工会議所", "保険代理店", "不動産会社", "その他"
  ];
  var PARTNER_RANKS = ["A", "B", "C", "D"];

  var SETTINGS_SHEET_NAME = "設定";
  var SETTINGS_HEADERS = ["キー", "値", "説明"];

  var LETTER_DRAFT_SHEET_NAME = "レター下書き";
  var LETTER_DRAFT_HEADERS = [
    "下書きID", "企業ID", "種別", "生成日時", "本文", "ステータス", "発送日"
  ];
  var LETTER_DRAFT_TYPES = ["初回DM", "ナーチャリング配信"];
  var LETTER_DRAFT_STATUSES = ["下書き", "送付済み", "見送り"];

  var DASHBOARD_SHEET_NAME = "ダッシュボード";
  var DASHBOARD_PLACEHOLDER_HEADERS = ["ダッシュボード(updateDashboardを実行すると内容が生成されます)"];

  var DASHBOARD_HISTORY_SHEET_NAME = "ダッシュボード履歴";
  var DASHBOARD_HISTORY_HEADERS = [
    "記録日時", "対象企業数",
    "ランクA_滞留企業数", "ランクB_滞留企業数", "ランクC_滞留企業数", "ランクD_滞留企業数",
    "掘り起こし待ち件数合計", "成約企業数", "連絡不要企業数", "長期検討企業数"
  ];

  var STAFF_SHEET_NAME = "スタッフ";
  // Slack User ID の調べ方: Slackで対象社員のプロフィールを開き「その他」→
  // 「メンバーIDをコピー」(U から始まる文字列)。メールアドレスではない。
  // LINE User ID の調べ方: LINE公式アカウントの管理画面から事前に一覧取得する方法が
  // ないため、対象社員が最初に音声を送ると返る「担当者が特定できませんでした」の
  // 返信に併記されるIDを、本人から管理者へ転送してもらって転記する。同じIDは
  // GAS側の実行ログにも出力される(glow-ma/src/LineVoiceLogRunner.gs参照)。
  var STAFF_HEADERS = ["氏名", "Slack User ID", "有効", "メールアドレス", "LINE User ID"];

  var PARTNER_INTERACTION_LOG_SHEET_NAME = "パートナー対応履歴ログ";
  var PARTNER_INTERACTION_LOG_HEADERS = [
    "履歴ID", "パートナーID", "日付", "対応者", "内容メモ", "次回アクション"
  ];

  var REFERRAL_RECORD_SHEET_NAME = "紹介実績ログ";
  var REFERRAL_RECORD_HEADERS = [
    "実績ID", "パートナーID", "紹介日", "対象企業ID", "紹介料率", "契約内容メモ", "成約有無"
  ];

  var PRE_SCREENING_STAGING_SHEET_NAME = "事前選定リスト";
  var PRE_SCREENING_MISMATCH_SHEET_NAME = "事前選定_未一致";
  var PRE_SCREENING_MISMATCH_HEADERS = ["会社名", "記録日時"];

  var CTI_CALL_LOG_SHEET_NAME = "CTI通話履歴";
  // BlueBean(顧客発着信履歴出力API)から取得した通話履歴の記録タブ。
  // 「group_callid」列は同一通話の再取得を防ぐための一意キー(CtiRunner.gs参照)。
  // 「対応履歴ログ記録」列は「記録済み」(対応履歴ログへ自動追記した)/「未記録」
  // (未マッチ、または通話ステータスがキャンセル等で対象外)のいずれか
  // (docs/議事_20260819_BlueBean CTI連携.md参照: 完了かつ一意マッチのみ自動記録)。
  var CTI_CALL_LOG_HEADERS = [
    "通話ID", "group_callid", "通話日時", "種別", "電話番号",
    "マッチ企業ID", "マッチ企業名", "発信者(BlueBeanオペレーター名)",
    "通話ステータス", "備考(BlueBeanノート)", "対応履歴ログ記録"
  ];

  var LINE_VOICE_LOG_SHEET_NAME = "音声ログ処理状況";
  var LINE_VOICE_LOG_HEADERS = [
    "処理ID", "LINEユーザーID", "LINEメッセージID", "ステータス",
    "受信日時", "会社名候補", "企業ID",
    "種別候補", "対応相手候補", "内容メモ", "次回アクション", "エラー内容",
    // v1.4 見込みシグナル(音声から抽出し、確定時に企業マスタへ反映する候補値)。
    // 既存シートの行とズレないよう、必ず末尾に追加すること
    "後継者状況候補", "興味商品候補", "次回予定日候補"
  ];
  // 「処理中」は、1つの実行(1分トリガー or postback)がその行を占有していることを示す
  // 一時ステータス。二重処理・二重書き込みを防ぐための確保(claim)に使う。
  var LINE_VOICE_LOG_STATUSES = [
    "受信済み", "処理中", "文字起こし済み", "企業選択待ち", "新規企業確認待ち",
    "最終確認待ち", "確定", "破棄", "エラー"
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
    PARTNER_TYPES: PARTNER_TYPES,
    PARTNER_RANKS: PARTNER_RANKS,
    SETTINGS_SHEET_NAME: SETTINGS_SHEET_NAME,
    SETTINGS_HEADERS: SETTINGS_HEADERS,
    LETTER_DRAFT_SHEET_NAME: LETTER_DRAFT_SHEET_NAME,
    LETTER_DRAFT_HEADERS: LETTER_DRAFT_HEADERS,
    LETTER_DRAFT_TYPES: LETTER_DRAFT_TYPES,
    LETTER_DRAFT_STATUSES: LETTER_DRAFT_STATUSES,
    DASHBOARD_SHEET_NAME: DASHBOARD_SHEET_NAME,
    DASHBOARD_PLACEHOLDER_HEADERS: DASHBOARD_PLACEHOLDER_HEADERS,
    DASHBOARD_HISTORY_SHEET_NAME: DASHBOARD_HISTORY_SHEET_NAME,
    DASHBOARD_HISTORY_HEADERS: DASHBOARD_HISTORY_HEADERS,
    STAFF_SHEET_NAME: STAFF_SHEET_NAME,
    STAFF_HEADERS: STAFF_HEADERS,
    PARTNER_INTERACTION_LOG_SHEET_NAME: PARTNER_INTERACTION_LOG_SHEET_NAME,
    PARTNER_INTERACTION_LOG_HEADERS: PARTNER_INTERACTION_LOG_HEADERS,
    REFERRAL_RECORD_SHEET_NAME: REFERRAL_RECORD_SHEET_NAME,
    REFERRAL_RECORD_HEADERS: REFERRAL_RECORD_HEADERS,
    PRE_SCREENING_STAGING_SHEET_NAME: PRE_SCREENING_STAGING_SHEET_NAME,
    PRE_SCREENING_MISMATCH_SHEET_NAME: PRE_SCREENING_MISMATCH_SHEET_NAME,
    PRE_SCREENING_MISMATCH_HEADERS: PRE_SCREENING_MISMATCH_HEADERS,
    LINE_VOICE_LOG_SHEET_NAME: LINE_VOICE_LOG_SHEET_NAME,
    LINE_VOICE_LOG_HEADERS: LINE_VOICE_LOG_HEADERS,
    LINE_VOICE_LOG_STATUSES: LINE_VOICE_LOG_STATUSES,
    CTI_CALL_LOG_SHEET_NAME: CTI_CALL_LOG_SHEET_NAME,
    CTI_CALL_LOG_HEADERS: CTI_CALL_LOG_HEADERS
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowSchema = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
