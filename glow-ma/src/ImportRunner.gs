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
    // 停止中は、バックアップのタブを作る前に止める(台帳に何も足さない)
    assertCompanyWriteNotPaused_();
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
    writeCompanyRecords_(companySheet, finalRecords, { allowRemovedIds: absorbedExistingIds, backupSheetName: backupName });
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
 *   1. 書く前の確認(phase: "precheck"): 今の企業マスタと照らし合わせる。会社が抜ける・並びが変わる・重複する・
 *      0社になる書き込みと、企業IDが空なのに値が入っている行(人が手で入力した行)がある場合は、何も書かずに止める
 *   2. 書き込み(phase: "write"): 先に消さず、上の行から CHUNK_ROWS 行ずつ上書きする。一時的なエラーだけを、
 *      回数と待ち時間の合計を決めてやり直す。途中で止まっても、まだ書いていない行には元のデータが残る
 *   3. 書いた後の照合(phase: "verify"): 企業ID列を読み直して照らし合わせる。行がずれる書き込みは全列を照らし合わせる。
 *      下に残った行は、空の行か、書いた会社・外してよい会社の古い行だけのときに消す。最後にもう一度、企業ID列全体を照らし合わせる
 * どこかで止まったときは、稼働状況タブに「企業マスタの書き込み」の失敗を残して通知し、companyWrite
 * ({ phase, dataChanged })を持つ例外を投げる。呼び出し側はこれを見て、後の処理を止めるかを決める(MaintenanceRunner.gs)。
 *
 * @param {Object} [options] { allowRemovedIds: 消してよい企業ID(名寄せで統合した分など。呼び出し側が名指しする),
 *                             backupSheetName: 書く前に作ったバックアップのタブ名(止めたときの戻し方の案内に使う) }
 */
function writeCompanyRecords_(sheet, records, options) {
  // 0. 緊急停止スイッチ(CompanyWritePauseRunner.gs)。停止中は何も読まず・書かずに止める
  assertCompanyWriteNotPaused_();
  var guard = GlowCompanyWriteGuard;
  var headers = GlowSchema.COMPANY_MASTER_HEADERS;
  var idIndex = headers.indexOf("企業ID");
  var allowedRemoved = (options && options.allowRemovedIds) || [];
  var recovery = companyWriteRecoveryHint_(options);
  var newIds = records.map(function (record) { return record["企業ID"]; });

  // 1. 書く前の確認(ここで止まったときは、企業マスタは変わっていない)
  var before;
  try {
    before = readCompanyMasterRows_(sheet, headers.length);
  } catch (error) {
    failCompanyWrite_("precheck", false, "書く前に企業マスタを読めませんでした(企業マスタは変更していません): " + error);
  }
  var idlessRows = guard.findIdlessDataRows(before, idIndex, 2);
  if (idlessRows.length > 0) {
    failCompanyWrite_("precheck", false,
      "書く前の確認で止めました(企業マスタは変更していません): 企業IDが空なのに値が入っている行が " + idlessRows.length +
      "行あります(" + idlessRows.slice(0, 5).join("・") + "行目" + (idlessRows.length > 5 ? " ほか" : "") +
      ")。消さないように止めました。企業IDを付けるか、要らない行なら人が消してください");
  }
  // 数式のセルは、値で書き戻すと数式が消えるため、書く前に止める(2026-11-15 最終安全審査。本番の企業マスタは数式0か所)
  var formulaCells;
  try {
    formulaCells = before.length ? guard.findFormulaCells(sheet.getRange(2, 1, before.length, headers.length).getFormulas(), headers, 2) : [];
  } catch (error) {
    failCompanyWrite_("precheck", false, "書く前に企業マスタの数式の有無を確かめられませんでした(企業マスタは変更していません): " + error);
  }
  if (formulaCells.length > 0) {
    failCompanyWrite_("precheck", false,
      "書く前の確認で止めました(企業マスタは変更していません): 数式が入っているセルが " + formulaCells.length + "か所あります(" +
      guard.describeCells(formulaCells) + ")。書き直すと数式が消えるため止めました。数式を値に直すか、企業マスタの外へ移してください");
  }
  var plan = guard.planCompanyWrite(before.map(function (row) { return row[idIndex]; }), newIds, options);
  if (!plan.ok) {
    failCompanyWrite_("precheck", false, "書く前の確認で止めました(企業マスタは変更していません): " + plan.reason);
  }
  if (records.length === 0) return;

  var rows = records.map(function (record) {
    return headers.map(function (header) {
      var value = record[header];
      if (Array.isArray(value)) return value.join("、");
      return value === undefined || value === null ? "" : value;
    });
  });

  // 「=」で始まる文字は、書くと数式として入って元の文字が失われるため、書く前に止める
  var formulaLike = guard.findFormulaLikeValues(rows, headers, 2);
  if (formulaLike.length > 0) {
    failCompanyWrite_("precheck", false,
      "書く前の確認で止めました(企業マスタは変更していません): 「=」で始まる文字が " + formulaLike.length + "か所あります(" +
      guard.describeCells(formulaLike) + ")。そのまま書くと数式として入り、元の文字が失われるため止めました。先頭の「=」を外してください");
  }

  // 時間の歯止め(executionBudget.js): この実行(上限6分)の残り時間が足りないときは、書き込みを始めない。
  // 上限で打ち切られると、記録も通知も動かないため(2026-11-16 の日次メンテナンスの時間切れ)
  var budget = GlowExecutionBudget;
  var elapsedAtStart = executionElapsedMs_();
  if (!budget.canStartWrite(elapsedAtStart, plan.shifted)) {
    failCompanyWrite_("precheck", false,
      "書く前の確認で止めました(企業マスタは変更していません): この実行は始まってから " + budget.seconds(elapsedAtStart) +
      "秒たっており、書き終える時間が足りないおそれがあるため、書き込みを始めませんでした。次の回に書きます");
  }

  // 2. 書き込み
  //    行がずれない書き込みでは、今の内容と同じかたまり(500行)は書かない(変わっていない日は1回も書かない。
  //    書く量を減らすほど、遅い日でも時間切れに届きにくく、途中で止まる機会も減る)
  var written = 0;          // ここまでの行は、書いたか・書く必要が無かった
  var attemptedEnd = 0;
  var touched = false;      // 企業マスタに1回でも書こうとしたか
  var writtenChunks = 0;
  var skippedChunks = 0;
  var slowestChunkMs = 0;
  var retryState = { waitedMs: 0 };
  var timeStop = null;      // 時間切れが近いために自分で止めたとき、その説明
  try {
    guard.chunkRanges(rows.length, guard.CHUNK_ROWS).forEach(function (range) {
      if (timeStop) return;
      var chunk = rows.slice(range.offset, range.offset + range.count);
      if (!plan.shifted &&
          guard.compareRows(chunk, before.slice(range.offset, range.offset + range.count), headers, 2 + range.offset).ok) {
        skippedChunks++;
        written = range.offset + range.count;
        return;
      }
      var elapsed = executionElapsedMs_();
      if (!budget.canStartChunk(elapsed, slowestChunkMs)) {
        timeStop = "この実行は始まってから " + budget.seconds(elapsed) + "秒たっており、上限(6分)で打ち切られる前に、区切りで止めました";
        return;
      }
      attemptedEnd = range.offset + range.count;
      touched = true;
      setValuesWithRetry_(sheet.getRange(2 + range.offset, 1, range.count, headers.length), chunk, retryState);
      slowestChunkMs = Math.max(slowestChunkMs, executionElapsedMs_() - elapsed);
      writtenChunks++;
      written = range.offset + range.count;
    });
    if (timeStop) throw new Error(timeStop);
  } catch (error) {
    var detail = "書き込みの途中で止まりました(" + written + "/" + rows.length + "社まで済みました。";
    if (plan.shifted) {
      // 行がずれる書き込みでは、止まった所の前後で1行の中に別の会社の値が混ざりうる。混ざった行を数えて知らせる
      var counts = countMixedCompanyRows_(sheet, rows.slice(0, Math.max(attemptedEnd, written)), headers);
      detail += "行がずれる書き込みのため、止まった所までに、1行の中に別の会社の値が混ざった行が " + counts.mixed +
        "行、まだ書けていない行が " + counts.notWritten + "行あります。" + recovery + ")";
    } else {
      detail += "会社の行の位置は変わらないため、まだ書いていない行には元のデータが残っています。会社は消えていません。残りは次の回に書きます)";
    }
    failCompanyWrite_("write", touched, detail + ": " + error);
  }

  // 何も変わっておらず、下に片付ける行も無ければ、ここで終わる(企業マスタには1回も書いていない)
  if (writtenChunks === 0 && before.length <= rows.length) {
    recordOpsStatus_("企業マスタの書き込み", true,
      rows.length + "社(今の内容と同じため、書き込みはしていません)");
    return;
  }

  // 3. 書いた後の照合(読み直しが失敗しても、必ず失敗として記録・通知して止める)
  try {
    flushSpreadsheet_();
    var after = readCompanyMasterRows_(sheet, headers.length);
    var writtenIds = after.slice(0, rows.length).map(function (row) { return row[idIndex]; });
    var writtenCheck = guard.verifyWrittenIds(newIds, writtenIds);
    if (!writtenCheck.ok) {
      failCompanyWrite_("verify", true, "書いた後の照合で違いが見つかりました(余った行は消していません。" + recovery + "): " + writtenCheck.reason);
    }
    if (plan.shifted) {
      // 行がずれる書き込み(名寄せの統合など)だけは、企業IDだけでなく全列を照らし合わせる
      var rowCheck = guard.compareRows(rows, after.slice(0, rows.length), headers, 2);
      if (!rowCheck.ok) {
        failCompanyWrite_("verify", true, "書いた後の全列の照合で違いが見つかりました(余った行は消していません。" + recovery + "): " + rowCheck.reason);
      }
    }
    var tail = after.slice(rows.length);
    var tailCheck = guard.checkTrailingRows(tail, idIndex, newIds, allowedRemoved, rows.length + 2);
    if (!tailCheck.ok) {
      failCompanyWrite_("verify", true, "書いた範囲より下に、消してはいけない行が残っています(余った行は消していません。" + recovery + "): " + tailCheck.reason);
    }
    if (tail.length > 0) {
      sheet.getRange(rows.length + 2, 1, tail.length, headers.length).clearContent();
      flushSpreadsheet_();
    }
    var finalCheck = guard.verifyWrittenIds(newIds, readCompanyIdColumn_(sheet, idIndex + 1));
    if (!finalCheck.ok) {
      failCompanyWrite_("verify", true, "最後の照合で違いが見つかりました(" + recovery + "): " + finalCheck.reason);
    }
  } catch (error) {
    if (error && error.companyWrite) throw error;
    failCompanyWrite_("verify", true, "書いた後の照合の途中で、企業マスタの読み書きに失敗しました(" + recovery + "): " + error);
  }
  recordOpsStatus_("企業マスタの書き込み", true,
    rows.length + "社(書き込み後に企業ID" + (plan.shifted ? "と全列" : "") + "を照合済み" +
    (skippedChunks ? "・変わっていない " + skippedChunks + "かたまりは書かず、" + writtenChunks + "かたまりを書いた" : "") +
    (plan.addedIds.length ? "・追加 " + plan.addedIds.length + "社" : "") +
    (plan.removedIds.length ? "・統合などで外した " + plan.removedIds.length + "社" : "") + ")");
}

/** 止まったときの戻し方の案内(書く前にバックアップのタブを作った呼び出しは、そのタブ名を渡す) */
function companyWriteRecoveryHint_(options) {
  var tab = options && options.backupSheetName;
  return tab
    ? "戻すときは、書く前に作ったバックアップのタブ「" + tab + "」の内容を企業マスタへ貼り戻してください"
    : "戻すときは、その日の朝のバックアップ(GLOW企業リレーション台帳_バックアップ_日付)の企業マスタを使ってください";
}

/** 書き込みの途中で止まった後、書こうとした範囲で「1行の中に別の会社の値が混ざった行」と「まだ書けていない行」を数える */
function countMixedCompanyRows_(sheet, rows, headers) {
  try {
    var actual = sheet.getRange(2, 1, rows.length, headers.length).getValues();
    return GlowCompanyWriteGuard.countMixedRows(rows, actual, headers);
  } catch (error) {
    return { mixed: "(数えられませんでした)", notWritten: "(数えられませんでした)" };
  }
}

/** 企業マスタの2行目から最後の行までを、全列そのまま返す */
function readCompanyMasterRows_(sheet, columnCount) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  return sheet.getRange(2, 1, lastRow - 1, columnCount).getValues();
}

/** 企業マスタの企業ID列(2行目から最後の行まで)を、空欄も含めて返す */
function readCompanyIdColumn_(sheet, idCol) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  return sheet.getRange(2, idCol, lastRow - 1, 1).getValues().map(function (row) { return row[0]; });
}

/**
 * 一時的なエラー(Google 側の失敗・混雑)のときだけ、少し待ってやり直す。権限・範囲の誤りなどはすぐに投げる。
 * 待ち時間の合計は retryState.waitedMs に足していき、上限(RETRY_BUDGET_MS)を超えるならやり直さない。
 * 同じ範囲に同じ値を書くので、やり直しても結果は同じ。
 */
function setValuesWithRetry_(range, values, retryState) {
  for (var attempt = 1; ; attempt++) {
    try {
      range.setValues(values);
      return;
    } catch (error) {
      var wait = GlowCompanyWriteGuard.retryWaitMs(error, attempt, retryState);
      if (wait < 0) throw error;
      Utilities.sleep(wait);
      retryState.waitedMs = (retryState.waitedMs || 0) + wait;
    }
  }
}

function flushSpreadsheet_() {
  if (typeof SpreadsheetApp.flush === "function") SpreadsheetApp.flush();
}

/**
 * 企業マスタの書き込みを止めたことを稼働状況タブに残し、通知してから例外を投げる。
 * 例外には companyWrite = { phase: "precheck" | "write" | "verify", dataChanged } を付ける
 * (呼び出し側はエラーの文言ではなく、これを見て後の処理を止めるかを決める)。
 */
function failCompanyWrite_(phase, dataChanged, message) {
  try {
    recordOpsStatus_("企業マスタの書き込み", false, message);
    notifyOpsFailure_("企業マスタの書き込み", message +
      "\n\n今朝のバックアップ(GLOW企業リレーション台帳_バックアップ_日付)と企業マスタの件数を比べてください。");
  } catch (notifyError) {
    Logger.log("企業マスタの書き込みの失敗を記録・通知できませんでした: " + notifyError);
  }
  var error = new Error("企業マスタの書き込みを止めました。" + message);
  error.companyWrite = { phase: phase, dataChanged: !!dataChanged };
  throw error;
}
