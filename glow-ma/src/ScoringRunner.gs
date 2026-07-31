/**
 * GLOW企業リレーション台帳: スコア・ランクの一括再計算
 * Apps Scriptエディタの関数選択で recalculateAllScores を選び、実行ボタンで手動実行する。
 * (将来的には日次の時間主導トリガーに登録して自動実行することを想定しているが、
 *  トリガー登録自体は本Planの範囲外。)
 *
 * 企業マスタの「初期スコア」= 属性スコア(業種+規模+代表者年齢) + 流入ルートボーナス
 * 「反応スコア」= 対応履歴ログの反応イベントの合算(GlowScoring.calculateReactionScore)
 * 「総合スコア」= 初期スコア + 反応スコア、「ランク」= 総合スコアからA〜Dを判定
 *
 * readCompanyRecords_ / writeCompanyRecords_ は glow-ma/src/ImportRunner.gs で
 * 定義済みのため、ここでは再定義せずそのまま呼び出す。
 *
 * writeCompanyRecords_ は企業マスタを丸ごと書き直す破壊的処理のため、
 * importCompaniesFromStaging(ImportRunner.gs)と同じLockServiceパターンで
 * 排他制御する(手動インポートと自動再計算が同時に走ってどちらかの書き込みを
 * 握りつぶすことを防ぐ)。
 */
function recalculateAllScores() {
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error(
      "他の処理が企業マスタを操作中のため、スコア再計算を開始できませんでした。" +
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
    var knownCompanyIds = {};
    records.forEach(function (record) {
      knownCompanyIds[record["企業ID"]] = true;
    });

    var orphanedCount = 0;
    Object.keys(interactionsByCompanyId).forEach(function (companyId) {
      if (!knownCompanyIds[companyId]) {
        orphanedCount += interactionsByCompanyId[companyId].length;
      }
    });

    records.forEach(function (record) {
      var interactionRows = interactionsByCompanyId[record["企業ID"]] || [];
      var initialScore = GlowScoring.calculateAttributeScore(record) + GlowScoring.calculateRouteBonus(record["流入ルート"]);
      var reactionScore = GlowScoring.calculateReactionScore(interactionRows);
      var totalScore = initialScore + reactionScore;

      record["初期スコア"] = initialScore;
      record["反応スコア"] = reactionScore;
      record["総合スコア"] = totalScore;
      record["ランク"] = GlowScoring.calculateRank(totalScore);
    });

    writeCompanyRecords_(companySheet, records);
    Logger.log("スコア再計算完了: " + records.length + "件");
    if (orphanedCount > 0) {
      Logger.log(
        "企業マスタに存在しない企業IDの対応履歴ログ: " + orphanedCount +
        "件(スコアに反映されません。企業IDの入力ミスがないか確認してください)"
      );
    }
  } finally {
    lock.releaseLock();
  }
}

function readInteractionsByCompanyId_(sheet) {
  var result = {};
  if (!sheet) return result;
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return result;
  var headers = GlowSchema.INTERACTION_LOG_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  values.forEach(function (row) {
    var record = {};
    headers.forEach(function (header, i) {
      record[header] = row[i];
    });
    var companyId = record["企業ID"];
    if (!companyId) return;
    if (!result[companyId]) result[companyId] = [];
    result[companyId].push(record);
  });
  return result;
}
