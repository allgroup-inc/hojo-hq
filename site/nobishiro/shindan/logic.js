/* ノビシロ 診断フォーム ロジック(ケンショウ対象)
 * ブラウザ(window)/Node(module.exports)の両方で動くUMD形式。
 * Node側は tests/nobishiro-shindan-logic.test.mjs で検証される(CI必須)。
 * バリデーション許容値は gas/nobishiro-shindan/Logic.gs (NBBackendLogic)側と一致させる
 * (デプロイ先が別々のためコード自体は複製だが、値の一致はテストで担保する)。
 */
(function (global) {
  "use strict";

  var VALID_INDUSTRIES = ["建設業", "飲食業", "小売業", "サービス業", "製造業", "その他"];
  var VALID_EMPLOYEE_COUNTS = ["1〜5人", "6〜20人", "21〜50人", "51人以上"];
  var VALID_REVENUE_RANGES = ["〜300万円", "300〜1000万円", "1000〜3000万円", "3000万円以上"];
  var VALID_COST_FEELINGS = ["かなり負担", "やや負担", "あまり気にならない"];
  var VALID_SALES_CHALLENGES = ["リード獲得", "追客", "提案書作成", "その他"];
  var VALID_PRIORITIES = ["コスト削減", "営業効率"];

  function validateForm(answers) {
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

  function submitDiagnosis(answers, endpointUrl, fetchFn) {
    var validation = validateForm(answers);
    if (!validation.valid) {
      return Promise.reject(new Error(validation.errors.join(" / ")));
    }
    // Content-Type: text/plain にするとブラウザのCORSプリフライト(OPTIONS)が発生せず、
    // GAS Web Appへの直接POSTが成功する(GAS側はcontent-typeに関わらずe.postData.contentsを読める)。
    return fetchFn(endpointUrl + "?type=submit", {
      method: "POST",
      headers: { "Content-Type": "text/plain" },
      body: JSON.stringify({ answers: answers }),
    })
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        if (data.error) {
          if (Array.isArray(data.details) && data.details.length > 0) {
            throw new Error(data.details.join(" / "));
          }
          var messages = {
            validation_failed: "入力内容をご確認ください。",
            stripe_session_failed: "決済ページの準備に失敗しました。時間をおいて再度お試しください。",
            invalid_json: "送信内容に問題がありました。もう一度お試しください。",
            unknown_type: "エラーが発生しました。時間をおいて再度お試しください。",
          };
          throw new Error(messages[data.error] || "エラーが発生しました。時間をおいて再度お試しください。");
        }
        return data.url;
      });
  }

  var api = {
    validateForm: validateForm,
    submitDiagnosis: submitDiagnosis,
    VALID_INDUSTRIES: VALID_INDUSTRIES,
    VALID_EMPLOYEE_COUNTS: VALID_EMPLOYEE_COUNTS,
    VALID_REVENUE_RANGES: VALID_REVENUE_RANGES,
    VALID_COST_FEELINGS: VALID_COST_FEELINGS,
    VALID_SALES_CHALLENGES: VALID_SALES_CHALLENGES,
    VALID_PRIORITIES: VALID_PRIORITIES,
  };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.NBShindan = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
