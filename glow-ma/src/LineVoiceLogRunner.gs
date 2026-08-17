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
 * 3. Botのユーザー ID(`U`から始まる32文字の英数字)を、スクリプト プロパティ
 *    LINE_BOT_USER_ID に設定する。
 *    Botのユーザー ID(`U`から始まる32文字の英数字)を取得するには、LINE Developers
 *    コンソールの「Messaging API設定」タブに表示されるBot basic IDの下、または
 *    LINE Messaging APIの`GET https://api.line.me/v2/bot/info`エンドポイント
 *    (Authorizationヘッダーにチャネルアクセストークンを付与して呼び出す)のレスポンスの
 *    `userId`フィールドで確認できる。Basic settingsページの「チャネルID」(数字のみ)とは
 *    別物なので注意すること。
 * 4. Gemini APIキーを、スクリプト プロパティ GEMINI_API_KEY に設定する
 * 5. `clasp push` した後、既存のWeb Appデプロイ(TRACKING_BASE_URLに設定済みのURL)を、
 *    LINE DevelopersコンソールのWebhook URLに設定し、Webhookを有効化する
 *    (doGetとdoPostは同じWeb AppのURLを共有するため、新しいURL/新規デプロイの作成は不要)
 *    ただし、`/exec` のURLは「デプロイ済みのバージョン」を固定で配信するため、
 *    **`clasp push` しただけでは新しいコードはそのURLに反映されない**。本機能のコードを
 *    変更して push するたびに、Apps Scriptエディタの
 *    デプロイ → デプロイを管理 → (既存のデプロイ) → 編集(鉛筆アイコン) →
 *    バージョン: 新バージョン → デプロイ
 *    を実行して、既存デプロイを新しいバージョンへ更新すること(URL自体は変わらない)
 * 6. スタッフがLINE公式アカウントに最初の音声を送ると、「担当者が特定できませんでした」
 *    と返信される。その時点の実行ログ(Apps Scriptエディタの「実行数」画面)から
 *    LINEユーザーIDを確認し、「スタッフ」タブの該当行の「LINE User ID」列へ手動で転記する
 * 7. installVoiceLogProcessingTrigger を1度だけ実行し、1分おきの処理トリガーを登録する
 *
 * セキュリティ上の注意: Apps ScriptのdoPostはHTTPヘッダーを読み取れないため、
 * LINEの署名(X-Line-Signature)による暗号学的な検証はできない。代わりに、
 * Webhookリクエスト本文のdestinationフィールド(=Bot自身のユーザーID)が
 * LINE_BOT_USER_IDと一致するかを確認する形式チェックのみで防御する(設計書5章参照)。
 */

/** LINEのBotユーザーID(destinationフィールド)の形式。`U`+32桁の16進数。 */
var LINE_BOT_USER_ID_PATTERN = /^U[0-9a-f]{32}$/i;

function doPost(e) {
  var body = parseLineWebhookBody_(e);
  if (!body) return ContentService.createTextOutput("");

  var expectedBotUserId = PropertiesService.getScriptProperties().getProperty("LINE_BOT_USER_ID");
  if (!expectedBotUserId || !LINE_BOT_USER_ID_PATTERN.test(String(expectedBotUserId).trim())) {
    Logger.log(
      "LINE_BOT_USER_ID の形式が不正です(未設定、または`U`+32桁の英数字になっていません)。" +
      "Basic settingsページの数字だけの「チャネルID」ではなく、Messaging API設定タブまたは " +
      "GET https://api.line.me/v2/bot/info の userId を設定してください。リクエストを破棄します。"
    );
    return ContentService.createTextOutput("");
  }
  if (body.destination !== String(expectedBotUserId).trim()) {
    Logger.log("LINE Webhookの形式チェックに失敗しました(destination不一致)。リクエストを破棄します。");
    return ContentService.createTextOutput("");
  }

  (body.events || []).forEach(function (event) {
    try {
      debugLog_("doPost event received: type=" + event.type +
        " messageType=" + (event.message && event.message.type) +
        " userId=" + (event.source && event.source.userId) +
        " replyToken=" + event.replyToken);
      handleLineEvent_(event);
    } catch (error) {
      debugLog_("doPost event error: " + error);
      Logger.log("LINEイベントの処理に失敗しました: " + error);
    }
  });
  return ContentService.createTextOutput("");
}

/**
 * [一時的な動作確認用] 直近のイベント処理・LINE返信の結果をスクリプトプロパティ
 * LAST_DEBUG_LOG に書き込む。ブラウザの実行ログ画面が不安定なため、
 * Apps Scriptエディタの「プロジェクトの設定」→「スクリプト プロパティ」から
 * いつでも確認できるようにするための暫定対応。動作確認が終わったら削除すること。
 */
function debugLog_(message) {
  try {
    PropertiesService.getScriptProperties().setProperty(
      "LAST_DEBUG_LOG",
      Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm:ss") + " " + message
    );
  } catch (error) {
    // 確認用ログの書き込み失敗は無視する(本処理に影響させない)
  }
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
 * 音声メッセージとpostback(ボタン操作)の両方をここで振り分ける。
 */
function handleLineEvent_(event) {
  if (event.type === "message" && event.message && event.message.type === "audio") {
    withUserFacingErrorReply_(event.replyToken, function () { handleAudioMessage_(event); });
    return;
  }
  if (event.type === "postback") {
    withUserFacingErrorReply_(event.replyToken, function () { handleLinePostback_(event); });
    return;
  }
  // テキストメッセージ・フォロー等、音声・postback以外のイベントは今回のスコープ外のため無視する
}

/**
 * 予期しない例外(タブ不在・ロック取得失敗等)が起きたとき、doPost側のcatchはログを
 * 出すだけで担当者には何も返らない。送ったのに無反応という状態を避けるため、
 * イベント処理の最後の砦としてここでエラーメッセージを返す。
 * (返信トークンを既に使い切っている場合、この返信自体は失敗するがログに残る)
 */
function withUserFacingErrorReply_(replyToken, action) {
  try {
    action();
  } catch (error) {
    Logger.log("LINEイベントの処理に失敗しました: " + error);
    if (replyToken) {
      lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    }
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
  debugLog_("handleAudioMessage_: lineUserId=" + lineUserId + " staffName=" + staffName);
  try {
    PropertiesService.getScriptProperties().setProperty("LAST_LINE_USER_ID", lineUserId);
  } catch (error) {
    // 確認用ログの書き込み失敗は無視する(本処理に影響させない)
  }
  if (!staffName) {
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildStaffNotFoundMessage()]);
    return;
  }

  var processId = "P-" + Utilities.getUuid();
  var receivedAt = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm");
  // 行の追加に失敗した場合(タブ不在・ロック取得失敗等)、doPost側のcatchはログを出すだけで
  // 何も返信しない。担当者から見ると「送ったのに無反応」になるため、ここで捕捉して必ず返信する。
  try {
    appendVoiceLogRow_(ss, [
      processId, lineUserId, event.message.id, "受信済み",
      receivedAt, "", "", "", "", "", "", ""
    ]);
  } catch (error) {
    Logger.log("音声ログ処理状況タブへの受付行の追加に失敗しました: " + error);
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }
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
 * 1件の音声ログを1つの実行(トリガー or postback)が占有していることを示す一時ステータス。
 * 同じ行を複数の実行が同時に進めようとしたとき、最初に「処理中」へ書き換えられた
 * 実行だけが処理を続行できる(GlowSchema.LINE_VOICE_LOG_STATUSESにも定義済み)。
 */
var VOICE_LOG_STATUS_PROCESSING = "処理中";

/** まだ確定・破棄・エラーになっていない(=担当者の次の録音をブロックする)ステータス。 */
var VOICE_LOG_IN_PROGRESS_STATUSES = [
  "受信済み", VOICE_LOG_STATUS_PROCESSING, "文字起こし済み",
  "企業選択待ち", "新規企業確認待ち", "最終確認待ち"
];

/** 途中で放置された音声ログを自動的に取り消すまでの時間(2時間)。 */
var VOICE_LOG_STALE_THRESHOLD_MS = 2 * 60 * 60 * 1000;
var VOICE_LOG_STALE_ERROR_MESSAGE = "一定時間操作がなかったため自動的に取り消しました";

/**
 * 指定したLINEユーザーIDについて、まだ確定・破棄・エラーになっていない
 * (=処理中の)音声ログが既にあるかを判定する。
 */
function hasInFlightProcess_(ss, lineUserId) {
  return readVoiceLogRows_(ss).some(function (record) {
    return record["LINEユーザーID"] === lineUserId &&
      VOICE_LOG_IN_PROGRESS_STATUSES.indexOf(record["ステータス"]) !== -1;
  });
}

/**
 * 「音声ログ処理状況」タブの1行を、期待する現在ステータスであることを確認したうえで
 * アトミックに更新する。ロックを取得したまま現在値を再確認するため、複数の postback や
 * トリガー実行が同じ行を同時に進めようとしても、最初の1つだけが成功する。
 * 期待するステータスと一致しなければ何も書き換えず false を返す(呼び出し元は
 * 「既に処理済み」として案内する)。
 *
 * 注意: この関数はドキュメントロックを取得・解放する。ロックを保持したまま呼ぶと
 * 入れ子になるため、対応履歴ログ・企業マスタへの書き込みロックの外側で使うこと。
 */
function transitionVoiceLogStatus_(ss, sheetRow, expectedStatuses, updates) {
  var sheet = ss.getSheetByName(GlowSchema.LINE_VOICE_LOG_SHEET_NAME);
  if (!sheet) return false;
  var headers = GlowSchema.LINE_VOICE_LOG_HEADERS;
  var statusColIndex = headers.indexOf("ステータス");
  if (statusColIndex === -1) return false;

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error("音声ログ処理状況タブのロック取得に失敗しました。");
  }
  try {
    var currentStatus = sheet.getRange(sheetRow, statusColIndex + 1).getValue();
    if (expectedStatuses.indexOf(currentStatus) === -1) return false;
    Object.keys(updates).forEach(function (key) {
      var colIndex = headers.indexOf(key);
      if (colIndex === -1) return;
      sheet.getRange(sheetRow, colIndex + 1).setValue(updates[key]);
    });
    return true;
  } finally {
    lock.releaseLock();
  }
}

/**
 * transitionVoiceLogStatus_ の「エラーへ倒す」用途のラッパー。エラー処理の途中で
 * さらに例外を投げて元の失敗原因を隠さないよう、ロック取得失敗も握りつぶしてログに残す。
 */
function markVoiceLogAsError_(ss, sheetRow, expectedStatuses, errorMessage) {
  try {
    var moved = transitionVoiceLogStatus_(ss, sheetRow, expectedStatuses, {
      "ステータス": "エラー",
      "エラー内容": errorMessage
    });
    if (!moved) {
      Logger.log("音声ログをエラーに更新できませんでした(既に別のステータスに遷移済み。行" + sheetRow + ")。");
    }
    return moved;
  } catch (error) {
    Logger.log("音声ログのエラー更新に失敗しました(行" + sheetRow + "): " + error);
    return false;
  }
}

/**
 * 「受信日時」("yyyy-MM-dd HH:mm" 形式の文字列、またはスプレッドシートが自動変換した
 * Date値)をDateに戻す。解釈できない場合はnullを返す(放置検知の対象外として扱う)。
 * GlowAlerting.toDate は "yyyy-MM-dd" のみを想定しており時刻部分を解釈できないため、
 * ここで専用に処理する。
 */
function parseVoiceLogReceivedAt_(value) {
  if (value instanceof Date) return value;
  var matched = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/.exec(String(value || "").trim());
  if (!matched) return null;
  return new Date(
    Number(matched[1]), Number(matched[2]) - 1, Number(matched[3]),
    Number(matched[4]), Number(matched[5])
  );
}

/**
 * LINEへの返信・プッシュ送信が失敗しても例外は投げない(ログのみ)ため、確認ボタンが
 * 担当者に届かないまま行が途中ステータスで残ることがある。その状態を放置すると
 * hasInFlightProcess_ が永久にその担当者の次の録音をブロックしてしまうので、
 * 受信から2時間以上経過した途中ステータスの行を「エラー」に倒して詰まりを解消する。
 * 既に反応しなかった担当者へ追加のLINE通知はしない(通知の連打を避けるため)。
 */
function sweepStaleVoiceLogs_(ss) {
  var now = new Date().getTime();
  readVoiceLogRows_(ss).forEach(function (record) {
    if (VOICE_LOG_IN_PROGRESS_STATUSES.indexOf(record["ステータス"]) === -1) return;
    var receivedAt = parseVoiceLogReceivedAt_(record["受信日時"]);
    if (!receivedAt) {
      Logger.log("受信日時を解釈できないため放置検知の対象外としました(処理ID " + record["処理ID"] + ")。");
      return;
    }
    if (now - receivedAt.getTime() < VOICE_LOG_STALE_THRESHOLD_MS) return;
    var swept = markVoiceLogAsError_(
      ss, record.sheetRow, VOICE_LOG_IN_PROGRESS_STATUSES, VOICE_LOG_STALE_ERROR_MESSAGE
    );
    if (swept) {
      Logger.log("放置された音声ログを自動的に取り消しました(処理ID " + record["処理ID"] + ")。");
    }
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
  debugLog_("lineReply_: HTTP " + responseCode + " body=" + response.getContentText());
  if (responseCode < 200 || responseCode >= 300) {
    Logger.log("LINEへの返信送信に失敗しました(HTTP " + responseCode + "): " + response.getContentText());
  }
}

/**
 * processQueuedVoiceLogs をインストール型の時間主導トリガーとして1分間隔で登録する。
 * 冪等: 実行時にまず同じハンドラ関数を指す既存トリガーをすべて削除してから
 * 新規登録するため、重複登録を心配せずに安全に再実行できる(ShippingRunner.gsの
 * installLetterDraftEditTriggerと同じパターン)。
 */
function installVoiceLogProcessingTrigger() {
  var existingTriggers = ScriptApp.getProjectTriggers();
  existingTriggers.forEach(function (trigger) {
    if (trigger.getHandlerFunction() === "processQueuedVoiceLogs") {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  ScriptApp.newTrigger("processQueuedVoiceLogs")
    .timeBased()
    .everyMinutes(1)
    .create();
  Logger.log("音声ログ処理用の1分間隔トリガーを登録しました。");
}

/**
 * 「受信済み」ステータスの音声ログを1件ずつ処理する。1件の失敗が他の未処理分を
 * 止めないよう、失敗した行は「エラー」ステータスに更新し、次の行の処理を続ける
 * (LetterRunner.gs等と同じ障害隔離の方針)。
 *
 * 1分間隔のトリガーは、前回の実行(Gemini呼び出しとリトライで数十秒かかりうる)が
 * 終わる前に次の実行が始まりうる。同じ行を二重に処理してGemini費用とLINE通知を
 * 重複させないよう、処理の直前に transitionVoiceLogStatus_ で「受信済み → 処理中」の
 * 確保(claim)を行い、確保できた実行だけが先へ進む。
 */
function processQueuedVoiceLogs() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  try {
    sweepStaleVoiceLogs_(ss);
  } catch (error) {
    Logger.log("放置された音声ログの自動取り消しに失敗しました: " + error);
  }

  var pending = readVoiceLogRows_(ss).filter(function (record) { return record["ステータス"] === "受信済み"; });
  pending.forEach(function (record) {
    var claimed;
    try {
      claimed = transitionVoiceLogStatus_(
        ss, record.sheetRow, ["受信済み"], { "ステータス": VOICE_LOG_STATUS_PROCESSING }
      );
    } catch (error) {
      Logger.log("音声ログの確保に失敗しました(処理ID " + record["処理ID"] + "): " + error);
      return;
    }
    if (!claimed) {
      Logger.log("音声ログは既に別の実行が確保済みのためスキップしました(処理ID " + record["処理ID"] + ")。");
      return;
    }

    try {
      processOneVoiceLog_(ss, record);
    } catch (error) {
      Logger.log("音声ログの処理に失敗しました(処理ID " + record["処理ID"] + "): " + error);
      markVoiceLogAsError_(ss, record.sheetRow, VOICE_LOG_IN_PROGRESS_STATUSES, String(error));
      linePush_(record["LINEユーザーID"], [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    }
  });
}

/**
 * 呼び出し時点で当該行は「処理中」として確保済みであることが前提。
 * Geminiの抽出結果はスプレッドシートに書く前にサニタイズし(先頭の = + - @ を数式と
 * 解釈させない)、種別・対応相手は書き込み時と同じ正規化を通してから保存する
 * (担当者が確認画面で見た値と、対応履歴ログに実際に記録される値を一致させるため)。
 */
function processOneVoiceLog_(ss, record) {
  var audioBlob = fetchLineAudioContent_(record["LINEメッセージID"]);
  var extracted = callGeminiForVoiceLog_(audioBlob);

  var companyNameCandidate = GlowLineVoiceLogContent.sanitizeSheetText(extracted.companyName);
  var interactionType = GlowLineVoiceLogContent.normalizeInteractionType(extracted.interactionType);
  var respondentType = GlowLineVoiceLogContent.normalizeRespondentType(extracted.respondentType);
  var contentMemo = GlowLineVoiceLogContent.sanitizeSheetText(extracted.contentMemo);
  var nextAction = GlowLineVoiceLogContent.sanitizeSheetText(extracted.nextAction);

  var transcribed = transitionVoiceLogStatus_(ss, record.sheetRow, [VOICE_LOG_STATUS_PROCESSING], {
    "ステータス": "文字起こし済み",
    "会社名候補": companyNameCandidate,
    "種別候補": interactionType,
    "対応相手候補": respondentType,
    "内容メモ": contentMemo,
    "次回アクション": nextAction
  });
  if (!transcribed) {
    Logger.log("文字起こし結果の書き込み前に他の処理が状態を変更したため中断しました(処理ID " + record["処理ID"] + ")。");
    return;
  }

  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  var candidates = GlowLineVoiceLogContent.matchCompanyCandidates(companies, extracted.companyName);

  var pushSpecs;
  var moved;
  if (candidates.length === 1) {
    moved = transitionVoiceLogStatus_(ss, record.sheetRow, ["文字起こし済み"], {
      "ステータス": "最終確認待ち", "企業ID": candidates[0]["企業ID"]
    });
    pushSpecs = [GlowLineVoiceLogContent.buildFinalConfirmPrompt(
      record["処理ID"], candidates[0]["会社名"], interactionType, respondentType, contentMemo, nextAction
    )];
  } else if (candidates.length > 1) {
    moved = transitionVoiceLogStatus_(ss, record.sheetRow, ["文字起こし済み"], { "ステータス": "企業選択待ち" });
    pushSpecs = [GlowLineVoiceLogContent.buildCompanySelectionPrompt(record["処理ID"], candidates)];
  } else {
    moved = transitionVoiceLogStatus_(ss, record.sheetRow, ["文字起こし済み"], { "ステータス": "新規企業確認待ち" });
    pushSpecs = [GlowLineVoiceLogContent.buildNewCompanyConfirmPrompt(record["処理ID"], companyNameCandidate || "(不明)")];
  }
  if (!moved) {
    Logger.log("確認メッセージの送信前に他の処理が状態を変更したため中断しました(処理ID " + record["処理ID"] + ")。");
    return;
  }
  linePush_(record["LINEユーザーID"], pushSpecs);
}

function fetchLineAudioContent_(messageId) {
  var token = PropertiesService.getScriptProperties().getProperty("LINE_CHANNEL_ACCESS_TOKEN");
  if (!token) {
    throw new Error("LINE_CHANNEL_ACCESS_TOKEN が未設定です。スクリプト プロパティで設定してください。");
  }
  var response = UrlFetchApp.fetch("https://api-data.line.me/v2/bot/message/" + messageId + "/content", {
    headers: { Authorization: "Bearer " + token },
    muteHttpExceptions: true
  });
  if (response.getResponseCode() !== 200) {
    throw new Error("LINEから音声データの取得に失敗しました(HTTP " + response.getResponseCode() + ")");
  }
  return response.getBlob();
}

function callGeminiForVoiceLog_(audioBlob) {
  return GlowResilience.withRetry(
    function () { return callGeminiForVoiceLogOnce_(audioBlob); },
    {
      maxAttempts: 3,
      backoffMs: [2000, 10000],
      sleepFn: Utilities.sleep,
      isRetryable: function (error) {
        return !error.statusCode || GlowResilience.isRetryableHttpStatus(error.statusCode);
      },
      onRetry: function (error, attempt) {
        Logger.log("Gemini API呼び出しを再試行します(" + attempt + "回目失敗): " + error);
      }
    }
  );
}

function callGeminiForVoiceLogOnce_(audioBlob) {
  var apiKey = PropertiesService.getScriptProperties().getProperty("GEMINI_API_KEY");
  if (!apiKey) {
    throw new Error("GEMINI_API_KEY が未設定です。スクリプト プロパティで設定してください。");
  }
  var payload = {
    contents: [{
      parts: [
        { text: buildGeminiPrompt_() },
        { inline_data: { mime_type: audioBlob.getContentType() || "audio/m4a", data: Utilities.base64Encode(audioBlob.getBytes()) } }
      ]
    }]
  };
  var response = UrlFetchApp.fetch(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key=" + apiKey,
    {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    }
  );
  var responseCode = response.getResponseCode();
  if (responseCode < 200 || responseCode >= 300) {
    var error = new Error("Gemini APIの呼び出しに失敗しました(ステータスコード " + responseCode + "): " + response.getContentText());
    error.statusCode = responseCode;
    throw error;
  }
  var body = JSON.parse(response.getContentText());
  var text = body.candidates && body.candidates[0] && body.candidates[0].content &&
    body.candidates[0].content.parts && body.candidates[0].content.parts[0] &&
    body.candidates[0].content.parts[0].text;
  if (!text) {
    throw new Error("Gemini APIのレスポンスからテキストを取得できませんでした。");
  }
  return parseGeminiExtractionResult_(text);
}

function buildGeminiPrompt_() {
  return "この音声は、営業担当者が企業訪問後に残した口頭のメモです。以下のJSON形式のみを出力してください" +
    "(説明文やコードブロックの記号は付けないこと):\n" +
    "{\"companyName\": \"話された会社名\", " +
    "\"interactionType\": \"" + GlowSchema.INTERACTION_TYPES.join("/") + "のいずれか\", " +
    "\"respondentType\": \"" + GlowSchema.RESPONDENT_TYPES.join("/") + "のいずれか\", " +
    "\"contentMemo\": \"話の内容の要約(2〜3文程度)\", " +
    "\"nextAction\": \"次にやるべきこと(無ければ空文字)\"}";
}

function parseGeminiExtractionResult_(text) {
  var cleaned = text.replace(/```json/g, "").replace(/```/g, "").trim();
  var parsed = JSON.parse(cleaned);
  return {
    companyName: parsed.companyName || "",
    interactionType: parsed.interactionType || "",
    respondentType: parsed.respondentType || "",
    contentMemo: parsed.contentMemo || "",
    nextAction: parsed.nextAction || ""
  };
}

function linePush_(lineUserId, specs) {
  var token = PropertiesService.getScriptProperties().getProperty("LINE_CHANNEL_ACCESS_TOKEN");
  if (!token) {
    Logger.log("LINE_CHANNEL_ACCESS_TOKEN が未設定のため、LINEへのプッシュ送信を送れませんでした。");
    return;
  }
  var messages = specs.map(buildLineMessagePayload_);
  var response = UrlFetchApp.fetch("https://api.line.me/v2/bot/message/push", {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "Bearer " + token },
    payload: JSON.stringify({ to: lineUserId, messages: messages }),
    muteHttpExceptions: true
  });
  var responseCode = response.getResponseCode();
  if (responseCode < 200 || responseCode >= 300) {
    Logger.log("LINEへのプッシュ送信に失敗しました(HTTP " + responseCode + "): " + response.getContentText());
  }
}

/**
 * postback(ボタン操作)イベントの処理。data文字列からaction/processId/valueを取り出し、
 * 対応する処理へ振り分ける。processIdに一致する「音声ログ処理状況」の行が無い場合
 * (二重タップ・古いボタン操作等)はエラーメッセージのみ返す。
 */
function handleLinePostback_(event) {
  var lineUserId = event.source && event.source.userId;
  var replyToken = event.replyToken;
  var parsed = GlowLineVoiceLogContent.parsePostbackData(event.postback && event.postback.data);
  if (!lineUserId || !replyToken || !parsed.action || !parsed.processId) return;

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var record = readVoiceLogRows_(ss).filter(function (r) { return r["処理ID"] === parsed.processId; })[0];
  if (!record) {
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }

  if (parsed.action === GlowLineVoiceLogContent.POSTBACK_ACTIONS.SELECT_COMPANY) {
    handleCompanySelectionPostback_(ss, replyToken, record, parsed.value);
    return;
  }
  if (parsed.action === GlowLineVoiceLogContent.POSTBACK_ACTIONS.NEW_COMPANY_CONFIRM) {
    handleNewCompanyConfirmPostback_(ss, replyToken, record, parsed.value);
    return;
  }
  if (parsed.action === GlowLineVoiceLogContent.POSTBACK_ACTIONS.FINAL_CONFIRM) {
    handleFinalConfirmPostback_(ss, replyToken, record, parsed.value);
    return;
  }
}

/**
 * postbackのvalueとして渡された企業IDの形式チェック。postbackの本文は(destination
 * チェックを突破された場合)外部から任意の値を送りうるため、TrackingWebApp.gsのdoGetと
 * 同じく企業IDの形式を検証してからシートに書き込む。
 */
var COMPANY_ID_PATTERN = /^C\d{6}$/;

function handleCompanySelectionPostback_(ss, replyToken, record, selectedValue) {
  if (selectedValue === GlowLineVoiceLogContent.NOT_FOUND_VALUE) {
    if (!transitionVoiceLogStatus_(ss, record.sheetRow, ["企業選択待ち"], { "ステータス": "新規企業確認待ち" })) {
      lineReply_(replyToken, [GlowLineVoiceLogContent.buildAlreadyHandledMessage()]);
      return;
    }
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildNewCompanyConfirmPrompt(record["処理ID"], record["会社名候補"] || "(不明)")]);
    return;
  }

  if (!COMPANY_ID_PATTERN.test(String(selectedValue || ""))) {
    Logger.log("企業IDの形式が不正なpostbackを受信したため破棄しました: " + selectedValue);
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }

  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  var company = companies.filter(function (c) { return c["企業ID"] === selectedValue; })[0];
  if (!company) {
    Logger.log("企業マスタに存在しない企業IDのpostbackを受信したため破棄しました: " + selectedValue);
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }

  var interactionType = GlowLineVoiceLogContent.normalizeInteractionType(record["種別候補"]);
  var respondentType = GlowLineVoiceLogContent.normalizeRespondentType(record["対応相手候補"]);
  var moved = transitionVoiceLogStatus_(ss, record.sheetRow, ["企業選択待ち"], {
    "ステータス": "最終確認待ち",
    "企業ID": selectedValue,
    "種別候補": interactionType,
    "対応相手候補": respondentType
  });
  if (!moved) {
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildAlreadyHandledMessage()]);
    return;
  }

  lineReply_(replyToken, [GlowLineVoiceLogContent.buildFinalConfirmPrompt(
    record["処理ID"], company["会社名"], interactionType, respondentType, record["内容メモ"], record["次回アクション"]
  )]);
}

function handleNewCompanyConfirmPostback_(ss, replyToken, record, answer) {
  if (answer !== GlowLineVoiceLogContent.YES_VALUE) {
    if (!transitionVoiceLogStatus_(ss, record.sheetRow, ["新規企業確認待ち"], { "ステータス": "破棄" })) {
      lineReply_(replyToken, [GlowLineVoiceLogContent.buildAlreadyHandledMessage()]);
      return;
    }
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildDiscardMessage()]);
    return;
  }

  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    markVoiceLogAsError_(ss, record.sheetRow, ["新規企業確認待ち"], "企業マスタタブが見つかりません");
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }

  // 企業マスタへの新規行追加は不可逆なため、まず行を「処理中」として確保する。
  // 二重タップやWebhook再送で同じpostbackが2回届いても、確保できるのは1回だけ。
  if (!transitionVoiceLogStatus_(ss, record.sheetRow, ["新規企業確認待ち"], { "ステータス": VOICE_LOG_STATUS_PROCESSING })) {
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildAlreadyHandledMessage()]);
    return;
  }

  var companyName = GlowLineVoiceLogContent.sanitizeSheetText(record["会社名候補"]) || "(社名不明)";
  var newCompanyId;

  // ImportRunner.gsのimportCompaniesFromStagingと同じく「ロック→読み取り→採番→書き込み」の
  // 順で行う。ロックの外で採番すると、同時に確定された2件が同じ企業IDを採番しうる。
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    markVoiceLogAsError_(ss, record.sheetRow, [VOICE_LOG_STATUS_PROCESSING], "企業マスタのロック取得に失敗しました");
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }
  // ステータス更新も同じドキュメントロックを使うため、ロックを保持したままエラー処理を
  // 行わない(入れ子のロック取得を避ける)。失敗は変数に退避し、解放後に処理する。
  var writeError = null;
  try {
    var companies = readCompanyRecords_(companySheet);
    newCompanyId = GlowCsvImport.buildCompanyId(GlowDedupe.nextSequenceNumber(companies));
    var newRow = GlowLineVoiceLogContent.buildNewCompanyRow(newCompanyId, companyName);
    var nextRow = companySheet.getLastRow() + 1;
    companySheet.getRange(nextRow, 1, 1, GlowSchema.COMPANY_MASTER_HEADERS.length).setValues([newRow]);
  } catch (error) {
    writeError = error;
  } finally {
    lock.releaseLock();
  }
  if (writeError) {
    Logger.log("企業マスタへの新規企業の追加に失敗しました(処理ID " + record["処理ID"] + "): " + writeError);
    markVoiceLogAsError_(ss, record.sheetRow, [VOICE_LOG_STATUS_PROCESSING], "企業マスタへの追加に失敗しました: " + writeError);
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }

  var interactionType = GlowLineVoiceLogContent.normalizeInteractionType(record["種別候補"]);
  var respondentType = GlowLineVoiceLogContent.normalizeRespondentType(record["対応相手候補"]);
  // 企業マスタへの追加は完了済み。ここで最終確認待ちに倒せなかった場合(放置検知の
  // 自動取り消しと競合した等)、追加された企業行は残るため、追跡できるようログに残す。
  if (!transitionVoiceLogStatus_(ss, record.sheetRow, [VOICE_LOG_STATUS_PROCESSING], {
    "ステータス": "最終確認待ち",
    "企業ID": newCompanyId,
    "種別候補": interactionType,
    "対応相手候補": respondentType
  })) {
    Logger.log(
      "企業マスタへの追加は成功しましたが、ステータスを最終確認待ちに更新できませんでした" +
      "(処理ID " + record["処理ID"] + " / 企業ID " + newCompanyId + ")。"
    );
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildAlreadyHandledMessage()]);
    return;
  }
  lineReply_(replyToken, [GlowLineVoiceLogContent.buildFinalConfirmPrompt(
    record["処理ID"], companyName, interactionType, respondentType, record["内容メモ"], record["次回アクション"]
  )]);
}

function handleFinalConfirmPostback_(ss, replyToken, record, answer) {
  if (answer !== GlowLineVoiceLogContent.CONFIRM_VALUE) {
    if (!transitionVoiceLogStatus_(ss, record.sheetRow, ["最終確認待ち"], { "ステータス": "破棄" })) {
      lineReply_(replyToken, [GlowLineVoiceLogContent.buildAlreadyHandledMessage()]);
      return;
    }
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildDiscardMessage()]);
    return;
  }

  // 対応履歴ログへの追記は不可逆なため、まず行を「処理中」として確保する。
  // 確保できなかった場合(二重タップ・Webhook再送)は一切書き込まずに案内だけ返す。
  if (!transitionVoiceLogStatus_(ss, record.sheetRow, ["最終確認待ち"], { "ステータス": VOICE_LOG_STATUS_PROCESSING })) {
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildAlreadyHandledMessage()]);
    return;
  }

  var staffName = resolveStaffNameByLineUserId_(ss, record["LINEユーザーID"]);
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  if (!logSheet || !staffName) {
    markVoiceLogAsError_(ss, record.sheetRow, [VOICE_LOG_STATUS_PROCESSING], "対応履歴ログタブまたは担当者が見つかりません");
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }

  var logId = "H-" + Utilities.getUuid();
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var row = GlowLineVoiceLogContent.buildInteractionLogRow(
    logId, record["企業ID"], todayString, staffName,
    record["種別候補"], record["対応相手候補"], record["内容メモ"], record["次回アクション"]
  );

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    markVoiceLogAsError_(ss, record.sheetRow, [VOICE_LOG_STATUS_PROCESSING], "対応履歴ログのロック取得に失敗しました");
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }
  // ステータス更新も同じドキュメントロックを使うため、ロックを保持したままエラー処理を
  // 行わない(入れ子のロック取得を避ける)。失敗は変数に退避し、解放後に処理する。
  var writeError = null;
  try {
    var nextRow = logSheet.getLastRow() + 1;
    logSheet.getRange(nextRow, 1, 1, GlowSchema.INTERACTION_LOG_HEADERS.length).setValues([row]);
  } catch (error) {
    writeError = error;
  } finally {
    lock.releaseLock();
  }
  if (writeError) {
    // 確保済みのまま「確定」にすると、実体の無い記録が確定扱いで残る。必ずエラーへ倒す。
    Logger.log("対応履歴ログへの書き込みに失敗しました(処理ID " + record["処理ID"] + "): " + writeError);
    markVoiceLogAsError_(ss, record.sheetRow, [VOICE_LOG_STATUS_PROCESSING], "対応履歴ログへの書き込みに失敗しました: " + writeError);
    lineReply_(replyToken, [GlowLineVoiceLogContent.buildProcessingErrorMessage()]);
    return;
  }

  // 対応履歴ログへの書き込みは完了しているため、ここで確定に倒せなくても記録自体は残る。
  // (放置検知の自動取り消しと競合した場合など)後から追跡できるようログに残す。
  if (!transitionVoiceLogStatus_(ss, record.sheetRow, [VOICE_LOG_STATUS_PROCESSING], { "ステータス": "確定" })) {
    Logger.log(
      "対応履歴ログへの書き込みは成功しましたが、ステータスを確定に更新できませんでした" +
      "(処理ID " + record["処理ID"] + " / 対応履歴ID " + logId + ")。"
    );
  }

  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  var company = companies.filter(function (c) { return c["企業ID"] === record["企業ID"]; })[0];
  var companyName = company ? company["会社名"] : (record["会社名候補"] || "");
  lineReply_(replyToken, [GlowLineVoiceLogContent.buildCompletionMessage(companyName)]);
}
