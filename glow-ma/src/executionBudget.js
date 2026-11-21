/**
 * GLOW企業リレーション台帳: 1回の実行に使える時間(6分)の中で、何を始めてよいかを決める(判定だけの純ロジック)
 *
 * 背景(2026-11-16): 7:32 の日次メンテナンスが、7つの手順を終えた直後に Apps Script の上限(6分)で打ち切られた。
 * その朝は Google 側の応答が遅く、企業マスタの書き直し2回が合わせて約170秒(ふだんは約17秒)かかっていた。
 * 上限で打ち切られると、後始末(記録・通知)は一切動かない。そこで、
 *   - 時間が足りなくなりそうなときは、新しい書き込み・新しい手順を「始めない」(自分で止めて、記録・通知する)
 *   - それでも打ち切られた場合に備えて、「実行中」の印を残し、後の別の実行が見つけて知らせる
 * の2段にする。経過時間は ExecutionClock.gs の executionElapsedMs_() が返す。
 */
(function (global) {
  "use strict";

  var LIMIT_MS = 6 * 60 * 1000;                    // Apps Script の1回の実行の上限
  var WRITE_START_DEADLINE_MS = 180 * 1000;        // これを過ぎたら、企業マスタの書き直しを始めない
  var SHIFTED_WRITE_START_DEADLINE_MS = 90 * 1000; // 行がずれる書き込み(途中で止まると値が混ざる)は、さらに早く締め切る
  var CHUNK_MIN_REMAINING_MS = 60 * 1000;          // 残りがこれより少なければ、次のかたまりを書き始めない
  var CHUNK_SLOWEST_FACTOR = 3;                    // 残りが「これまでで一番遅かったかたまりの3倍」より少なければ、書き始めない
  var STEP_START_DEADLINE_MS = 270 * 1000;         // これを過ぎたら、日次メンテナンスの次の手順を始めない(最後の記録・通知の時間を残す)
  var STALE_AFTER_MS = 8 * 60 * 1000;              // 「実行中」の印がこれより古ければ、打ち切られたとみなす(上限6分+余裕)

  function ms(value) {
    var n = Number(value);
    return isFinite(n) && n > 0 ? n : 0;
  }

  /** 企業マスタの書き直しを始めてよいか */
  function canStartWrite(elapsedMs, shifted) {
    return ms(elapsedMs) <= (shifted ? SHIFTED_WRITE_START_DEADLINE_MS : WRITE_START_DEADLINE_MS);
  }

  /** 次のかたまり(500行)を書き始めてよいか。slowestChunkMs は、この書き込みでこれまで一番遅かったかたまりの時間 */
  function canStartChunk(elapsedMs, slowestChunkMs) {
    var remaining = LIMIT_MS - ms(elapsedMs);
    return remaining >= Math.max(CHUNK_MIN_REMAINING_MS, CHUNK_SLOWEST_FACTOR * ms(slowestChunkMs));
  }

  /** 日次メンテナンスの次の手順を始めてよいか */
  function canStartStep(elapsedMs) {
    return ms(elapsedMs) <= STEP_START_DEADLINE_MS;
  }

  function seconds(elapsedMs) {
    return Math.round(ms(elapsedMs) / 1000);
  }

  /** 「実行中」の印を作る(JSON)。step は今の手順名、master は "write" | "read" | "none" */
  function buildRunning(startedAtMs, startedAtText, step, master, done) {
    return JSON.stringify({
      startedAtMs: ms(startedAtMs), startedAtText: String(startedAtText || ""),
      step: String(step || ""), master: String(master || ""), done: Number(done) || 0
    });
  }

  /** 「実行中」の印を読む。空なら null。読めない値は、開始時刻の分からない印として返す(見逃さない) */
  function parseRunning(raw) {
    if (raw === undefined || raw === null || raw === "") return null;
    try {
      var parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        return {
          startedAtMs: ms(parsed.startedAtMs), startedAtText: String(parsed.startedAtText || ""),
          step: String(parsed.step || ""), master: String(parsed.master || ""), done: Number(parsed.done) || 0
        };
      }
    } catch (error) {
      // 下で、読めない印として返す
    }
    return { startedAtMs: 0, startedAtText: "", step: "", master: "", done: 0, unreadable: true };
  }

  /** 「実行中」の印が、打ち切られたとみなす古さか。開始時刻が分からない印は、古いとみなす */
  function isStale(running, nowMs) {
    if (!running) return false;
    if (!running.startedAtMs) return true;
    return ms(nowMs) - running.startedAtMs > STALE_AFTER_MS;
  }

  /** 打ち切られた日次メンテナンスの説明(稼働状況タブ・通知に出す) */
  function describeStale(running, totalSteps) {
    var head = "日次メンテナンスが途中で打ち切られました(開始 " + (running.startedAtText || "不明") +
      "。6分の上限、または異常終了)。";
    if (running.unreadable) return head + "どこまで進んだかの記録が読めません。稼働状況タブと実行記録で確かめてください";
    var where = running.step
      ? "「" + running.step + "」の途中でした(" + running.done + "/" + totalSteps + "件が完了)。"
      : "最後の記録の途中でした(" + running.done + "/" + totalSteps + "件が完了)。";
    var data = running.step && running.master === "write"
      ? "企業マスタを書き直す手順の途中です。会社の行の位置は変えずに上書きしているため、会社は消えていないはずですが、企業マスタの件数を今朝のバックアップと比べてください"
      : "企業マスタを書き直す手順の途中ではありません(企業マスタの書き込みは、終わっているか、まだ始まっていません)";
    return head + where + data + "。終わっていない手順は、次の日次メンテナンスで動きます";
  }

  var api = {
    LIMIT_MS: LIMIT_MS,
    WRITE_START_DEADLINE_MS: WRITE_START_DEADLINE_MS,
    SHIFTED_WRITE_START_DEADLINE_MS: SHIFTED_WRITE_START_DEADLINE_MS,
    CHUNK_MIN_REMAINING_MS: CHUNK_MIN_REMAINING_MS,
    STEP_START_DEADLINE_MS: STEP_START_DEADLINE_MS,
    STALE_AFTER_MS: STALE_AFTER_MS,
    canStartWrite: canStartWrite,
    canStartChunk: canStartChunk,
    canStartStep: canStartStep,
    seconds: seconds,
    buildRunning: buildRunning,
    parseRunning: parseRunning,
    isStale: isStale,
    describeStale: describeStale
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowExecutionBudget = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
