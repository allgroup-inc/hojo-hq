/* GLOW企業リレーション台帳: 使っていないタブの整理(2026-11-07 小柳さん承認・改善⑥)
 *
 * タブが28個あり、空の「シート1〜」や古いバックアップが混ざって目的のタブを探しにくい。
 * 次のタブだけを「非表示」にする(消さない。シートの右クリック → 「非表示のシートを表示」でいつでも戻せる)。
 *   - 「シート」+数字の名前のタブ(手で足した名前の無いタブ。コードからは使っていない)
 *   - 「企業マスタ_backup」で始まる古いバックアップ(毎日のバックアップは別のファイルに取っている)
 *   - 行の無い「QR生成結果」
 * 見えるタブが1つも残らなくなる場合は何もしない(スプレッドシートの決まりで、すべては隠せない)。
 *
 * GAS(global.GlowTabTidy)と Node(module.exports)の両方で動く UMD 形式。
 * テスト: tests/glow_ma_todayList.test.mjs
 */
(function (global) {
  "use strict";

  var RULES = [
    function (s) { return /^シート\d+$/.test(s.name); },
    function (s) { return /^企業マスタ_backup/.test(s.name); },
    function (s) { return s.name === "QR生成結果" && !(s.rows > 0); }
  ];

  /* sheets: [{name, hidden, rows}] → 非表示にするタブの名前(元の並び順) */
  function planHide(sheets) {
    var list = sheets || [];
    var targets = list.filter(function (s) {
      return !s.hidden && RULES.some(function (rule) { return rule(s); });
    }).map(function (s) { return s.name; });
    var visibleLeft = list.filter(function (s) { return !s.hidden && targets.indexOf(s.name) === -1; }).length;
    return visibleLeft > 0 ? targets : [];
  }

  var api = { planHide: planHide };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowTabTidy = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
