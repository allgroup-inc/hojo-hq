/* GLOW企業リレーション台帳 スコアリング・ランク判定ロジック
 * ブラウザ相当のGAS(global.GlowScoring)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_scoring.test.mjs で検証される。
 *
 * 数値の根拠: docs/superpowers/specs/2026-07-27-glow-ma-scoring-triangle-review.md
 * (2026-07-27 glow-ma-triangle-review確定、見直し期限2026-10-27)。
 *
 * industryTiers.high は「事業承継ニーズが相対的に高いとされる業種」のたたき台キーワード
 * リストであり、GLOWチームの実務レビューを経た確定版ではない。運用しながら見直すこと。
 */
(function (global) {
  "use strict";

  var DEFAULT_CONFIG = {
    industryTiers: {
      high: ["建設", "運送", "介護", "美容", "理容", "飲食", "小売"],
      low: []
    },
    industryTierPoints: { high: 20, mid: 10, low: 0 },
    sizeBands: [
      { min: 10, max: 50, points: 10 },
      { min: 5, max: 9, points: 5 },
      { min: 51, max: 100, points: 5 }
    ],
    ageBands: [
      { min: 70, max: 120, points: 15 },
      { min: 60, max: 69, points: 10 },
      { min: 50, max: 59, points: 5 }
    ],
    routeBonus: { "①紹介": 30, "②手紙DM": 0, "③ミカタ経由": 20 },
    reactionPointsByType: {
      "レターURLアクセス": 5,
      "返信": 15,
      "入電": 20,
      "ゆんたく相談実施": 25,
      "面談実施": 25,
      "資料請求": 10
    },
    decisionMakerBonus: 15,
    rankThresholds: { A: 70, B: 40, C: 15 }
  };

  function classifyIndustryTier(industryText, config) {
    config = config || DEFAULT_CONFIG;
    var text = String(industryText || "");
    var matchesAny = function (keywords) {
      return (keywords || []).some(function (keyword) {
        return text.indexOf(keyword) !== -1;
      });
    };
    if (matchesAny(config.industryTiers.high)) return "high";
    if (matchesAny(config.industryTiers.low)) return "low";
    // 未一致(空文字含む)は「未分類」と「実質mid」を区別できないため、
    // lowとして減点せずmid(中立)扱いにする。意図的な仕様。
    return "mid";
  }

  function extractNumber(text) {
    var match = String(text || "").match(/\d+/);
    return match ? parseInt(match[0], 10) : null;
  }

  function findBandPoints(numericValue, bands) {
    for (var i = 0; i < bands.length; i++) {
      var band = bands[i];
      if (numericValue >= band.min && numericValue <= band.max) return band.points;
    }
    return 0;
  }

  function calculateSizeBandPoints(sizeText, config) {
    config = config || DEFAULT_CONFIG;
    var n = extractNumber(sizeText);
    if (n === null) return 0;
    return findBandPoints(n, config.sizeBands);
  }

  function calculateAgeBandPoints(ageText, config) {
    config = config || DEFAULT_CONFIG;
    var n = extractNumber(ageText);
    if (n === null) return 0;
    return findBandPoints(n, config.ageBands);
  }

  function calculateAttributeScore(company, config) {
    config = config || DEFAULT_CONFIG;
    var tier = classifyIndustryTier(company["業種"], config);
    var industryPoints = config.industryTierPoints[tier] || 0;
    var sizePoints = calculateSizeBandPoints(company["規模"], config);
    var agePoints = calculateAgeBandPoints(company["代表者年齢"], config);
    return industryPoints + sizePoints + agePoints;
  }

  function calculateRouteBonus(routes, config) {
    config = config || DEFAULT_CONFIG;
    var max = 0;
    (routes || []).forEach(function (route) {
      var points = config.routeBonus[route];
      if (typeof points === "number" && points > max) max = points;
    });
    return max;
  }

  /**
   * 事前選定スコア(外部の選定作業による評価点)を数値として取り出す。
   * 空欄・非数値は0として扱い、既存の計算結果に影響しない
   * (設計書: docs/superpowers/specs/2026-08-11-glow-ma-pre-screening-score-import-design.md)。
   */
  function calculatePreScreeningScore(record) {
    var n = Number(record["事前選定スコア"]);
    return isNaN(n) ? 0 : n;
  }

  // 反応スコアの上限化: 種別ごとに最初の1件のみ加点し(同一種別の繰り返しは加点しない)、
  // 意思決定者接触ボーナスも企業ごとに最大1回のみ加点する。
  // 根拠: docs/superpowers/specs/2026-07-27-glow-ma-reaction-score-cap-triangle-review.md
  function calculateReactionScore(interactionRows, config) {
    config = config || DEFAULT_CONFIG;
    var total = 0;
    var seenTypes = {};
    var decisionMakerContacted = false;
    (interactionRows || []).forEach(function (row) {
      var type = row["種別"];
      var typePoints = config.reactionPointsByType[type];
      if (typeof typePoints === "number" && !seenTypes[type]) {
        seenTypes[type] = true;
        total += typePoints;
      }
      if (row["対応相手"] === "オーナー社長本人") {
        decisionMakerContacted = true;
      }
    });
    if (decisionMakerContacted) {
      total += config.decisionMakerBonus;
    }
    return total;
  }

  function calculateRank(totalScore, config) {
    config = config || DEFAULT_CONFIG;
    var t = config.rankThresholds;
    if (totalScore >= t.A) return "A";
    if (totalScore >= t.B) return "B";
    if (totalScore >= t.C) return "C";
    return "D";
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    classifyIndustryTier: classifyIndustryTier,
    calculateSizeBandPoints: calculateSizeBandPoints,
    calculateAgeBandPoints: calculateAgeBandPoints,
    calculateAttributeScore: calculateAttributeScore,
    calculateRouteBonus: calculateRouteBonus,
    calculatePreScreeningScore: calculatePreScreeningScore,
    calculateReactionScore: calculateReactionScore,
    calculateRank: calculateRank
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowScoring = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
