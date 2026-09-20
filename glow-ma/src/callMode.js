/* GLOW企業リレーション台帳 連続架電モード(コールモード)の純ロジック(v1.7.0)
 * ブラウザ相当のGAS(global.GlowCallMode)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_callMode.test.mjs で検証される。
 *
 * 役割: (1)架電リストの並び順・除外規則 (2)架電結果→対応履歴の種別・次回アクションの
 * 変換規則。AdminRunner.gs の getCallQueue / recordCallOutcome がこれを呼ぶ。
 *
 * 日数ルール(不在→3営業日後、時期が合わない→6ヶ月後)はCALL_RULESに集約する。
 * 変更は運用調整として可能だが、ルール変更は議事を残すこと
 * (docs/議事_20260903_連続架電モード.md)。
 */
(function (global) {
  "use strict";

  function getGlowAlerting_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./alerting.js");
    }
    return global.GlowAlerting;
  }

  var CALL_RULES = {
    // 不在時の再架電までの営業日数(土日を除く)
    RETRY_BUSINESS_DAYS: 3,
    // 「時期が合わない」見送りを再掘り起こしするまでの月数
    RECYCLE_MONTHS: 6,
    // 断り理由の選択肢(ワンタップ記録用。台帳の見送り理由データになる)
    REJECT_REASONS: ["時期が合わない", "必要ない", "他社利用中", "その他"]
  };

  function pad2_(n) {
    var s = String(n);
    return s.length < 2 ? "0" + s : s;
  }

  function formatDate_(date) {
    return date.getFullYear() + "-" + pad2_(date.getMonth() + 1) + "-" + pad2_(date.getDate());
  }

  function parseDate_(dateString) {
    var iso = String(dateString).slice(0, 10);
    return new Date(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10)));
  }

  function normalizeDate_(value) {
    var date = getGlowAlerting_().toDate(value);
    return date ? formatDate_(date) : "";
  }

  /** 土日を飛ばして営業日で日数を足す(祝日は考慮しない簡易版)。 */
  function addBusinessDays(dateString, days) {
    var date = parseDate_(dateString);
    var added = 0;
    while (added < days) {
      date.setDate(date.getDate() + 1);
      var dow = date.getDay();
      if (dow !== 0 && dow !== 6) added += 1;
    }
    return formatDate_(date);
  }

  /** 月数を足す。月末はみ出し(8/31+6ヶ月など)は行き先の月の末日に丸める。 */
  function addMonths(dateString, months) {
    var base = parseDate_(dateString);
    var target = new Date(base.getFullYear(), base.getMonth() + months, 1);
    var lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
    target.setDate(Math.min(base.getDate(), lastDay));
    return formatDate_(target);
  }

  var RANK_ORDER_ = { A: 0, B: 1, C: 2, D: 3 };

  /**
   * 架電リストを組み立てる。
   * 除外: 連絡不要 / 電話番号なし / 本日すでに接触済み(同日の重複架電防止)。
   * 並び順: ランクA→D → 期限超過の古い順 → 未着手 → 将来予定の近い順。
   * 返す項目は架電画面に必要な最小限とし、日付はyyyy-MM-dd文字列に正規化する
   * (Dateオブジェクトを返すとgoogle.script.runの応答全体が壊れる既知の癖)。
   */
  function buildCallQueue(companies, todayString) {
    var alerting = getGlowAlerting_();
    var entries = (companies || [])
      .filter(function (company) {
        if (company["連絡不要"] === true) return false;
        if (!String(company["電話番号"] || "").trim()) return false;
        if (normalizeDate_(company["最終接触日"]) === todayString) return false;
        return true;
      })
      .map(function (company) {
        var nextDate = normalizeDate_(company["次回アクション予定日"]);
        var diff = nextDate ? alerting.daysBetween(todayString, nextDate) : null;
        // 並び順のグループ: 0=期限超過(本日含む) 1=未着手 2=将来予定
        var bucket = nextDate === "" ? 1 : (diff !== null && diff <= 0 ? 0 : 2);
        return {
          "企業ID": company["企業ID"],
          "会社名": company["会社名"],
          "代表者名": company["代表者名"] || "",
          "電話番号": String(company["電話番号"] || "").trim(),
          "ランク": company["ランク"] || "",
          "現在ステージ": company["現在ステージ"] || "",
          "担当者": company["担当者"] || "",
          "次回アクション予定日": nextDate,
          "次回アクション内容": company["次回アクション内容"] || "",
          "最終接触日": normalizeDate_(company["最終接触日"]),
          bucket: bucket
        };
      });
    entries.sort(function (a, b) {
      var rankA = RANK_ORDER_[a["ランク"]] !== undefined ? RANK_ORDER_[a["ランク"]] : 9;
      var rankB = RANK_ORDER_[b["ランク"]] !== undefined ? RANK_ORDER_[b["ランク"]] : 9;
      if (rankA !== rankB) return rankA - rankB;
      if (a.bucket !== b.bucket) return a.bucket - b.bucket;
      var da = a["次回アクション予定日"];
      var db = b["次回アクション予定日"];
      if (da === db) return 0;
      return da < db ? -1 : 1;
    });
    return entries;
  }

  /**
   * 架電結果 → 対応履歴の種別・メモ・次回アクションの変換規則。
   * 返り値: { ok, type, memo, nextDate, nextNote } または { ok:false, errors }。
   */
  function resolveCallOutcome(outcome, todayString, extra) {
    var e = extra || {};
    var memo = String(e.memo || "").trim();

    if (outcome === "不在") {
      return {
        ok: true, type: "電話", memo: memo || "架電・不在",
        nextDate: addBusinessDays(todayString, CALL_RULES.RETRY_BUSINESS_DAYS),
        nextNote: "再架電(不在のため・" + CALL_RULES.RETRY_BUSINESS_DAYS + "営業日後)"
      };
    }
    if (outcome === "話せた") {
      var nextDate = String(e.nextDate || "").trim();
      if (nextDate && !/^\d{4}-\d{2}-\d{2}$/.test(nextDate)) {
        return { ok: false, errors: ["次回予定日は yyyy-MM-dd 形式で指定してください"] };
      }
      return {
        ok: true, type: "電話", memo: memo || "架電・会話",
        nextDate: nextDate,
        nextNote: nextDate ? (String(e.nextNote || "").trim() || "継続フォロー") : ""
      };
    }
    if (outcome === "アポ獲得") {
      var apptDate = String(e.apptDate || "").trim();
      if (!/^\d{4}-\d{2}-\d{2}$/.test(apptDate)) {
        return { ok: false, errors: ["面談日を yyyy-MM-dd 形式で指定してください"] };
      }
      return {
        ok: true, type: "アポ獲得", memo: memo || "架電でアポ獲得",
        nextDate: apptDate, nextNote: "面談(アポ確定)"
      };
    }
    if (outcome === "断り") {
      var reason = String(e.reason || "").trim();
      if (CALL_RULES.REJECT_REASONS.indexOf(reason) === -1) {
        return { ok: false, errors: ["断り理由が正しくありません: " + reason] };
      }
      var recycle = reason === "時期が合わない";
      return {
        ok: true, type: "見送り",
        memo: "見送り(理由: " + reason + ")" + (memo ? " " + memo : ""),
        nextDate: recycle ? addMonths(todayString, CALL_RULES.RECYCLE_MONTHS) : "",
        nextNote: recycle ? "再掘り起こし(時期が合わない・" + CALL_RULES.RECYCLE_MONTHS + "ヶ月後)" : ""
      };
    }
    if (outcome === "番号違い") {
      return {
        ok: true, type: "電話",
        memo: "番号違い・不通(リスト要修正)" + (memo ? " " + memo : ""),
        nextDate: "", nextNote: ""
      };
    }
    return { ok: false, errors: ["未知の架電結果です: " + outcome] };
  }

  var api = {
    CALL_RULES: CALL_RULES,
    addBusinessDays: addBusinessDays,
    addMonths: addMonths,
    buildCallQueue: buildCallQueue,
    resolveCallOutcome: resolveCallOutcome
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowCallMode = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
