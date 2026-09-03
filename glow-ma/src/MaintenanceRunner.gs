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
    { name: "台帳のバックアップ", run: backupLedger },
    { name: "お断り(連絡不要)の反映", run: syncDoNotContactFlags },
    { name: "スコア・ランクの再計算", run: recalculateAllScores },
    { name: "ダッシュボードの更新", run: updateDashboard },
    { name: "掘り起こしアラートの送信", run: runDailyAlerts }
  ];

  var failures = [];
  steps.forEach(function (step) {
    try {
      step.run();
      Logger.log("日次メンテナンス: 「" + step.name + "」が完了しました。");
    } catch (error) {
      Logger.log("日次メンテナンス: 「" + step.name + "」が失敗しました: " + error);
      failures.push(step.name + ": " + error);
    }
  });

  if (failures.length === 0) {
    Logger.log("日次メンテナンスがすべて完了しました。");
    return;
  }
  notifyMaintenanceFailures_(failures, steps.length);
}

/**
 * 失敗をSlackへ通知する。通知自体が失敗しても日次メンテナンスは失敗扱いにしない
 * (実行ログとGASのエラー通知メールが最後の砦として残るため)。
 */
function notifyMaintenanceFailures_(failures, totalStepCount) {
  var message = "【GLOW台帳】日次メンテナンスで " + failures.length + "/" + totalStepCount +
    " 件が失敗しました。\n" + failures.join("\n");
  try {
    postToSlack_(message);
  } catch (error) {
    Logger.log("日次メンテナンスの失敗通知をSlackへ送れませんでした: " + error);
  }
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
