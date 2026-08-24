/* GLOW企業リレーション台帳 レター文面組み立て・ナーチャリング対象選定ロジック
 * ブラウザ相当のGAS(global.GlowLetterContent)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_letterContent.test.mjs で検証される。
 *
 * daysBetween は glow-ma/src/alerting.js の GlowAlerting をそのまま利用し、
 * 日付計算ロジックをこのファイルで重複定義しない。
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
    referralRoute: "①紹介",
    leadProductForReferral: "M&A",
    leadProductDefault: "法人保険・経営相談",
    nurturing: {
      eligibleStages: ["関係構築中", "提案中", "案件化"],
      eligibleRanks: ["B", "C", "D"],
      minIntervalDays: 90
    }
  };

  function determineLeadProduct(record, config) {
    config = config || DEFAULT_CONFIG;
    var routes = record["流入ルート"] || [];
    if (routes.indexOf(config.referralRoute) !== -1) {
      return config.leadProductForReferral;
    }
    return config.leadProductDefault;
  }

  function buildTrackingUrl(companyId, baseUrl) {
    if (!companyId || !baseUrl) return "";
    var separator = baseUrl.indexOf("?") === -1 ? "?" : "&";
    return baseUrl + separator + "id=" + encodeURIComponent(companyId);
  }

  function buildLetterPrompt(record, trackingUrl, config) {
    config = config || DEFAULT_CONFIG;
    var leadProduct = determineLeadProduct(record, config);
    var isReferralLead = leadProduct === config.leadProductForReferral;
    var leadProductCondition = isReferralLead
      ? "- この企業は紹介ルート経由のため、M&Aの話から入って構わない"
      : "- いきなりM&Aの話から入らないこと";
    var lines = [
      "あなたは沖縄の中小企業向けM&A・不動産・法人保険を扱う株式会社GLOWの営業担当です。",
      "以下の企業宛てに送る手紙の文面を、丁寧で押しつけがましくない経営相談ベースのトーンで下書きしてください。",
      "",
      "企業名: " + (record["会社名"] || ""),
      "業種: " + (record["業種"] || "不明"),
      "最初にご案内する内容: " + leadProduct,
      "",
      "条件:",
      "- 「売り込み」ではなく「無料の経営相談・情報提供」という体裁にすること",
      leadProductCondition,
      "- 文末に次のURLへの案内を自然に含めること: " + (trackingUrl || ""),
      "- 断定的な成果保証をしないこと",
      "",
      "文章の質(AIが書いたと分かる定型文を避ける。.claude/skills/humanizer準拠):",
      "- 「〜をご存知でしょうか」「実は、」といった定型の書き出しや、",
      "  「ぜひご検討ください!」のような判で押した結びを使わないこと",
      "- 絵文字・「!」の多用、意味のない強調は使わないこと",
      "- 一文の長さにばらつきを持たせ、すべての文を同じ語尾(「です・ます」等)で",
      "  終わらせず、実際に人が書いた手紙のような自然な文章にすること",
      "",
      "300〜500字程度の手紙文面のみを出力してください。"
    ];
    return lines.join("\n");
  }

  var INITIAL_OUTREACH_RANK_ORDER = ["A", "B", "C", "D"];

  /**
   * 初回DM(手紙第1便)を送る対象を選定する。「現在ステージ」が未接触、かつ連絡不要でない
   * 企業を、ランク(A→D、未分類は最後)→総合スコア降順の順に並べ、上位limit件を返す
   * (limit省略時は該当企業全件)。
   */
  function selectInitialOutreachTargets(records, limit, config) {
    config = config || DEFAULT_CONFIG;
    var eligible = (records || []).filter(function (record) {
      if (record["連絡不要"] === true) return false;
      return record["現在ステージ"] === "未接触";
    });
    var sorted = eligible.slice().sort(function (a, b) {
      var rankA = INITIAL_OUTREACH_RANK_ORDER.indexOf(a["ランク"]);
      if (rankA === -1) rankA = INITIAL_OUTREACH_RANK_ORDER.length;
      var rankB = INITIAL_OUTREACH_RANK_ORDER.indexOf(b["ランク"]);
      if (rankB === -1) rankB = INITIAL_OUTREACH_RANK_ORDER.length;
      if (rankA !== rankB) return rankA - rankB;
      return (Number(b["総合スコア"]) || 0) - (Number(a["総合スコア"]) || 0);
    });
    return typeof limit === "number" ? sorted.slice(0, limit) : sorted;
  }

  function selectNurturingTargets(records, todayValue, config) {
    config = config || DEFAULT_CONFIG;
    var nurturing = config.nurturing || DEFAULT_CONFIG.nurturing;
    return (records || []).filter(function (record) {
      if (record["連絡不要"] === true) return false;
      if (nurturing.eligibleStages.indexOf(record["現在ステージ"]) === -1) return false;
      // 意図的に企業マスタの「ランク」列(スコアそのもの)で判定する。alerting.jsの
      // resolveEffectiveRank(紹介ルートは常にA相当)は接触サイクル判定専用の例外であり、
      // 紹介ルートは既にAサイクルでフォローされるため、ナーチャリング対象の選定には適用しない。
      if (nurturing.eligibleRanks.indexOf(record["ランク"]) === -1) return false;
      var lastTouch = record["最終接触日"] || record["登録日"];
      var days = getGlowAlerting_().daysBetween(lastTouch, todayValue);
      if (days === null) return false;
      return days >= nurturing.minIntervalDays;
    });
  }

  var api = {
    DEFAULT_CONFIG: DEFAULT_CONFIG,
    determineLeadProduct: determineLeadProduct,
    buildTrackingUrl: buildTrackingUrl,
    buildLetterPrompt: buildLetterPrompt,
    selectInitialOutreachTargets: selectInitialOutreachTargets,
    selectNurturingTargets: selectNurturingTargets
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowLetterContent = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
