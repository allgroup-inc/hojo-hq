/**
 * GLOW企業リレーション台帳: レターURLアクセスの反応計測(Web App)
 *
 * デプロイ手順(人間が一度だけ行う):
 * 1. Apps Scriptエディタの「デプロイ」→「新しいデプロイ」→種類「ウェブアプリ」を選ぶ
 * 2. 「実行ユーザー」は必ず「自分」を選ぶ(「アクセスしているユーザー」にすると、
 *    匿名の訪問者がスプレッドシートを操作する権限を持たずアクセスできない)
 * 3. 「アクセスできるユーザー」は「全員」を選ぶ(手紙を受け取った企業側の担当者が
 *    Googleアカウントなしでもアクセスできるようにするため)
 * 4. デプロイ後に発行されるURLを、スクリプト プロパティの TRACKING_BASE_URL に設定する
 * 5. スクリプト プロパティに TRACKING_REDIRECT_URL(アクセス後に案内する実際の
 *    遷移先ページ、例: 沖縄企業のミカタのトップページ)を設定する
 *
 * URL(例: <Web AppのURL>?id=C000001)へのアクセスがあると、対応履歴ログに
 * 「レターURLアクセス」として1行追記してから TRACKING_REDIRECT_URL へ案内する。
 * このWeb Appは「全員」に公開されるため、id パラメータは "C" + 数字6桁
 * (buildCompanyId, glow-ma/src/csvImport.js)の形式でない限りログに書き込まない
 * (形式検証しないと、悪意あるリクエストで対応履歴ログのセルに任意の値・数式を
 * 書き込まれるリスクがあるため)。存在しない企業IDでも形式さえ一致すれば記録は残るが
 * (対応履歴ログ側で企業マスタに一致しないIDとして後から検知できる)、エラーにはしない。
 *
 * リダイレクトは、GASのHtmlServiceがサンドボックス化されたiframe内で出力を
 * 描画する(meta refreshはこのiframeしか動かさず訪問者のブラウザは遷移しない)ため、
 * window.top.location.href によるトップレベル遷移を使う。
 *
 * また、対応履歴ログへの追記は setValues によるプログラム的な書き込みのため
 * onEditトリガー(AlertRunner.gsのhandleInteractionLogEdit)では検知できない。
 * そのためこのファイル自身がSpeed-to-Lead即時アラートとして直接Slackへ通知する
 * (AlertRunner.gsのpostToSlack_/lookupCompanyName_を再利用)。
 */
function doGet(e) {
  var companyId = e && e.parameter && e.parameter.id;
  if (companyId && /^C\d{6}$/.test(companyId)) {
    logTrackingAccess_(companyId);
  }
  var redirectUrl = PropertiesService.getScriptProperties().getProperty("TRACKING_REDIRECT_URL");
  if (!redirectUrl) {
    return HtmlService.createHtmlOutput("<p>ページが見つかりません。</p>");
  }
  var escapedForAttribute = redirectUrl.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
  var html = "<script>window.top.location.href = " + JSON.stringify(redirectUrl) + ";</script>" +
    "<p>移動しています... <a target=\"_top\" href=\"" + escapedForAttribute + "\">こちら</a></p>";
  return HtmlService.createHtmlOutput(html);
}

function logTrackingAccess_(companyId) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  var logWritten = false;
  if (logSheet) {
    var lock = LockService.getDocumentLock();
    if (lock.tryLock(10000)) {
      try {
        var nextRow = logSheet.getLastRow() + 1;
        var logId = "H-" + Utilities.getUuid();
        var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
        logSheet.getRange(nextRow, 1, 1, GlowSchema.INTERACTION_LOG_HEADERS.length).setValues([[
          logId, companyId, todayString, "システム(自動記録)", "レターURLアクセス", "未接触",
          "パーソナライズURL経由のアクセス", ""
        ]]);
        logWritten = true;
      } finally {
        lock.releaseLock();
      }
    } else {
      Logger.log(
        "対応履歴ログのロック取得に失敗したため、レターURLアクセスの記録をスキップしました: " + companyId
      );
    }
  }

  // Speed-to-Lead: このWeb AppへのアクセスはprogrammaticなsetValuesであり、
  // AlertRunner.gsのhandleInteractionLogEdit(onEditインストール型トリガー)は
  // 人間によるUI編集にしか反応しないため検知できない。ログ書き込みの成否に
  // かかわらず(ロック競合でログが遅延しても)、companyIdが検証済みならここで
  // 直接Slackへ即時通知する。
  var companyName = lookupCompanyName_(companyId);
  postToSlack_(
    "【即時アラート】" + companyName + "(" + companyId + ") がレターURLにアクセスしました。至急対応してください。"
  );
  return logWritten;
}
