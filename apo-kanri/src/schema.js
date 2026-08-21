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
    // 名寄せキー。**当面の保存はアセンドの顧客id**(2026-08-21 軸の裁定①)。
    // KM-000001 は名寄せの親統合で採番が動くため、確定前に焼き付けると全部ずれる。
    // KM- は読み取り時に resolve API で引き、カットオーバーで焼き付けてから不変にする。
    // **フォームには出さない**(営業に手入力させない=タップを増やさない)。
    // 自動連携(❶または❸からの登録)が通るまでは空のまま。
    "顧客ID",
    // 差し戻しの理由(顧客都合/自社都合)。ステータスは共通語彙のまま、理由は属性で持つ
    // (2026-08-21 軸の裁定③)。自社都合は「他の見込み客に使えたはずの訪問枠を捨てた」
    // 最も高くつく損失であり、顧客都合と混ぜると見えなくなるため必ず分ける。
    // **人事評価に使わないこと**(使われると全部「顧客都合」になり項目が嘘になる)。
    "差し戻し理由"
  ];
  // ※アポ種別(再訪/新規紹介/新規ご家族)と紹介元は、リードがどこから来たかの属性であり
  //   「対面営業マン物件管理システム」の領分。本システムは予定を回すことに専念する
  //   (2026-08-19 小柳さん指摘で撤去。引き渡し: docs/連携メモ_20260819_対面営業マン物件管理システム.md)
  var APPOINTMENT_FORMATS = ["訪問", "来店", "オンライン"];
  var TEMPERATURES = ["高", "中", "低"];

  /* ステータスは5システム共通語彙。言い換え禁止(共通の約束【4】)。
   * 旧語彙からの読み替え(2026-08-21 軸の裁定②③で移行。本番未投入のためデータ移行は不要):
   *   予定 / 再調整中          → スケジュール調整中
   *   確定                     → アポ確定
   *   実施済                   → 訪問済(❸が持つ。❷は読むだけ)
   *   申込み                   → 申込(❹が持つ。❷は読むだけ)
   *   キャンセル(顧客都合)   → 差し戻し + 差し戻し理由「顧客都合」
   *   キャンセル(自社都合)   → 差し戻し + 差し戻し理由「自社都合」
   */

  // ❷(このシステム)が書き換えてよいステータス。
  // 差し戻し=訪問に至らず❶へ返却。対象外=架電禁止・アポ禁(持ち場と無関係に最優先)。
  var OWNED_STATUSES = ["スケジュール調整中", "アポ確定", "差し戻し", "対象外"];
  // ❸❹が持つステータス。❷は**読むだけ**(2026-08-21 軸の裁定②:
  // 「持つ(書き換える)」と「見る(読む)」は別物。共通仕様が禁じているのは書き換え)。
  var HANDED_OFF_STATUSES = ["訪問済", "追客中", "申込", "成立", "保全中"];
  var APPOINTMENT_STATUSES = [
    "スケジュール調整中", "アポ確定",
    "訪問済", "追客中", "申込", "成立", "保全中",
    "差し戻し", "対象外"
  ];
  var RETURN_REASONS = ["顧客都合", "自社都合"];
  /* 訪問枠が空くステータス。差し戻し=❶へ返却、対象外=架電禁止/アポ禁。
   * これ以外(調整中を含む)は枠を押さえている扱い。調整の途中で他アポに枠を取られると
   * 調整そのものが破綻するため、流れたら差し戻しにして明示的に空ける。 */
  var SLOT_FREED_STATUSES = ["差し戻し", "対象外"];

  /* ❷から訪問結果(訪問済/申込 等)を書き換えられるかの切替。
   * 軸の裁定②は「編集不可にする」。ただし**❸からの結果連携が通るまで禁止にすると、
   * 誰も結果を入れられずファネルが真っ暗になる**ため、連携が通るまでは "許可"。
   * ❸連携の実装と同じリリースで "禁止" に倒す(それが裁定の完成形)。
   */
  var RESULT_INPUT_MODE = "許可";

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
    OWNED_STATUSES: OWNED_STATUSES,
    HANDED_OFF_STATUSES: HANDED_OFF_STATUSES,
    RETURN_REASONS: RETURN_REASONS,
    SLOT_FREED_STATUSES: SLOT_FREED_STATUSES,
    RESULT_INPUT_MODE: RESULT_INPUT_MODE,
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
