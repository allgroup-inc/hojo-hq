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
