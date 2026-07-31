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
  writeLetterDraft_(record, "初回DM");
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
  targets.forEach(function (record) {
    writeLetterDraft_(record, "ナーチャリング配信");
  });
  Logger.log("ナーチャリング下書き生成完了: " + targets.length + "件");
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
  var nextRow = draftSheet.getLastRow() + 1;
  var draftId = "D-" + Utilities.getUuid();
  var generatedAt = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm");
  draftSheet.getRange(nextRow, 1, 1, GlowSchema.LETTER_DRAFT_HEADERS.length).setValues([[
    draftId, record["企業ID"], draftType, generatedAt, draftBody, "下書き"
  ]]);
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
