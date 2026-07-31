/* GLOW企業リレーション台帳 ダッシュボード集計ロジック
 * ブラウザ相当のGAS(global.GlowDashboard)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_dashboard.test.mjs で検証される。
 *
 * ランク別サマリーは glow-ma/src/alerting.js の GlowAlerting をそのまま利用し、
 * 実効ランク・掘り起こし判定ロジックを重複定義しない。GASのファイル読み込み順序に
 * 依存しないよう、モジュール読み込み時ではなく関数呼び出し時に遅延解決する
 * (Phase 4最終レビューで見つかった同種の不具合の再発防止)。
 */
(function (global) {
  "use strict";

  function getGlowAlerting_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./alerting.js");
    }
    return global.GlowAlerting;
  }

  var DEFAULT_CONFIG = {
    routes: ["①紹介", "②手紙DM", "③ミカタ経由"],
    stages: ["未接触", "アプローチ実施", "電話済み", "相談実施", "関係構築中", "提案中", "案件化", "成約", "見送り"],
    products: ["M&A", "不動産", "法人保険"],
    ranks: ["A", "B", "C", "D"]
  };

  function buildRouteStageFunnel(records, config) {
    config = config || DEFAULT_CONFIG;
    var counts = {};
    config.routes.forEach(function (route) {
      counts[route] = {};
      config.stages.forEach(function (stage) {
        counts[route][stage] = 0;
      });
    });
    (records || []).forEach(function (record) {
      var routes = record["流入ルート"] || [];
      var stage = record["現在ステージ"];
      routes.forEach(function (route) {
        if (counts[route] && Object.prototype.hasOwnProperty.call(counts[route], stage)) {
          counts[route][stage]++;
        }
      });
    });
    var result = [];
    config.routes.forEach(function (route) {
      config.stages.forEach(function (stage) {
        result.push({ "流入ルート": route, "現在ステージ": stage, "件数": counts[route][stage] });
      });
    });
    return result;
  }

  function buildProductFunnel(records, config) {
    config = config || DEFAULT_CONFIG;
    var reachedDealStageValues = ["案件化", "成約"];
    var counts = {};
    config.products.forEach(function (product) {
      counts[product] = { "提案数": 0, "案件化数": 0, "成約数": 0 };
    });
    (records || []).forEach(function (record) {
      var products = record["提案商品"] || [];
      var stage = record["現在ステージ"];
      products.forEach(function (product) {
        if (!counts[product]) return;
        counts[product]["提案数"]++;
        if (reachedDealStageValues.indexOf(stage) !== -1) counts[product]["案件化数"]++;
        if (stage === "成約") counts[product]["成約数"]++;
      });
    });
    return config.products.map(function (product) {
      return {
        "商品": product,
        "提案数": counts[product]["提案数"],
        "案件化数": counts[product]["案件化数"],
        "成約数": counts[product]["成約数"]
      };
    });
  }

  function buildRankSummary(records, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var alerting = getGlowAlerting_();
    var terminalStages = (alerting.DEFAULT_CONFIG && alerting.DEFAULT_CONFIG.terminalStages) || [];
    var counts = {};
    config.ranks.forEach(function (rank) {
      counts[rank] = { "滞留企業数": 0, "掘り起こし待ち件数": 0 };
    });
    (records || []).forEach(function (record) {
      if (terminalStages.indexOf(record["現在ステージ"]) !== -1) return;
      var effectiveRank = alerting.resolveEffectiveRank(record);
      if (!counts[effectiveRank]) return;
      counts[effectiveRank]["滞留企業数"]++;
      if (alerting.isOverdue(record, todayValue)) {
        counts[effectiveRank]["掘り起こし待ち件数"]++;
      }
    });
    return config.ranks.map(function (rank) {
      return {
        "ランク": rank,
        "滞留企業数": counts[rank]["滞留企業数"],
        "掘り起こし待ち件数": counts[rank]["掘り起こし待ち件数"]
      };
    });
  }

  function countUnclassifiedCompanies(records, config) {
    config = config || DEFAULT_CONFIG;
    var alerting = getGlowAlerting_();
    var list = records || [];
    var unknownStageCount = 0;
    var unknownRouteCount = 0;
    var unknownProductCount = 0;
    list.forEach(function (record) {
      var stage = record["現在ステージ"];
      if (config.stages.indexOf(stage) === -1) unknownStageCount++;
      var routes = record["流入ルート"] || [];
      var hasKnownRoute = routes.some(function (route) { return config.routes.indexOf(route) !== -1; });
      if (routes.length === 0 || !hasKnownRoute) unknownRouteCount++;
      var products = record["提案商品"] || [];
      var hasKnownProduct = products.some(function (product) { return config.products.indexOf(product) !== -1; });
      if (products.length === 0 || !hasKnownProduct) unknownProductCount++;
    });
    return {
      "対象企業数": list.length,
      "未スコア企業数": alerting.countUnscoredCompanies(list),
      "現在ステージ未分類企業数": unknownStageCount,
      "流入ルート未分類企業数": unknownRouteCount,
      "提案商品未設定企業数": unknownProductCount
    };
  }

  function buildHistorySnapshot(records, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var list = records || [];
    var rankSummary = buildRankSummary(list, todayValue, config);
    var findRank_ = function (rank) {
      var found = rankSummary.filter(function (r) { return r["ランク"] === rank; })[0];
      return found || { "滞留企業数": 0, "掘り起こし待ち件数": 0 };
    };
    var totalOverdue = rankSummary.reduce(function (sum, r) {
      return sum + r["掘り起こし待ち件数"];
    }, 0);
    var closedDealCount = list.filter(function (record) {
      return record["現在ステージ"] === "成約";
    }).length;
    var doNotContactCount = list.filter(function (record) {
      return record["連絡不要"] === true;
    }).length;
    return {
      "対象企業数": list.length,
      "ランクA_滞留企業数": findRank_("A")["滞留企業数"],
      "ランクB_滞留企業数": findRank_("B")["滞留企業数"],
      "ランクC_滞留企業数": findRank_("C")["滞留企業数"],
      "ランクD_滞留企業数": findRank_("D")["滞留企業数"],
      "掘り起こし待ち件数合計": totalOverdue,
      "成約企業数": closedDealCount,
      "連絡不要企業数": doNotContactCount
    };
  }

  var PARTNER_SUMMARY_FIELDS = ["名称", "累計紹介数", "成約数", "関係性ランク", "提供済み情報ログ", "逆紹介履歴"];

  function calculateConversionRate_(referralCountValue, dealCountValue) {
    var referrals = Number(referralCountValue);
    var deals = Number(dealCountValue);
    if (!referrals || isNaN(referrals) || referrals <= 0 || isNaN(deals)) return "";
    return (deals / referrals * 100).toFixed(1) + "%";
  }

  function formatPartnerSummary(partnerRecords) {
    return (partnerRecords || []).map(function (partner) {
      var summary = {};
      PARTNER_SUMMARY_FIELDS.forEach(function (field) {
        var value = partner[field];
        summary[field] = value === undefined || value === null ? "" : value;
      });
      summary["成約率"] = calculateConversionRate_(partner["累計紹介数"], partner["成約数"]);
      return summary;
    });
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    buildRouteStageFunnel: buildRouteStageFunnel,
    buildProductFunnel: buildProductFunnel,
    buildRankSummary: buildRankSummary,
    buildHistorySnapshot: buildHistorySnapshot,
    countUnclassifiedCompanies: countUnclassifiedCompanies,
    formatPartnerSummary: formatPartnerSummary,
    PARTNER_SUMMARY_FIELDS: PARTNER_SUMMARY_FIELDS
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowDashboard = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
