/* GLOW企業リレーション台帳 法人番号による名寄せロジック
 * ブラウザ相当のGAS(global.GlowDedupe)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_dedupe.test.mjs で検証される。
 */
(function (global) {
  "use strict";

  function normalizeCorporateNumber(raw) {
    if (raw === null || raw === undefined) return null;
    var digits = String(raw).replace(/[^0-9]/g, "");
    if (digits.length !== 13) return null;
    return digits;
  }

  function normalizePhoneNumber(raw) {
    if (raw === null || raw === undefined) return "";
    return String(raw).replace(/[^0-9]/g, "");
  }

  function findDuplicateGroups(companies) {
    var byNumber = {};
    var order = [];
    companies.forEach(function (company) {
      var num = normalizeCorporateNumber(company["法人番号"]);
      if (!num) return;
      if (!byNumber[num]) {
        byNumber[num] = [];
        order.push(num);
      }
      byNumber[num].push(company);
    });
    var groups = [];
    order.forEach(function (num) {
      if (byNumber[num].length > 1) groups.push(byNumber[num]);
    });
    return groups;
  }

  var SCALAR_FIELDS = [
    "企業ID", "法人番号", "会社名", "業種", "規模", "代表者名", "代表者年齢", "所在地", "電話番号",
    "起点担当者_紹介元", "現在ステージ", "初期スコア", "反応スコア", "総合スコア", "ランク",
    "最終接触日", "次回アクション予定日", "次回アクション内容", "担当者", "登録日", "後継者状況"
  ];

  function unionArrayField(records, field) {
    var seen = {};
    var result = [];
    records.forEach(function (record) {
      (record[field] || []).forEach(function (value) {
        if (!seen[value]) {
          seen[value] = true;
          result.push(value);
        }
      });
    });
    return result;
  }

  function mergeCompanyRecords(records) {
    if (!records || records.length === 0) {
      throw new Error("mergeCompanyRecords requires at least one record");
    }
    var merged = {};
    SCALAR_FIELDS.forEach(function (field) {
      merged[field] = "";
      for (var i = 0; i < records.length; i++) {
        var value = records[i][field];
        if (value !== undefined && value !== null && value !== "") {
          merged[field] = value;
          break;
        }
      }
    });

    merged["流入ルート"] = unionArrayField(records, "流入ルート");
    merged["提案商品"] = unionArrayField(records, "提案商品");
    // 連絡不要はいずれかの重複レコードでTRUEなら統合後もTRUEを維持する
    // (SCALAR_FIELDSの「最初に見つかった非空値」ロジックだとfalseが先に見つかった場合に
    // 連絡不要TRUEの情報が失われ、DNC対象に再度架電しかねないため特別扱いする)
    merged["連絡不要"] = records.some(function (record) { return record["連絡不要"] === true; });

    var absorbedIds = records.slice(1).map(function (r) { return r["企業ID"]; }).filter(Boolean);
    var noteParts = [];
    if (records[0]["備考"]) noteParts.push(records[0]["備考"]);
    if (absorbedIds.length > 0) {
      noteParts.push("名寄せ統合: " + absorbedIds.join("、") + " を統合");
    }
    merged["備考"] = noteParts.join(" / ");

    // 関係メモは蓄積した関係性情報であり、SCALAR_FIELDSの「最初に見つかった非空値」ロジックだと
    // 統合先以外のレコードに書かれたメモが黙って失われる。備考と同様に全レコード分を連結して残す。
    merged["関係メモ"] = records
      .map(function (record) { return record["関係メモ"]; })
      .filter(Boolean)
      .join(" / ");

    return { merged: merged, absorbedIds: absorbedIds };
  }

  function nextSequenceNumber(records) {
    var max = 0;
    (records || []).forEach(function (record) {
      var id = record && record["企業ID"];
      if (typeof id !== "string") return;
      var match = id.match(/^C(\d+)$/);
      if (!match) return;
      var num = parseInt(match[1], 10);
      if (num > max) max = num;
    });
    return max + 1;
  }

  function applyMerges(records) {
    records = records || [];
    if (records.length === 0) {
      return { records: [], absorbedCount: 0 };
    }
    var duplicateGroups = findDuplicateGroups(records);
    var absorbedIdSet = {};
    var mergedByFirstId = {};
    duplicateGroups.forEach(function (group) {
      var result = mergeCompanyRecords(group);
      mergedByFirstId[group[0]["企業ID"]] = result.merged;
      result.absorbedIds.forEach(function (id) { absorbedIdSet[id] = true; });
    });
    var finalRecords = records
      .filter(function (record) { return !absorbedIdSet[record["企業ID"]]; })
      .map(function (record) { return mergedByFirstId[record["企業ID"]] || record; });
    return { records: finalRecords, absorbedCount: Object.keys(absorbedIdSet).length };
  }

  function propagateDoNotContact(records) {
    var doNotContactPhoneKeys = {};
    (records || []).forEach(function (record) {
      var phoneKey = normalizePhoneNumber(record["電話番号"]);
      if (phoneKey && record["連絡不要"] === true) {
        doNotContactPhoneKeys[phoneKey] = true;
      }
    });
    return (records || []).map(function (record) {
      var phoneKey = normalizePhoneNumber(record["電話番号"]);
      if (phoneKey && doNotContactPhoneKeys[phoneKey] && record["連絡不要"] !== true) {
        var updated = {};
        Object.keys(record).forEach(function (key) { updated[key] = record[key]; });
        updated["連絡不要"] = true;
        var note = "連絡不要伝播(同一電話番号)";
        updated["備考"] = record["備考"] ? record["備考"] + " / " + note : note;
        return updated;
      }
      return record;
    });
  }

  var api = {
    normalizeCorporateNumber: normalizeCorporateNumber,
    normalizePhoneNumber: normalizePhoneNumber,
    findDuplicateGroups: findDuplicateGroups,
    mergeCompanyRecords: mergeCompanyRecords,
    nextSequenceNumber: nextSequenceNumber,
    applyMerges: applyMerges,
    propagateDoNotContact: propagateDoNotContact,
    SCALAR_FIELDS: SCALAR_FIELDS
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowDedupe = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
