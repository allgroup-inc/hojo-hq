import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const lineVoiceLogContent = require("../glow-ma/src/lineVoiceLogContent.js");
const schema = require("../glow-ma/src/schema.js");

test("matchCompanyCandidates: 完全一致は部分一致より先頭に来る", () => {
  const companies = [
    { "企業ID": "C000001", "会社名": "沖縄建設" },
    { "企業ID": "C000002", "会社名": "沖縄建設工業" }
  ];
  const result = lineVoiceLogContent.matchCompanyCandidates(companies, "沖縄建設");
  assert.equal(result.length, 2);
  assert.equal(result[0]["企業ID"], "C000001");
});

test("matchCompanyCandidates: 一致する企業が無ければ空配列", () => {
  const companies = [{ "企業ID": "C000001", "会社名": "沖縄建設" }];
  const result = lineVoiceLogContent.matchCompanyCandidates(companies, "存在しない商事");
  assert.deepEqual(result, []);
});

test("matchCompanyCandidates: spokenNameが空なら空配列", () => {
  const companies = [{ "企業ID": "C000001", "会社名": "沖縄建設" }];
  assert.deepEqual(lineVoiceLogContent.matchCompanyCandidates(companies, ""), []);
  assert.deepEqual(lineVoiceLogContent.matchCompanyCandidates(companies, null), []);
});

test("matchCompanyCandidates: 最大5件までに絞られる", () => {
  const companies = [];
  for (let i = 1; i <= 8; i++) {
    companies.push({ "企業ID": "C00000" + i, "会社名": "沖縄商事" + i });
  }
  const result = lineVoiceLogContent.matchCompanyCandidates(companies, "沖縄商事");
  assert.equal(result.length, 5);
});

test("normalizeInteractionType: 既知の種別はそのまま返す", () => {
  assert.equal(lineVoiceLogContent.normalizeInteractionType("電話"), "電話");
});

test("normalizeInteractionType: 未知の値は既定値(面談実施)にフォールバックする", () => {
  assert.equal(lineVoiceLogContent.normalizeInteractionType("雑談"), "面談実施");
  assert.equal(lineVoiceLogContent.normalizeInteractionType(""), "面談実施");
});

test("normalizeRespondentType: 既知の対応相手はそのまま返す", () => {
  assert.equal(lineVoiceLogContent.normalizeRespondentType("オーナー社長本人"), "オーナー社長本人");
});

test("normalizeRespondentType: 未知の値は既定値(経理・総務等の窓口担当)にフォールバックする", () => {
  assert.equal(lineVoiceLogContent.normalizeRespondentType("不明な人物"), "経理・総務等の窓口担当");
});

test("buildInteractionLogRow: INTERACTION_LOG_HEADERSの並び順で配列を返す", () => {
  const row = lineVoiceLogContent.buildInteractionLogRow(
    "H-test-1", "C000001", "2026-08-17", "嶺井忍", "電話", "オーナー社長本人", "内容メモ本文", "次回訪問"
  );
  assert.deepEqual(row, [
    "H-test-1", "C000001", "2026-08-17", "嶺井忍", "電話", "オーナー社長本人", "内容メモ本文", "次回訪問"
  ]);
  assert.equal(row.length, schema.INTERACTION_LOG_HEADERS.length);
});

test("buildInteractionLogRow: 種別・対応相手は正規化される", () => {
  const row = lineVoiceLogContent.buildInteractionLogRow(
    "H-test-2", "C000001", "2026-08-17", "嶺井忍", "雑談", "不明", "メモ", ""
  );
  const typeIndex = schema.INTERACTION_LOG_HEADERS.indexOf("種別");
  const respondentIndex = schema.INTERACTION_LOG_HEADERS.indexOf("対応相手");
  assert.equal(row[typeIndex], "面談実施");
  assert.equal(row[respondentIndex], "経理・総務等の窓口担当");
});

test("buildNewCompanyRow: 企業ID・会社名以外は空欄、連絡不要はfalse", () => {
  const row = lineVoiceLogContent.buildNewCompanyRow("C009999", "テスト新規企業");
  assert.equal(row.length, schema.COMPANY_MASTER_HEADERS.length);
  const idIndex = schema.COMPANY_MASTER_HEADERS.indexOf("企業ID");
  const nameIndex = schema.COMPANY_MASTER_HEADERS.indexOf("会社名");
  const dncIndex = schema.COMPANY_MASTER_HEADERS.indexOf("連絡不要");
  assert.equal(row[idIndex], "C009999");
  assert.equal(row[nameIndex], "テスト新規企業");
  assert.equal(row[dncIndex], false);
  row.forEach((value, index) => {
    if (index === idIndex || index === nameIndex || index === dncIndex) return;
    assert.equal(value, "");
  });
});
