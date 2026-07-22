/* フクギイロ 世帯診断ロジック v1(ミチビキ)
 * - ブラウザ(window.FGShindan)とNode(module.exports)の両方で動くUMD形式。
 *   Node側は tests/shindan.test.mjs のトラジェクトリevalで検証される(CI必須)。
 * - 方針(診断フロー設計v1・守り部):
 *   - 医療・健康/介護カテゴリと「障がい」対象制度は診断結果に出さない(掲載ページ案内のみ)
 *   - 出力は「可能性: 高/中」の2段階+要確認表示。断定語は使わない
 */
(function (global) {
  "use strict";

  var EXCLUDED_CATEGORIES = ["医療・健康", "介護"];
  var EXCLUDED_EVENTS = ["障がい"];
  var SCHOOL_AGES = ["高校生", "大学・専門"];

  /**
   * @param items  seido.json の items
   * @param answers {municipality, children, childAges:[], lifeEvents:[], housing}
   * @returns [{item, likelihood}] likelihood: "高" | "中"
   */
  function matchSeido(items, answers) {
    var results = [];
    var a = answers || {};
    var lifeEvents = a.lifeEvents || [];
    var childAges = a.childAges || [];
    var children = a.children || 0;

    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      if (EXCLUDED_CATEGORIES.indexOf(it.category) >= 0) continue;
      var excluded = false;
      for (var j = 0; j < EXCLUDED_EVENTS.length; j++) {
        if ((it.life_events || []).indexOf(EXCLUDED_EVENTS[j]) >= 0 &&
            (it.life_events || []).length === 1) { excluded = true; }
      }
      if (excluded) continue;

      // 地域: 全国 / 沖縄県 / 回答した市町村のみ。県外回答なら全国のみ
      var area = it.area || "全国";
      var areaOk = area === "全国" ||
        (a.municipality !== "県外" && (area === "沖縄県" || area === a.municipality));
      if (!areaOk) continue;

      // 子育て・教育カテゴリは子どもがいる世帯のみ
      var needsChild = it.category === "子育て" || it.category === "教育";
      if (needsChild && !(children > 0)) {
        // 妊娠・出産イベントは子ども0人でも対象になりうる(第一子妊娠中)
        var pregnancy = (it.life_events || []).indexOf("妊娠・出産") >= 0 &&
          lifeEvents.indexOf("妊娠・出産") >= 0;
        if (!pregnancy) continue;
      }
      // 教育カテゴリは高校生・大学等の年齢帯か、入学イベントがあるとき
      if (it.category === "教育") {
        var ageHit = childAges.some(function (ag) { return SCHOOL_AGES.indexOf(ag) >= 0; });
        var nyugaku = lifeEvents.indexOf("入園・入学") >= 0;
        if (!ageHit && !nyugaku) continue;
      }

      // 可能性: 選んだライフイベントに直接一致=高 / 世帯構成からの推定=中
      var direct = (it.life_events || []).some(function (ev) {
        return lifeEvents.indexOf(ev) >= 0;
      });
      var inferred = needsChild && children > 0;
      if (!direct && !inferred) continue;

      results.push({ item: it, likelihood: direct ? "高" : "中" });
    }

    // 高を先に、同順位は名前順(安定表示)
    results.sort(function (x, y) {
      if (x.likelihood !== y.likelihood) return x.likelihood === "高" ? -1 : 1;
      return x.item.name < y.item.name ? -1 : 1;
    });
    return results;
  }

  var api = { matchSeido: matchSeido };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.FGShindan = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
