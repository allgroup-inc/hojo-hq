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
