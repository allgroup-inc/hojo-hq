import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const schema = require("../glow-ma/src/schema.js");

test("4つのシート全てのヘッダー定義が配列で存在する", () => {
  assert.ok(Array.isArray(schema.COMPANY_MASTER_HEADERS));
  assert.ok(Array.isArray(schema.INTERACTION_LOG_HEADERS));
  assert.ok(Array.isArray(schema.PARTNER_MASTER_HEADERS));
  assert.ok(Array.isArray(schema.SETTINGS_HEADERS));
});

test("企業マスタのヘッダーに重複がない", () => {
  const unique = new Set(schema.COMPANY_MASTER_HEADERS);
  assert.equal(unique.size, schema.COMPANY_MASTER_HEADERS.length);
});

test("企業マスタに設計書5.1節の必須列が含まれる", () => {
  const required = [
    "企業ID", "法人番号", "会社名", "流入ルート", "起点担当者_紹介元",
    "現在ステージ", "提案商品", "総合スコア", "ランク", "次回アクション予定日"
  ];
  required.forEach((col) => {
    assert.ok(schema.COMPANY_MASTER_HEADERS.includes(col), `${col} が企業マスタに必要`);
  });
});

test("対応履歴ログに対応相手の列が含まれる(設計書5.2節)", () => {
  assert.ok(schema.INTERACTION_LOG_HEADERS.includes("対応相手"));
});

test("紹介パートナーマスタに紹介料率と逆紹介履歴の列が含まれる(設計書5.3節)", () => {
  assert.ok(schema.PARTNER_MASTER_HEADERS.includes("紹介料率"));
  assert.ok(schema.PARTNER_MASTER_HEADERS.includes("逆紹介履歴"));
});
