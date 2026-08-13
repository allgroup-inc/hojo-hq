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
