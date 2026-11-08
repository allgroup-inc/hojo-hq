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

  /* 法人番号(13桁)を確かめる(2026-11-06 §9-7)。
   * 先頭の1桁は検査用の数字で、残り12桁から決まる(国税庁の定め):
   *   検査用の数字 = 9 − (Σ 12桁の各数字 × 重み) を 9 で割った余り
   *   重みは、12桁を右の桁から数えて奇数番目が1、偶数番目が2
   * 戻り値: { ok, value(13桁の数字) , reason } */
  function validateCorporateNumber(raw) {
    var text = toHalfWidth(String(raw === null || raw === undefined ? "" : raw)).replace(/[\s-]/g, "");
    if (!text) return { ok: false, value: "", reason: "法人番号が空" };
    if (!/^[0-9]{13}$/.test(text)) return { ok: false, value: "", reason: "法人番号が13桁の数字でない" };
    var base = text.slice(1);
    var sum = 0;
    for (var n = 1; n <= 12; n++) {
      var digit = Number(base.charAt(12 - n));
      sum += digit * (n % 2 === 1 ? 1 : 2);
    }
    var expected = 9 - (sum % 9);
    if (Number(text.charAt(0)) !== expected) return { ok: false, value: "", reason: "法人番号の検査用の数字が合わない" };
    return { ok: true, value: text, reason: "" };
  }

  /* 新しく入る会社(LINE・LPの問い合わせなど)を、既にある会社へ自動で結び付けてよいかを決める(§9-7)。
   * 自動で結び付けるのは、次がすべてそろうときだけ。それ以外は自動では結び付けず、確認担当に回す。
   *   1. 入ってきた法人番号が正しい形(13桁・検査用の数字が合う)
   *   2. 台帳に、正しい形でその法人番号を持つ会社がちょうど1社ある(台帳側の番号も同じ確かめ方をする)
   *   3. 会社名か電話番号の少なくとも1つが、台帳のその会社と一致する(2026-11-06: 法人番号だけでは結び付けない)
   *   4. 会社名・電話番号に食い違いが無い(両方にあって違えば食い違い)
   * incoming: {法人番号, 会社名, 電話番号, 携帯番号}、companies: 企業マスタの行
   * 戻り値: { auto: true, companyId } / { auto: false, reason, candidates: [企業ID...] } */
  function decideAutoLink(incoming, companies) {
    var list = companies || [];
    var inc = incoming || {};
    var check = validateCorporateNumber(inc["法人番号"]);
    var candidates = findCandidatePairs([{ 企業ID: "__incoming__", 会社名: inc["会社名"], 電話番号: inc["電話番号"], 携帯番号: inc["携帯番号"], 法人番号: inc["法人番号"] }].concat(list))
      .pairs.filter(function (p) { return p.ids.indexOf("__incoming__") >= 0; })
      .map(function (p) { return p.ids[0] === "__incoming__" ? p.ids[1] : p.ids[0]; });
    if (!check.ok) return { auto: false, reason: check.reason, candidates: candidates };
    var same = list.filter(function (c) {
      var own = validateCorporateNumber(c["法人番号"]);
      return own.ok && own.value === check.value;
    });
    if (same.length === 0) return { auto: false, reason: "台帳に同じ法人番号の会社が無い", candidates: candidates };
    if (same.length > 1) return { auto: false, reason: "台帳に同じ法人番号の会社が複数ある", candidates: same.map(function (c) { return String(c["企業ID"]); }) };
    var hit = same[0];
    var hitId = String(hit["企業ID"]);
    var nameA = normalizeCompanyName(inc["会社名"]), nameB = normalizeCompanyName(hit["会社名"]);
    if (nameA && nameB && nameA !== nameB) return { auto: false, reason: "会社名が台帳と食い違う", candidates: [hitId] };
    var phonesA = [normalizePhone(inc["電話番号"]), normalizePhone(inc["携帯番号"])].filter(Boolean);
    var phonesB = [normalizePhone(hit["電話番号"]), normalizePhone(hit["携帯番号"])].filter(Boolean);
    var phoneMatch = phonesA.some(function (p) { return phonesB.indexOf(p) >= 0; });
    if (phonesA.length && phonesB.length && !phoneMatch) {
      return { auto: false, reason: "電話番号が台帳と食い違う", candidates: [hitId] };
    }
    var nameMatch = !!(nameA && nameB && nameA === nameB);
    if (!nameMatch && !phoneMatch) {
      return { auto: false, reason: "法人番号のほかに台帳と一致する会社名・電話番号が無い", candidates: [hitId] };
    }
    return { auto: true, companyId: hitId };
  }

  /* 台帳(企業マスタ)側の法人番号を確かめる(2026-11-06)。台帳は書き換えない。
   * 戻り値: { invalid: [{企業ID, reason}], duplicates: [[企業ID...]], counts: {...} }
   *  - 空欄は「未入力」として数えるだけで、正しくないものには入れない
   *  - 正しい形の番号が2社以上で同じなら、重複として組を出す(同じ会社の二重登録か、入力の誤り)
   * 番号そのものは返さない(件数と企業IDだけ) */
  function auditCorporateNumbers(companies) {
    var invalid = [], byNumber = {};
    var counts = { 確かめた会社: 0, 正しい形: 0, 未入力: 0, 正しくない: 0, 重複の組: 0 };
    (companies || []).forEach(function (c) {
      var id = String(c["企業ID"] || "").trim();
      if (!id) return;
      counts.確かめた会社++;
      var r = validateCorporateNumber(c["法人番号"]);
      if (r.ok) {
        counts.正しい形++;
        (byNumber[r.value] = byNumber[r.value] || []).push(id);
      } else if (r.reason === "法人番号が空") {
        counts.未入力++;
      } else {
        counts.正しくない++;
        invalid.push({ 企業ID: id, reason: r.reason });
      }
    });
    var duplicates = Object.keys(byNumber)
      .map(function (k) { return byNumber[k].filter(function (id, i, arr) { return arr.indexOf(id) === i; }).sort(); })
      .filter(function (ids) { return ids.length > 1; })
      .sort(function (a, b) { return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0; });
    counts.重複の組 = duplicates.length;
    invalid.sort(function (a, b) { return a.企業ID < b.企業ID ? -1 : a.企業ID > b.企業ID ? 1 : 0; });
    return { invalid: invalid, duplicates: duplicates, counts: counts };
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
    validateCorporateNumber: validateCorporateNumber,
    decideAutoLink: decideAutoLink,
    auditCorporateNumbers: auditCorporateNumbers,
    orphanIds: orphanIds
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowWld02NameMatch = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
