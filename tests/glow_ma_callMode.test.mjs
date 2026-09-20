import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const callMode = require("../glow-ma/src/callMode.js");

const TODAY = "2026-09-03"; // 木曜日

// ---- buildCallQueue(架電リストの並び順・除外規則) ----

test("buildCallQueue: 連絡不要・電話番号なし・本日接触済みの企業を除外する", () => {
  const companies = [
    { "企業ID": "C1", "会社名": "対象", "電話番号": "098-1", "連絡不要": false, "最終接触日": "2026-08-01", "ランク": "B" },
    { "企業ID": "C2", "会社名": "連絡不要", "電話番号": "098-2", "連絡不要": true, "ランク": "A" },
    { "企業ID": "C3", "会社名": "番号なし", "電話番号": "", "連絡不要": false, "ランク": "A" },
    { "企業ID": "C4", "会社名": "本日接触済み", "電話番号": "098-4", "連絡不要": false, "最終接触日": "2026-09-03", "ランク": "A" }
  ];
  const queue = callMode.buildCallQueue(companies, TODAY);
  assert.deepEqual(queue.map((e) => e["企業ID"]), ["C1"]);
});

test("buildCallQueue: ランク順(A→D)→期限超過の古い順→未着手の順に並ぶ", () => {
  const companies = [
    { "企業ID": "B未着手", "会社名": "b", "電話番号": "1", "連絡不要": false, "ランク": "B" },
    { "企業ID": "A未着手", "会社名": "a", "電話番号": "1", "連絡不要": false, "ランク": "A" },
    { "企業ID": "A超過古い", "会社名": "a", "電話番号": "1", "連絡不要": false, "ランク": "A", "次回アクション予定日": "2026-08-01" },
    { "企業ID": "A超過新しい", "会社名": "a", "電話番号": "1", "連絡不要": false, "ランク": "A", "次回アクション予定日": "2026-09-01" },
    { "企業ID": "A将来", "会社名": "a", "電話番号": "1", "連絡不要": false, "ランク": "A", "次回アクション予定日": "2026-10-01" }
  ];
  const queue = callMode.buildCallQueue(companies, TODAY);
  assert.deepEqual(queue.map((e) => e["企業ID"]),
    ["A超過古い", "A超過新しい", "A未着手", "A将来", "B未着手"]);
});

test("buildCallQueue: 返す項目は架電に必要な最小限で、日付は文字列に正規化される(google.script.run対策)", () => {
  const companies = [
    { "企業ID": "C1", "会社名": "テスト社", "代表者名": "山田", "電話番号": "098-000-0000",
      "連絡不要": false, "ランク": "A", "現在ステージ": "未接触", "担当者": "小柳",
      "次回アクション予定日": new Date(2026, 7, 1), "次回アクション内容": "再架電",
      "最終接触日": new Date(2026, 6, 1), "関係メモ": "含めない大きな項目" }
  ];
  const queue = callMode.buildCallQueue(companies, TODAY);
  assert.equal(queue[0]["次回アクション予定日"], "2026-08-01");
  assert.equal(queue[0]["最終接触日"], "2026-07-01");
  assert.equal(queue[0]["代表者名"], "山田");
  assert.equal(queue[0]["関係メモ"], undefined);
});

// ---- 日付ヘルパー ----

test("addBusinessDays: 土日を飛ばして営業日で足す(木+3営業日=火)", () => {
  assert.equal(callMode.addBusinessDays("2026-09-03", 3), "2026-09-08");
  assert.equal(callMode.addBusinessDays("2026-09-04", 3), "2026-09-09"); // 金→水
});

test("addMonths: 月末はみ出しは月末に丸める(8/31+6ヶ月=2/28)", () => {
  assert.equal(callMode.addMonths("2026-08-31", 6), "2027-02-28");
  assert.equal(callMode.addMonths("2026-09-03", 6), "2027-03-03");
});

// ---- resolveCallOutcome(結果→記録・次回アクションの変換規則) ----

test("resolveCallOutcome: 不在 → 電話で記録し、3営業日後に再架電を自動設定", () => {
  const r = callMode.resolveCallOutcome("不在", TODAY, {});
  assert.equal(r.ok, true);
  assert.equal(r.type, "電話");
  assert.equal(r.nextDate, "2026-09-08");
  assert.ok(r.nextNote.includes("再架電"));
});

test("resolveCallOutcome: 話せた → メモと選んだ次回予定を反映", () => {
  const r = callMode.resolveCallOutcome("話せた", TODAY, { memo: "資料送付の約束", nextDate: "2026-09-10" });
  assert.equal(r.ok, true);
  assert.equal(r.type, "電話");
  assert.equal(r.memo, "資料送付の約束");
  assert.equal(r.nextDate, "2026-09-10");
});

test("resolveCallOutcome: アポ獲得 → 種別アポ獲得+面談日必須", () => {
  const ok = callMode.resolveCallOutcome("アポ獲得", TODAY, { apptDate: "2026-09-12" });
  assert.equal(ok.ok, true);
  assert.equal(ok.type, "アポ獲得");
  assert.equal(ok.nextDate, "2026-09-12");
  assert.ok(ok.nextNote.includes("面談"));
  const bad = callMode.resolveCallOutcome("アポ獲得", TODAY, {});
  assert.equal(bad.ok, false);
});

test("resolveCallOutcome: 断り(時期が合わない)だけは6ヶ月後の再掘り起こしを自動設定", () => {
  const recycle = callMode.resolveCallOutcome("断り", TODAY, { reason: "時期が合わない" });
  assert.equal(recycle.ok, true);
  assert.equal(recycle.type, "見送り");
  assert.equal(recycle.nextDate, "2027-03-03");
  assert.ok(recycle.nextNote.includes("再掘り起こし"));
  const drop = callMode.resolveCallOutcome("断り", TODAY, { reason: "必要ない" });
  assert.equal(drop.nextDate, "");
  const bad = callMode.resolveCallOutcome("断り", TODAY, { reason: "知らない理由" });
  assert.equal(bad.ok, false);
});

test("resolveCallOutcome: 番号違い → 記録のみで次回予定は設定しない", () => {
  const r = callMode.resolveCallOutcome("番号違い", TODAY, {});
  assert.equal(r.ok, true);
  assert.ok(r.memo.includes("番号違い"));
  assert.equal(r.nextDate, "");
});

test("resolveCallOutcome: 未知の結果はok:false", () => {
  assert.equal(callMode.resolveCallOutcome("謎の結果", TODAY, {}).ok, false);
});

test("CALL_RULES: 日数ルールが定数として1箇所にまとまっている(運用で調整可能)", () => {
  assert.equal(callMode.CALL_RULES.RETRY_BUSINESS_DAYS, 3);
  assert.equal(callMode.CALL_RULES.RECYCLE_MONTHS, 6);
  assert.deepEqual(callMode.CALL_RULES.REJECT_REASONS,
    ["時期が合わない", "必要ない", "他社利用中", "その他"]);
});
