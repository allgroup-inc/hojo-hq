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

var HEARTBEAT_LOCK_WAIT_MS = 500;

/**
 * 生存信号を送る時期なら送る。どんな失敗も台帳の処理へ持ち込まない。
 *
 * 毎分のトリガーは前の実行が終わる前に次が始まることがあり、またトリガーの持ち主が複数いることがある
 * (installVoiceLogProcessingTrigger は自分のトリガーしか消せないため、別の編集者が復旧メニューを押すと、
 * その人のトリガーも並んで動く)。そこで次のようにする。
 * - ロックは ScriptLock を使う。UserLock は同じ人の実行どうししか排他しないため、持ち主の違う実行を止められない。
 *   ScriptLock はスクリプト全体で1つ(録音の送信 DriveVoiceRunner.gs と共有)。持つのは状態の読み書きの数ミリ秒だけ。
 *   取れなければ(録音の送信中など)待つのは最大0.5秒までで、送らずに次の実行に回す
 * - 送る前に、ロックの中で「送る番」を取る: 送信ごとの識別子を付け、状態を ok:false(失敗扱い)で先に書く
 * - 通信はロックの外で行う(通信が遅くても他の実行を止めない)
 * - 結果は、ロックの中で「今の状態が自分の識別子のままか」を確かめてから書く。自分より新しい送信が番を取って
 *   いたら書かない(古い送信の結果で、新しい状態を上書きしない)
 * - 番を取ったあと通信の途中で実行が打ち切られても、状態は ok:false のままなので、10分後に送り直す
 */
function sendHeartbeatIfDue_(run) {
  try {
    var props = PropertiesService.getScriptProperties();
    var url = GlowHeartbeat.normalizePingUrl(props.getProperty(HEARTBEAT_URL_PROPERTY));
    if (!url) return;
    var now = Date.now();
    var attemptId = newHeartbeatAttemptId_(now);
    if (!claimHeartbeatTurn_(props, now, run, attemptId)) return;

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
    if (!saveHeartbeatResult_(props, now, attemptId, ok)) {
      // 新しい送信が既に番を取っている(または記録できなかった)。結果は書かず、新しい送信に任せる
      console.warn("生存信号の結果を記録しませんでした(より新しい送信があるため、または記録の順番が取れないため): " + detail);
      return;
    }
    if (!ok) console.warn("生存信号を送れませんでした: " + detail);
    recordOpsStatus_(HEARTBEAT_OPS_NAME, ok, ok ? "送信済み" : "送信できず(" + detail + ")。10分後に送り直します");
  } catch (error) {
    console.warn("生存信号の処理に失敗しました: " + GlowHeartbeat.describeError(error));
  }
}

/** 送信ごとの識別子(状態の照合だけに使う。外へは送らない) */
function newHeartbeatAttemptId_(now) {
  try {
    return Utilities.getUuid();
  } catch (e) {
    return String(now) + "-" + String(Math.random()).slice(2);
  }
}

/** 送る時期かを決め、送るならロックの中で番を取る(識別子付きで ok:false を書く)。送ってよければ true。 */
function claimHeartbeatTurn_(props, now, run, attemptId) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(HEARTBEAT_LOCK_WAIT_MS)) return false;
  try {
    var decision = GlowHeartbeat.decidePing({
      nowMs: now,
      state: GlowHeartbeat.parseState(props.getProperty(HEARTBEAT_STATE_PROPERTY)),
      completed: run.completed,
      stepErrors: run.stepErrors,
      elapsedMs: run.elapsedMs
    });
    if (!decision.send) return false;
    props.setProperty(HEARTBEAT_STATE_PROPERTY, GlowHeartbeat.serializeState({ at: now, ok: false, id: attemptId }));
    return true;
  } finally {
    lock.releaseLock();
  }
}

/** 結果を書く。今の状態が自分の番(同じ識別子)のときだけ書き、書けたら true。 */
function saveHeartbeatResult_(props, at, attemptId, ok) {
  var lock = LockService.getScriptLock();
  // 取れなければ書かない。状態は ok:false のまま残り、10分後に送り直す(信号が1回余分に届くだけで害は無い)
  if (!lock.tryLock(HEARTBEAT_LOCK_WAIT_MS)) return false;
  try {
    var current = GlowHeartbeat.parseState(props.getProperty(HEARTBEAT_STATE_PROPERTY));
    if (!GlowHeartbeat.isSameAttempt(current, attemptId)) return false;
    props.setProperty(HEARTBEAT_STATE_PROPERTY, GlowHeartbeat.serializeState({ at: at, ok: ok, id: attemptId }));
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
