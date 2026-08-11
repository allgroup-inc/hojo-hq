/**
 * GLOW企業リレーション台帳: 事前選定スコア・ランクの取り込み(遡及反映)
 *
 * 使い方:
 * 1. スプレッドシートに「事前選定リスト」という名前のタブを作る
 * 2. 1行目に元データの見出し、2行目以降にデータを貼り付ける
 * 3. 下の PRE_SCREENING_COLUMN_MAP の右辺を、実際の見出し文字列に合わせて書き換える
 * 4. Apps Scriptエディタで applyPreScreeningScores を実行する
 *
 * 実行すると、企業マスタの会社名と「事前選定リスト」の会社名を(空白除去・全角英数字の半角変換のみの
 * 正規化で)突き合わせ、一致した企業の「事前選定ランク」「事前選定スコア」だけを更新する。
 * 一致しなかった行は件数をログに出し、会社名一覧を「事前選定_未一致」タブに書き出す
 * (目視確認は必須ではない。設計書4.3節参照)。
 *
 * 見出しが異なる複数のファイルを取り込む場合は、PRE_SCREENING_COLUMN_MAP を書き換えて
 * ファ​イルごとに複数回実行する。
 *
 * 設計書: docs/superpowers/specs/2026-08-11-glow-ma-pre-screening-score-import-design.md
 */
var PRE_SCREENING_COLUMN_MAP = {
  // 左が企業マスタの列名、右が「事前選定リスト」タブの見出し文字列。
  // 実データの見出しに合わせてここを書き換えてから実行する。
  "会社名": "正式商号",
  "事前選定ランク": "仮ランク",
  "事前選定スコア": "仮スコア"
};

function applyPreScreeningScores() {
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error(
      "他の処理が企業マスタを操作中のため、取り込みを開始できませんでした。" +
      "しばらく待ってから再実行してください。"
    );
  }
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var stagingSheet = ss.getSheetByName(GlowSchema.PRE_SCREENING_STAGING_SHEET_NAME);
    if (!stagingSheet) {
      throw new Error(
        "「" + GlowSchema.PRE_SCREENING_STAGING_SHEET_NAME + "」タブが見つかりません。" +
        "元データを貼り付けてから実行してください。"
      );
    }
    var values = stagingSheet.getDataRange().getValues();
    if (values.length < 2) {
      Logger.log("取り込み対象のデータ行がありません。");
      return;
    }
    var headerRow = values[0].map(String);

    var missingHeaders = Object.keys(PRE_SCREENING_COLUMN_MAP)
      .map(function (targetField) { return PRE_SCREENING_COLUMN_MAP[targetField]; })
      .filter(function (sourceHeader) { return headerRow.indexOf(sourceHeader) === -1; });
    if (missingHeaders.length > 0) {
      throw new Error(
        "PRE_SCREENING_COLUMN_MAP が「" + GlowSchema.PRE_SCREENING_STAGING_SHEET_NAME +
        "」タブの見出しと一致しません。見つからない見出し: " + missingHeaders.join("、") +
        " / PRE_SCREENING_COLUMN_MAP を実際の見出しに合わせて書き換えてから再実行してください。"
      );
    }

    var stagingRows = values.slice(1).map(function (row) {
      var stagingRow = {};
      Object.keys(PRE_SCREENING_COLUMN_MAP).forEach(function (targetField) {
        var sourceHeader = PRE_SCREENING_COLUMN_MAP[targetField];
        var columnIndex = headerRow.indexOf(sourceHeader);
        stagingRow[targetField] = row[columnIndex];
      });
      return stagingRow;
    });

    var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
    if (!companySheet) {
      throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
    }
    var companyRecords = readCompanyRecords_(companySheet);

    var matchResult = GlowPreScreeningImport.matchPreScreeningRows(stagingRows, companyRecords);
    var updatedRecords = GlowPreScreeningImport.applyMatchesToCompanyRecords(companyRecords, matchResult.matches);
    writeCompanyRecords_(companySheet, updatedRecords);

    Logger.log(
      "事前選定スコア取り込み完了: 一致 " + matchResult.matches.length + "件 / " +
      "未一致 " + matchResult.unmatchedNames.length + "件"
    );

    if (matchResult.unmatchedNames.length > 0) {
      var mismatchSheet = ss.getSheetByName(GlowSchema.PRE_SCREENING_MISMATCH_SHEET_NAME);
      if (!mismatchSheet) {
        mismatchSheet = ensureTab_(ss, GlowSchema.PRE_SCREENING_MISMATCH_SHEET_NAME, GlowSchema.PRE_SCREENING_MISMATCH_HEADERS);
      }
      var recordedAt = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm");
      var mismatchRows = matchResult.unmatchedNames.map(function (name) {
        return [name, recordedAt];
      });
      var nextRow = mismatchSheet.getLastRow() + 1;
      mismatchSheet.getRange(nextRow, 1, mismatchRows.length, GlowSchema.PRE_SCREENING_MISMATCH_HEADERS.length)
        .setValues(mismatchRows);
    }
  } finally {
    lock.releaseLock();
  }
}
