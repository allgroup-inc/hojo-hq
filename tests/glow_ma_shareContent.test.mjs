import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const shareContent = require("../glow-ma/src/shareContent.js");

test("buildMapsUrl: 住所をエンコードしたGoogleマップ検索URLを返す", () => {
  assert.equal(
    shareContent.buildMapsUrl("沖縄県那覇市字ぶんとう1-1"),
    "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent("沖縄県那覇市字ぶんとう1-1")
  );
});

test("buildMapsUrl: 住所が空なら空文字列", () => {
  assert.equal(shareContent.buildMapsUrl(""), "");
  assert.equal(shareContent.buildMapsUrl(null), "");
  assert.equal(shareContent.buildMapsUrl(undefined), "");
});

test("buildShareMessage: 会社名・業種・ランク・現在ステージ・地図・連絡先を含む", () => {
  const record = {
    会社名: "テスト商事株式会社", 業種: "建設業", ランク: "A", 現在ステージ: "提案中",
    所在地: "沖縄県那覇市", 電話番号: "098-000-0000", 携帯番号: "090-1111-2222", 窓口担当者名: "金城さん"
  };
  const message = shareContent.buildShareMessage(record, { senderEmail: "takashi@example.com" });
  assert.match(message, /テスト商事株式会社/);
  assert.match(message, /建設業/);
  assert.match(message, /Aランク/);
  assert.match(message, /提案中/);
  assert.match(message, /maps\.google|google\.com\/maps/);
  assert.match(message, /098-000-0000/);
  assert.match(message, /090-1111-2222/);
  assert.match(message, /金城さん/);
  assert.match(message, /送信者: takashi@example\.com/);
});

test("buildShareMessage: 連絡不要企業は警告文を先頭付近に必ず含む", () => {
  const record = { 会社名: "テスト商事株式会社", 連絡不要: true };
  const message = shareContent.buildShareMessage(record, { senderEmail: "takashi@example.com" });
  assert.match(message, /連絡不要/);
  assert.match(message, /架電禁止/);
});

test("buildShareMessage: 連絡不要でない企業には警告文を含まない", () => {
  const record = { 会社名: "テスト商事株式会社", 連絡不要: false };
  const message = shareContent.buildShareMessage(record, { senderEmail: "takashi@example.com" });
  assert.doesNotMatch(message, /架電禁止/);
});

test("buildShareMessage: 関係メモは100文字を超えると切り詰めて…を付ける", () => {
  const longMemo = "あ".repeat(150);
  const record = { 会社名: "テスト商事株式会社", 関係メモ: longMemo };
  const message = shareContent.buildShareMessage(record, { senderEmail: "takashi@example.com" });
  assert.match(message, /あ{100}…/);
  assert.doesNotMatch(message, /あ{101}/);
});

test("buildShareMessage: 関係メモが100文字以下ならそのまま(…を付けない)", () => {
  const record = { 会社名: "テスト商事株式会社", 関係メモ: "決算期は3月" };
  const message = shareContent.buildShareMessage(record, { senderEmail: "takashi@example.com" });
  assert.match(message, /関係メモ: 決算期は3月$/m);
});

test("buildShareMessage: 一言メモ(note)を渡すと本文に含まれる", () => {
  const record = { 会社名: "テスト商事株式会社" };
  const message = shareContent.buildShareMessage(record, { note: "今まさに後継者の話をしています", senderEmail: "takashi@example.com" });
  assert.match(message, /今の状況: 今まさに後継者の話をしています/);
});

test("buildShareMessage: noteを渡さなければ「今の状況」行は出ない", () => {
  const record = { 会社名: "テスト商事株式会社" };
  const message = shareContent.buildShareMessage(record, { senderEmail: "takashi@example.com" });
  assert.doesNotMatch(message, /今の状況/);
});

test("buildShareMessage: 未入力項目(電話番号・携帯番号・窓口担当者名・関係メモ・所在地)があってもエラーにならず該当行を省く", () => {
  const record = { 会社名: "テスト商事株式会社" };
  const message = shareContent.buildShareMessage(record, { senderEmail: "takashi@example.com" });
  assert.doesNotMatch(message, /undefined/);
  assert.doesNotMatch(message, /地図:/);
  assert.doesNotMatch(message, /電話番号/);
});

test("buildShareMessage: senderEmailが無くてもエラーにならない", () => {
  const record = { 会社名: "テスト商事株式会社" };
  const message = shareContent.buildShareMessage(record, {});
  assert.match(message, /送信者: 不明/);
});
