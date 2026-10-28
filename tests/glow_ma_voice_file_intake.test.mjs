import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const v = require("../glow-ma/src/voiceFileIntake.js");

const STAFF = [
  { name: "福田", email: "Staff.A@example.com", lineUserId: "Uaaa" },
  { name: "未登録LINE", email: "staff.b@example.com", lineUserId: "" },
];

test("録音アプリの形式(WAV/AAC/M4A/MP3)を受け付け、それ以外や受付済みは受け付けない", () => {
  assert.ok(v.isAcceptableFileName("面談_1026.wav"));
  assert.ok(v.isAcceptableFileName("A社.AAC"));
  assert.ok(v.isAcceptableFileName("memo.m4a"));
  assert.ok(!v.isAcceptableFileName("議事録.txt"));
  assert.ok(!v.isAcceptableFileName("受付済_面談_1026.wav"));
  assert.equal(v.audioMimeType("x.wav"), "audio/wav");
  assert.equal(v.audioMimeType("x.aac"), "audio/aac");
});

test("スタッフのメールアドレス(大文字小文字を区別しない)で担当者を決める", () => {
  const plan = v.planIntake([{ id: "f1", name: "a.wav", ownerEmail: "staff.a@example.com" }], STAFF, [], []);
  assert.equal(plan.accept.length, 1);
  assert.equal(plan.accept[0].staff.lineUserId, "Uaaa");
});

test("LINE User ID が無い担当者・スタッフ外のファイルは受け付けず、理由を返す", () => {
  const plan = v.planIntake([
    { id: "f1", name: "a.wav", ownerEmail: "staff.b@example.com" },
    { id: "f2", name: "b.wav", ownerEmail: "other@example.com" },
  ], STAFF, [], []);
  assert.equal(plan.accept.length, 0);
  assert.equal(plan.skip.length, 2);
});

test("同じ担当者の録音は1件ずつ(処理中があれば待つ・同時に2件は受けない)", () => {
  const two = v.planIntake([
    { id: "f1", name: "a.wav", ownerEmail: "staff.a@example.com" },
    { id: "f2", name: "b.wav", ownerEmail: "staff.a@example.com" },
  ], STAFF, [], []);
  assert.equal(two.accept.length, 1);
  const busy = v.planIntake([{ id: "f1", name: "a.wav", ownerEmail: "staff.a@example.com" }], STAFF, [], ["Uaaa"]);
  assert.equal(busy.accept.length, 0);
});

test("既に受け付けたファイル(処理状況にある)は二度と受け付けない", () => {
  const plan = v.planIntake([{ id: "f1", name: "a.wav", ownerEmail: "staff.a@example.com" }], STAFF, ["drive:f1"], []);
  assert.equal(plan.accept.length, 0);
  assert.equal(v.driveFileIdOf("drive:f1"), "f1");
  assert.equal(v.driveFileIdOf("123456"), "");
});

test("分割アップロードの区切り: 16MiBずつ、最後だけ端数", () => {
  const MB = 1024 * 1024;
  const total = 40 * MB;
  const a = v.nextChunk(0, total);
  assert.deepEqual(a, { start: 0, end: 16 * MB - 1, isLast: false });
  const c = v.nextChunk(32 * MB, total);
  assert.deepEqual(c, { start: 32 * MB, end: total - 1, isLast: true });
  assert.equal(v.nextChunk(total, total), null);
  assert.equal((16 * MB) % (8 * MB), 0, "途中の区切りは 8MiB の倍数");
});

test("送信位置のずれ(wrong offset)から、Gemini が待っている位置を取り出す", () => {
  const body = '{"error":{"code":400,"message":"Client uploaded to the wrong offset (134217728 instead of 117440512)."}}';
  assert.equal(v.expectedUploadOffset(body), 117440512);
  assert.equal(v.expectedUploadOffset("Client uploaded to the wrong offset (0 instead of 16777216)."), 16777216);
  assert.equal(v.expectedUploadOffset("HTTP 500 Internal error"), null);
  assert.equal(v.expectedUploadOffset(""), null);
});

test("ファイル名のヒントは受付済みの印と拡張子を外して渡す", () => {
  assert.match(v.fileNameHint("受付済_株式会社テスト_1026.wav"), /「株式会社テスト_1026」/);
  assert.equal(v.fileNameHint(""), "");
});

test("1人が複数のメールアドレス(区切りは , 、 ; 空白)を登録でき、どれから入れても受け付ける", () => {
  assert.deepEqual(v.staffEmails("A@example.com, b@example.com、c@example.com"), ["a@example.com", "b@example.com", "c@example.com"]);
  assert.deepEqual(v.staffEmails(""), []);
  assert.deepEqual(v.staffEmails("メモ"), []);
  const staff = [{ name: "福田", email: "work@example.com\nDrive@example.com", lineUserId: "Uaaa" }];
  const plan = v.planIntake([{ id: "f1", name: "a.wav", ownerEmail: "drive@example.com" }], staff, [], []);
  assert.equal(plan.accept.length, 1);
  assert.equal(plan.accept[0].staff.name, "福田");
});

test("Geminiの支払いエラー(402)を見分ける(一時的な混雑・ほかのエラーとは区別する)", () => {
  const e = new Error("x"); e.statusCode = 402;
  assert.ok(v.isBillingError(e));
  assert.ok(v.isBillingError("Error: Geminiへのアップロード開始に失敗しました(HTTP 402)"));
  assert.ok(v.isBillingError("Error: Gemini APIの呼び出しに失敗しました(ステータスコード 402): {}"));
  assert.ok(!v.isBillingError("Error: Gemini APIの呼び出しに失敗しました(ステータスコード 429): {}"));
  assert.ok(!v.isBillingError("HTTP 4021"));
  assert.ok(!v.isBillingError(null));
});

test("確認ボタンの期限は、確認を送った日(日本時間)の翌日の正午", () => {
  const jst = (s) => Date.parse(s + "+09:00");
  assert.equal(v.confirmDeadlineMs(jst("2026-10-28T17:41:00")), jst("2026-10-29T12:00:00"));
  assert.equal(v.confirmDeadlineMs(jst("2026-10-28T08:00:00")), jst("2026-10-29T12:00:00"));
  assert.equal(v.confirmDeadlineMs(jst("2026-10-29T00:30:00")), jst("2026-10-30T12:00:00"), "日本時間の日付で数える(UTCでは前日)");
  assert.equal(v.confirmDeadlineMs(jst("2026-12-31T23:59:00")), jst("2027-01-01T12:00:00"));
});
