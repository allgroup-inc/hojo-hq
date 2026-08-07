/* GLOW企業リレーション台帳 外部呼び出し(Slack通知・Claude API)の壊れにくさユーティリティ
 * ブラウザ相当のGAS(global.GlowResilience)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_resilience.test.mjs で検証される。
 *
 * .claude/skills/resilient-agent-design の原則④(べき等性)⑤(リトライの上限と種類)を
 * AlertRunner.gs(Slack通知)・LetterRunner.gs(Claude API呼び出し)に適用するための共通部品。
 * 2026-08-07 glow-ma-triangle-review確定: リトライは最大3回・一時エラーのみ・
 * 状態はGASのScript Properties(または呼び出し元が渡すgetProperty/setProperty相当)に保存する。
 */
(function (global) {
  "use strict";

  var DEFAULT_MAX_ATTEMPTS = 3;
  var DEFAULT_BACKOFF_MS = [2000, 10000];

  /**
   * HTTPステータスコードが「再試行してよい」一時的な失敗かどうかを判定する。
   * 429(レート制限)・5xx(サーバ側一時停止)のみ再試行対象。
   * 401/403/404等は権限・存在しない対象・入力不正であり、再試行しても直らないため対象外。
   */
  function isRetryableHttpStatus(statusCode) {
    return statusCode === 429 || (statusCode >= 500 && statusCode < 600);
  }

  /**
   * attemptFn を最大 maxAttempts 回まで実行する。attemptFn は成功時に値を返し、
   * 失敗時は Error を throw する(呼び出し元が isRetryable で再試行可否を伝える)。
   *
   * options:
   *   maxAttempts: 最大試行回数(既定3回)
   *   backoffMs: 各リトライ前に待つミリ秒の配列(既定 [2000, 10000])
   *   isRetryable: (error) => boolean。省略時は全エラーを再試行対象とする
   *   sleepFn: (ms) => void。既定は何もしない(Node側のテスト用)。
   *            GAS側の呼び出し元は Utilities.sleep を渡すこと。
   *   onRetry: (error, attemptNumber) => void。リトライ発生のたびに呼ばれる(ログ記録用)
   *
   * 戻り値: attemptFn の成功時の戻り値。
   * 全試行が失敗した場合、または isRetryable が false を返した場合は最後のエラーを rethrow する。
   */
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

  /**
   * 「本日分は既に完了しているか」を判定する、日次バッチ向けのべき等性チェック。
   * lastCompletedDate(前回完了日の文字列, 例: "2026-08-07")と todayString を比較するだけの
   * 純粋関数。実際の読み書き先(Script Properties等)は呼び出し元の責務とする。
   */
  function isAlreadyCompletedToday(lastCompletedDate, todayString) {
    return !!lastCompletedDate && lastCompletedDate === todayString;
  }

  var api = {
    DEFAULT_MAX_ATTEMPTS: DEFAULT_MAX_ATTEMPTS,
    DEFAULT_BACKOFF_MS: DEFAULT_BACKOFF_MS,
    isRetryableHttpStatus: isRetryableHttpStatus,
    withRetry: withRetry,
    isAlreadyCompletedToday: isAlreadyCompletedToday
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowResilience = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
