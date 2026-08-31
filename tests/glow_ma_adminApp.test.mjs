import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const adminApp = require("../glow-ma/src/adminApp.js");

test("buildAdminAppHtml: 検索・絞り込み・一覧テーブル・詳細ドロワーの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["searchInput", "filterRank", "filterStage", "filterOwner", "companyTableBody", "drawer", "paneOverview", "paneHistory"]
    .forEach((id) => {
      assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
    });
});

test("buildAdminAppHtml: ランクの選択肢はA/B/C/Dの4つ(固定)", () => {
  const html = adminApp.buildAdminAppHtml();
  ["A", "B", "C", "D"].forEach((rank) => {
    assert.ok(html.indexOf('<option value="' + rank + '">') !== -1, "ランク" + rank + "の選択肢がない");
  });
});

test("buildAdminAppHtml: google.script.runでgetCompanyList・getCompanyDetail・getFilterOptionsを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getCompanyList(") !== -1);
  assert.ok(html.indexOf(".getCompanyDetail(") !== -1);
  assert.ok(html.indexOf(".getFilterOptions(") !== -1);
});

test("buildAdminAppHtml: google.script.runでupdateCompanyMemoを呼ぶ(Phase 18b: 関係メモ編集)", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".updateCompanyMemo(") !== -1);
});

test("buildAdminAppHtml: 想定外の書き込み系google.script.run呼び出しを含まない", () => {
  const html = adminApp.buildAdminAppHtml();
  ["appendInteractionLog", "addPartner", "logPartnerInteraction", "recordReferral"].forEach((forbidden) => {
    assert.equal(html.indexOf(forbidden), -1, forbidden + " への呼び出しが含まれてはいけない(未実装の機能)");
  });
});

test("buildAdminAppHtml: 企業詳細ドロワーに関係メモ編集用の要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["memoEditBtn", "memoValue", "memoTextarea", "memoEditControls", "memoSaveBtn", "memoCancelBtn", "memoStatus"]
    .forEach((id) => {
      assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
    });
});

test("buildAdminAppHtml: 関係メモの保存に成功/失敗した場合の表示分岐を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf("保存しました") !== -1, "保存成功時のメッセージがない");
  assert.ok(html.indexOf("保存に失敗しました") !== -1, "保存失敗時のメッセージがない");
});

test("buildAdminAppHtml: 未保存の変更がある状態でドロワーを閉じようとすると確認する", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf("confirm(") !== -1, "confirm()による離脱確認がない");
  assert.ok(html.indexOf("保存されていない変更があります") !== -1, "離脱確認のメッセージがない");
});

test("buildAdminAppHtml: 画面切り替えスイッチャー・パートナー一覧・パートナードロワーの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["viewCompanyBtn", "viewPartnerBtn", "companyView", "partnerView", "partnerTableBody",
   "partnerEmptyState", "partnerDrawer", "partnerDrawerName", "partnerDrawerId", "partnerDrawerClose"]
    .forEach((id) => {
      assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
    });
});

test("buildAdminAppHtml: google.script.runでgetPartnerListを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getPartnerList(") !== -1);
});

test("buildAdminAppHtml: パートナードロワーに概要・対応履歴・紹介実績の3タブを含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["tabPartnerOverviewBtn", "tabPartnerHistoryBtn", "tabPartnerReferralsBtn",
   "panePartnerOverview", "panePartnerHistory", "panePartnerReferrals"]
    .forEach((id) => {
      assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
    });
});

test("buildAdminAppHtml: google.script.runでgetPartnerDetailを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getPartnerDetail(") !== -1);
});

test("buildAdminAppHtml: 書き込み系のgoogle.script.run呼び出しを一切含まない(紹介パートナー開拓状況ビューも読み取り専用)", () => {
  const html = adminApp.buildAdminAppHtml();
  ["addPartner", "logPartnerInteraction", "recordReferral"].forEach((forbidden) => {
    assert.equal(html.indexOf(forbidden), -1, forbidden + " への呼び出しが含まれてはいけない(後続フェーズの機能)");
  });
});

test("buildAdminAppHtml: 生成されるクライアントスクリプトが構文エラーを含まない", () => {
  const html = adminApp.buildAdminAppHtml();
  const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
  assert.doesNotThrow(() => new Function(script));
});

test("buildAdminAppHtml: コーポレートカラーの変数とロゴのアニメーションを含む", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf("--kin:#F88800") !== -1 || html.indexOf("--kin: #F88800") !== -1,
    "コーポレートカラー(金)が定義されていない");
  assert.ok(html.indexOf("logoGlow") !== -1, "ロゴの光るアニメーションが定義されていない");
  assert.ok(html.indexOf("prefers-reduced-motion") !== -1, "reduced-motion対応がない");
});

test("buildAdminAppHtml: 企業詳細の電話番号・携帯番号がtel:リンクとして出力される(BlueBeanクリック発信対応)", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.match(
    html,
    /href="tel:' \+ escapeHtml\(String\(f\[1\]\)\.replace\(\/\[\^0-9\+\]\/g,''\)\)/,
    "電話番号/携帯番号をtel:リンクにするコードが含まれていない"
  );
  assert.ok(html.indexOf("isPhoneField") !== -1, "電話番号フィールドの判定ロジックが含まれていない");
});

test("buildAdminAppHtml: ホーム画面追加(PWA風)に必要なメタタグ・アイコンを含む", () => {
  const html = adminApp.buildAdminAppHtml();
  [
    'rel="icon"',
    'rel="apple-touch-icon"',
    'name="apple-mobile-web-app-capable" content="yes"',
    'name="mobile-web-app-capable" content="yes"',
    'name="theme-color" content="#00335c"'
  ].forEach((needle) => {
    assert.ok(html.indexOf(needle) !== -1, needle + " が含まれていない");
  });
});

test("buildAdminAppHtml: 企業一覧にチェックボックス選択とQR用CSV出力の仕組みが組み込まれている", () => {
  const html = adminApp.buildAdminAppHtml();
  [
    'id="selectAllCheckbox"',
    'id="qrExportBar"',
    'id="qrExportBtn"',
    'id="qrExportClearBtn"',
    'id="qrExportModal"',
    'id="qrExportRunBtn"',
    'class="row-check"',
    "getQrExportForSelectedCompanies"
  ].forEach((needle) => {
    assert.ok(html.indexOf(needle) !== -1, needle + " が含まれていない");
  });
});

test("buildAdminAppHtml: 使い方ガイド(howto)のマークアップが実際に出力される(CSS定義だけでなくアコーディオン本体を確認)", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf('class="howto"') !== -1, "class=\"howto\" の使い方ガイドがヘッダー直後に出力されていない");
  assert.ok(html.indexOf("使い方ガイド") !== -1, "使い方ガイドの見出しテキストが含まれていない");
  assert.ok(html.indexOf("データが蓄積される仕組み") !== -1, "データ蓄積の仕組みの説明が含まれていない");
});

test("buildAdminAppHtml: 一覧テーブルの次回アクション列にurgencyドットのマークアップが出力される(CSS定義だけでなく実際の描画コードを確認)", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.match(
    html,
    /class="dot ' \+ escapeHtml\(row\.urgency/,
    "drawTableの行テンプレートにurgencyドット(class=\"dot ...\")が組み込まれていない"
  );
});

test("buildAdminAppHtml: ヘッダーに実際のロゴ画像要素が出力される(CSS定義だけでなくマークアップ自体を確認)", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.match(
    html,
    /<img class="topbar-logo"[^>]*src="data:image\/(png|svg\+xml);base64,[A-Za-z0-9+/=]+"/,
    "topbar-logoクラスの<img>要素がヘッダーに出力されていない(CSSのlogoGlow定義だけでは画面に何も表示されない)"
  );
});

test("buildAdminAppHtml: KPIカード・緊急度ドット・ランクバッジ用のCSSクラスを含む", () => {
  const html = adminApp.buildAdminAppHtml();
  [".kpi{", ".rank-A{", ".rank-B{", ".rank-C{", ".rank-D{", ".dot.overdue{", ".dot.soon{", ".dot.ok{"]
    .forEach((selector) => {
      assert.ok(html.indexOf(selector) !== -1, selector + " が定義されていない");
    });
});

test("buildAdminAppHtml: 流入ルート・提案商品の絞り込みと、列ソート用の見出しを含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["filterRoute", "filterProduct"].forEach((id) => {
    assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
  });
  ["data-sort=\"name\"", "data-sort=\"biz\"", "data-sort=\"route\"", "data-sort=\"stage\"",
   "data-sort=\"products\"", "data-sort=\"rank\"", "data-sort=\"next\""]
    .forEach((attr) => {
      assert.ok(html.indexOf(attr) !== -1, attr + " が含まれていない");
    });
});

test("buildAdminAppHtml: google.script.runでgetFilterOptionsの結果からroute/product選択肢を組み立てる", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf("options.routes") !== -1, "流入ルート選択肢の組み立てがない");
  assert.ok(html.indexOf("options.products") !== -1, "提案商品選択肢の組み立てがない");
});

test("buildAdminAppHtml: KPI行とKPIモーダルの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["kpiRow", "kpiModal", "kmTitle", "kmSub", "kmBody"].forEach((id) => {
    assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
  });
});

test("buildAdminAppHtml: google.script.runでgetKpiSummaryを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getKpiSummary(") !== -1);
});

test("buildAdminAppHtml: ネクストアクション・ワークロードパネルの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["queue", "workloadList"].forEach((id) => {
    assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
  });
});

test("buildAdminAppHtml: google.script.runでgetNextActionQueue・getOwnerWorkloadを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getNextActionQueue(") !== -1);
  assert.ok(html.indexOf(".getOwnerWorkload(") !== -1);
});

test("buildAdminAppHtml: ドロワーに🤝連携ボタンと共有モーダルの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["shareBtn", "shareModal", "shareTitle", "shareStaffList", "shareNote", "sharePreview", "shareSendBtn"]
    .forEach((id) => {
      assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
    });
});

test("buildAdminAppHtml: google.script.runでgetShareableStaffList・shareCompanyWithStaffを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getShareableStaffList(") !== -1);
  assert.ok(html.indexOf(".shareCompanyWithStaff(") !== -1);
});

test("buildAdminAppHtml: renderDrawerで連絡不要フラグをshareTargetDncに反映する", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf("shareTargetDnc") !== -1 && /shareTargetDnc\s*=\s*!!/.test(html),
    "renderDrawer内でshareTargetDncへの代入が見つからない");
});

test("buildAdminAppHtml: レター下書きプレビューボタン・モーダルの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  ["letterPreviewBtn", "letterPreviewModal", "letterPreviewBody"].forEach((id) => {
    assert.ok(html.indexOf('id="' + id + '"') !== -1, id + " が含まれていない");
  });
});

test("buildAdminAppHtml: google.script.runでgetLatestLetterDraftを呼ぶ", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf(".getLatestLetterDraft(") !== -1);
});

test("buildAdminAppHtml: ドロワー・オーバーレイ・タブに、Task8で導入したCSS(.scrim/.drawer/.tab)が適用されるクラスが付与されている(最終レビュー Finding 1)", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf('class="scrim" id="overlay"') !== -1, "overlayにclass=scrimがない");
  assert.ok(html.indexOf('class="scrim" id="partnerOverlay"') !== -1, "partnerOverlayにclass=scrimがない");
  assert.ok(html.indexOf('class="drawer" id="drawer"') !== -1, "drawerにclass=drawerがない");
  assert.ok(html.indexOf('class="drawer" id="partnerDrawer"') !== -1, "partnerDrawerにclass=drawerがない");
  assert.ok(html.indexOf('class="drawer-head" id="drawerHeader"') !== -1, "drawerHeaderにclass=drawer-headがない");
  assert.ok(html.indexOf('class="drawer-content" id="drawerBody"') !== -1, "drawerBodyにclass=drawer-contentがない");
  assert.ok(html.indexOf('class="tab active" id="tabOverviewBtn"') !== -1, "tabOverviewBtnにclass=tab activeがない");
  assert.ok(html.indexOf('class="tab" id="tabHistoryBtn"') !== -1, "tabHistoryBtnにclass=tabがない");
});

test("buildAdminAppHtml: STYLE内に.scrim/.drawer/.drawer.open/.tab/.tab.activeのCSSルールが定義されている(最終レビュー Finding 1)", () => {
  const html = adminApp.buildAdminAppHtml();
  [".scrim{", ".drawer{", ".drawer.open{", ".drawer-head{", ".drawer-content{", ".tab{", ".tab.active{"]
    .forEach((selector) => {
      assert.ok(html.indexOf(selector) !== -1, selector + " が定義されていない");
    });
});

test("buildAdminAppHtml: .app/.body-gridでラップされ、KPI行・企業テーブル・サイドパネルが二カラムレイアウトの対象になっている(最終レビュー再検証 Fix 4)", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.indexOf('class="app"') !== -1, "class=\"app\" が含まれていない");
  assert.ok(html.indexOf('class="body-grid"') !== -1, "class=\"body-grid\" が含まれていない");
  const idxBodyGrid = html.indexOf('class="body-grid"');
  ['id="kpiRow"', 'id="companyTableBody"', 'id="queue"'].forEach((needle) => {
    const idx = html.indexOf(needle);
    assert.ok(idx > idxBodyGrid, needle + " が class=\"body-grid\" より後(内側)にない");
  });
});

test("buildAdminAppHtml: デモに存在しないPhase 18a/18b由来のUI(viewSwitcher/viewPane/empty/btn-small/memoTextarea)のCSSが復元されている(最終レビュー Finding 1)", () => {
  const html = adminApp.buildAdminAppHtml();
  ["#viewSwitcher{", "#viewSwitcher button{", "#viewSwitcher button.active{", ".viewPane{", ".viewPane.active{",
   "header{", ".empty{", ".btn-small{", ".btn-primary{", "#memoTextarea{", "#memoEditControls{",
   "#memoStatus{", "#memoStatus.error{", ".field{", ".field .label{", ".field .value{"]
    .forEach((selector) => {
      assert.ok(html.indexOf(selector) !== -1, selector + " が定義されていない");
    });
});

test("buildAdminAppHtml: 列見出しに矢印アイコンとソート状態管理・クリックハンドラを含む(設計§4)", () => {
  const html = adminApp.buildAdminAppHtml();
  ["name", "biz", "route", "stage", "products", "rank", "next"].forEach((key) => {
    const th = html.indexOf('data-sort="' + key + '"');
    assert.ok(th !== -1, key + " 列の見出しがない");
    const nextTh = html.indexOf("</th>", th);
    const arrowInThisHeader = html.indexOf('<span class="arrow">▾</span>', th);
    assert.ok(
      arrowInThisHeader !== -1 && arrowInThisHeader < nextTh,
      key + " 列に矢印アイコンが含まれていない"
    );
  });
  const arrowCount = (html.match(/<span class="arrow">▾<\/span>/g) || []).length;
  assert.equal(arrowCount, 7, "ソート可能な7列すべてに矢印スパンが必要");
  assert.ok(html.indexOf("var sortKey = null;") !== -1, "sortKey状態変数がない");
  assert.ok(html.indexOf("var sortDir = 1;") !== -1, "sortDir状態変数がない");
  assert.ok(html.indexOf("function getSortedRows()") !== -1, "getSortedRows関数がない");
  assert.ok(html.indexOf("function updateSortIndicators()") !== -1, "updateSortIndicators関数がない");
  assert.ok(html.indexOf("thead th[data-sort]") !== -1, "ソート見出しへのクリックハンドラ登録がない");
  assert.ok(html.indexOf("sortDir = -sortDir") !== -1, "昇順・降順トグルロジックがない");
});

test("buildAdminAppHtml: getSortedRowsが7列すべてに対応する比較ロジックを持つ", () => {
  const html = adminApp.buildAdminAppHtml();
  ["case 'name':", "case 'biz':", "case 'route':", "case 'stage':", "case 'products':",
   "case 'rank':", "case 'next':"]
    .forEach((caseLine) => {
      assert.ok(html.indexOf(caseLine) !== -1, caseLine + " の比較ロジックがない");
    });
  assert.ok(html.indexOf("rankOrder") !== -1, "ランクの並び順定義(A<B<C<D)がない");
});

test("buildAdminAppHtml: パートナービューに「新規パートナー登録」ボタンと登録モーダルの主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("id=\"partnerAddBtn\""));
  assert.ok(html.includes("新規パートナー登録"));
  assert.ok(html.includes("id=\"partnerRegModal\""));
  assert.ok(html.includes("id=\"partnerRegName\""));
  assert.ok(html.includes("id=\"partnerRegType\""));
  assert.ok(html.includes("id=\"partnerRegOwner\""));
  assert.ok(html.includes("id=\"partnerRegRank\""));
  assert.ok(html.includes("id=\"partnerRegRate\""));
  assert.ok(html.includes("id=\"partnerRegMemo\""));
  assert.ok(html.includes("id=\"partnerRegLastContact\""));
  assert.ok(html.includes("id=\"partnerRegNextAction\""));
  assert.ok(html.includes("id=\"partnerRegSubmitBtn\""));
  assert.ok(html.includes("id=\"partnerRegStatus\""));
});

test("buildAdminAppHtml: 種別・関係性ランクの選択肢はスキーマ(PARTNER_TYPES/PARTNER_RANKS)から生成される", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("<option value=\"銀行\">銀行</option>"));
  assert.ok(html.includes("<option value=\"信用金庫\">信用金庫</option>"));
  assert.ok(html.includes("<option value=\"その他\">その他</option>"));
  assert.ok(html.includes("<option value=\"A\">A(最重要・強い関係)</option>"));
  assert.ok(html.includes("<option value=\"D\">D(接点づくり中)</option>"));
});

test("buildAdminAppHtml: google.script.runでregisterPartnerを呼び、成功時に一覧を再読み込みする", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(/google\.script\.run[\s\S]{0,900}\.registerPartner\(input\)/.test(html));
  assert.ok(html.includes("function submitPartnerRegistration()"));
  assert.ok(html.includes("function openPartnerRegModal()"));
  assert.ok(html.includes("function closePartnerRegModal()"));
});

test("buildAdminAppHtml: 使い方ガイドにパートナー登録の説明がある", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("紹介パートナー開拓状況」タブ"));
});

test("buildAdminAppHtml: 要対応ポップアップ(リマインダーモーダル)の主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("id=\"reminderModal\""));
  assert.ok(html.includes("id=\"reminderList\""));
  assert.ok(html.includes("id=\"reminderCloseBtn\""));
  assert.ok(html.includes("本日の要対応"));
  assert.ok(html.includes("function renderReminders("));
  // bootstrapの応答からremindersを受け取って表示する
  assert.ok(html.includes("renderReminders(data.reminders"));
});

test("buildAdminAppHtml: リマインダーの行クリックで企業詳細が開く", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(/reminderList[\s\S]{0,900}openDrawer\(/.test(html));
});

test("buildAdminAppHtml: ヘッダーにアプリのバージョンが表示される", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("id=\"appVersion\""));
  assert.ok(/v\d+\.\d+\.\d+/.test(html));
});

test("buildAdminAppHtml: 使い方ガイドに「更新履歴」セクションがあり、直近の変更が載っている", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("④ 更新履歴"));
  assert.ok(html.includes("新規パートナー登録"));
  assert.ok(html.includes("本日の要対応ポップアップ"));
});

test("buildAdminAppHtml: 訪問・架電スケジュールビュー(第3タブ)の主要要素を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("id=\"viewScheduleBtn\""));
  assert.ok(html.includes("id=\"scheduleView\""));
  assert.ok(html.includes("id=\"scheduleOwnerFilter\""));
  assert.ok(html.includes("id=\"scheduleList\""));
  assert.ok(html.includes("id=\"scheduleRefreshBtn\""));
  assert.ok(html.includes(".getVisitSchedule("));
  assert.ok(html.includes("function renderSchedule("));
});

test("buildAdminAppHtml: switchViewが3ビュー(企業・パートナー・スケジュール)を切り替える", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(/scheduleView'\)\.classList\.toggle\('active', isSchedule\)/.test(html));
  assert.ok(html.includes("target === 'schedule'"));
});

test("buildAdminAppHtml: 企業詳細に次回アクションの編集欄(日付・内容・クイックボタン・保存)を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("id=\"naDate\""));
  assert.ok(html.includes("id=\"naNote\""));
  assert.ok(html.includes("id=\"naSaveBtn\""));
  assert.ok(html.includes("id=\"naStatus\""));
  assert.ok(html.includes("data-days=\"1\""));
  assert.ok(html.includes("data-days=\"7\""));
  assert.ok(html.includes(".updateNextAction("));
});

test("buildAdminAppHtml: 要対応ポップアップは1回の閲覧で1度だけ表示される(保存後の再取得で再ポップアップしない)", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("remindersShown"));
});

test("buildAdminAppHtml: バージョンがv1.2.0に上がり、更新履歴にスケジュール表の説明がある", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("v1.2.0"));
  assert.ok(html.includes("訪問・架電スケジュール"));
});

test("buildAdminAppHtml: スケジュールタブに行動量ダッシュボード(実績パネル)を含む", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("id=\"activityPanel\""));
  assert.ok(html.includes("function renderActivity("));
  assert.ok(html.includes("行動量(直近4週の実績)"));
  // スケジュールと同じ応答(activity)から描画し、担当者絞り込みにも連動する
  assert.ok(html.includes("scheduleData.activity"));
});

test("buildAdminAppHtml: バージョンがv1.3.0に上がり、更新履歴に行動量ダッシュボードの説明がある", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("v1.3.0"));
  assert.ok(html.includes("行動量"));
});

// ---- v1.3.1 使いやすさ改善 ----

test("buildAdminAppHtml: 日付欄はすべてカレンダー選択式(type=date)で手打ち不要", () => {
  const html = adminApp.buildAdminAppHtml();
  ["naDate", "partnerRegLastContact", "partnerRegNextAction", "qrExportDateInput"].forEach((id) => {
    const pattern = new RegExp('<input type="date"[^>]*id="' + id + '"');
    assert.match(html, pattern, id + " がtype=dateになっていない");
  });
});

test("buildAdminAppHtml: Escキーで開いているモーダル・詳細画面を閉じられる", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("ev.key !== 'Escape'") || html.includes("ev.key === 'Escape'"));
  // 会社ドロワーは未保存メモの確認(closeDrawer)を通す
  assert.ok(/Escape[\s\S]{0,900}closeDrawer\(\)/.test(html));
});

test("buildAdminAppHtml: 起動直後に読み込み中の表示を出す(数秒の空白画面を防ぐ)", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("読み込み中…"));
  assert.ok(/読み込み中[\s\S]{0,2200}loadBootstrap\(\);/.test(html));
});

test("buildAdminAppHtml: KPIの数値は桁区切りで表示する(3212→3,212)", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("toLocaleString"));
});

test("buildAdminAppHtml: パートナー0件のときは次の行動(新規パートナー登録)を案内する", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("まだ登録されたパートナーがありません"));
});

test("buildAdminAppHtml: 次回アクションの入力欄でEnterを押すと保存される", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(/naDate[\s\S]{0,400}Enter[\s\S]{0,200}saveNextAction/.test(html) ||
    /\['naDate','naNote'\][\s\S]{0,300}Enter/.test(html));
});

test("buildAdminAppHtml: バージョンがv1.3.1に上がっている", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("v1.3.1"));
});

test("buildAdminAppHtml: バージョンがv1.4.0に上がり、更新履歴にLINE連携強化の説明がある", () => {
  const html = adminApp.buildAdminAppHtml();
  assert.ok(html.includes("v1.4.0"));
  assert.ok(html.includes("見込みコメント"));
});
