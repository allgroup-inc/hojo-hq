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
 * - 掲載契約は、解除・取消があっても累計に残す。今も有効な数は別に数える。「誤登録」は外す
 * - 2026-10-04 より前に成立した掲載契約は「参考実績」として別の列に数え、正式な累計には足さない(11/4 確定)
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

  // 掲載契約の状態。「誤登録」は基本ルール「誤登録・重複は理由と訂正履歴を残して修正できる」のために
  // 足した状態(2026-11-04 小柳さん確定: 誤登録は累計から外し、取消は累計に残す)。
  var CONTRACT_ACTIVE = "有効";
  var CONTRACT_MISTAKE = "誤登録";

  var WEEKLY_STATUS_OK = "集計済み";
  var WEEKLY_STATUS_UNAVAILABLE = "取得不能";

  var WEEKLY_FIELDS = [
    "週の開始日", "集計日時", "状態",
    "相談企業数_累計", "相談企業数_週内の新規",
    "掲載契約企業数_累計", "掲載契約企業数_有効", "掲載契約企業数_参考_10月4日より前",
    "確認待ちの面談数", "流入経路の要確認数", "実行ID",
    // 2026-11-06 §9-3: 参考の数字(正式KPIは上の相談企業数・掲載契約企業数)。列は末尾に足す
    "問い合わせ企業数_累計", "問い合わせ企業数_週内の新規",
    "問い合わせから相談の割合", "相談から掲載契約の割合",
    "目標までの残り社数", "目標日までの残り週数", "必要な週あたりの相談数"
  ];

  // 問い合わせに数える対応履歴の種別(§9-2。電話・LINEだけの問い合わせも、ここでは数える。正式KPIの相談とは別)
  var INQUIRY_TYPES = ["入電", "返信", "資料請求", "面談実施"];
  // 割合は母数が少ないと大きく揺れるため、この数より少なければ出さない(§9-3)
  var RATIO_MIN_BASE = 10;
  var NO_VALUE = "—";

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
      // 日本時間の日付にそろえる(2026-11-06: 動く場所の時刻設定に左右されないようにする。
      // GASは日本時間、テストや他の環境はUTCのことがあり、0時前後の面談が別の週に入るのを防ぐ)
      var jst = new Date(v.getTime() + 9 * 60 * 60 * 1000);
      return jst.getUTCFullYear() + "-" + pad2(jst.getUTCMonth() + 1) + "-" + pad2(jst.getUTCDate());
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

  /* 面談確認記録のうち、今有効な行だけを返す(2026-11-06)。
   * 同じ面談(元の履歴ID)を確かめ直したときは、取消でない行のうち最も新しい判定(確認日時、同じなら後の行)を正とする。
   * 「対象外」→「確認済み」にも、「確認済み」→「対象外」にも、行を足すだけで判定をやり直せる。
   * 元の履歴IDが空の行(台帳に無い面談を直接記録したもの)は、1行ずつ別の面談として扱う */
  function effectiveConfirmations(confirmRows) {
    var latest = {}, direct = [];
    (confirmRows || []).forEach(function (row, i) {
      if (isCancelled(row)) return;
      var hid = str(row.元の履歴ID);
      if (!hid) { direct.push(row); return; }
      var at = str(row.確認日時);
      var cur = latest[hid];
      if (!cur || at > cur.at || (at === cur.at && i > cur.i)) latest[hid] = { row: row, at: at, i: i };
    });
    return direct.concat(Object.keys(latest).map(function (k) { return latest[k].row; }));
  }

  // 相談企業(統合後の企業ID → 最初の確認済み面談日)
  function consultationFirstDates(confirmRows, resolver) {
    var first = {};
    effectiveConfirmations(confirmRows).forEach(function (row) {
      if (!countsAsConsultation(row)) return;
      var id = resolver.resolve(row.企業ID);
      if (!id) return;
      var d = toDate(row.面談日);
      if (!first[id] || d < first[id]) first[id] = d;
    });
    return first;
  }

  // 掲載契約記録(状態が変わるたびに行を足す)。契約IDごとに最後の行が今の状態。
  // 状態を変えるたびに行を足す(§2-2)。今の状態は「状態が変わった日」(無ければ契約成立日)が最も新しい行で決める。
  // 同じ日なら、後の行を新しいとみなす(2026-11-06: 行の並び順だけで決めていたのを直した)
  function contractStates(contractRows, resolver) {
    var byContract = {};
    var ordered = (contractRows || []).map(function (row, i) {
      return { row: row, i: i, on: toDate(row.状態が変わった日) || toDate(row.契約成立日) || "" };
    }).sort(function (a, b) {
      if (a.on !== b.on) return a.on < b.on ? -1 : 1;
      return a.i - b.i;
    });
    ordered.forEach(function (item) {
      var row = item.row, i = item.i;
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

    var everSigned = {}, activeNow = {}, beforeStart = {};
    var contracts = contractStates(sources.contracts, resolver);
    Object.keys(contracts).forEach(function (cid) {
      var c = contracts[cid];
      if (!c.companyId || !c.signedOn || c.state === CONTRACT_MISTAKE) return;
      if (c.signedOn >= weekEnd) return;
      if (c.signedOn < KPI_START_DATE) { beforeStart[c.companyId] = true; return; }
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
    row.掲載契約企業数_参考_10月4日より前 = Object.keys(beforeStart).filter(function (id) { return !everSigned[id]; }).length;
    row.確認待ちの面談数 = pendingMeetingIds(sources.history, sources.confirmations).length;
    row.流入経路の要確認数 = routeCheck;

    // §9-3 参考の数字(問い合わせ・割合・目標までの残り)
    var inquiries = inquiryFirstDates(sources.history, routeOf, resolver);
    var inquiryTotal = 0, inquiryNew = 0;
    Object.keys(inquiries).forEach(function (id) {
      if (inquiries[id] < weekEnd) inquiryTotal++;
      if (inquiries[id] >= weekStart && inquiries[id] < weekEnd) inquiryNew++;
    });
    row.問い合わせ企業数_累計 = inquiryTotal;
    row.問い合わせ企業数_週内の新規 = inquiryNew;
    row.問い合わせから相談の割合 = ratio(total, inquiryTotal);
    row.相談から掲載契約の割合 = ratio(row.掲載契約企業数_累計, total);
    var pace = goalPace(total, weekEnd);
    row.目標までの残り社数 = pace.remaining;
    row.目標日までの残り週数 = pace.weeks;
    row.必要な週あたりの相談数 = pace.perWeek;
    return { row: row, problems: resolver.problems.slice() };
  }

  /* 問い合わせ企業(統合後の企業ID → 最初の問い合わせの日)。
   * 流入ルート④が付いた会社(統合前のIDに付いていても統合後へまとめる)のうち、
   * 対応履歴ログに入電・返信・資料請求・面談実施のどれかがある会社。集計開始日(10/4)より前の記録は数えない */
  function inquiryFirstDates(historyRows, routeOf, resolver) {
    var first = {};
    (historyRows || []).forEach(function (h) {
      if (INQUIRY_TYPES.indexOf(str(h.種別)) < 0) return;
      var id = resolver.resolve(h.企業ID);
      var d = toDate(h.日付);
      if (!id || !d || d < KPI_START_DATE) return;
      if (!hasWorldRoute(routeOf[id] || [])) return;
      if (!first[id] || d < first[id]) first[id] = d;
    });
    return first;
  }

  // 割合(%・小数1桁)。母数が RATIO_MIN_BASE より少なければ出さない
  function ratio(numerator, denominator) {
    if (!(denominator >= RATIO_MIN_BASE)) return NO_VALUE;
    return Math.round((numerator / denominator) * 1000) / 10;
  }

  /* 100社の目標までの残り。週の終わり(次の月曜)から目標日(2027-04-04)までを週で数え(端数は1週)、
   * 残りの社数をその週数で割って、1週あたりに必要な相談の数(切り上げ)を出す。
   * 目標に届いていれば残り0・必要0。目標日を過ぎていれば週数0・必要は「—」 */
  function goalPace(total, weekEnd) {
    var remaining = Math.max(KPI_TARGET_COMPANIES - total, 0);
    var days = (Date.parse(KPI_TARGET_DATE + "T00:00:00Z") - Date.parse(weekEnd + "T00:00:00Z")) / 86400000 + 1;
    var weeks = days > 0 ? Math.ceil(days / 7) : 0;
    var perWeek = remaining === 0 ? 0 : (weeks > 0 ? Math.ceil(remaining / weeks) : NO_VALUE);
    return { remaining: remaining, weeks: weeks, perWeek: perWeek };
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
    planWeeklyUpsert: planWeeklyUpsert,
    INQUIRY_TYPES: INQUIRY_TYPES,
    RATIO_MIN_BASE: RATIO_MIN_BASE,
    effectiveConfirmations: effectiveConfirmations,
    ratio: ratio,
    goalPace: goalPace
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowWld02Kpi = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
