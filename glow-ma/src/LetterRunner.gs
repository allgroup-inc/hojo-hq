/**
 * GLOW企業リレーション台帳: レター下書き生成(Claude API)
 *
 * 使い方:
 * 1. Apps Scriptエディタの「プロジェクトの設定」→「スクリプト プロパティ」で
 *    ANTHROPIC_API_KEY を設定する(コードにAPIキーを直接書かない)
 * 2. TRACKING_BASE_URL(Task 7でデプロイするWeb AppのURL)も同様に設定する
 *    (未設定の場合、トラッキングURLなしで下書きが生成される)
 * 3. 1社分だけ生成したい場合は、Apps Scriptエディタでこのファイルの末尾に
 *    一時的に `generateLetterDraftForCompany("C000001");` のような呼び出し行を足して実行する
 * 4. ナーチャリング対象全件分をまとめて生成する場合は generateNurturingDraftsForEligibleCompanies
 *    を実行する
 *
 * 生成された下書きは「レター下書き」タブに追記される。ステータスは常に
 * 「下書き」で作成され、自動送信は行わない。必ず人が内容を確認してから送付すること。
 */
function generateLetterDraftForCompany(companyId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var records = readCompanyRecords_(companySheet);
  var record = records.filter(function (r) { return r["企業ID"] === companyId; })[0];
  if (!record) {
    throw new Error("企業ID " + companyId + " が企業マスタに見つかりません。");
  }
  if (record["連絡不要"] === true) {
    throw new Error("企業ID " + companyId + " は「連絡不要」に設定されているため、レター下書きを生成できません。");
  }
  writeLetterDraft_(record, GlowSchema.LETTER_DRAFT_TYPES[0]);
  Logger.log("レター下書きを生成しました: " + companyId);
}

function generateNurturingDraftsForEligibleCompanies() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var records = readCompanyRecords_(companySheet);
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var targets = GlowLetterContent.selectNurturingTargets(records, todayString);
  var generatedCount = 0;
  var skippedCount = 0;
  targets.forEach(function (record) {
    if (hasRecentNurturingDraft_(record["企業ID"], todayString)) {
      skippedCount++;
      return;
    }
    writeLetterDraft_(record, GlowSchema.LETTER_DRAFT_TYPES[1]);
    generatedCount++;
  });
  Logger.log("ナーチャリング下書き生成完了: " + generatedCount + "件(直近生成済みのためスキップ: " + skippedCount + "件)");
}

/**
 * 直近 GlowLetterContent.DEFAULT_CONFIG.nurturing.minIntervalDays 日以内に
 * 同じ企業へのナーチャリング配信下書きが既に生成されていないかを確認する。
 * generateNurturingDraftsForEligibleCompanies を複数回実行しても、同じ企業に対して
 * 毎回新しい下書き(と新しいClaude API呼び出し)が発生しないようにするための冪等化。
 */
function hasRecentNurturingDraft_(companyId, todayString) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var draftSheet = ss.getSheetByName(GlowSchema.LETTER_DRAFT_SHEET_NAME);
  if (!draftSheet) return false;
  var lastRow = draftSheet.getLastRow();
  if (lastRow < 2) return false;
  var headers = GlowSchema.LETTER_DRAFT_HEADERS;
  var values = draftSheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var companyIdIndex = headers.indexOf("企業ID");
  var typeIndex = headers.indexOf("種別");
  var generatedAtIndex = headers.indexOf("生成日時");
  var minIntervalDays = GlowLetterContent.DEFAULT_CONFIG.nurturing.minIntervalDays;
  for (var i = 0; i < values.length; i++) {
    var row = values[i];
    if (row[companyIdIndex] !== companyId) continue;
    if (row[typeIndex] !== GlowSchema.LETTER_DRAFT_TYPES[1]) continue;
    var generatedDate = String(row[generatedAtIndex]).split(" ")[0];
    var days = GlowAlerting.daysBetween(generatedDate, todayString);
    if (days !== null && days < minIntervalDays) return true;
  }
  return false;
}

function writeLetterDraft_(record, draftType) {
  var baseUrl = PropertiesService.getScriptProperties().getProperty("TRACKING_BASE_URL");
  var trackingUrl = baseUrl ? GlowLetterContent.buildTrackingUrl(record["企業ID"], baseUrl) : "";
  var prompt = GlowLetterContent.buildLetterPrompt(record, trackingUrl);
  var draftBody = callClaudeApi_(prompt);

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var draftSheet = ss.getSheetByName(GlowSchema.LETTER_DRAFT_SHEET_NAME);
  if (!draftSheet) {
    throw new Error("レター下書きタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error(
      "他の処理がレター下書きタブを操作中のため、下書きの書き込みができませんでした。" +
      "生成された文面は保存されていません。しばらく待ってから再実行してください。"
    );
  }
  try {
    var nextRow = draftSheet.getLastRow() + 1;
    var draftId = "D-" + Utilities.getUuid();
    var generatedAt = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm");
    draftSheet.getRange(nextRow, 1, 1, GlowSchema.LETTER_DRAFT_HEADERS.length).setValues([[
      draftId, record["企業ID"], draftType, generatedAt, draftBody, "下書き"
    ]]);
  } finally {
    lock.releaseLock();
  }

  if (draftType === GlowSchema.LETTER_DRAFT_TYPES[1]) {
    appendNurturingInteractionLog_(record["企業ID"]);
  }
}

/**
 * ナーチャリング配信の下書きを生成したことを対応履歴ログに記録する
 * (設計書11章: ナーチャリング配信は対応履歴ログに種別「ナーチャリング配信」として残すこと)。
 */
function appendNurturingInteractionLog_(companyId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  if (!logSheet) return;
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    Logger.log("対応履歴ログのロック取得に失敗したため、ナーチャリング配信の記録をスキップしました: " + companyId);
    return;
  }
  try {
    var nextRow = logSheet.getLastRow() + 1;
    var logId = "H-" + Utilities.getUuid();
    var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
    logSheet.getRange(nextRow, 1, 1, GlowSchema.INTERACTION_LOG_HEADERS.length).setValues([[
      logId, companyId, todayString, "システム(自動記録)", GlowSchema.LETTER_DRAFT_TYPES[1], "未接触",
      "ナーチャリング下書きを生成", ""
    ]]);
  } finally {
    lock.releaseLock();
  }
}

function callClaudeApi_(prompt) {
  var apiKey = PropertiesService.getScriptProperties().getProperty("ANTHROPIC_API_KEY");
  if (!apiKey) {
    throw new Error("ANTHROPIC_API_KEY が未設定です。スクリプト プロパティで設定してください。");
  }
  var response = UrlFetchApp.fetch("https://api.anthropic.com/v1/messages", {
    method: "post",
    contentType: "application/json",
    headers: {
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01"
    },
    payload: JSON.stringify({
      model: "claude-sonnet-5",
      max_tokens: 1024,
      messages: [{ role: "user", content: prompt }]
    }),
    muteHttpExceptions: true
  });
  var responseCode = response.getResponseCode();
  if (responseCode < 200 || responseCode >= 300) {
    throw new Error("Claude APIの呼び出しに失敗しました(ステータスコード " + responseCode + "): " + response.getContentText());
  }
  var body = JSON.parse(response.getContentText());
  return body.content && body.content[0] && body.content[0].text ? body.content[0].text : "";
}
