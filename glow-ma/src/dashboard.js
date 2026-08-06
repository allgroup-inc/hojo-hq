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

  // 担当者別ワークロード(Phase 12): 実働キャパシティの偏りを検知するための集計。
  // 成約/見送り(終了ステージ)と連絡不要(DNC)は「もう動かす必要がない」企業のため対象外にする。
  // 掘り起こし待ち件数が多い担当者ほど先頭に来るよう並び替える。
  function buildOwnerWorkloadSummary(records, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var alerting = getGlowAlerting_();
    var terminalStages = (alerting.DEFAULT_CONFIG && alerting.DEFAULT_CONFIG.terminalStages) || [];
    var counts = {};
    var order = [];
    (records || []).forEach(function (record) {
      if (terminalStages.indexOf(record["現在ステージ"]) !== -1) return;
      if (record["連絡不要"] === true) return;
      var owner = record["担当者"] || "未割当";
      if (!counts[owner]) {
        counts[owner] = { "保有企業数": 0, "Aランク保有数": 0, "掘り起こし待ち件数": 0 };
        order.push(owner);
      }
      counts[owner]["保有企業数"]++;
      if (alerting.resolveEffectiveRank(record) === "A") counts[owner]["Aランク保有数"]++;
      if (alerting.isOverdue(record, todayValue)) counts[owner]["掘り起こし待ち件数"]++;
    });
    return order
      .map(function (owner) {
        return {
          "担当者": owner,
          "保有企業数": counts[owner]["保有企業数"],
          "Aランク保有数": counts[owner]["Aランク保有数"],
          "掘り起こし待ち件数": counts[owner]["掘り起こし待ち件数"]
        };
      })
      .sort(function (a, b) { return b["掘り起こし待ち件数"] - a["掘り起こし待ち件数"]; });
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
    var staleCount = getGlowAlerting_().buildStaleList(list, todayValue).length;
    return {
      "対象企業数": list.length,
      "ランクA_滞留企業数": findRank_("A")["滞留企業数"],
      "ランクB_滞留企業数": findRank_("B")["滞留企業数"],
      "ランクC_滞留企業数": findRank_("C")["滞留企業数"],
      "ランクD_滞留企業数": findRank_("D")["滞留企業数"],
      "掘り起こし待ち件数合計": totalOverdue,
      "成約企業数": closedDealCount,
      "連絡不要企業数": doNotContactCount,
      "長期検討企業数": staleCount
    };
  }

  var DEAL_STAGE_TYPES = ["NDA締結", "意向表明受領", "DD開始"];

  function buildDealStageProgressSummary(interactionRecords, companyRecords, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var alerting = getGlowAlerting_();
    var terminalStages = (alerting.DEFAULT_CONFIG && alerting.DEFAULT_CONFIG.terminalStages) || [];
    var terminalCompanyIds = {};
    (companyRecords || []).forEach(function (record) {
      if (terminalStages.indexOf(record["現在ステージ"]) !== -1) {
        terminalCompanyIds[record["企業ID"]] = true;
      }
    });
    var latestByCompany = {};
    (interactionRecords || []).forEach(function (record) {
      if (DEAL_STAGE_TYPES.indexOf(record["種別"]) === -1) return;
      var companyId = record["企業ID"];
      if (!companyId || terminalCompanyIds[companyId]) return;
      var recordDate = alerting.toDate(record["日付"]);
      if (!recordDate) return;
      var current = latestByCompany[companyId];
      if (!current || recordDate.getTime() > current["日付"].getTime()) {
        latestByCompany[companyId] = { "種別": record["種別"], "日付": recordDate };
      }
    });
    var daysListByStage = {};
    DEAL_STAGE_TYPES.forEach(function (type) { daysListByStage[type] = []; });
    Object.keys(latestByCompany).forEach(function (companyId) {
      var entry = latestByCompany[companyId];
      var days = alerting.daysBetween(entry["日付"], todayValue);
      if (days === null) return;
      daysListByStage[entry["種別"]].push(days);
    });
    return DEAL_STAGE_TYPES.map(function (type) {
      var daysList = daysListByStage[type];
      var count = daysList.length;
      var avgDays = count > 0 ? Math.round(daysList.reduce(function (a, b) { return a + b; }, 0) / count) : 0;
      return { "工程": type, "滞留企業数": count, "平均滞留日数": avgDays };
    });
  }

  var PARTNER_SUMMARY_FIELDS = ["名称", "累計紹介数", "成約数", "関係性ランク", "提供済み情報ログ", "逆紹介履歴"];

  var MIN_REFERRALS_FOR_CONVERSION_RATE = 3;

  function calculateConversionRate_(referralCountValue, dealCountValue) {
    var referrals = Number(referralCountValue);
    var deals = Number(dealCountValue);
    if (!referrals || isNaN(referrals) || referrals < MIN_REFERRALS_FOR_CONVERSION_RATE || isNaN(deals)) return "";
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
    buildOwnerWorkloadSummary: buildOwnerWorkloadSummary,
    buildHistorySnapshot: buildHistorySnapshot,
    buildDealStageProgressSummary: buildDealStageProgressSummary,
    DEAL_STAGE_TYPES: DEAL_STAGE_TYPES,
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
