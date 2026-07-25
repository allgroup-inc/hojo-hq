/* ノビシロ 診断商品バックエンド GASグルーコード
 * GAS固有API(UrlFetchApp/SpreadsheetApp/PropertiesService/MailApp/Utilities)に依存する。
 * Node環境では実行できないため、ユニットテストはない(node --checkで構文のみ検証)。
 * 純粋ロジックは Logic.gs(NBBackendLogic)を参照。
 *
 * デプロイ後のWeb App URLは2つの用途で使う(クエリパラメータtypeで振り分け):
 *   ?type=submit  … このサイトのフロントからのフォーム送信
 *   ?type=webhook&token=<秘密トークン> … StripeのWebhook登録先
 * GASのdoPost(e)はHTTPヘッダーを公開しないため、Stripeの署名検証(Stripe-Signature
 * ヘッダー)は実装できない。代わりにWebhook登録URLに埋め込んだ秘密トークンで認証する。
 */

var COLUMN = {
  diagnosisId: 1,
  timestamp: 2,
  answersJson: 3,
  email: 4,
  paymentStatus: 5,
  stripeSessionId: 6,
  reportStatus: 7,
  sentAt: 8,
};

function doPost(e) {
  var type = e.parameter.type;
  if (type === "submit") {
    return handleSubmit(e);
  }
  if (type === "webhook") {
    return handleStripeWebhook(e);
  }
  return jsonResponse({ error: "unknown_type" });
}

function jsonResponse(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function getLeadSheet() {
  var sheetId = PropertiesService.getScriptProperties().getProperty("SHEET_ID");
  return SpreadsheetApp.openById(sheetId).getSheetByName("リード台帳");
}

function handleSubmit(e) {
  var body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonResponse({ error: "invalid_json" });
  }

  var validation = NBBackendLogic.validateSubmission(body.answers);
  if (!validation.valid) {
    return jsonResponse({ error: "validation_failed", details: validation.errors });
  }

  var diagnosisId = Utilities.getUuid();
  var sheet = getLeadSheet();
  sheet.appendRow([
    diagnosisId,
    new Date().toISOString(),
    JSON.stringify(body.answers),
    body.answers.email,
    "pending",
    "",
    "not_sent",
    "",
  ]);

  var session = createStripeCheckoutSession(diagnosisId, body.answers.email);
  if (!session || !session.url) {
    return jsonResponse({ error: "stripe_session_failed" });
  }
  return jsonResponse({ url: session.url });
}

function createStripeCheckoutSession(diagnosisId, email) {
  var props = PropertiesService.getScriptProperties();
  var secretKey = props.getProperty("STRIPE_SECRET_KEY");
  var baseUrl = props.getProperty("SITE_BASE_URL");

  var payload = {
    "payment_method_types[0]": "card",
    "line_items[0][price_data][currency]": "jpy",
    "line_items[0][price_data][product_data][name]": "ノビシロ AI活用診断レポート",
    "line_items[0][price_data][unit_amount]": String(NBBackendLogic.PRICE_YEN),
    "line_items[0][quantity]": "1",
    mode: "payment",
    success_url: baseUrl + "/shindan/complete/?session_id={CHECKOUT_SESSION_ID}",
    cancel_url: baseUrl + "/shindan/",
    client_reference_id: diagnosisId,
    customer_email: email,
  };

  try {
    var response = UrlFetchApp.fetch("https://api.stripe.com/v1/checkout/sessions", {
      method: "post",
      headers: { Authorization: "Bearer " + secretKey },
      payload: payload,
      muteHttpExceptions: true,
    });
    return JSON.parse(response.getContentText());
  } catch (err) {
    return null;
  }
}

function handleStripeWebhook(e) {
  var expectedToken = PropertiesService.getScriptProperties().getProperty("WEBHOOK_TOKEN");
  if (!NBBackendLogic.isValidWebhookToken(e.parameter.token, expectedToken)) {
    return jsonResponse({ error: "invalid_token" });
  }

  var stripeEvent;
  try {
    stripeEvent = JSON.parse(e.postData.contents);
  } catch (err) {
    return jsonResponse({ error: "invalid_json" });
  }

  if (stripeEvent.type !== "checkout.session.completed") {
    return jsonResponse({ ok: true, ignored: true });
  }

  var session = stripeEvent.data.object;
  var diagnosisId = session.client_reference_id;
  var row = findRowByDiagnosisId(diagnosisId);
  if (!row) {
    return jsonResponse({ error: "diagnosis_not_found" });
  }

  if (row.values[COLUMN.reportStatus - 1] === "sent") {
    return jsonResponse({ ok: true, duplicate: true });
  }

  updateRowField(row.rowIndex, COLUMN.paymentStatus, "paid");
  updateRowField(row.rowIndex, COLUMN.stripeSessionId, session.id);

  try {
    var answers = JSON.parse(row.values[COLUMN.answersJson - 1]);
    var reportText = generateReport(answers);
    var html = NBBackendLogic.buildReportEmailHtml(reportText, answers);
    MailApp.sendEmail({
      to: row.values[COLUMN.email - 1],
      subject: "【ノビシロ】AI活用診断レポートが届きました",
      htmlBody: html,
    });
    updateRowField(row.rowIndex, COLUMN.reportStatus, "sent");
    updateRowField(row.rowIndex, COLUMN.sentAt, new Date().toISOString());
  } catch (err) {
    // 決済は完了しているので行は残す。カチカクくんが日次で "paid_pending_report" 相当を確認し手動フォローする
    var errMessage = (err && err.message) ? err.message : String(err);
    updateRowField(row.rowIndex, COLUMN.reportStatus, "failed: " + errMessage);
  }

  return jsonResponse({ ok: true });
}

function findRowByDiagnosisId(diagnosisId) {
  var sheet = getLeadSheet();
  var values = sheet.getDataRange().getValues();
  for (var i = 0; i < values.length; i++) {
    if (values[i][COLUMN.diagnosisId - 1] === diagnosisId) {
      return { rowIndex: i + 1, values: values[i] };
    }
  }
  return null;
}

function updateRowField(rowIndex, column, value) {
  getLeadSheet().getRange(rowIndex, column).setValue(value);
}

function generateReport(answers) {
  var apiKey = PropertiesService.getScriptProperties().getProperty("ANTHROPIC_API_KEY");
  var prompt = NBBackendLogic.buildReportPrompt(answers);
  var response = UrlFetchApp.fetch("https://api.anthropic.com/v1/messages", {
    method: "post",
    contentType: "application/json",
    headers: { "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
    payload: JSON.stringify({
      model: "claude-sonnet-5",
      max_tokens: 2048,
      messages: [{ role: "user", content: prompt }],
    }),
    muteHttpExceptions: true,
  });
  var data = JSON.parse(response.getContentText());
  if (data.error) {
    throw new Error("Claude API error: " + (data.error.message || JSON.stringify(data.error)));
  }
  if (!data.content || !data.content[0] || !data.content[0].text) {
    throw new Error("Claude API returned unexpected response shape: " + response.getContentText());
  }
  return data.content[0].text;
}
