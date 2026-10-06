/**
 * LINE Webhook Handler for Automatic Reply Message (会社情報登録)
 *
 * 背景: LINE Official Account Manager の自動応答メッセージが手動設定に頼っているため、
 * Webhook経由で自動応答を実装し、メッセージの自動化・バージョン管理を実現。
 *
 * 配置場所: Google Apps Script プロジェクト内 Apps Script Editor
 * デプロイ: 「新しいデプロイ」→ 「ウェブアプリ」→ 実行ユーザー「ウェブアプリケーションにアクセスしているユーザー」
 * Webhook URL: デプロイの実行URLを LINE Channel Settings の Message API → Webhook URL に登録
 */

// ========== 環境設定 ==========
const LINE_CHANNEL_ACCESS_TOKEN = PropertiesService.getScriptProperties().getProperty('LINE_CHANNEL_ACCESS_TOKEN');
const LINE_REPLY_ENDPOINT = 'https://api.line.biz/v2/bot/message/reply';

// 登録確認メッセージテンプレート
const COMPANY_REGISTRATION_REPLY = `ありがとうございます。以下の情報で承りました:

【登録済み情報】
企業名: {company_name}
代表者: {representative}
所在地: {location}
電話: {phone}

【今後のお知らせ】
毎週、貴社に合った制度をお知らせします
締切の約1か月前に個別アラート
気になる制度は星マークで保存できます

1営業日以内に担当よりご連絡します。
ご質問やご相談があればお気軽にどうぞ。`;

// ========== Webhook エントリーポイント ==========
function doPost(e) {
  if (!e || !e.postData) {
    return sendResponse_(400, 'Invalid request');
  }

  try {
    const event = JSON.parse(e.postData.contents);

    // Webhook 署名検証（本番環境では必須）
    const signature = e.parameter['X-Line-Signature'];
    if (!verifySignature_(e.postData.contents, signature)) {
      console.warn('[warning] Signature verification failed');
      // 本番では return sendResponse_(403, 'Unauthorized');
    }

    // メッセージイベント処理
    if (event.events && Array.isArray(event.events)) {
      event.events.forEach(evt => {
        handleEvent_(evt);
      });
    }

    return sendResponse_(200, 'OK');
  } catch (error) {
    console.error('[error] Webhook processing failed:', error);
    return sendResponse_(500, 'Internal server error');
  }
}

// ========== イベント処理 ==========
function handleEvent_(event) {
  if (event.type !== 'message') {
    console.log('[info] Skipping non-message event:', event.type);
    return;
  }

  const message = event.message;
  if (message.type !== 'text') {
    console.log('[info] Skipping non-text message');
    return;
  }

  // 「【会社情報登録】」で始まるメッセージを検出
  if (!message.text.startsWith('【会社情報登録】')) {
    console.log('[info] Message does not match company registration pattern');
    return;
  }

  console.log('[info] Company registration detected:', message.text);

  // 登録情報をパース（フォーマット例: 【会社情報登録】\n企業名: xxx\n代表者: yyy\n...）
  const registrationData = parseRegistrationMessage_(message.text);
  console.log('[info] Parsed registration:', JSON.stringify(registrationData));

  // 改善されたメッセージを送信
  const replyMessage = buildReplyMessage_(registrationData);
  replyMessage_(event.replyToken, replyMessage);

  // イベントログを記録
  logEvent_(event, registrationData);
}

// ========== メッセージ処理関数 ==========
function parseRegistrationMessage_(text) {
  const result = {
    company_name: '(確認中)',
    representative: '(確認中)',
    location: '(確認中)',
    phone: '(確認中)'
  };

  // 各フィールドを抽出（単純な行分割パース）
  const lines = text.split('\n');
  lines.forEach(line => {
    if (line.includes('企業名:') || line.includes('会社名:')) {
      result.company_name = line.split(':')[1]?.trim() || result.company_name;
    } else if (line.includes('代表者:') || line.includes('代表:')) {
      result.representative = line.split(':')[1]?.trim() || result.representative;
    } else if (line.includes('所在地:') || line.includes('所在:') || line.includes('市町村:')) {
      result.location = line.split(':')[1]?.trim() || result.location;
    } else if (line.includes('電話:') || line.includes('TEL:') || line.includes('tel:')) {
      result.phone = line.split(':')[1]?.trim() || result.phone;
    }
  });

  return result;
}

function buildReplyMessage_(data) {
  return COMPANY_REGISTRATION_REPLY
    .replace('{company_name}', data.company_name || '[会社名]')
    .replace('{representative}', data.representative || '[代表者名]')
    .replace('{location}', data.location || '[市町村]')
    .replace('{phone}', data.phone || '[電話番号]');
}

function replyMessage_(replyToken, messageText) {
  if (!LINE_CHANNEL_ACCESS_TOKEN) {
    console.error('[error] LINE_CHANNEL_ACCESS_TOKEN not configured');
    return false;
  }

  try {
    const payload = {
      replyToken: replyToken,
      messages: [
        {
          type: 'text',
          text: messageText
        }
      ]
    };

    const options = {
      method: 'post',
      headers: {
        'Authorization': 'Bearer ' + LINE_CHANNEL_ACCESS_TOKEN,
        'Content-Type': 'application/json'
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };

    const response = UrlFetchApp.fetch(LINE_REPLY_ENDPOINT, options);
    const status = response.getResponseCode();

    if (status === 200) {
      console.log('[success] Reply sent');
      return true;
    } else {
      console.error('[error] LINE API error:', status, response.getContentText());
      return false;
    }
  } catch (error) {
    console.error('[error] Failed to send reply:', error);
    return false;
  }
}

// ========== Webhook 署名検証 ==========
function verifySignature_(body, signature) {
  const secret = PropertiesService.getScriptProperties().getProperty('LINE_CHANNEL_SECRET');
  if (!secret) {
    console.warn('[warning] LINE_CHANNEL_SECRET not configured');
    return false;
  }

  try {
    const computed = Utilities.computeHmacSha256Signature(body, secret);
    const expected = Utilities.base64Encode(computed);
    return expected === signature;
  } catch (error) {
    console.error('[error] Signature verification error:', error);
    return false;
  }
}

// ========== ロギング・レスポンス ==========
function logEvent_(event, data) {
  const timestamp = new Date().toISOString();
  const sheet = getOrCreateLogSheet_();

  sheet.appendRow([
    timestamp,
    event.timestamp,
    event.source.type,
    event.source.userId || 'unknown',
    data.company_name,
    data.representative,
    data.location,
    data.phone,
    'processed'
  ]);
}

function getOrCreateLogSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('LINE_Webhook_Log');

  if (!sheet) {
    sheet = ss.insertSheet('LINE_Webhook_Log');
    sheet.appendRow([
      'Timestamp (JST)',
      'Event Timestamp',
      'Source Type',
      'Line User ID',
      'Company Name',
      'Representative',
      'Location',
      'Phone',
      'Status'
    ]);
  }

  return sheet;
}

function sendResponse_(statusCode, message) {
  return ContentService
    .createTextOutput(JSON.stringify({
      statusCode: statusCode,
      message: message
    }))
    .setMimeType(ContentService.MimeType.JSON);
}

// ========== テスト・デバッグ用 ==========
function testReplyMessage() {
  const testData = {
    company_name: '株式会社テスト',
    representative: '田中太郎',
    location: '沖縄県那覇市',
    phone: '098-123-4567'
  };

  const message = buildReplyMessage_(testData);
  Logger.log('[test] Generated message:');
  Logger.log(message);
}
