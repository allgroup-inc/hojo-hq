/**
 * 会社情報の読み取り(v1.8・2026-10-17 福田さん依頼「同じ質問が繰り返される」への対応)
 *
 * これまでは「会社名：」「代表者名：」と一字一句同じ書き方のときだけ読み取れたため、
 * 「代表者：」「社名 ◯◯」「値を次の行に書く」などの書き方だと会社名・代表者名が空になり、
 * テンプレの記入をもう一度お願いする返信が繰り返されていた。
 * ここでは項目名の言い換え・区切り記号の有無・次の行への記入を受け付け、
 * 読み取れた項目と読み取れなかった項目を分けて返す(未回答の項目だけを聞き直すため)。
 *
 * GASではファイルをまたいで関数を共有する。Node(テスト)では module.exports で読み込む。
 */

// 項目名の言い換え。長いものから順に照合する(「代表取締役」を「代表」より先に)
const INFO_LABELS = [
  ['company', ['会社名', '企業名', '法人名', '事業所名', '事業者名', '屋号', '店舗名', '店名', '社名']],
  ['ceo', ['代表取締役社長', '代表者名', '代表者氏名', '代表取締役', '代表者', '社長名', '代表', '社長']],
  ['contact', ['担当者名', '担当者氏名', 'ご担当者', '担当者', '担当']],
  ['tel', ['電話番号', '携帯番号', '連絡先電話', '電話', '携帯', 'TEL', 'Tel', 'tel']],
  ['mail', ['メールアドレス', 'Eメール', 'E-mail', 'e-mail', 'Email', 'email', 'メール', 'MAIL', 'Mail', 'mail']],
  ['city', ['所在地', '住所', '市町村', '所在']],
];
// 短い項目名は、後ろに区切り(：や空白)があるときだけ項目名とみなす(「代表的な…」等の誤認防止)
const INFO_SHORT_LABEL_MAX = 2;
const INFO_HEADER_RE = /^[\s　]*【?\s*会社情報登録\s*】?/;
const INFO_SEP_RE = /^[\s　]*[：:＝=]/;

function infoLabelIndex_() {
  const list = [];
  INFO_LABELS.forEach(function (pair) {
    pair[1].forEach(function (label) { list.push({ field: pair[0], label: label }); });
  });
  list.sort(function (a, b) { return b.label.length - a.label.length; });
  return list;
}

/* 1行を「項目名+値」に分ける。項目名で始まらない行は null */
function splitLabeledLine_(line, index) {
  const s = String(line || '').replace(/^[\s　・\-\*■●○◆◇▶︎▶►✔✅①-⑳0-9０-９\.．、)）]+/, '');
  for (let i = 0; i < index.length; i++) {
    const label = index[i].label;
    if (s.indexOf(label) !== 0) continue;
    const after = s.slice(label.length);
    const hasSep = INFO_SEP_RE.test(after);
    const hasSpace = /^[\s　]/.test(after);
    if (label.length <= INFO_SHORT_LABEL_MAX && after && !hasSep && !hasSpace) continue;
    // 「会社名は◯◯です」のような書き方の「は」「です」も外す
    // (区切り記号があるときは外さない。「会社名：はなまる商事」の「は」を守る)
    let value = after.replace(INFO_SEP_RE, '').replace(/^[\s　]+|[\s　]+$/g, '');
    if (!hasSep) value = value.replace(/^(は|が|も)[\s　]*/, '');
    value = value.replace(/[\s　]*(です|になります)[。.!！]?$/, '');
    return { field: index[i].field, value: value };
  }
  return null;
}

/**
 * 本文から会社情報を読み取る。
 * 戻り値: { hasHeader, company, ceo, contact, tel, mail, city, labeled(項目名つきの行数), rest(項目名のない行) }
 */
function parseCompanyInfo_(text) {
  const index = infoLabelIndex_();
  const out = { hasHeader: false, company: '', ceo: '', contact: '', tel: '', mail: '', city: '', labeled: 0, rest: [] };
  let body = String(text || '').replace(/\r\n?/g, '\n');
  if (INFO_HEADER_RE.test(body) && /会社情報登録/.test(body.split('\n')[0])) {
    out.hasHeader = true;
    body = body.replace(INFO_HEADER_RE, '');
  }
  const lines = body.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].replace(/^[\s　]+|[\s　]+$/g, '');
    if (!line) continue;
    const hit = splitLabeledLine_(line, index);
    if (!hit) { out.rest.push(line); continue; }
    out.labeled++;
    let value = hit.value;
    // 「会社名：」の次の行に値を書く書き方にも対応(次の行が別の項目名なら空のまま)
    if (!value && i + 1 < lines.length) {
      const next = lines[i + 1].replace(/^[\s　]+|[\s　]+$/g, '');
      if (next && !splitLabeledLine_(next, index)) { value = next; i++; }
    }
    // 「メールで連絡ください」等の文を、メールアドレスとして拾わない
    if (hit.field === 'mail' && value && value.indexOf('@') === -1 && value.indexOf('＠') === -1) {
      out.labeled--; out.rest.push(line); continue;
    }
    if (value && !out[hit.field]) out[hit.field] = value;
  }
  // 項目名がなくても、メールアドレス・電話番号の形の行は拾う
  out.rest = out.rest.filter(function (line) {
    if (!out.mail && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(line)) { out.mail = line; return false; }
    if (!out.tel && /^[0０+＋][0-9０-９\-－ー‐()（）\s　]{8,}$/.test(line)) { out.tel = line; return false; }
    return true;
  });
  return out;
}

/* 会話の途中で「会社名：◯◯」のように項目名ごと送られたら、値だけを取り出す */
function stripInfoLabel_(text) {
  const t = String(text || '').trim();
  const hit = splitLabeledLine_(t, infoLabelIndex_());
  return hit && hit.value ? hit.value : t;
}

/* 必須項目(会社名・代表者名)のうち、まだ無いものを順に返す */
function missingInfoFields_(info) {
  const missing = [];
  if (!info.company) missing.push('company');
  if (!info.ceo) missing.push('ceo');
  return missing;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    parseCompanyInfo_: parseCompanyInfo_,
    stripInfoLabel_: stripInfoLabel_,
    missingInfoFields_: missingInfoFields_,
  };
}
