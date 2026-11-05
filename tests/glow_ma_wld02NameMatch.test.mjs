// 世界の架け橋 WLD-02 名寄せ照合(候補を出すだけ)のテスト。会社名・番号はすべて架空
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const m = require("../glow-ma/wld02/nameMatch.js");

test("会社名は法人の種類・略号・空白・全角をそろえる", () => {
  assert.equal(m.normalizeCompanyName("株式会社 テスト物産"), "テスト物産");
  assert.equal(m.normalizeCompanyName("(株)テスト物産"), "テスト物産");
  assert.equal(m.normalizeCompanyName("㈱テスト物産"), "テスト物産");
  assert.equal(m.normalizeCompanyName("テスト物産　株式会社"), "テスト物産");
  assert.equal(m.normalizeCompanyName("有限会社ＡＢＣ商会"), "abc商会");
  assert.equal(m.normalizeCompanyName("(社名不明)"), "");
  assert.equal(m.normalizeCompanyName(""), "");
  assert.equal(m.normalizeCompanyName(null), "");
});

test("電話番号は数字だけにし、短すぎるものは照合しない", () => {
  assert.equal(m.normalizePhone("098-111-2222"), "0981112222");
  assert.equal(m.normalizePhone("０９８（１１１）２２２２"), "0981112222");
  assert.equal(m.normalizePhone("123"), "");
});

test("同じ会社かもしれない組を、理由つきで出す", () => {
  const companies = [
    { 企業ID: "C900001", 会社名: "株式会社テスト物産", 電話番号: "098-111-2222", 法人番号: "" },
    { 企業ID: "C900002", 会社名: "(株)テスト物産", 電話番号: "0981112222", 法人番号: "" },
    { 企業ID: "C900003", 会社名: "うみかぜ商店", 電話番号: "", 法人番号: "1234567890123" },
    { 企業ID: "C900004", 会社名: "有限会社 そらいろ", 電話番号: "", 法人番号: "1234567890123" },
    { 企業ID: "C900005", 会社名: "まったく別の会社", 電話番号: "098-999-0000", 法人番号: "" },
    { 企業ID: "C900006", 会社名: "(社名不明)", 電話番号: "", 法人番号: "" },
    { 企業ID: "C900007", 会社名: "(社名不明)", 電話番号: "", 法人番号: "" },
  ];
  const { pairs, counts } = m.findCandidatePairs(companies);
  assert.deepEqual(pairs, [
    { ids: ["C900001", "C900002"], reasons: ["電話番号が同じ", "会社名が同じ"] },
    { ids: ["C900003", "C900004"], reasons: ["法人番号が同じ"] },
  ]);
  assert.equal(counts.候補の組, 2);
  assert.equal(counts.理由が2つ以上, 1);
  assert.equal(counts.かかわる企業ID, 4);
});

test("携帯番号でも照合し、同じ行の電話と携帯が同じでも自分とは組にしない", () => {
  const companies = [
    { 企業ID: "C900001", 会社名: "A", 電話番号: "090-1111-2222", 携帯番号: "090-1111-2222" },
    { 企業ID: "C900002", 会社名: "B", 電話番号: "", 携帯番号: "09011112222" },
  ];
  assert.deepEqual(m.findCandidatePairs(companies).pairs, [{ ids: ["C900001", "C900002"], reasons: ["電話番号が同じ"] }]);
});

test("3社が同じなら3組を出す", () => {
  const companies = ["C900003", "C900001", "C900002"].map((id) => ({ 企業ID: id, 会社名: "同名商事" }));
  assert.deepEqual(m.findCandidatePairs(companies).pairs.map((p) => p.ids.join("-")), [
    "C900001-C900002", "C900001-C900003", "C900002-C900003",
  ]);
});

test("企業マスタに無い企業IDを、指している記録から見つける", () => {
  assert.deepEqual(m.orphanIds(["C900001", "C900009", "", "C900009"], [{ 企業ID: "C900001" }]), ["C900009"]);
});
