/* GLOW企業リレーション台帳 録音ファイル(Googleドライブ経由)の受付ロジック(2026-10-26 追加)
 * ブラウザ相当のGAS(global.GlowVoiceFileIntake)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_voice_file_intake.test.mjs で検証される。
 *
 * 背景(福田さん 2026-10-26): LINEのボイスメッセージは最大30分・スリープで停止・送信後にデータが
 * 消えることがあり、面談の記録に使いにくい。録音アプリ(PCM録音等)で保存したWAV/AACを、
 * 決められたドライブのフォルダに入れるだけで、LINE音声と同じ流れ(文字起こし→要約→確認→台帳へ記録、
 * 企業の関係メモへ要約を追記)に乗せる。大きなファイルは分割してGeminiへ送る。
 */
(function (global) {
  "use strict";

  var AUDIO_MIME_BY_EXT = {
    wav: "audio/wav", aac: "audio/aac", m4a: "audio/mp4", mp3: "audio/mp3",
    ogg: "audio/ogg", flac: "audio/flac", aiff: "audio/aiff", aif: "audio/aiff"
  };
  // 取り込み済みの印(ファイル名の先頭に付ける)。付いているファイルは二度と受け付けない
  var DONE_PREFIX = "受付済_";
  // LINEメッセージID欄に入れる、ドライブ由来の印
  var DRIVE_ID_PREFIX = "drive:";
  // Gemini のアップロードは 8MiB の倍数で区切る必要がある(最後の1回を除く)
  var CHUNK_BYTES = 16 * 1024 * 1024;
  // これより小さければ、従来どおり音声をそのまま送る(分割アップロード不要)
  var INLINE_MAX_BYTES = 14 * 1024 * 1024;

  function extOf(name) {
    var m = /\.([A-Za-z0-9]+)$/.exec(String(name || ""));
    return m ? m[1].toLowerCase() : "";
  }

  function audioMimeType(name, fallback) {
    return AUDIO_MIME_BY_EXT[extOf(name)] || fallback || "";
  }

  function isAcceptableFileName(name) {
    var n = String(name || "");
    return n.indexOf(DONE_PREFIX) !== 0 && !!AUDIO_MIME_BY_EXT[extOf(n)];
  }

  function toDriveMessageId(fileId) { return DRIVE_ID_PREFIX + fileId; }

  function driveFileIdOf(messageId) {
    var s = String(messageId || "");
    return s.indexOf(DRIVE_ID_PREFIX) === 0 ? s.slice(DRIVE_ID_PREFIX.length) : "";
  }

  /**
   * スタッフタブの「メールアドレス」欄から、メールアドレスの一覧を取り出す。
   * 1人が複数のGoogleアカウントを使うことがある(仕事用とドライブ用が別など)ため、
   * 「,」「、」「;」・空白・改行で区切って複数書けるようにする(2026-10-26)。小文字にそろえる。
   */
  function staffEmails(cell) {
    return String(cell || "").split(/[,、;；\s]+/).map(function (e) {
      return e.trim().toLowerCase();
    }).filter(function (e) { return e.indexOf("@") > 0; });
  }

  /** 次に送る範囲 {start, end(含む), isLast}。全部送り終えていれば null */
  function nextChunk(offset, totalBytes, chunkBytes) {
    var size = chunkBytes || CHUNK_BYTES;
    if (offset >= totalBytes) return null;
    var end = Math.min(offset + size, totalBytes) - 1;
    return { start: offset, end: end, isLast: end === totalBytes - 1 };
  }

  /**
   * Gemini の「Client uploaded to the wrong offset (送った位置 instead of 正しい位置)」から、
   * 正しい位置(バイト)を取り出す。読めなければ null
   */
  function expectedUploadOffset(text) {
    var m = /wrong offset \((\d+) instead of (\d+)\)/i.exec(String(text || ""));
    return m ? Number(m[2]) : null;
  }

  /**
   * フォルダ内のファイルから、今回受け付けるものを選ぶ。
   * files: [{id, name, ownerEmail}]、staff: [{email, name, lineUserId}]、
   * knownMessageIds: 音声ログ処理状況にあるLINEメッセージID、busyLineUserIds: 処理中の担当者
   * 戻り値: { accept: [{file, staff}], skip: [{file, reason}] }
   * 1人の担当者につき同時に1件(LINE音声と同じ。確認ボタンが混ざらないように)
   */
  function planIntake(files, staff, knownMessageIds, busyLineUserIds) {
    var known = {};
    (knownMessageIds || []).forEach(function (id) { known[String(id)] = true; });
    var busy = {};
    (busyLineUserIds || []).forEach(function (id) { busy[String(id)] = true; });
    var byEmail = {};
    (staff || []).forEach(function (s) {
      if (!s) return;
      staffEmails(s.email).forEach(function (email) { byEmail[email] = s; });
    });
    var accept = [], skip = [];
    (files || []).forEach(function (f) {
      if (!isAcceptableFileName(f.name)) return;
      if (known[toDriveMessageId(f.id)]) return;
      var s = byEmail[String(f.ownerEmail || "").trim().toLowerCase()];
      if (!s) { skip.push({ file: f, reason: "スタッフ登録のないアカウントのファイル" }); return; }
      if (!s.lineUserId) { skip.push({ file: f, reason: "担当者のLINE User IDが未登録(確認ボタンを送れない)" }); return; }
      if (busy[s.lineUserId]) { skip.push({ file: f, reason: "同じ担当者の別の録音を処理中" }); return; }
      busy[s.lineUserId] = true;
      accept.push({ file: f, staff: s });
    });
    return { accept: accept, skip: skip };
  }

  /** Gemini への指示に足す、ファイル名からのヒント(会社名・日付が入っていることが多い) */
  function fileNameHint(name) {
    var base = String(name || "").replace(/\.[A-Za-z0-9]+$/, "").replace(/^受付済_/, "");
    if (!base) return "";
    return "参考: 録音ファイル名は「" + base + "」です。会社名や日付が含まれていれば手がかりにしてよいが、" +
      "音声の内容と食い違う場合は音声を優先すること。";
  }

  /**
   * Gemini が「支払いが必要(402)」を返した失敗か(前払い残高の不足など)。
   * この失敗は待っても直らないが、残高を補充すれば同じ録音でそのまま処理できるため、
   * 「エラー」で確定させずに待機させる(2026-10-26 福田さんの録音3件で発生)。
   */
  function isBillingError(error) {
    if (error && Number(error.statusCode) === 402) return true;
    return /(HTTP |ステータスコード )402\b/.test(String(error || ""));
  }

  var BILLING_WAIT_NOTE = "AIの利用枠(残高)の不足で待機中。補充されしだい自動で再開します";

  /**
   * 確認ボタンを押してもらう期限: 確認を送った日(日本時間)の翌日の正午(2026-10-29 小柳さん決裁)。
   * それまでは2時間で取り消していたが、外回り中・夕方に届くと押せないまま消えていた。
   */
  function confirmDeadlineMs(startMs) {
    var jst = new Date(Number(startMs) + 9 * 60 * 60 * 1000);
    return Date.UTC(jst.getUTCFullYear(), jst.getUTCMonth(), jst.getUTCDate() + 1, 3, 0, 0);
  }

  var api = {
    confirmDeadlineMs: confirmDeadlineMs,
    isBillingError: isBillingError,
    BILLING_WAIT_NOTE: BILLING_WAIT_NOTE,
    DONE_PREFIX: DONE_PREFIX,
    CHUNK_BYTES: CHUNK_BYTES,
    INLINE_MAX_BYTES: INLINE_MAX_BYTES,
    audioMimeType: audioMimeType,
    staffEmails: staffEmails,
    isAcceptableFileName: isAcceptableFileName,
    toDriveMessageId: toDriveMessageId,
    driveFileIdOf: driveFileIdOf,
    nextChunk: nextChunk,
    expectedUploadOffset: expectedUploadOffset,
    planIntake: planIntake,
    fileNameHint: fileNameHint
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowVoiceFileIntake = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
