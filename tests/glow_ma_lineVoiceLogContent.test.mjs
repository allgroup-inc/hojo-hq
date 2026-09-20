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

test("isRespondentUncertain: Geminiが「不明」と返した場合はtrue", () => {
  assert.equal(lineVoiceLogContent.isRespondentUncertain("不明"), true);
});

test("isRespondentUncertain: 既知の対応相手や無関係な文字列はfalse", () => {
  assert.equal(lineVoiceLogContent.isRespondentUncertain("オーナー社長本人"), false);
  assert.equal(lineVoiceLogContent.isRespondentUncertain("不明な人物"), false);
  assert.equal(lineVoiceLogContent.isRespondentUncertain(""), false);
  assert.equal(lineVoiceLogContent.isRespondentUncertain(undefined), false);
});

test("buildFinalConfirmPrompt: 対応相手が「不明」の場合は訂正を促す注意書きを付ける", () => {
  const prompt = lineVoiceLogContent.buildFinalConfirmPrompt(
    "P-2", "沖縄建設", "面談実施", "不明", "見積の話", ""
  );
  assert.ok(prompt.text.includes("対応相手: 経理・総務等の窓口担当"));
  assert.ok(prompt.text.includes("⚠️"));
  assert.ok(prompt.text.includes("スプレッドシートで訂正"));
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

// ---- 2026-08-28 追加: 未登録担当者の登録導線と、対応相手が不明なときの追跡可能性 ----

test("buildStaffNotFoundMessage: LINE User IDを渡すと本文に含める(管理者への転送用)", () => {
  const id = "U0123456789abcdef0123456789abcdef";
  const msg = lineVoiceLogContent.buildStaffNotFoundMessage(id);
  assert.ok(msg.includes("担当者が特定できませんでした"));
  assert.ok(msg.includes(id), "IDが本文に含まれること");
});

test("buildStaffNotFoundMessage: 引数なしでも従来どおりの案内を返す", () => {
  const msg = lineVoiceLogContent.buildStaffNotFoundMessage();
  assert.equal(msg, "担当者が特定できませんでした。管理者に「スタッフ」タブへの登録を依頼してください。");
});

test("markMemoIfRespondentUncertain: 不明のときだけ目印を付ける", () => {
  const mark = lineVoiceLogContent.RESPONDENT_REVIEW_MARK;
  assert.equal(
    lineVoiceLogContent.markMemoIfRespondentUncertain("後継者は未定", "不明"),
    mark + " 後継者は未定"
  );
  assert.equal(
    lineVoiceLogContent.markMemoIfRespondentUncertain("後継者は未定", "オーナー社長本人"),
    "後継者は未定"
  );
});

test("markMemoIfRespondentUncertain: 二重に付けない・空メモでも壊れない", () => {
  const mark = lineVoiceLogContent.RESPONDENT_REVIEW_MARK;
  const once = lineVoiceLogContent.markMemoIfRespondentUncertain("メモ", "不明");
  assert.equal(lineVoiceLogContent.markMemoIfRespondentUncertain(once, "不明"), once);
  assert.equal(lineVoiceLogContent.markMemoIfRespondentUncertain("", "不明"), mark);
  assert.equal(lineVoiceLogContent.markMemoIfRespondentUncertain(null, "不明"), mark);
});

test("buildFinalConfirmPrompt: 生の「不明」を渡すと警告が出る(正規化済みだと出なかった不具合の再発防止)", () => {
  const withRaw = lineVoiceLogContent.buildFinalConfirmPrompt(
    "P-1", "テスト建設", "面談実施", "不明", "メモ", "次回"
  );
  assert.ok(withRaw.text.includes("⚠️"), "未判別の警告が出ること");

  // 正規化してから渡すと警告が消える = これが2026-08-28まで起きていた状態
  const normalized = lineVoiceLogContent.normalizeRespondentType("不明");
  const withNormalized = lineVoiceLogContent.buildFinalConfirmPrompt(
    "P-1", "テスト建設", "面談実施", normalized, "メモ", "次回"
  );
  assert.ok(!withNormalized.text.includes("⚠️"));
});

test("buildInteractionLogRow: 「不明」は台帳へ書く時点で必ず3値に正規化される", () => {
  const row = lineVoiceLogContent.buildInteractionLogRow(
    "H-1", "C000001", "2026-09-01", "嶺井", "面談実施", "不明", "メモ", "次回"
  );
  const idx = schema.INTERACTION_LOG_HEADERS.indexOf("対応相手");
  assert.ok(
    schema.RESPONDENT_TYPES.includes(row[idx]),
    "対応履歴ログの入力規則(3値)に必ず収まること"
  );
});

// ---- v1.4: 見込みシグナルの抽出と企業台帳への反映 ----

test("normalizeProspectSignals: 後継者状況・興味商品・次回予定日を検証済みの値に正規化する", () => {
  const signals = lineVoiceLogContent.normalizeProspectSignals({
    successorStatus: "なし",
    interestedProducts: ["M&A", "不動産", "存在しない商品"],
    nextActionDate: "2026-09-10"
  });
  assert.equal(signals.successorStatus, "なし");
  assert.deepEqual(signals.interestedProducts, ["M&A", "不動産"]);
  assert.equal(signals.nextActionDate, "2026-09-10");
});

test("normalizeProspectSignals: 不正な値は空にする(決めつけ禁止・正確性最優先)", () => {
  const signals = lineVoiceLogContent.normalizeProspectSignals({
    successorStatus: "たぶんいない",
    interestedProducts: "M&A",
    nextActionDate: "来週"
  });
  assert.equal(signals.successorStatus, "");
  assert.deepEqual(signals.interestedProducts, []);
  assert.equal(signals.nextActionDate, "");
});

test("normalizeProspectSignals: 未定義でも安全に空を返す", () => {
  const signals = lineVoiceLogContent.normalizeProspectSignals({});
  assert.equal(signals.successorStatus, "");
  assert.deepEqual(signals.interestedProducts, []);
  assert.equal(signals.nextActionDate, "");
});

test("buildProspectUpdates: 最終接触日は常に更新し、要約を関係メモの先頭に日付付きで追記する", () => {
  const record = {
    "種別候補": "面談実施",
    "内容メモ": "社長と面談。業績は堅調だが後継者がいない。",
    "次回アクション": "M&Aの初期資料を持参",
    "後継者状況候補": "なし",
    "興味商品候補": "M&A",
    "次回予定日候補": "2026-09-10"
  };
  const company = {
    "企業ID": "C1", "関係メモ": "既存のメモ", "提案商品": [],
    "後継者状況": "不明"
  };
  const result = lineVoiceLogContent.buildProspectUpdates(record, company, "2026-08-31");
  assert.equal(result.updates["最終接触日"], "2026-08-31");
  assert.equal(result.updates["次回アクション予定日"], "2026-09-10");
  assert.equal(result.updates["次回アクション内容"], "M&Aの初期資料を持参");
  assert.equal(result.updates["後継者状況"], "なし");
  assert.equal(result.updates["提案商品"], "M&A");
  assert.ok(result.updates["関係メモ"].startsWith("【2026-08-31 面談実施(LINE音声)】社長と面談。"));
  assert.ok(result.updates["関係メモ"].includes("▶次: M&Aの初期資料を持参"));
  assert.ok(result.updates["関係メモ"].endsWith("既存のメモ"));
});

test("buildProspectUpdates: 変わらない項目は更新に含めない(後継者状況が同じ・興味商品が既登録)", () => {
  const record = {
    "種別候補": "電話", "内容メモ": "近況確認",
    "次回アクション": "", "後継者状況候補": "なし",
    "興味商品候補": "M&A", "次回予定日候補": ""
  };
  const company = {
    "企業ID": "C1", "関係メモ": "", "提案商品": ["M&A"], "後継者状況": "なし"
  };
  const result = lineVoiceLogContent.buildProspectUpdates(record, company, "2026-08-31");
  assert.equal(result.updates["後継者状況"], undefined);
  assert.equal(result.updates["提案商品"], undefined);
  assert.equal(result.updates["次回アクション予定日"], undefined);
  assert.equal(result.updates["次回アクション内容"], undefined);
  assert.equal(result.updates["最終接触日"], "2026-08-31");
});

test("buildProspectUpdates: 後継者状況候補「不明」は既存の値を上書きしない", () => {
  const record = {
    "種別候補": "電話", "内容メモ": "", "次回アクション": "",
    "後継者状況候補": "不明", "興味商品候補": "", "次回予定日候補": ""
  };
  const company = { "企業ID": "C1", "関係メモ": "", "提案商品": [], "後継者状況": "あり" };
  const result = lineVoiceLogContent.buildProspectUpdates(record, company, "2026-08-31");
  assert.equal(result.updates["後継者状況"], undefined);
  assert.equal(result.updates["関係メモ"], undefined);
});

test("buildProspectUpdates: 提案商品は既存とマージして「、」区切りで返す(既存が文字列でも配列でも)", () => {
  const record = {
    "種別候補": "電話", "内容メモ": "", "次回アクション": "",
    "後継者状況候補": "", "興味商品候補": "不動産、法人保険", "次回予定日候補": ""
  };
  const asArray = lineVoiceLogContent.buildProspectUpdates(record, { "提案商品": ["M&A"], "関係メモ": "" }, "2026-08-31");
  assert.equal(asArray.updates["提案商品"], "M&A、不動産、法人保険");
  const asString = lineVoiceLogContent.buildProspectUpdates(record, { "提案商品": "M&A", "関係メモ": "" }, "2026-08-31");
  assert.equal(asString.updates["提案商品"], "M&A、不動産、法人保険");
});

test("buildProspectUpdates: 関係メモが長くなりすぎたら古い側を切り詰める(上限6000文字)", () => {
  const record = {
    "種別候補": "電話", "内容メモ": "新しい要約", "次回アクション": "",
    "後継者状況候補": "", "興味商品候補": "", "次回予定日候補": ""
  };
  const company = { "関係メモ": "あ".repeat(7000), "提案商品": [] };
  const result = lineVoiceLogContent.buildProspectUpdates(record, company, "2026-08-31");
  assert.ok(result.updates["関係メモ"].length <= 6000);
  assert.ok(result.updates["関係メモ"].startsWith("【2026-08-31 電話(LINE音声)】新しい要約"));
  assert.ok(result.updates["関係メモ"].includes("(古いメモは省略)"));
});

test("buildProspectUpdateSummaryMessage: 台帳に反映した項目を人が読める1通にまとめる", () => {
  const message = lineVoiceLogContent.buildProspectUpdateSummaryMessage({
    "最終接触日": "2026-08-31",
    "次回アクション予定日": "2026-09-10",
    "関係メモ": "【…】…",
    "後継者状況": "なし",
    "提案商品": "M&A、不動産"
  });
  assert.equal(typeof message, "string");
  assert.ok(message.includes("台帳にも反映しました"));
  assert.ok(message.includes("次回予定: 2026-09-10"));
  assert.ok(message.includes("後継者状況: なし"));
  assert.ok(message.includes("関係メモに要約を追記"));
  assert.ok(message.includes("興味あり商品: M&A、不動産"));
});

test("buildProspectUpdateSummaryMessage: 最終接触日だけの場合も成立する", () => {
  const message = lineVoiceLogContent.buildProspectUpdateSummaryMessage({ "最終接触日": "2026-08-31" });
  assert.ok(message.includes("台帳にも反映しました"));
  assert.ok(message.includes("最終接触日"));
});

// --- 一時的な障害の再試行(2026-09-03 GeminiのHTTP 503で訪問メモが失われた件) ---

test("isTransientProcessingError: 429と5xxだけを再試行対象と判定する", () => {
  const withStatus = (statusCode) => Object.assign(new Error("x"), { statusCode });
  assert.equal(lineVoiceLogContent.isTransientProcessingError(withStatus(503)), true);
  assert.equal(lineVoiceLogContent.isTransientProcessingError(withStatus(500)), true);
  assert.equal(lineVoiceLogContent.isTransientProcessingError(withStatus(429)), true);
  // 認証切れ・モデル廃止・入力不正は再試行しても直らない(2026-08-18に401と404で実際に失敗している)
  assert.equal(lineVoiceLogContent.isTransientProcessingError(withStatus(401)), false);
  assert.equal(lineVoiceLogContent.isTransientProcessingError(withStatus(404)), false);
  assert.equal(lineVoiceLogContent.isTransientProcessingError(new Error("statusCodeなし")), false);
  assert.equal(lineVoiceLogContent.isTransientProcessingError(null), false);
});

test("parseTransientRetryCount: 未記録なら0、記録済みならその回数を読む", () => {
  assert.equal(lineVoiceLogContent.parseTransientRetryCount(""), 0);
  assert.equal(lineVoiceLogContent.parseTransientRetryCount(null), 0);
  assert.equal(lineVoiceLogContent.parseTransientRetryCount("Error: 何かの失敗"), 0);
  assert.equal(lineVoiceLogContent.parseTransientRetryCount("再試行中(3/10) Error: 503"), 3);
});

test("buildTransientRetryNote: 回数が1ずつ増え、元のメッセージも残る", () => {
  const first = lineVoiceLogContent.buildTransientRetryNote("", "Error: 503");
  assert.ok(first.startsWith("再試行中(1/10)"));
  assert.ok(first.includes("Error: 503"));
  const second = lineVoiceLogContent.buildTransientRetryNote(first, "Error: 503");
  assert.equal(lineVoiceLogContent.parseTransientRetryCount(second), 2);
});

test("hasTransientRetryLeft: 上限に達したら再試行しない", () => {
  assert.equal(lineVoiceLogContent.hasTransientRetryLeft(""), true);
  const atLimit = "再試行中(" + lineVoiceLogContent.MAX_TRANSIENT_RETRIES + "/10) Error: 503";
  assert.equal(lineVoiceLogContent.hasTransientRetryLeft(atLimit), false);
});

test("再試行の記録は何度重ねても上限を超えたら止まる(無限ループしない)", () => {
  let note = "";
  for (let i = 0; i < 50; i++) {
    if (!lineVoiceLogContent.hasTransientRetryLeft(note)) break;
    note = lineVoiceLogContent.buildTransientRetryNote(note, "Error: 503");
  }
  assert.equal(
    lineVoiceLogContent.parseTransientRetryCount(note),
    lineVoiceLogContent.MAX_TRANSIENT_RETRIES
  );
});

test("buildTransientRetryExhaustedMessage: 録り直しを促す文面になっている", () => {
  const message = lineVoiceLogContent.buildTransientRetryExhaustedMessage();
  assert.ok(message.includes("もう一度録音"));
});
