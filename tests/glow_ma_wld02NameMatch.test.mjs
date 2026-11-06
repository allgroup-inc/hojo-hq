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

// ---- 2026-11-06 §9-7: 法人番号の確かめ方と、自動で結び付けてよいかの判定(すべて合成データ) ----
// 12桁から検査用の数字を計算して、合成の法人番号を作る(実在の会社の番号は使わない)
function corpNo(base12) {
  let sum = 0;
  for (let n = 1; n <= 12; n++) sum += Number(base12[12 - n]) * (n % 2 === 1 ? 1 : 2);
  return String(9 - (sum % 9)) + base12;
}
const NO_A = corpNo("990000000011");
const NO_B = corpNo("990000000022");
const wrongCheck = (no) => String((Number(no[0]) % 9) + 1) + no.slice(1); // 検査用の数字だけを変える

test("法人番号: 13桁・検査用の数字が合うものだけを正しいとする(全角・ハイフンも読む)", () => {
  assert.deepEqual(m.validateCorporateNumber(NO_A), { ok: true, value: NO_A, reason: "" });
  assert.equal(m.validateCorporateNumber(wrongCheck(NO_A)).ok, false);
  assert.match(m.validateCorporateNumber(wrongCheck(NO_A)).reason, /検査用の数字/);
  assert.match(m.validateCorporateNumber("123456789012").reason, /13桁/);
  assert.match(m.validateCorporateNumber("12345678901234").reason, /13桁/);
  assert.match(m.validateCorporateNumber("").reason, /空/);
  const wide = NO_A.replace(/[0-9]/g, (c) => String.fromCharCode(c.charCodeAt(0) + 0xFEE0));
  assert.equal(m.validateCorporateNumber(wide).ok, true);
  assert.equal(m.validateCorporateNumber(NO_A.slice(0, 1) + "-" + NO_A.slice(1)).ok, true);
});

const MASTER = [
  { 企業ID: "C900001", 会社名: "株式会社うみかぜ物産", 電話番号: "098-111-0001", 法人番号: NO_A },
  { 企業ID: "C900002", 会社名: "株式会社そらいろ", 電話番号: "098-111-0002", 法人番号: "" },
];

test("自動で結び付けてよいのは、法人番号が正しく・台帳に1社だけ・会社名と電話に食い違いが無いときだけ", () => {
  assert.deepEqual(m.decideAutoLink({ 法人番号: NO_A, 会社名: "(株)うみかぜ物産", 電話番号: "0981110001" }, MASTER),
    { auto: true, companyId: "C900001" });
  // 会社名か電話のどちらか1つが一致すれば足りる
  assert.deepEqual(m.decideAutoLink({ 法人番号: NO_A, 電話番号: "098-111-0001" }, MASTER), { auto: true, companyId: "C900001" });
  assert.deepEqual(m.decideAutoLink({ 法人番号: NO_A, 会社名: "うみかぜ物産 株式会社" }, MASTER), { auto: true, companyId: "C900001" });
});

test("法人番号だけが一致し、会社名・電話番号を照らし合わせられないときは、自動で結び付けず確認担当へ回す", () => {
  const r = m.decideAutoLink({ 法人番号: NO_A }, MASTER);
  assert.equal(r.auto, false);
  assert.match(r.reason, /ほかに/);
  assert.deepEqual(r.candidates, ["C900001"]);
  // 台帳側に会社名・電話が無い場合も同じ
  const bare = [{ 企業ID: "C900005", 会社名: "", 電話番号: "", 法人番号: NO_A }];
  const r2 = m.decideAutoLink({ 法人番号: NO_A, 会社名: "株式会社うみかぜ物産", 電話番号: "098-111-0001" }, bare);
  assert.equal(r2.auto, false);
  assert.deepEqual(r2.candidates, ["C900005"]);
  // 「(社名不明)」は照らし合わせに使わない
  const r3 = m.decideAutoLink({ 法人番号: NO_A, 会社名: "(社名不明)" }, MASTER);
  assert.equal(r3.auto, false);
});

test("台帳側の法人番号も確かめ、検査用の数字が合わない台帳の行には結び付けない", () => {
  // 台帳の番号が「13桁だが検査用の数字が違う」場合、入ってきた正しい番号とは一致しない扱い
  const ledger = [{ 企業ID: "C900006", 会社名: "株式会社うみかぜ物産", 電話番号: "098-111-0001", 法人番号: wrongCheck(NO_A) }];
  assert.equal(m.decideAutoLink({ 法人番号: NO_A, 会社名: "株式会社うみかぜ物産" }, ledger).auto, false);
  // 全角・ハイフン入りで台帳に入っていても、正しい番号なら同じとみなす
  const wide = NO_A.replace(/[0-9]/g, (c) => String.fromCharCode(c.charCodeAt(0) + 0xFEE0));
  const ledger2 = [{ 企業ID: "C900007", 会社名: "株式会社うみかぜ物産", 法人番号: wide.slice(0, 1) + "-" + wide.slice(1) }];
  assert.deepEqual(m.decideAutoLink({ 法人番号: NO_A, 会社名: "(株)うみかぜ物産" }, ledger2), { auto: true, companyId: "C900007" });
});

test("台帳の法人番号の点検: 正しい形・未入力・正しくない・重複を数え、番号そのものは返さない", () => {
  const rows = [
    { 企業ID: "C900001", 法人番号: NO_A },
    { 企業ID: "C900002", 法人番号: NO_A },          // 重複
    { 企業ID: "C900003", 法人番号: wrongCheck(NO_B) }, // 検査用の数字が違う
    { 企業ID: "C900004", 法人番号: "12345" },       // 桁が足りない
    { 企業ID: "C900005", 法人番号: "" },            // 未入力
    { 企業ID: "C900006", 法人番号: NO_B },
    { 企業ID: "", 法人番号: NO_B },                  // 企業IDが無い行は数えない
  ];
  const a = m.auditCorporateNumbers(rows);
  assert.deepEqual(a.counts, { 確かめた会社: 6, 正しい形: 3, 未入力: 1, 正しくない: 2, 重複の組: 1 });
  assert.deepEqual(a.duplicates, [["C900001", "C900002"]]);
  assert.deepEqual(a.invalid.map((x) => x.企業ID), ["C900003", "C900004"]);
  assert.match(a.invalid[0].reason, /検査用の数字/);
  assert.match(a.invalid[1].reason, /13桁/);
  assert.ok(!JSON.stringify(a).includes(NO_A) && !JSON.stringify(a).includes(NO_B.slice(1)));
});

test("電話番号・会社名が一致しても、法人番号が無ければ自動で結び付けない(候補として確認担当へ)", () => {
  const r = m.decideAutoLink({ 法人番号: "", 会社名: "株式会社そらいろ", 電話番号: "098-111-0002" }, MASTER);
  assert.equal(r.auto, false);
  assert.match(r.reason, /空/);
  assert.deepEqual(r.candidates, ["C900002"]);
});

test("法人番号の検査用の数字が合わないときは、自動で結び付けない", () => {
  const r = m.decideAutoLink({ 法人番号: wrongCheck(NO_A), 会社名: "株式会社うみかぜ物産" }, MASTER);
  assert.equal(r.auto, false);
  assert.match(r.reason, /検査用の数字/);
  assert.deepEqual(r.candidates, ["C900001"]); // 会社名が同じなので候補には出る
});

test("台帳に同じ法人番号の会社が無い・複数ある・台帳の番号が正しくないときは、自動で結び付けない", () => {
  assert.match(m.decideAutoLink({ 法人番号: NO_B }, MASTER).reason, /無い/);
  const dup = MASTER.concat([{ 企業ID: "C900003", 会社名: "うみかぜ物産", 法人番号: NO_A }]);
  const r = m.decideAutoLink({ 法人番号: NO_A }, dup);
  assert.equal(r.auto, false);
  assert.match(r.reason, /複数/);
  assert.deepEqual(r.candidates.sort(), ["C900001", "C900003"]);
  const bad = wrongCheck(NO_B);
  const r2 = m.decideAutoLink({ 法人番号: bad }, [{ 企業ID: "C900009", 会社名: "x", 法人番号: bad }]);
  assert.equal(r2.auto, false); // 入ってきた番号が正しくない時点で止まる
});

test("法人番号が一致しても、会社名か電話番号が台帳と食い違えば、自動で結び付けない", () => {
  const r1 = m.decideAutoLink({ 法人番号: NO_A, 会社名: "株式会社まったく別", 電話番号: "098-111-0001" }, MASTER);
  assert.equal(r1.auto, false);
  assert.match(r1.reason, /会社名/);
  assert.deepEqual(r1.candidates, ["C900001"]);
  const r2 = m.decideAutoLink({ 法人番号: NO_A, 会社名: "株式会社うみかぜ物産", 電話番号: "098-999-9999" }, MASTER);
  assert.equal(r2.auto, false);
  assert.match(r2.reason, /電話番号/);
});
