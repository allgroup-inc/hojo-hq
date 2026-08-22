/**
 * GLOW企業リレーション台帳: BlueBean CTI通話履歴の取得・企業マスタ突合・対応履歴ログ自動記録
 *
 * BlueBean(ソフツー)の「顧客発着信履歴出力API」(pull型。webhookは存在しない)を時間主導
 * トリガーで定期ポーリングし、通話履歴を「CTI通話履歴」タブへ記録する。電話番号が企業マスタと
 * 一意にマッチし、かつ通話ステータスが「完了」の場合のみ、対応履歴ログへも自動記録する
 * (docs/議事_20260819_BlueBean CTI連携.md参照。未マッチ・複数企業ヒット・キャンセル等は
 * 「CTI通話履歴」タブに記録は残るが対応履歴ログへは書き込まず、人間のレビュー対象とする)。
 *
 * 事前準備:
 * 1. スクリプト プロパティに以下4つを設定する(すべて秘匿情報。コード上に直書きしないこと):
 *    - BLUEBEAN_DOMAIN: 例 "bbw2960-g-low2.softsu.com"(https://は含めない)
 *    - BLUEBEAN_USERNAME: BlueBean管理画面のユーザー名(現状は人間の管理者アカウントと共用。
 *      API連携専用アカウントの発行可否は小柳さんへ確認中。共用のままパスワードが変更されると
 *      連携が無言で止まるため、失敗時は「業務ID」欄のエラー(E002/E003)をまず確認すること)
 *    - BLUEBEAN_PASSWORD: 上記のパスワード
 *    - BLUEBEAN_CAMPAIGN_ID: 例 "8002"(BlueBeanの作業グループID。手紙の返信用封筒に記載した
 *      GLOW管理番号の架電キャンペーンを指す)
 * 2. ensureLedgerTabs を実行し、「CTI通話履歴」タブを作成する
 * 3. installCtiSyncTrigger を1度だけ実行し、1時間おきの同期トリガーを登録する
 *    (BlueBeanの架電はキャンペーン単位でまとまって行われるため、LINE音声ログ(1分間隔)ほど
 *    高頻度なポーリングは不要という判断。頻度を変えたい場合は everyHours(1) を調整する)
 * 4. (必須設定) Apps Scriptエディタの「トリガー」画面で、syncCtiCallHistoryトリガーの
 *    編集メニューから「失敗通知の設定」を「毎回通知を受け取る」に設定する(AlertRunner.gsと
 *    同じ理由。Slack自体の長時間ダウン等、コード内の通知だけでは検知できない単一障害点への対策)
 *
 * BlueBean APIの呼び出しが失敗した場合(認証情報の変更等)、AlertRunner.gsが既に使っている
 * SLACK_WEBHOOK_URL(スクリプト プロパティ)経由でSlackにも通知する。無言のまま同期が
 * 止まり続けることを防ぐための仕組みで、新しいプロパティの追加は不要(未設定の場合は
 * Slack通知だけスキップされ、実行ログへの記録は従来どおり行われる)。
 */
function syncCtiCallHistory() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var callLogSheet = ss.getSheetByName(GlowSchema.CTI_CALL_LOG_SHEET_NAME);
  if (!callLogSheet) {
    throw new Error("「" + GlowSchema.CTI_CALL_LOG_SHEET_NAME + "」タブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  if (!logSheet) {
    throw new Error("対応履歴ログタブが見つかりません。先に ensureLedgerTabs を実行してください。");
  }

  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(30000)) {
    throw new Error("他の処理がCTI通話履歴を操作中のため、同期を中断しました。しばらく待ってから再実行してください。");
  }
  try {
    var properties = PropertiesService.getScriptProperties();
    // 初回実行時はwatermark(前回同期完了時点)が無いため、直近24時間分から取得を開始する。
    var startDate = properties.getProperty("BLUEBEAN_LAST_SYNCED_AT") ||
      Utilities.formatDate(new Date(Date.now() - 24 * 60 * 60 * 1000), "Asia/Tokyo", "yyyy-MM-dd HH:mm:ss");
    var endDate = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm:ss");

    var apiResponse;
    try {
      apiResponse = callBlueBeanApi_(startDate, endDate);
      if (apiResponse.result !== "OK") {
        throw new Error("BlueBean APIがエラーを返しました: " + JSON.stringify(apiResponse));
      }
    } catch (error) {
      // BLUEBEAN_USERNAME/PASSWORDは人間の管理者アカウントと共用のため、パスワード変更等で
      // 無言のまま止まりうる(docs/議事_20260819_BlueBean CTI連携.md参照)。実行ログだけに
      // 頼らず、Slackにも通知して気づけるようにする(resilient-agent-design原則: 無言の失敗を作らない)。
      postToSlackWithRetry_(
        "⚠️ BlueBean CTI通話履歴の同期に失敗しました。認証情報(BLUEBEAN_USERNAME/PASSWORD)が" +
        "変更されていないか確認してください。エラー: " + error
      );
      throw error;
    }
    var calls = GlowCtiContent.flattenBlueBeanCalls(apiResponse);

    var existingCallIds = readExistingGroupCallIds_(callLogSheet);
    var newCalls = calls.filter(function (call) {
      return !existingCallIds[String(call.group_callid)];
    });

    var companies = readCompanyRecords_(companySheet);
    var recordedCount = 0;
    var skippedCount = 0;
    newCalls.forEach(function (call) {
      var matchedCompany = GlowCtiContent.matchCompanyByPhone(companies, call.phone);
      var callLogRow = GlowCtiContent.buildCallLogRow("CTI-" + call.group_callid, call, matchedCompany);
      callLogSheet.appendRow(callLogRow);

      if (GlowCtiContent.shouldRecordInteractionLog(call, matchedCompany)) {
        var logId = "H-" + Utilities.getUuid();
        var interactionRow = GlowCtiContent.buildInteractionLogRowForCall(logId, call, matchedCompany);
        logSheet.appendRow(interactionRow);
        recordedCount++;
      } else {
        skippedCount++;
      }
    });

    properties.setProperty("BLUEBEAN_LAST_SYNCED_AT", endDate);
    Logger.log(
      "CTI通話履歴の同期完了(" + startDate + " 〜 " + endDate + "): " +
      "新規取得 " + newCalls.length + "件(うち対応履歴ログへ自動記録 " + recordedCount +
      "件、未記録(未マッチ・複数企業ヒット・キャンセル等) " + skippedCount + "件)。" +
      "取得済みのためスキップ " + (calls.length - newCalls.length) + "件。"
    );
  } finally {
    lock.releaseLock();
  }
}

/**
 * 「CTI通話履歴」タブに既に記録済みのgroup_callidの集合を返す(重複取得防止用)。
 * ensureTab_が書式をシート全体に適用するためgetLastRow()が実データ行数より大きくなりうる
 * (readCompanyRecords_と同じ既知の挙動)が、group_callid列が空の行は無視するだけなので影響しない。
 */
function readExistingGroupCallIds_(sheet) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return {};
  var headers = GlowSchema.CTI_CALL_LOG_HEADERS;
  var idIndex = headers.indexOf("group_callid");
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var ids = {};
  values.forEach(function (row) {
    if (row[idIndex]) ids[String(row[idIndex])] = true;
  });
  return ids;
}

function callBlueBeanApi_(startDate, endDate) {
  return GlowResilience.withRetry(
    function () { return callBlueBeanApiOnce_(startDate, endDate); },
    {
      maxAttempts: 3,
      backoffMs: [2000, 10000],
      sleepFn: Utilities.sleep,
      isRetryable: function (error) {
        return !error.statusCode || GlowResilience.isRetryableHttpStatus(error.statusCode);
      },
      onRetry: function (error, attempt) {
        Logger.log("BlueBean API呼び出しを再試行します(" + attempt + "回目失敗): " + error);
      }
    }
  );
}

function callBlueBeanApiOnce_(startDate, endDate) {
  var properties = PropertiesService.getScriptProperties();
  var domain = properties.getProperty("BLUEBEAN_DOMAIN");
  var username = properties.getProperty("BLUEBEAN_USERNAME");
  var password = properties.getProperty("BLUEBEAN_PASSWORD");
  var campaignId = properties.getProperty("BLUEBEAN_CAMPAIGN_ID");
  if (!domain || !username || !password || !campaignId) {
    throw new Error(
      "BLUEBEAN_DOMAIN / BLUEBEAN_USERNAME / BLUEBEAN_PASSWORD / BLUEBEAN_CAMPAIGN_ID が" +
      "未設定です。スクリプト プロパティで設定してください。"
    );
  }
  var response = UrlFetchApp.fetch("https://" + domain + "/quick/api/export_customer_call_history.php", {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify({
      username: username,
      password: password,
      campaign_id: campaignId,
      start_date: startDate,
      end_date: endDate
    }),
    muteHttpExceptions: true
  });
  var responseCode = response.getResponseCode();
  if (responseCode < 200 || responseCode >= 300) {
    var error = new Error(
      "BlueBean APIの呼び出しに失敗しました(ステータスコード " + responseCode + "): " + response.getContentText()
    );
    error.statusCode = responseCode;
    throw error;
  }
  return JSON.parse(response.getContentText());
}

/**
 * syncCtiCallHistory をインストール型の時間主導トリガーとして1時間間隔で登録する。
 * 冪等: 実行時にまず同じハンドラ関数を指す既存トリガーをすべて削除してから
 * 新規登録するため、重複登録を心配せずに安全に再実行できる
 * (LineVoiceLogRunner.gsのinstallVoiceLogProcessingTriggerと同じパターン)。
 */
function installCtiSyncTrigger() {
  var existingTriggers = ScriptApp.getProjectTriggers();
  existingTriggers.forEach(function (trigger) {
    if (trigger.getHandlerFunction() === "syncCtiCallHistory") {
      ScriptApp.deleteTrigger(trigger);
    }
  });
  ScriptApp.newTrigger("syncCtiCallHistory")
    .timeBased()
    .everyHours(1)
    .create();
  Logger.log("CTI通話履歴同期用の1時間間隔トリガーを登録しました。");
}
