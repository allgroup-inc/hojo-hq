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
 *    - BLUEBEAN_DOMAIN: BlueBean管理画面のドメイン部分(https://は含めない)。実際の値は
 *      公開リポジトリに書かない(ログイン画面のURLを公開しないため。2026-09-07 守り観点で一般化)
 *    - BLUEBEAN_USERNAME: BlueBean管理画面のユーザー名(2026-09-07 決定: 人間の管理者アカウントと
 *      共用で開始。共用のままパスワードが変更されると連携が無言で止まるため、失敗時は
 *      「業務ID」欄のエラー(E002/E003)をまず確認すること。Slack通知でも検知できる)
 *    - BLUEBEAN_PASSWORD: 上記のパスワード(受け渡しはメール・チャット禁止。口頭かLINEで)
 *    - BLUEBEAN_CAMPAIGN_ID: BlueBeanの作業グループID。**カンマ区切りで複数指定できる**
 *      (2026-10-16: 接続時に設定した作業グループと、福田さんが実際に架電している作業グループが
 *      別だったため、取得が0件のまま誰も気づかなかった。現場が使う作業グループをすべて並べる。
 *      実際の番号は公開リポジトリには書かない)
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
/**
 * トリガーから呼ばれる入口。結果を「稼働状況」タブへ記録し、失敗は通知する(OpsStatus.gs)。
 * 0件でも「成功・0件」と残るので、「動いているのに取れていない」も台帳から見える。
 */
/** 同期を試みた時刻(成否を問わない)。毎分の処理から1時間おきに呼ぶ判定に使う */
var CTI_SYNC_LAST_ATTEMPT_PROP = "CTI_SYNC_LAST_ATTEMPT_MS";
var CTI_SYNC_INTERVAL_MS = 60 * 60 * 1000;

/**
 * 毎分の音声ログ処理(processQueuedVoiceLogs)に相乗りして、前回の試行から1時間たっていれば同期する。
 * 2026-10-24 9時以降、1時間おきのトリガーが毎回「承認が必要です」で止まり、同期が1件も走っていなかった
 * (毎分のトリガーは正常に動いている)。トリガーの状態に左右されないよう、こちらでも同期する。
 */
function runCtiSyncIfDue_() {
  var props = PropertiesService.getScriptProperties();
  if (!props.getProperty("BLUEBEAN_DOMAIN")) return;
  var last = Number(props.getProperty(CTI_SYNC_LAST_ATTEMPT_PROP) || 0);
  if (Date.now() - last < CTI_SYNC_INTERVAL_MS) return;
  syncCtiCallHistory();
}

function syncCtiCallHistory() {
  PropertiesService.getScriptProperties().setProperty(CTI_SYNC_LAST_ATTEMPT_PROP, String(Date.now()));
  try {
    var summary = syncCtiCallHistoryCore_();
    recordOpsStatus_("BlueBean架電履歴の同期", true, summary);
  } catch (error) {
    recordOpsStatus_("BlueBean架電履歴の同期", false, String(error));
    notifyOpsFailure_("BlueBean架電履歴の同期",
      "認証情報(BLUEBEAN_USERNAME/PASSWORD)の変更や、作業グループID(BLUEBEAN_CAMPAIGN_ID)の誤りがないか確認してください。\n" +
      "エラー: " + error);
    throw error;
  }
}

function syncCtiCallHistoryCore_() {
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

    // BLUEBEAN_USERNAME/PASSWORDは人間の管理者アカウントと共用のため、パスワード変更等で
    // 無言のまま止まりうる(docs/議事_20260819_BlueBean CTI連携.md参照)。失敗は呼び出し元の
    // syncCtiCallHistory が稼働状況タブへの記録と通知(Slack未設定ならメール)を行う。
    var campaignIds = readCampaignIds_();
    var calls = [];
    var perCampaign = [];
    campaignIds.forEach(function (campaignId, index) {
      var apiResponse = callBlueBeanApi_(startDate, endDate, campaignId);
      if (apiResponse.result !== "OK") {
        throw new Error("BlueBean APIがエラーを返しました(作業グループ" + (index + 1) + "件目): " +
          JSON.stringify(apiResponse));
      }
      var got = GlowCtiContent.flattenBlueBeanCalls(apiResponse);
      perCampaign.push("グループ" + (index + 1) + "(ID " + campaignId + "): " + got.length + "件");
      calls = calls.concat(got);
    });

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
    return startDate + "〜" + endDate + " / 作業グループ" + campaignIds.length + "件(" + perCampaign.join("、") +
      ") / 新規 " + newCalls.length + "件(対応履歴へ記録 " + recordedCount + "件)";
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

/** BLUEBEAN_CAMPAIGN_ID をカンマ区切りで読み、空要素・重複を除いた配列を返す。 */
function readCampaignIds_() {
  var raw = PropertiesService.getScriptProperties().getProperty("BLUEBEAN_CAMPAIGN_ID") || "";
  var seen = {};
  var ids = raw.split(/[,，、\s]+/).filter(function (id) {
    if (!id || seen[id]) return false;
    seen[id] = true;
    return true;
  });
  if (ids.length === 0) {
    throw new Error("BLUEBEAN_CAMPAIGN_ID が未設定です。スクリプト プロパティで設定してください。");
  }
  return ids;
}

function callBlueBeanApi_(startDate, endDate, campaignId) {
  return GlowResilience.withRetry(
    function () { return callBlueBeanApiOnce_(startDate, endDate, campaignId); },
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

function callBlueBeanApiOnce_(startDate, endDate, campaignId) {
  var properties = PropertiesService.getScriptProperties();
  var domain = properties.getProperty("BLUEBEAN_DOMAIN");
  var username = properties.getProperty("BLUEBEAN_USERNAME");
  var password = properties.getProperty("BLUEBEAN_PASSWORD");
  if (!domain || !username || !password || !campaignId) {
    throw new Error(
      "BLUEBEAN_DOMAIN / BLUEBEAN_USERNAME / BLUEBEAN_PASSWORD / BLUEBEAN_CAMPAIGN_ID が" +
      "未設定です。スクリプト プロパティで設定してください。"
    );
  }
  // 2026-10 から BlueBean のサーバー入口に「1回目のログイン」(ベーシック認証)が追加された
  // (福田さん 2026-10-26: 毎日の初回ログインで2重ログインを求められる)。これが無いと、
  // APIの手前で 401「Authentication required!」が返る。入口のID/パスワードはスクリプトプロパティ
  // BLUEBEAN_BASIC_USER / BLUEBEAN_BASIC_PASSWORD に置く(未設定なら従来どおり送らない)
  var headers = {};
  var basicUser = properties.getProperty("BLUEBEAN_BASIC_USER");
  var basicPassword = properties.getProperty("BLUEBEAN_BASIC_PASSWORD");
  if (basicUser && basicPassword) {
    headers.Authorization = "Basic " + Utilities.base64Encode(basicUser + ":" + basicPassword, Utilities.Charset.UTF_8);
  }
  var response = UrlFetchApp.fetch("https://" + domain + "/quick/api/export_customer_call_history.php", {
    method: "post",
    contentType: "application/json",
    headers: headers,
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
    var body = response.getContentText();
    var hint = "";
    if (responseCode === 401 && /Authentication required/i.test(body)) {
      hint = basicUser
        ? "BlueBeanの入口のログイン(1回目)が通りません。BLUEBEAN_BASIC_USER / BLUEBEAN_BASIC_PASSWORD が最新か確認してください"
        : "BlueBeanの入口のログイン(1回目)が必要です。スクリプトプロパティ BLUEBEAN_BASIC_USER / BLUEBEAN_BASIC_PASSWORD を設定してください";
    }
    var error = new Error(
      "BlueBean APIの呼び出しに失敗しました(ステータスコード " + responseCode + ")" +
      (hint ? ": " + hint : ": " + body.slice(0, 300))
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
