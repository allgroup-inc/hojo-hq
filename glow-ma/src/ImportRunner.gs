/**
 * GLOW企業リレーション台帳: 7000件リストの一括インポート
 *
 * 使い方:
 * 1. スプレッドシートに「インポート待ち」という名前のタブを作る
 * 2. 1行目に元データの見出し、2行目以降にデータを貼り付ける
 * 3. 下の IMPORT_COLUMN_MAP の右辺を、実際の見出し文字列に合わせて書き換える
 * 4. Apps Scriptエディタで importCompaniesFromStaging を実行する
 *
 * 実行すると、企業マスタの既存データと突き合わせて法人番号が一致するものは
 * GlowDedupe.mergeCompanyRecords で統合し、企業マスタを丸ごと書き直す。
 */
var IMPORT_COLUMN_MAP = {
  // 左が企業マスタの列名、右が「インポート待ち」タブの見出し文字列。
  // 実データの見出しに合わせてここを書き換えてから実行する(設計書15章オープンクエスチョン)。
  "会社名": "会社名",
  "法人番号": "法人番号",
  "業種": "業種",
  "規模": "規模",
  "代表者名": "代表者名",
  "代表者年齢": "代表者年齢",
  "所在地": "所在地",
  "電話番号": "電話番号"
  // 将来、取り込み元リストにDNC(連絡不要)情報の列が追加された場合は、
  // "連絡不要": "<実データの見出し>" をここに追加すればよい(csvImport.jsが自動で真偽値へ変換する)。
  // 現時点の実リストにはこの列がないため、デフォルトではマッピングしない。
};
var STAGING_SHEET_NAME = "インポート待ち";

function importCompaniesFromStaging() {
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error(
      "他の処理が企業マスタを操作中のため、インポートを開始できませんでした。" +
      "しばらく待ってから再実行してください。"
    );
  }
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var staging = ss.getSheetByName(STAGING_SHEET_NAME);
    if (!staging) {
      throw new Error("「" + STAGING_SHEET_NAME + "」タブが見つかりません。元データを貼り付けてから実行してください。");
    }
    var values = staging.getDataRange().getValues();
    if (values.length < 2) {
      Logger.log("インポート対象のデータ行がありません。");
      return;
    }
    var headerRow = values[0].map(String);

    var missingHeaders = Object.keys(IMPORT_COLUMN_MAP)
      .map(function (targetField) { return IMPORT_COLUMN_MAP[targetField]; })
      .filter(function (sourceHeader) { return headerRow.indexOf(sourceHeader) === -1; });
    if (missingHeaders.length > 0) {
      throw new Error(
        "IMPORT_COLUMN_MAP が「" + STAGING_SHEET_NAME + "」タブの見出しと一致しません。" +
        "見つからない見出し: " + missingHeaders.join("、") +
        " / IMPORT_COLUMN_MAP を実際の見出しに合わせて書き換えてから再実行してください。"
      );
    }

    var dataRows = values.slice(1).filter(function (row) {
      return !row.every(function (cell) { return cell === "" || cell === null; });
    });

    var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
    if (!companySheet) {
      throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
    }

    var existingRecords = readCompanyRecords_(companySheet);
    var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");

    var nextId = GlowDedupe.nextSequenceNumber(existingRecords);
    var newRecords = dataRows.map(function (row, index) {
      return GlowCsvImport.parseCompanyCsvRow(headerRow, row, IMPORT_COLUMN_MAP, nextId + index, todayString);
    });

    var invalidCorporateNumberCount = newRecords.filter(function (record) {
      return !GlowDedupe.normalizeCorporateNumber(record["法人番号"]);
    }).length;

    var combined = existingRecords.concat(newRecords);
    var mergeResult = GlowDedupe.applyMerges(combined);
    var finalRecords = GlowDedupe.propagateDoNotContact(mergeResult.records);

    var idOccurrences = {};
    finalRecords.forEach(function (record) {
      var id = record["企業ID"];
      idOccurrences[id] = (idOccurrences[id] || 0) + 1;
    });
    var duplicateIds = Object.keys(idOccurrences).filter(function (id) { return idOccurrences[id] > 1; });
    if (duplicateIds.length > 0) {
      throw new Error(
        "企業IDの重複を検出したため、書き込みを中止しました(データは変更されていません)。" +
        "企業マスタを確認してください。重複している企業ID: " + duplicateIds.join("、")
      );
    }

    var backupName = "企業マスタ_backup_" + todayString + "_" + Utilities.formatDate(new Date(), "Asia/Tokyo", "HHmmss");
    companySheet.copyTo(ss).setName(backupName);

    writeCompanyRecords_(companySheet, finalRecords);
    Logger.log(
      "インポート完了: 新規読込 " + newRecords.length + "件 / 名寄せ統合 " +
      mergeResult.absorbedCount + "件 / 最終件数 " + finalRecords.length + "件"
    );
    Logger.log(
      "法人番号が不正または空の新規行: " + invalidCorporateNumberCount + "件(名寄せ対象外)"
    );
  } finally {
    lock.releaseLock();
  }
}

function readCompanyRecords_(sheet) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.COMPANY_MASTER_HEADERS;
  var idIndex = headers.indexOf("企業ID");
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var records = [];
  var skippedWithDataCount = 0;
  values.forEach(function (row) {
    // 企業マスタの列(電話番号のセル形式・連絡不要チェックボックス・後継者状況の
    // プルダウンなど)はensureTab_で将来の入力に備えてシート全体(getMaxRows()分)に
    // あらかじめ書式・入力規則を設定している。Apps Scriptはこの「書式だけの空セル」も
    // getLastRow()の対象に含めてしまうため、実データが無くても書式が及ぶ行数分だけ
    // 空の行が返ってくる。企業IDが空の行は実データではないため読み飛ばす
    // (本番運用2026-08-10で発見。readPartnerInteractionsByPartnerId_等と同じガード)。
    // ただし、企業IDが空でも他の列に値がある行は「人が入力途中の行」の可能性がある。
    // writeCompanyRecords_の一括書き戻しで消えてしまうため、件数をログに残す
    // (最終レビュー2026-08-10 I5)。
    if (!row[idIndex]) {
      // 未チェックのチェックボックス列はfalseを返すため、空セル扱いにする
      // (そうしないと書式だけの空行がすべて「入力途中」と誤検知される)。
      var hasOtherValue = row.some(function (cell) {
        return cell !== "" && cell !== null && cell !== undefined && cell !== false;
      });
      if (hasOtherValue) skippedWithDataCount++;
      return;
    }
    var record = {};
    headers.forEach(function (header, i) {
      record[header] = row[i];
    });
    record["流入ルート"] = record["流入ルート"] ? String(record["流入ルート"]).split("、") : [];
    record["提案商品"] = record["提案商品"] ? String(record["提案商品"]).split("、") : [];
    records.push(record);
  });
  if (skippedWithDataCount > 0) {
    Logger.log(
      skippedWithDataCount + "件の企業ID未設定の行をスキップしました" +
      "(データ入力中の可能性があるため確認してください)"
    );
  }
  return records;
}

function writeCompanyRecords_(sheet, records) {
  var headers = GlowSchema.COMPANY_MASTER_HEADERS;
  var lastRow = sheet.getLastRow();
  if (lastRow > 1) {
    sheet.getRange(2, 1, lastRow - 1, headers.length).clearContent();
  }
  if (records.length === 0) return;
  var rows = records.map(function (record) {
    return headers.map(function (header) {
      var value = record[header];
      if (Array.isArray(value)) return value.join("、");
      return value === undefined || value === null ? "" : value;
    });
  });
  sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
}
