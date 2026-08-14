/**
 * アポ管理コンソール: Web Appランナー(ルーティング・シートI/O・Slack送信)
 *
 * ロジックは持たず、UMDモジュール(ApoSchema / ApoAccess / ApoCore / ApoNotify /
 * ApoPage / ApoResilience)へ委譲する薄い層。Nodeテストの対象外。
 *
 * セットアップ(人間が一度だけ行う):
 * 1. SheetSetup.gs の手順で ensureApoTabs 実行済みであること
 * 2. 「スタッフ」タブに全利用者の 氏名 / Slack User ID / 有効✔ / メールアドレス / 役割 を登録する
 * 3. Slackで通知チャンネル用の Incoming Webhook を発行し、Apps Scriptエディタの
 *    「プロジェクトの設定」→「スクリプト プロパティ」で SLACK_WEBHOOK_URL に設定する
 *    (コードにWebhook URLを直接書かない。未設定時は通知をスキップしログのみ)
 * 4. 「デプロイ」→「新しいデプロイ」→種類「ウェブアプリ」。実行ユーザー: 自分。
 *    アクセスできるユーザー: 「Googleアカウントを持つ全員」
 * 5. デプロイURLをスタッフタブに登録した人へ共有する(スマホのホーム画面に追加推奨)
 *
 * 認証: 個人Gmail運用のためWeb Appのアクセス設定では利用者を限定できない。
 * Session.getActiveUser().getEmail() をスタッフタブと照合する許可リスト方式が唯一の
 * 防御線のため、doGet だけでなく公開関数(末尾 `_` なし)それぞれの冒頭でも
 * requireApoAccess_ を呼ぶ(多層防御。glow-ma 三名体制レビュー2026-08-09と同方式)。
 */

function doGet() {
  if (!isApoStaff_()) {
    return HtmlService.createHtmlOutput(ApoAccess.buildAccessDeniedHtml());
  }
  return HtmlService.createHtmlOutput(ApoPage.buildApoAppHtml())
    .setTitle("家計のポッ")
    .addMetaTag("viewport", "width=device-width, initial-scale=1");
}

function isApoStaff_() {
  var email = Session.getActiveUser().getEmail();
  return ApoAccess.isAllowedEmail(email, readStaffRows_());
}

function requireApoAccess_() {
  if (!isApoStaff_()) {
    throw new Error("この操作を行う権限がありません。");
  }
}

function readStaffRows_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(ApoSchema.STAFF_SHEET_NAME);
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = ApoSchema.STAFF_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var nameIndex = headers.indexOf("氏名");
  var slackIndex = headers.indexOf("Slack User ID");
  var activeIndex = headers.indexOf("有効");
  var emailIndex = headers.indexOf("メールアドレス");
  var roleIndex = headers.indexOf("役割");
  return values
    .filter(function (row) { return row[activeIndex] === true && row[emailIndex]; })
    .map(function (row) {
      return {
        name: row[nameIndex],
        slackUserId: row[slackIndex],
        email: row[emailIndex],
        role: row[roleIndex]
      };
    });
}

/**
 * アポ予定タブの全行をレコード配列で返す。日付・時刻は文字列に正規化する
 * (google.script.run はDateの受け渡しで事故りやすいため、サーバ側で常に文字列化)。
 */
function readAppointments_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(ApoSchema.APPOINTMENT_SHEET_NAME);
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = ApoSchema.APPOINTMENT_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  return values.map(function (row) {
    var record = {};
    headers.forEach(function (header, index) { record[header] = row[index]; });
    record["日付"] = ApoCore.normalizeDateString(record["日付"]);
    record["開始時刻"] = ApoCore.normalizeTimeString(record["開始時刻"]);
    record["登録日時"] = String(record["登録日時"] || "");
    record["最終更新日時"] = String(record["最終更新日時"] || "");
    return record;
  });
}

function nowStamp_() {
  return Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm:ss");
}

/**
 * 本日ビュー・週ビュー・スタッフ選択肢をまとめて返す。
 * params: { view: "day"|"week", date: "yyyy-MM-dd", owner: 担当営業名 or "" }
 */
function getBoard(params) {
  requireApoAccess_();
  var options = params || {};
  var date = options.date || ApoCore.normalizeDateString(new Date());
  var owner = options.owner || null;
  var appointments = readAppointments_();
  var staffRows = readStaffRows_();
  var meName = ApoAccess.resolveStaffName(Session.getActiveUser().getEmail(), staffRows);
  return {
    date: date,
    dayView: ApoCore.buildDayView(appointments, date, owner),
    week: ApoCore.buildWeekView(
      owner
        ? appointments.filter(function (a) { return a["担当営業"] === owner; })
        : appointments,
      date
    ),
    salesStaff: ApoAccess.listSalesStaff(staffRows),
    meName: meName
  };
}

/**
 * 分析タブ用の集計: 本日の埋まり状況(営業別)+過去30日の転換ファネル(チーム全体のみ)。
 * 営業マン別の転換率は評価誤用リスクのため返さない(v1.1三名体制裁定)。
 */
function getStats() {
  requireApoAccess_();
  var appointments = readAppointments_();
  var staffRows = readStaffRows_();
  var today = ApoCore.normalizeDateString(new Date());
  var since = ApoCore.normalizeDateString(new Date(Date.now() - 30 * 24 * 60 * 60 * 1000));
  return {
    date: today,
    sinceDate: since,
    fill: ApoCore.buildFillStats(appointments, today, ApoAccess.listSalesStaff(staffRows)),
    funnel: ApoCore.buildConversionStats(appointments, { sinceDate: since }),
    byTemperature: ApoCore.buildTemperatureStats(appointments, { sinceDate: since })
  };
}

function getFormOptions() {
  requireApoAccess_();
  var staffRows = readStaffRows_();
  return {
    salesStaff: ApoAccess.listSalesStaff(staffRows),
    setterStaff: ApoAccess.listSetterStaff(staffRows),
    formats: ApoSchema.APPOINTMENT_FORMATS,
    temperatures: ApoSchema.TEMPERATURES,
    statuses: ApoSchema.APPOINTMENT_STATUSES
  };
}

/**
 * 新規登録・編集の両方を受ける。ダブルブッキングは警告のみで登録は止めない:
 * confirmedOverlap=false で重複ありなら保存せず警告を返し、画面がもう一度
 * 保存させることで「警告を見たうえでの登録」にする(2度押し確定方式)。
 */
function saveAppointment(payload) {
  requireApoAccess_();
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(20000)) {
    throw new Error("他の操作が実行中のため保存できませんでした。少し待ってからもう一度お試しください。");
  }
  try {
    var appointments = readAppointments_();
    var overlaps = ApoCore.detectOverlap(appointments, payload);
    if (overlaps.length > 0 && !payload.confirmedOverlap) {
      return {
        ok: false,
        overlapWarning: overlaps.map(function (apo) {
          return { "開始時刻": apo["開始時刻"], "顧客名": apo["顧客名"] };
        })
      };
    }

    var staffRows = readStaffRows_();
    var operator = ApoAccess.resolveStaffName(Session.getActiveUser().getEmail(), staffRows);
    var salesStaff = ApoAccess.findStaffByName(payload["担当営業"], staffRows);
    var mention = ApoNotify.formatMention(salesStaff && salesStaff.slackUserId, payload["担当営業"]);

    if (payload["アポID"]) {
      var oldRecord = findAppointmentById_(appointments, payload["アポID"]);
      if (!oldRecord) throw new Error("対象のアポが見つかりません: " + payload["アポID"]);
      var diff = ApoCore.buildChangeDiff(oldRecord, payload);
      updateAppointmentRow_(payload);
      if (diff) {
        appendHistory_(payload["アポID"], operator, "変更", diff);
        notifySafely_(payload["アポID"], operator, "変更",
          buildStatusAwareMessage_(payload, oldRecord["ステータス"], diff, mention));
      }
      return { ok: true, apoId: payload["アポID"] };
    }

    var apoId = generateUniqueApoId_(appointments);
    payload["アポID"] = apoId;
    appendAppointmentRow_(payload);
    appendHistory_(apoId, operator, "新規", ApoCore.buildChangeDiff({}, payload));
    notifySafely_(apoId, operator, "新規", ApoNotify.buildNewAppointmentMessage(payload, mention));
    return { ok: true, apoId: apoId };
  } finally {
    lock.releaseLock();
  }
}

/**
 * カードのアクションシートからのステータスだけの更新(2タップ操作)。
 * 履歴・通知は saveAppointment の編集と同じ扱いにする。
 */
function updateStatus(apoId, status) {
  requireApoAccess_();
  if (ApoSchema.APPOINTMENT_STATUSES.indexOf(status) === -1) {
    throw new Error("不正なステータスです: " + status);
  }
  var appointments = readAppointments_();
  var record = findAppointmentById_(appointments, apoId);
  if (!record) throw new Error("対象のアポが見つかりません: " + apoId);
  var updated = {};
  Object.keys(record).forEach(function (key) { updated[key] = record[key]; });
  updated["ステータス"] = status;
  updated.confirmedOverlap = true;
  return saveAppointment(updated);
}

/**
 * 遅れそうワンタップ連絡。操作者(営業)の本日・現時刻以降のアポを抽出し、
 * 各アポのアポ入れ担当へSlack通知する。アポの時刻は変更しない
 * (設計書 三名体制裁定①: 判断は人間・通知のみ)。
 */
function reportDelay(minutes) {
  requireApoAccess_();
  var staffRows = readStaffRows_();
  var operator = ApoAccess.resolveStaffName(Session.getActiveUser().getEmail(), staffRows);
  var today = ApoCore.normalizeDateString(new Date());
  var nowTime = Utilities.formatDate(new Date(), "Asia/Tokyo", "HH:mm");
  var targets = ApoCore.buildDelayTargets(readAppointments_(), operator, today, nowTime);
  var mentionResolver = function (setterName) {
    var setter = ApoAccess.findStaffByName(setterName, staffRows);
    return ApoNotify.formatMention(setter && setter.slackUserId, setterName);
  };
  var firstApoId = targets.length > 0 ? targets[0]["アポID"] : "-";
  appendHistory_(firstApoId, operator, "遅延連絡",
    "+" + minutes + "分遅れ見込み(影響しうる後続アポ " + targets.length + "件)");
  notifySafely_(firstApoId, operator, "遅延連絡",
    ApoNotify.buildDelayMessage(operator, minutes, targets, mentionResolver));
  return { ok: true, targetCount: targets.length };
}

// ---- 内部ヘルパー ----

function findAppointmentById_(appointments, apoId) {
  return appointments.filter(function (a) { return a["アポID"] === apoId; })[0] || null;
}

function generateUniqueApoId_(appointments) {
  for (var attempt = 0; attempt < 5; attempt++) {
    var apoId = ApoCore.generateApoId(new Date(), Math.random);
    if (!findAppointmentById_(appointments, apoId)) return apoId;
  }
  throw new Error("アポIDの採番に失敗しました。もう一度お試しください。");
}

function payloadToRow_(payload) {
  return ApoSchema.APPOINTMENT_HEADERS.map(function (header) {
    var value = payload[header];
    return value === undefined || value === null ? "" : value;
  });
}

function appendAppointmentRow_(payload) {
  payload["登録日時"] = nowStamp_();
  payload["最終更新日時"] = nowStamp_();
  var sheet = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName(ApoSchema.APPOINTMENT_SHEET_NAME);
  sheet.appendRow(payloadToRow_(payload));
}

function updateAppointmentRow_(payload) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName(ApoSchema.APPOINTMENT_SHEET_NAME);
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) throw new Error("アポ予定タブにデータがありません。");
  var idColumn = ApoSchema.APPOINTMENT_HEADERS.indexOf("アポID") + 1;
  var ids = sheet.getRange(2, idColumn, lastRow - 1, 1).getValues();
  for (var i = 0; i < ids.length; i++) {
    if (ids[i][0] === payload["アポID"]) {
      var existing = readAppointments_()[i];
      payload["登録日時"] = existing ? existing["登録日時"] : nowStamp_();
      payload["最終更新日時"] = nowStamp_();
      sheet.getRange(i + 2, 1, 1, ApoSchema.APPOINTMENT_HEADERS.length)
        .setValues([payloadToRow_(payload)]);
      return;
    }
  }
  throw new Error("対象のアポ行が見つかりません: " + payload["アポID"]);
}

function appendHistory_(apoId, operator, operation, detail) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName(ApoSchema.HISTORY_SHEET_NAME);
  if (!sheet) return;
  var historyId = "H-" + Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyyMMddHHmmss") +
    "-" + Math.floor(Math.random() * 1000);
  sheet.appendRow([historyId, apoId, nowStamp_(), operator, operation, detail || ""]);
}

/**
 * ステータス変化に応じて通知種別を出し分ける(申込み🎉/キャンセル❌/その他は変更🔁)。
 */
function buildStatusAwareMessage_(payload, oldStatus, diff, mention) {
  var newStatus = payload["ステータス"];
  if (newStatus !== oldStatus) {
    if (newStatus === "申込み") return ApoNotify.buildSignupMessage(payload, mention);
    if (newStatus.indexOf("キャンセル") === 0) {
      return ApoNotify.buildCancelMessage(payload, newStatus, mention);
    }
  }
  return ApoNotify.buildChangeMessage(payload, diff, mention);
}

/**
 * Slack通知。失敗しても保存は成功扱い(保存が正・通知は従)。失敗は変更履歴に記録する。
 */
function notifySafely_(apoId, operator, operation, message) {
  try {
    postToApoSlack_(message);
  } catch (error) {
    Logger.log("Slack通知に失敗しました: " + error);
    appendHistory_(apoId, operator, operation, "Slack通知失敗: " + error);
  }
}

function postToApoSlack_(message) {
  var webhookUrl = PropertiesService.getScriptProperties().getProperty("SLACK_WEBHOOK_URL");
  if (!webhookUrl) {
    Logger.log("SLACK_WEBHOOK_URL が未設定のため通知をスキップしました: " + message);
    return;
  }
  ApoResilience.withRetry(function () {
    var response = UrlFetchApp.fetch(webhookUrl, {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify({ text: message }),
      muteHttpExceptions: true
    });
    var code = response.getResponseCode();
    if (code >= 300) {
      var error = new Error("Slack通知が失敗しました: HTTP " + code);
      error.statusCode = code;
      throw error;
    }
  }, {
    isRetryable: function (error) {
      return ApoResilience.isRetryableHttpStatus(error.statusCode || 0);
    },
    sleepFn: function (ms) { Utilities.sleep(ms); }
  });
}
