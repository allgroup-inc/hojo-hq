/* ノビシロ 診断商品バックエンド 純粋ロジック(ケンショウ/守り部ゲート対象)
 * GAS固有API(UrlFetchApp/MailApp/SpreadsheetApp/PropertiesService)には一切依存しない。
 * ブラウザ(window)/GAS(globalThis)/Node(module.exports)のいずれでも動くUMD形式。
 * Node側は tests/nobishiro-shindan-backend.test.mjs で検証される(CI必須)。
 */
(function (global) {
  "use strict";

  var PRICE_YEN = 14800;

  var VALID_INDUSTRIES = ["建設業", "飲食業", "小売業", "サービス業", "製造業", "その他"];
  var VALID_EMPLOYEE_COUNTS = ["1〜5人", "6〜20人", "21〜50人", "51人以上"];
  var VALID_REVENUE_RANGES = ["〜300万円", "300〜1000万円", "1000〜3000万円", "3000万円以上"];
  var VALID_COST_FEELINGS = ["かなり負担", "やや負担", "あまり気にならない"];
  var VALID_SALES_CHALLENGES = ["リード獲得", "追客", "提案書作成", "その他"];
  var VALID_PRIORITIES = ["コスト削減", "営業効率"];

  function validateSubmission(answers) {
    if (!answers || typeof answers !== "object") {
      return { valid: false, errors: ["回答データがありません"] };
    }
    var errors = [];
    if (!answers.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(answers.email)) {
      errors.push("メールアドレスを正しく入力してください");
    }
    if (VALID_INDUSTRIES.indexOf(answers.industry) === -1) errors.push("業種を選択してください");
    if (VALID_EMPLOYEE_COUNTS.indexOf(answers.employeeCount) === -1) errors.push("従業員数を選択してください");
    if (VALID_REVENUE_RANGES.indexOf(answers.monthlyRevenue) === -1) errors.push("月商規模を選択してください");
    if (VALID_COST_FEELINGS.indexOf(answers.costFeeling) === -1) errors.push("管理コストの実感を選択してください");
    if (VALID_SALES_CHALLENGES.indexOf(answers.salesChallenge) === -1) errors.push("営業効率の課題を選択してください");
    if (VALID_PRIORITIES.indexOf(answers.priority) === -1) errors.push("最優先課題を選択してください");
    return { valid: errors.length === 0, errors: errors };
  }

  function buildReportPrompt(answers) {
    return [
      "あなたは「ガジュマルくん」という、沖縄の中小企業のバックオフィス業務をAIで自動化・改善提案するアシスタントです。",
      "以下の企業の回答をもとに、やさしい言葉で、断定的な表現を避けた診断レポートを作成してください。",
      "",
      "# 回答内容",
      "業種: " + answers.industry,
      "従業員数: " + answers.employeeCount,
      "月商規模: " + answers.monthlyRevenue,
      "管理コストの実感: " + answers.costFeeling,
      "営業効率の課題: " + answers.salesChallenge,
      "最優先課題: " + answers.priority,
      "",
      "# レポートの構成(この順番で、見出し記号なしの日本語プレーンテキストで)",
      "1. 現状分析(2〜3文、回答内容の要約と課題の言語化)",
      "2. コスト構造の推定(一般的な傾向として、断定を避けた表現で。金額を断定しない)",
      "3. おすすめプラン(ライト/スタンダード/プロのいずれかを、理由とともに1つ提案)",
      "4. 次の一歩(無料相談への誘導を1文)",
      "",
      "文字数は600〜800字程度。専門用語は使わず、経営者にやさしく語りかけるトーンで。",
    ].join("\n");
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function buildReportEmailHtml(reportText, answers) {
    var body = escapeHtml(reportText).replace(/\n/g, "<br>");
    return [
      '<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px;color:#1F2A2E;">',
      '<h1 style="color:#2F6B4F;font-size:1.3rem;">ガジュマルくんからの診断レポート</h1>',
      "<p>お待たせしました。あなたの会社向けのAI活用診断レポートです。</p>",
      '<div style="background:#FAF7F0;border:1px solid #E4DCC9;border-radius:12px;padding:20px;">',
      body,
      "</div>",
      '<p style="margin-top:24px;">より詳しいご相談は<a href="https://allgroup-inc.github.io/hojo-hq/nobishiro/contact/">無料相談予約ページ</a>からどうぞ。</p>',
      '<p style="font-size:.85rem;color:#5C6B70;">本レポートはAIが自動生成したものであり、内容の詳細は改めてご相談の上ご確認ください。</p>',
      "</div>",
    ].join("");
  }

  var api = {
    PRICE_YEN: PRICE_YEN,
    VALID_INDUSTRIES: VALID_INDUSTRIES,
    VALID_EMPLOYEE_COUNTS: VALID_EMPLOYEE_COUNTS,
    VALID_REVENUE_RANGES: VALID_REVENUE_RANGES,
    VALID_COST_FEELINGS: VALID_COST_FEELINGS,
    VALID_SALES_CHALLENGES: VALID_SALES_CHALLENGES,
    VALID_PRIORITIES: VALID_PRIORITIES,
    validateSubmission: validateSubmission,
    buildReportPrompt: buildReportPrompt,
    escapeHtml: escapeHtml,
    buildReportEmailHtml: buildReportEmailHtml,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.NBBackendLogic = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
