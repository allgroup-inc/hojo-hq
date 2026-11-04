/* 世界の架け橋 WLD-02 相談企業KPIの集計ロジック(2026-11-04 開発・テスト段階)
 *
 * 台帳を触らない計算だけの関数。Node(module.exports)とGAS(global.GlowWld02Kpi)の両方で動くUMD形式。
 * テスト: tests/glow_ma_wld02Kpi.test.mjs
 *
 * 置き場所について: glow-ma/src/ ではなく glow-ma/wld02/ に置いている。src/ に入れると main への
 * マージで台帳のスクリプトへ自動反映されるため。本番台帳への反映(4つのタブの作成)と自動実行の登録は、
 * それぞれ別に承認を得てから src/ へ移す(設計書 v0 §6 の段階4・5)。
 *
 * 決まりごと(2026-11-02 WLD-02 決裁・2026-11-04 承認の推奨):
 * - 相談 = 確認担当が「確認済み」とした、実際の対面・オンライン面談だけ。電話・LINEのみは数えない
 * - AIや取り込みが付けた「面談実施」は、確認されるまで数えない(確認待ちとして別に数える)
 * - 集計開始日 2026-10-04。同じ会社は、企業ID対応表で統合後のIDにそろえてから1社と数える
 * - 流入経路④が後で外れても、確認済みの相談は累計に残す(要確認として別に数える)
 * - 掲載契約は、解除・取消があっても累計に残す。今も有効な数は別に数える
 * - 「現在ステージ」は使わない
 * - 週は月曜始まり。同じ週の行は上書きする(再実行で二重に数えない)
 * - 読めない記録が1つでもあれば、その週は「取得不能」とし、0件として書かない
 */
(function (global) {
  "use strict";

  var KPI_START_DATE = "2026-10-04";
  var KPI_TARGET_DATE = "2027-04-04";
  var KPI_TARGET_COMPANIES = 100;
  var WORLD_BUSINESS = "世界の架け橋";
  var WORLD_ROUTE_MARK = "④";
  var MEETING_TYPE = "面談実施";
  var MEETING_FORMATS = ["対面", "オンライン"];
  var VERDICT_CONFIRMED = "確認済み";

  // 2026-11-04 v0: 掲載契約の状態。「誤登録」は v0 の設計書に無い状態で、基本ルール
  // 「誤登録・重複は理由と訂正履歴を残して修正できる」を満たすために足した(v1 のレビューで確認する)。
  var CONTRACT_ACTIVE = "有効";
  var CONTRACT_MISTAKE = "誤登録";

  var WEEKLY_STATUS_OK = "集計済み";
  var WEEKLY_STATUS_UNAVAILABLE = "取得不能";

  var WEEKLY_FIELDS = [
    "週の開始日", "集計日時", "状態",
    "相談企業数_累計", "相談企業数_週内の新規",
    "掲載契約企業数_累計", "掲載契約企業数_有効",
    "確認待ちの面談数", "流入経路の要確認数", "実行ID"
  ];

  function str(v) {
    return v === null || v === undefined ? "" : String(v).trim();
  }

  function pad2(n) {
    return (n < 10 ? "0" : "") + n;
  }

  // "2026-10-04" / "2026/10/4" / Date を "YYYY-MM-DD" にする。読めなければ ""
  function toDate(v) {
    if (v instanceof Date) {
      if (isNaN(v.getTime())) return "";
      return v.getFullYear() + "-" + pad2(v.getMonth() + 1) + "-" + pad2(v.getDate());
    }
    var m = /^(\d{4})[-\/.](\d{1,2})[-\/.](\d{1,2})/.exec(str(v));
    if (!m) return "";
    var y = Number(m[1]), mo = Number(m[2]), d = Number(m[3]);
    var dt = new Date(Date.UTC(y, mo - 1, d));
    if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) return "";
    return y + "-" + pad2(mo) + "-" + pad2(d);
  }

  function addDays(dateStr, days) {
    var p = dateStr.split("-");
    var dt = new Date(Date.UTC(Number(p[0]), Number(p[1]) - 1, Number(p[2]) + days));
    return dt.getUTCFullYear() + "-" + pad2(dt.getUTCMonth() + 1) + "-" + pad2(dt.getUTCDate());
  }

  // その日を含む週の月曜日
  function weekStartMonday(dateLike) {
    var d = toDate(dateLike);
    if (!d) return "";
    var p = d.split("-");
    var dow = new Date(Date.UTC(Number(p[0]), Number(p[1]) - 1, Number(p[2]))).getUTCDay(); // 0=日
    return addDays(d, dow === 0 ? -6 : 1 - dow);
  }

  // 月曜の集計で数える「前の週」の月曜日(nowMs は日本時間で判定する)
  function previousWeekStart(nowMs) {
    var jst = new Date(nowMs + 9 * 60 * 60 * 1000);
    var today = jst.getUTCFullYear() + "-" + pad2(jst.getUTCMonth() + 1) + "-" + pad2(jst.getUTCDate());
    return addDays(weekStartMonday(today), -7);
  }

  function isCancelled(row) {
    var v = row && row.取消;
    return v === true || /^(true|取消|はい|1|済)$/i.test(str(v));
  }

  // 企業ID対応表 → 旧ID から統合後のIDへの対応。
  // 同じ旧IDの行が複数あれば、後の行(新しい記録)を正とする。「取消」の行は統合を取り消す。
  // A→B・B→C のようにつながっていれば A→C までたどる。輪になっていたら、その旧IDは統合しない。
  function buildIdResolver(idMapRows) {
    var latest = {};
    (idMapRows || []).forEach(function (row) {
      var from = str(row.旧企業ID);
      if (!from) return;
      latest[from] = isCancelled(row) ? null : str(row.統合後の企業ID) || null;
    });
    var problems = [];
    function resolve(id) {
      var start = str(id);
      if (!start) return "";
      var seen = {};
      var cur = start;
      while (latest[cur] && latest[cur] !== cur) {
        seen[cur] = true;
        cur = latest[cur];
        if (seen[cur]) {
          problems.push("企業ID対応表が輪になっています(" + start + ")");
          return start;
        }
      }
      return cur;
    }
    return { resolve: resolve, problems: problems };
  }

  function hasWorldRoute(route) {
    if (Array.isArray(route)) return route.some(function (r) { return str(r).indexOf(WORLD_ROUTE_MARK) === 0; });
    return str(route).indexOf(WORLD_ROUTE_MARK) >= 0;
  }

  // 面談確認記録のうち、正式KPIに数える行か
  function countsAsConsultation(row) {
    return str(row.判定) === VERDICT_CONFIRMED &&
      str(row.事業) === WORLD_BUSINESS &&
      MEETING_FORMATS.indexOf(str(row.形式)) >= 0 &&
      !isCancelled(row) &&
      toDate(row.面談日) !== "" &&
      toDate(row.面談日) >= KPI_START_DATE;
  }

  // 相談企業(統合後の企業ID → 最初の確認済み面談日)
  function consultationFirstDates(confirmRows, resolver) {
    var first = {};
    (confirmRows || []).forEach(function (row) {
      if (!countsAsConsultation(row)) return;
      var id = resolver.resolve(row.企業ID);
      if (!id) return;
      var d = toDate(row.面談日);
      if (!first[id] || d < first[id]) first[id] = d;
    });
    return first;
  }

  // 掲載契約記録(状態が変わるたびに行を足す)。契約IDごとに最後の行が今の状態。
  function contractStates(contractRows, resolver) {
    var byContract = {};
    (contractRows || []).forEach(function (row, i) {
      var cid = str(row.契約ID);
      if (!cid) return;
      var prev = byContract[cid];
      byContract[cid] = {
        companyId: resolver.resolve(row.企業ID) || (prev && prev.companyId) || "",
        signedOn: toDate(row.契約成立日) || (prev && prev.signedOn) || "",
        state: str(row.状態) || (prev && prev.state) || "",
        order: i
      };
    });
    return byContract;
  }

  // 対応履歴ログの「面談実施」のうち、まだ確認されていないもの(過去分も含む)。
  // 確認記録が取り消された履歴は、もう一度確認待ちに戻る。
  function pendingMeetingIds(historyRows, confirmRows) {
    var judged = {};
    (confirmRows || []).forEach(function (row) {
      var hid = str(row.元の履歴ID);
      if (hid && !isCancelled(row) && str(row.判定)) judged[hid] = true;
    });
    var pending = [];
    (historyRows || []).forEach(function (row) {
      var hid = str(row.履歴ID);
      if (str(row.種別) === MEETING_TYPE && hid && !judged[hid]) pending.push(hid);
    });
    return pending;
  }

  /* その週の週次KPIの行を作る。
   * sources: { confirmations, contracts, idMap, history, companies } — どれかが null/undefined
   *   (= 読めなかった)なら、数字を空にした「取得不能」の行を返す。
   * opts: { weekStart: "YYYY-MM-DD"(月曜), runAt: "YYYY-MM-DD HH:mm", runId }
   */
  function buildWeeklyRow(sources, opts) {
    var weekStart = weekStartMonday(opts && opts.weekStart);
    if (!weekStart || weekStart !== toDate(opts.weekStart)) {
      throw new Error("週の開始日は月曜日の日付で指定してください: " + str(opts && opts.weekStart));
    }
    var row = {};
    WEEKLY_FIELDS.forEach(function (f) { row[f] = ""; });
    row.週の開始日 = weekStart;
    row.集計日時 = str(opts.runAt);
    row.実行ID = str(opts.runId);

    var names = ["confirmations", "contracts", "idMap", "history", "companies"];
    var missing = names.filter(function (n) { return !sources || !Array.isArray(sources[n]); });
    if (missing.length) {
      row.状態 = WEEKLY_STATUS_UNAVAILABLE;
      return { row: row, problems: ["読めなかった記録: " + missing.join(", ")] };
    }

    var resolver = buildIdResolver(sources.idMap);
    var weekEnd = addDays(weekStart, 7); // この日を含まない

    var first = consultationFirstDates(sources.confirmations, resolver);
    var total = 0, newInWeek = 0;
    Object.keys(first).forEach(function (id) {
      if (first[id] < weekEnd) total++;
      if (first[id] >= weekStart && first[id] < weekEnd) newInWeek++;
    });

    var everSigned = {}, activeNow = {};
    var contracts = contractStates(sources.contracts, resolver);
    Object.keys(contracts).forEach(function (cid) {
      var c = contracts[cid];
      if (!c.companyId || !c.signedOn || c.state === CONTRACT_MISTAKE) return;
      if (c.signedOn < KPI_START_DATE || c.signedOn >= weekEnd) return;
      everSigned[c.companyId] = true;
      if (c.state === CONTRACT_ACTIVE) activeNow[c.companyId] = true;
    });

    // 確認済みの相談がある会社のうち、今の流入ルートに④が無い会社(②: 累計には残し、要確認として数える)
    var routeOf = {};
    sources.companies.forEach(function (c) {
      var id = resolver.resolve(c.企業ID);
      if (id) routeOf[id] = (routeOf[id] || []).concat(Array.isArray(c.流入ルート) ? c.流入ルート : [str(c.流入ルート)]);
    });
    var routeCheck = Object.keys(first).filter(function (id) {
      return first[id] < weekEnd && !hasWorldRoute(routeOf[id] || []);
    }).length;

    row.状態 = WEEKLY_STATUS_OK;
    row.相談企業数_累計 = total;
    row.相談企業数_週内の新規 = newInWeek;
    row.掲載契約企業数_累計 = Object.keys(everSigned).length;
    row.掲載契約企業数_有効 = Object.keys(activeNow).length;
    row.確認待ちの面談数 = pendingMeetingIds(sources.history, sources.confirmations).length;
    row.流入経路の要確認数 = routeCheck;
    return { row: row, problems: resolver.problems.slice() };
  }

  /* 週次KPIタブへの書き込み計画。同じ週の行があれば上書き、無ければ足す。
   * 取得不能の行は、既に集計済みの値がある週を上書きしない(前の値を残す)。
   * 戻り値: { action: "update" | "append" | "keep", index } — index は existingRows の位置(append は -1)
   */
  function planWeeklyUpsert(existingRows, newRow) {
    var week = toDate(newRow && newRow.週の開始日);
    var index = -1;
    (existingRows || []).forEach(function (r, i) {
      if (toDate(r.週の開始日) === week) index = i;
    });
    if (index < 0) return { action: "append", index: -1 };
    if (str(newRow.状態) === WEEKLY_STATUS_UNAVAILABLE && str(existingRows[index].状態) === WEEKLY_STATUS_OK) {
      return { action: "keep", index: index };
    }
    return { action: "update", index: index };
  }

  var api = {
    KPI_START_DATE: KPI_START_DATE,
    KPI_TARGET_DATE: KPI_TARGET_DATE,
    KPI_TARGET_COMPANIES: KPI_TARGET_COMPANIES,
    WEEKLY_FIELDS: WEEKLY_FIELDS,
    toDate: toDate,
    weekStartMonday: weekStartMonday,
    previousWeekStart: previousWeekStart,
    buildIdResolver: buildIdResolver,
    countsAsConsultation: countsAsConsultation,
    pendingMeetingIds: pendingMeetingIds,
    buildWeeklyRow: buildWeeklyRow,
    planWeeklyUpsert: planWeeklyUpsert
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowWld02Kpi = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
