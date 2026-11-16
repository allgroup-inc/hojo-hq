/**
 * GLOW企業リレーション台帳: この実行が始まってからの経過時間
 *
 * Apps Script は、実行のたびに全ファイルを読み込み直す。ファイルの一番外側に書いた式は、その実行の最初に1回だけ動くので、
 * ここで時刻を覚えておけば「この実行が始まってから何ミリ秒たったか」が分かる(トリガー・メニュー・エディタのどれから動いても同じ)。
 * 何を始めてよいかの判定は executionBudget.js(GlowExecutionBudget)。
 */
var GLOW_EXECUTION_STARTED_MS = Date.now();

function executionElapsedMs_() {
  return Date.now() - GLOW_EXECUTION_STARTED_MS;
}
