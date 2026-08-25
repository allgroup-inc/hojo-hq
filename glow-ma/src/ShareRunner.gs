/**
 * GLOW企業リレーション台帳: 対面連携(Slack DM即時共有)
 *
 * 対面商談中に、その場で別の担当者へ企業の基本情報(住所→地図・電話番号・
 * 窓口担当者名・関係メモ)を即座に共有するための機能。「企業マスタ」タブで
 * 企業の行を選択してメニューから実行すると、連携先スタッフを選ぶダイアログが開き、
 * 選んだスタッフへSlack DMで送信する。
 *
 * セットアップ(人間が一度だけ行う):
 * 1. https://api.slack.com/apps で新しいSlack Appを作成する
 * 2. 「OAuth & Permissions」→「Bot Token Scopes」に chat:write を追加する
 *    (それ以外のスコープは付与しない。原則⑥「権限は最小限から」)
 * 3. ワークスペースにインストールし、発行された Bot User OAuth Token
 *    (xoxb-で始まる文字列)を、Apps Scriptエディタの「プロジェクトの設定」→
 *    「スクリプト プロパティ」で SLACK_BOT_TOKEN として設定する
 *    (コードに書かない。このトークンは絶対に外部へ持ち出さないこと)
 * 4. 「スタッフ」タブ(ensureLedgerTabsで作成済み)に、連携対象にしたい社員の
 *    「氏名」「Slack User ID」を入力し、「有効」列にチェックを入れる。
 *    Slack User IDの調べ方: Slackで対象社員のプロフィールを開き
 *    「その他」→「メンバーIDをコピー」(Uから始まる文字列。メールアドレスではない)
 *    なお、管理画面Web Appの🤝連携ボタンから本機能を使うには requireAdminAccess_
 *    による管理者確認を通過する必要があるため、「メールアドレス」欄も入力し
 *    「有効」列にチェックを入れておくこと(AdminRunner.gsのスタッフ許可リストと共通)
 * 5. `clasp push` で最新コードを反映する。スプレッドシートを開き直すと
 *    メニューバーに「GLOW台帳」が追加される
 *
 * 使い方:
 * 1. 「企業マスタ」タブで、連携したい企業の行(どのセルでもよい)を選択する
 * 2. メニュー「GLOW台帳」→「選択中の企業を連携する」を実行する
 * 3. 開いたダイアログで連携先スタッフにチェックを入れ、必要なら
 *    「今の状況」を一言入力して「連携する」を押す
 *
 * 耐障害性(2026-08-07 resilient-agent-design + glow-ma-triangle-review確定):
 * - Slack DM送信は一時的な失敗(429/5xx/ネットワーク例外)のみ最大3回、
 *   2秒→10秒のバックオフで再試行する(glow-ma/src/resilience.js)
 * - 複数人へ同時送信する際、1人への送信が失敗しても他の宛先への送信は続ける
 *   (1人の失敗で全員への連携が止まらないようにする障害隔離)
 * - 連絡不要(DNC)企業・機微な関係メモの扱いはglow-ma/src/shareContent.jsを参照
 */
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("GLOW台帳")
    .addItem("選択中の企業を連携する", "showShareDialog")
    .addItem("発送日でCSV出力", "exportShippingCsvForDate")
    .addSeparator()
    .addItem("G1フェーズA試験を実行", "showPhaseATestDialog")
    .addToUi();
}

function showShareDialog() {
  var ui = SpreadsheetApp.getUi();
  var sheet = SpreadsheetApp.getActiveSheet();
  if (sheet.getName() !== GlowSchema.COMPANY_MASTER_SHEET_NAME) {
    ui.alert("「" + GlowSchema.COMPANY_MASTER_SHEET_NAME + "」タブで、連携したい企業の行を選択してから実行してください。");
    return;
  }
  var row = sheet.getActiveCell().getRow();
  if (row < 2) {
    ui.alert("見出し行ではなく、連携したい企業の行を選択してから実行してください。");
    return;
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companyIdColumnIndex = GlowSchema.COMPANY_MASTER_HEADERS.indexOf("企業ID") + 1;
  var companyId = sheet.getRange(row, companyIdColumnIndex).getValue();

  var records = readCompanyRecords_(companySheet);
  var record = records.filter(function (r) { return r["企業ID"] === companyId; })[0];
  if (!record) {
    ui.alert("企業ID " + companyId + " が企業マスタに見つかりません。");
    return;
  }

  var staffList = readActiveStaff_(ss);
  var html = GlowShareDialog.buildStaffSelectionHtml(record["会社名"], companyId, staffList);
  var output = HtmlService.createHtmlOutput(html).setWidth(420).setHeight(480);
  ui.showModalDialog(output, "企業情報を連携");
}

function readActiveStaff_(ss) {
  var sheet = ss.getSheetByName(GlowSchema.STAFF_SHEET_NAME);
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.STAFF_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var nameIndex = headers.indexOf("氏名");
  var slackIdIndex = headers.indexOf("Slack User ID");
  var activeIndex = headers.indexOf("有効");
  return values
    .filter(function (row) { return row[activeIndex] === true && row[nameIndex] && row[slackIdIndex]; })
    .map(function (row) { return { name: row[nameIndex], slackUserId: row[slackIdIndex] }; });
}

/**
 * shareDialog.js の画面(google.script.run)から呼ばれる。
 * 選択されたスタッフ(Slack User IDの配列)へ、companyIdの企業情報をDM送信する。
 * 1人への送信失敗が他の宛先への送信を止めないよう、宛先ごとに障害を隔離する。
 */
function shareCompanyWithStaff(companyId, staffIds, note) {
  requireAdminAccess_();
  if (!staffIds || staffIds.length === 0) {
    throw new Error("連携先が選択されていません。");
  }
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var records = readCompanyRecords_(companySheet);
  var record = records.filter(function (r) { return r["企業ID"] === companyId; })[0];
  if (!record) {
    throw new Error("企業ID " + companyId + " が企業マスタに見つかりません。");
  }

  var senderEmail = Session.getActiveUser().getEmail();
  var message = GlowShareContent.buildShareMessage(record, { note: note, senderEmail: senderEmail });

  var succeededCount = 0;
  var failedCount = 0;
  staffIds.forEach(function (slackUserId) {
    try {
      postSlackDmWithRetry_(slackUserId, message);
      succeededCount++;
    } catch (error) {
      Logger.log("Slack DM送信に失敗しました(宛先 " + slackUserId + "): " + error);
      failedCount++;
    }
  });

  if (failedCount === 0) {
    return succeededCount + "名に連携しました。";
  }
  return succeededCount + "名に連携しました(" + failedCount +
    "名は送信失敗。Slack User IDの誤り、またはBot Tokenの権限を確認してください)。";
}

function postSlackDmWithRetry_(slackUserId, message) {
  return GlowResilience.withRetry(
    function () { return postSlackDmOnce_(slackUserId, message); },
    {
      maxAttempts: 3,
      backoffMs: [2000, 10000],
      sleepFn: Utilities.sleep,
      isRetryable: function (error) {
        return (!!error.statusCode && GlowResilience.isRetryableHttpStatus(error.statusCode)) ||
          error.slackError === "ratelimited";
      },
      onRetry: function (error, attempt) {
        Logger.log("Slack DM送信を再試行します(" + attempt + "回目失敗、宛先 " + slackUserId + "): " + error);
      }
    }
  );
}

function postSlackDmOnce_(slackUserId, message) {
  var token = PropertiesService.getScriptProperties().getProperty("SLACK_BOT_TOKEN");
  if (!token) {
    throw new Error("SLACK_BOT_TOKEN が未設定です。スクリプト プロパティで設定してください。");
  }
  var channelId = openSlackDmChannel_(token, slackUserId);
  postSlackMessageToChannel_(token, channelId, message);
}

function openSlackDmChannel_(token, slackUserId) {
  var response = UrlFetchApp.fetch("https://slack.com/api/conversations.open", {
    method: "post",
    contentType: "application/json; charset=utf-8",
    headers: { Authorization: "Bearer " + token },
    payload: JSON.stringify({ users: slackUserId }),
    muteHttpExceptions: true
  });
  var body = parseSlackResponse_(response);
  return body.channel.id;
}

function postSlackMessageToChannel_(token, channelId, message) {
  var response = UrlFetchApp.fetch("https://slack.com/api/chat.postMessage", {
    method: "post",
    contentType: "application/json; charset=utf-8",
    headers: { Authorization: "Bearer " + token },
    payload: JSON.stringify({ channel: channelId, text: message }),
    muteHttpExceptions: true
  });
  parseSlackResponse_(response);
}

/**
 * SlackのAPIはHTTP自体は200を返しつつ、本文のokがfalseで論理エラーを表すことが多い。
 * HTTPレベルの一時エラー(429/5xx)と、Slackの"ratelimited"エラーのみリトライ対象にする
 * (postSlackDmWithRetry_のisRetryableで判定するため、statusCode/slackErrorをErrorに残す)。
 */
function parseSlackResponse_(response) {
  var responseCode = response.getResponseCode();
  var body = JSON.parse(response.getContentText());
  if (responseCode < 200 || responseCode >= 300) {
    var httpError = new Error("Slack APIの呼び出しに失敗しました(HTTP " + responseCode + "): " + response.getContentText());
    httpError.statusCode = responseCode;
    throw httpError;
  }
  if (!body.ok) {
    var slackError = new Error("Slack APIがエラーを返しました: " + body.error);
    slackError.slackError = body.error;
    throw slackError;
  }
  return body;
}
