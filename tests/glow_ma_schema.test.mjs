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

test("4つのシート全てのヘッダー定義が空配列でない", () => {
  assert.ok(schema.COMPANY_MASTER_HEADERS.length > 0);
  assert.ok(schema.INTERACTION_LOG_HEADERS.length > 0);
  assert.ok(schema.PARTNER_MASTER_HEADERS.length > 0);
  assert.ok(schema.SETTINGS_HEADERS.length > 0);
});

test("4つのシート名が期待する文字列と完全一致する", () => {
  assert.equal(schema.COMPANY_MASTER_SHEET_NAME, "企業マスタ");
  assert.equal(schema.INTERACTION_LOG_SHEET_NAME, "対応履歴ログ");
  assert.equal(schema.PARTNER_MASTER_SHEET_NAME, "紹介パートナーマスタ");
  assert.equal(schema.SETTINGS_SHEET_NAME, "設定");
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

test("対応履歴ログの対応相手(RESPONDENT_TYPES)が設計書5.2節の3種と一致する", () => {
  assert.deepEqual(schema.RESPONDENT_TYPES, ["オーナー社長本人", "経理・総務等の窓口担当", "未接触"]);
});

test("対応履歴ログの種別(INTERACTION_TYPES)が設計書5.2節の15種+連絡不要受領+工程遷移イベントと一致する", () => {
  const expected = [
    "手紙送付", "電話", "ゆんたく相談実施", "面談実施", "紹介受領", "ミカタ接点確認",
    "レターURLアクセス", "返信", "資料請求",
    "提案(M&A)", "提案(不動産)", "提案(法人保険)",
    "成約", "見送り", "ナーチャリング配信", "連絡不要受領",
    "NDA締結", "意向表明受領", "DD開始"
  ];
  assert.deepEqual(schema.INTERACTION_TYPES, expected);
});

test("レター下書きタブの名称・見出し・種別・ステータスが定義されている", () => {
  assert.equal(schema.LETTER_DRAFT_SHEET_NAME, "レター下書き");
  assert.deepEqual(schema.LETTER_DRAFT_HEADERS, [
    "下書きID", "企業ID", "種別", "生成日時", "本文", "ステータス"
  ]);
  assert.deepEqual(schema.LETTER_DRAFT_TYPES, ["初回DM", "ナーチャリング配信"]);
  assert.deepEqual(schema.LETTER_DRAFT_STATUSES, ["下書き", "送付済み", "見送り"]);
});

test("ダッシュボードタブの名称・プレースホルダー見出しが定義されている", () => {
  assert.equal(schema.DASHBOARD_SHEET_NAME, "ダッシュボード");
  assert.deepEqual(schema.DASHBOARD_PLACEHOLDER_HEADERS, [
    "ダッシュボード(updateDashboardを実行すると内容が生成されます)"
  ]);
});

test("企業マスタに電話番号・連絡不要列が追加されている", () => {
  assert.ok(schema.COMPANY_MASTER_HEADERS.indexOf("電話番号") !== -1);
  assert.ok(schema.COMPANY_MASTER_HEADERS.indexOf("連絡不要") !== -1);
});

test("対応履歴ログの種別に連絡不要受領が追加されている", () => {
  assert.ok(schema.INTERACTION_TYPES.indexOf("連絡不要受領") !== -1);
});

test("ダッシュボード履歴タブの名称・見出しが定義されている", () => {
  assert.equal(schema.DASHBOARD_HISTORY_SHEET_NAME, "ダッシュボード履歴");
  assert.deepEqual(schema.DASHBOARD_HISTORY_HEADERS, [
    "記録日時", "対象企業数",
    "ランクA_滞留企業数", "ランクB_滞留企業数", "ランクC_滞留企業数", "ランクD_滞留企業数",
    "掘り起こし待ち件数合計", "成約企業数", "連絡不要企業数"
  ]);
});
