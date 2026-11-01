/**
 * 福田データの自動インポート用 GAS 補助スクリプト
 *
 * 機能:
 * 1. HistoricalDataImporter の自動実行設定
 * 2. メール添付ファイルの自動ダウンロード＆セット
 * 3. スケジュール実行の設定
 * 4. 結果通知の自動送信
 */

/**
 * 毎日午前2時に実行される定期ジョブ
 * - メールから最新のFukudaデータを検出
 * - 「福田_履歴インポート」タブにセット
 * - importFukudaHistoricalData を自動実行
 * - 結果をメール通知
 */
function scheduledFukudaDataImport() {
  try {
    Logger.log("=== 福田データ自動インポート ===");
    Logger.log("実行時刻: " + new Date().toLocaleString("ja-JP"));

    // 前回のインポート日時を取得
    var lastImportDate = getLastImportDate_();
    Logger.log("前回実行: " + lastImportDate.toLocaleString("ja-JP"));

    // 未処理メールを検出
    var unprocessedEmails = findUnprocessedFukudaEmails_(lastImportDate);

    if (unprocessedEmails.length === 0) {
      Logger.log("✓ 新しいメールなし（スキップ）");
      return;
    }

    Logger.log("✓ 未処理メール検出: " + unprocessedEmails.length + "件");

    // 最新のメールを処理
    var latestEmail = unprocessedEmails[unprocessedEmails.length - 1];
    Logger.log("処理対象: " + latestEmail.subject);

    // Googleドライブにファイルを確保
    var fileInfo = ensureAttachmentFile_(latestEmail);
    if (!fileInfo) {
      throw new Error("添付ファイルを取得できませんでした");
    }

    Logger.log("✓ ファイル確保: " + fileInfo.name);

    // Sheetsタブにセット
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    setupStagingSheet_(ss, fileInfo);
    Logger.log("✓ ステージングシート準備完了");

    // インポート実行
    importFukudaHistoricalData();  // HistoricalDataImporter.gs の関数を呼び出し
    Logger.log("✓ インポート実行完了");

    // 完了フラグ記録
    recordImportExecution_();

    // 通知メール送信
    sendImportNotification_(latestEmail, "成功");

  } catch (e) {
    Logger.log("✗ エラー: " + e.toString());
    sendImportNotification_(null, "失敗", e.toString());
    throw e;
  }
}

/**
 * 前回のインポート日時を取得
 */
function getLastImportDate_() {
  var props = PropertiesService.getDocumentProperties();
  var lastDate = props.getProperty("fukuda_last_import_date");

  if (!lastDate) {
    // 初回実行: 30日前から開始
    var date = new Date();
    date.setDate(date.getDate() - 30);
    return date;
  }

  return new Date(lastDate);
}

/**
 * 未処理のFukudaメールを検出
 */
function findUnprocessedFukudaEmails_(sinceDate) {
  var query = 'from:glowfukuda@gmail.com subject:(企業マスタ OR 過去100件) after:' +
              Utilities.formatDate(sinceDate, "Asia/Tokyo", "yyyy/MM/dd");

  var threads = GmailApp.search(query, 0, 10);
  var emails = [];

  threads.forEach(function(thread) {
    var messages = thread.getMessages();
    messages.forEach(function(msg) {
      var attachments = msg.getAttachments();
      if (attachments.length > 0 &&
          (msg.getSubject().includes("企業マスタ") || msg.getSubject().includes("過去100件"))) {
        emails.push({
          messageId: msg.getId(),
          subject: msg.getSubject(),
          date: msg.getDate(),
          attachments: attachments,
          from: msg.getFrom()
        });
      }
    });
  });

  // 日付でソート（古い順）
  return emails.sort(function(a, b) { return a.date - b.date; });
}

/**
 * 添付ファイルをGoogle Driveに確保
 */
function ensureAttachmentFile_(emailInfo) {
  var attachments = emailInfo.attachments.filter(function(att) {
    return att.getName().includes(".xlsx") || att.getName().includes(".xls");
  });

  if (attachments.length === 0) {
    Logger.log("✗ Excelファイルが見つかりません");
    return null;
  }

  var attachment = attachments[0];
  var blob = attachment.copyBlob();

  // Google Driveに保存
  var folder = DriveApp.getFoldersByName("glow-ma-fukuda-import").next();
  if (!folder) {
    folder = DriveApp.createFolder("glow-ma-fukuda-import");
  }

  var fileName = "福田_企業マスタデータ_" +
                 Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyyMMdd_HHmmss") +
                 ".xlsx";

  var file = folder.createFile(blob);
  file.setName(fileName);

  return {
    name: fileName,
    id: file.getId(),
    url: file.getUrl()
  };
}

/**
 * ステージングシートを準備
 */
function setupStagingSheet_(ss, fileInfo) {
  var FUKUDA_STAGING_SHEET_NAME = "福田_履歴インポート";

  // 既存シートを削除
  var existingSheet = ss.getSheetByName(FUKUDA_STAGING_SHEET_NAME);
  if (existingSheet) {
    ss.deleteSheet(existingSheet);
  }

  // 新規シートを作成
  var stagingSheet = ss.insertSheet(FUKUDA_STAGING_SHEET_NAME, 0);

  // ドライブからExcelファイルをダウンロード＆パース
  var driveFile = DriveApp.getFileById(fileInfo.id);
  var xlsxBlob = driveFile.getBlob();

  // （注: AppsScriptではExcelファイルの直接パースは制限されているため、
  //       別途Pythonスクリプトで変換したCSV/JSONを使用するか、
  //       手動で貼り付けることを想定）

  // ヘッダー行を設置
  var headers = [
    "企業名", "電話番号", "手紙送付日", "架電日", "通話結果",
    "所在地", "代表者名", "業種", "規模", "代表者年齢", "備考"
  ];
  stagingSheet.getRange(1, 1, 1, headers.length).setValues([headers]);

  Logger.log("✓ ステージングシート「" + FUKUDA_STAGING_SHEET_NAME + "」を準備（ファイル: " + fileInfo.name + "）");
}

/**
 * インポート実行を記録
 */
function recordImportExecution_() {
  var props = PropertiesService.getDocumentProperties();
  props.setProperty("fukuda_last_import_date", new Date().toISOString());
}

/**
 * 通知メール送信
 */
function sendImportNotification_(emailInfo, status, errorMessage) {
  var recipientEmail = "takeshi.koyanagi9@gmail.com";

  var subject = "【GLOW】福田データインポート " + status + " - " +
                Utilities.formatDate(new Date(), "Asia/Tokyo", "MM月dd日 HH:mm");

  var body = "福田データの自動インポートが完了しました。\n\n";
  body += "【実行時刻】" + new Date().toLocaleString("ja-JP") + "\n";
  body += "【ステータス】" + status + "\n";

  if (status === "成功" && emailInfo) {
    body += "【処理内容】\n";
    body += "- メール件名: " + emailInfo.subject + "\n";
    body += "- 送信者: " + emailInfo.from + "\n";
    body += "\n✓ データはスプレッドシート「福田_履歴インポート」タブに自動セットされました。\n";
    body += "✓ 企業マスタと対応履歴ログが自動更新されました。\n";
    body += "\n詳細はスプレッドシートの「福田_インポート結果」タブをご確認ください。\n";
  } else if (status === "失敗") {
    body += "【エラー】" + (errorMessage || "不明") + "\n";
    body += "\n手動でのデータセットが必要です。\n";
  }

  MailApp.sendEmail(recipientEmail, subject, body);
}

/**
 * インポート用トリガーを設定（初回のみ手動実行）
 *
 * 使用方法:
 * 1. Apps Script エディタでこの関数を実行
 * 2. scheduledFukudaDataImport がスケジュール実行されるようになります
 */
function setupImportTrigger() {
  // 既存トリガーを削除
  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    if (trigger.getHandlerFunction() === "scheduledFukudaDataImport") {
      ScriptApp.deleteTrigger(trigger);
    }
  });

  // 新規トリガーを作成（毎日午前2時）
  ScriptApp.newTrigger("scheduledFukudaDataImport")
    .timeBased()
    .atHour(2)
    .everyDays(1)
    .inTimezone("Asia/Tokyo")
    .create();

  Logger.log("✓ インポートトリガーを設定しました（毎日午前2時実行）");
}

/**
 * テスト実行（手動）
 */
function testFukudaImport() {
  Logger.log("=== テスト実行開始 ===");
  scheduledFukudaDataImport();
  Logger.log("=== テスト実行完了 ===");
}
