import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const qrContent = require("../glow-ma/src/qrContent.js");

test("buildQrManifestRows: 指定した発送日に一致する下書きのみ、企業マスタと突合してトラッキングURL付きの一覧を作る", () => {
  const letterDrafts = [
    { 下書きID: "D-1", 企業ID: "C000001", 発送日: "2026-08-20" },
    { 下書きID: "D-2", 企業ID: "C000002", 発送日: "2026-08-21" }
  ];
  const companies = [
    { 企業ID: "C000001", 会社名: "テスト商事株式会社" },
    { 企業ID: "C000002", 会社名: "サンプル建設株式会社" }
  ];
  const rows = qrContent.buildQrManifestRows(
    letterDrafts, companies, "2026-08-20", "https://example.com/track"
  );
  assert.deepEqual(rows, [
    { "企業ID": "C000001", "会社名": "テスト商事株式会社", trackingUrl: "https://example.com/track?id=C000001" }
  ]);
});

test("buildQrManifestRows: 発送日が未入力の下書きは対象外", () => {
  const letterDrafts = [{ 下書きID: "D-1", 企業ID: "C000001", 発送日: "" }];
  const companies = [{ 企業ID: "C000001", 会社名: "テスト商事株式会社" }];
  const rows = qrContent.buildQrManifestRows(
    letterDrafts, companies, "2026-08-20", "https://example.com/track"
  );
  assert.deepEqual(rows, []);
});

test("buildQrManifestRows: 一致する発送日がなければ空配列を返す", () => {
  const rows = qrContent.buildQrManifestRows([], [], "2026-08-20", "https://example.com/track");
  assert.deepEqual(rows, []);
});

test("buildQrManifestRows: 企業マスタに一致する企業が見つからない下書き行はスキップする(障害隔離)", () => {
  const letterDrafts = [{ 下書きID: "D-1", 企業ID: "C999999", 発送日: "2026-08-20" }];
  const rows = qrContent.buildQrManifestRows(letterDrafts, [], "2026-08-20", "https://example.com/track");
  assert.deepEqual(rows, []);
});

test("buildQrManifestRows: 発送日がDateオブジェクト(getValues由来)でも突合できる", () => {
  const letterDrafts = [{ 下書きID: "D-1", 企業ID: "C000001", 発送日: new Date(2026, 7, 20) }];
  const companies = [{ 企業ID: "C000001", 会社名: "テスト商事株式会社" }];
  const rows = qrContent.buildQrManifestRows(
    letterDrafts, companies, "2026-08-20", "https://example.com/track"
  );
  assert.deepEqual(rows, [
    { "企業ID": "C000001", "会社名": "テスト商事株式会社", trackingUrl: "https://example.com/track?id=C000001" }
  ]);
});

test("buildQrManifestRows: baseUrlが空ならトラッキングURLが組み立てられないため対象外", () => {
  const letterDrafts = [{ 下書きID: "D-1", 企業ID: "C000001", 発送日: "2026-08-20" }];
  const companies = [{ 企業ID: "C000001", 会社名: "テスト商事株式会社" }];
  const rows = qrContent.buildQrManifestRows(letterDrafts, companies, "2026-08-20", "");
  assert.deepEqual(rows, []);
});
