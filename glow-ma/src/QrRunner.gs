/**
 * GLOW企業リレーション台帳: レター発送 個別QRコード生成
 *
 * メニュー「GLOW台帳」→「発送日でQR出力」から実行する。指定した発送日に一致する
 * レター下書きを企業マスタと突合し、各企業のトラッキングURL(letterContent.jsの
 * buildTrackingUrlと同じもの)をQRコード画像化してGoogle Driveに保存する。
 * 外部QR生成API(api.qrserver.com、APIキー不要)を使う。生成結果(成功/失敗)は
 * 「QR生成結果」タブに一覧で書き出す。
 *
 * 1社のQR生成失敗が全体の処理を止めないよう障害隔離する(LetterRunner.gs等と同じ方針)。
 *
 * セットアップ: 既存のScript Property TRACKING_BASE_URL(Phase 4で設定済み)が前提。
 * 新しい設定項目は追加しない。
 *
 * 発送はロット単位(数社〜数十社程度)を想定している。GASの1回の実行には6分の
 * 制限があるため、対象社数が多い場合は発送日を分けて複数回実行すること。
 */
function exportQrCodesForDate() {
  var ui = SpreadsheetApp.getUi();
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var response = ui.prompt(
    "発送日でQR出力",
    "対象の発送日を yyyy-MM-dd 形式で入力してください(空欄なら本日: " + todayString + ")",
    ui.ButtonSet.OK_CANCEL
  );
  if (response.getSelectedButton() !== ui.Button.OK) return;
  var targetDate = response.getResponseText().trim() || todayString;

  var baseUrl = PropertiesService.getScriptProperties().getProperty("TRACKING_BASE_URL");
  if (!baseUrl) {
    ui.alert("スクリプトプロパティ TRACKING_BASE_URL が未設定です。先に設定してください。");
    return;
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var draftSheet = ss.getSheetByName(GlowSchema.LETTER_DRAFT_SHEET_NAME);
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var qrResultSheet = ss.getSheetByName(GlowSchema.QR_RESULT_SHEET_NAME);
  if (!draftSheet || !companySheet || !qrResultSheet) {
    ui.alert(
      "「" + GlowSchema.LETTER_DRAFT_SHEET_NAME + "」「" + GlowSchema.COMPANY_MASTER_SHEET_NAME +
      "」「" + GlowSchema.QR_RESULT_SHEET_NAME +
      "」タブのいずれかが見つかりません。先に ensureLedgerTabs を実行してください。"
    );
    return;
  }

  var letterDrafts = readLetterDrafts_(draftSheet);
  var companies = readCompanyRecords_(companySheet);
  var manifest = GlowQrContent.buildQrManifestRows(letterDrafts, companies, targetDate, baseUrl);
  if (manifest.length === 0) {
    ui.alert("発送日「" + targetDate + "」に該当するデータがありません。");
    return;
  }

  var folder = getOrCreateQrFolder_(targetDate);
  var results = manifest.map(function (row) {
    return generateAndSaveQr_(row, folder, targetDate);
  });

  writeQrResultSheet_(ss, results);
  var successCount = results.filter(function (r) { return r["ステータス"] === "成功"; }).length;
  ui.alert(
    "発送日「" + targetDate + "」のQR出力が完了しました(" + successCount + "/" + results.length + "件成功)。" +
    "Driveフォルダ「" + folder.getName() + "」と「" + GlowSchema.QR_RESULT_SHEET_NAME + "」タブを確認してください。"
  );
}

/**
 * 発送日ごとのQR画像保存先フォルダを取得または新規作成する。
 * 同じ発送日で再実行しても重複フォルダを作らないことが目的。
 *
 * 権限を`drive.file`(スクリプト自身が作成したファイル・フォルダのみ)に絞っているため、
 * 名前での検索(getFoldersByName)は`drive.file`では呼び出し自体が例外になることを
 * 本番動作確認(2026-08-15)で確認した(「指定された権限では DriveApp.getFoldersByName
 * を呼び出すことができません」)。黙って空を返すのではなく処理全体が落ちるため、
 * 名前検索へのフォールバックはできない。そこで参照はスクリプトプロパティに記録した
 * フォルダID(getFolderById、検索に依存しない)のみを使い、記録が無い/失効している
 * 場合はそのまま新規作成する。
 *
 * 取得・作成できたフォルダのIDは毎回プロパティへ書き戻し、次回以降はそのIDで参照する。
 */
function getOrCreateQrFolder_(targetDate) {
  var folderName = "QR_" + targetDate;
  var properties = PropertiesService.getScriptProperties();
  var propertyKey = "QR_FOLDER_ID_" + targetDate;
  var folder = null;

  var cachedId = properties.getProperty(propertyKey);
  if (cachedId) {
    try {
      folder = DriveApp.getFolderById(cachedId);
      // ゴミ箱に入れられたフォルダもIDでは取得できてしまう。そのまま使うと
      // 生成したQR画像がゴミ箱の中に保存され、運用者から見えなくなる。
      if (folder.isTrashed()) folder = null;
    } catch (err) {
      // 記録済みIDのフォルダが削除された・IDが古い等。新規作成にフォールバックする。
      Logger.log("QRフォルダIDでの取得に失敗しました: " + cachedId + " — " + err);
      folder = null;
    }
  }

  if (!folder) {
    folder = DriveApp.createFolder(folderName);
  }

  properties.setProperty(propertyKey, folder.getId());
  return folder;
}

/**
 * 1社分のQRコード画像を外部API経由で生成し、Driveフォルダへ保存する。
 * API呼び出し・画像保存のいずれかが失敗しても例外を投げず、ステータス付きの
 * 結果オブジェクトを返す(1社の失敗で全体の処理を止めないため)。
 *
 * HTTP 200 でも本文が画像とは限らない(外部APIのメンテナンス画面等が 200 text/html で
 * 返る場合がある)。読めないPNGを「成功」として印刷業者に渡さないため、Content-Type が
 * image/ で始まることまで確認してから成功扱いにする(CLAUDE.md 絶対ルール1: 断定しない)。
 */
function generateAndSaveQr_(row, folder, targetDate) {
  var qrApiUrl = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" +
    encodeURIComponent(row.trackingUrl);
  try {
    var response = UrlFetchApp.fetch(qrApiUrl, { muteHttpExceptions: true });
    if (response.getResponseCode() !== 200) {
      return {
        "企業ID": row["企業ID"], "会社名": row["会社名"], "発送日": targetDate,
        "トラッキングURL": row.trackingUrl,
        "QR画像リンク": "", "ステータス": "QR生成失敗(HTTP " + response.getResponseCode() + ")"
      };
    }
    var blob = response.getBlob();
    var contentType = blob.getContentType();
    if (!contentType || contentType.indexOf("image/") !== 0) {
      Logger.log("QR生成APIが画像以外を返しました: " + row["企業ID"] + " — Content-Type: " + contentType);
      return {
        "企業ID": row["企業ID"], "会社名": row["会社名"], "発送日": targetDate,
        "トラッキングURL": row.trackingUrl,
        "QR画像リンク": "", "ステータス": "QR生成失敗(画像データではない)"
      };
    }
    var fileName = row["企業ID"] + ".png";
    blob.setName(fileName);
    // 同じ発送日で再実行したときに同名ファイルが二重に残らないよう、古いファイルは
    // ゴミ箱に移す(Driveは同名ファイルの重複を許すため)。
    // 順序が重要: 先に新しいファイルを作り、成功してから古いファイルを消す。
    // 先に消してからcreateFileが失敗すると、前回の正しいQR画像も失って手元に何も
    // 残らなくなるため(CLAUDE.md 絶対ルール1: 印刷業者に渡す実物を壊さない)。
    var file = folder.createFile(blob);
    var newFileId = file.getId();
    var sameNameFiles = folder.getFilesByName(fileName);
    while (sameNameFiles.hasNext()) {
      var existing = sameNameFiles.next();
      // 今作ったファイル自身は消さない(作成直後は同名ファイルが2つ並ぶため、
      // 名前ではなくIDで判定する)。
      if (existing.getId() !== newFileId) existing.setTrashed(true);
    }
    return {
      "企業ID": row["企業ID"], "会社名": row["会社名"], "発送日": targetDate,
      "トラッキングURL": row.trackingUrl,
      "QR画像リンク": file.getUrl(), "ステータス": "成功"
    };
  } catch (err) {
    Logger.log("QR生成に失敗しました: " + row["企業ID"] + " — " + err);
    return {
      "企業ID": row["企業ID"], "会社名": row["会社名"], "発送日": targetDate,
      "トラッキングURL": row.trackingUrl,
      "QR画像リンク": "", "ステータス": "QR生成失敗(" + String(err) + ")"
    };
  }
}

/**
 * QR生成結果一覧を「QR生成結果」タブに書き込む。実行のたびに既存の内容(見出し行を除く)を
 * クリアしてから書き込む(前回の発送日の結果が残らないようにするため)。
 */
function writeQrResultSheet_(ss, results) {
  var sheet = ss.getSheetByName(GlowSchema.QR_RESULT_SHEET_NAME);
  if (!sheet) return;
  var headers = GlowSchema.QR_RESULT_HEADERS;
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  var lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, headers.length).clearContent();
  }
  if (results.length === 0) return;
  var rows = results.map(function (result) {
    return headers.map(function (header) { return result[header] || ""; });
  });
  sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
}
