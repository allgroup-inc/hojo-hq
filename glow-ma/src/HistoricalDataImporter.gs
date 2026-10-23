/**
 * GLOW企業リレーション台帳: 過去100件の手紙・架電記録インポート
 *
 * 福田さんが手動で BlueBean に入力した過去100件の架電記録を、システムに反映させるためのツール。
 * 企業マスタへの追加 + 対応履歴ログへの記録を一括実行します。
 *
 * 使い方:
 * 1. スプレッドシートに「福田_履歴インポート」という名前のタブを作る
 * 2. 1行目に見出しを入力:
 *    - 企業名, 電話番号, 手紙送付日, 架電日, 通話結果
 *    （その他のフィールド: 所在地, 代表者名, 業種, 規模, 代表者年齢 等は任意）
 * 3. 2行目以降にFukudaの100件データを貼り付ける
 * 4. Apps Scriptエディタで importFukudaHistoricalData() を実行する
 *
 * 処理フロー:
 * ① データバリデーション（必須フィールド・形式確認）
 * ② 重複検出（既存台帳との照合）
 * ③ 企業データの正規化（電話番号フォーマット等）
 * ④ 企業マスタへの追加登録
 * ⑤ 対応履歴ログへの記録（手紙送付・架電）
 * ⑥ 結果レポート出力
 */

var FUKUDA_STAGING_SHEET_NAME = "福田_履歴インポート";
var FUKUDA_RESULT_SHEET_NAME = "福田_インポート結果";

// インポート時の列マッピング
var FUKUDA_COLUMN_MAP = {
  "企業名": "企業名",
  "電話番号": "電話番号",
  // 手紙送付日・架電日は企業マスタには入らず、対応履歴ログに記録される
  // 任意フィールド（あれば取り込む）
  "所在地": "所在地",
  "代表者名": "代表者名",
  "業種": "業種",
  "規模": "規模",
  "代表者年齢": "代表者年齢",
  "備考": "業態メモ"
};

var FUKUDA_OPTIONAL_FIELDS = ["所在地", "代表者名", "業種", "規模", "代表者年齢", "備考"];

/**
 * 過去100件の手紙・架電記録をインポートする（メイン実行関数）
 */
function importFukudaHistoricalData() {
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(60000)) {
    throw new Error("他の処理が台帳を操作中のため、インポートを開始できません。しばらく待ってから再実行してください。");
  }

  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet();
    var stagingSheet = ss.getSheetByName(FUKUDA_STAGING_SHEET_NAME);

    if (!stagingSheet) {
      throw new Error("「" + FUKUDA_STAGING_SHEET_NAME + "」タブが見つかりません。");
    }

    // ① データ読み込み＆バリデーション
    var validationResult = validateFukudaHistoricalData_(stagingSheet);
    if (!validationResult.isValid) {
      throw new Error("バリデーションエラー:\n" + validationResult.errors.join("\n"));
    }

    var dataRows = validationResult.dataRows;
    var headerRow = validationResult.headerRow;
    Logger.log("✓ バリデーション完了: " + dataRows.length + "件");

    // ② 重複検出
    var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
    var existingRecords = readCompanyRecords_(companySheet);

    var dedupeResult = detectDuplicates_(dataRows, headerRow, existingRecords);
    Logger.log("✓ 重複検出完了: 既存台帳との重複 " + dedupeResult.duplicateCount +
              "件, 電話番号関連会社 " + dedupeResult.relatedCount + "件");

    // ③ 企業データを正規化＆企業マスタに追加
    var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
    var nextId = GlowDedupe.nextSequenceNumber(existingRecords);

    var newCompanies = dataRows.map(function(row, index) {
      return parseFukudaHistoricalRow_(headerRow, row, nextId + index, todayString);
    });

    var combined = existingRecords.concat(newCompanies);
    var mergeResult = GlowDedupe.applyMerges(combined);
    var finalRecords = GlowDedupe.propagateDoNotContact(mergeResult.records);

    // 企業マスタを更新
    writeCompanyRecords_(companySheet, finalRecords);
    Logger.log("✓ 企業マスタを更新: " + newCompanies.length + "件追加");

    // ④ 対応履歴ログに記録
    var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
    var logResult = recordHistoricalInteractions_(logSheet, newCompanies, headerRow, dataRows);
    Logger.log("✓ 対応履歴ログを記録: 手紙送付 " + logResult.letterCount + "件, 架電 " + logResult.callCount + "件");

    // ⑤ 結果レポート出力
    var reportSheet = ensureResultSheet_(ss);
    writeImportResultReport_(reportSheet, {
      importedCount: newCompanies.length,
      duplicateCount: dedupeResult.duplicateCount,
      relatedCount: dedupeResult.relatedCount,
      letterCount: logResult.letterCount,
      callCount: logResult.callCount,
      errors: validationResult.warnings
    });

    Logger.log("✓ インポート完了！");
  } finally {
    lock.releaseLock();
  }
}

/**
 * ① バリデーション：必須フィールド・データ形式確認
 */
function validateFukudaHistoricalData_(stagingSheet) {
  var values = stagingSheet.getDataRange().getValues();
  if (values.length < 2) {
    return {
      isValid: false,
      errors: ["データ行が見つかりません（見出し + データが最低2行必要）"]
    };
  }

  var headerRow = values[0].map(String);
  var dataRows = values.slice(1).filter(function(row) {
    return !row.every(function(cell) { return cell === "" || cell === null; });
  });

  // 必須フィールド確認
  var requiredFields = ["企業名", "電話番号"];
  var missingFields = requiredFields.filter(function(field) {
    return headerRow.indexOf(field) === -1;
  });

  if (missingFields.length > 0) {
    return {
      isValid: false,
      errors: ["必須フィールドが見つかりません: " + missingFields.join(", ")]
    };
  }

  // 各行のバリデーション
  var warnings = [];
  dataRows = dataRows.filter(function(row, idx) {
    var cellMap = createCellMap_(headerRow, row);
    var rowNum = idx + 2; // 1=見出し, 2=データ開始行

    // 企業名確認
    if (!cellMap["企業名"] || cellMap["企業名"].toString().trim() === "") {
      warnings.push("行 " + rowNum + ": 企業名が空（スキップ）");
      return false;
    }

    // 電話番号形式確認
    var phoneNumber = cellMap["電話番号"] ? cellMap["電話番号"].toString().trim() : "";
    if (!phoneNumber) {
      warnings.push("行 " + rowNum + ": 電話番号が空（スキップ）");
      return false;
    }

    var normalizedPhone = phoneNumber.replace(/[^\d]/g, "");
    if (normalizedPhone.length < 10 || normalizedPhone.length > 11) {
      warnings.push("行 " + rowNum + ": 電話番号が無効な形式 '" + phoneNumber + "'（スキップ）");
      return false;
    }

    // 日付形式確認（手紙送付日・架電日）
    if (cellMap["手紙送付日"] && !isValidDate_(cellMap["手紙送付日"])) {
      warnings.push("行 " + rowNum + ": 手紙送付日が無効な日付形式（スキップ）");
      return false;
    }

    if (cellMap["架電日"] && !isValidDate_(cellMap["架電日"])) {
      warnings.push("行 " + rowNum + ": 架電日が無効な日付形式（スキップ）");
      return false;
    }

    // 時系列チェック
    if (cellMap["手紙送付日"] && cellMap["架電日"]) {
      var letterDate = parseDate_(cellMap["手紙送付日"]);
      var callDate = parseDate_(cellMap["架電日"]);
      if (letterDate && callDate && letterDate > callDate) {
        warnings.push("行 " + rowNum + ": 手紙送付日が架電日より後（警告）");
      }
    }

    return true;
  });

  return {
    isValid: true,
    headerRow: headerRow,
    dataRows: dataRows,
    warnings: warnings
  };
}

/**
 * ② 重複検出：既存台帳との照合
 */
function detectDuplicates_(dataRows, headerRow, existingRecords) {
  var duplicateCount = 0;
  var relatedCount = 0;
  var seenPhoneNumbers = {};

  dataRows.forEach(function(row) {
    var cellMap = createCellMap_(headerRow, row);
    var phoneNumber = cellMap["電話番号"].toString().trim().replace(/[^\d]/g, "");

    // 既存企業との重複確認
    var isDuplicate = existingRecords.some(function(record) {
      var existingPhone = (record["電話番号"] || "").toString().replace(/[^\d]/g, "");
      return existingPhone === phoneNumber;
    });

    if (isDuplicate) {
      duplicateCount++;
      return;
    }

    // 同一電話番号の関連会社検出
    if (seenPhoneNumbers[phoneNumber]) {
      relatedCount++;
    }
    seenPhoneNumbers[phoneNumber] = true;
  });

  return {
    duplicateCount: duplicateCount,
    relatedCount: relatedCount
  };
}

/**
 * ③ 企業データ解析＆正規化
 */
function parseFukudaHistoricalRow_(headerRow, row, companyId, todayString) {
  var cellMap = createCellMap_(headerRow, row);

  var company = {
    "企業ID": "C" + String(companyId).padStart(6, "0"),
    "企業名": cellMap["企業名"] || "",
    "電話番号": normalizePhoneNumber_(cellMap["電話番号"]),
    "所在地": cellMap["所在地"] || "",
    "代表者名": cellMap["代表者名"] || "",
    "業種": cellMap["業種"] || "",
    "規模": cellMap["規模"] || "",
    "代表者年齢": cellMap["代表者年齢"] || "",
    "業態メモ": cellMap["備考"] || "",
    "流入ルート": "②手紙DM", // Fukudaの過去データはすべて手紙DM経由
    "ステージ": "既接触", // 過去に架電があるので「既接触」
    "ランク": cellMap["ランク"] || "D", // 未指定ならランクD
    "法人番号": "",
    "作成日": todayString,
    "最後の接触日": determinePrimaryContactDate_(cellMap),
    "連絡不要": false
  };

  return company;
}

/**
 * ④ 対応履歴ログへの記録
 */
function recordHistoricalInteractions_(logSheet, newCompanies, headerRow, dataRows) {
  var letterCount = 0;
  var callCount = 0;

  var existingLogs = readInteractionLogs_(logSheet);
  var newLogs = [];

  dataRows.forEach(function(row, index) {
    var cellMap = createCellMap_(headerRow, row);
    var company = newCompanies[index];

    // 手紙送付日の記録
    if (cellMap["手紙送付日"] && isValidDate_(cellMap["手紙送付日"])) {
      newLogs.push({
        "企業ID": company["企業ID"],
        "対応日時": formatDate_(parseDate_(cellMap["手紙送付日"])),
        "架電種別": "手紙送付",
        "メモ": "過去履歴インポート（" + formatDate_(new Date()) + "実施）",
        "備考": ""
      });
      letterCount++;
    }

    // 架電日の記録
    if (cellMap["架電日"] && isValidDate_(cellMap["架電日"])) {
      var callResult = cellMap["通話結果"] ? cellMap["通話結果"].toString().trim() : "";
      newLogs.push({
        "企業ID": company["企業ID"],
        "対応日時": formatDate_(parseDate_(cellMap["架電日"])),
        "架電種別": callResult === "繋がった" ? "電話着信" : "架電不応答",
        "メモ": "通話結果: " + callResult,
        "備考": "過去履歴インポート"
      });
      callCount++;
    }
  });

  // ログシートに追記
  appendInteractionLogs_(logSheet, newLogs);

  return {
    letterCount: letterCount,
    callCount: callCount
  };
}

/**
 * 対応履歴ログを読み込む（既存実装の参照関数を使用）
 */
function readInteractionLogs_(logSheet) {
  if (!logSheet) return [];
  var values = logSheet.getDataRange().getValues();
  if (values.length < 2) return [];
  return values.slice(1).map(function(row) {
    return {
      "企業ID": row[0],
      "対応日時": row[1],
      "架電種別": row[2],
      "メモ": row[3],
      "備考": row[4]
    };
  });
}

/**
 * 対応履歴ログに追記
 */
function appendInteractionLogs_(logSheet, newLogs) {
  if (newLogs.length === 0) return;
  var data = newLogs.map(function(log) {
    return [log["企業ID"], log["対応日時"], log["架電種別"], log["メモ"], log["備考"]];
  });
  logSheet.getRange(logSheet.getLastRow() + 1, 1, data.length, 5).setValues(data);
}

/**
 * 結果シート確保
 */
function ensureResultSheet_(ss) {
  var sheet = ss.getSheetByName(FUKUDA_RESULT_SHEET_NAME);
  if (!sheet) {
    sheet = ss.insertSheet(FUKUDA_RESULT_SHEET_NAME);
    sheet.getRange(1, 1, 1, 6).setValues([["実行日時", "インポート件数", "既存重複", "関連会社", "手紙記録", "架電記録"]]);
  }
  return sheet;
}

/**
 * インポート結果レポート出力
 */
function writeImportResultReport_(reportSheet, result) {
  var now = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm:ss");
  var reportRow = [
    now,
    result.importedCount,
    result.duplicateCount,
    result.relatedCount,
    result.letterCount,
    result.callCount
  ];
  reportSheet.getRange(reportSheet.getLastRow() + 1, 1, 1, 6).setValues([reportRow]);
}

// ===== ユーティリティ関数 =====

function createCellMap_(headerRow, dataRow) {
  var map = {};
  headerRow.forEach(function(header, idx) {
    map[header] = dataRow[idx];
  });
  return map;
}

function normalizePhoneNumber_(phone) {
  if (!phone) return "";
  var digits = phone.toString().replace(/[^\d]/g, "");
  if (digits.length === 11) return digits.substring(1); // 国番号除去
  return digits;
}

function isValidDate_(value) {
  if (!value) return false;
  var parsed = parseDate_(value);
  return parsed !== null;
}

function parseDate_(value) {
  if (value instanceof Date) return value;
  if (typeof value === "number") return new Date(value * 86400000 + new Date("1899-12-30"));

  var dateStr = value.toString().trim();
  var patterns = [
    /^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})$/,
    /^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$/
  ];

  for (var i = 0; i < patterns.length; i++) {
    var match = dateStr.match(patterns[i]);
    if (match) {
      var year = match[1].length === 4 ? match[1] : match[3];
      var month = patterns[i].source.indexOf("\\d{4}") === 0 ? match[2] : match[1];
      var day = patterns[i].source.indexOf("\\d{4}") === 0 ? match[3] : match[2];
      return new Date(year, month - 1, day);
    }
  }
  return null;
}

function formatDate_(date) {
  if (!date) return "";
  return Utilities.formatDate(date, "Asia/Tokyo", "yyyy-MM-dd");
}

function determinePrimaryContactDate_(cellMap) {
  var dates = [];
  if (cellMap["架電日"] && isValidDate_(cellMap["架電日"])) {
    dates.push(parseDate_(cellMap["架電日"]));
  }
  if (cellMap["手紙送付日"] && isValidDate_(cellMap["手紙送付日"])) {
    dates.push(parseDate_(cellMap["手紙送付日"]));
  }
  if (dates.length === 0) return formatDate_(new Date());
  return formatDate_(dates.reduce(function(max, d) { return d > max ? d : max; }));
}
