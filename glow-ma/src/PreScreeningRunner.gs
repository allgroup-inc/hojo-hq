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

    // 左辺(企業マスタ側の列名)の検証。非エンジニアがマップを書き換える運用のため、
    // キーを壊した場合に「一致0件」や「既存値の消去」として静かに壊れるのを防ぐ
    // (最終レビュー2026-08-11 I4)。
    var targetFields = Object.keys(PRE_SCREENING_COLUMN_MAP);
    if (targetFields.indexOf("会社名") === -1) {
      throw new Error(
        "PRE_SCREENING_COLUMN_MAP に「会社名」のマッピングが必要です。" +
        "会社名は企業マスタと突き合わせるためのキーです。左辺の「会社名」は書き換えないでください。"
      );
    }
    var unknownFields = targetFields.filter(function (targetField) {
      return GlowSchema.COMPANY_MASTER_HEADERS.indexOf(targetField) === -1;
    });
    if (unknownFields.length > 0) {
      throw new Error(
        "PRE_SCREENING_COLUMN_MAP の左辺に企業マスタに存在しない列名があります: " +
        unknownFields.join("、") +
        " / 左辺は企業マスタの列名(会社名・事前選定ランク・事前選定スコア)である必要があります。"
      );
    }

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

    // 書式だけが及んだ空行がgetDataRange()に含まれることがある(ImportRunner.gsと同じガード)。
    // 空行を残すと未一致件数が水増しされ、設計書1章の「未一致率2割」の判断が歪む
    // (最終レビュー2026-08-11 I3)。
    var dataRows = values.slice(1).filter(function (row) {
      return !row.every(function (cell) { return cell === "" || cell === null; });
    });

    var stagingRows = dataRows.map(function (row) {
      var stagingRow = {};
      Object.keys(PRE_SCREENING_COLUMN_MAP).forEach(function (targetField) {
        var sourceHeader = PRE_SCREENING_COLUMN_MAP[targetField];
        var columnIndex = headerRow.indexOf(sourceHeader);
        stagingRow[targetField] = row[columnIndex];
      });
      return stagingRow;
    }).filter(function (stagingRow) {
      // 他の列に値があっても会社名が空の行は突き合わせ不能なため除外する(同 I3)。
      return String(stagingRow["会社名"] || "").trim() !== "";
    });

    var blankCompanyNameCount = dataRows.length - stagingRows.length;
    if (blankCompanyNameCount > 0) {
      Logger.log("会社名が空欄のため取り込み対象外にした行: " + blankCompanyNameCount + "件");
    }
    if (stagingRows.length === 0) {
      Logger.log("取り込み対象のデータ行がありません(会社名が入力された行が1件もありません)。");
      return;
    }

    var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
    if (!companySheet) {
      throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
    }
    var companyRecords = readCompanyRecords_(companySheet);

    var matchResult = GlowPreScreeningImport.matchPreScreeningRows(stagingRows, companyRecords);
    var updatedRecords = GlowPreScreeningImport.applyMatchesToCompanyRecords(companyRecords, matchResult.matches);

    // writeCompanyRecords_は企業マスタの2行目以降をclearContent()してから一括再書き込みする
    // 破壊的処理のため、importCompaniesFromStagingと同じくバックアップシートを先に作る
    // (最終レビュー2026-08-11 I1)。
    var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
    var backupName = "企業マスタ_backup_事前選定_" + todayString + "_" +
      Utilities.formatDate(new Date(), "Asia/Tokyo", "HHmmss");
    companySheet.copyTo(ss).setName(backupName);

    writeCompanyRecords_(companySheet, updatedRecords);

    Logger.log(
      "事前選定スコア取り込み完了: 一致 " + matchResult.matches.length + "件 / " +
      "未一致 " + matchResult.unmatchedNames.length + "件"
    );

    // 未一致タブへの書き出しは「記録」であり、企業マスタの更新(上で完了済み)より重要度が低い。
    // ここで失敗しても実行者に「取り込み自体が失敗した」と誤解させて再実行させないよう、
    // try/catchでログに残すだけにとどめる(最終レビュー2026-08-11 I2)。
    if (matchResult.unmatchedNames.length > 0) {
      try {
        var mismatchSheet = ss.getSheetByName(GlowSchema.PRE_SCREENING_MISMATCH_SHEET_NAME);
        if (!mismatchSheet) {
          mismatchSheet = ensureTab_(ss, GlowSchema.PRE_SCREENING_MISMATCH_SHEET_NAME, GlowSchema.PRE_SCREENING_MISMATCH_HEADERS);
        }
        var recordedAt = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm");
        var mismatchRows = matchResult.unmatchedNames.map(function (name) {
          return [name, recordedAt];
        });
        var nextRow = mismatchSheet.getLastRow() + 1;
        // insertSheetで作られたタブの初期グリッドは1,000行。未一致が多いとグリッド外になるため、
        // 書き込み前に行数を確保する(ensureTab_は行を追加しない)。
        var neededLastRow = nextRow + mismatchRows.length - 1;
        if (neededLastRow > mismatchSheet.getMaxRows()) {
          mismatchSheet.insertRowsAfter(mismatchSheet.getMaxRows(), neededLastRow - mismatchSheet.getMaxRows());
        }
        mismatchSheet.getRange(nextRow, 1, mismatchRows.length, GlowSchema.PRE_SCREENING_MISMATCH_HEADERS.length)
          .setValues(mismatchRows);
      } catch (mismatchWriteError) {
        Logger.log(
          "警告: 「" + GlowSchema.PRE_SCREENING_MISMATCH_SHEET_NAME + "」タブへの書き出しに失敗しました: " +
          mismatchWriteError +
          " / 企業マスタの更新自体は正常に完了しています(再実行は不要です)。" +
          "未一致の会社名は上のログの件数のみ記録されています。"
        );
      }
    }
  } finally {
    lock.releaseLock();
  }
}
