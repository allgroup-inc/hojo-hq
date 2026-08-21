/* アポ管理台帳 コアロジック(ビュー生成・重複判定・遅延対象抽出・変更差分)
 * ブラウザ相当のGAS(global.ApoCore)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/apo_kanri_core.test.mjs で検証される。
 *
 * すべて純関数。現在時刻・乱数は引数で注入する(テスト容易性と再現性のため)。
 * Sheetsの getValues() は日付・時刻セルをJSの Date で返すため、
 * normalizeDateString / normalizeTimeString で文字列に正規化してから比較する。
 */
(function (global) {
  "use strict";

  // 訪問枠が空くステータスの定義は schema.js に一本置き(2箇所に持つと必ずズレる)。
  // GASは読み込み順が保証されないため、モジュール評価時ではなく呼び出し時に引く。
  function slotFreed_(status) {
    return getApoSchema_().SLOT_FREED_STATUSES.indexOf(status) !== -1;
  }
  // 旧「再調整中」は共通語彙に無く「スケジュール調整中」へ統合された(2026-08-21 軸の裁定)
  var UNCONFIRMED_STATUSES = ["スケジュール調整中"];
  // 差分通知の対象外(システムが自動で書く列)
  var DIFF_EXCLUDED_COLUMNS = ["登録日時", "最終更新日時"];

  function pad2_(n) {
    return String(n).padStart(2, "0");
  }

  function normalizeDateString(value) {
    if (!value) return "";
    if (value instanceof Date) {
      return value.getFullYear() + "-" + pad2_(value.getMonth() + 1) + "-" + pad2_(value.getDate());
    }
    return String(value).trim();
  }

  function normalizeTimeString(value) {
    if (!value && value !== 0) return "";
    if (value instanceof Date) {
      return pad2_(value.getHours()) + ":" + pad2_(value.getMinutes());
    }
    var text = String(value).trim();
    var match = text.match(/^(\d{1,2}):(\d{2})/);
    if (!match) return text;
    return pad2_(Number(match[1])) + ":" + match[2];
  }

  function generateApoId(now, randomFn) {
    var random = typeof randomFn === "function" ? randomFn : function () { return 0; };
    var chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    var suffix = "";
    for (var i = 0; i < 4; i++) {
      suffix += chars.charAt(Math.floor(random() * chars.length) % chars.length);
    }
    return "APO-" + now.getFullYear() + pad2_(now.getMonth() + 1) + pad2_(now.getDate()) + "-" + suffix;
  }

  function timeToMinutes_(timeString) {
    var normalized = normalizeTimeString(timeString);
    var match = normalized.match(/^(\d{2}):(\d{2})$/);
    if (!match) return null;
    return Number(match[1]) * 60 + Number(match[2]);
  }

  function sortAppointments(list) {
    return (list || []).slice().sort(function (a, b) {
      var da = normalizeDateString(a["日付"]);
      var db = normalizeDateString(b["日付"]);
      if (da !== db) return da < db ? -1 : 1;
      var ta = normalizeTimeString(a["開始時刻"]);
      var tb = normalizeTimeString(b["開始時刻"]);
      if (ta !== tb) return ta < tb ? -1 : 1;
      var na = String(a["顧客名"] || "");
      var nb = String(b["顧客名"] || "");
      if (na === nb) return 0;
      return na < nb ? -1 : 1;
    });
  }

  // 壊れた行(日付なし等)はスキップして描画を継続する(1行の不正で全画面を落とさない)
  function validAppointments_(list) {
    return (list || []).filter(function (record) {
      return !!normalizeDateString(record["日付"]);
    });
  }

  function buildDayView(appointments, dateString, ownerFilter) {
    var items = sortAppointments(
      validAppointments_(appointments).filter(function (record) {
        if (normalizeDateString(record["日付"]) !== dateString) return false;
        if (ownerFilter && record["担当営業"] !== ownerFilter) return false;
        return true;
      })
    );
    var unconfirmed = items.filter(function (record) {
      return UNCONFIRMED_STATUSES.indexOf(record["ステータス"]) !== -1;
    }).length;
    return { items: items, summary: { total: items.length, unconfirmed: unconfirmed } };
  }

  function addDays_(dateString, days) {
    var parts = dateString.split("-").map(Number);
    var date = new Date(parts[0], parts[1] - 1, parts[2] + days);
    return normalizeDateString(date);
  }

  function buildWeekView(appointments, startDateString) {
    var valid = validAppointments_(appointments);
    var week = [];
    for (var i = 0; i < 7; i++) {
      var date = addDays_(startDateString, i);
      week.push({
        date: date,
        items: sortAppointments(valid.filter(function (record) {
          return normalizeDateString(record["日付"]) === date;
        }))
      });
    }
    return week;
  }

  /**
   * ダブルブッキング判定: 同一担当営業・同一日付で時間帯([開始, 開始+所要分))が交差する
   * アポを返す。差し戻し・対象外は「その時間は空く」ため対象外。
   * candidate 自身のアポIDは除外する(編集時に自分と重複判定しないため)。
   * 隣接(10:00-11:00 と 11:00-12:00)は重複ではない。
   */
  function detectOverlap(appointments, candidate) {
    var candidateStart = timeToMinutes_(candidate["開始時刻"]);
    if (candidateStart === null) return [];
    var candidateEnd = candidateStart + (Number(candidate["所要分"]) || 60);
    var candidateDate = normalizeDateString(candidate["日付"]);
    return (appointments || []).filter(function (record) {
      if (record["アポID"] === candidate["アポID"]) return false;
      if (record["担当営業"] !== candidate["担当営業"]) return false;
      if (normalizeDateString(record["日付"]) !== candidateDate) return false;
      if (slotFreed_(record["ステータス"])) return false;
      var start = timeToMinutes_(record["開始時刻"]);
      if (start === null) return false;
      var end = start + (Number(record["所要分"]) || 60);
      return start < candidateEnd && candidateStart < end;
    });
  }

  /**
   * 遅れそう連絡の通知対象: 当該営業の同日・fromTime以降のアポ(差し戻し・対象外を除く)。
   * 時刻の自動変更はしない(設計書 三名体制裁定①: 判断は人間・通知のみ)。
   */
  function buildDelayTargets(appointments, salesOwner, dateString, fromTimeString) {
    var fromMinutes = timeToMinutes_(fromTimeString);
    return sortAppointments((appointments || []).filter(function (record) {
      if (record["担当営業"] !== salesOwner) return false;
      if (normalizeDateString(record["日付"]) !== dateString) return false;
      if (slotFreed_(record["ステータス"])) return false;
      var start = timeToMinutes_(record["開始時刻"]);
      if (start === null) return false;
      return fromMinutes === null || start >= fromMinutes;
    }));
  }

  function getApoSchema_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./schema.js");
    }
    return global.ApoSchema;
  }

  /**
   * 変更履歴・変更通知用の差分文字列。値が変わった列だけを「列名: 旧→新」で連結する。
   * 走査対象は**スキーマのアポ予定列のみ**(タイムスタンプ2列を除く)。
   * クライアントのペイロードには confirmedOverlap 等の内部フラグが混ざるため、
   * キーの和集合を走査すると内部フラグが差分・Slack通知に漏れる(2026-08-17レビュー指摘#2)。
   */
  function buildChangeDiff(oldRecord, newRecord) {
    var keys = getApoSchema_().APPOINTMENT_HEADERS.filter(function (key) {
      return DIFF_EXCLUDED_COLUMNS.indexOf(key) === -1;
    });
    var parts = [];
    keys.forEach(function (key) {
      var oldValue = normalizeForDiff_(key, (oldRecord || {})[key]);
      var newValue = normalizeForDiff_(key, (newRecord || {})[key]);
      if (oldValue !== newValue) {
        parts.push(key + ": " + (oldValue || "(空)") + "→" + (newValue || "(空)"));
      }
    });
    return parts.join(" / ");
  }

  function normalizeForDiff_(key, value) {
    if (key === "日付") return normalizeDateString(value);
    if (key === "開始時刻") return normalizeTimeString(value);
    if (value === null || value === undefined) return "";
    return String(value);
  }

  // 埋まり状況の営業時間窓(9:00〜18:00 = 540分)。将来変えたくなったら設定タブ化を検討
  var WORKDAY_MINUTES = 540;
  // 「その時間が埋まっている」とみなすステータス(差し戻し・対象外だけが空き扱い)
  var BOOKED_STATUSES = ["スケジュール調整中", "アポ確定", "訪問済", "追客中", "申込", "成立", "保全中"];

  /**
   * 本日の埋まり状況: 営業ごとの予約済み分数・件数・埋まり率(営業時間窓に対する割合)。
   * アポゼロの営業も0%で返し、全員の稼働が一目で見えるようにする。
   * ※評価目的では使わない(v1.1三名体制裁定)。
   */
  function buildFillStats(appointments, dateString, salesStaffNames) {
    var byOwner = {};
    (salesStaffNames || []).forEach(function (name) {
      byOwner[name] = { owner: name, bookedMinutes: 0, count: 0 };
    });
    var totalMinutes = 0;
    var totalCount = 0;
    validAppointments_(appointments).forEach(function (record) {
      if (normalizeDateString(record["日付"]) !== dateString) return;
      if (BOOKED_STATUSES.indexOf(record["ステータス"]) === -1) return;
      var owner = record["担当営業"];
      if (!byOwner[owner]) byOwner[owner] = { owner: owner, bookedMinutes: 0, count: 0 };
      var minutes = Number(record["所要分"]) || 60;
      byOwner[owner].bookedMinutes += minutes;
      byOwner[owner].count += 1;
      totalMinutes += minutes;
      totalCount += 1;
    });
    var order = (salesStaffNames || []).slice();
    Object.keys(byOwner).forEach(function (name) {
      if (order.indexOf(name) === -1) order.push(name);
    });
    var owners = order.map(function (name) {
      var entry = byOwner[name];
      entry.ratio = Math.min(1, entry.bookedMinutes / WORKDAY_MINUTES);
      return entry;
    });
    return {
      owners: owners,
      total: { bookedMinutes: totalMinutes, count: totalCount }
    };
  }

  // 訪問に至ったとみなすステータス / 申込に至ったとみなすステータス。
  // ★定義は軸が一元管理する(2026-08-21 裁定②:「❷が独自に数えないでください」)。
  //   ❷と❸が別々に数えると必ずズレ、どちらが正しいかの議論になって両方信用されなくなる。
  //   下記は軸から正式定義が届くまでの**暫定**。届いたら差し替える(画面にも暫定と明示)。
  var VISITED_STATUSES = ["訪問済", "追客中", "申込", "成立", "保全中"];
  var SIGNED_STATUSES = ["申込", "成立", "保全中"];

  /**
   * 転換ファネル(チーム全体のみ。営業マン別は評価誤用リスクのため見送り):
   * - 母数 = 結果が出たアポ(訪問に至った + 差し戻し)。調整中・確定・対象外は除外
   * - 訪問実施率 = 訪問に至った ÷ 母数 / 申込率 = 申込に至った ÷ 訪問に至った
   * 母数0のときは率をnullで返す(0%や100%と断定しない。表示側は「—」にする)。
   */
  function buildConversionStats(appointments, options) {
    var sinceDate = (options || {}).sinceDate || "";
    var concluded = 0;
    var completed = 0;
    var signups = 0;
    validAppointments_(appointments).forEach(function (record) {
      if (sinceDate && normalizeDateString(record["日付"]) < sinceDate) return;
      var status = record["ステータス"];
      var isCompleted = VISITED_STATUSES.indexOf(status) !== -1;
      var isReturned = status === "差し戻し";
      if (!isCompleted && !isReturned) return;
      concluded += 1;
      if (isCompleted) completed += 1;
      if (SIGNED_STATUSES.indexOf(status) !== -1) signups += 1;
    });
    return {
      concluded: concluded,
      completed: completed,
      signups: signups,
      visitRate: concluded > 0 ? completed / concluded : null,
      signupRate: completed > 0 ? signups / completed : null
    };
  }

  /**
   * 内訳別の申込率を作る共通処理。dimensionKey の値ごとに
   * 訪問に至ったアポを母数、申込に至ったアポを分子として率を出す。
   * 母数0は率null(0%や100%と断定しない)。定義されていない値の行は無視する。
   */
  function buildBreakdownStats_(appointments, options, dimensionKey, order, labelKey) {
    var sinceDate = (options || {}).sinceDate || "";
    var byValue = {};
    order.forEach(function (value) {
      var entry = { completed: 0, signups: 0 };
      entry[labelKey] = value;
      byValue[value] = entry;
    });
    validAppointments_(appointments).forEach(function (record) {
      if (sinceDate && normalizeDateString(record["日付"]) < sinceDate) return;
      var status = record["ステータス"];
      if (VISITED_STATUSES.indexOf(status) === -1) return;
      var entry = byValue[record[dimensionKey]];
      if (!entry) return;
      entry.completed += 1;
      if (SIGNED_STATUSES.indexOf(status) !== -1) entry.signups += 1;
    });
    return order.map(function (value) {
      var entry = byValue[value];
      entry.rate = entry.completed > 0 ? entry.signups / entry.completed : null;
      return entry;
    });
  }

  /**
   * 温度感別の申込率(高・中・低の順で固定)。チーム全体のみ・個人別は出さない。
   * 母数 = その温度感で訪問に至ったアポ。母数0は率null(断定しない)。
   * 「どんなアポを取れば決まるか」をアポ入れ側の改善につなげるための指標
   * (2026-08-14 小柳さん採用)。
   */
  function buildTemperatureStats(appointments, options) {
    return buildBreakdownStats_(appointments, options, "温度感",
      ["高", "中", "低"], "temperature");
  }

  /**
   * 代打候補(GPSレス版・2026-08-14 小柳さん決裁): アポが差し戻しになった枠に対し、
   * その時間帯が空いている営業を「同日の直前・直後のアポ(時刻・場所)」付きで返す。
   * 位置情報は一切取得しない。どの候補が近いかの判断は、前後の場所を見た人間が行う。
   * 並び順: 前後にアポがある(現場に出ている)営業を先頭に。元の担当営業は候補外。
   */
  function buildSubstituteCandidates(appointments, returnedApo, salesStaffNames) {
    var dateString = normalizeDateString(returnedApo["日付"]);
    var windowStart = timeToMinutes_(returnedApo["開始時刻"]);
    if (windowStart === null) return [];
    var windowEnd = windowStart + (Number(returnedApo["所要分"]) || 60);

    var sameDayActive = validAppointments_(appointments).filter(function (record) {
      if (record["アポID"] === returnedApo["アポID"]) return false;
      if (normalizeDateString(record["日付"]) !== dateString) return false;
      return BOOKED_STATUSES.indexOf(record["ステータス"]) !== -1;
    });

    var candidates = [];
    (salesStaffNames || []).forEach(function (owner) {
      if (owner === returnedApo["担当営業"]) return;
      var mine = sameDayActive.filter(function (record) { return record["担当営業"] === owner; });
      var isBusy = mine.some(function (record) {
        var start = timeToMinutes_(record["開始時刻"]);
        if (start === null) return false;
        var end = start + (Number(record["所要分"]) || 60);
        return start < windowEnd && windowStart < end;
      });
      if (isBusy) return;
      var before = null;
      var after = null;
      mine.forEach(function (record) {
        var start = timeToMinutes_(record["開始時刻"]);
        if (start === null) return;
        if (start < windowStart) {
          if (!before || start > timeToMinutes_(before["開始時刻"])) before = record;
        } else {
          if (!after || start < timeToMinutes_(after["開始時刻"])) after = record;
        }
      });
      candidates.push({ owner: owner, before: before, after: after });
    });

    return candidates.sort(function (a, b) {
      var aField = (a.before || a.after) ? 0 : 1;
      var bField = (b.before || b.after) ? 0 : 1;
      return aField - bField;
    });
  }

  // 営業時間の窓。空き枠の計算と埋まり率の分母に使う
  var WORKDAY_START = "09:00";
  var WORKDAY_END = "18:00";
  // 「まもなく訪問日」とみなす日数。当日+2日先までを手当ての射程にする
  // (それ以上先を出すと毎日ずっと出続けて、見なくなる)
  var IMMINENT_DAYS = 2;
  // 訪問終了から何分過ぎたら「結果が入っていない」と数えるか。
  // 訪問直後に押させると現場の手間になるので、終わって一息つく余裕を見る
  var RESULT_GRACE_MINUTES = 90;
  // 結果待ちを何日さかのぼって出すか。無制限にすると初日から壁のような一覧になり、
  // 「多すぎて見ない」= 埋もれるのと同じ状態になる
  var RESULT_LOOKBACK_DAYS = 14;

  function diffDays_(fromDateString, toDateString) {
    var a = fromDateString.split("-").map(Number);
    var b = toDateString.split("-").map(Number);
    var ms = new Date(b[0], b[1] - 1, b[2]) - new Date(a[0], a[1] - 1, a[2]);
    return Math.round(ms / 86400000);
  }

  /**
   * 「今日やること」= 手当てが要るアポの一覧(2026-08-21 追加)。
   *
   * 新しい入力は一切増やさず、すでにある列だけから導く。放置されているものを人の記憶に
   * 頼らず浮上させることが目的(共通の前提【4】)。
   * options: { today: "yyyy-MM-dd", now: "HH:mm", owner: 絞り込む担当営業名 }
   *
   * 種別と並び順(緊急な順):
   *   result  結果が入っていない(訪問したのか差し戻しか分からない = 最も埋もれる)
   *   overlap 同じ営業の時間が重なっている
   *   unconfirmed 訪問日が迫っているのにスケジュール調整中のまま
   *   place   訪問・来店なのに行き先が空のまま訪問日が迫っている
   *   owner   担当営業が空(通知が誰にも飛ばない)
   */
  function buildAttentionList(appointments, options) {
    var opts = options || {};
    var today = opts.today || "";
    var nowMinutes = timeToMinutes_(opts.now || "23:59");
    /* シート全体ではなく、手当てが要りうる期間だけを見る。台帳は日々増え続けるので、
       全行を毎回走査すると画面を開くたびに遅くなる(共通の前提【6】待たせない)。 */
    var live = validAppointments_(appointments).filter(function (record) {
      if (slotFreed_(record["ステータス"])) return false;
      if (opts.owner && record["担当営業"] !== opts.owner) return false;
      if (!today) return true;
      var days = diffDays_(today, normalizeDateString(record["日付"]));
      return days >= -RESULT_LOOKBACK_DAYS;
    });
    // 重なりの照合は総当たりになるため、まだ手当てできる未来分だけに絞ってから行う
    var upcoming = live.filter(function (record) {
      return !today || diffDays_(today, normalizeDateString(record["日付"])) >= 0;
    });

    var items = [];
    var seenOverlap = {};
    live.forEach(function (record) {
      var date = normalizeDateString(record["日付"]);
      var days = today ? diffDays_(today, date) : 0;
      var status = record["ステータス"];
      var start = timeToMinutes_(record["開始時刻"]);
      var end = start === null ? null : start + (Number(record["所要分"]) || 60);

      // 1. 結果が入っていない(訪問時間が終わって猶予も過ぎたのに、まだ❷の持ち場のまま)
      var isPending = ["スケジュール調整中", "アポ確定"].indexOf(status) !== -1;
      var elapsed = days < 0 || (days === 0 && end !== null &&
        nowMinutes >= end + RESULT_GRACE_MINUTES);
      if (isPending && elapsed && days >= -RESULT_LOOKBACK_DAYS) {
        items.push({ kind: "result", apo: record,
          reason: days === 0 ? "本日の訪問時間が終わっています"
            : (-days) + "日前のアポです" });
        return; // 1件につき1つだけ出す。同じ行が何度も並ぶと一覧が読めなくなる
      }
      if (days < 0) return; // 過去のアポで結果待ち以外は手当てのしようがない

      // 2. 担当営業が空(通知先が決まらない。フォームでは必須だがシート直接編集で起きうる)
      if (!record["担当営業"]) {
        items.push({ kind: "owner", apo: record, reason: "通知が誰にも届きません" });
        return;
      }
      // 3. 訪問日が迫っているのに未確定
      if (status === "スケジュール調整中" && days <= IMMINENT_DAYS) {
        items.push({ kind: "unconfirmed", apo: record,
          reason: days === 0 ? "本日です" : days + "日後です" });
        return;
      }
      // 4. 行き先が空(オンラインは場所が要らないので対象外)
      if (record["形式"] !== "オンライン" && !record["場所またはURL"] && days <= IMMINENT_DAYS) {
        items.push({ kind: "place", apo: record,
          reason: days === 0 ? "本日なのに行き先が空です" : "行き先が空です" });
      }
    });

    // 5. 時間の重なり(両方のアポを1組として1回だけ出す)。
    // すでに始まってしまった重なりは手当てのしようがないので出さない
    // (出すと「もう終わったこと」で一覧が埋まり、直せるものが埋もれる)
    upcoming.forEach(function (record) {
      var recordDays = today ? diffDays_(today, normalizeDateString(record["日付"])) : 0;
      var recordStart = timeToMinutes_(record["開始時刻"]);
      if (recordDays === 0 && recordStart !== null && recordStart <= nowMinutes) return;
      detectOverlap(upcoming, record).forEach(function (other) {
        var pair = [record["アポID"], other["アポID"]].sort().join("|");
        if (seenOverlap[pair]) return;
        seenOverlap[pair] = true;
        items.push({ kind: "overlap", apo: record,
          reason: other["開始時刻"] + " " + other["顧客名"] + " と重なっています" });
      });
    });

    var order = { result: 0, overlap: 1, unconfirmed: 2, place: 3, owner: 4 };
    return items.sort(function (a, b) {
      if (order[a.kind] !== order[b.kind]) return order[a.kind] - order[b.kind];
      var da = normalizeDateString(a.apo["日付"]);
      var db = normalizeDateString(b.apo["日付"]);
      if (da !== db) return da < db ? -1 : 1;
      return normalizeTimeString(a.apo["開始時刻"]) < normalizeTimeString(b.apo["開始時刻"]) ? -1 : 1;
    });
  }

  /**
   * 埋まっていない訪問枠(2026-08-21 追加)。営業ごとに、営業時間の中で
   * minGapMinutes 以上つながっている空き時間を返す。アポ入れ担当が
   * 「誰の・いつなら入れられるか」を探さずに見られるようにするためのもの。
   * options: { days: 何日分, minGapMinutes: 何分以上を空きとみなすか }
   */
  function buildOpenSlots(appointments, startDateString, salesStaffNames, options) {
    var opts = options || {};
    var days = opts.days || 7;
    var minGap = opts.minGapMinutes || 90;
    var dayStart = timeToMinutes_(WORKDAY_START);
    var dayEnd = timeToMinutes_(WORKDAY_END);
    var booked = validAppointments_(appointments).filter(function (record) {
      return BOOKED_STATUSES.indexOf(record["ステータス"]) !== -1;
    });

    var result = [];
    for (var d = 0; d < days; d++) {
      var date = addDays_(startDateString, d);
      var slots = [];
      (salesStaffNames || []).forEach(function (owner) {
        var spans = booked.filter(function (record) {
          return record["担当営業"] === owner && normalizeDateString(record["日付"]) === date;
        }).map(function (record) {
          var start = timeToMinutes_(record["開始時刻"]);
          return start === null ? null
            : { start: start, end: start + (Number(record["所要分"]) || 60) };
        }).filter(Boolean).sort(function (a, b) { return a.start - b.start; });

        var cursor = dayStart;
        spans.forEach(function (span) {
          if (span.start - cursor >= minGap) {
            slots.push({ owner: owner, from: minutesToTime_(cursor), to: minutesToTime_(span.start),
              minutes: span.start - cursor, allDay: false });
          }
          cursor = Math.max(cursor, span.end);
        });
        if (dayEnd - cursor >= minGap) {
          slots.push({ owner: owner, from: minutesToTime_(cursor), to: minutesToTime_(dayEnd),
            minutes: dayEnd - cursor, allDay: cursor === dayStart });
        }
      });
      // 全員が終日空いている日は、人数分のチップを並べても情報が増えない。
      // 1行にたたむ(見るものが多い日とそうでない日に差が付かないと、読み飛ばされる)
      var names = (salesStaffNames || []);
      var allOpen = names.length > 0 && names.every(function (owner) {
        return slots.some(function (slot) { return slot.owner === owner && slot.allDay; });
      });
      result.push({ date: date, slots: slots, allOpen: allOpen });
    }
    return result;
  }

  function minutesToTime_(minutes) {
    return pad2_(Math.floor(minutes / 60)) + ":" + pad2_(minutes % 60);
  }

  /**
   * 本日の全体表(2026-08-21 追加)。営業ごとに、営業時間を横軸にした帯を返す。
   * 誰がいつ動いていて、どこが空いているかを一目で見るためのもの。
   * 位置と幅は営業時間窓に対する%で返し、描画側は数字を持たない。
   * options: { now: "HH:mm" }
   */
  function buildDayTimeline(appointments, dateString, salesStaffNames, options) {
    var opts = options || {};
    var dayStart = timeToMinutes_(WORKDAY_START);
    var dayEnd = timeToMinutes_(WORKDAY_END);
    var span = dayEnd - dayStart;
    var nowMinutes = timeToMinutes_(opts.now || "");

    var today = validAppointments_(appointments).filter(function (record) {
      return normalizeDateString(record["日付"]) === dateString &&
        record["ステータス"] !== "対象外";
    });

    var names = (salesStaffNames || []).slice();
    today.forEach(function (record) {
      var owner = record["担当営業"] || "(担当なし)";
      if (names.indexOf(owner) === -1) names.push(owner);
    });

    var rows = names.map(function (owner) {
      var mine = sortAppointments(today.filter(function (record) {
        return (record["担当営業"] || "(担当なし)") === owner;
      }));
      var bars = mine.map(function (record) {
        var start = timeToMinutes_(record["開始時刻"]);
        if (start === null) return null;
        var end = start + (Number(record["所要分"]) || 60);
        // 営業時間の外にはみ出すアポも、端で切って必ず見えるようにする
        var from = Math.max(dayStart, Math.min(start, dayEnd));
        var to = Math.max(dayStart, Math.min(end, dayEnd));
        return {
          apoId: record["アポID"],
          customer: record["顧客名"],
          time: normalizeTimeString(record["開始時刻"]),
          status: record["ステータス"],
          outcome: classifyOutcome_(record, dateString, nowMinutes),
          left: ((from - dayStart) / span) * 100,
          width: Math.max(((to - from) / span) * 100, 2)
        };
      }).filter(Boolean);
      return { owner: owner, bars: bars };
    });

    var hours = [];
    for (var m = dayStart; m <= dayEnd; m += 60) {
      hours.push({ label: minutesToTime_(m), left: ((m - dayStart) / span) * 100 });
    }
    return {
      date: dateString,
      hours: hours,
      rows: rows,
      nowLeft: (nowMinutes !== null && nowMinutes >= dayStart && nowMinutes <= dayEnd)
        ? ((nowMinutes - dayStart) / span) * 100 : null
    };
  }

  /* 1件のアポが「今どういう状態か」を5つに束ねる。
   * 訪問済/申込の判定は転換ファネルと同じ定数を使う(❷が独自に数えないため。
   * 2つ持つと必ずズレて、どちらが正しいかの議論になる)。 */
  function classifyOutcome_(record, dateString, nowMinutes) {
    var status = record["ステータス"];
    if (SIGNED_STATUSES.indexOf(status) !== -1) return "signed";
    if (VISITED_STATUSES.indexOf(status) !== -1) return "visited";
    if (status === "差し戻し") return "returned";
    var start = timeToMinutes_(record["開始時刻"]);
    var end = start === null ? null : start + (Number(record["所要分"]) || 60);
    if (nowMinutes !== null && end !== null && nowMinutes >= end + RESULT_GRACE_MINUTES) {
      return "pending";
    }
    return "ahead";
  }

  var OUTCOME_KEYS = ["ahead", "pending", "visited", "signed", "returned"];

  /**
   * 本日の結果集計(2026-08-21 追加)。営業ごとと全体の件数を返す。
   * これから / 結果待ち / 訪問済 / 申込 / 差し戻し の5つ。
   * ※評価目的では使わない(v1.1三名体制裁定・軸の裁定③と同じ理由)。
   */
  function buildDayResultStats(appointments, dateString, salesStaffNames, options) {
    var nowMinutes = timeToMinutes_((options || {}).now || "");
    var today = validAppointments_(appointments).filter(function (record) {
      return normalizeDateString(record["日付"]) === dateString &&
        record["ステータス"] !== "対象外";
    });
    var names = (salesStaffNames || []).slice();
    today.forEach(function (record) {
      var owner = record["担当営業"] || "(担当なし)";
      if (names.indexOf(owner) === -1) names.push(owner);
    });

    function emptyCounts_() {
      var counts = { total: 0 };
      OUTCOME_KEYS.forEach(function (key) { counts[key] = 0; });
      return counts;
    }
    var totals = emptyCounts_();
    var owners = names.map(function (owner) {
      var counts = emptyCounts_();
      today.forEach(function (record) {
        if ((record["担当営業"] || "(担当なし)") !== owner) return;
        var outcome = classifyOutcome_(record, dateString, nowMinutes);
        counts[outcome] += 1;
        counts.total += 1;
        totals[outcome] += 1;
        totals.total += 1;
      });
      counts.owner = owner;
      return counts;
    });
    return { date: dateString, owners: owners, totals: totals };
  }

  var api = {
    generateApoId: generateApoId,
    buildDayTimeline: buildDayTimeline,
    buildDayResultStats: buildDayResultStats,
    OUTCOME_KEYS: OUTCOME_KEYS,
    buildAttentionList: buildAttentionList,
    buildOpenSlots: buildOpenSlots,
    normalizeDateString: normalizeDateString,
    normalizeTimeString: normalizeTimeString,
    sortAppointments: sortAppointments,
    buildDayView: buildDayView,
    buildWeekView: buildWeekView,
    detectOverlap: detectOverlap,
    buildDelayTargets: buildDelayTargets,
    buildChangeDiff: buildChangeDiff,
    buildFillStats: buildFillStats,
    buildConversionStats: buildConversionStats,
    buildTemperatureStats: buildTemperatureStats,
    buildSubstituteCandidates: buildSubstituteCandidates
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.ApoCore = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
