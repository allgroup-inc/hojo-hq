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
  "電話番号": "電話番号",
  // 2026-09-18 架電リスト(ホテル等)投入用に追加: リスト側で初期ランク・流入ルート・
  // 備考(業態メモ)を持たせて取り込めるようにする(議事_20260918参照)。
  // 下のIMPORT_OPTIONAL_FIELDSに載せているため「あれば取り込む」任意列で、
  // 列が無い既存の手紙DMリスト形式でもエラーにならない。
  "ランク": "ランク",
  "流入ルート": "流入ルート",
  "備考": "業態メモ"
  // 将来、取り込み元リストにDNC(連絡不要)情報の列が追加された場合は、
  // "連絡不要": "<実データの見出し>" をここに追加すればよい(csvImport.jsが自動で真偽値へ変換する)。
  // 現時点の実リストにはこの列がないため、デフォルトではマッピングしない。
  // 将来、取り込み元リストに事前選定ランク・事前選定スコアの列がある場合は、
  // "事前選定ランク": "<実データの見出し>", "事前選定スコア": "<実データの見出し>" を
  // ここに追加すればよい(csvImport.jsの汎用マッピング処理がそのまま対応する)。
};
// 「インポート待ち」タブに見出しが無くてもエラーにしない任意項目(無ければ既定値のまま)。
var IMPORT_OPTIONAL_FIELDS = ["ランク", "流入ルート", "備考"];
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
      .filter(function (targetField) { return IMPORT_OPTIONAL_FIELDS.indexOf(targetField) === -1; })
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

    // 名寄せで統合して消える既存の企業IDだけを、消してよいものとして名指しする(それ以外が抜けたら書き込みを止める)
    var finalIdSet = {};
    finalRecords.forEach(function (record) { finalIdSet[record["企業ID"]] = true; });
    var absorbedExistingIds = existingRecords
      .map(function (record) { return record["企業ID"]; })
      .filter(function (id) { return !finalIdSet[id]; });
    writeCompanyRecords_(companySheet, finalRecords, { allowRemovedIds: absorbedExistingIds });
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

/**
 * 企業マスタの2行目以降を records の内容に書き直す。
 *
 * 2026-11-11 失敗台帳 FK-010: 以前は「全部消してから全社分を一度に書く」作りで、書く途中に Google 側の
 * エラー(Service Spreadsheets failed)が起きると、書けなかった会社がまるごと消えた(企業マスタの約6割)。
 * 今は次の順に書く(判定は companyWriteGuard.js の GlowCompanyWriteGuard)。
 *   1. 書く前に、今の企業ID列と照らし合わせる。会社が抜ける・並びが変わる・重複する書き込みは、何も書かずに止める
 *   2. 先に消さず、上の行から CHUNK_ROWS 行ずつ上書きする(一時的なエラーはその場で数回やり直す)。
 *      途中で止まっても、まだ書いていない行には元のデータが残る
 *   3. 書いた範囲の企業ID列を読み直して照らし合わせる。合っていたら、余った行だけを消す
 *   4. 最後にもう一度、企業ID列全体を照らし合わせる
 * どこかで止まったときは、稼働状況タブに「企業マスタの書き込み」の失敗を残して通知し、例外を投げる
 * (呼び出し側の処理もそこで止まる)。
 *
 * @param {Object} [options] { allowRemovedIds: 消してよい企業ID(名寄せで統合した分など。呼び出し側が名指しする) }
 */
function writeCompanyRecords_(sheet, records, options) {
  var guard = GlowCompanyWriteGuard;
  var headers = GlowSchema.COMPANY_MASTER_HEADERS;
  var idCol = headers.indexOf("企業ID") + 1;
  var oldIdsRaw = readCompanyIdColumn_(sheet, idCol);
  var newIds = records.map(function (record) { return record["企業ID"]; });

  var plan = guard.planCompanyWrite(oldIdsRaw, newIds, options);
  if (!plan.ok) {
    failCompanyWrite_("書き込む前の確認で止めました(企業マスタは変更していません): " + plan.reason);
  }
  if (records.length === 0) return;

  var rows = records.map(function (record) {
    return headers.map(function (header) {
      var value = record[header];
      if (Array.isArray(value)) return value.join("、");
      return value === undefined || value === null ? "" : value;
    });
  });

  var written = 0;
  try {
    guard.chunkRanges(rows.length, guard.CHUNK_ROWS).forEach(function (range) {
      var chunk = rows.slice(range.offset, range.offset + range.count);
      setValuesWithRetry_(sheet.getRange(2 + range.offset, 1, range.count, headers.length), chunk, guard.MAX_ATTEMPTS);
      written = range.offset + range.count;
    });
  } catch (error) {
    failCompanyWrite_(
      "書き込みの途中で止まりました(" + written + "/" + rows.length + "社まで書きました。" +
      "まだ書いていない行には元のデータが残っています): " + error
    );
  }

  flushSpreadsheet_();
  var writtenCheck = guard.verifyWrittenIds(newIds, readCompanyIdColumn_(sheet, idCol).slice(0, rows.length));
  if (!writtenCheck.ok) {
    failCompanyWrite_("書いた後の照合で違いが見つかりました(余った行は消していません): " + writtenCheck.reason);
  }

  var lastRow = sheet.getLastRow();
  if (lastRow > rows.length + 1) {
    sheet.getRange(rows.length + 2, 1, lastRow - rows.length - 1, headers.length).clearContent();
    flushSpreadsheet_();
  }
  var finalCheck = guard.verifyWrittenIds(newIds, readCompanyIdColumn_(sheet, idCol));
  if (!finalCheck.ok) {
    failCompanyWrite_("最後の照合で違いが見つかりました: " + finalCheck.reason);
  }
  recordOpsStatus_("企業マスタの書き込み", true,
    rows.length + "社(書き込み後に企業IDを照合済み" +
    (plan.addedIds.length ? "・追加 " + plan.addedIds.length + "社" : "") +
    (plan.removedIds.length ? "・統合などで外した " + plan.removedIds.length + "社" : "") + ")");
}

/** 企業マスタの企業ID列(2行目から最後の行まで)を、空欄も含めて返す */
function readCompanyIdColumn_(sheet, idCol) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  return sheet.getRange(2, idCol, lastRow - 1, 1).getValues().map(function (row) { return row[0]; });
}

/** 一時的なエラーで失敗したら、少し待ってやり直す(同じ範囲に同じ値を書くので、やり直しても結果は同じ) */
function setValuesWithRetry_(range, values, maxAttempts) {
  var lastError = null;
  for (var attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      range.setValues(values);
      return;
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) Utilities.sleep(2000 * attempt);
    }
  }
  throw lastError;
}

function flushSpreadsheet_() {
  if (typeof SpreadsheetApp.flush === "function") SpreadsheetApp.flush();
}

/** 企業マスタの書き込みを止めたことを稼働状況タブに残し、通知してから例外を投げる */
function failCompanyWrite_(message) {
  try {
    recordOpsStatus_("企業マスタの書き込み", false, message);
    notifyOpsFailure_("企業マスタの書き込み", message +
      "\n\n今朝のバックアップ(GLOW企業リレーション台帳_バックアップ_日付)と企業マスタの件数を比べてください。");
  } catch (notifyError) {
    Logger.log("企業マスタの書き込みの失敗を記録・通知できませんでした: " + notifyError);
  }
  throw new Error("企業マスタの書き込みを止めました。" + message);
}
