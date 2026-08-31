/* GLOW企業リレーション台帳 集客ファネルの週次集計(Phase A: v1.5)
 * ブラウザ相当のGAS(global.GlowFunnelContent)とNode(module.exports)の両方で動くUMD形式。
 *
 * hojo-hq側で毎日自動収集されているKPIデータ(LP閲覧=Plausible、LINE友だち数=LINE
 * Insight API)と、glow-ma内部のデータ(企業マスタの新規登録・対応履歴の面談/提案/成約)を
 * 「閲覧 → LINE登録 → 新規登録 → 面談 → 提案 → 成約」のファネルとして週次で1つの表に揃える。
 * AdminRunner.gs の getFunnelSummary がデータを読み取り・取得した後にこれを呼ぶ。
 *
 * 数値が取得できない週は0ではなくnullを返す(「実績ゼロ」と「データ取得できず」を
 * 混同すると、KGIの現在地を見誤る。絶対ルール1: 不明時は断定しない)。
 */
(function (global) {
  "use strict";

  function getGlowAlerting_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./alerting.js");
    }
    return global.GlowAlerting;
  }

  var FUNNEL_ROUTES_ = ["①紹介", "②手紙DM", "③ミカタ経由"];
  var WEEK_LABELS_ = ["今週", "先週", "2週前", "3週前", "4週前", "5週前"];

  function formatDate_(date) {
    var year = date.getFullYear();
    var month = String(date.getMonth() + 1);
    if (month.length < 2) month = "0" + month;
    var day = String(date.getDate());
    if (day.length < 2) day = "0" + day;
    return year + "-" + month + "-" + day;
  }

  function normalizeDate_(value) {
    var date = getGlowAlerting_().toDate(value);
    return date ? formatDate_(date) : "";
  }

  /**
   * 月曜はじまりの週の区切りを作る(buildActivitySummaryと同じ規約)。
   */
  function buildWeekRanges_(todayString, weeksBack) {
    var parts = todayString.split("-").map(Number);
    var today = new Date(parts[0], parts[1] - 1, parts[2]);
    var mondayOffset = (today.getDay() + 6) % 7;
    var ranges = [];
    for (var w = 0; w < weeksBack; w++) {
      var start = new Date(today.getFullYear(), today.getMonth(), today.getDate() - mondayOffset - w * 7);
      var end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 6);
      ranges.push({
        label: WEEK_LABELS_[w] || w + "週前",
        start: formatDate_(start),
        end: formatDate_(end)
      });
    }
    return ranges;
  }

  /**
   * 1週分のLP閲覧数。24h(日次)集計の合計を基本とし、日次が1件もない週は
   * その週の7d(週次)集計の最後の値で代用する(Plausible収集が止まっていた期間への対応)。
   * どちらも無ければnull(=取得できず)。
   */
  function sumLpVisitors_(siteTraffic, start, end) {
    var dailySum = null;
    var weeklyFallback = null;
    (siteTraffic || []).forEach(function (entry) {
      if (!entry || !entry.date || entry.date < start || entry.date > end) return;
      var visitors = entry.domain && typeof entry.domain.visitors === "number" ? entry.domain.visitors : null;
      if (visitors === null) return;
      if (entry.period === "24h") {
        dailySum = (dailySum === null ? 0 : dailySum) + visitors;
      } else if (entry.period === "7d") {
        weeklyFallback = visitors;
      }
    });
    if (dailySum !== null) return dailySum;
    return weeklyFallback;
  }

  /**
   * 指定日以前の最新のLINE友だち数(累計)。無ければnull。
   */
  function followersAsOf_(lineFollowers, dateString) {
    var latest = null;
    (lineFollowers || []).forEach(function (entry) {
      if (!entry || !entry.date || entry.date > dateString) return;
      if (typeof entry.followers !== "number") return;
      if (!latest || entry.date > latest.date) latest = entry;
    });
    return latest ? latest.followers : null;
  }

  function buildWeeklyFunnel(input, todayString, weeksBack) {
    var source = input || {};
    var count = typeof weeksBack === "number" ? weeksBack : 4;
    var ranges = buildWeekRanges_(todayString, count);
    var activityWeeks = {};
    ((source.activity && source.activity.weeks) || []).forEach(function (week) {
      activityWeeks[week.start] = week.total || {};
    });

    var weeks = ranges.map(function (range) {
      var lineEnd = followersAsOf_(source.lineFollowers, range.end);
      var lineBefore = followersAsOf_(
        source.lineFollowers,
        // 週初日の前日 = 前週の末日
        formatDate_(new Date(
          Number(range.start.slice(0, 4)),
          Number(range.start.slice(5, 7)) - 1,
          Number(range.start.slice(8, 10)) - 1
        ))
      );
      var newByRoute = {};
      FUNNEL_ROUTES_.forEach(function (route) { newByRoute[route] = 0; });
      var newCompanies = 0;
      (source.companies || []).forEach(function (company) {
        var registered = normalizeDate_(company["登録日"]);
        if (!registered || registered < range.start || registered > range.end) return;
        newCompanies += 1;
        (company["流入ルート"] || []).forEach(function (route) {
          if (newByRoute[route] !== undefined) newByRoute[route] += 1;
        });
      });
      var activityTotals = activityWeeks[range.start] || {};
      return {
        label: range.label,
        start: range.start,
        end: range.end,
        lpVisitors: sumLpVisitors_(source.siteTraffic, range.start, range.end),
        lineFollowersEnd: lineEnd,
        lineNet: (lineEnd !== null && lineBefore !== null) ? lineEnd - lineBefore : null,
        newCompanies: newCompanies,
        newByRoute: newByRoute,
        meetings: typeof activityTotals["面談・訪問"] === "number" ? activityTotals["面談・訪問"] : 0,
        proposals: typeof activityTotals["提案"] === "number" ? activityTotals["提案"] : 0,
        closings: typeof activityTotals["成約"] === "number" ? activityTotals["成約"] : 0
      };
    });

    var target = typeof source.kgiTarget === "number" ? source.kgiTarget : 1000;
    var current = followersAsOf_(source.lineFollowers, "9999-12-31");
    return {
      kgi: {
        current: current,
        target: target,
        ratePercent: current === null ? null : Math.round((current / target) * 1000) / 10
      },
      weeks: weeks
    };
  }

  var api = {
    buildWeeklyFunnel: buildWeeklyFunnel,
    FUNNEL_ROUTES: FUNNEL_ROUTES_
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowFunnelContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
