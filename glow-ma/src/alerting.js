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

  var DEFAULT_CONFIG = {
    cycleDaysByRank: { A: 30, B: 90, C: 180, D: 365 },
    referralRoute: "①紹介"
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

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    toDate: toDate,
    daysBetween: daysBetween,
    resolveEffectiveRank: resolveEffectiveRank,
    isOverdue: isOverdue
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowAlerting = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
