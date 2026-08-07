import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const shippingContent = require("../glow-ma/src/shippingContent.js");

test("computeFollowUpDate: 発送日からN日後の日付をyyyy-MM-dd形式で返す", () => {
  assert.equal(shippingContent.computeFollowUpDate("2026-08-07", 10), "2026-08-17");
});

test("computeFollowUpDate: 月をまたぐ場合も正しく計算する", () => {
  assert.equal(shippingContent.computeFollowUpDate("2026-08-25", 10), "2026-09-04");
});

test("computeFollowUpDate: 不正な日付や空文字ならnullを返す", () => {
  assert.equal(shippingContent.computeFollowUpDate("", 10), null);
  assert.equal(shippingContent.computeFollowUpDate(null, 10), null);
  assert.equal(shippingContent.computeFollowUpDate("不正な値", 10), null);
});

test("computeFollowUpDate: Dateオブジェクト(getValues由来)でも計算できる", () => {
  assert.equal(shippingContent.computeFollowUpDate(new Date(2026, 7, 7), 10), "2026-08-17");
});

test("buildShippingCsvRows: 指定した発送日に一致する下書きのみ、企業マスタと突合してCSV行を作る", () => {
  const letterDrafts = [
    { 下書きID: "D-1", 企業ID: "C000001", 発送日: "2026-08-10" },
    { 下書きID: "D-2", 企業ID: "C000002", 発送日: "2026-08-11" }
  ];
  const companies = [
    { 企業ID: "C000001", 会社名: "テスト商事株式会社", 所在地: "沖縄県那覇市1-1-1", 窓口担当者名: "山田" },
    { 企業ID: "C000002", 会社名: "サンプル建設株式会社", 所在地: "沖縄県浦添市2-2-2", 窓口担当者名: "田中" }
  ];
  const rows = shippingContent.buildShippingCsvRows(letterDrafts, companies, "2026-08-10");
  assert.deepEqual(rows, [
    ["発送日", "企業ID", "会社名", "所在地", "窓口担当者名"],
    ["2026-08-10", "C000001", "テスト商事株式会社", "沖縄県那覇市1-1-1", "山田"]
  ]);
});

test("buildShippingCsvRows: 発送日が未入力の下書きは対象外", () => {
  const letterDrafts = [{ 下書きID: "D-1", 企業ID: "C000001", 発送日: "" }];
  const companies = [{ 企業ID: "C000001", 会社名: "テスト商事株式会社" }];
  const rows = shippingContent.buildShippingCsvRows(letterDrafts, companies, "2026-08-10");
  assert.deepEqual(rows, [["発送日", "企業ID", "会社名", "所在地", "窓口担当者名"]]);
});

test("buildShippingCsvRows: 一致する発送日がなければヘッダー行のみ返す", () => {
  const rows = shippingContent.buildShippingCsvRows([], [], "2026-08-10");
  assert.deepEqual(rows, [["発送日", "企業ID", "会社名", "所在地", "窓口担当者名"]]);
});

test("buildShippingCsvRows: 企業マスタに一致する企業が見つからない下書き行はスキップする(障害隔離)", () => {
  const letterDrafts = [{ 下書きID: "D-1", 企業ID: "C999999", 発送日: "2026-08-10" }];
  const rows = shippingContent.buildShippingCsvRows(letterDrafts, [], "2026-08-10");
  assert.deepEqual(rows, [["発送日", "企業ID", "会社名", "所在地", "窓口担当者名"]]);
});

test("buildShippingCsvRows: 発送日がDateオブジェクト(getValues由来)でも突合できる", () => {
  const letterDrafts = [
    { 下書きID: "D-1", 企業ID: "C000001", 発送日: new Date(2026, 7, 10) }
  ];
  const companies = [
    { 企業ID: "C000001", 会社名: "テスト商事株式会社", 所在地: "沖縄県那覇市1-1-1", 窓口担当者名: "山田" }
  ];
  const rows = shippingContent.buildShippingCsvRows(letterDrafts, companies, "2026-08-10");
  assert.deepEqual(rows, [
    ["発送日", "企業ID", "会社名", "所在地", "窓口担当者名"],
    ["2026-08-10", "C000001", "テスト商事株式会社", "沖縄県那覇市1-1-1", "山田"]
  ]);
});

test("toCsvString: カンマを含む値をダブルクォートで囲む", () => {
  const rows = [["発送日", "会社名"], ["2026-08-10", "テスト,商事株式会社"]];
  assert.equal(
    shippingContent.toCsvString(rows),
    '発送日,会社名\r\n2026-08-10,"テスト,商事株式会社"'
  );
});

test("toCsvString: ダブルクォートを含む値は二重にしてエスケープする", () => {
  const rows = [["会社名"], ['テスト"商事"株式会社']];
  assert.equal(
    shippingContent.toCsvString(rows),
    '会社名\r\n"テスト""商事""株式会社"'
  );
});

test("toCsvString: 空配列なら空文字列を返す", () => {
  assert.equal(shippingContent.toCsvString([]), "");
});
