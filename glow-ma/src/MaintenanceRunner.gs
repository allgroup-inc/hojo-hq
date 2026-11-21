/**
 * GLOW企業リレーション台帳: 日次メンテナンス(お断り反映・スコア再計算・ダッシュボード・アラート)
 *
 * 背景(2026-09-03 運用点検で判明):
 * syncDoNotContactFlags / recalculateAllScores / updateDashboard は、いずれも各ファイルの
 * 冒頭コメントに「Apps Scriptエディタで手動実行する。トリガー登録自体は本Planの範囲外」と
 * 書かれたまま本番稼働に入ろうとしていた。担当者が毎日エディタを開いて4つの関数を順に
 * 押すことは現実には起こらないので、次のことが起きる。
 *
 *   - 対応履歴ログに「連絡不要受領」を記録しても企業マスタのフラグが立たず、断った会社に再び架電する
 *   - 訪問ログを入れてもスコアとランクが古いまま更新されず、掘り起こしアラートが的外れな会社を出す
 *   - ダッシュボードの数字が止まり、役員が古い数字で判断する
 *
 * そこで、4つを「正しい順番で」実行する1本の関数にまとめ、日次トリガー1つで回す。
 *
 * 順番には意味がある(入れ替えないこと):
 *   1. バックアップ   … その日の変更を加える前の状態を残す。必ず最初
 *   2. お断りの反映   … 以降の処理が、断られた会社を対象から外せるようにする
 *   3. スコア再計算   … 前日までの対応履歴をランクへ反映する
 *   4. ダッシュボード … 3で確定したスコア・ランクを集計する
 *   5. 掘り起こしアラート … 3のランクを使って通知する
 *
 * 障害隔離: 1つが失敗しても残りは実行する(スコア計算がこけた日にお断りの反映まで
 * 止まると、断った会社への再架電という一番避けたい事故が起きるため)。
 * 失敗はまとめてSlackへ通知する。黙って失敗し続ける状態を作らないこと自体が目的。
 *
 * セットアップ(人間が一度だけ行う):
 *   1. `clasp push` で最新コードを反映する
 *   2. Apps Scriptエディタで installDailyMaintenanceTrigger を一度だけ実行する(冪等)
 *   3. Apps Scriptエディタの「トリガー」画面で、登録されたトリガーの
 *      「エラー通知設定」を「毎回通知」にする
 */

/** 日次メンテナンスの実行時刻(24時間表記)。営業開始前に終わらせる。 */
var DAILY_MAINTENANCE_HOUR = 7;

/**
 * 日次メンテナンスの本体。各ステップは独立して失敗しうるものとして扱い、
 * 失敗しても次のステップへ進む。最後に結果をまとめてSlackへ通知する。
 */
function runDailyMaintenance() {
  var steps = [
    // master: その手順が企業マスタを "write"(書き直す)・"read"(読むだけ)・"none"(使わない)のどれか。
    // 企業マスタの書き込みを止めたときに、どの手順まで止めるかをこれで決める(下の stopsStep_)
    { name: "台帳のバックアップ", run: backupLedger, master: "none" },
    { name: "お断り(連絡不要)の反映", run: syncDoNotContactFlags, master: "write" },
    { name: "スコア・ランクの再計算", run: recalculateAllScores, master: "write" },
    { name: "ダッシュボードの更新", run: updateDashboard, master: "read" },
    // 2026-11-07 改善③: 3で確定したスコアを使って「今日の連絡先」タブを作り直す(台帳の記録は書き換えない)
    { name: "今日の連絡先の更新", run: updateTodayList, master: "read" },
    // 2026-11-07 改善⑦: 世界の架け橋の週次KPI(前の週がまだなら集計)と法人番号の点検(Wld02Runner.gs)
    { name: "世界の架け橋の週次KPI", run: runWld02WeeklyIfDue_, master: "read" },
    { name: "掘り起こしアラートの送信", run: runDailyAlerts, master: "read" }
  ];

  var failures = [];
  var stop = null;  // 企業マスタの書き込みを止めたとき: { by: 手順名, dataChanged }
  // 「実行中」の印(下の markDailyMaintenanceRunning_)。上限(6分)で打ち切られると、この関数の最後の記録・通知は動かない。
  // 印を残しておけば、後の別の実行(毎分の処理)が checkDailyMaintenanceStale_ で見つけて知らせる
  var startedAtMs = Date.now();
  var startedAtText = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm");
  var doneCount = 0;
  checkDailyMaintenanceStale_();  // 前の回の印が残っていたら(打ち切られたまま誰も見つけていない)、先に知らせる
  markDailyMaintenanceRunning_(startedAtMs, startedAtText, "", "", 0);
  Logger.log("日次メンテナンスを開始しました。");
  steps.forEach(function (step) {
    // 時間の歯止め(executionBudget.js): 残り時間が少なければ、次の手順を始めない(最後の記録・通知の時間を残す)
    var elapsed = executionElapsedMs_();
    if (!GlowExecutionBudget.canStartStep(elapsed)) {
      Logger.log("日次メンテナンス: 「" + step.name + "」は、時間切れが近いため始めませんでした。");
      failures.push(step.name + ": この実行は始まってから " + GlowExecutionBudget.seconds(elapsed) +
        "秒たっており、上限(6分)が近いため、始めませんでした(次の日次メンテナンスで動きます)");
      return;
    }
    if (stop && stopsStep_(stop, step)) {
      failures.push(step.name + ": 「" + stop.by + "」で企業マスタの書き込みを止めたため、実行しませんでした" +
        (stop.dataChanged ? "(企業マスタが途中まで書き換わっている可能性があるため)" : "(企業マスタは変わっていないが、同じ理由で書き込みが止まるため)"));
      return;
    }
    markDailyMaintenanceRunning_(startedAtMs, startedAtText, step.name, step.master, doneCount);
    try {
      step.run();
      doneCount++;
      Logger.log("日次メンテナンス: 「" + step.name + "」が完了しました。");
    } catch (error) {
      Logger.log("日次メンテナンス: 「" + step.name + "」が失敗しました: " + error);
      failures.push(step.name + ": " + error);
      var companyWrite = companyWriteStopOf_(error);
      if (companyWrite && !stop) stop = { by: step.name, dataChanged: companyWrite.dataChanged };
    }
  });

  // ここから先は「最後の記録」。手順の名前を空にして、どこで打ち切られたかが分かるようにする
  markDailyMaintenanceRunning_(startedAtMs, startedAtText, "", "", doneCount);
  if (failures.length === 0) {
    Logger.log("日次メンテナンスがすべて完了しました。");
    recordOpsStatus_("日次メンテナンス", true, steps.length + "件すべて完了");
  } else {
    recordOpsStatus_("日次メンテナンス", false, failures.join(" / "));
    notifyMaintenanceFailures_(failures, steps.length);
  }
  // 最後まで来たら、印を消す(上限で打ち切られた・思わぬ例外で抜けたときは、印が残る)
  clearDailyMaintenanceRunning_();
  Logger.log("日次メンテナンスを終了しました。");
}

/** 「実行中」の印(スクリプトプロパティ)の名前 */
var DAILY_MAINTENANCE_RUNNING_PROPERTY = "DAILY_MAINTENANCE_RUNNING";

/** 「実行中」の印を付ける・書き換える。印を付けられなくても、日次メンテナンスは続ける */
function markDailyMaintenanceRunning_(startedAtMs, startedAtText, stepName, master, doneCount) {
  try {
    PropertiesService.getScriptProperties().setProperty(DAILY_MAINTENANCE_RUNNING_PROPERTY,
      GlowExecutionBudget.buildRunning(startedAtMs, startedAtText, stepName, master, doneCount));
  } catch (error) {
    Logger.log("日次メンテナンス: 実行中の印を付けられませんでした: " + error);
  }
}

function clearDailyMaintenanceRunning_() {
  try {
    PropertiesService.getScriptProperties().deleteProperty(DAILY_MAINTENANCE_RUNNING_PROPERTY);
  } catch (error) {
    Logger.log("日次メンテナンス: 実行中の印を消せませんでした: " + error);
  }
}

/**
 * 打ち切られた日次メンテナンスを見つけて知らせる(毎分の処理 processQueuedVoiceLogs と、次の日次メンテナンスの最初に呼ぶ)。
 * 「実行中」の印が8分より古ければ、上限(6分)や異常終了で打ち切られたとみなし、稼働状況タブに失敗として残して通知する。
 * 打ち切られた実行そのものは何も残せないので、別の実行が後から見つける。
 * @return {boolean} 打ち切りを見つけて知らせたら true
 */
function checkDailyMaintenanceStale_() {
  var props, running;
  try {
    props = PropertiesService.getScriptProperties();
    running = GlowExecutionBudget.parseRunning(props.getProperty(DAILY_MAINTENANCE_RUNNING_PROPERTY));
  } catch (error) {
    return false;
  }
  if (!GlowExecutionBudget.isStale(running, Date.now())) return false;
  // 先に印を消す(知らせる処理が遅くても、次の分にもう一度知らせないように)
  props.deleteProperty(DAILY_MAINTENANCE_RUNNING_PROPERTY);
  var message = GlowExecutionBudget.describeStale(running, 7);
  console.error(message);
  recordOpsStatus_("日次メンテナンス", false, message);
  notifyOpsFailure_("日次メンテナンス", message);
  return true;
}

/**
 * writeCompanyRecords_(ImportRunner.gs)が企業マスタの書き込みを止めたときの例外なら、その中身
 * ({ phase, dataChanged })を返す。エラーの文言ではなく、例外に付いた companyWrite で判断する。
 */
function companyWriteStopOf_(error) {
  var info = error && error.companyWrite;
  return info && typeof info === "object" ? info : null;
}

/**
 * 企業マスタの書き込みを止めたあと、この手順を止めるか。
 * - 書き込みが途中まで走った(dataChanged): 企業マスタを読む手順・書く手順をすべて止める(欠けた・混ざった企業マスタで
 *   スコア・今日の連絡先・アラートを作らない)。企業マスタを使わない手順だけ続ける
 * - 書く前の確認で止めた(企業マスタは変わっていない): 企業マスタを書き直す手順だけ止める(同じ理由でまた止まる)。
 *   読むだけの手順(ダッシュボード・今日の連絡先・アラートなど)は続ける
 */
function stopsStep_(stop, step) {
  if (step.master === "none") return false;
  if (stop.dataChanged) return true;
  return step.master === "write";
}

/**
 * 失敗をSlackへ通知する。通知自体が失敗しても日次メンテナンスは失敗扱いにしない
 * (実行ログとGASのエラー通知メールが最後の砦として残るため)。
 */
function notifyMaintenanceFailures_(failures, totalStepCount) {
  var message = "【GLOW台帳】日次メンテナンスで " + failures.length + "/" + totalStepCount +
    " 件が失敗しました。\n" + failures.join("\n");
  // Slack未設定でも黙らないよう、メールへ代替する共通の通知を使う(OpsStatus.gs)
  notifyOpsFailure_("日次メンテナンス", message);
}

/**
 * 日次メンテナンス用の時間主導トリガーを登録する。
 * 冪等: 同じハンドラの既存トリガーを消してから作り直すので、何度実行しても1本だけ残る。
 */
function installDailyMaintenanceTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (trigger) {
    if (trigger.getHandlerFunction() === "runDailyMaintenance") {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  ScriptApp.newTrigger("runDailyMaintenance")
    .timeBased()
    .atHour(DAILY_MAINTENANCE_HOUR)
    .everyDays(1)
    .create();
  Logger.log(
    "日次メンテナンス用のトリガーを登録しました(毎日 " + DAILY_MAINTENANCE_HOUR + "時台)。" +
    "「トリガー」画面でエラー通知設定を「毎回通知」にしてください。"
  );
}

/**
 * 現在登録されているトリガーの一覧を実行ログに出す点検用。
 * 「動いているはず」と「実際に登録されている」がズレていないかを、
 * エディタのトリガー画面を見に行かずに確認するために使う。
 */
function listInstalledTriggers() {
  var triggers = ScriptApp.getProjectTriggers();
  if (triggers.length === 0) {
    Logger.log("登録されているトリガーはありません。");
    return;
  }
  Logger.log("登録済みトリガー " + triggers.length + "件:");
  triggers.forEach(function (trigger) {
    Logger.log("  - " + trigger.getHandlerFunction() + " (" + trigger.getEventType() + ")");
  });
}
