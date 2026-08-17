/**
 * GLOW企業リレーション台帳: 現場訪問ログ LINE音声記録
 *
 * LINE公式アカウント(GLOW実務チーム専用、新規開設)に音声メッセージを送ると、
 * Gemini APIで文字起こし・構造化データ抽出を行い、LINE上のボタン操作で確認・確定
 * したうえで対応履歴ログ(必要なら企業マスタ)に反映する。設計書:
 * docs/superpowers/specs/2026-08-17-glow-ma-line-voice-log-design.md
 *
 * セットアップ(人間が一度だけ行う):
 * 1. LINE Developersコンソールで新規のMessaging APIチャネル(GLOW実務チーム専用)を作成する
 * 2. 発行されたチャネルアクセストークンを、スクリプト プロパティ LINE_CHANNEL_ACCESS_TOKEN に設定する
 * 3. チャネルID(Basic settingsページのChannel ID)を、スクリプト プロパティ LINE_CHANNEL_ID に設定する
 * 4. Gemini APIキーを、スクリプト プロパティ GEMINI_API_KEY に設定する
 * 5. `clasp push` した後、既存のWeb Appデプロイ(TRACKING_BASE_URLに設定済みのURL)を、
 *    LINE DevelopersコンソールのWebhook URLに設定し、Webhookを有効化する
 *    (doGetとdoPostは同じWeb AppのURLを共有するため、新しいデプロイは不要)
 * 6. スタッフがLINE公式アカウントに最初の音声を送ると、「担当者が特定できませんでした」
 *    と返信される。その時点の実行ログ(Apps Scriptエディタの「実行数」画面)から
 *    LINEユーザーIDを確認し、「スタッフ」タブの該当行の「LINE User ID」列へ手動で転記する
 * 7. installVoiceLogProcessingTrigger を1度だけ実行し、1分おきの処理トリガーを登録する
 *    (Task 6で追加)
 *
 * セキュリティ上の注意: Apps ScriptのdoPostはHTTPヘッダーを読み取れないため、
 * LINEの署名(X-Line-Signature)による暗号学的な検証はできない。代わりに、
 * Webhookリクエスト本文のdestinationフィールドが自チャネルID(LINE_CHANNEL_ID)と
 * 一致するかを確認する形式チェックのみで防御する(設計書5章参照)。
 */
function doPost(e) {
  var body = parseLineWebhookBody_(e);
  if (!body) return ContentService.createTextOutput("");

  var expectedChannelId = PropertiesService.getScriptProperties().getProperty("LINE_CHANNEL_ID");
  if (!expectedChannelId || body.destination !== expectedChannelId) {
    Logger.log("LINE Webhookの形式チェックに失敗しました(destination不一致)。リクエストを破棄します。");
    return ContentService.createTextOutput("");
  }

  (body.events || []).forEach(function (event) {
    try {
      handleLineEvent_(event);
    } catch (error) {
      Logger.log("LINEイベントの処理に失敗しました: " + error);
    }
  });
  return ContentService.createTextOutput("");
}

function parseLineWebhookBody_(e) {
  if (!e || !e.postData || !e.postData.contents) return null;
  try {
    return JSON.parse(e.postData.contents);
  } catch (error) {
    Logger.log("LINE Webhookの本文をJSONとして解析できませんでした: " + error);
    return null;
  }
}

/**
 * 音声メッセージのみをこの時点で処理する。postback(ボタン操作)の処理はTask 7で
 * この関数に分岐を追加する。
 */
function handleLineEvent_(event) {
  if (event.type === "message" && event.message && event.message.type === "audio") {
    handleAudioMessage_(event);
  }
}

/**
 * 音声メッセージ受信時の処理。担当者の特定・多重処理の防止までをこの場で行い、
 * 実際の文字起こし・要約は時間主導トリガー(processQueuedVoiceLogs、Task 6)に委ねる
 * (LINEの応答時間制限に対応するため、doPost内では重い処理をしない)。
 */
function handleAudioMessage_(event) {
  var lineUserId = event.source && event.source.userId;
  var replyToken = event.replyToken;
  if (!lineUserId || !replyToken) return;

  var ss = SpreadsheetApp.getActiveSpreadsheet();

  if (hasInFlightProcess_(ss, lineUserId)) {
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildAlreadyProcessingMessage()]);
    return;
  }

  var staffName = resolveStaffNameByLineUserId_(ss, lineUserId);
  if (!staffName) {
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildStaffNotFoundMessage()]);
    return;
  }

  var processId = "P-" + Utilities.getUuid();
  var receivedAt = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm");
  appendVoiceLogRow_(ss, [
    processId, lineUserId, event.message.id, "受信済み",
    receivedAt, "", "", "", "", "", "", ""
  ]);
  lineReply_(replyToken, [GlowLineVoiceLogContent.ACK_MESSAGE_TEXT]);
}

/**
 * 「スタッフ」タブのLINE User ID列から、有効な担当者の氏名を逆引きする。
 * 見つからない場合(未登録・無効化済み)はnullを返す。
 */
function resolveStaffNameByLineUserId_(ss, lineUserId) {
  var sheet = ss.getSheetByName(GlowSchema.STAFF_SHEET_NAME);
  if (!sheet) return null;
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return null;
  var headers = GlowSchema.STAFF_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var nameIndex = headers.indexOf("氏名");
  var activeIndex = headers.indexOf("有効");
  var lineIdIndex = headers.indexOf("LINE User ID");
  for (var i = 0; i < values.length; i++) {
    var row = values[i];
    if (row[activeIndex] === true && row[lineIdIndex] === lineUserId && row[nameIndex]) {
      return row[nameIndex];
    }
  }
  return null;
}

/**
 * 「音声ログ処理状況」タブの全行を、ヘッダー名をキーとしたオブジェクトの配列として読む。
 * 各オブジェクトにはスプレッドシート上の実際の行番号(1始まり)をsheetRowとして含める
 * (Task 6・7の更新処理で使う)。
 */
function readVoiceLogRows_(ss) {
  var sheet = ss.getSheetByName(GlowSchema.LINE_VOICE_LOG_SHEET_NAME);
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.LINE_VOICE_LOG_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  return values.map(function (row, index) {
    var record = { sheetRow: index + 2 };
    headers.forEach(function (header, colIndex) { record[header] = row[colIndex]; });
    return record;
  });
}

/**
 * 指定したLINEユーザーIDについて、まだ確定・破棄・エラーになっていない
 * (=処理中の)音声ログが既にあるかを判定する。
 */
function hasInFlightProcess_(ss, lineUserId) {
  var inProgressStatuses = ["受信済み", "文字起こし済み", "企業選択待ち", "新規企業確認待ち", "最終確認待ち"];
  return readVoiceLogRows_(ss).some(function (record) {
    return record["LINEユーザーID"] === lineUserId && inProgressStatuses.indexOf(record["ステータス"]) !== -1;
  });
}

function appendVoiceLogRow_(ss, rowValues) {
  var sheet = ss.getSheetByName(GlowSchema.LINE_VOICE_LOG_SHEET_NAME);
  if (!sheet) {
    throw new Error("「" + GlowSchema.LINE_VOICE_LOG_SHEET_NAME + "」タブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    throw new Error("音声ログ処理状況タブのロック取得に失敗しました。");
  }
  try {
    var nextRow = sheet.getLastRow() + 1;
    sheet.getRange(nextRow, 1, 1, GlowSchema.LINE_VOICE_LOG_HEADERS.length).setValues([rowValues]);
  } finally {
    lock.releaseLock();
  }
}

/**
 * 「音声ログ処理状況」タブの指定行を部分更新する。updatesは{列名: 値}のオブジェクト。
 * ロック取得に失敗した場合は、例外を投げず警告ログのみ出す(呼び出し元の処理を
 * 止めないため。更新できなかった行は次回のprocessQueuedVoiceLogs実行で再度拾われうる)。
 */
function updateVoiceLogRow_(ss, sheetRow, updates) {
  var sheet = ss.getSheetByName(GlowSchema.LINE_VOICE_LOG_SHEET_NAME);
  if (!sheet) return;
  var headers = GlowSchema.LINE_VOICE_LOG_HEADERS;
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    Logger.log("音声ログ処理状況タブのロック取得に失敗したため更新をスキップしました(行" + sheetRow + ")。");
    return;
  }
  try {
    Object.keys(updates).forEach(function (key) {
      var colIndex = headers.indexOf(key);
      if (colIndex === -1) return;
      sheet.getRange(sheetRow, colIndex + 1).setValue(updates[key]);
    });
  } finally {
    lock.releaseLock();
  }
}

/**
 * GlowLineVoiceLogContentが返す{text}または{text, options}構造を、LINEの
 * メッセージJSON形式(テキスト、必要ならquickReply付き)に変換する。
 */
function buildLineMessagePayload_(spec) {
  if (typeof spec === "string") {
    return { type: "text", text: spec };
  }
  var message = { type: "text", text: spec.text };
  if (spec.options && spec.options.length > 0) {
    message.quickReply = {
      items: spec.options.map(function (option) {
        return {
          type: "action",
          action: { type: "postback", label: option.label, data: option.data, displayText: option.label }
        };
      })
    };
  }
  return message;
}

function lineReply_(replyToken, specs) {
  var token = PropertiesService.getScriptProperties().getProperty("LINE_CHANNEL_ACCESS_TOKEN");
  if (!token) {
    Logger.log("LINE_CHANNEL_ACCESS_TOKEN が未設定のため、LINEへの返信を送れませんでした。");
    return;
  }
  var messages = specs.map(buildLineMessagePayload_);
  var response = UrlFetchApp.fetch("https://api.line.me/v2/bot/message/reply", {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "Bearer " + token },
    payload: JSON.stringify({ replyToken: replyToken, messages: messages }),
    muteHttpExceptions: true
  });
  var responseCode = response.getResponseCode();
  if (responseCode < 200 || responseCode >= 300) {
    Logger.log("LINEへの返信送信に失敗しました(HTTP " + responseCode + "): " + response.getContentText());
  }
}
