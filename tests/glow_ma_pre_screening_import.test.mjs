import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const preScreeningImport = require("../glow-ma/src/preScreeningImport.js");

test("normalizeCompanyName: 前後の空白を除去する", () => {
  assert.equal(preScreeningImport.normalizeCompanyName("  太田建設株式会社  "), "太田建設株式会社");
});

test("normalizeCompanyName: 全角スペースを除去する", () => {
  assert.equal(preScreeningImport.normalizeCompanyName("株式会社　つながり"), "株式会社つながり");
});

test("normalizeCompanyName: 文中の半角・全角スペースもすべて除去する", () => {
  assert.equal(preScreeningImport.normalizeCompanyName("有限会社 ケア センター"), "有限会社ケアセンター");
});

test("normalizeCompanyName: 全角英数字を半角に変換する", () => {
  assert.equal(preScreeningImport.normalizeCompanyName("株式会社ＷＡＮ　ＳＴＹＬＥ１２３"), "株式会社WANSTYLE123");
});

test("normalizeCompanyName: 空文字・null・undefinedは空文字を返す", () => {
  assert.equal(preScreeningImport.normalizeCompanyName(""), "");
  assert.equal(preScreeningImport.normalizeCompanyName(null), "");
  assert.equal(preScreeningImport.normalizeCompanyName(undefined), "");
});

const SAMPLE_COMPANIES = [
  { "企業ID": "C000001", "会社名": "太田建設株式会社" },
  { "企業ID": "C000002", "会社名": "株式会社　南西工業" },
  { "企業ID": "C000003", "会社名": "仲程土建株式会社" }
];

test("matchPreScreeningRows: 正規化した会社名が一致した行をmatchesに含める", () => {
  const stagingRows = [
    { "会社名": "太田建設株式会社", "事前選定ランク": "仮S", "事前選定スコア": "37" }
  ];
  const result = preScreeningImport.matchPreScreeningRows(stagingRows, SAMPLE_COMPANIES);
  assert.deepEqual(result.matches, [
    { "企業ID": "C000001", "事前選定ランク": "仮S", "事前選定スコア": "37" }
  ]);
  assert.deepEqual(result.unmatchedNames, []);
});

test("matchPreScreeningRows: 空白の入り方(半角/全角)が違っても同じ会社名なら一致する", () => {
  const stagingRows = [
    // 企業マスタ側は「株式会社　南西工業」(全角スペース)。半角スペース版でも一致するはずの確認
    { "会社名": "株式会社 南西工業", "事前選定ランク": "A", "事前選定スコア": "29" }
  ];
  const result = preScreeningImport.matchPreScreeningRows(stagingRows, SAMPLE_COMPANIES);
  assert.deepEqual(result.matches, [
    { "企業ID": "C000002", "事前選定ランク": "A", "事前選定スコア": "29" }
  ]);
  assert.deepEqual(result.unmatchedNames, []);
});

test("matchPreScreeningRows: 部分一致では一致しない(完全一致のみ)", () => {
  const stagingRows = [
    // 企業マスタ側は「株式会社　南西工業」であり、「南西工業」だけでは一致しない
    { "会社名": "南西工業", "事前選定ランク": "A", "事前選定スコア": "29" }
  ];
  const result = preScreeningImport.matchPreScreeningRows(stagingRows, SAMPLE_COMPANIES);
  assert.deepEqual(result.matches, []);
  assert.deepEqual(result.unmatchedNames, ["南西工業"]);
});

test("matchPreScreeningRows: 一致しない行はunmatchedNamesに元の会社名(正規化前)で入る", () => {
  const stagingRows = [
    { "会社名": "存在しない株式会社", "事前選定ランク": "B", "事前選定スコア": "10" }
  ];
  const result = preScreeningImport.matchPreScreeningRows(stagingRows, SAMPLE_COMPANIES);
  assert.deepEqual(result.matches, []);
  assert.deepEqual(result.unmatchedNames, ["存在しない株式会社"]);
});

test("matchPreScreeningRows: 複数行を正しく振り分ける", () => {
  const stagingRows = [
    { "会社名": "太田建設株式会社", "事前選定ランク": "仮S", "事前選定スコア": "37" },
    { "会社名": "株式会社南西工業", "事前選定ランク": "仮S", "事前選定スコア": "37" },
    { "会社名": "未知の会社", "事前選定ランク": "C", "事前選定スコア": "5" }
  ];
  const result = preScreeningImport.matchPreScreeningRows(stagingRows, SAMPLE_COMPANIES);
  assert.equal(result.matches.length, 2);
  assert.deepEqual(result.unmatchedNames, ["未知の会社"]);
});

test("applyMatchesToCompanyRecords: 一致した企業のみ事前選定ランク・スコアを更新する", () => {
  const companyRecords = [
    { "企業ID": "C000001", "会社名": "太田建設株式会社", "事前選定ランク": "", "事前選定スコア": "" },
    { "企業ID": "C000002", "会社名": "株式会社南西工業", "事前選定ランク": "", "事前選定スコア": "" }
  ];
  const matches = [{ "企業ID": "C000001", "事前選定ランク": "仮S", "事前選定スコア": "37" }];
  const result = preScreeningImport.applyMatchesToCompanyRecords(companyRecords, matches);
  assert.equal(result[0]["事前選定ランク"], "仮S");
  assert.equal(result[0]["事前選定スコア"], "37");
  assert.equal(result[1]["事前選定ランク"], "");
});

test("applyMatchesToCompanyRecords: 入力配列を変更しない", () => {
  const companyRecords = [
    { "企業ID": "C000001", "会社名": "太田建設株式会社", "事前選定ランク": "", "事前選定スコア": "" }
  ];
  const matches = [{ "企業ID": "C000001", "事前選定ランク": "仮S", "事前選定スコア": "37" }];
  preScreeningImport.applyMatchesToCompanyRecords(companyRecords, matches);
  assert.equal(companyRecords[0]["事前選定ランク"], "");
});

test("applyMatchesToCompanyRecords: 事前選定ランクが空欄の一致は既存のランクを保持する(最終レビュー2026-08-11 I4)", () => {
  const companyRecords = [
    { "企業ID": "C000001", "会社名": "太田建設株式会社", "事前選定ランク": "仮S", "事前選定スコア": "37" }
  ];
  const matches = [{ "企業ID": "C000001", "事前選定ランク": "", "事前選定スコア": "20" }];
  const result = preScreeningImport.applyMatchesToCompanyRecords(companyRecords, matches);
  assert.equal(result[0]["事前選定ランク"], "仮S");
  assert.equal(result[0]["事前選定スコア"], "20");
});

test("applyMatchesToCompanyRecords: 事前選定スコアが空欄の一致は既存のスコアを保持する(同 I4)", () => {
  const companyRecords = [
    { "企業ID": "C000001", "会社名": "太田建設株式会社", "事前選定ランク": "仮S", "事前選定スコア": "37" }
  ];
  const matches = [{ "企業ID": "C000001", "事前選定ランク": "仮A", "事前選定スコア": "" }];
  const result = preScreeningImport.applyMatchesToCompanyRecords(companyRecords, matches);
  assert.equal(result[0]["事前選定ランク"], "仮A");
  assert.equal(result[0]["事前選定スコア"], "37");
});

test("applyMatchesToCompanyRecords: 両方が空欄・undefinedの一致は既存値を両方とも保持する(同 I4)", () => {
  const companyRecords = [
    { "企業ID": "C000001", "会社名": "太田建設株式会社", "事前選定ランク": "仮S", "事前選定スコア": "37" },
    { "企業ID": "C000002", "会社名": "株式会社南西工業", "事前選定ランク": "仮A", "事前選定スコア": "30" }
  ];
  const matches = [
    { "企業ID": "C000001", "事前選定ランク": "", "事前選定スコア": "" },
    { "企業ID": "C000002" }
  ];
  const result = preScreeningImport.applyMatchesToCompanyRecords(companyRecords, matches);
  assert.equal(result[0]["事前選定ランク"], "仮S");
  assert.equal(result[0]["事前選定スコア"], "37");
  assert.equal(result[1]["事前選定ランク"], "仮A");
  assert.equal(result[1]["事前選定スコア"], "30");
});

test("applyMatchesToCompanyRecords: 値が揃った一致は従来どおり両方を上書きする(回帰確認)", () => {
  const companyRecords = [
    { "企業ID": "C000001", "会社名": "太田建設株式会社", "事前選定ランク": "仮B", "事前選定スコア": "10" }
  ];
  const matches = [{ "企業ID": "C000001", "事前選定ランク": "仮S", "事前選定スコア": "37" }];
  const result = preScreeningImport.applyMatchesToCompanyRecords(companyRecords, matches);
  assert.equal(result[0]["事前選定ランク"], "仮S");
  assert.equal(result[0]["事前選定スコア"], "37");
});
