import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const dedupe = require("../glow-ma/src/dedupe.js");
const schema = require("../glow-ma/src/schema.js");

test("normalizeCorporateNumber: 13桁の数字はそのまま正規化される", () => {
  assert.equal(dedupe.normalizeCorporateNumber("1234567890123"), "1234567890123");
});

test("normalizeCorporateNumber: ハイフンや空白が入っていても13桁なら正規化される", () => {
  assert.equal(dedupe.normalizeCorporateNumber(" 1234-5678-90123 "), "1234567890123");
});

test("normalizeCorporateNumber: 13桁でない場合はnull", () => {
  assert.equal(dedupe.normalizeCorporateNumber("123456789012"), null);
});

test("normalizeCorporateNumber: null/undefined/空文字はnull", () => {
  assert.equal(dedupe.normalizeCorporateNumber(null), null);
  assert.equal(dedupe.normalizeCorporateNumber(undefined), null);
  assert.equal(dedupe.normalizeCorporateNumber(""), null);
});

test("findDuplicateGroups: 同じ法人番号のレコードが1グループにまとまる", () => {
  const companies = [
    { 企業ID: "C000001", 法人番号: "1234567890123" },
    { 企業ID: "C000002", 法人番号: "1234567890123" },
    { 企業ID: "C000003", 法人番号: "9999999999999" }
  ];
  const groups = dedupe.findDuplicateGroups(companies);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].length, 2);
  assert.deepEqual(groups[0].map((c) => c.企業ID), ["C000001", "C000002"]);
});

test("findDuplicateGroups: 重複がなければ空配列", () => {
  const companies = [
    { 企業ID: "C000001", 法人番号: "1234567890123" },
    { 企業ID: "C000002", 法人番号: "9999999999999" }
  ];
  assert.deepEqual(dedupe.findDuplicateGroups(companies), []);
});

test("findDuplicateGroups: 法人番号が空のレコードはグループ化対象外", () => {
  const companies = [
    { 企業ID: "C000001", 法人番号: "" },
    { 企業ID: "C000002", 法人番号: "" }
  ];
  assert.deepEqual(dedupe.findDuplicateGroups(companies), []);
});

test("mergeCompanyRecords: 流入ルートと提案商品は重複なく統合される", () => {
  const records = [
    { 企業ID: "C000001", 会社名: "テスト商事株式会社", 流入ルート: ["①紹介"], 提案商品: [], 備考: "" },
    { 企業ID: "C000002", 会社名: "", 流入ルート: ["②手紙DM"], 提案商品: ["法人保険"], 備考: "" }
  ];
  const { merged, absorbedIds } = dedupe.mergeCompanyRecords(records);
  assert.deepEqual(merged.流入ルート, ["①紹介", "②手紙DM"]);
  assert.deepEqual(merged.提案商品, ["法人保険"]);
  assert.deepEqual(absorbedIds, ["C000002"]);
});

test("mergeCompanyRecords: スカラー項目は先頭レコードの値を優先し、空なら後続を採用する", () => {
  const records = [
    { 企業ID: "C000001", 会社名: "", 業種: "小売業", 流入ルート: [], 提案商品: [], 備考: "" },
    { 企業ID: "C000002", 会社名: "テスト商事株式会社", 業種: "卸売業", 流入ルート: [], 提案商品: [], 備考: "" }
  ];
  const { merged } = dedupe.mergeCompanyRecords(records);
  assert.equal(merged.会社名, "テスト商事株式会社");
  assert.equal(merged.業種, "小売業");
});

test("mergeCompanyRecords: 統合した企業IDを備考に記録する", () => {
  const records = [
    { 企業ID: "C000001", 流入ルート: [], 提案商品: [], 備考: "既存メモ" },
    { 企業ID: "C000002", 流入ルート: [], 提案商品: [], 備考: "" }
  ];
  const { merged } = dedupe.mergeCompanyRecords(records);
  assert.match(merged.備考, /既存メモ/);
  assert.match(merged.備考, /名寄せ統合: C000002 を統合/);
});

test("mergeCompanyRecords: レコードが空配列なら例外を投げる", () => {
  assert.throws(() => dedupe.mergeCompanyRecords([]));
});

test("SCALAR_FIELDS: 配列/備考/連絡不要項目と合わせると企業マスタのヘッダーと過不足なく一致する(スキーマ変更の検知)", () => {
  const combined = new Set([...dedupe.SCALAR_FIELDS, "流入ルート", "提案商品", "備考", "連絡不要"]);
  const expected = new Set(schema.COMPANY_MASTER_HEADERS);
  assert.deepStrictEqual(combined, expected);
});

test("mergeCompanyRecords: 連絡不要はいずれかのレコードでTRUEなら統合後もTRUEを維持する(falseが先頭でも失われない)", () => {
  const records = [
    { 企業ID: "C000001", 電話番号: "098-000-0001", 連絡不要: false, 流入ルート: [], 提案商品: [], 備考: "" },
    { 企業ID: "C000002", 電話番号: "098-000-0001", 連絡不要: true, 流入ルート: [], 提案商品: [], 備考: "" }
  ];
  const { merged } = dedupe.mergeCompanyRecords(records);
  assert.equal(merged.連絡不要, true);
});

test("mergeCompanyRecords: どのレコードも連絡不要でなければfalse", () => {
  const records = [
    { 企業ID: "C000001", 流入ルート: [], 提案商品: [], 備考: "" },
    { 企業ID: "C000002", 流入ルート: [], 提案商品: [], 備考: "" }
  ];
  const { merged } = dedupe.mergeCompanyRecords(records);
  assert.equal(merged.連絡不要, false);
});

test("nextSequenceNumber: レコードが空配列なら1を返す", () => {
  assert.equal(dedupe.nextSequenceNumber([]), 1);
});

test("nextSequenceNumber: 既存IDの最大値+1を返す", () => {
  const records = [
    { 企業ID: "C000001" },
    { 企業ID: "C000004" }
  ];
  assert.equal(dedupe.nextSequenceNumber(records), 5);
});

test("nextSequenceNumber: 形式が一致しないIDは無視する", () => {
  const records = [
    { 企業ID: "C000002" },
    { 企業ID: "不正なID" },
    { 企業ID: "" },
    { 企業ID: undefined }
  ];
  assert.equal(dedupe.nextSequenceNumber(records), 3);
});

test("applyMerges: 3件の重複グループは1件に統合され、absorbedCountは2、備考に統合先2件が記録される", () => {
  const records = [
    { 企業ID: "C000001", 法人番号: "1111111111111", 会社名: "テスト商事株式会社", 流入ルート: [], 提案商品: [], 備考: "" },
    { 企業ID: "C000002", 法人番号: "1111111111111", 会社名: "", 流入ルート: [], 提案商品: [], 備考: "" },
    { 企業ID: "C000003", 法人番号: "1111111111111", 会社名: "", 流入ルート: [], 提案商品: [], 備考: "" }
  ];
  const { records: finalRecords, absorbedCount } = dedupe.applyMerges(records);
  assert.equal(finalRecords.length, 1);
  assert.equal(absorbedCount, 2);
  assert.equal(finalRecords[0].企業ID, "C000001");
  assert.match(finalRecords[0].備考, /C000002/);
  assert.match(finalRecords[0].備考, /C000003/);
});

test("applyMerges: 重複ペアと無関係な単独レコードが混在する場合、正しい最終件数になる", () => {
  const records = [
    { 企業ID: "C000001", 法人番号: "1111111111111", 会社名: "テスト商事株式会社", 流入ルート: [], 提案商品: [], 備考: "" },
    { 企業ID: "C000002", 法人番号: "1111111111111", 会社名: "", 流入ルート: [], 提案商品: [], 備考: "" },
    { 企業ID: "C000003", 法人番号: "9999999999999", 会社名: "サンプル建設株式会社", 流入ルート: [], 提案商品: [], 備考: "" }
  ];
  const { records: finalRecords, absorbedCount } = dedupe.applyMerges(records);
  assert.equal(finalRecords.length, 2);
  assert.equal(absorbedCount, 1);
  assert.deepEqual(finalRecords.map((r) => r.企業ID).sort(), ["C000001", "C000003"]);
});

test("applyMerges: 空配列を渡すと {records: [], absorbedCount: 0} を返す", () => {
  assert.deepEqual(dedupe.applyMerges([]), { records: [], absorbedCount: 0 });
});

test("企業ID重複防止の回帰テスト: 名寄せで欠番が生じても2回目インポートのIDが既存レコードと衝突しない", () => {
  // ラウンド1: 既存1件 + 新規2件(うち1件は既存と法人番号が重複)
  const existingRound1 = [
    { 企業ID: "C000001", 法人番号: "1111111111111", 会社名: "サンプル建設株式会社", 流入ルート: [], 提案商品: [], 備考: "" }
  ];
  const nextIdRound1 = dedupe.nextSequenceNumber(existingRound1);
  assert.equal(nextIdRound1, 2);
  const newRound1 = [
    { 企業ID: "C" + String(nextIdRound1).padStart(6, "0"), 法人番号: "1111111111111", 会社名: "", 流入ルート: [], 提案商品: [], 備考: "" },
    { 企業ID: "C" + String(nextIdRound1 + 1).padStart(6, "0"), 法人番号: "3333333333333", 会社名: "テスト太郎商店", 流入ルート: [], 提案商品: [], 備考: "" }
  ];
  const combinedRound1 = existingRound1.concat(newRound1);
  const round1Result = dedupe.applyMerges(combinedRound1);

  // 名寄せにより C000002 は吸収され、生存レコードは C000001・C000003 のみ(欠番が発生)
  assert.equal(round1Result.absorbedCount, 1);
  const round1Ids = round1Result.records.map((r) => r.企業ID).sort();
  assert.deepEqual(round1Ids, ["C000001", "C000003"]);

  // 旧ロジック(existingRecords.length + index + 1)なら 2 + 0 + 1 = 3 → C000003 と衝突していたはず
  const buggySequenceNumber = round1Result.records.length + 0 + 1;
  assert.equal(buggySequenceNumber, 3, "旧ロジックは生存レコードのC000003と衝突するIDを生成していたことの確認");

  // ラウンド2: 新ロジックで採番すると欠番を考慮した4番になり衝突しない
  const nextIdRound2 = dedupe.nextSequenceNumber(round1Result.records);
  assert.equal(nextIdRound2, 4);
  const newRound2 = [
    { 企業ID: "C" + String(nextIdRound2).padStart(6, "0"), 法人番号: "4444444444444", 会社名: "テスト四郎商店", 流入ルート: [], 提案商品: [], 備考: "" }
  ];
  const combinedRound2 = round1Result.records.concat(newRound2);
  const round2Result = dedupe.applyMerges(combinedRound2);

  // 衝突していないことを確認: 全企業IDが重複なく、ラウンド1の生存IDを含む3件になる
  const idCounts = {};
  round2Result.records.forEach((r) => { idCounts[r.企業ID] = (idCounts[r.企業ID] || 0) + 1; });
  Object.values(idCounts).forEach((count) => assert.equal(count, 1));
  assert.deepEqual(round2Result.records.map((r) => r.企業ID).sort(), ["C000001", "C000003", "C000004"]);
});

test("propagateDoNotContact: 同じ電話番号を持つ企業のいずれかが連絡不要ならすべてに伝播し、伝播先の備考に監査メモが残る", () => {
  const records = [
    { "企業ID": "C000001", "電話番号": "098-000-0001", "連絡不要": true },
    { "企業ID": "C000002", "電話番号": "098-000-0001", "連絡不要": false },
    { "企業ID": "C000003", "電話番号": "098-000-0002", "連絡不要": false }
  ];
  const result = dedupe.propagateDoNotContact(records);
  const find = (id) => result.find((r) => r["企業ID"] === id);
  assert.equal(find("C000001")["連絡不要"], true);
  assert.equal(find("C000002")["連絡不要"], true);
  assert.match(find("C000002")["備考"], /連絡不要伝播/);
  assert.equal(find("C000003")["連絡不要"], false);
});

test("propagateDoNotContact: 電話番号が空欄の企業同士は連絡不要を伝播しない", () => {
  const records = [
    { "企業ID": "C000001", "電話番号": "", "連絡不要": true },
    { "企業ID": "C000002", "電話番号": "", "連絡不要": false }
  ];
  const result = dedupe.propagateDoNotContact(records);
  const find = (id) => result.find((r) => r["企業ID"] === id);
  assert.equal(find("C000002")["連絡不要"], false);
});

test("propagateDoNotContact: 元の配列を書き換えない(非破壊)", () => {
  const records = [
    { "企業ID": "C000001", "電話番号": "098-000-0001", "連絡不要": true },
    { "企業ID": "C000002", "電話番号": "098-000-0001", "連絡不要": false }
  ];
  dedupe.propagateDoNotContact(records);
  assert.equal(records[1]["連絡不要"], false);
});

test("propagateDoNotContact: 既に連絡不要の企業には伝播メモを追加しない(元の備考を維持)", () => {
  const records = [
    { "企業ID": "C000001", "電話番号": "098-000-0001", "連絡不要": true, "備考": "既存メモ" },
    { "企業ID": "C000002", "電話番号": "098-000-0001", "連絡不要": true, "備考": "既存メモ2" }
  ];
  const result = dedupe.propagateDoNotContact(records);
  const find = (id) => result.find((r) => r["企業ID"] === id);
  assert.equal(find("C000001")["備考"], "既存メモ");
  assert.equal(find("C000002")["備考"], "既存メモ2");
});

test("propagateDoNotContact: 電話番号の表記ゆれ(ハイフンあり/なし)があっても正規化して同一グループとして伝播する", () => {
  const records = [
    { "企業ID": "C000001", "電話番号": "098-000-0001", "連絡不要": true },
    { "企業ID": "C000002", "電話番号": "0980000001", "連絡不要": false }
  ];
  const result = dedupe.propagateDoNotContact(records);
  const find = (id) => result.find((r) => r["企業ID"] === id);
  assert.equal(find("C000002")["連絡不要"], true);
  assert.match(find("C000002")["備考"], /連絡不要伝播/);
});

test("normalizePhoneNumber: 数字以外の記号を除去する", () => {
  assert.equal(dedupe.normalizePhoneNumber("098-000-0001"), "0980000001");
  assert.equal(dedupe.normalizePhoneNumber("098 000 0001"), "0980000001");
});

test("normalizePhoneNumber: null/undefinedは空文字", () => {
  assert.equal(dedupe.normalizePhoneNumber(null), "");
  assert.equal(dedupe.normalizePhoneNumber(undefined), "");
});
