/**
 * GLOW企業リレーション台帳: 連絡不要(DNC)フラグの同期
 * 対応履歴ログに「連絡不要受領」が記録された企業を検出し、企業マスタの
 * 「連絡不要」フラグをTRUEにする。さらに同じ電話番号を持つ他の企業
 * (関連会社・家族経営等)にも連絡不要を伝播させる(GlowDedupe.propagateDoNotContact)。
 *
 * 通常は MaintenanceRunner.gs の runDailyMaintenance から日次で自動実行される
 * (2026-09-03 まで手動実行のみだったため、断った会社への再架電が起こりうる状態だった)。
 * 単発で反映したいときだけ、Apps Scriptエディタで syncDoNotContactFlags を直接実行する。
 */
function syncDoNotContactFlags() {
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error(
      "他の処理が企業マスタを操作中のため、連絡不要フラグの同期を開始できませんでした。" +
      "しばらく待ってから再実行してください。"
    );
  }
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
    if (!companySheet) {
      throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
    }
    var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
    var interactionsByCompanyId = readInteractionsByCompanyId_(logSheet);

    var records = readCompanyRecords_(companySheet);
    var newlyMarkedCount = 0;
    records.forEach(function (record) {
      var interactionRows = interactionsByCompanyId[record["企業ID"]] || [];
      var hasDoNotContactEvent = interactionRows.some(function (row) {
        return row["種別"] === "連絡不要受領";
      });
      if (hasDoNotContactEvent && record["連絡不要"] !== true) {
        record["連絡不要"] = true;
        newlyMarkedCount++;
      }
    });

    var propagated = GlowDedupe.propagateDoNotContact(records);
    writeCompanyRecords_(companySheet, propagated);

    var totalDoNotContactCount = propagated.filter(function (record) {
      return record["連絡不要"] === true;
    }).length;
    Logger.log(
      "連絡不要フラグの同期完了: 対応履歴ログから新規検出 " + newlyMarkedCount + "件 / " +
      "同一電話番号への伝播後の合計 " + totalDoNotContactCount + "件"
    );
  } finally {
    lock.releaseLock();
  }
}
