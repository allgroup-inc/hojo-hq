// 1回の実行(上限6分)の中で、何を始めてよいかの判定(executionBudget.js)だけを確かめる試験
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const B = require("../glow-ma/src/executionBudget.js");

test("企業マスタの書き直しは、開始から180秒を過ぎたら始めない。行がずれる書き込みは90秒まで", () => {
  assert.equal(B.canStartWrite(0, false), true);
  assert.equal(B.canStartWrite(180000, false), true);
  assert.equal(B.canStartWrite(180001, false), false);
  assert.equal(B.canStartWrite(90000, true), true);
  assert.equal(B.canStartWrite(90001, true), false);
  assert.equal(B.canStartWrite("読めない値", false), true, "時間が分からないときは0秒として扱う(ふだんの動きを止めない)");
});

test("次のかたまりは、残りが60秒未満、または「一番遅かったかたまりの3倍」未満なら書き始めない", () => {
  assert.equal(B.canStartChunk(0, 0), true);
  assert.equal(B.canStartChunk(300000, 0), true, "残りちょうど60秒");
  assert.equal(B.canStartChunk(300001, 0), false);
  assert.equal(B.canStartChunk(200000, 50000), true, "残り160秒 ≥ 150秒");
  assert.equal(B.canStartChunk(250000, 50000), false, "残り110秒 < 150秒");
  assert.equal(B.canStartChunk(100000, 100000), false, "残り260秒 < 300秒");
});

test("日次メンテナンスの次の手順は、開始から270秒を過ぎたら始めない", () => {
  assert.equal(B.canStartStep(270000), true);
  assert.equal(B.canStartStep(270001), false);
  assert.equal(B.seconds(271400), 271);
});

test("「実行中」の印: 8分より古ければ打ち切りとみなす。読めない印は、古いとみなして見逃さない", () => {
  const t = Date.parse("2026-11-16T07:32:22+09:00");
  const running = B.parseRunning(B.buildRunning(t, "2026-11-16 07:32", "スコア・ランクの再計算", "write", 2));
  assert.deepEqual(running, { startedAtMs: t, startedAtText: "2026-11-16 07:32", step: "スコア・ランクの再計算", master: "write", done: 2 });
  assert.equal(B.isStale(running, t + 8 * 60 * 1000), false, "ちょうど8分はまだ");
  assert.equal(B.isStale(running, t + 8 * 60 * 1000 + 1), true);
  assert.equal(B.isStale(null, t), false);
  assert.equal(B.parseRunning(""), null);
  assert.equal(B.parseRunning(null), null);
  for (const broken of ["{", "1", "実行中"]) {
    const r = B.parseRunning(broken);
    assert.equal(B.isStale(r, t), true, broken);
  }
});

test("打ち切りの説明: 書き直す手順の途中か、そうでないか、最後の記録の途中かを言い分ける", () => {
  const t = 1;
  const write = B.describeStale(B.parseRunning(B.buildRunning(t, "2026-11-16 07:32", "スコア・ランクの再計算", "write", 2)), 7);
  assert.match(write, /開始 2026-11-16 07:32/);
  assert.match(write, /「スコア・ランクの再計算」の途中でした\(2\/7件が完了\)/);
  assert.match(write, /企業マスタを書き直す手順の途中です.*バックアップと比べてください/);
  const read = B.describeStale(B.parseRunning(B.buildRunning(t, "2026-11-16 07:32", "ダッシュボードの更新", "read", 3)), 7);
  assert.match(read, /企業マスタを書き直す手順の途中ではありません/);
  const tail = B.describeStale(B.parseRunning(B.buildRunning(t, "2026-11-16 07:32", "", "", 7)), 7);
  assert.match(tail, /最後の記録の途中でした\(7\/7件が完了\)/);
  assert.match(tail, /企業マスタを書き直す手順の途中ではありません/);
  assert.match(B.describeStale(B.parseRunning("{"), 7), /記録が読めません/);
});
