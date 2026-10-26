/**
 * GLOW企業リレーション台帳: 録音ファイル(Googleドライブ経由)の受付(2026-10-26 追加)
 *
 * 使い方(担当者): 録音アプリ(PCM録音など)で録った WAV / AAC / M4A / MP3 を、
 * ドライブの「GLOW音声ログ受付」フォルダに入れるだけ(スマホのドライブアプリから「アップロード」)。
 * 数分以内に受け付けられ(ファイル名の先頭に「受付済_」が付く)、LINE音声と同じ流れで
 * 文字起こし・要約 → LINEで確認ボタン → 対応履歴ログへ記録 → 企業の関係メモへ要約を追記、まで進む。
 * ファイル名に会社名を入れておく(例: 「株式会社◯◯_1026.wav」)と、会社の特定が確実になる。
 *
 * 前提: 「スタッフ」タブに、その人のメールアドレス(ドライブにアップロードするアカウント)と
 * LINE User ID が登録されていること(確認ボタンをLINEで送るため)。
 * 判断のロジックは voiceFileIntake.js(テストあり)。
 */

var VOICE_DRIVE_FOLDER_NAME = "GLOW音声ログ受付";
var VOICE_DRIVE_FOLDER_PROP = "VOICE_DRIVE_FOLDER_ID";
var VOICE_UPLOAD_STATE_PREFIX = "VOICE_UPLOAD_";
// 1回の実行(上限6分)のうち、分割アップロードに使ってよい時間。超えたら続きは次の実行へ
var VOICE_UPLOAD_TIME_BUDGET_MS = 4 * 60 * 1000;

/** 受付フォルダを用意し、有効なスタッフを編集者に加える(自己点検から呼ぶ・冪等) */
function ensureVoiceDriveFolder_() {
  var folder = getVoiceDriveFolder_(true);
  var editors = {};
  folder.getEditors().forEach(function (u) { editors[String(u.getEmail()).toLowerCase()] = true; });
  var owner = folder.getOwner();
  if (owner) editors[String(owner.getEmail()).toLowerCase()] = true;
  var added = [];
  readVoiceStaff_().forEach(function (s) {
    // 1人が複数のアカウントを使う場合に備え、「メールアドレス」欄の全アドレスに共有する
    GlowVoiceFileIntake.staffEmails(s.email).forEach(function (email) {
      if (editors[email]) return;
      folder.addEditor(email);
      editors[email] = true;
      added.push(s.name || "スタッフ");
    });
  });
  return "あり(" + folder.getUrl() + ")" + (added.length ? " / 共有を追加: " + added.join("、") : "");
}

function getVoiceDriveFolder_(create) {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty(VOICE_DRIVE_FOLDER_PROP);
  if (id) {
    try {
      var existing = DriveApp.getFolderById(id);
      if (!existing.isTrashed()) return existing;
    } catch (error) {
      Logger.log("音声ログ受付フォルダが見つからないため作り直します: " + error);
    }
  }
  if (!create) return null;
  var found = DriveApp.getFoldersByName(VOICE_DRIVE_FOLDER_NAME);
  var folder = found.hasNext() ? found.next() : DriveApp.createFolder(VOICE_DRIVE_FOLDER_NAME);
  props.setProperty(VOICE_DRIVE_FOLDER_PROP, folder.getId());
  return folder;
}

/** スタッフタブの有効な人: {name, email, lineUserId} */
function readVoiceStaff_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(GlowSchema.STAFF_SHEET_NAME);
  if (!sheet || sheet.getLastRow() < 2) return [];
  var headers = GlowSchema.STAFF_HEADERS;
  var values = sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues();
  var nameI = headers.indexOf("氏名"), emailI = headers.indexOf("メールアドレス");
  var activeI = headers.indexOf("有効"), lineI = headers.indexOf("LINE User ID");
  return values.filter(function (r) { return r[activeI] === true; }).map(function (r) {
    return { name: String(r[nameI] || ""), email: String(r[emailI] || ""), lineUserId: String(r[lineI] || "").trim() };
  });
}

/** 毎分のトリガーから呼ぶ。フォルダに新しい録音があれば「音声ログ処理状況」へ受け付ける */
function enqueueDriveVoiceFiles_(ss) {
  var folder = getVoiceDriveFolder_(false);
  if (!folder) {
    // 初回: フォルダを作ってスタッフに共有する(以後は自己点検でも見直す)
    var created = ensureVoiceDriveFolder_();
    recordOpsStatus_("録音ファイルの受付フォルダ", true, created);
    console.log("録音ファイルの受付フォルダを用意しました");
    return 0;
  }
  logVoiceFolderHeartbeat_(folder);
  syncVoiceFolderSharingIfDue_();
  var files = [];
  var iter = folder.getFiles();
  while (iter.hasNext()) {
    var f = iter.next();
    if (f.isTrashed() || !GlowVoiceFileIntake.isAcceptableFileName(f.getName())) continue;
    var owner = f.getOwner();
    files.push({ id: f.getId(), name: f.getName(), ownerEmail: owner ? owner.getEmail() : "", file: f });
  }
  if (!files.length) return 0;

  var rows = readVoiceLogRows_(ss);
  var known = rows.map(function (r) { return r["LINEメッセージID"]; });
  var busy = rows.filter(function (r) { return VOICE_LOG_IN_PROGRESS_STATUSES.indexOf(r["ステータス"]) !== -1; })
    .map(function (r) { return r["LINEユーザーID"]; });
  var plan = GlowVoiceFileIntake.planIntake(files, readVoiceStaff_(), known, busy);
  plan.skip.forEach(function (s) {
    console.warn("録音ファイルを受け付けませんでした: " + s.reason);
    notifyVoiceFileSkippedOnce_(s);
  });

  plan.accept.forEach(function (item) {
    var processId = "P-" + Utilities.getUuid();
    var receivedAt = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm");
    appendVoiceLogRow_(ss, [
      processId, item.staff.lineUserId, GlowVoiceFileIntake.toDriveMessageId(item.file.id), "受信済み",
      receivedAt, "", "", "", "", "", "", "", "", "", ""
    ]);
    item.file.file.setName(GlowVoiceFileIntake.DONE_PREFIX + item.file.name);
    linePush_(item.staff.lineUserId, [{
      text: "録音ファイル「" + item.file.name + "」を受け付けました。文字起こしと要約が終わったら、確認のご連絡をします(長い録音は数分〜十数分かかります)。"
    }]);
  });
  if (plan.accept.length) console.log("録音ファイルを受け付けました: " + plan.accept.length + "件");
  return plan.accept.length;
}

/**
 * スタッフタブに足したメールアドレスへ、10分以内に共有を広げる(自己点検の6時間を待たない)。
 * 2026-10-26: 福田さんがスタッフタブとは別のアカウントでフォルダを開こうとして「アクセス権のリクエスト」になった。
 */
function syncVoiceFolderSharingIfDue_() {
  var props = PropertiesService.getScriptProperties();
  var last = Number(props.getProperty("VOICE_DRIVE_SHARE_SYNC_MS") || 0);
  if (Date.now() - last < 10 * 60 * 1000) return;
  props.setProperty("VOICE_DRIVE_SHARE_SYNC_MS", String(Date.now()));
  try {
    ensureVoiceDriveFolder_();
  } catch (error) {
    console.error("録音ファイルの受付フォルダの共有を更新できませんでした: " + error);
  }
}

/**
 * 受け付けられない録音ファイル(スタッフ登録の無いアカウント・LINE User ID 未登録)は、本人へLINEで返せないため、
 * 管理者へ1ファイルにつき1回だけ知らせる(黙って置きっぱなしにしない)。
 */
function notifyVoiceFileSkippedOnce_(skip) {
  if (skip.reason === "同じ担当者の別の録音を処理中") return;
  var props = PropertiesService.getScriptProperties();
  var key = "VOICE_SKIP_NOTICE_" + skip.file.id;
  if (props.getProperty(key)) return;
  props.setProperty(key, String(Date.now()));
  notifyOpsFailure_("録音ファイルの受付",
    "「GLOW音声ログ受付」フォルダに、受け付けられない録音ファイルがあります(" + skip.reason + ")。\n" +
    "台帳の「スタッフ」タブで、そのファイルを入れた人の「メールアドレス」欄にアカウントを追加してください" +
    "(複数あるときは「,」で区切って並べられます)。追加すると数分で自動的に受け付けます。");
}

/** 受付フォルダが使える状態かを、6時間に1回だけ実行記録(Cloud Logging)に残す(外から稼働を確かめるため) */
function logVoiceFolderHeartbeat_(folder) {
  var props = PropertiesService.getScriptProperties();
  var last = Number(props.getProperty("VOICE_DRIVE_HEARTBEAT_MS") || 0);
  if (Date.now() - last < 6 * 60 * 60 * 1000) return;
  props.setProperty("VOICE_DRIVE_HEARTBEAT_MS", String(Date.now()));
  console.log("録音ファイルの受付フォルダ: 稼働中(共有 " + folder.getEditors().length + " 人)");
}

/**
 * 文字起こしに渡す音声を用意する。
 * 戻り値: { blob } (そのまま送る) / { fileUri, mimeType } (Geminiへアップロード済み)。どちらにも hint が付く
 */
function prepareVoiceAudio_(record) {
  var driveId = GlowVoiceFileIntake.driveFileIdOf(record["LINEメッセージID"]);
  if (!driveId) {
    var lineBlob = fetchLineAudioContent_(record["LINEメッセージID"]);
    if (lineBlob.getBytes().length <= GlowVoiceFileIntake.INLINE_MAX_BYTES) return { blob: lineBlob, hint: "" };
    // LINEで送られた長めの録音ファイル(14MB超)は、そのままでは送れないためGeminiへ一括アップロードする
    var lineMime = lineBlob.getContentType() || "audio/mp4";
    var lineUploaded = uploadBlobToGemini_(lineBlob, lineMime, record["処理ID"]);
    return { fileUri: lineUploaded.uri, mimeType: lineMime, hint: "" };
  }
  var file = DriveApp.getFileById(driveId);
  var name = file.getName();
  var mimeType = GlowVoiceFileIntake.audioMimeType(name, file.getMimeType());
  var hint = GlowVoiceFileIntake.fileNameHint(name);
  var size = file.getSize();
  if (size <= GlowVoiceFileIntake.INLINE_MAX_BYTES) {
    return { blob: file.getBlob().setContentType(mimeType), hint: hint };
  }
  var uploaded = uploadDriveFileToGemini_(record["処理ID"], driveId, size, mimeType);
  return { fileUri: uploaded.uri, mimeType: mimeType, hint: hint };
}

/**
 * ドライブのファイルを分割して読み、Gemini のファイル置き場へ分割アップロードする。
 * 1回の実行で終わらなければ進み具合を保存し、一時的な障害(503)として次の実行へ回す
 * (processQueuedVoiceLogs が「受信済み」へ戻して、続きから再開する)。
 */
function uploadDriveFileToGemini_(processId, driveId, size, mimeType) {
  var apiKey = PropertiesService.getScriptProperties().getProperty("GEMINI_API_KEY");
  if (!apiKey) throw new Error("GEMINI_API_KEY が未設定です。スクリプト プロパティで設定してください。");
  var props = PropertiesService.getScriptProperties();
  var stateKey = VOICE_UPLOAD_STATE_PREFIX + processId;
  var state = JSON.parse(props.getProperty(stateKey) || "null");

  if (!state) {
    var start = UrlFetchApp.fetch("https://generativelanguage.googleapis.com/upload/v1beta/files?key=" + apiKey, {
      method: "post",
      contentType: "application/json",
      headers: {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": String(size),
        "X-Goog-Upload-Header-Content-Type": mimeType
      },
      payload: JSON.stringify({ file: { display_name: processId } }),
      muteHttpExceptions: true
    });
    var headers = start.getAllHeaders();
    var url = headers["x-goog-upload-url"] || headers["X-Goog-Upload-URL"];
    if (start.getResponseCode() !== 200 || !url) {
      var startError = new Error("Geminiへのアップロード開始に失敗しました(HTTP " + start.getResponseCode() + "): " +
      String(start.getContentText()).slice(0, 300));
      startError.statusCode = start.getResponseCode();
      throw startError;
    }
    state = { url: url, offset: 0 };
    props.setProperty(stateKey, JSON.stringify(state));
  }

  var token = ScriptApp.getOAuthToken();
  var began = Date.now();
  var result = null;
  var chunk;
  while ((chunk = GlowVoiceFileIntake.nextChunk(state.offset, size))) {
    if (Date.now() - began > VOICE_UPLOAD_TIME_BUDGET_MS) {
      var pause = new Error("録音ファイルのアップロード途中です(" + Math.round(state.offset / 1048576) + "MB / " +
        Math.round(size / 1048576) + "MB)。続きは次の実行で行います");
      pause.statusCode = 503;
      throw pause;
    }
    var part = UrlFetchApp.fetch("https://www.googleapis.com/drive/v3/files/" + driveId + "?alt=media", {
      headers: { Authorization: "Bearer " + token, Range: "bytes=" + chunk.start + "-" + chunk.end },
      muteHttpExceptions: true
    });
    if (part.getResponseCode() !== 206 && part.getResponseCode() !== 200) {
      var readError = new Error("ドライブから録音ファイルを読めませんでした(HTTP " + part.getResponseCode() + ")");
      readError.statusCode = part.getResponseCode() >= 500 ? part.getResponseCode() : 400;
      throw readError;
    }
    var put = UrlFetchApp.fetch(state.url, {
      method: "post",
      contentType: mimeType,
      headers: {
        "X-Goog-Upload-Command": chunk.isLast ? "upload, finalize" : "upload",
        "X-Goog-Upload-Offset": String(chunk.start)
      },
      payload: part.getContent(),
      muteHttpExceptions: true
    });
    if (put.getResponseCode() !== 200) {
      var putError = new Error("Geminiへのアップロードに失敗しました(HTTP " + put.getResponseCode() + "): " +
      String(put.getContentText()).slice(0, 300));
      putError.statusCode = put.getResponseCode();
      throw putError;
    }
    state.offset = chunk.end + 1;
    props.setProperty(stateKey, JSON.stringify(state));
    if (chunk.isLast) result = JSON.parse(put.getContentText()).file;
  }
  props.deleteProperty(stateKey);
  if (!result || !result.uri) throw new Error("Geminiへのアップロード結果を読めませんでした");
  return waitGeminiFileActive_(result, apiKey);
}

/** 手元にある音声(LINEから受け取ったもの。上限50MB)を、Gemini のファイル置き場へ1回で送る */
function uploadBlobToGemini_(blob, mimeType, displayName) {
  var apiKey = PropertiesService.getScriptProperties().getProperty("GEMINI_API_KEY");
  if (!apiKey) throw new Error("GEMINI_API_KEY が未設定です。スクリプト プロパティで設定してください。");
  var bytes = blob.getBytes();
  var start = UrlFetchApp.fetch("https://generativelanguage.googleapis.com/upload/v1beta/files?key=" + apiKey, {
    method: "post",
    contentType: "application/json",
    headers: {
      "X-Goog-Upload-Protocol": "resumable",
      "X-Goog-Upload-Command": "start",
      "X-Goog-Upload-Header-Content-Length": String(bytes.length),
      "X-Goog-Upload-Header-Content-Type": mimeType
    },
    payload: JSON.stringify({ file: { display_name: displayName } }),
    muteHttpExceptions: true
  });
  var headers = start.getAllHeaders();
  var url = headers["x-goog-upload-url"] || headers["X-Goog-Upload-URL"];
  if (start.getResponseCode() !== 200 || !url) {
    var startError = new Error("Geminiへのアップロード開始に失敗しました(HTTP " + start.getResponseCode() + "): " +
      String(start.getContentText()).slice(0, 300));
    startError.statusCode = start.getResponseCode();
    throw startError;
  }
  var put = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: mimeType,
    headers: { "X-Goog-Upload-Command": "upload, finalize", "X-Goog-Upload-Offset": "0" },
    payload: bytes,
    muteHttpExceptions: true
  });
  if (put.getResponseCode() !== 200) {
    var putError = new Error("Geminiへのアップロードに失敗しました(HTTP " + put.getResponseCode() + "): " +
      String(put.getContentText()).slice(0, 300));
    putError.statusCode = put.getResponseCode();
    throw putError;
  }
  return waitGeminiFileActive_(JSON.parse(put.getContentText()).file, apiKey);
}

function waitGeminiFileActive_(file, apiKey) {
  var current = file;
  for (var i = 0; i < 30 && current.state === "PROCESSING"; i++) {
    Utilities.sleep(3000);
    current = JSON.parse(UrlFetchApp.fetch(
      "https://generativelanguage.googleapis.com/v1beta/" + file.name + "?key=" + apiKey, { muteHttpExceptions: true }
    ).getContentText());
  }
  if (current.state && current.state !== "ACTIVE") {
    var error = new Error("Gemini側で録音ファイルの準備が終わりませんでした(状態: " + current.state + ")");
    error.statusCode = current.state === "PROCESSING" ? 503 : 400;
    throw error;
  }
  return current;
}

/* ---------- Gemini の支払いエラー(402)の待機と自動再開(2026-10-26 追加) ---------- */
var GEMINI_BILLING_BLOCK_PROP = "GEMINI_BILLING_BLOCKED_UNTIL_MS";
var GEMINI_BILLING_RETRY_MS = 60 * 60 * 1000;

/** 支払いエラーのあと、次に試すまでの待ち時間の間か */
function isGeminiBillingBlocked_() {
  var until = Number(PropertiesService.getScriptProperties().getProperty(GEMINI_BILLING_BLOCK_PROP) || 0);
  return Date.now() < until;
}

/**
 * 支払いエラーになった録音を「受信済み」に戻して待機させる(エラーで確定させない)。
 * LINEの音声はLINE側の保存期間が過ぎると取り直せなくなるため、受付フォルダへ写してから待たせる。
 * 担当者へはその日1回だけ、管理者へは失敗通知(1日1回)で知らせる。
 */
function holdVoiceLogForBilling_(ss, record, error) {
  var props = PropertiesService.getScriptProperties();
  props.setProperty(GEMINI_BILLING_BLOCK_PROP, String(Date.now() + GEMINI_BILLING_RETRY_MS));
  var updates = { "ステータス": "受信済み", "エラー内容": GlowVoiceFileIntake.BILLING_WAIT_NOTE };
  if (!GlowVoiceFileIntake.driveFileIdOf(record["LINEメッセージID"])) {
    try {
      var blob = fetchLineAudioContent_(record["LINEメッセージID"]);
      var ext = String(blob.getContentType() || "").indexOf("wav") !== -1 ? "wav" : "m4a";
      var copy = getVoiceDriveFolder_(true).createFile(
        blob.setName(GlowVoiceFileIntake.DONE_PREFIX + "LINE_" + record["処理ID"] + "." + ext));
      updates["LINEメッセージID"] = GlowVoiceFileIntake.toDriveMessageId(copy.getId());
    } catch (copyError) {
      console.error("LINEの音声を受付フォルダへ写せませんでした: " + copyError);
    }
  }
  transitionVoiceLogStatus_(ss, record.sheetRow, VOICE_LOG_IN_PROGRESS_STATUSES, updates);
  notifyOpsFailure_("音声ログの文字起こし(Gemini)",
    "Gemini API が「支払いが必要(HTTP 402)」を返しました。Google AI Studio の請求(前払い残高)を確認し、補充してください。\n" +
    "録音は保存してあり、補充後は1時間以内に自動で処理を再開します。\n詳細: " + String(error).slice(0, 300));
  var today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var noticeKey = "VOICE_BILLING_NOTICE_" + record["LINEユーザーID"];
  if (record["LINEユーザーID"] && props.getProperty(noticeKey) !== today) {
    props.setProperty(noticeKey, today);
    linePush_(record["LINEユーザーID"], [{
      text: "録音は受け取っています。いまAIの処理が一時的に止まっているため、再開しだい自動で要約して確認をお送りします(録音はそのまま保存されています)。"
    }]);
  }
  console.warn("Geminiの支払いエラーのため、音声ログを待機させました");
}

/** 支払いエラーで「エラー」になっていた行を、待ち時間が明けたら「受信済み」に戻して再開する */
function requeueBillingHeldVoiceLogs_(ss) {
  readVoiceLogRows_(ss).forEach(function (r) {
    if (r["ステータス"] !== "エラー" || !GlowVoiceFileIntake.isBillingError(r["エラー内容"])) return;
    transitionVoiceLogStatus_(ss, r.sheetRow, ["エラー"], {
      "ステータス": "受信済み", "エラー内容": GlowVoiceFileIntake.BILLING_WAIT_NOTE
    });
  });
}

