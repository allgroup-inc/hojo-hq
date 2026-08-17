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

test("buildPostbackData / parsePostbackData: 往復できる", () => {
  const data = lineVoiceLogContent.buildPostbackData("selectCompany", "P-123", "C000001");
  const parsed = lineVoiceLogContent.parsePostbackData(data);
  assert.deepEqual(parsed, { action: "selectCompany", processId: "P-123", value: "C000001" });
});

test("buildPostbackData: 値に&や=が含まれてもエンコードされ壊れない", () => {
  const data = lineVoiceLogContent.buildPostbackData("selectCompany", "P-1", "A&B=C");
  const parsed = lineVoiceLogContent.parsePostbackData(data);
  assert.equal(parsed.value, "A&B=C");
});

test("buildCompanySelectionPrompt: 候補+見つからないボタンを含む", () => {
  const candidates = [
    { "企業ID": "C000001", "会社名": "沖縄建設" },
    { "企業ID": "C000002", "会社名": "沖縄建設工業" }
  ];
  const prompt = lineVoiceLogContent.buildCompanySelectionPrompt("P-1", candidates);
  assert.equal(prompt.options.length, 3);
  assert.equal(prompt.options[2].label, "見つからない");
  const parsed = lineVoiceLogContent.parsePostbackData(prompt.options[0].data);
  assert.equal(parsed.value, "C000001");
  assert.equal(parsed.action, lineVoiceLogContent.POSTBACK_ACTIONS.SELECT_COMPANY);
});

test("buildCompanySelectionPrompt: 会社名が長い場合はボタンのラベルを20文字以内に切り詰める", () => {
  const longName = "とてもとても長い名前の株式会社沖縄総合建設不動産開発コンサルティング";
  const prompt = lineVoiceLogContent.buildCompanySelectionPrompt("P-1", [{ "企業ID": "C000001", "会社名": longName }]);
  assert.ok(prompt.options[0].label.length <= 20);
});

test("buildNewCompanyConfirmPrompt: Yes/Noボタンを含む", () => {
  const prompt = lineVoiceLogContent.buildNewCompanyConfirmPrompt("P-1", "テスト商事");
  assert.equal(prompt.options.length, 2);
  assert.ok(prompt.text.includes("テスト商事"));
});

test("buildFinalConfirmPrompt: 入力内容がテキストに含まれる", () => {
  const prompt = lineVoiceLogContent.buildFinalConfirmPrompt(
    "P-1", "沖縄建設", "電話", "オーナー社長本人", "見積の話", "来週再訪問"
  );
  assert.ok(prompt.text.includes("沖縄建設"));
  assert.ok(prompt.text.includes("見積の話"));
  assert.equal(prompt.options.length, 2);
});

test("buildCompletionMessage / buildDiscardMessage: 固定文言を返す", () => {
  assert.ok(lineVoiceLogContent.buildCompletionMessage("沖縄建設").includes("沖縄建設"));
  assert.ok(lineVoiceLogContent.buildDiscardMessage().length > 0);
  assert.ok(lineVoiceLogContent.buildProcessingErrorMessage().length > 0);
  assert.ok(lineVoiceLogContent.buildStaffNotFoundMessage().length > 0);
  assert.ok(lineVoiceLogContent.buildAlreadyProcessingMessage().length > 0);
});

test("sanitizeSheetText: 数式と解釈される先頭文字はアポストロフィで無害化する", () => {
  assert.equal(lineVoiceLogContent.sanitizeSheetText("=SUM(A1:A2)"), "'=SUM(A1:A2)");
  assert.equal(lineVoiceLogContent.sanitizeSheetText("+1-800-000"), "'+1-800-000");
  assert.equal(lineVoiceLogContent.sanitizeSheetText("-来週再訪問"), "'-来週再訪問");
  assert.equal(lineVoiceLogContent.sanitizeSheetText("@ここから"), "'@ここから");
});

test("sanitizeSheetText: 通常のテキストはそのまま返す(空値は空文字)", () => {
  assert.equal(lineVoiceLogContent.sanitizeSheetText("沖縄建設"), "沖縄建設");
  assert.equal(lineVoiceLogContent.sanitizeSheetText(""), "");
  assert.equal(lineVoiceLogContent.sanitizeSheetText(null), "");
  assert.equal(lineVoiceLogContent.sanitizeSheetText(undefined), "");
});

test("sanitizeSheetText: 二重適用しても増殖しない(冪等)", () => {
  const once = lineVoiceLogContent.sanitizeSheetText("=A1");
  assert.equal(lineVoiceLogContent.sanitizeSheetText(once), once);
});

test("buildInteractionLogRow: 内容メモ・次回アクションをサニタイズする", () => {
  const row = lineVoiceLogContent.buildInteractionLogRow(
    "H-test-2", "C000001", "2026-08-17", "嶺井忍", "電話", "オーナー社長本人", "=1+1", "@来週"
  );
  const headers = schema.INTERACTION_LOG_HEADERS;
  assert.equal(row[headers.indexOf("内容メモ")], "'=1+1");
  assert.equal(row[headers.indexOf("次回アクション")], "'@来週");
});

test("buildNewCompanyRow: 会社名をサニタイズする", () => {
  const row = lineVoiceLogContent.buildNewCompanyRow("C000009", "=cmd");
  const headers = schema.COMPANY_MASTER_HEADERS;
  assert.equal(row[headers.indexOf("会社名")], "'=cmd");
});

test("buildFinalConfirmPrompt: 種別・対応相手は記録時と同じ正規化後の値を表示する", () => {
  const prompt = lineVoiceLogContent.buildFinalConfirmPrompt(
    "P-1", "沖縄建設", "雑談", "不明な人物", "見積の話", "来週再訪問"
  );
  // Geminiの生の値(雑談 / 不明な人物)ではなく、実際に記録される既定値が表示されること
  assert.ok(prompt.text.includes("種別: 面談実施"));
  assert.ok(prompt.text.includes("対応相手: 経理・総務等の窓口担当"));
  assert.ok(!prompt.text.includes("雑談"));
  assert.ok(!prompt.text.includes("不明な人物"));

  const row = lineVoiceLogContent.buildInteractionLogRow(
    "H-test-3", "C000001", "2026-08-17", "嶺井忍", "雑談", "不明な人物", "見積の話", "来週再訪問"
  );
  const headers = schema.INTERACTION_LOG_HEADERS;
  assert.equal(row[headers.indexOf("種別")], "面談実施");
  assert.equal(row[headers.indexOf("対応相手")], "経理・総務等の窓口担当");
});

test("buildAlreadyHandledMessage: 処理済み案内の固定文言を返す", () => {
  assert.equal(lineVoiceLogContent.buildAlreadyHandledMessage(), "この記録はすでに処理済みか、無効になっています。");
});
