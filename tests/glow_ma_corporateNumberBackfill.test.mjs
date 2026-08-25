import test from "node:test";
import assert from "node:assert/strict";
import corporateNumberBackfill from "../glow-ma/src/corporateNumberBackfill.js";

test("extractMunicipality: 都道府県を除いた市区町村を抽出する", () => {
  assert.equal(corporateNumberBackfill.extractMunicipality("沖縄県那覇市字X"), "那覇市");
  assert.equal(
    corporateNumberBackfill.extractMunicipality("沖縄県島尻郡八重瀬町字Y"),
    "島尻郡八重瀬町"
  );
});

test("extractMunicipality: 都道府県名が無くても市区町村を抽出できる", () => {
  assert.equal(corporateNumberBackfill.extractMunicipality("那覇市字X"), "那覇市");
});

test("extractMunicipality: 抽出できない・空の場合はnullを返す(断定しない)", () => {
  assert.equal(corporateNumberBackfill.extractMunicipality(""), null);
  assert.equal(corporateNumberBackfill.extractMunicipality(null), null);
  assert.equal(corporateNumberBackfill.extractMunicipality(undefined), null);
  assert.equal(corporateNumberBackfill.extractMunicipality("字XX番地のみ"), null);
});

test("selectCorporateNumberMatch: 会社名一致が0件ならno_candidate", () => {
  const result = corporateNumberBackfill.selectCorporateNumberMatch(
    { "会社名": "株式会社存在しない", "所在地": "沖縄県那覇市字X" },
    [{ corporateNumber: "1000000000001", name: "株式会社別会社", address: "沖縄県那覇市字Y" }]
  );
  assert.equal(result.status, "no_candidate");
  assert.equal(result.corporateNumber, null);
  assert.deepEqual(result.candidates, []);
});

test("selectCorporateNumberMatch: 会社名一致が1件だけなら所在地を見ずにmatched", () => {
  const result = corporateNumberBackfill.selectCorporateNumberMatch(
    { "会社名": "株式会社共和", "所在地": "沖縄県那覇市字X" },
    [{ corporateNumber: "1000000000001", name: "株式会社共和", address: "沖縄県宮古島市字Z" }]
  );
  assert.equal(result.status, "matched");
  assert.equal(result.corporateNumber, "1000000000001");
});

test("selectCorporateNumberMatch: 空白の表記ゆれ(全角/半角スペース)を無視して完全一致判定する", () => {
  const result = corporateNumberBackfill.selectCorporateNumberMatch(
    { "会社名": "有限会社 比嘉組", "所在地": "沖縄県那覇市字X" },
    [{ corporateNumber: "1000000000001", name: "有限会社比嘉組", address: "沖縄県宮古島市字Z" }]
  );
  assert.equal(result.status, "matched");
});

test("selectCorporateNumberMatch: 同名複数でも所在地(市区町村)で1件に絞れればmatched", () => {
  const result = corporateNumberBackfill.selectCorporateNumberMatch(
    { "会社名": "有限会社比嘉組", "所在地": "沖縄県那覇市字X" },
    [
      { corporateNumber: "1000000000001", name: "有限会社比嘉組", address: "沖縄県那覇市字Y" },
      { corporateNumber: "1000000000002", name: "有限会社比嘉組", address: "沖縄県宮古島市字Z" },
      { corporateNumber: "1000000000003", name: "有限会社比嘉組", address: "沖縄県石垣市字W" }
    ]
  );
  assert.equal(result.status, "matched");
  assert.equal(result.corporateNumber, "1000000000001");
});

test("selectCorporateNumberMatch: 所在地で絞っても複数件残ればambiguous(自動確定しない)", () => {
  const result = corporateNumberBackfill.selectCorporateNumberMatch(
    { "会社名": "有限会社比嘉組", "所在地": "沖縄県那覇市字X" },
    [
      { corporateNumber: "1000000000001", name: "有限会社比嘉組", address: "沖縄県那覇市字Y" },
      { corporateNumber: "1000000000002", name: "有限会社比嘉組", address: "沖縄県那覇市字Z" }
    ]
  );
  assert.equal(result.status, "ambiguous");
  assert.equal(result.corporateNumber, null);
  assert.equal(result.candidates.length, 2);
});

test("selectCorporateNumberMatch: 所在地で絞ると0件になる場合もambiguous(消去法で断定しない)", () => {
  const result = corporateNumberBackfill.selectCorporateNumberMatch(
    { "会社名": "有限会社比嘉組", "所在地": "沖縄県うるま市字X" },
    [
      { corporateNumber: "1000000000001", name: "有限会社比嘉組", address: "沖縄県那覇市字Y" },
      { corporateNumber: "1000000000002", name: "有限会社比嘉組", address: "沖縄県宮古島市字Z" }
    ]
  );
  assert.equal(result.status, "ambiguous");
  assert.equal(result.candidates.length, 2);
});

test("selectCorporateNumberMatch: 会社側の所在地が抽出できない場合は所在地で絞らずambiguous", () => {
  const result = corporateNumberBackfill.selectCorporateNumberMatch(
    { "会社名": "有限会社比嘉組", "所在地": "" },
    [
      { corporateNumber: "1000000000001", name: "有限会社比嘉組", address: "沖縄県那覇市字Y" },
      { corporateNumber: "1000000000002", name: "有限会社比嘉組", address: "沖縄県宮古島市字Z" }
    ]
  );
  assert.equal(result.status, "ambiguous");
});
