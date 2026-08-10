/* GLOW企業リレーション台帳 管理画面Web Appの許可リスト照合・企業一覧の絞り込みロジック
 * ブラウザ相当のGAS(global.GlowAdminAccess)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_adminAccess.test.mjs で検証される。
 *
 * 個人Gmail運用(Workspaceドメインなし)のため、Web Appのアクセス設定だけでは
 * 利用者を限定できない。AdminRunner.gs が Session.getActiveUser().getEmail() で
 * 取得した実際のアクセス者のメールアドレスを、ここで「スタッフ」タブの登録
 * メールアドレスと照合する(三名体制レビュー2026-08-09裁定1・2)。
 */
(function (global) {
  "use strict";

  function normalizeEmail_(email) {
    return String(email || "").trim().toLowerCase();
  }

  function getGlowAlerting_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./alerting.js");
    }
    return global.GlowAlerting;
  }

  function formatDate_(date) {
    var year = date.getFullYear();
    var month = String(date.getMonth() + 1).padStart(2, "0");
    var day = String(date.getDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
  }

  /**
   * Sheetsの getValues() は日付セルを文字列ではなくJSの Date オブジェクトで返す。
   * これをそのまま String(...) すると "Thu Aug 20 2026 00:00:00 GMT+0900 ..." のような
   * 表示になり、曜日名基準でソートされてしまう(alerting.js の toDate と同じ問題への対処)。
   * Date/"yyyy-MM-dd"文字列のどちらが来ても "yyyy-MM-dd" 文字列に正規化する。
   */
  function normalizeDateForDisplay(value) {
    var date = getGlowAlerting_().toDate(value);
    return date ? formatDate_(date) : "";
  }

  function isAllowedEmail(email, staffRows) {
    var target = normalizeEmail_(email);
    if (!target) return false;
    return (staffRows || []).some(function (staff) {
      return normalizeEmail_(staff.email) === target;
    });
  }

  function buildAccessDeniedHtml() {
    return "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">" +
      "<style>body{font-family:-apple-system,BlinkMacSystemFont,\"Hiragino Sans\"," +
      "\"Noto Sans JP\",Meiryo,sans-serif;padding:3rem 2rem;text-align:center;color:#11202c}" +
      "h1{font-size:1.15rem;margin:0 0 0.75rem}p{color:#4a5a66;line-height:1.7}</style></head>" +
      "<body><h1>アクセス権がありません</h1>" +
      "<p>このページを利用できるのは許可されたスタッフのみです。<br>" +
      "心当たりがある場合は管理者に確認してください。</p></body></html>";
  }

  function resolveStaffName(email, staffRows) {
    var target = normalizeEmail_(email);
    var match = (staffRows || []).filter(function (staff) {
      return normalizeEmail_(staff.email) === target;
    })[0];
    return match && match.name ? match.name : "不明";
  }

  var COMPANY_LIST_FIELDS = ["企業ID", "会社名", "ランク", "現在ステージ", "次回アクション予定日", "担当者"];
  var DEFAULT_LIST_LIMIT = 100;

  function pickCompanyListFields_(company) {
    var picked = {};
    COMPANY_LIST_FIELDS.forEach(function (field) {
      picked[field] = company[field] !== undefined ? company[field] : "";
    });
    picked["次回アクション予定日"] = normalizeDateForDisplay(company["次回アクション予定日"]);
    return picked;
  }

  function hasAnyFilter(filters) {
    var f = filters || {};
    return !!(String(f.search || "").trim() || f.rank || f.stage || f.owner);
  }

  function applyCompanyFilters(companies, filters) {
    var f = filters || {};
    var searchTerm = String(f.search || "").trim().toLowerCase();
    return (companies || []).filter(function (company) {
      if (searchTerm) {
        var name = String(company["会社名"] || "").toLowerCase();
        var rep = String(company["代表者名"] || "").toLowerCase();
        if (name.indexOf(searchTerm) === -1 && rep.indexOf(searchTerm) === -1) return false;
      }
      if (f.rank && company["ランク"] !== f.rank) return false;
      if (f.stage && company["現在ステージ"] !== f.stage) return false;
      if (f.owner && company["担当者"] !== f.owner) return false;
      return true;
    });
  }

  function sortByNextActionDateDesc_(companies) {
    return companies.slice().sort(function (a, b) {
      var da = normalizeDateForDisplay(a["次回アクション予定日"]);
      var db = normalizeDateForDisplay(b["次回アクション予定日"]);
      if (da === db) return 0;
      return da < db ? 1 : -1;
    });
  }

  function buildCompanyListResult(companies, filters) {
    var filtered = applyCompanyFilters(companies, filters);
    var limited = hasAnyFilter(filters)
      ? filtered
      : sortByNextActionDateDesc_(filtered).slice(0, DEFAULT_LIST_LIMIT);
    return limited.map(pickCompanyListFields_);
  }

  function sortInteractionsByDateDesc(records) {
    return (records || [])
      .map(function (record) {
        var normalized = {};
        Object.keys(record).forEach(function (key) {
          normalized[key] = record[key];
        });
        normalized["日付"] = normalizeDateForDisplay(record["日付"]);
        return normalized;
      })
      .sort(function (a, b) {
        var da = a["日付"];
        var db = b["日付"];
        if (da === db) return 0;
        return da < db ? 1 : -1;
      });
  }

  /**
   * パートナー一覧(紹介パートナーマスタ全件+対応回数)の行を組み立てる。
   * AdminRunner.gs の getPartnerList がシート読み取り後にこれを呼ぶ。
   */
  function buildPartnerListRows(partners, interactionsByPartnerId) {
    var interactionsMap = interactionsByPartnerId || {};
    return (partners || []).map(function (partner) {
      var partnerId = partner["パートナーID"];
      return {
        "パートナーID": partnerId,
        "名称": partner["名称"],
        "種別": partner["種別"],
        "関係性ランク": partner["関係性ランク"],
        "対応回数": (interactionsMap[partnerId] || []).length
      };
    });
  }

  /**
   * 紹介実績ログの各レコードの「紹介日」を "yyyy-MM-dd" 文字列に正規化する。
   * 入力配列・要素は変更せず、新しい配列・オブジェクトを返す。
   */
  function normalizeReferralRecords(referrals) {
    return (referrals || []).map(function (record) {
      var normalized = {};
      Object.keys(record).forEach(function (key) {
        normalized[key] = record[key];
      });
      normalized["紹介日"] = normalizeDateForDisplay(record["紹介日"]);
      return normalized;
    });
  }

  var api = {
    isAllowedEmail: isAllowedEmail,
    buildAccessDeniedHtml: buildAccessDeniedHtml,
    resolveStaffName: resolveStaffName,
    COMPANY_LIST_FIELDS: COMPANY_LIST_FIELDS,
    DEFAULT_LIST_LIMIT: DEFAULT_LIST_LIMIT,
    hasAnyFilter: hasAnyFilter,
    applyCompanyFilters: applyCompanyFilters,
    buildCompanyListResult: buildCompanyListResult,
    sortInteractionsByDateDesc: sortInteractionsByDateDesc,
    normalizeDateForDisplay: normalizeDateForDisplay,
    buildPartnerListRows: buildPartnerListRows,
    normalizeReferralRecords: normalizeReferralRecords
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowAdminAccess = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
