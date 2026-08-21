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

  // ❶へ返却したもの。枠は空く
  var RETURNED_STATUS = "差し戻し";
  // 日程がまだ固まっていないもの(旧「予定」「再調整中」)
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
   * アポを返す。
   * **枠を押さえているかはステータスではなく「日時が入っているか」で判定する**
   * (議事_20260821: 共通語彙は❷に2値しか許さないため、旧「予定/再調整中」の
   *  押さえる/押さえないの違いを日時の有無で表す)。差し戻しは❶へ返却済みなので常に空く。
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
      if (record["ステータス"] === RETURNED_STATUS) return false;
      var start = timeToMinutes_(record["開始時刻"]);
      if (start === null) return false;
      var end = start + (Number(record["所要分"]) || 60);
      return start < candidateEnd && candidateStart < end;
    });
  }

  /**
   * 遅れそう連絡の通知対象: 当該営業の同日・fromTime以降のアポ(差し戻し済みは除く)。
   * 時刻の自動変更はしない(設計書 三名体制裁定①: 判断は人間・通知のみ)。
   */
  function buildDelayTargets(appointments, salesOwner, dateString, fromTimeString) {
    var fromMinutes = timeToMinutes_(fromTimeString);
    return sortAppointments((appointments || []).filter(function (record) {
      if (record["担当営業"] !== salesOwner) return false;
      if (normalizeDateString(record["日付"]) !== dateString) return false;
      if (record["ステータス"] === RETURNED_STATUS) return false;
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
  // 「その時間が埋まっている」= 日時が入っていて、まだ❶へ差し戻していないもの。
  // ステータスでは判定しない(detectOverlap と同じ考え方)。
  function isBooked_(record) {
    if (record["ステータス"] === RETURNED_STATUS) return false;
    return timeToMinutes_(record["開始時刻"]) !== null;
  }

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
      if (!isBooked_(record)) return;
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

  /**
   * 転換ファネル(チーム全体のみ。営業マン別は評価誤用リスクのため見送り):
   * - 母数 = 結果が出たアポ(訪問済+申込+キャンセル2種)。予定・確定・再調整中は除外
   * - 訪問実施率 = (訪問済+申込) ÷ 母数 / 申込率 = 申込 ÷ (訪問済+申込)
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
      var isCompleted = status === "訪問済" || status === "申込";
      var isCancelled = status === RETURNED_STATUS;
      if (!isCompleted && !isCancelled) return;
      concluded += 1;
      if (isCompleted) completed += 1;
      if (status === "申込") signups += 1;
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
   * 訪問実施(訪問済+申込)を母数、申込を分子として率を出す。
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
      if (status !== "訪問済" && status !== "申込") return;
      var entry = byValue[record[dimensionKey]];
      if (!entry) return;
      entry.completed += 1;
      if (status === "申込") entry.signups += 1;
    });
    return order.map(function (value) {
      var entry = byValue[value];
      entry.rate = entry.completed > 0 ? entry.signups / entry.completed : null;
      return entry;
    });
  }

  /**
   * アポ種別(再訪/新規紹介/新規ご家族/新規その他)別の申込率。
   * 再訪と新規は決まり方が違うため、混ぜた平均では改善判断ができない
   * (2026-08-19 小柳さん決裁)。チーム全体のみ・個人別は出さない。
   */
  function buildKindStats(appointments, options) {
    return buildBreakdownStats_(appointments, options, "アポ種別",
      getApoSchema_().APPOINTMENT_KINDS, "kind");
  }

  /**
   * 温度感別の申込率(高・中・低の順で固定)。チーム全体のみ・個人別は出さない。
   * 母数 = その温度感の訪問実施(訪問済+申込)。母数0は率null(断定しない)。
   * 「どんなアポを取れば決まるか」をアポ入れ側の改善につなげるための指標
   * (2026-08-14 小柳さん採用)。
   */
  function buildTemperatureStats(appointments, options) {
    return buildBreakdownStats_(appointments, options, "温度感",
      ["高", "中", "低"], "temperature");
  }

  /**
   * 代打候補(GPSレス版・2026-08-14 小柳さん決裁): アポがキャンセルになった枠に対し、
   * その時間帯が空いている営業を「同日の直前・直後のアポ(時刻・場所)」付きで返す。
   * 位置情報は一切取得しない。どの候補が近いかの判断は、前後の場所を見た人間が行う。
   * 並び順: 前後にアポがある(現場に出ている)営業を先頭に。元の担当営業は候補外。
   */
  function buildSubstituteCandidates(appointments, cancelledApo, salesStaffNames) {
    var dateString = normalizeDateString(cancelledApo["日付"]);
    var windowStart = timeToMinutes_(cancelledApo["開始時刻"]);
    if (windowStart === null) return [];
    var windowEnd = windowStart + (Number(cancelledApo["所要分"]) || 60);

    var sameDayActive = validAppointments_(appointments).filter(function (record) {
      if (record["アポID"] === cancelledApo["アポID"]) return false;
      if (normalizeDateString(record["日付"]) !== dateString) return false;
      return isBooked_(record);
    });

    var candidates = [];
    (salesStaffNames || []).forEach(function (owner) {
      if (owner === cancelledApo["担当営業"]) return;
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

  var api = {
    generateApoId: generateApoId,
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
    buildKindStats: buildKindStats,
    buildSubstituteCandidates: buildSubstituteCandidates
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.ApoCore = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
