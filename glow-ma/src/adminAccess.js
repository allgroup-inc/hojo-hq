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

  function computeUrgency(company, todayString) {
    if (company["連絡不要"] === true) return "none";
    var nextDate = company["次回アクション予定日"];
    if (!nextDate) return "untouched";
    var diffDays = getGlowAlerting_().daysBetween(todayString, nextDate);
    if (diffDays === null) return "untouched";
    if (diffDays <= 0) return "overdue";
    if (diffDays <= 3) return "soon";
    return "ok";
  }

  function buildKpiSummary(companies, todayString) {
    var list = companies || [];
    var byRank = { A: 0, B: 0, C: 0, D: 0 };
    var overdueOrUntouched = 0;
    var hot = 0;
    var deal = 0;
    var dealStages = ["提案中", "案件化"];
    list.forEach(function (company) {
      var rank = company["ランク"];
      if (byRank[rank] !== undefined) byRank[rank]++;
      var urgency = computeUrgency(company, todayString);
      if (urgency === "overdue" || urgency === "untouched") overdueOrUntouched++;
      if (company["本日反応あり"]) hot++;
      if (dealStages.indexOf(company["現在ステージ"]) !== -1) deal++;
    });
    var stale = getGlowAlerting_().buildStaleList(list, todayString).length;
    return {
      total: list.length,
      overdueOrUntouched: overdueOrUntouched,
      hot: hot,
      byRank: byRank,
      deal: deal,
      stale: stale
    };
  }

  function buildOwnerWorkload(companies, todayString) {
    var counts = {};
    var order = [];
    (companies || []).forEach(function (company) {
      var owner = company["担当者"];
      if (!owner) return;
      if (!counts[owner]) {
        counts[owner] = { owner: owner, total: 0, overdueOrUntouched: 0 };
        order.push(owner);
      }
      counts[owner].total++;
      var urgency = computeUrgency(company, todayString);
      if (urgency === "overdue" || urgency === "untouched") counts[owner].overdueOrUntouched++;
    });
    return order.map(function (owner) { return counts[owner]; })
      .sort(function (a, b) { return b.total - a.total; });
  }

  var URGENCY_ORDER_ = { untouched: 0, overdue: 1, soon: 2, ok: 3, none: 4 };

  function buildNextActionQueue(companies, todayString, limit) {
    var max = typeof limit === "number" ? limit : 8;
    var candidates = (companies || [])
      .map(function (company) {
        var urgency = computeUrgency(company, todayString);
        var withUrgency = {};
        Object.keys(company).forEach(function (key) { withUrgency[key] = company[key]; });
        withUrgency["次回アクション予定日"] = normalizeDateForDisplay(company["次回アクション予定日"]);
        withUrgency.urgency = urgency;
        return withUrgency;
      })
      .filter(function (company) {
        return company["本日反応あり"] || company.urgency === "overdue" ||
          company.urgency === "untouched" || company.urgency === "soon";
      });
    candidates.sort(function (a, b) {
      if (!!a["本日反応あり"] !== !!b["本日反応あり"]) return a["本日反応あり"] ? -1 : 1;
      return URGENCY_ORDER_[a.urgency] - URGENCY_ORDER_[b.urgency];
    });
    return candidates.slice(0, max);
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

  var COMPANY_LIST_FIELDS = [
    "企業ID", "会社名", "ランク", "現在ステージ", "次回アクション予定日", "担当者",
    "業種", "所在地", "流入ルート", "提案商品"
  ];
  var DEFAULT_LIST_LIMIT = 100;

  function pickCompanyListFields_(company, todayString) {
    var picked = {};
    COMPANY_LIST_FIELDS.forEach(function (field) {
      picked[field] = company[field] !== undefined ? company[field] : "";
    });
    picked["次回アクション予定日"] = normalizeDateForDisplay(company["次回アクション予定日"]);
    picked["流入ルート"] = company["流入ルート"] || [];
    picked["提案商品"] = company["提案商品"] || [];
    picked["urgency"] = computeUrgency(company, todayString);
    return picked;
  }

  function hasAnyFilter(filters) {
    var f = filters || {};
    return !!(String(f.search || "").trim() || f.rank || f.stage || f.owner || f.route || f.product);
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
      if (f.route && (company["流入ルート"] || []).indexOf(f.route) === -1) return false;
      if (f.product && (company["提案商品"] || []).indexOf(f.product) === -1) return false;
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

  function buildCompanyListResult(companies, filters, todayString) {
    var filtered = applyCompanyFilters(companies, filters);
    var limited = hasAnyFilter(filters)
      ? filtered
      : sortByNextActionDateDesc_(filtered).slice(0, DEFAULT_LIST_LIMIT);
    return limited.map(function (company) {
      return pickCompanyListFields_(company, todayString);
    });
  }

  /**
   * 一覧画面の「現在ステージ」「担当者」「流入ルート」「提案商品」フィルタの選択肢を、
   * 企業マスタに実在する値から重複なく作る(ランクはA/B/C/Dで固定のため画面側で
   * ハードコードする)。AdminRunner.gsのgetFilterOptions/getAdminBootstrapの両方から
   * 同じロジックを共有する。
   */
  function buildFilterOptions(companies) {
    var stageSet = {};
    var ownerSet = {};
    var routeSet = {};
    var productSet = {};
    (companies || []).forEach(function (company) {
      if (company["現在ステージ"]) stageSet[company["現在ステージ"]] = true;
      if (company["担当者"]) ownerSet[company["担当者"]] = true;
      (company["流入ルート"] || []).forEach(function (route) { routeSet[route] = true; });
      (company["提案商品"] || []).forEach(function (product) { productSet[product] = true; });
    });
    return {
      stages: Object.keys(stageSet).sort(),
      owners: Object.keys(ownerSet).sort(),
      routes: Object.keys(routeSet).sort(),
      products: Object.keys(productSet).sort()
    };
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

  // 企業詳細(getCompanyDetail)が返す企業オブジェクトの日付列。
  // SheetsのgetValues()はこれらをJSのDateオブジェクトのまま返すため、
  // google.script.runでブラウザへ渡す前に文字列へ正規化する必要がある
  // (Dateオブジェクトが混ざったオブジェクトを返すと、応答がブラウザ側でnull扱いに
  // なることがある。一覧側は既にpickCompanyListFields_で対応済みだったが、
  // 詳細側は未対応で「該当する企業が見つかりません」という誤表示を招いていた)。
  var COMPANY_DETAIL_DATE_FIELDS = ["最終接触日", "次回アクション予定日", "登録日"];

  function normalizeCompanyDetailDates(company) {
    if (!company) return company;
    var normalized = {};
    Object.keys(company).forEach(function (key) { normalized[key] = company[key]; });
    COMPANY_DETAIL_DATE_FIELDS.forEach(function (field) {
      if (normalized[field] !== undefined) {
        normalized[field] = normalizeDateForDisplay(normalized[field]);
      }
    });
    return normalized;
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
    buildFilterOptions: buildFilterOptions,
    sortInteractionsByDateDesc: sortInteractionsByDateDesc,
    normalizeDateForDisplay: normalizeDateForDisplay,
    normalizeCompanyDetailDates: normalizeCompanyDetailDates,
    buildPartnerListRows: buildPartnerListRows,
    normalizeReferralRecords: normalizeReferralRecords,
    computeUrgency: computeUrgency,
    buildKpiSummary: buildKpiSummary,
    buildOwnerWorkload: buildOwnerWorkload,
    buildNextActionQueue: buildNextActionQueue
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowAdminAccess = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
