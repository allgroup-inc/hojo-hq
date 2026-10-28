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
// 1回の実行(上限6分)のうち、分割アップロードに使ってよい時間(実行の開始から数える)。超えたら続きは次の実行へ
var VOICE_UPLOAD_TIME_BUDGET_MS = 4 * 60 * 1000;
// 送り終えた時点でこれを過ぎていたら、文字起こし(1〜2分かかる)は次の実行に回す
var VOICE_TRANSCRIBE_START_LIMIT_MS = 3 * 60 * 1000;
// 送り終えた録音の場所(Gemini側の保存は約48時間)。この時間内なら送り直さずに使う
var VOICE_UPLOADED_PREFIX = "VOICE_UPLOADED_";
var VOICE_UPLOADED_KEEP_MS = 40 * 60 * 60 * 1000;
// processQueuedVoiceLogs の開始時刻(実行ごとに設定する)
var VOICE_RUN_STARTED_MS = 0;

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
  var props = PropertiesService.getScriptProperties();
  // 送り終えた録音は、Gemini側に約2日残る。実行の時間切れで文字起こしまで進めなかったときは、送り直さずに使う
  var doneKey = VOICE_UPLOADED_PREFIX + processId;
  var done = JSON.parse(props.getProperty(doneKey) || "null");
  if (done && done.uri && Date.now() - done.at < VOICE_UPLOADED_KEEP_MS) return done;
  // 大きな録音を2つの実行が同時に送ると、互いの送信位置を追い越して失敗する(2026-10-28)。送るのは1つずつ
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(2000)) throw voiceWaitError_("別の録音を送信中のため、順番を待ちます");
  try {
    var uploaded = uploadDriveFileToGeminiLocked_(processId, driveId, size, mimeType);
    props.setProperty(doneKey, JSON.stringify({ uri: uploaded.uri, at: Date.now() }));
    if (voiceRunElapsedMs_() > VOICE_TRANSCRIBE_START_LIMIT_MS) {
      throw voiceWaitError_("録音の送信が終わりました。文字起こしは次の実行で行います");
    }
    return uploaded;
  } finally {
    lock.releaseLock();
  }
}

/** 実行の時間切れなど、待てば進む状態。再試行の回数に数えず、順番待ちへ戻す */
function voiceWaitError_(message) {
  var error = new Error(message);
  error.statusCode = 503;
  error.waitOnly = true;
  return error;
}

/** この実行(processQueuedVoiceLogs)が始まってからの時間 */
function voiceRunElapsedMs_() {
  return VOICE_RUN_STARTED_MS ? Date.now() - VOICE_RUN_STARTED_MS : 0;
}

function uploadDriveFileToGeminiLocked_(processId, driveId, size, mimeType) {
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
  } else {
    // 続きから送る前に、Gemini側が実際に受け取った量を問い合わせる。前回の実行が送信直後に止まると、
    // 手元の記録が遅れて「wrong offset」で失敗する(2026-10-27 福田さんの188MBの録音)
    var received = queryGeminiUploadOffset_(state.url);
    console.log("録音の送信を再開します(記録 " + mb_(state.offset) + "MB / Gemini側 " +
      (received === null ? "不明" : mb_(received) + "MB") + " / " + mb_(size) + "MB)");
    if (received === null) {
      props.deleteProperty(stateKey);
      return uploadDriveFileToGeminiLocked_(processId, driveId, size, mimeType);
    }
    state.offset = received;
  }
  var realigned = 0;

  var token = ScriptApp.getOAuthToken();
  var began = Date.now();
  var result = null;
  var chunk;
  while ((chunk = GlowVoiceFileIntake.nextChunk(state.offset, size))) {
    // 時間は実行の開始から数える(この前に他の処理で時間を使うと、6分の上限で途中終了していた)
    if (Math.max(Date.now() - began, voiceRunElapsedMs_()) > VOICE_UPLOAD_TIME_BUDGET_MS) {
      throw voiceWaitError_("録音ファイルのアップロード途中です(" + mb_(state.offset) + "MB / " +
        mb_(size) + "MB)。続きは次の実行で行います");
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
      // 送った位置のずれは、Gemini が待っている位置がエラー文に書いてあるので、そこから送り直す
      var expected = GlowVoiceFileIntake.expectedUploadOffset(put.getContentText());
      if (expected !== null && expected < size && expected !== chunk.start && realigned < 3) {
        realigned++;
        console.log("録音の送信位置を合わせ直しました(" + mb_(chunk.start) + "MB → " + mb_(expected) + "MB / " + mb_(size) + "MB)");
        state.offset = expected;
        props.setProperty(stateKey, JSON.stringify(state));
        continue;
      }
      var putError = new Error("Geminiへのアップロードに失敗しました(HTTP " + put.getResponseCode() + "): " +
      String(put.getContentText()).slice(0, 300));
      if (expected !== null || /terminated|not active/i.test(put.getContentText()) || put.getResponseCode() === 404) {
        // 合わせ直せない・送信の受け口が閉じた(既に全部届いた・期限切れ等)ときは、最初から送り直す
        props.deleteProperty(stateKey);
        putError.statusCode = 503;
      } else {
        putError.statusCode = put.getResponseCode();
      }
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

function mb_(bytes) {
  return Math.round(bytes / 104857.6) / 10;
}

/**
 * 分割アップロードの途中で、Gemini側が受け取った量(バイト)を返す。
 * 続けられない(期限切れ・完了済み・応答なし)ときは null(最初からやり直す)。
 */
function queryGeminiUploadOffset_(url) {
  var res = UrlFetchApp.fetch(url, {
    method: "post",
    headers: { "X-Goog-Upload-Command": "query" },
    muteHttpExceptions: true
  });
  if (res.getResponseCode() !== 200) return null;
  var headers = res.getAllHeaders();
  var status = String(headers["x-goog-upload-status"] || headers["X-Goog-Upload-Status"] || "");
  var received = Number(headers["x-goog-upload-size-received"] || headers["X-Goog-Upload-Size-Received"]);
  if (status !== "active" || !isFinite(received) || received < 0) return null;
  return received;
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

/**
 * 1回限りの復旧(2026-10-27): 10/26 17:14ごろ福田さんが送った録音は、残高不足で待機している間に、
 * 放置検知(受信から2時間)で「取り消し」にされた。その時間帯に取り消された行を待機へ戻す。
 */
function recoverBillingSweptVoiceLogsOnce_(ss) {
  var props = PropertiesService.getScriptProperties();
  var flag = "VOICE_BILLING_RECOVERY_20261027_DONE";
  if (props.getProperty(flag)) return;
  var from = new Date(2026, 9, 26, 17, 0).getTime();
  var to = new Date(2026, 9, 26, 19, 0).getTime();
  readVoiceLogRows_(ss).forEach(function (r) {
    if (r["ステータス"] !== "エラー" || r["エラー内容"] !== VOICE_LOG_STALE_ERROR_MESSAGE) return;
    var at = parseVoiceLogReceivedAt_(r["受信日時"]);
    if (!at || at.getTime() < from || at.getTime() >= to) return;
    transitionVoiceLogStatus_(ss, r.sheetRow, ["エラー"], {
      "ステータス": "受信済み", "エラー内容": GlowVoiceFileIntake.BILLING_WAIT_NOTE
    });
    console.log("残高不足の待機中に取り消された録音を、待機に戻しました");
  });
  props.setProperty(flag, String(Date.now()));
}

/**
 * 1回限りの復旧(2026-10-28 その2): 大きな録音の送信が、2つの実行の取り合いで
 * 「wrong offset」「terminated」のエラーになった(10/28 17:43)。送信の記録を消して、順番待ちへ戻す。
 */
function recoverUploadRaceVoiceLogsOnce_(ss) {
  var props = PropertiesService.getScriptProperties();
  var flag = "VOICE_UPLOAD_RACE_RECOVERY_20261028_DONE";
  if (props.getProperty(flag)) return;
  var from = new Date(2026, 9, 26, 17, 0).getTime();
  readVoiceLogRows_(ss).forEach(function (r) {
    if (r["ステータス"] !== "エラー" || !/wrong offset|terminated/i.test(String(r["エラー内容"] || ""))) return;
    var at = parseVoiceLogReceivedAt_(r["受信日時"]);
    if (!at || at.getTime() < from) return;
    if (transitionVoiceLogStatus_(ss, r.sheetRow, ["エラー"], { "ステータス": "受信済み", "エラー内容": "" })) {
      props.deleteProperty(VOICE_UPLOAD_STATE_PREFIX + r["処理ID"]);
      console.log("送信の取り合いでエラーになった録音を、順番待ちへ戻しました");
    }
  });
  props.setProperty(flag, String(Date.now()));
}

/**
 * 1回限りの復旧(2026-10-28): 残高の補充後に要約まで進んだ福田さんの録音が、確認ボタンが押されないまま
 * 2時間の放置検知で取り消された(10/27 18:23・19:07)。録音は残っているので、順番待ちへ戻して
 * 要約し直し、確認ボタンを1件ずつ送り直す。
 */
function recoverUnconfirmedVoiceLogsOnce_(ss) {
  var props = PropertiesService.getScriptProperties();
  var flag = "VOICE_CONFIRM_RECOVERY_20261028_DONE";
  if (props.getProperty(flag)) return;
  var from = new Date(2026, 9, 26, 17, 0).getTime();
  readVoiceLogRows_(ss).forEach(function (r) {
    if (r["ステータス"] !== "エラー" || r["エラー内容"] !== VOICE_LOG_STALE_ERROR_MESSAGE) return;
    var at = parseVoiceLogReceivedAt_(r["受信日時"]);
    if (!at || at.getTime() < from) return;
    var moved = transitionVoiceLogStatus_(ss, r.sheetRow, ["エラー"], {
      "ステータス": "受信済み", "エラー内容": "", "会社名候補": "", "企業ID": "", "種別候補": "",
      "対応相手候補": "", "内容メモ": "", "次回アクション": "",
      "後継者状況候補": "", "興味商品候補": "", "次回予定日候補": ""
    });
    if (moved) {
      props.deleteProperty(VOICE_LOG_CLOCK_PREFIX + r["処理ID"]);
      console.log("確認されないまま取り消された録音を、要約し直すため順番待ちへ戻しました");
    }
  });
  props.setProperty(flag, String(Date.now()));
}

/**
 * 1回限りの復旧(2026-10-27 その2): 残高の補充後に処理を再開した福田さんの録音が、
 * ①分割アップロード中に放置検知で取り消され ②送信位置のずれ(wrong offset)でエラーになった。
 * 文字起こしまで進まなかった(処理の時刻の記録がない)行だけを、順番待ちへ戻す。
 */
function recoverResumedVoiceLogsOnce_(ss) {
  var props = PropertiesService.getScriptProperties();
  var flag = "VOICE_RESUME_RECOVERY_20261027_DONE";
  if (props.getProperty(flag)) return;
  var from = new Date(2026, 9, 26, 17, 0).getTime();
  readVoiceLogRows_(ss).forEach(function (r) {
    if (r["ステータス"] !== "エラー") return;
    var note = String(r["エラー内容"] || "");
    if (note !== VOICE_LOG_STALE_ERROR_MESSAGE && !/wrong offset/i.test(note)) return;
    var at = parseVoiceLogReceivedAt_(r["受信日時"]);
    if (!at || at.getTime() < from) return;
    if (props.getProperty(VOICE_LOG_CLOCK_PREFIX + r["処理ID"])) return;
    transitionVoiceLogStatus_(ss, r.sheetRow, ["エラー"], { "ステータス": "受信済み", "エラー内容": "" });
    console.log("残高の補充後に止まった録音を、順番待ちへ戻しました");
  });
  props.setProperty(flag, String(Date.now()));
}

