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

  var api = {
    PRICE_YEN: PRICE_YEN,
    VALID_INDUSTRIES: VALID_INDUSTRIES,
    VALID_EMPLOYEE_COUNTS: VALID_EMPLOYEE_COUNTS,
    VALID_REVENUE_RANGES: VALID_REVENUE_RANGES,
    VALID_COST_FEELINGS: VALID_COST_FEELINGS,
    VALID_SALES_CHALLENGES: VALID_SALES_CHALLENGES,
    VALID_PRIORITIES: VALID_PRIORITIES,
    validateSubmission: validateSubmission,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.NBBackendLogic = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
