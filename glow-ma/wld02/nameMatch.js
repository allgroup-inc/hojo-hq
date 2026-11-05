/* 世界の架け橋 WLD-02 過去の企業IDの名寄せ照合(読み取りのみ・候補を出すだけ)
 *
 * 企業マスタの行から「同じ会社かもしれない企業IDの組」の候補を出す。台帳は書き換えない。
 * 候補は確認担当(当面は小柳さん)が見て、承認したものだけを企業ID対応表に入れる(設計書 v0 §5)。
 * 候補の中身(会社名・企業ID)は顧客情報のため、非公開リポジトリ(glow-docs-private)にだけ置く。
 * hojo-hq には件数だけを書く(2026-11-04 の議事のウタガイ)。
 *
 * 候補にする理由(強い順):
 * - 法人番号が同じ(13桁)
 * - 電話番号が同じ(数字だけで10桁以上)
 * - 会社名が同じ(株式会社・有限会社・(株) 等と空白・記号を除き、全角英数を半角にそろえる)
 * 1組に理由が複数あれば、すべて並べる。
 */
(function (global) {
  "use strict";

  var LEGAL_FORMS = [
    "株式会社", "有限会社", "合同会社", "合資会社", "合名会社",
    "一般社団法人", "一般財団法人", "公益社団法人", "公益財団法人",
    "社会福祉法人", "医療法人社団", "医療法人財団", "医療法人", "特定非営利活動法人", "NPO法人",
    "農業協同組合", "協同組合", "企業組合", "事業協同組合"
  ];
  var LEGAL_ABBREVIATIONS = /[(（]\s*(株|有|合|同|資|名|社|財|医|特非)\s*[)）]|㈱|㈲|㈳|㈶/g;

  function toHalfWidth(s) {
    return s.replace(/[！-～]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0xFEE0); })
      .replace(/　/g, " ");
  }

  function normalizeCompanyName(raw) {
    var s = toHalfWidth(String(raw === null || raw === undefined ? "" : raw)).trim();
    if (!s) return "";
    s = s.replace(LEGAL_ABBREVIATIONS, "");
    LEGAL_FORMS.forEach(function (form) { s = s.split(form).join(""); });
    s = s.replace(/[\s・･.,、。\-ー―‐()（）「」『』"'"]/g, "").toLowerCase();
    // 「(社名不明)」などの仮の名前は照合しない
    if (!s || /^社名不明/.test(s) || s === "不明") return "";
    return s;
  }

  function normalizeCorporateNumber(raw) {
    var digits = String(raw === null || raw === undefined ? "" : raw).replace(/[^0-9]/g, "");
    return digits.length === 13 ? digits : "";
  }

  function normalizePhone(raw) {
    var digits = toHalfWidth(String(raw === null || raw === undefined ? "" : raw)).replace(/[^0-9]/g, "");
    return digits.length >= 10 ? digits : "";
  }

  /* companies: [{企業ID, 法人番号, 会社名, 電話番号, 携帯番号}]
   * 戻り値: { pairs: [{ids:[a,b], reasons:[...]}], counts: {...} } — ids は並べ替え済み、pairs は ids 順 */
  function findCandidatePairs(companies) {
    var keys = [
      { reason: "法人番号が同じ", of: function (c) { return [normalizeCorporateNumber(c["法人番号"])]; } },
      { reason: "電話番号が同じ", of: function (c) { return [normalizePhone(c["電話番号"]), normalizePhone(c["携帯番号"])]; } },
      { reason: "会社名が同じ", of: function (c) { return [normalizeCompanyName(c["会社名"])]; } }
    ];
    var pairMap = {};
    keys.forEach(function (key) {
      var groups = {};
      (companies || []).forEach(function (c) {
        var id = String(c["企業ID"] || "").trim();
        if (!id) return;
        var seen = {};
        key.of(c).forEach(function (v) {
          if (!v || seen[v]) return;
          seen[v] = true;
          (groups[v] = groups[v] || []).push(id);
        });
      });
      Object.keys(groups).forEach(function (v) {
        var ids = groups[v].filter(function (id, i, arr) { return arr.indexOf(id) === i; }).sort();
        for (var i = 0; i < ids.length; i++) {
          for (var j = i + 1; j < ids.length; j++) {
            var k = ids[i] + "|" + ids[j];
            var p = pairMap[k] || (pairMap[k] = { ids: [ids[i], ids[j]], reasons: [] });
            if (p.reasons.indexOf(key.reason) < 0) p.reasons.push(key.reason);
          }
        }
      });
    });
    var pairs = Object.keys(pairMap).sort().map(function (k) { return pairMap[k]; });
    var counts = { 候補の組: pairs.length, 法人番号が同じ: 0, 電話番号が同じ: 0, 会社名が同じ: 0, 理由が2つ以上: 0 };
    pairs.forEach(function (p) {
      p.reasons.forEach(function (r) { counts[r]++; });
      if (p.reasons.length > 1) counts.理由が2つ以上++;
    });
    var involved = {};
    pairs.forEach(function (p) { involved[p.ids[0]] = true; involved[p.ids[1]] = true; });
    counts.かかわる企業ID = Object.keys(involved).length;
    return { pairs: pairs, counts: counts };
  }

  /* 対応履歴ログなどが指している企業IDのうち、企業マスタに無いもの(消えた・統合された可能性) */
  function orphanIds(referencedIds, companies) {
    var known = {};
    (companies || []).forEach(function (c) { known[String(c["企業ID"] || "").trim()] = true; });
    var out = {};
    (referencedIds || []).forEach(function (id) {
      var s = String(id || "").trim();
      if (s && !known[s]) out[s] = true;
    });
    return Object.keys(out).sort();
  }

  var api = {
    normalizeCompanyName: normalizeCompanyName,
    normalizePhone: normalizePhone,
    findCandidatePairs: findCandidatePairs,
    orphanIds: orphanIds
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowWld02NameMatch = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
