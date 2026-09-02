/* GLOW企業リレーション台帳 管理画面Web Appの許可リスト照合・企業一覧の絞り込みロジック
 * ブラウザ相当のGAS(global.GlowAdminAccess)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_adminAccess.test.mjs で検証される。
 *
 * 個人Gmail運用(Workspaceドメインなし)のため、Web Appのアクセス設定だけでは
 * 利用者を限定できない。AdminRunner.gs が Session.getActiveUser().getEmail() で
 * 取得した実際のアクセス者のメールアドレスを、ここで「スタッフ」タブの登録
 * メールアドレスと照合する(三名体制レビュー2026-08-09裁定1・2)。
 */
(function (global) {
  "use strict";

  function normalizeEmail_(email) {
    return String(email || "").trim().toLowerCase();
  }

  function getGlowAlerting_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./alerting.js");
    }
    return global.GlowAlerting;
  }

  function getGlowSchema_() {
    if (typeof module !== "undefined" && module.exports) {
      return require("./schema.js");
    }
    return global.GlowSchema;
  }

  function computeUrgency(company, todayString) {
    if (company["連絡不要"] === true) return "none";
    var nextDate = company["次回アクション予定日"];
    if (!nextDate) return "untouched";
    var diffDays = getGlowAlerting_().daysBetween(todayString, nextDate);
    if (diffDays === null) return "untouched";
    if (diffDays <= 0) return "overdue";
    if (diffDays <= 3) return "soon";
    return "ok";
  }

  function buildKpiSummary(companies, todayString) {
    var list = companies || [];
    var byRank = { A: 0, B: 0, C: 0, D: 0 };
    var overdueOrUntouched = 0;
    var hot = 0;
    var deal = 0;
    var dealStages = ["提案中", "案件化"];
    list.forEach(function (company) {
      var rank = company["ランク"];
      if (byRank[rank] !== undefined) byRank[rank]++;
      var urgency = computeUrgency(company, todayString);
      if (urgency === "overdue" || urgency === "untouched") overdueOrUntouched++;
      if (company["本日反応あり"]) hot++;
      if (dealStages.indexOf(company["現在ステージ"]) !== -1) deal++;
    });
    var stale = getGlowAlerting_().buildStaleList(list, todayString).length;
    return {
      total: list.length,
      overdueOrUntouched: overdueOrUntouched,
      hot: hot,
      byRank: byRank,
      deal: deal,
      stale: stale
    };
  }

  function buildOwnerWorkload(companies, todayString) {
    var counts = {};
    var order = [];
    (companies || []).forEach(function (company) {
      var owner = company["担当者"];
      if (!owner) return;
      if (!counts[owner]) {
        counts[owner] = { owner: owner, total: 0, overdueOrUntouched: 0 };
        order.push(owner);
      }
      counts[owner].total++;
      var urgency = computeUrgency(company, todayString);
      if (urgency === "overdue" || urgency === "untouched") counts[owner].overdueOrUntouched++;
    });
    return order.map(function (owner) { return counts[owner]; })
      .sort(function (a, b) { return b.total - a.total; });
  }

  var URGENCY_ORDER_ = { untouched: 0, overdue: 1, soon: 2, ok: 3, none: 4 };

  function buildNextActionQueue(companies, todayString, limit) {
    var max = typeof limit === "number" ? limit : 8;
    var candidates = (companies || [])
      .map(function (company) {
        var urgency = computeUrgency(company, todayString);
        // company(readCompanyRecords_の生レコード)には登録日・最終接触日等がJSのDate
        // オブジェクトのまま入っている。normalizeCompanyDetailDatesで文字列化しておかないと
        // google.script.runの応答全体が壊れ、ブラウザ側にnull/undefinedが渡ってしまう
        // (getCompanyDetailで踏んだのと同じ既知の癖。2026-08-31 getAdminBootstrap
        // 導入時に発覚)。
        var withUrgency = normalizeCompanyDetailDates(company);
        withUrgency.urgency = urgency;
        return withUrgency;
      })
      .filter(function (company) {
        return company["本日反応あり"] || company.urgency === "overdue" ||
          company.urgency === "untouched" || company.urgency === "soon";
      });
    candidates.sort(function (a, b) {
      if (!!a["本日反応あり"] !== !!b["本日反応あり"]) return a["本日反応あり"] ? -1 : 1;
      return URGENCY_ORDER_[a.urgency] - URGENCY_ORDER_[b.urgency];
    });
    return candidates.slice(0, max);
  }

  function formatDate_(date) {
    var year = date.getFullYear();
    var month = String(date.getMonth() + 1).padStart(2, "0");
    var day = String(date.getDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
  }

  /**
   * 「本日の要対応」ポップアップ用: 次回アクション予定日が本日以前(=期限到来・超過)の
   * 企業を、予定日の古い順に返す。管理画面を開いた瞬間に表示し、話した後に決めた
   * 「次に架電する時期」が埋もれるのを防ぐ。
   *
   * buildNextActionQueue(サイドパネル)との違い: あちらは未着手(予定日なし)も含む
   * 掘り起こしの優先順位リスト。こちらは「予定日を自分で決めた企業」だけに絞る。
   * 未着手3,000社超を毎回ポップアップに出すと、本当に今日やるべき数件が埋もれるため。
   *
   * 返り値: { total: 全該当件数, items: 上位limit件(既定10件) }
   */
  function buildFollowUpReminders(companies, todayString, limit) {
    var max = typeof limit === "number" ? limit : 10;
    var due = (companies || [])
      .filter(function (company) {
        if (company["連絡不要"] === true) return false;
        var next = company["次回アクション予定日"];
        if (!next) return false;
        var diff = getGlowAlerting_().daysBetween(todayString, next);
        return diff !== null && diff <= 0;
      })
      .map(function (company) {
        var next = normalizeDateForDisplay(company["次回アクション予定日"]);
        var diff = getGlowAlerting_().daysBetween(todayString, next);
        return {
          "企業ID": company["企業ID"],
          "会社名": company["会社名"],
          "担当者": company["担当者"] || "",
          "ランク": company["ランク"] || "",
          "次回アクション予定日": next,
          "次回アクション内容": company["次回アクション内容"] || "",
          "遅延日数": Math.abs(diff)
        };
      })
      .sort(function (a, b) {
        if (a["次回アクション予定日"] === b["次回アクション予定日"]) return 0;
        return a["次回アクション予定日"] < b["次回アクション予定日"] ? -1 : 1;
      });
    return { total: due.length, items: due.slice(0, max) };
  }

  var WEEKDAY_LABELS_ = ["日", "月", "火", "水", "木", "金", "土"];

  /**
   * 訪問・架電スケジュール表(第3タブ)用: 今日からdaysAhead日分の日付ブロックと、
   * 各日の予定企業(次回アクション予定日ベース)を返す。期限超過はoverdueに古い順で
   * まとめる(予定日の再設定を促すため)。
   * 「1日に予定を詰め込みすぎていないか」「空いている日はどこか」を見て行動量を
   * 平準化する、法人営業の週次行動計画の定石をそのまま画面にしたもの。
   */
  function buildVisitSchedule(companies, todayString, daysAhead) {
    var ahead = typeof daysAhead === "number" ? daysAhead : 14;
    var scheduled = (companies || [])
      .filter(function (company) {
        if (company["連絡不要"] === true) return false;
        return !!company["次回アクション予定日"];
      })
      .map(function (company) {
        return {
          "企業ID": company["企業ID"],
          "会社名": company["会社名"],
          "担当者": company["担当者"] || "",
          "ランク": company["ランク"] || "",
          "次回アクション予定日": normalizeDateForDisplay(company["次回アクション予定日"]),
          "次回アクション内容": company["次回アクション内容"] || ""
        };
      });

    function byRankThenName(a, b) {
      var rankA = a["ランク"] || "Z";
      var rankB = b["ランク"] || "Z";
      if (rankA !== rankB) return rankA < rankB ? -1 : 1;
      var nameA = a["会社名"] || "";
      var nameB = b["会社名"] || "";
      if (nameA === nameB) return 0;
      return nameA < nameB ? -1 : 1;
    }

    var overdueItems = scheduled
      .filter(function (item) { return item["次回アクション予定日"] < todayString; })
      .sort(function (a, b) {
        if (a["次回アクション予定日"] === b["次回アクション予定日"]) return byRankThenName(a, b);
        return a["次回アクション予定日"] < b["次回アクション予定日"] ? -1 : 1;
      });

    var parts = todayString.split("-").map(Number);
    var days = [];
    for (var i = 0; i < ahead; i++) {
      var date = new Date(parts[0], parts[1] - 1, parts[2] + i);
      var dateString = formatDate_(date);
      days.push({
        date: dateString,
        "曜日": WEEKDAY_LABELS_[date.getDay()],
        items: scheduled
          .filter(function (item) { return item["次回アクション予定日"] === dateString; })
          .sort(byRankThenName)
      });
    }
    return {
      today: todayString,
      overdue: { total: overdueItems.length, items: overdueItems },
      days: days
    };
  }

  // 行動量ダッシュボードの指標と、対応履歴ログの「種別」との対応。
  // ここに載っていない種別(返信・レターURLアクセス・関係メモ更新等)は行動量には数えない
  // (企業側の反応や記録操作であり、営業側の行動量ではないため)。
  var ACTIVITY_METRICS_ = [
    { key: "手紙", types: ["手紙送付"] },
    { key: "架電", types: ["電話"] },
    { key: "アポ獲得", types: ["アポ獲得"] },
    { key: "面談・訪問", types: ["面談実施", "ゆんたく相談実施"] },
    { key: "提案", types: ["提案(M&A)", "提案(不動産)", "提案(法人保険)"] },
    { key: "成約", types: ["成約"] }
  ];

  /**
   * 行動量の実績ダッシュボード: 対応履歴ログを月曜はじまりの週ごとに
   * 「手紙・架電・アポ獲得・面談/訪問・提案・成約」へ分類して集計する。
   * 予定(訪問・架電スケジュール)と実績の差を見るための土台で、
   * 「行動量→アポ率→面談→成約」のファネルを数字で追う法人営業の定石に沿う。
   * 返り値: { metrics: 指標名の配列, weeks: [{label, start, end, total, byOwner}] }(今週が先頭)
   */
  function buildActivitySummary(interactions, todayString, weeksBack) {
    var count = typeof weeksBack === "number" ? weeksBack : 4;
    var typeToMetric = {};
    ACTIVITY_METRICS_.forEach(function (metric) {
      metric.types.forEach(function (type) { typeToMetric[type] = metric.key; });
    });
    function emptyCounts() {
      var counts = {};
      ACTIVITY_METRICS_.forEach(function (metric) { counts[metric.key] = 0; });
      return counts;
    }
    var parts = todayString.split("-").map(Number);
    var today = new Date(parts[0], parts[1] - 1, parts[2]);
    var mondayOffset = (today.getDay() + 6) % 7;
    var labels = ["今週", "先週", "2週前", "3週前", "4週前", "5週前"];
    var weeks = [];
    for (var w = 0; w < count; w++) {
      var start = new Date(today.getFullYear(), today.getMonth(), today.getDate() - mondayOffset - w * 7);
      var end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + 6);
      weeks.push({
        label: labels[w] || w + "週前",
        start: formatDate_(start),
        end: formatDate_(end),
        total: emptyCounts(),
        byOwner: {}
      });
    }
    (interactions || []).forEach(function (record) {
      var metric = typeToMetric[record["種別"]];
      if (!metric) return;
      var date = normalizeDateForDisplay(record["日付"]);
      if (!date) return;
      weeks.forEach(function (week) {
        if (date < week.start || date > week.end) return;
        week.total[metric] += 1;
        var owner = String(record["担当者"] || "").trim() || "未記入";
        if (!week.byOwner[owner]) week.byOwner[owner] = emptyCounts();
        week.byOwner[owner][metric] += 1;
      });
    });
    return {
      metrics: ACTIVITY_METRICS_.map(function (metric) { return metric.key; }),
      weeks: weeks
    };
  }

  var QUICK_LOG_MEMO_MAX_ = 2000;

  /**
   * 詳細ドロワーからのクイック記録(対応履歴の直接追加・v1.6.0)の入力検証。
   * 「電話したが不在」のような最速記録を許すため、メモは空でもよい。
   * 種別はスキーマのINTERACTION_TYPESに一致するもののみ(表記ゆれで集計から
   * 漏れるのを防ぐ。行動量ダッシュボード・スコアリングと同じ語彙を共有する)。
   */
  function validateQuickLog(input) {
    var source = input || {};
    var errors = [];
    var companyId = String(source["企業ID"] || "").trim();
    if (!companyId) errors.push("企業IDがありません");
    var type = String(source["種別"] || "").trim();
    if (getGlowSchema_().INTERACTION_TYPES.indexOf(type) === -1) {
      errors.push("種別が正しくありません: " + type);
    }
    var memo = String(source["内容メモ"] || "").trim();
    if (memo.length > QUICK_LOG_MEMO_MAX_) {
      errors.push("メモが長すぎます(" + QUICK_LOG_MEMO_MAX_ + "文字以内)");
    }
    if (errors.length > 0) return { ok: false, errors: errors };
    return { ok: true, companyId: companyId, type: type, memo: memo };
  }

  /**
   * 企業詳細ドロワーからの次回アクション直接編集の入力検証。
   * 日付は空でもよい(予定を消す操作)。入力があればyyyy-MM-dd形式のみ許可。
   */
  function buildNextActionUpdate(dateString, note) {
    var date = String(dateString || "").trim();
    var text = String(note || "").trim();
    if (date && !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      return { ok: false, errors: ["予定日は yyyy-MM-dd 形式で入力してください(例: 2026-09-05)"] };
    }
    return { ok: true, date: date, note: text };
  }

  /**
   * Sheetsの getValues() は日付セルを文字列ではなくJSの Date オブジェクトで返す。
   * これをそのまま String(...) すると "Thu Aug 20 2026 00:00:00 GMT+0900 ..." のような
   * 表示になり、曜日名基準でソートされてしまう(alerting.js の toDate と同じ問題への対処)。
   * Date/"yyyy-MM-dd"文字列のどちらが来ても "yyyy-MM-dd" 文字列に正規化する。
   */
  function normalizeDateForDisplay(value) {
    var date = getGlowAlerting_().toDate(value);
    return date ? formatDate_(date) : "";
  }

  function isAllowedEmail(email, staffRows) {
    var target = normalizeEmail_(email);
    if (!target) return false;
    return (staffRows || []).some(function (staff) {
      return normalizeEmail_(staff.email) === target;
    });
  }

  function buildAccessDeniedHtml() {
    return "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">" +
      "<style>body{font-family:-apple-system,BlinkMacSystemFont,\"Hiragino Sans\"," +
      "\"Noto Sans JP\",Meiryo,sans-serif;padding:3rem 2rem;text-align:center;color:#11202c}" +
      "h1{font-size:1.15rem;margin:0 0 0.75rem}p{color:#4a5a66;line-height:1.7}</style></head>" +
      "<body><h1>アクセス権がありません</h1>" +
      "<p>このページを利用できるのは許可されたスタッフのみです。<br>" +
      "心当たりがある場合は管理者に確認してください。</p></body></html>";
  }

  function resolveStaffName(email, staffRows) {
    var target = normalizeEmail_(email);
    var match = (staffRows || []).filter(function (staff) {
      return normalizeEmail_(staff.email) === target;
    })[0];
    return match && match.name ? match.name : "不明";
  }

  var COMPANY_LIST_FIELDS = [
    "企業ID", "会社名", "ランク", "現在ステージ", "次回アクション予定日", "担当者",
    "業種", "所在地", "流入ルート", "提案商品"
  ];
  var DEFAULT_LIST_LIMIT = 100;

  function pickCompanyListFields_(company, todayString) {
    var picked = {};
    COMPANY_LIST_FIELDS.forEach(function (field) {
      picked[field] = company[field] !== undefined ? company[field] : "";
    });
    picked["次回アクション予定日"] = normalizeDateForDisplay(company["次回アクション予定日"]);
    picked["流入ルート"] = company["流入ルート"] || [];
    picked["提案商品"] = company["提案商品"] || [];
    picked["urgency"] = computeUrgency(company, todayString);
    return picked;
  }

  function hasAnyFilter(filters) {
    var f = filters || {};
    return !!(String(f.search || "").trim() || f.rank || f.stage || f.owner || f.route || f.product);
  }

  function applyCompanyFilters(companies, filters) {
    var f = filters || {};
    var searchTerm = String(f.search || "").trim().toLowerCase();
    return (companies || []).filter(function (company) {
      if (searchTerm) {
        var name = String(company["会社名"] || "").toLowerCase();
        var rep = String(company["代表者名"] || "").toLowerCase();
        if (name.indexOf(searchTerm) === -1 && rep.indexOf(searchTerm) === -1) return false;
      }
      if (f.rank && company["ランク"] !== f.rank) return false;
      if (f.stage && company["現在ステージ"] !== f.stage) return false;
      if (f.owner && company["担当者"] !== f.owner) return false;
      if (f.route && (company["流入ルート"] || []).indexOf(f.route) === -1) return false;
      if (f.product && (company["提案商品"] || []).indexOf(f.product) === -1) return false;
      return true;
    });
  }

  function sortByNextActionDateDesc_(companies) {
    return companies.slice().sort(function (a, b) {
      var da = normalizeDateForDisplay(a["次回アクション予定日"]);
      var db = normalizeDateForDisplay(b["次回アクション予定日"]);
      if (da === db) return 0;
      return da < db ? 1 : -1;
    });
  }

  function buildCompanyListResult(companies, filters, todayString) {
    var filtered = applyCompanyFilters(companies, filters);
    var limited = hasAnyFilter(filters)
      ? filtered
      : sortByNextActionDateDesc_(filtered).slice(0, DEFAULT_LIST_LIMIT);
    return limited.map(function (company) {
      return pickCompanyListFields_(company, todayString);
    });
  }

  /**
   * 一覧画面の「現在ステージ」「担当者」「流入ルート」「提案商品」フィルタの選択肢を、
   * 企業マスタに実在する値から重複なく作る(ランクはA/B/C/Dで固定のため画面側で
   * ハードコードする)。AdminRunner.gsのgetFilterOptions/getAdminBootstrapの両方から
   * 同じロジックを共有する。
   */
  function buildFilterOptions(companies) {
    var stageSet = {};
    var ownerSet = {};
    var routeSet = {};
    var productSet = {};
    (companies || []).forEach(function (company) {
      if (company["現在ステージ"]) stageSet[company["現在ステージ"]] = true;
      if (company["担当者"]) ownerSet[company["担当者"]] = true;
      (company["流入ルート"] || []).forEach(function (route) { routeSet[route] = true; });
      (company["提案商品"] || []).forEach(function (product) { productSet[product] = true; });
    });
    return {
      stages: Object.keys(stageSet).sort(),
      owners: Object.keys(ownerSet).sort(),
      routes: Object.keys(routeSet).sort(),
      products: Object.keys(productSet).sort()
    };
  }

  function sortInteractionsByDateDesc(records) {
    return (records || [])
      .map(function (record) {
        var normalized = {};
        Object.keys(record).forEach(function (key) {
          normalized[key] = record[key];
        });
        normalized["日付"] = normalizeDateForDisplay(record["日付"]);
        return normalized;
      })
      .sort(function (a, b) {
        var da = a["日付"];
        var db = b["日付"];
        if (da === db) return 0;
        return da < db ? 1 : -1;
      });
  }

  /**
   * パートナー一覧(紹介パートナーマスタ全件+対応回数)の行を組み立てる。
   * AdminRunner.gs の getPartnerList がシート読み取り後にこれを呼ぶ。
   */
  function buildPartnerListRows(partners, interactionsByPartnerId) {
    var interactionsMap = interactionsByPartnerId || {};
    return (partners || []).map(function (partner) {
      var partnerId = partner["パートナーID"];
      return {
        "パートナーID": partnerId,
        "名称": partner["名称"],
        "種別": partner["種別"],
        "関係性ランク": partner["関係性ランク"],
        "対応回数": (interactionsMap[partnerId] || []).length
      };
    });
  }

  /**
   * 紹介実績ログの各レコードの「紹介日」を "yyyy-MM-dd" 文字列に正規化する。
   * 入力配列・要素は変更せず、新しい配列・オブジェクトを返す。
   */
  function normalizeReferralRecords(referrals) {
    return (referrals || []).map(function (record) {
      var normalized = {};
      Object.keys(record).forEach(function (key) {
        normalized[key] = record[key];
      });
      normalized["紹介日"] = normalizeDateForDisplay(record["紹介日"]);
      return normalized;
    });
  }

  // 企業詳細(getCompanyDetail)が返す企業オブジェクトの日付列。
  // SheetsのgetValues()はこれらをJSのDateオブジェクトのまま返すため、
  // google.script.runでブラウザへ渡す前に文字列へ正規化する必要がある
  // (Dateオブジェクトが混ざったオブジェクトを返すと、応答がブラウザ側でnull扱いに
  // なることがある。一覧側は既にpickCompanyListFields_で対応済みだったが、
  // 詳細側は未対応で「該当する企業が見つかりません」という誤表示を招いていた)。
  var COMPANY_DETAIL_DATE_FIELDS = ["最終接触日", "次回アクション予定日", "登録日"];

  function normalizeCompanyDetailDates(company) {
    if (!company) return company;
    var normalized = {};
    Object.keys(company).forEach(function (key) { normalized[key] = company[key]; });
    COMPANY_DETAIL_DATE_FIELDS.forEach(function (field) {
      if (normalized[field] !== undefined) {
        normalized[field] = normalizeDateForDisplay(normalized[field]);
      }
    });
    return normalized;
  }

  /**
   * 新規パートナー登録の入力検証+紹介パートナーマスタへ追記する1行を組み立てる。
   * AdminRunner.gs の registerPartner がシート読み取り後にこれを呼ぶ。
   *
   * - パートナーIDは既存の "P-NNN" 形式の最大値+1で自動採番(3桁ゼロ埋め、
   *   1000件以降は自然に4桁へ伸びる)。P-形式でない既存IDは採番の対象外。
   * - 名称は必須+既存名称との重複禁止(前後空白は無視して比較)。手動でシートに
   *   追加された行との二重登録を防ぐため、IDではなく名称で重複を見る。
   * - 最終接触日が未入力なら登録日(todayString)で初期化する(開拓できた時に
   *   登録する運用のため、登録日=直近の接触日とみなせる)。
   */
  function buildPartnerRegistration(input, existingPartners, todayString) {
    var source = input || {};
    var partners = existingPartners || [];
    var errors = [];

    var name = String(source["名称"] || "").trim();
    if (!name) {
      errors.push("名称は必須です");
    } else {
      var duplicated = partners.some(function (p) {
        return String(p["名称"] || "").trim() === name;
      });
      if (duplicated) {
        errors.push("「" + name + "」は既に登録されています(同じ名称のパートナーの二重登録を防ぐため、別名称にするか既存の行を更新してください)");
      }
    }

    ["最終接触日", "次回アクション予定日"].forEach(function (field) {
      var value = String(source[field] || "").trim();
      if (value && !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
        errors.push(field + "は yyyy-MM-dd 形式で入力してください(例: " + todayString + ")");
      }
    });

    if (errors.length > 0) return { ok: false, errors: errors };

    var maxNumber = 0;
    partners.forEach(function (p) {
      var matched = /^P-(\d+)$/.exec(String(p["パートナーID"] || "").trim());
      if (!matched) return;
      var n = parseInt(matched[1], 10);
      if (n > maxNumber) maxNumber = n;
    });
    var numberText = String(maxNumber + 1);
    while (numberText.length < 3) numberText = "0" + numberText;
    var partnerId = "P-" + numberText;

    var record = {
      "パートナーID": partnerId,
      "名称": name,
      "種別": String(source["種別"] || "").trim(),
      "担当者名": String(source["担当者名"] || "").trim(),
      "関係性ランク": String(source["関係性ランク"] || "").trim(),
      "累計紹介数": 0,
      "成約数": 0,
      "提供済み情報ログ": String(source["提供済み情報ログ"] || "").trim(),
      "紹介料率": String(source["紹介料率"] || "").trim(),
      "逆紹介履歴": "",
      "最終接触日": String(source["最終接触日"] || "").trim() || todayString,
      "次回アクション予定日": String(source["次回アクション予定日"] || "").trim()
    };
    var row = getGlowSchema_().PARTNER_MASTER_HEADERS.map(function (header) {
      return record[header];
    });
    return { ok: true, partnerId: partnerId, record: record, row: row };
  }

  var api = {
    isAllowedEmail: isAllowedEmail,
    buildAccessDeniedHtml: buildAccessDeniedHtml,
    resolveStaffName: resolveStaffName,
    COMPANY_LIST_FIELDS: COMPANY_LIST_FIELDS,
    DEFAULT_LIST_LIMIT: DEFAULT_LIST_LIMIT,
    hasAnyFilter: hasAnyFilter,
    applyCompanyFilters: applyCompanyFilters,
    buildCompanyListResult: buildCompanyListResult,
    buildFilterOptions: buildFilterOptions,
    sortInteractionsByDateDesc: sortInteractionsByDateDesc,
    normalizeDateForDisplay: normalizeDateForDisplay,
    normalizeCompanyDetailDates: normalizeCompanyDetailDates,
    buildPartnerListRows: buildPartnerListRows,
    buildPartnerRegistration: buildPartnerRegistration,
    normalizeReferralRecords: normalizeReferralRecords,
    computeUrgency: computeUrgency,
    buildKpiSummary: buildKpiSummary,
    buildOwnerWorkload: buildOwnerWorkload,
    buildNextActionQueue: buildNextActionQueue,
    buildFollowUpReminders: buildFollowUpReminders,
    buildVisitSchedule: buildVisitSchedule,
    buildNextActionUpdate: buildNextActionUpdate,
    buildActivitySummary: buildActivitySummary,
    validateQuickLog: validateQuickLog
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowAdminAccess = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
