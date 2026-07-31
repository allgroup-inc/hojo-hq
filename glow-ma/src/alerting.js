/* GLOW企業リレーション台帳 掘り起こしアラート・ネクストベストアクション判定ロジック
 * ブラウザ相当のGAS(global.GlowAlerting)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_alerting.test.mjs で検証される。
 *
 * ランク別接触サイクル・紹介ルートの例外は
 * docs/superpowers/specs/2026-07-26-glow-ma-relation-system-design.md 8章
 * (2026-07-27 glow-ma-triangle-review確定)に基づく。
 */
(function (global) {
  "use strict";

  var NEXT_BEST_ACTION_RULES = [
    { rank: "A", stages: ["未接触", "アプローチ実施", "電話済み"], action: "至急電話推奨(最優先ランク)" },
    { rank: "B", stages: ["未接触", "アプローチ実施"], action: "電話推奨" },
    { rank: "C", stages: ["アプローチ実施", "電話済み"], action: "ゆんたく相談室の再案内" },
    { rank: "D", stages: null, action: "ナーチャリング配信の対象に追加" }
  ];
  var DEFAULT_NEXT_BEST_ACTION = "対応履歴を確認し次のアクションを検討";

  var DEFAULT_CONFIG = {
    cycleDaysByRank: { A: 30, B: 90, C: 180, D: 365 },
    referralRoute: "①紹介",
    nextBestActionRules: NEXT_BEST_ACTION_RULES,
    defaultNextBestAction: DEFAULT_NEXT_BEST_ACTION
  };

  function toDate(value) {
    if (value instanceof Date) return value;
    if (typeof value === "string" && value) {
      var parts = value.split("-");
      if (parts.length === 3) {
        var year = Number(parts[0]);
        var month = Number(parts[1]);
        var day = Number(parts[2]);
        if (!isNaN(year) && !isNaN(month) && !isNaN(day)) {
          return new Date(year, month - 1, day);
        }
      }
    }
    return null;
  }

  function daysBetween(fromValue, toValue) {
    var from = toDate(fromValue);
    var to = toDate(toValue);
    if (!from || !to) return null;
    var msPerDay = 24 * 60 * 60 * 1000;
    return Math.floor((to.getTime() - from.getTime()) / msPerDay);
  }

  function resolveEffectiveRank(record, config) {
    config = config || DEFAULT_CONFIG;
    var routes = record["流入ルート"] || [];
    if (routes.indexOf(config.referralRoute) !== -1) return "A";
    return record["ランク"];
  }

  function isOverdue(record, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var dueDate = record["次回アクション予定日"];
    if (dueDate) {
      var daysUntilDue = daysBetween(todayValue, dueDate);
      if (daysUntilDue !== null) return daysUntilDue <= 0;
    }
    var effectiveRank = resolveEffectiveRank(record, config);
    var cycleDays = config.cycleDaysByRank[effectiveRank];
    if (typeof cycleDays !== "number") return false;
    var lastTouch = record["最終接触日"] || record["登録日"];
    var daysSinceTouch = daysBetween(lastTouch, todayValue);
    if (daysSinceTouch === null) return false;
    return daysSinceTouch >= cycleDays;
  }

  function determineNextBestAction(record, config) {
    config = config || DEFAULT_CONFIG;
    var rank = resolveEffectiveRank(record, config);
    var stage = record["現在ステージ"];
    var rules = config.nextBestActionRules || NEXT_BEST_ACTION_RULES;
    for (var i = 0; i < rules.length; i++) {
      var rule = rules[i];
      if (rule.rank !== rank) continue;
      if (rule.stages && rule.stages.indexOf(stage) === -1) continue;
      return rule.action;
    }
    return config.defaultNextBestAction || DEFAULT_NEXT_BEST_ACTION;
  }

  function buildDailyAlertList(records, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var rankOrder = { A: 0, B: 1, C: 2, D: 3 };
    var alerts = [];
    (records || []).forEach(function (record) {
      if (!isOverdue(record, todayValue, config)) return;
      alerts.push({
        "企業ID": record["企業ID"],
        "会社名": record["会社名"],
        "ランク": resolveEffectiveRank(record, config),
        "ネクストベストアクション": determineNextBestAction(record, config)
      });
    });
    alerts.sort(function (a, b) {
      var aOrder = rankOrder[a["ランク"]];
      var bOrder = rankOrder[b["ランク"]];
      aOrder = typeof aOrder === "number" ? aOrder : 99;
      bOrder = typeof bOrder === "number" ? bOrder : 99;
      return aOrder - bOrder;
    });
    return alerts;
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    toDate: toDate,
    daysBetween: daysBetween,
    resolveEffectiveRank: resolveEffectiveRank,
    isOverdue: isOverdue,
    determineNextBestAction: determineNextBestAction,
    buildDailyAlertList: buildDailyAlertList
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowAlerting = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
