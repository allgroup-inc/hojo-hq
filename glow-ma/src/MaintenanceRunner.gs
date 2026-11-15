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
  var skipped = [];  // 緊急停止スイッチで見送った手順
  var stop = null;  // 企業マスタの書き込みを止めたとき: { by: 手順名, dataChanged }
  // 緊急停止スイッチ(CompanyWritePauseRunner.gs): 停止中は、企業マスタを書き直す手順を試さずに見送る。
  // 失敗としては数えない(人が決めて止めている)。バックアップと読むだけの手順は続ける
  var pause = readCompanyWritePause_();
  steps.forEach(function (step) {
    if (pause.paused && step.master === "write") {
      skipped.push(step.name);
      Logger.log("日次メンテナンス: 「" + step.name + "」は、企業マスタの書き込みが停止中のため見送りました。");
      return;
    }
    if (stop && stopsStep_(stop, step)) {
      failures.push(step.name + ": 「" + stop.by + "」で企業マスタの書き込みを止めたため、実行しませんでした" +
        (stop.dataChanged ? "(企業マスタが途中まで書き換わっている可能性があるため)" : "(企業マスタは変わっていないが、同じ理由で書き込みが止まるため)"));
      return;
    }
    try {
      step.run();
      Logger.log("日次メンテナンス: 「" + step.name + "」が完了しました。");
    } catch (error) {
      Logger.log("日次メンテナンス: 「" + step.name + "」が失敗しました: " + error);
      failures.push(step.name + ": " + error);
      var companyWrite = companyWriteStopOf_(error);
      if (companyWrite && !stop) stop = { by: step.name, dataChanged: companyWrite.dataChanged };
    }
  });

  if (skipped.length > 0) remindCompanyWritePaused_(pause, skipped);
  if (failures.length === 0 && skipped.length === 0) {
    Logger.log("日次メンテナンスがすべて完了しました。");
    recordOpsStatus_("日次メンテナンス", true, steps.length + "件すべて完了");
    return;
  }
  var skippedNote = skipped.length === 0 ? "" :
    "見送り " + skipped.length + "件(" + skipped.join("・") + "): 企業マスタの書き込みが停止中";
  if (failures.length === 0) {
    Logger.log("日次メンテナンス: 企業マスタの書き込みが停止中のため、" + skipped.length + "件を見送りました。ほかは完了しました。");
    recordOpsStatus_("日次メンテナンス", "停止中",
      (steps.length - skipped.length) + "件完了 / " + skippedNote);
    return;
  }
  recordOpsStatus_("日次メンテナンス", false, failures.concat(skippedNote ? [skippedNote] : []).join(" / "));
  notifyMaintenanceFailures_(failures, steps.length);
}

/**
 * 停止中であることを、毎朝1回、稼働状況タブとお知らせで伝える(止めたまま忘れないように)。
 * 自動では再開しない。お断り(連絡不要)の反映も止まっているため、日数を添える。
 */
function remindCompanyWritePaused_(pause, skipped) {
  var days = GlowCompanyWritePause.pausedDays(pause, Date.now());
  var detail = GlowCompanyWritePause.describeState(pause) + (days >= 0 ? " / 停止から " + days + "日" : "");
  recordOpsStatus_(GlowCompanyWritePause.OPS_NAME, "停止中", detail);
  notifyOpsNotice_("【GLOW台帳】企業マスタの書き込みは停止中です",
    detail + "\n今朝の日次メンテナンスで見送った手順: " + skipped.join("・") +
    "\nお断り(連絡不要)の反映も止まっています。長く止めると、断った会社が連絡先の一覧に戻るおそれがあります。" +
    "\n再開は、代表者の承認の後、台帳のメニュー「GLOW台帳 → 企業マスタの書き込みを再開する」から。",
    "企業マスタの書き込み停止中");
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
