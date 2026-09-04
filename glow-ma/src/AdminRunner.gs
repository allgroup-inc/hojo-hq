/**
 * GLOW企業リレーション台帳: 管理画面Web App
 * (Phase 18a: 企業一覧・詳細の閲覧 / Phase 18b: 関係メモ編集)
 *
 * 既存の TrackingWebApp.gs の doGet に ?page=admin での分岐が追加されており、
 * この分岐先が本ファイルの renderAdminPage_ を呼ぶ。実処理はすべてこのファイルに
 * 委譲し、doGet 自体はルーティングのみを行う(三名体制レビュー2026-08-09裁定3)。
 *
 * セットアップ(人間が一度だけ行う):
 * 1. 「スタッフ」タブに、管理画面へのアクセスを許可する人の「氏名」「メールアドレス」を
 *    入力し、「有効」列にチェックを入れる(Slack User IDは対面連携機能専用で、
 *    本機能の利用には不要)
 * 2. `clasp push` で最新コードを反映する
 * 3. Apps Scriptエディタの「デプロイ」→「新しいデプロイ」→種類「ウェブアプリ」で、
 *    トラッキング用(Phase 4)とは別に新規デプロイを作成する。実行ユーザー: 自分。
 *    アクセスできるユーザー: 「Googleアカウントを持つ全員」
 * 4. デプロイ後に発行されるURLの末尾に `?page=admin` を付けたものを、
 *    「スタッフ」タブに登録した人へ共有する
 *
 * 認証は Session.getActiveUser().getEmail()(実際のアクセス者のメールアドレス)を
 * 「スタッフ」タブの登録メールアドレスと照合する方式。個人Gmail運用(Workspace
 * ドメインなし)のため、Web Appのアクセス設定(「Googleアカウントを持つ全員」)だけでは
 * 利用者を限定できず、この許可リスト照合が唯一の防御線になる。そのため
 * getCompanyList・getCompanyDetail など公開される関数それぞれの冒頭でも
 * requireAdminAccess_ を呼ぶ(doGetでの一度きりのチェックに依存しない多層防御。
 * 三名体制レビュー2026-08-09裁定1・2)。
 */
function isAdminUser_() {
  var email = Session.getActiveUser().getEmail();
  var staffRows = readStaffAllowlistEmails_();
  return GlowAdminAccess.isAllowedEmail(email, staffRows);
}

function requireAdminAccess_() {
  if (!isAdminUser_()) {
    throw new Error("この操作を行う権限がありません。");
  }
}

function readStaffAllowlistEmails_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(GlowSchema.STAFF_SHEET_NAME);
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.STAFF_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var nameIndex = headers.indexOf("氏名");
  var emailIndex = headers.indexOf("メールアドレス");
  var activeIndex = headers.indexOf("有効");
  return values
    .filter(function (row) { return row[activeIndex] === true && row[emailIndex]; })
    .map(function (row) { return { email: row[emailIndex], name: row[nameIndex] }; });
}

function renderAdminPage_() {
  if (!isAdminUser_()) {
    return HtmlService.createHtmlOutput(GlowAdminAccess.buildAccessDeniedHtml());
  }
  return HtmlService.createHtmlOutput(GlowAdminApp.buildAdminAppHtml())
    .setTitle("GLOW企業リレーション台帳");
}

/**
 * 企業一覧(絞り込み・並び替え済み、最小フィールドのみ)を返す。
 * google.script.run 経由で adminApp.js の画面から呼ばれる。
 *
 * 以下3関数(getCompanyList・getCompanyDetail・getFilterOptions)は名前の末尾に
 * `_` を付けてはいけない。Apps Scriptは末尾が`_`の関数を非公開扱いにし、
 * google.script.run から呼び出せなくする(呼んでもエラーにすらならず、単に
 * 何も起きない)。アクセス制御は関数名ではなく、各関数の冒頭で呼んでいる
 * requireAdminAccess_() だけが担う(最終レビュー2026-08-09 Fix 1)。
 */
function getCompanyList(filters) {
  requireAdminAccess_();
  var loaded = loadCompaniesWithReactionFlag_();
  return GlowAdminAccess.buildCompanyListResult(loaded.companies, filters || {}, loaded.todayString);
}

/**
 * 企業1社分の全項目(機微情報を含む)と、対応履歴ログ(日付降順)を返す。
 * 該当企業が見つからない場合はnullを返す。
 */
function getCompanyDetail(companyId) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  var company = companies.filter(function (c) { return c["企業ID"] === companyId; })[0];
  if (!company) return null;

  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  var interactionsByCompany = logSheet ? readInteractionsByCompanyId_(logSheet) : {};
  var history = GlowAdminAccess.sortInteractionsByDateDesc(interactionsByCompany[companyId] || []);

  return { company: GlowAdminAccess.normalizeCompanyDetailDates(company), history: history };
}

/**
 * 一覧画面の「現在ステージ」「担当者」フィルタの選択肢を、企業マスタに実在する
 * 値から重複なく作る(ランクはA/B/C/Dで固定のため画面側にハードコードする)。
 */
function getFilterOptions() {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  return GlowAdminAccess.buildFilterOptions(companies);
}

/**
 * 対応履歴ログから、本日日付の行がある企業IDの集合を返す(即時アラート/KPIの「hot」判定用)。
 */
function buildTodayReactedCompanyIdSet_(logSheet, todayString) {
  var result = {};
  if (!logSheet) return result;
  var lastRow = logSheet.getLastRow();
  if (lastRow < 2) return result;
  var headers = GlowSchema.INTERACTION_LOG_HEADERS;
  var dateIndex = headers.indexOf("日付");
  var idIndex = headers.indexOf("企業ID");
  var values = logSheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  values.forEach(function (row) {
    var companyId = row[idIndex];
    if (!companyId) return;
    var dateValue = row[dateIndex];
    var dateString = dateValue instanceof Date
      ? Utilities.formatDate(dateValue, "Asia/Tokyo", "yyyy-MM-dd")
      : String(dateValue || "");
    if (dateString === todayString) result[companyId] = true;
  });
  return result;
}

function loadCompaniesWithReactionFlag_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var reactedSet = buildTodayReactedCompanyIdSet_(logSheet, todayString);
  companies.forEach(function (company) {
    company["本日反応あり"] = !!reactedSet[company["企業ID"]];
  });
  return { companies: companies, todayString: todayString };
}

function getKpiSummary() {
  requireAdminAccess_();
  var loaded = loadCompaniesWithReactionFlag_();
  return GlowAdminAccess.buildKpiSummary(loaded.companies, loaded.todayString);
}

function getOwnerWorkload() {
  requireAdminAccess_();
  var loaded = loadCompaniesWithReactionFlag_();
  return GlowAdminAccess.buildOwnerWorkload(loaded.companies, loaded.todayString);
}

function getNextActionQueue() {
  requireAdminAccess_();
  var loaded = loadCompaniesWithReactionFlag_();
  return GlowAdminAccess.buildNextActionQueue(loaded.companies, loaded.todayString, 8);
}

/**
 * 管理画面を開いた直後の初回表示に必要なデータ(企業一覧・KPI・ワークロード・
 * ネクストアクション・フィルタ選択肢)を1回のスプレッドシート読み込みでまとめて返す。
 *
 * 個別関数(getCompanyList/getKpiSummary/getOwnerWorkload/getNextActionQueue/
 * getFilterOptions)はそれぞれ独立に企業マスタ全件(3,000件超)を読み直しており、
 * 初回表示だけで5回分の重複読み込みが発生し体感速度を悪化させていた
 * (2026-08-31 小柳さんの「動作が遅い」報告を受けて調査・特定)。
 * 個別関数は絞り込み後の再取得(getCompanyList)等で引き続き使うため残す。
 */
function getAdminBootstrap() {
  requireAdminAccess_();
  var loaded = loadCompaniesWithReactionFlag_();
  return {
    companyList: GlowAdminAccess.buildCompanyListResult(loaded.companies, {}, loaded.todayString),
    kpi: GlowAdminAccess.buildKpiSummary(loaded.companies, loaded.todayString),
    workload: GlowAdminAccess.buildOwnerWorkload(loaded.companies, loaded.todayString),
    queue: GlowAdminAccess.buildNextActionQueue(loaded.companies, loaded.todayString, 8),
    filterOptions: GlowAdminAccess.buildFilterOptions(loaded.companies),
    reminders: GlowAdminAccess.buildFollowUpReminders(loaded.companies, loaded.todayString, 10)
  };
}

/**
 * 企業一覧でチェックした企業を、make_qr_cards.py(❸事業構成&ゆんたく)の入力形式
 * (発送日・企業ID・会社名・所在地・窓口担当者名のCSV。ShippingRunner.gsの
 * 「発送日でCSV出力」と同じ列)でまとめて出力する。QRコード画像自体の生成・印刷は
 * 引き続きmake_qr_cards.pyが担当し、この管理画面では対象企業の選定とCSV化のみ行う
 * (2026-08-31 小柳さんの依頼: 管理画面で任意の企業を選んで一括印刷準備をしたい)。
 *
 * BOM付きUTF-8でbase64化して返す(ShippingRunner.gsのbuildCsvDownloadHtml_と同じ
 * 理由: BOMがないと日本語Excelが文字化けする)。プレビュー用に企業名一覧も返す。
 */
function getQrExportForSelectedCompanies(companyIds, targetDate) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  var companies = companySheet ? readCompanyRecords_(companySheet) : [];
  var rows = GlowShippingContent.buildRowsForCompanyIds(companies, companyIds || [], targetDate);
  var csvString = GlowShippingContent.toCsvString(rows);
  var base64Csv = Utilities.base64Encode("﻿" + csvString, Utilities.Charset.UTF_8);
  var preview = rows.slice(1).map(function (row) {
    return { "企業ID": row[1], "会社名": row[2], "所在地": row[3], "窓口担当者名": row[4] };
  });
  return { base64Csv: base64Csv, count: preview.length, preview: preview };
}

/**
 * ドロワーの🤝連携ボタン用。ShareRunner.gsのreadActiveStaff_と同じロジックだが、
 * 呼び出し元(スプレッドシートメニュー vs Web App)が異なるため、末尾に`_`を付けない
 * 公開関数として別途用意する(google.script.runから呼ぶため)。
 */
function getShareableStaffList() {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(GlowSchema.STAFF_SHEET_NAME);
  if (!sheet) return [];
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return [];
  var headers = GlowSchema.STAFF_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var nameIndex = headers.indexOf("氏名");
  var slackIdIndex = headers.indexOf("Slack User ID");
  var activeIndex = headers.indexOf("有効");
  return values
    .filter(function (row) { return row[activeIndex] === true && row[nameIndex] && row[slackIdIndex]; })
    .map(function (row) { return { name: row[nameIndex], slackUserId: row[slackIdIndex] }; });
}

/**
 * 企業1社分の最新レター下書き(生成日時が最も新しい行)を返す。存在しなければnull。
 */
function getLatestLetterDraft(companyId) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(GlowSchema.LETTER_DRAFT_SHEET_NAME);
  if (!sheet) return null;
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return null;
  var headers = GlowSchema.LETTER_DRAFT_HEADERS;
  var idIndex = headers.indexOf("企業ID");
  var dateIndex = headers.indexOf("生成日時");
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  var latest = null;
  values.forEach(function (row) {
    if (row[idIndex] !== companyId) return;
    var record = {};
    headers.forEach(function (header, i) { record[header] = row[i]; });
    if (!latest) { latest = record; return; }
    var currentDate = row[dateIndex] instanceof Date ? row[dateIndex] : new Date(row[dateIndex]);
    var latestDate = latest["生成日時"] instanceof Date ? latest["生成日時"] : new Date(latest["生成日時"]);
    if (currentDate > latestDate) latest = record;
  });
  if (latest && latest["生成日時"] instanceof Date) {
    latest["生成日時"] = Utilities.formatDate(latest["生成日時"], "Asia/Tokyo", "yyyy-MM-dd HH:mm");
  }
  return latest;
}

/**
 * パートナー対応履歴ログを読み、パートナーIDごとに配列へグルーピングして返す。
 * readInteractionsByCompanyId_(ScoringRunner.gs、企業向け)と同じパターンだが、
 * 対象タブ・キー列(パートナーID)が異なるため専用の関数として定義する。
 */
function readPartnerInteractionsByPartnerId_(sheet) {
  var result = {};
  if (!sheet) return result;
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return result;
  var headers = GlowSchema.PARTNER_INTERACTION_LOG_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  values.forEach(function (row) {
    var record = {};
    headers.forEach(function (header, i) {
      record[header] = row[i];
    });
    var partnerId = record["パートナーID"];
    if (!partnerId) return;
    if (!result[partnerId]) result[partnerId] = [];
    result[partnerId].push(record);
  });
  return result;
}

/**
 * パートナー一覧(紹介パートナーマスタ全件+パートナー対応履歴ログの記録件数)を返す。
 * 企業一覧と異なり件数が少ない想定のため、絞り込み必須・件数上限は設けない。
 *
 * この関数の名前の末尾に `_` を付けてはいけない。Apps Scriptは末尾が`_`の関数を
 * 非公開扱いにし、google.script.run から呼び出せなくする(呼んでもエラーにすら
 * ならず、単に何も起きない)。アクセス制御は関数名ではなく、冒頭で呼んでいる
 * requireAdminAccess_() だけが担う(Phase 18a最終レビュー2026-08-09 Fix 1と同じ理由)。
 */
function getPartnerList() {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var partnerSheet = ss.getSheetByName(GlowSchema.PARTNER_MASTER_SHEET_NAME);
  var partners = readPartnerRecords_(partnerSheet);

  var logSheet = ss.getSheetByName(GlowSchema.PARTNER_INTERACTION_LOG_SHEET_NAME);
  var interactionsByPartner = readPartnerInteractionsByPartnerId_(logSheet);

  return GlowAdminAccess.buildPartnerListRows(partners, interactionsByPartner);
}

function readReferralRecordsByPartnerId_(sheet) {
  var result = {};
  if (!sheet) return result;
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return result;
  var headers = GlowSchema.REFERRAL_RECORD_HEADERS;
  var values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
  values.forEach(function (row) {
    var record = {};
    headers.forEach(function (header, i) {
      record[header] = row[i];
    });
    var partnerId = record["パートナーID"];
    if (!partnerId) return;
    if (!result[partnerId]) result[partnerId] = [];
    result[partnerId].push(record);
  });
  return result;
}

/**
 * パートナー1件分の基本情報+対応履歴(日付降順)+紹介実績を返す。
 * 該当パートナーが見つからない場合はnullを返す。
 *
 * 紹介実績は件数が少ない想定のため、この時点では並び替えを行わずシート上の
 * 順序のまま返す(対応履歴のような大量データではないため、Task 5・6の時点では
 * ソートの必要性が薄いと判断。必要になれば後続フェーズで追加する)。
 *
 * この関数の名前の末尾に `_` を付けてはいけない(getPartnerListと同じ理由)。
 */
function getPartnerDetail(partnerId) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var partnerSheet = ss.getSheetByName(GlowSchema.PARTNER_MASTER_SHEET_NAME);
  var partners = readPartnerRecords_(partnerSheet);
  var partner = partners.filter(function (p) { return p["パートナーID"] === partnerId; })[0];
  if (!partner) return null;

  var logSheet = ss.getSheetByName(GlowSchema.PARTNER_INTERACTION_LOG_SHEET_NAME);
  var interactionsByPartner = readPartnerInteractionsByPartnerId_(logSheet);
  var history = GlowAdminAccess.sortInteractionsByDateDesc(interactionsByPartner[partnerId] || []);

  var referralSheet = ss.getSheetByName(GlowSchema.REFERRAL_RECORD_SHEET_NAME);
  var referrals = readReferralRecordsByPartnerId_(referralSheet)[partnerId] || [];
  referrals = GlowAdminAccess.normalizeReferralRecords(referrals);

  return { partner: partner, history: history, referrals: referrals };
}

/**
 * 訪問・架電スケジュール表(今日からdaysAhead日分+期限超過)を返す。
 * この関数の名前の末尾に `_` を付けてはいけない(getPartnerListと同じ理由)。
 */
function getVisitSchedule(daysAhead) {
  requireAdminAccess_();
  var loaded = loadCompaniesWithReactionFlag_();
  var schedule = GlowAdminAccess.buildVisitSchedule(loaded.companies, loaded.todayString, daysAhead);

  // 行動量ダッシュボード(週次実績)も同じ応答に載せ、往復回数を増やさない
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  var flatInteractions = [];
  if (logSheet) {
    var byCompany = readInteractionsByCompanyId_(logSheet);
    Object.keys(byCompany).forEach(function (companyId) {
      Array.prototype.push.apply(flatInteractions, byCompany[companyId]);
    });
  }
  schedule.activity = GlowAdminAccess.buildActivitySummary(flatInteractions, loaded.todayString, 4);
  return schedule;
}

/**
 * 詳細ドロワーからのクイック記録(v1.6.0): 対応履歴ログへ1行追記し、
 * 最終接触日を当日に更新する(記録=接触の事実。LINE音声ログ確定時と同じ扱い)。
 * 検証はGlowAdminAccess.validateQuickLog(純ロジック)が担う。担当者は
 * ログイン中のスタッフをスタッフタブから逆引きし、手入力ゼロにする。
 * ロック理由はupdateCompanyMemoと同じ(全体書き戻しとの競合・行ズレ防止)。
 * この関数の名前の末尾に `_` を付けてはいけない(getPartnerListと同じ理由)。
 */
function appendInteractionLog(companyId, interactionType, memo) {
  requireAdminAccess_();
  var validated = GlowAdminAccess.validateQuickLog({
    "企業ID": companyId, "種別": interactionType, "内容メモ": memo
  });
  if (!validated.ok) {
    return { ok: false, errors: validated.errors };
  }
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  if (!logSheet) {
    throw new Error("対応履歴ログタブが見つかりません。");
  }
  var staffName = GlowAdminAccess.resolveStaffName(
    Session.getActiveUser().getEmail(), readStaffAllowlistEmails_()
  );
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var record = {
    "履歴ID": "H-" + Utilities.getUuid(),
    "企業ID": validated.companyId,
    "日付": todayString,
    "担当者": staffName,
    "種別": validated.type,
    "対応相手": "",
    "内容メモ": validated.memo,
    "次回アクション": ""
  };
  var headers = GlowSchema.INTERACTION_LOG_HEADERS;
  var row = headers.map(function (header) {
    return record[header] !== undefined ? record[header] : "";
  });
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    throw new Error("他の処理がデータを操作中のため、記録を中断しました。しばらく待ってから再実行してください。");
  }
  try {
    logSheet.getRange(logSheet.getLastRow() + 1, 1, 1, headers.length).setValues([row]);
    var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
    if (companySheet) {
      var rowIndex = findCompanyRowIndex_(companySheet, validated.companyId);
      if (rowIndex !== -1) {
        var lastContactColumn = GlowSchema.COMPANY_MASTER_HEADERS.indexOf("最終接触日") + 1;
        companySheet.getRange(rowIndex, lastContactColumn).setValue(todayString);
      }
    }
  } finally {
    lock.releaseLock();
  }
  return { ok: true, record: record };
}

/**
 * 連続架電モード(v1.7.0): 現在の絞り込み条件で架電リストを返す。
 * 並び順・除外規則はGlowCallMode.buildCallQueue(純ロジック)が担う。
 * この関数の名前の末尾に `_` を付けてはいけない(getPartnerListと同じ理由)。
 */
function getCallQueue(filters) {
  requireAdminAccess_();
  var loaded = loadCompaniesWithReactionFlag_();
  var filtered = GlowAdminAccess.applyCompanyFilters(loaded.companies, filters || {});
  return GlowCallMode.buildCallQueue(filtered, loaded.todayString);
}

/**
 * 連続架電モードの結果記録(v1.7.0): 結果ボタン1つで、対応履歴への記録+
 * 次回アクションの自動設定+最終接触日の更新を1ロックの中で行う。
 * 結果→記録内容の変換はGlowCallMode.resolveCallOutcome(純ロジック)、
 * 入力検証は既存のvalidateQuickLog/buildNextActionUpdateを再利用する。
 * この関数の名前の末尾に `_` を付けてはいけない(getPartnerListと同じ理由)。
 */
function recordCallOutcome(companyId, outcome, extra) {
  requireAdminAccess_();
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var resolved = GlowCallMode.resolveCallOutcome(outcome, todayString, extra || {});
  if (!resolved.ok) {
    return { ok: false, errors: resolved.errors };
  }
  var quick = GlowAdminAccess.validateQuickLog({
    "企業ID": companyId, "種別": resolved.type, "内容メモ": resolved.memo
  });
  if (!quick.ok) {
    return { ok: false, errors: quick.errors };
  }
  var nextAction = GlowAdminAccess.buildNextActionUpdate(resolved.nextDate, resolved.nextNote);
  if (!nextAction.ok) {
    return { ok: false, errors: nextAction.errors };
  }
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!logSheet || !companySheet) {
    throw new Error("対応履歴ログまたは企業マスタのタブが見つかりません。");
  }
  var staffName = GlowAdminAccess.resolveStaffName(
    Session.getActiveUser().getEmail(), readStaffAllowlistEmails_()
  );
  var record = {
    "履歴ID": "H-" + Utilities.getUuid(),
    "企業ID": quick.companyId,
    "日付": todayString,
    "担当者": staffName,
    "種別": quick.type,
    "対応相手": "",
    "内容メモ": quick.memo,
    "次回アクション": nextAction.note
  };
  var headers = GlowSchema.INTERACTION_LOG_HEADERS;
  var row = headers.map(function (header) {
    return record[header] !== undefined ? record[header] : "";
  });
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    throw new Error("他の処理がデータを操作中のため、記録を中断しました。しばらく待ってから再実行してください。");
  }
  try {
    logSheet.getRange(logSheet.getLastRow() + 1, 1, 1, headers.length).setValues([row]);
    var rowIndex = findCompanyRowIndex_(companySheet, quick.companyId);
    if (rowIndex !== -1) {
      var masterHeaders = GlowSchema.COMPANY_MASTER_HEADERS;
      companySheet.getRange(rowIndex, masterHeaders.indexOf("最終接触日") + 1).setValue(todayString);
      companySheet.getRange(rowIndex, masterHeaders.indexOf("次回アクション予定日") + 1).setValue(nextAction.date);
      companySheet.getRange(rowIndex, masterHeaders.indexOf("次回アクション内容") + 1).setValue(nextAction.note);
    }
  } finally {
    lock.releaseLock();
  }
  return { ok: true, record: record, nextDate: nextAction.date, nextNote: nextAction.note };
}

/**
 * 集客ファネル(週次)を返す。LP閲覧・LINE友だち数はhojo-hq(公開リポジトリ)で
 * 毎日自動収集されているKPIデータをraw.githubusercontent.comから読む。
 * 取得に失敗してもglow-ma内部の数字(新規登録・面談・成約)だけで表は成立させ、
 * 欠けた列はnull(画面では「—」)として返す。
 * この関数の名前の末尾に `_` を付けてはいけない(getPartnerListと同じ理由)。
 */
function getFunnelSummary() {
  requireAdminAccess_();
  var loaded = loadCompaniesWithReactionFlag_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  var flatInteractions = [];
  if (logSheet) {
    var byCompany = readInteractionsByCompanyId_(logSheet);
    Object.keys(byCompany).forEach(function (companyId) {
      Array.prototype.push.apply(flatInteractions, byCompany[companyId]);
    });
  }
  var activity = GlowAdminAccess.buildActivitySummary(flatInteractions, loaded.todayString, 4);
  var siteTraffic = fetchPublicKpiJson_("site_traffic.json");
  var lineFollowers = fetchPublicKpiJson_("line_followers.json");
  return GlowFunnelContent.buildWeeklyFunnel({
    siteTraffic: (siteTraffic && siteTraffic.history) || [],
    lineFollowers: (lineFollowers && lineFollowers.history) || [],
    kgiTarget: (lineFollowers && lineFollowers.kgi_target) || 1000,
    companies: loaded.companies,
    activity: activity
  }, loaded.todayString, 4);
}

/**
 * hojo-hq(公開リポジトリ)のdata/kpi/配下のJSONを読む。公開データのみが対象
 * (認証トークン不要)。失敗時はnullを返し、呼び出し側が「—」表示に倒す。
 */
function fetchPublicKpiJson_(fileName) {
  try {
    var response = UrlFetchApp.fetch(
      "https://raw.githubusercontent.com/allgroup-inc/hojo-hq/main/data/kpi/" + fileName,
      { muteHttpExceptions: true }
    );
    if (response.getResponseCode() !== 200) {
      Logger.log("KPIデータの取得に失敗しました(" + fileName + "): HTTP " + response.getResponseCode());
      return null;
    }
    return JSON.parse(response.getContentText());
  } catch (error) {
    Logger.log("KPIデータの取得に失敗しました(" + fileName + "): " + error);
    return null;
  }
}

/**
 * 企業詳細ドロワーからの次回アクション(予定日・内容)の直接更新。
 * 検証はGlowAdminAccess.buildNextActionUpdate(純ロジック)が担う。
 * ロック理由はupdateCompanyMemoと同じ(行特定と書き込みの間の全体書き戻し・行ズレ防止)。
 * この関数の名前の末尾に `_` を付けてはいけない(getPartnerListと同じ理由)。
 */
function updateNextAction(companyId, dateString, note) {
  requireAdminAccess_();
  var validated = GlowAdminAccess.buildNextActionUpdate(dateString, note);
  if (!validated.ok) {
    return { ok: false, errors: validated.errors };
  }
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。");
  }
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    throw new Error("他の処理がデータを操作中のため、保存を中断しました。しばらく待ってから再実行してください。");
  }
  try {
    var rowIndex = findCompanyRowIndex_(companySheet, companyId);
    if (rowIndex === -1) {
      throw new Error("該当する企業が見つかりません: " + companyId);
    }
    var dateColumnIndex = GlowSchema.COMPANY_MASTER_HEADERS.indexOf("次回アクション予定日") + 1;
    var noteColumnIndex = GlowSchema.COMPANY_MASTER_HEADERS.indexOf("次回アクション内容") + 1;
    companySheet.getRange(rowIndex, dateColumnIndex).setValue(validated.date);
    companySheet.getRange(rowIndex, noteColumnIndex).setValue(validated.note);
    return { ok: true, date: validated.date, note: validated.note };
  } finally {
    lock.releaseLock();
  }
}

/**
 * 新規パートナーを紹介パートナーマスタへ1行追記する(管理画面の登録フォームから)。
 * 入力検証・ID自動採番・行組み立てはGlowAdminAccess.buildPartnerRegistration(純ロジック)が担う。
 *
 * ロックは、既存ID読み取り→採番→appendRowの間に別の登録が挟まってIDが重複するのを
 * 防ぐため(updateCompanyMemoと同じgetDocumentLockで、シート全体の書き込みと排他する)。
 *
 * この関数の名前の末尾に `_` を付けてはいけない(getPartnerListと同じ理由。
 * google.script.runから呼べなくなる)。
 */
function registerPartner(input) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(GlowSchema.PARTNER_MASTER_SHEET_NAME);
  if (!sheet) {
    throw new Error("紹介パートナーマスタタブが見つかりません。");
  }
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    throw new Error("他の処理がデータを操作中のため、登録を中断しました。しばらく待ってから再実行してください。");
  }
  try {
    var partners = readPartnerRecords_(sheet);
    var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
    var result = GlowAdminAccess.buildPartnerRegistration(input, partners, todayString);
    if (!result.ok) {
      return { ok: false, errors: result.errors };
    }
    sheet.appendRow(result.row);
    return { ok: true, partnerId: result.partnerId };
  } finally {
    lock.releaseLock();
  }
}

/**
 * 企業マスタの中から「企業ID」が一致する行の行番号(1始まり、ヘッダー行込み)を返す。
 * 見つからなければ-1を返す。updateCompanyMemoが書き込み先の行を特定するために使う。
 */
function findCompanyRowIndex_(sheet, companyId) {
  var lastRow = sheet.getLastRow();
  if (lastRow < 2) return -1;
  var idColumnIndex = GlowSchema.COMPANY_MASTER_HEADERS.indexOf("企業ID") + 1;
  var ids = sheet.getRange(2, idColumnIndex, lastRow - 1, 1).getValues();
  for (var i = 0; i < ids.length; i++) {
    if (ids[i][0] === companyId) return i + 2;
  }
  return -1;
}

/**
 * 指定した列(1始まりの列番号)を上から走査し、値が入っている最後の行番号を返す。
 * ヘッダー行のみの場合は1を返す。
 *
 * getLastRow()は書式設定だけが及んでいる空行もデータ有りとみなしてしまうため
 * (ImportRunner.gsのreadCompanyRecords_と同じ原因。本番運用2026-08-10で発見)、
 * 新しい行を追記する位置を決めるときはこの関数で実データの末尾を確認すること。
 */
function findLastDataRow_(sheet, keyColumnIndex) {
  var maxRow = sheet.getLastRow();
  if (maxRow < 2) return 1;
  var values = sheet.getRange(2, keyColumnIndex, maxRow - 1, 1).getValues();
  var lastDataRow = 1;
  for (var i = 0; i < values.length; i++) {
    if (values[i][0]) lastDataRow = i + 2;
  }
  return lastDataRow;
}

/**
 * 関係メモが上書きされる直前に、更新前の内容を対応履歴ログへ1行自動記録する
 * (設計書4章。専用の変更履歴テーブルを作らず、既存の対応履歴ログの仕組みで
 * 「上書きされる前の情報」を追跡可能にする)。
 * この記録が失敗した場合は例外を投げ、呼び出し元(updateCompanyMemo)で
 * 関係メモの上書き自体を行わせない。
 *
 * ドキュメントロックはこの関数では取得しない。呼び出し元のupdateCompanyMemoが
 * 行特定〜メモ書き込みまでを1つのロックで保護しており、ここで取り直すと
 * その保護が途切れてしまうため(最終レビュー2026-08-10 I2)。
 */
function appendMemoUpdateInteractionLog_(companyId, oldMemo) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var logSheet = ss.getSheetByName(GlowSchema.INTERACTION_LOG_SHEET_NAME);
  if (!logSheet) {
    throw new Error("対応履歴ログタブが見つかりません。");
  }
  var idColumnIndex = GlowSchema.INTERACTION_LOG_HEADERS.indexOf("履歴ID") + 1;
  var nextRow = findLastDataRow_(logSheet, idColumnIndex) + 1;
  var logId = "H-" + Utilities.getUuid();
  var todayString = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");
  var staffRows = readStaffAllowlistEmails_();
  var staffName = GlowAdminAccess.resolveStaffName(Session.getActiveUser().getEmail(), staffRows);
  var oldMemoText = oldMemo ? String(oldMemo) : "(更新前は未記入)";
  logSheet.getRange(nextRow, 1, 1, GlowSchema.INTERACTION_LOG_HEADERS.length).setValues([[
    logId, companyId, todayString, staffName, "関係メモ更新", "未接触",
    "関係メモを更新しました(更新前の内容: " + oldMemoText + ")", ""
  ]]);
}

/**
 * 企業詳細ドロワーから呼ばれる、関係メモの更新関数。
 *
 * この関数の名前の末尾に `_` を付けてはいけない(getCompanyList等と同じ理由。
 * Apps Scriptは末尾が`_`の関数を非公開扱いにし、google.script.runから呼び出せなくする)。
 *
 * 対応履歴ログへの記録(appendMemoUpdateInteractionLog_)が完了してから
 * 関係メモを上書きする順序を守ること(設計書3章。記録なき上書きを避けるため)。
 *
 * ドキュメントロックは行特定〜ログ記録〜メモ書き込みの全体にかける。人間同士の
 * 同時編集対策ではなく(それが当初の狭すぎる理由だった)、企業マスタ全体を
 * 読み込み→加工→clearContent+一括書き戻しするrecalculateScores(ScoringRunner.gs)・
 * syncDoNotContact(DncRunner.gs)・importCompaniesFromStaging(ImportRunner.gs)との
 * 排他が目的。ロックが途切れると、行特定と書き込みの間に全体書き戻しが挟まって
 * メモが黙って元に戻る(ロストアップデート)か、行位置がずれて別企業の行に
 * メモを書き込む(誤行破壊)可能性がある(最終レビュー2026-08-10 I2)。
 */
function updateCompanyMemo(companyId, memo) {
  requireAdminAccess_();
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var companySheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  if (!companySheet) {
    throw new Error("企業マスタタブが見つかりません。");
  }
  var lock = LockService.getDocumentLock();
  if (!lock.tryLock(10000)) {
    throw new Error("他の処理がデータを操作中のため、保存を中断しました。しばらく待ってから再実行してください。");
  }
  try {
    var rowIndex = findCompanyRowIndex_(companySheet, companyId);
    if (rowIndex === -1) {
      throw new Error("該当する企業が見つかりません: " + companyId);
    }
    var memoColumnIndex = GlowSchema.COMPANY_MASTER_HEADERS.indexOf("関係メモ") + 1;
    var oldMemo = companySheet.getRange(rowIndex, memoColumnIndex).getValue();

    appendMemoUpdateInteractionLog_(companyId, oldMemo);

    companySheet.getRange(rowIndex, memoColumnIndex).setValue(memo);
  } finally {
    lock.releaseLock();
  }
}
