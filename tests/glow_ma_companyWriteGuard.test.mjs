// 企業マスタの書き込みの安全確認(companyWriteGuard.js)の判定だけを確かめるテスト。企業IDは架空
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const G = require("../glow-ma/src/companyWriteGuard.js");

const ids = (n, from = 1) => Array.from({ length: n }, (_, i) => "C9" + String(from + i).padStart(5, "0"));

test("同じ会社を同じ並びで書き直す(スコアの再計算など)は通す", () => {
  const p = G.planCompanyWrite(ids(5), ids(5));
  assert.equal(p.ok, true);
  assert.deepEqual(p.removedIds, []);
  assert.deepEqual(p.addedIds, []);
});

test("末尾に新しい会社を足すのは通す。今の列に空欄(書式だけの行)があっても数えない", () => {
  const p = G.planCompanyWrite([...ids(3), "", ""], ids(5));
  assert.equal(p.ok, true);
  assert.equal(p.oldCount, 3);
  assert.deepEqual(p.addedIds, ids(2, 4));
});

test("今ある会社が抜ける書き込みは止める(名指しされていなければ)", () => {
  const p = G.planCompanyWrite(ids(5), ids(5).filter((id) => id !== "C900003"));
  assert.equal(p.ok, false);
  assert.match(p.reason, /1社が、書き込む内容から抜けています\(C900003\)/);
});

test("今回の事故の形: 約6割の会社が抜ける書き込み(3,000社 → 1,200社)は止める", () => {
  const p = G.planCompanyWrite(ids(3000), ids(1200));
  assert.equal(p.ok, false);
  assert.match(p.reason, /1800社が、書き込む内容から抜けています/);
  assert.match(p.reason, /ほか1795件/);
});

test("名寄せで統合した会社だけを名指しすれば、その会社は外してよい", () => {
  const next = ids(5).filter((id) => id !== "C900002").concat(["C900006"]);
  const ok = G.planCompanyWrite(ids(5), next, { allowRemovedIds: ["C900002"] });
  assert.equal(ok.ok, true);
  assert.deepEqual(ok.removedIds, ["C900002"]);
  const ng = G.planCompanyWrite(ids(5), next, { allowRemovedIds: ["C900004"] });
  assert.equal(ng.ok, false);
});

test("会社の並びが変わる書き込みは止める(途中で止まると会社が消えうるため)", () => {
  const swapped = ["C900001", "C900003", "C900002", "C900004"];
  const p = G.planCompanyWrite(ids(4), swapped);
  assert.equal(p.ok, false);
  assert.match(p.reason, /並び順/);
});

test("新しい会社が今ある会社より前に入る書き込みは止める", () => {
  const p = G.planCompanyWrite(ids(3), ["C900001", "C999999", "C900002", "C900003"]);
  assert.equal(p.ok, false);
  assert.match(p.reason, /C999999.*より前/);
});

test("企業IDの空欄・重複がある書き込みは止める", () => {
  assert.match(G.planCompanyWrite(ids(2), ["C900001", ""]).reason, /1社に企業IDがありません/);
  assert.match(G.planCompanyWrite(ids(2), ["C900001", "C900001"]).reason, /重複/);
});

test("今の企業マスタに重複がある場合も、人が確かめるまで止める", () => {
  const p = G.planCompanyWrite(["C900001", "C900001"], ["C900001"]);
  assert.equal(p.ok, false);
  assert.match(p.reason, /同じ企業IDが2つ以上/);
});

test("0社で上書きする(企業マスタを空にする)書き込みは止める。空の台帳に0社は通す", () => {
  assert.equal(G.planCompanyWrite(ids(3), []).ok, false);
  assert.equal(G.planCompanyWrite([], []).ok, true);
});

test("照合: 書いたとおりなら通す。末尾の空欄は数えない", () => {
  assert.equal(G.verifyWrittenIds(ids(3), [...ids(3), "", ""]).ok, true);
});

test("照合: 件数・欠け・重複・書いていないID・途中の空欄・並びの違いを見つける", () => {
  const missing = G.verifyWrittenIds(ids(3), ids(2));
  assert.equal(missing.ok, false);
  assert.deepEqual(missing.missing, ["C900003"]);
  const dup = G.verifyWrittenIds(ids(3), ["C900001", "C900002", "C900003", "C900003"]);
  assert.deepEqual(dup.duplicates, ["C900003"]);
  assert.match(dup.reason, /件数 4社/);
  const extra = G.verifyWrittenIds(ids(2), ["C900001", "C999999"]);
  assert.deepEqual(extra.unexpected, ["C999999"]);
  const hole = G.verifyWrittenIds(ids(3), ["C900001", "", "C900002", "C900003"]);
  assert.equal(hole.ok, false);
  assert.match(hole.reason, /空の行が途中に 1行/);
  const order = G.verifyWrittenIds(ids(3), ["C900001", "C900003", "C900002"]);
  assert.equal(order.ok, false);
  assert.match(order.reason, /2番目/);
});

test("分割: 1,201行を500行ずつに分ける", () => {
  assert.deepEqual(G.chunkRanges(1201, 500), [
    { offset: 0, count: 500 }, { offset: 500, count: 500 }, { offset: 1000, count: 201 },
  ]);
  assert.deepEqual(G.chunkRanges(0, 500), []);
});

test("行がずれるか: 並びも位置も同じ・末尾に足すだけならずれない。途中を外す・途中の空行を詰めるとずれる", () => {
  assert.equal(G.planCompanyWrite(ids(5), ids(5)).shifted, false);
  assert.equal(G.planCompanyWrite(ids(3), ids(5)).shifted, false);
  const removed = G.planCompanyWrite(ids(5), ids(5).filter((id) => id !== "C900002"), { allowRemovedIds: ["C900002"] });
  assert.equal(removed.ok, true);
  assert.equal(removed.shifted, true);
  assert.equal(G.planCompanyWrite(["C900001", "", "C900002"], ["C900001", "C900002"]).shifted, true);
  const lastRemoved = G.planCompanyWrite(ids(5), ids(4), { allowRemovedIds: ["C900005"] });
  assert.equal(lastRemoved.shifted, false, "最後の会社を外すだけなら、ほかの会社の位置は変わらない");
});

const H = ["企業ID", "会社名", "電話番号", "最終接触日", "総合スコア", "連絡不要"];

test("全列の照合: 同じなら通す。シートが日付・数値・真偽値に変えても同じとみなす", () => {
  const written = [["C900001", "架空建設", "098-000-0000", "2026-10-01", 12, false]];
  const read = [["C900001", "架空建設", "098-000-0000", new Date("2026-10-01T00:00:00+09:00"), "12", "FALSE"]];
  assert.equal(G.compareRows(written, read, H, 2).ok, true);
});

test("全列の照合: 1行の中に別の会社の値が混ざった行を、行番号・企業ID・列名で示す(値は出さない)", () => {
  const written = [["C900001", "架空建設", "098-000-0001", "", 1, false], ["C900002", "架空工業", "098-000-0002", "", 2, false]];
  const read = [["C900001", "架空建設", "098-000-0001", "", 1, false], ["C900002", "架空建設", "098-000-0001", "", 2, false]];
  const r = G.compareRows(written, read, H, 2);
  assert.equal(r.ok, false);
  assert.deepEqual(r.mismatched, [{ row: 3, id: "C900002", columns: ["会社名", "電話番号"] }]);
  assert.match(r.reason, /違う行が 1行あります\(3行目 C900002: 会社名・電話番号\)/);
  assert.doesNotMatch(r.reason, /架空/);
});

test("全列の照合: 先頭が0の番号は数値として扱わない(0980 と 980 は別)", () => {
  assert.equal(G.sameCell("0980", 980), false);
  assert.equal(G.sameCell(0, "0"), true);
});

test("途中で止まった後の数え方: 混ざった行(IDは正しい)と、まだ書けていない行(IDが違う)を分ける", () => {
  const written = [["C900001", "架空A", "1", "", 0, false], ["C900003", "架空C", "3", "", 0, false], ["C900004", "架空D", "4", "", 0, false]];
  const read = [["C900001", "架空A", "1", "", 0, false], ["C900003", "架空B", "2", "", 0, false], ["C900003", "架空C", "3", "", 0, false]];
  assert.deepEqual(G.countMixedRows(written, read, H), { mixed: 1, notWritten: 1 });
});
