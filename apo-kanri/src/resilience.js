/* アポ管理台帳 外部呼び出し(Slack通知)の壊れにくさユーティリティ
 * ブラウザ相当のGAS(global.ApoResilience)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/apo_kanri_resilience.test.mjs で検証される。
 *
 * .claude/skills/resilient-agent-design の原則④(べき等性)⑤(リトライの上限と種類)を
 * ApoRunner.gs(Slack通知)に適用するための共通部品。glow-ma と同じ確定方針:
 * リトライは最大3回・一時エラー(429/5xx)のみ。
 * ※ glow-ma/src/resilience.js と同内容だが、apo-kanri から glow-ma への参照は
 *   禁止(設計書裁定②)のため、名前空間を変えて自前で持つ。
 */
(function (global) {
  "use strict";

  var DEFAULT_MAX_ATTEMPTS = 3;
  var DEFAULT_BACKOFF_MS = [2000, 10000];

  function isRetryableHttpStatus(statusCode) {
    return statusCode === 429 || (statusCode >= 500 && statusCode < 600);
  }

  function withRetry(attemptFn, options) {
    var opts = options || {};
    var maxAttempts = opts.maxAttempts || DEFAULT_MAX_ATTEMPTS;
    var backoffMs = opts.backoffMs || DEFAULT_BACKOFF_MS;
    var isRetryable = typeof opts.isRetryable === "function" ? opts.isRetryable : function () { return true; };
    var sleepFn = typeof opts.sleepFn === "function" ? opts.sleepFn : function () {};
    var onRetry = typeof opts.onRetry === "function" ? opts.onRetry : function () {};

    var lastError;
    for (var attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        return attemptFn(attempt);
      } catch (error) {
        lastError = error;
        var isLastAttempt = attempt === maxAttempts;
        if (isLastAttempt || !isRetryable(error)) {
          throw error;
        }
        onRetry(error, attempt);
        sleepFn(backoffMs[attempt - 1] || backoffMs[backoffMs.length - 1]);
      }
    }
    throw lastError;
  }

  var api = {
    DEFAULT_MAX_ATTEMPTS: DEFAULT_MAX_ATTEMPTS,
    DEFAULT_BACKOFF_MS: DEFAULT_BACKOFF_MS,
    isRetryableHttpStatus: isRetryableHttpStatus,
    withRetry: withRetry
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.ApoResilience = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
