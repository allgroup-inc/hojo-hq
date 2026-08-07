/**
 * GLOW企業リレーション台帳: レター発送日の記録・発送業者連携用CSV出力
 *
 * 「発送日」は「投函完了日」(実際に送った日、または発送業者への依頼が完了し
 * 発送が確定した日)を意味する。これから依頼する予定日ではない。
 *
 * セットアップ(人間が一度だけ行う):
 * 1. `clasp push` で最新コードを反映する
 * 2. Apps Scriptエディタで installLetterDraftEditTrigger を一度だけ手動実行する
 *    (冪等なので安全に再実行できる。初回実行時に認可ダイアログが出るのは正常な挙動)
 *
 * 使い方:
 * 1. 「レター下書き」タブで、送付した下書きの行の「発送日」列に日付(yyyy-MM-dd)を入力する
 * 2. 自動的に以下が行われる:
 *    - 企業マスタの当該企業の「次回アクション予定日」が空の場合のみ、発送日+10日を
 *      セットする(既に別の予定日が設定されている場合は上書きしない)
 *    - 対応履歴ログに「手紙送付」が自動追記される(同じ下書きIDでの重複記録はしない)
 *
 * 注意: この関数は「onEdit」という予約名を使っていない。もし onEdit という名前にすると
 * GASの**シンプルトリガー**として自動実行されてしまうが、シンプルトリガーは権限が制限された
 * 実行コンテキストで動作し、LockServiceを使う本関数は認可が必要なため失敗する。そのため
 * この関数自体は直接トリガーされない普通の関数として定義し、installLetterDraftEditTrigger を
 * Apps Scriptエディタから**人間が手動で実行**して、認可済みの「インストール型トリガー」
 * として登録する必要がある(AlertRunner.gsのhandleInteractionLogEditと同じ設計)。
 */
function handleLetterDraftEdit(e) {
  if (!e || !e.range) return;
  var sheet = e.range.getSheet();
  if (sheet.getName() !== GlowSchema.LETTER_DRAFT_SHEET_NAME) return;
  if (e.range.getNumRows() !== 1 || e.range.getNumColumns() !== 1) return;

  var shippedDateColumnIndex = GlowSchema.LETTER_DRAFT_HEADERS.indexOf("発送日") + 1;
  if (e.range.getColumn() !== shippedDateColumnIndex) return;

  var row = e.range.getRow();
  if (row < 2) return;

  // Fetch the full typed row FIRST, before using the date value.
  // e.value may not be properly formatted for date cells; getValues() returns the typed Date object.
  var headers = GlowSchema.LETTER_DRAFT_HEADERS;
  var rowValues = sheet.getRange(row, 1, 1, headers.length).getValues()[0];

  var sentDateValue = rowValues[headers.indexOf("発送日")];
  if (!sentDateValue) return;

  var draftId = rowValues[headers.indexOf("下書きID")];
  var companyId = rowValues[headers.indexOf("企業ID")];

  updateFollowUpDateIfEmpty_(companyId, sentDateValue);
  appendShippedInteractionLogIfNew_(companyId, draftId, sentDateValue);
}

/**
 * 企業マスタの「次回アクション予定日」が空の場合のみ、発送日+設定日数をセットする。
 * 既に値がある場合は何もしない(担当者が個別設定した予定日を上書きしないため)。
 */
function updateFollowUpDateIfEmpty_(companyId, sentDateValue) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) return;

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    Logger.log(
      "企業マスタのロック取得に失敗したため、次回アクション予定日の自動セットをスキップしました: " + companyId
    );
    return;
  }
  try {
    var headers = GlowSchema.COMPANY_MASTER_HEADERS;
    var lastRow = companySheet.getLastRow();
    if (lastRow < 2) return;
    var values = companySheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
    var companyIdIndex = headers.indexOf("企業ID");
    var nextActionDateIndex = headers.indexOf("次回アクション予定日");
    var nextActionContentIndex = headers.indexOf("次回アクション内容");

    for (var i = 0; i < values.length; i++) {
      if (values[i][companyIdIndex] !== companyId) continue;
      if (values[i][nextActionDateIndex]) return;

      var followUpDate = GlowShippingContent.computeFollowUpDate(
        sentDateValue, GlowShippingContent.DEFAULT_CONFIG.followUpDays
      );
      if (!followUpDate) return;

      var sheetRow = i + 2;
      companySheet.getRange(sheetRow, nextActionDateIndex + 1).setValue(followUpDate);
      companySheet.getRange(sheetRow, nextActionContentIndex + 1).setValue(
        GlowShippingContent.DEFAULT_CONFIG.followUpAction
      );
      return;
    }
  } finally {
    lock.releaseLock();
  }
}

/**
 * 対応履歴ログに「手紙送付」を自動追記する。同じ下書きID由来の記録が既に
 * 存在する場合はスキップする(発送日セルを後から訂正しても重複記録しないため)。
 */
function appendShippedInteractionLogIfNew_(companyId, draftId, sentDateValue) {
  if (!draftId) return;  // Guard against falsy draftId to prevent false-positive marker matches

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  if (!logSheet) return;

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    Logger.log("対応履歴ログのロック取得に失敗したため、手紙送付の自動記録をスキップしました: " + companyId);
    return;
  }
  try {
    var headers = GlowSchema.INTERACTION_LOG_HEADERS;
    var marker = "下書きID: " + draftId;
    var lastRow = logSheet.getLastRow();
    if (lastRow >= 2) {
      var memoIndex = headers.indexOf("内容メモ");
      var values = logSheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
      for (var i = 0; i < values.length; i++) {
        if (String(values[i][memoIndex]).indexOf(marker) !== -1) return;
      }
    }

    var nextRow = logSheet.getLastRow() + 1;
    var logId = "H-" + Utilities.getUuid();
    logSheet.getRange(nextRow, 1, 1, headers.length).setValues([[
      logId, companyId, sentDateValue, "システム(自動記録)", "手紙送付", "未接触",
      "発送日の記録により自動追記(" + marker + ")", ""
    ]]);
  } finally {
    lock.releaseLock();
  }
}

/**
 * handleLetterDraftEdit をインストール型のonEditトリガーとして登録する。
 * 冪等: 実行時にまず同じハンドラ関数を指す既存トリガーをすべて削除してから
 * 新規登録するため、重複登録を心配せずに安全に再実行できる。
 */
function installLetterDraftEditTrigger() {
  var existingTriggers = ScriptApp.getProjectTriggers();
  existingTriggers.forEach(function (trigger) {
    if (trigger.getHandlerFunction() === "handleLetterDraftEdit") {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  ScriptApp.newTrigger("handleLetterDraftEdit")
    .forSpreadsheet(ss)
    .onEdit()
    .create();
  Logger.log("発送日記録用のonEditトリガーを登録しました。");
}
