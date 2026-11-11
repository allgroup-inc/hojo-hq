/* GLOW企業リレーション台帳 企業マスタの書き込みの安全確認(純ロジック)
 *
 * 2026-11-11 小柳さん承認(案A)。失敗台帳 FK-010:
 * 7:34 の日次メンテナンス(スコア・ランクの再計算)で、企業マスタを「全部消してから全社分を書き戻す」
 * 途中に Google 側のエラー(Service Spreadsheets failed)が起き、企業マスタの約6割の会社が消えた。
 *
 * ここでは書き込みの前後に使う判定だけを持つ(シートには触らない)。書き込みそのものは
 * ImportRunner.gs の writeCompanyRecords_ が行う。考え方:
 * - 先に消さない。上の行から順に上書きし、余った行は最後に、照合が済んでから消す。
 *   こうすると、途中で止まっても、まだ書いていない行には元のデータが残る。
 * - そのために、残す会社の並び順が元と同じで、新しい会社は末尾にだけ足すことを求める
 *   (並びが同じなら、どの会社も元の行か、それより上の行に書かれる。途中で止まっても会社は消えない)。
 * - 元の会社が消える書き込み・件数が減る書き込みは、呼び出し側が消してよい企業IDを名指ししない限り止める。
 * - 書いた後に企業IDの列を読み直し、件数・重複・欠け・並びが期待どおりかを照らし合わせる。
 *
 * GAS(global.GlowCompanyWriteGuard)と Node(module.exports)の両方で動く UMD 形式。
 * Node 側は tests/glow_ma_companyWriteGuard.test.mjs で検証する。
 */
(function (global) {
  "use strict";

  var CHUNK_ROWS = 500;        // 一度に書く行数(大きな一括書き込みを避け、失敗の影響を小さくする)
  var MAX_ATTEMPTS = 3;        // 1回の書き込みが一時的なエラーで失敗したときの試行回数
  var SAMPLE_LIMIT = 5;        // 理由の文に載せる企業IDの数(長くしない)

  function idOf(value) {
    return value === null || value === undefined ? "" : String(value).trim();
  }

  function sample(ids) {
    var shown = ids.slice(0, SAMPLE_LIMIT).join("、");
    return ids.length > SAMPLE_LIMIT ? shown + " ほか" + (ids.length - SAMPLE_LIMIT) + "件" : shown;
  }

  function duplicatesOf(ids) {
    var seen = {};
    var dups = [];
    ids.forEach(function (id) {
      if (seen[id] === 1) dups.push(id);
      seen[id] = (seen[id] || 0) + 1;
    });
    return dups;
  }

  function toSet(ids) {
    var set = {};
    ids.forEach(function (id) { set[id] = true; });
    return set;
  }

  /**
   * 書き込みの前に、この書き込みで会社が消えたり壊れたりしないかを判定する。
   * @param {Array} oldIdsRaw 今の企業マスタの企業ID列(2行目から最後の行まで。空欄を含んでよい)
   * @param {Array} newIds 書き込む企業IDの並び
   * @param {Object} [options] { allowRemovedIds: 消してよい企業ID(名寄せで統合した分など) }
   * @return {Object} { ok, reason, removedIds, addedIds, oldCount, newCount, shifted }
   */
  function planCompanyWrite(oldIdsRaw, newIds, options) {
    options = options || {};
    var oldIds = (oldIdsRaw || []).map(idOf).filter(function (id) { return id !== ""; });
    var next = (newIds || []).map(idOf);
    var result = { ok: false, reason: "", removedIds: [], addedIds: [], oldCount: oldIds.length, newCount: next.length, shifted: false };

    var blankCount = next.filter(function (id) { return id === ""; }).length;
    if (blankCount > 0) {
      result.reason = "書き込む会社のうち " + blankCount + "社に企業IDがありません";
      return result;
    }
    var newDups = duplicatesOf(next);
    if (newDups.length > 0) {
      result.reason = "書き込む会社の企業IDが重複しています(" + sample(newDups) + ")";
      return result;
    }
    var oldDups = duplicatesOf(oldIds);
    if (oldDups.length > 0) {
      result.reason = "今の企業マスタに同じ企業IDが2つ以上あります(" + sample(oldDups) + ")。先に人が確かめてください";
      return result;
    }
    if (oldIds.length > 0 && next.length === 0) {
      result.reason = "書き込む会社が0社です(今は " + oldIds.length + "社)。企業マスタを空にする書き込みは止めます";
      return result;
    }

    var nextSet = toSet(next);
    var oldSet = toSet(oldIds);
    var allowed = toSet((options.allowRemovedIds || []).map(idOf));
    result.removedIds = oldIds.filter(function (id) { return !nextSet[id]; });
    result.addedIds = next.filter(function (id) { return !oldSet[id]; });

    var notAllowed = result.removedIds.filter(function (id) { return !allowed[id]; });
    if (notAllowed.length > 0) {
      result.reason = "今の企業マスタにある " + notAllowed.length + "社が、書き込む内容から抜けています(" +
        sample(notAllowed) + ")";
      return result;
    }

    // 残す会社の並びが元と同じか(途中で止まっても消えないための条件)
    var kept = oldIds.filter(function (id) { return nextSet[id]; });
    var keptInNew = next.filter(function (id) { return oldSet[id]; });
    for (var i = 0; i < kept.length; i++) {
      if (kept[i] !== keptInNew[i]) {
        result.reason = "会社の並び順が今の企業マスタと違います(" + (i + 1) + "番目: 今は " + kept[i] +
          "、書き込みは " + keptInNew[i] + ")";
        return result;
      }
    }
    // 新しい会社は末尾にだけ足す
    var firstAdded = -1;
    for (var j = 0; j < next.length; j++) {
      if (!oldSet[next[j]]) { firstAdded = j; break; }
    }
    if (firstAdded !== -1) {
      for (var k = firstAdded; k < next.length; k++) {
        if (oldSet[next[k]]) {
          result.reason = "新しい会社(" + next[firstAdded] + ")が、今ある会社(" + next[k] + ")より前に入っています";
          return result;
        }
      }
    }

    // 行がずれるか(会社を外す・途中の空行を詰める)。ずれると、1行の書き込みが列の途中で止まったときに
    // 1行の中に別の会社の値が混ざりうるため、書いた後に全列を照らし合わせる(呼び出し側)
    var rawPos = {};
    (oldIdsRaw || []).forEach(function (raw, index) {
      var id = idOf(raw);
      if (id !== "" && rawPos[id] === undefined) rawPos[id] = index;
    });
    result.shifted = next.some(function (id, index) {
      return rawPos[id] !== undefined && rawPos[id] !== index;
    });

    result.ok = true;
    return result;
  }

  // 書いた値と読み直した値を比べるための形にそろえる(シートが日付・数値・真偽値に変える癖を吸収する)
  function comparable(value) {
    if (value === null || value === undefined) return "";
    if (Object.prototype.toString.call(value) === "[object Date]") {
      var jst = new Date(value.getTime() + 9 * 3600 * 1000).toISOString();
      var time = jst.slice(11, 19);
      return time === "00:00:00" ? jst.slice(0, 10) : jst.slice(0, 10) + " " + time;
    }
    if (typeof value === "boolean") return value ? "true" : "false";
    var s = String(value).trim();
    if (/^(true|false)$/i.test(s)) return s.toLowerCase();
    if (/^-?\d+(\.\d+)?$/.test(s) && !/^0\d/.test(s)) return String(Number(s));
    return s;
  }

  function sameCell(written, read) {
    return comparable(written) === comparable(read);
  }

  /**
   * 書いた行と読み直した行を、全列で照らし合わせる。違う行の行番号・企業ID・列名だけを返す(値は返さない)。
   * @param {Array} expectedRows 書いた行(2次元配列)
   * @param {Array} actualRows 読み直した行(2次元配列。同じ範囲)
   * @param {Array} headers 列名
   * @param {number} firstRowNumber expectedRows[0] がシートの何行目か
   * @return {Object} { ok, reason, mismatched: [{ row, id, columns }], count }
   */
  function compareRows(expectedRows, actualRows, headers, firstRowNumber) {
    var idIndex = headers.indexOf("企業ID");
    var mismatched = [];
    (expectedRows || []).forEach(function (expected, i) {
      var actual = (actualRows || [])[i] || [];
      var columns = [];
      headers.forEach(function (header, j) {
        if (!sameCell(expected[j], actual[j])) columns.push(header);
      });
      if (columns.length) {
        mismatched.push({ row: firstRowNumber + i, id: idOf(expected[idIndex]), columns: columns });
      }
    });
    var result = { ok: mismatched.length === 0, reason: "", mismatched: mismatched, count: mismatched.length };
    if (!result.ok) {
      result.reason = "書いた内容と違う行が " + mismatched.length + "行あります(" +
        mismatched.slice(0, SAMPLE_LIMIT).map(function (m) {
          return m.row + "行目 " + m.id + ": " + m.columns.slice(0, 3).join("・") + (m.columns.length > 3 ? " ほか" : "");
        }).join(" / ") + (mismatched.length > SAMPLE_LIMIT ? " ほか" : "") + ")";
    }
    return result;
  }

  /**
   * 書き込みの途中で止まった後、書こうとした範囲を2つに分けて数える。
   * mixed: 企業IDは書いたとおりなのに、ほかの列が違う行(1行の中に別の会社の値が混ざった行)
   * notWritten: 企業IDが書いたとおりでない行(まだ書けていない行。行がずれる書き込みでは、ずれたまま残る)
   */
  function countMixedRows(expectedRows, actualRows, headers) {
    var idIndex = headers.indexOf("企業ID");
    var counts = { mixed: 0, notWritten: 0 };
    compareRows(expectedRows, actualRows, headers, 2).mismatched.forEach(function (m) {
      if (m.columns.indexOf(headers[idIndex]) !== -1) counts.notWritten++;
      else counts.mixed++;
    });
    return counts;
  }

  /**
   * 書いた後に読み直した企業ID列が、書き込んだ並びと同じかを照らし合わせる。
   * @param {Array} expectedIds 書き込んだ企業IDの並び
   * @param {Array} actualIdsRaw 読み直した企業ID列(2行目から最後の行まで。空欄を含んでよい)
   * @return {Object} { ok, reason, missing, duplicates, unexpected, count }
   */
  function verifyWrittenIds(expectedIds, actualIdsRaw) {
    var expected = (expectedIds || []).map(idOf);
    var raw = (actualIdsRaw || []).map(idOf);
    var actual = raw.filter(function (id) { return id !== ""; });
    var actualSet = toSet(actual);
    var expectedSet = toSet(expected);
    var result = {
      ok: false, reason: "",
      missing: expected.filter(function (id) { return !actualSet[id]; }),
      duplicates: duplicatesOf(actual),
      unexpected: actual.filter(function (id) { return !expectedSet[id]; }),
      count: actual.length
    };
    var problems = [];
    if (actual.length !== expected.length) problems.push("件数 " + actual.length + "社(書いたのは " + expected.length + "社)");
    if (result.missing.length) problems.push("見つからない企業ID " + result.missing.length + "件(" + sample(result.missing) + ")");
    if (result.duplicates.length) problems.push("重複した企業ID " + result.duplicates.length + "件(" + sample(result.duplicates) + ")");
    if (result.unexpected.length) problems.push("書いていない企業ID " + result.unexpected.length + "件(" + sample(result.unexpected) + ")");
    if (problems.length === 0) {
      // 空欄が途中に入っていないか(書いた範囲の中は詰まっているはず)
      var lastFilled = -1;
      for (var i = raw.length - 1; i >= 0; i--) { if (raw[i] !== "") { lastFilled = i; break; } }
      var blanksInside = raw.slice(0, lastFilled + 1).filter(function (id) { return id === ""; }).length;
      if (blanksInside > 0) problems.push("企業IDが空の行が途中に " + blanksInside + "行あります");
      for (var j = 0; j < expected.length && problems.length === 0; j++) {
        if (actual[j] !== expected[j]) problems.push((j + 1) + "番目の企業IDが違います(" + actual[j] + "、期待は " + expected[j] + ")");
      }
    }
    if (problems.length > 0) {
      result.reason = problems.join(" / ");
      return result;
    }
    result.ok = true;
    return result;
  }

  /** 書き込む行を CHUNK_ROWS ずつに分けた [{ offset, count }] を返す(offset は0始まり) */
  function chunkRanges(total, size) {
    size = size || CHUNK_ROWS;
    var ranges = [];
    for (var offset = 0; offset < total; offset += size) {
      ranges.push({ offset: offset, count: Math.min(size, total - offset) });
    }
    return ranges;
  }

  var api = {
    CHUNK_ROWS: CHUNK_ROWS,
    MAX_ATTEMPTS: MAX_ATTEMPTS,
    planCompanyWrite: planCompanyWrite,
    verifyWrittenIds: verifyWrittenIds,
    compareRows: compareRows,
    countMixedRows: countMixedRows,
    sameCell: sameCell,
    chunkRanges: chunkRanges
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowCompanyWriteGuard = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
