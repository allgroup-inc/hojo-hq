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
        if (stage === "案件化") counts[product]["案件化数"]++;
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
    var counts = {};
    config.ranks.forEach(function (rank) {
      counts[rank] = { "滞留企業数": 0, "掘り起こし待ち件数": 0 };
    });
    (records || []).forEach(function (record) {
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

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    buildRouteStageFunnel: buildRouteStageFunnel,
    buildProductFunnel: buildProductFunnel,
    buildRankSummary: buildRankSummary
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowDashboard = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
