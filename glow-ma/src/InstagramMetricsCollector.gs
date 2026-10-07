/**
 * Instagram Graph API からメトリクスを取得してダッシュボードセクションを生成
 * 企業マスタの「Instagramアカウント」列に記載されたアカウントのフォロワー数・エンゲージメント等を取得
 */
function fetchInstagramMetrics() {
  var token = PropertiesService.getScriptProperties().getProperty("INSTAGRAM_ACCESS_TOKEN");
  if (!token) {
    Logger.log("INSTAGRAM_ACCESS_TOKEN が未設定のため、Instagramメトリクス取得をスキップします");
    return [];
  }

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    Logger.log("企業マスタが見つかりません。Instagramメトリクス取得をスキップします");
    return [];
  }

  var records = readCompanyRecords_(companySheet);
  var result = [];

  records.forEach(function(company) {
    var instaAccount = company["Instagramアカウント（@で始まる）"];
    if (!instaAccount) return;

    // Instagram Graph API の /me/insights?metric=impressions,reach,profile_visits エンドポイント
    // 注: これはBusiness Account が必須で、事前に Meta Developers で設定が必要
    try {
      var url = "https://graph.instagram.com/v18.0/me/insights?" +
        "metric=impressions,reach,follower_count&access_token=" + encodeURIComponent(token);
      var response = UrlFetchApp.fetch(url, {muteHttpExceptions: true});
      var data = JSON.parse(response.getContentText());

      if (data.error) {
        Logger.log("Instagramメトリクス取得失敗: " + instaAccount + " - " + data.error.message);
        return;
      }

      var metrics = {};
      (data.data || []).forEach(function(metric) {
        metrics[metric.name] = metric.values[0].value;
      });

      result.push({
        "企業ID": company["企業ID"],
        "Instagramアカウント": instaAccount,
        "フォロワー数": metrics.follower_count || 0,
        "リーチ数": metrics.reach || 0,
        "インプレッション": metrics.impressions || 0,
        "取得日時": Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd HH:mm")
      });
    } catch (error) {
      Logger.log("Instagramメトリクス取得エラー: " + instaAccount + " - " + error);
    }
  });

  return result;
}

function buildInstagramSummary() {
  var metrics = fetchInstagramMetrics();
  if (metrics.length === 0) {
    return [
      ["Instagramメトリクスサマリー"],
      ["指標", "数値"],
      ["合計フォロワー数", 0],
      ["30日リーチ合計", 0],
      ["取得企業数", 0]
    ];
  }

  var totalFollowers = 0;
  var totalReach = 0;

  metrics.forEach(function(m) {
    totalFollowers += m["フォロワー数"] || 0;
    totalReach += m["リーチ数"] || 0;
  });

  return [
    ["Instagramメトリクスサマリー"],
    ["指標", "数値"],
    ["合計フォロワー数", totalFollowers],
    ["30日リーチ合計", totalReach],
    ["取得企業数", metrics.length]
  ];
}
