/**
 * GLOW企業リレーション台帳: 生存信号(healthchecks.io)の送信 — 監視C方式
 *
 * 2026-11-06 小柳さん承認(監視C+D方式。ローカル実装と合成テストまで。本番チェックの作成・反映は別承認)。
 * 背景: GitHub の定期実行(3時間おきの点検)は、この repo では予定の半分前後しか動かない日がある。
 * そこで、台帳の毎分の処理が「最後まで正常に終わった」ときだけ、1時間に1回 healthchecks.io へ信号を送る。
 * 信号が途切れると healthchecks.io が知らせる(GitHub に頼らない見張り役)。
 *
 * - 送り先はスクリプトプロパティ HEALTHCHECKS_PING_URL。未設定なら何もしない(今までどおり動く)
 * - 送るのは hc-ping.com への GET だけ。台帳の中身・顧客情報は送らない(heartbeatPing.js で形を確かめる)
 * - 送れなくても、例外はここで受け止めて台帳の処理を止めない
 * - 送り先のURLはログ・稼働状況タブに書かない
 */

var HEARTBEAT_URL_PROPERTY = "HEALTHCHECKS_PING_URL";
var HEARTBEAT_STATE_PROPERTY = "HEALTHCHECKS_LAST_PING";
var HEARTBEAT_OPS_NAME = "生存信号(healthchecks.io)";

/**
 * 毎分の時間主導トリガーの入口(トリガー名は変えない: 既存のトリガーと点検の処理名がこの名前を見ている)。
 * 本体の例外は受け止めずに上へ投げる(Apps Script の「トリガーの失敗通知」= D方式が届くように)。
 */
function processQueuedVoiceLogs() {
  VOICE_RUN_STEP_ERRORS = 0;
  processQueuedVoiceLogsCore_();
  sendHeartbeatIfDue_({
    completed: true,
    stepErrors: VOICE_RUN_STEP_ERRORS,
    elapsedMs: voiceRunElapsedMs_()
  });
}

/**
 * 生存信号を送る時期なら送る。どんな失敗も台帳の処理へ持ち込まない。
 *
 * 毎分のトリガーは前の実行が終わる前に次が始まることがあるため、同じ信号を2つの実行が送らないよう、
 * 「送る番を取る」(状態を ok:false で先に書く)ところだけをロックで囲む。
 * - ロックは UserLock を使う。台帳の書き込み(DocumentLock)や録音の送信(ScriptLock)とは別のロックなので、
 *   信号のために台帳の処理を待たせない。取れなければ待たずに諦め、次の実行に回す
 * - 通信はロックの外で行う(通信が遅くても他の実行を止めない)
 * - 番を取ったあと通信の途中で実行が打ち切られても、状態は ok:false のままなので、10分後に送り直す
 */
function sendHeartbeatIfDue_(run) {
  try {
    var props = PropertiesService.getScriptProperties();
    var url = GlowHeartbeat.normalizePingUrl(props.getProperty(HEARTBEAT_URL_PROPERTY));
    if (!url) return;
    var now = Date.now();
    if (!claimHeartbeatTurn_(props, now, run)) return;

    var ok = false;
    var detail = "";
    try {
      var response = UrlFetchApp.fetch(url, { method: "get", muteHttpExceptions: true, followRedirects: false });
      var code = response.getResponseCode();
      ok = GlowHeartbeat.isPingSuccess(code);
      detail = "HTTP " + code;
    } catch (fetchError) {
      detail = GlowHeartbeat.describeError(fetchError);
    }
    props.setProperty(HEARTBEAT_STATE_PROPERTY, GlowHeartbeat.serializeState({ at: now, ok: ok }));
    if (!ok) console.warn("生存信号を送れませんでした: " + detail);
    recordOpsStatus_(HEARTBEAT_OPS_NAME, ok, ok ? "送信済み" : "送信できず(" + detail + ")。10分後に送り直します");
  } catch (error) {
    console.warn("生存信号の処理に失敗しました: " + GlowHeartbeat.describeError(error));
  }
}

/** 送る時期かを決め、送るならロックの中で番を取る。送ってよければ true。 */
function claimHeartbeatTurn_(props, now, run) {
  var lock = LockService.getUserLock();
  if (!lock.tryLock(100)) return false;
  try {
    var decision = GlowHeartbeat.decidePing({
      nowMs: now,
      state: GlowHeartbeat.parseState(props.getProperty(HEARTBEAT_STATE_PROPERTY)),
      completed: run.completed,
      stepErrors: run.stepErrors,
      elapsedMs: run.elapsedMs
    });
    if (!decision.send) return false;
    props.setProperty(HEARTBEAT_STATE_PROPERTY, GlowHeartbeat.serializeState({ at: now, ok: false }));
    return true;
  } finally {
    lock.releaseLock();
  }
}

/** 設定の確かめ用(エディタから手で実行)。今の設定と前回の送信結果を表示する。URLは表示しない。 */
function showHeartbeatStatus() {
  var props = PropertiesService.getScriptProperties();
  var raw = props.getProperty(HEARTBEAT_URL_PROPERTY);
  var url = GlowHeartbeat.normalizePingUrl(raw);
  var state = GlowHeartbeat.parseState(props.getProperty(HEARTBEAT_STATE_PROPERTY));
  var lines = [
    "送り先: " + (url ? "設定済み(形は正しい)" : (raw ? "設定されているが形が正しくない(送りません)" : "未設定(送りません)")),
    "前回の送信: " + (state ? new Date(state.at).toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" }) + (state.ok ? " 成功" : " 失敗") : "まだ無し")
  ];
  Logger.log(lines.join("\n"));
  return lines.join("\n");
}
