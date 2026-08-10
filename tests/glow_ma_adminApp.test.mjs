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

test("buildAdminAppHtml: 書き込み系のgoogle.script.run呼び出しを一切含まない(読み取り専用の担保)", () => {
  const html = adminApp.buildAdminAppHtml();
  ["shareCompanyWithStaff", "saveRelationMemo", "appendInteractionLog"].forEach((forbidden) => {
    assert.equal(html.indexOf(forbidden), -1, forbidden + " への呼び出しが含まれてはいけない(Phase 18b以降の機能)");
  });
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
