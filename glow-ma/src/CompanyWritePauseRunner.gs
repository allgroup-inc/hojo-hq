/**
 * GLOW企業リレーション台帳: 企業マスタの書き込みの緊急停止スイッチ(操作と状態の読み書き)
 *
 * 判定は companyWritePause.js(GlowCompanyWritePause)。ここは、スクリプトプロパティ・画面・通知とのやり取りだけ。
 *
 * 止まるもの: 企業マスタを一括で書き直す処理(writeCompanyRecords_ を通る6つ: スコアの再計算・お断りの反映・
 *   インポート・事前選定・過去記録の取り込み・試験データの片付け)。
 * 止まらないもの: 読むだけの処理(ダッシュボード・今日の連絡先・アラートなど)、台帳のバックアップ、
 *   担当者の記録に伴う1社ずつの更新(管理画面・LINEの録音・発送)。
 *
 * 使い方(台帳のメニュー「GLOW台帳」):
 *   - 企業マスタの書き込みを止める(緊急停止) … 台帳を編集できる人なら誰でも。確認と理由が要る
 *   - 企業マスタの書き込みを再開する(代表者のみ) … 台帳の持ち主だけ。「再開」と入力し、承認の記録を書く
 *   - 企業マスタの書き込みの状態・履歴を見る
 * メニューを開けないとき(止めるだけ): Apps Script エディタで emergencyStopCompanyWrites を実行する。
 */

/** 今の停止の状態。プロパティを読めないときは、停止中として扱う(止まる側に倒す) */
function readCompanyWritePause_() {
  try {
    var raw = PropertiesService.getScriptProperties().getProperty(GlowCompanyWritePause.STATE_PROPERTY);
    return GlowCompanyWritePause.parseState(raw);
  } catch (error) {
    return { paused: true, at: "", by: "", unreadable: true,
      reason: "停止の状態を読めなかったため、停止中として扱っています(" + error + ")" };
  }
}

/**
 * 停止中なら例外を投げる(企業マスタを書く処理の最初に呼ぶ)。
 * 例外には companyWrite = { phase: "paused", dataChanged: false, paused: true } を付ける。
 * 人が決めて止めている状態なので、失敗としては記録・通知しない(毎朝のお知らせは日次メンテナンスが出す)。
 */
function assertCompanyWriteNotPaused_() {
  var state = readCompanyWritePause_();
  if (!state.paused) return;
  var error = new Error(GlowCompanyWritePause.pausedMessage(state));
  error.companyWrite = { phase: "paused", dataChanged: false, paused: true };
  throw error;
}

function companyWritePauseNow_() {
  return Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm");
}

function companyWritePauseActor_() {
  try {
    return Session.getEffectiveUser().getEmail() || "";
  } catch (error) {
    return "";
  }
}

function companyWritePauseOwner_() {
  try {
    var owner = SpreadsheetApp.getActiveSpreadsheet().getOwner();
    return owner ? owner.getEmail() || "" : "";
  } catch (error) {
    return "";
  }
}

/** 操作の記録を残す(プロパティ・実行記録)。記録の失敗で操作そのものは止めない */
function recordCompanyWritePauseHistory_(action, by, note) {
  var entry = { at: companyWritePauseNow_(), action: action, by: by, note: note };
  try {
    var props = PropertiesService.getScriptProperties();
    props.setProperty(GlowCompanyWritePause.HISTORY_PROPERTY,
      GlowCompanyWritePause.appendHistory(props.getProperty(GlowCompanyWritePause.HISTORY_PROPERTY), entry));
  } catch (error) {
    Logger.log("企業マスタの書き込み停止スイッチ: 操作の記録を保存できませんでした: " + error);
  }
  Logger.log("企業マスタの書き込み停止スイッチ: " + action + " / " + entry.at);
}

/**
 * 止める(画面なし)。メニューとエディタの両方から使う。すでに停止中なら何も変えない。
 * @return {Object} { changed, state }
 */
function pauseCompanyWritesNow_(by, reason) {
  var current = readCompanyWritePause_();
  if (current.paused && !current.unreadable) return { changed: false, state: current };
  var at = companyWritePauseNow_();
  PropertiesService.getScriptProperties().setProperty(
    GlowCompanyWritePause.STATE_PROPERTY, GlowCompanyWritePause.buildStopState(at, by, reason));
  var state = readCompanyWritePause_();
  recordCompanyWritePauseHistory_("stop", by, reason);
  recordOpsStatus_(GlowCompanyWritePause.OPS_NAME, "停止中", GlowCompanyWritePause.describeState(state));
  notifyOpsNotice_("【GLOW台帳】企業マスタの書き込みを止めました",
    "企業マスタの書き込みを止めました。\n" + GlowCompanyWritePause.describeState(state) +
    "\n\n止まるもの: スコアの再計算・お断り(連絡不要)の反映・インポート・事前選定・過去記録の取り込み。" +
    "\n続くもの: バックアップ・ダッシュボード・今日の連絡先・アラート・担当者の記録。" +
    "\n自動では再開しません。再開は、代表者の承認の後、台帳のメニュー「GLOW台帳 → 企業マスタの書き込みを再開する」から。");
  return { changed: true, state: state };
}

/** メニュー: 企業マスタの書き込みを止める(緊急停止) */
function stopCompanyWrites() {
  var ui = SpreadsheetApp.getUi();
  var current = readCompanyWritePause_();
  if (current.paused && !current.unreadable) {
    ui.alert("企業マスタの書き込みは、すでに止まっています", GlowCompanyWritePause.describeState(current), ui.ButtonSet.OK);
    return;
  }
  var confirmed = ui.alert("企業マスタの書き込みを止めます",
    "スコアの再計算・お断り(連絡不要)の反映・インポート・過去記録の取り込みが、再開するまで動かなくなります。\n" +
    "バックアップ・ダッシュボード・今日の連絡先・担当者の記録は続きます。\n" +
    "自動では再開しません。再開できるのは代表者だけです。\n\n止めますか?", ui.ButtonSet.YES_NO);
  if (confirmed !== ui.Button.YES) return;
  var answer = ui.prompt("止める理由", "止める理由を書いてください(必須。例: 企業マスタの件数が合わないため)", ui.ButtonSet.OK_CANCEL);
  if (answer.getSelectedButton() !== ui.Button.OK) return;
  var reason = GlowCompanyWritePause.validateNote(answer.getResponseText());
  if (!reason.ok) {
    ui.alert("止めていません", "理由が空のため、止めませんでした。もう一度メニューから操作してください。", ui.ButtonSet.OK);
    return;
  }
  var result = pauseCompanyWritesNow_(companyWritePauseActor_(), reason.note);
  ui.alert("企業マスタの書き込みを止めました", GlowCompanyWritePause.describeState(result.state) +
    "\n\n再開は、代表者の承認の後、メニュー「企業マスタの書き込みを再開する」から。", ui.ButtonSet.OK);
}

/** エディタから止める(メニューを開けないとき用。画面を使わない)。再開はメニューからだけ */
function emergencyStopCompanyWrites() {
  var result = pauseCompanyWritesNow_(companyWritePauseActor_(), "エディタからの緊急停止");
  Logger.log(result.changed ? "企業マスタの書き込みを止めました。" : "すでに止まっています。");
}

/** メニュー: 企業マスタの書き込みを再開する(代表者のみ) */
function resumeCompanyWrites() {
  var ui = SpreadsheetApp.getUi();
  var state = readCompanyWritePause_();
  if (!state.paused) {
    ui.alert("企業マスタの書き込みは止まっていません", "再開の操作は不要です。", ui.ButtonSet.OK);
    return;
  }
  var actor = companyWritePauseActor_();
  var allowed = GlowCompanyWritePause.canResume(actor, companyWritePauseOwner_());
  if (!allowed.ok) {
    recordCompanyWritePauseHistory_("resume_refused", actor, allowed.reason);
    ui.alert("再開できません", allowed.reason + "\n\n" + GlowCompanyWritePause.describeState(state), ui.ButtonSet.OK);
    return;
  }
  var phrase = ui.prompt("企業マスタの書き込みを再開します",
    GlowCompanyWritePause.describeState(state) +
    "\n\n止めた原因が解消し、企業マスタの件数がバックアップと合っていることを確かめてから再開してください。" +
    "\n再開するには「" + GlowCompanyWritePause.RESUME_PHRASE + "」と入力してください。", ui.ButtonSet.OK_CANCEL);
  if (phrase.getSelectedButton() !== ui.Button.OK) return;
  if (!GlowCompanyWritePause.isResumePhrase(phrase.getResponseText())) {
    ui.alert("再開していません", "「" + GlowCompanyWritePause.RESUME_PHRASE + "」と入力されなかったため、停止のままです。", ui.ButtonSet.OK);
    return;
  }
  var approval = ui.prompt("承認の記録", "承認の記録を書いてください(必須。例: 11/20 件数の一致を確認・小柳承認)", ui.ButtonSet.OK_CANCEL);
  if (approval.getSelectedButton() !== ui.Button.OK) return;
  var note = GlowCompanyWritePause.validateNote(approval.getResponseText());
  if (!note.ok) {
    ui.alert("再開していません", "承認の記録が空のため、停止のままです。", ui.ButtonSet.OK);
    return;
  }
  PropertiesService.getScriptProperties().deleteProperty(GlowCompanyWritePause.STATE_PROPERTY);
  recordCompanyWritePauseHistory_("resume", actor, note.note);
  recordOpsStatus_(GlowCompanyWritePause.OPS_NAME, "稼働中", "再開 " + companyWritePauseNow_() + " / 承認の記録: " + note.note);
  notifyOpsNotice_("【GLOW台帳】企業マスタの書き込みを再開しました",
    "企業マスタの書き込みを再開しました。\n止めていた内容: " + GlowCompanyWritePause.describeState(state) +
    "\n承認の記録: " + note.note + "\n\n次の日次メンテナンス(毎朝7時台)から、スコアの再計算とお断りの反映が動きます。");
  ui.alert("企業マスタの書き込みを再開しました", "次の日次メンテナンス(毎朝7時台)から、スコアの再計算とお断りの反映が動きます。", ui.ButtonSet.OK);
}

/** メニュー: 企業マスタの書き込みの状態・履歴を見る */
function showCompanyWritePauseStatus() {
  var history = "";
  try {
    history = PropertiesService.getScriptProperties().getProperty(GlowCompanyWritePause.HISTORY_PROPERTY);
  } catch (error) {
    history = "";
  }
  SpreadsheetApp.getUi().alert("企業マスタの書き込みの状態",
    GlowCompanyWritePause.describeState(readCompanyWritePause_()) +
    "\n\n直近の操作:\n" + GlowCompanyWritePause.describeHistory(history), SpreadsheetApp.getUi().ButtonSet.OK);
}

/** 台帳を開いたとき、停止中なら右下に知らせる(onOpen から呼ぶ。失敗しても台帳は開ける) */
function showCompanyWritePauseToast_() {
  try {
    var state = readCompanyWritePause_();
    if (!state.paused) return;
    SpreadsheetApp.getActiveSpreadsheet().toast(GlowCompanyWritePause.describeState(state), "企業マスタの書き込みは停止中です", 20);
  } catch (error) {
    Logger.log("停止中のお知らせを出せませんでした: " + error);
  }
}
