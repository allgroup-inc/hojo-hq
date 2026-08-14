/* アポ管理コンソール Web App画面(1ページ・モバイルファースト)
 * ブラウザ相当のGAS(global.ApoPage)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/apo_kanri_page.test.mjs でスモークテストされる。
 *
 * 設計原則(2026-08-14 小柳さん要望): 連携・管理・確認・便利さのすべてで最高の使い勝手。
 * 「主要操作は2タップ以内」「開いた瞬間に今日が見える」を守る。
 * サーバ関数は ApoRunner.gs の getBoard / saveAppointment / updateStatus /
 * reportDelay / getFormOptions を google.script.run で呼ぶ。
 * 画面側の描画は必ず esc() を通す(顧客名・メモ等の自由入力をinnerHTMLへ生で入れない)。
 */
(function (global) {
  "use strict";

  function buildApoAppHtml() {
    return "<!doctype html>\n" +
"<html lang=\"ja\"><head><meta charset=\"utf-8\">\n" +
"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n" +
"<title>アポ管理コンソール</title>\n" +
"<style>\n" +
":root{--navy:#00335c;--navy-deep:#001f3a;--orange:#F88800;--bg:#f4f6f9;--card:#ffffff;--ink:#11202c;--sub:#4a5a66;--line:#dde4ea;--ok:#1a7f4e;--warn:#b95000;--bad:#b3261e;--chip:#e8eef4}\n" +
"@media (prefers-color-scheme: dark){:root{--bg:#0d1721;--card:#152232;--ink:#e8eef4;--sub:#9fb0bd;--line:#28394b;--chip:#1d2d3f}}\n" +
"*{box-sizing:border-box;margin:0;padding:0}\n" +
"body{font-family:-apple-system,BlinkMacSystemFont,\"Hiragino Sans\",\"Noto Sans JP\",Meiryo,sans-serif;background:var(--bg);color:var(--ink);padding-bottom:6rem}\n" +
"header{position:sticky;top:0;z-index:20;background:linear-gradient(135deg,var(--navy-deep),var(--navy));color:#fff;padding:0.8rem 1rem 0.6rem;box-shadow:0 2px 8px rgba(0,0,0,.25)}\n" +
"header h1{font-size:1rem;letter-spacing:.05em}\n" +
"header h1 span{color:var(--orange)}\n" +
".topbar{display:flex;align-items:center;justify-content:space-between;gap:.5rem}\n" +
".seg{display:flex;background:rgba(255,255,255,.14);border-radius:999px;padding:2px}\n" +
".seg button{border:0;background:transparent;color:#fff;padding:.35rem .9rem;border-radius:999px;font-size:.85rem;cursor:pointer}\n" +
".seg button.on{background:var(--orange);color:#fff;font-weight:700}\n" +
".chips{display:flex;gap:.4rem;overflow-x:auto;padding:.6rem 1rem .2rem;-webkit-overflow-scrolling:touch}\n" +
".chip{flex:none;border:1px solid var(--line);background:var(--chip);color:var(--ink);border-radius:999px;padding:.3rem .8rem;font-size:.8rem;cursor:pointer}\n" +
".chip.on{background:var(--navy);border-color:var(--navy);color:#fff}\n" +
".summary{display:flex;gap:.6rem;align-items:baseline;padding:.5rem 1rem .2rem;color:var(--sub);font-size:.85rem}\n" +
".summary b{color:var(--ink);font-size:1.05rem}\n" +
".summary .unconf b{color:var(--warn)}\n" +
"main{padding:0.4rem 1rem}\n" +
".daylabel{margin:.9rem 0 .3rem;font-size:.85rem;color:var(--sub);font-weight:700}\n" +
".card{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--navy);border-radius:12px;padding:.7rem .85rem;margin:.5rem 0;display:flex;gap:.8rem;cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,.06)}\n" +
".card .time{flex:none;text-align:center;min-width:3.4rem}\n" +
".card .time b{display:block;font-size:1.05rem}\n" +
".card .time small{color:var(--sub)}\n" +
".card .body{flex:1;min-width:0}\n" +
".card .cust{font-weight:700;font-size:.95rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n" +
".card .meta{color:var(--sub);font-size:.8rem;margin-top:.15rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n" +
".badges{display:flex;gap:.35rem;margin-top:.35rem;flex-wrap:wrap}\n" +
".pill{font-size:.7rem;border-radius:999px;padding:.12rem .55rem;border:1px solid var(--line);color:var(--sub)}\n" +
".pill.st-予定{background:#fff4e0;color:#8a5b00;border-color:#f0d9a8}\n" +
".pill.st-確定{background:#e2f2e9;color:var(--ok);border-color:#b7dcc8}\n" +
".pill.st-実施済{background:var(--chip)}\n" +
".pill.st-申込み{background:var(--orange);color:#fff;border-color:var(--orange);font-weight:700}\n" +
".pill.st-再調整中{background:#fdebd7;color:var(--warn);border-color:#f4c894}\n" +
".pill.cancel{background:#fbe9e7;color:var(--bad);border-color:#eec2bd;text-decoration:line-through}\n" +
".pill.temp-高{border-color:var(--bad);color:var(--bad)}\n" +
".pill.temp-中{border-color:var(--warn);color:var(--warn)}\n" +
".card.done{opacity:.62}\n" +
".empty{text-align:center;color:var(--sub);padding:2.2rem 1rem;font-size:.9rem}\n" +
".fab{position:fixed;right:1rem;bottom:1.2rem;z-index:25;border:0;border-radius:999px;background:var(--orange);color:#fff;font-size:.95rem;font-weight:700;padding:.9rem 1.3rem;box-shadow:0 4px 14px rgba(248,136,0,.45);cursor:pointer}\n" +
".sheetback{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:30;display:none}\n" +
".sheetback.open{display:block}\n" +
".sheet{position:fixed;left:0;right:0;bottom:0;z-index:31;background:var(--card);border-radius:16px 16px 0 0;padding:1rem 1rem 1.4rem;transform:translateY(105%);transition:transform .22s ease}\n" +
"@media (prefers-reduced-motion: reduce){.sheet{transition:none}}\n" +
".sheet.open{transform:translateY(0)}\n" +
".sheet h2{font-size:.95rem;margin-bottom:.6rem}\n" +
".sheet .grid{display:grid;grid-template-columns:1fr 1fr;gap:.5rem}\n" +
".sheet button{border:1px solid var(--line);background:var(--chip);color:var(--ink);border-radius:10px;padding:.7rem .4rem;font-size:.85rem;cursor:pointer}\n" +
".sheet button.primary{background:var(--navy);border-color:var(--navy);color:#fff;font-weight:700}\n" +
".sheet button.danger{color:var(--bad)}\n" +
".sheet .delayrow{display:flex;gap:.5rem;margin-top:.6rem}\n" +
".sheet .delayrow button{flex:1;background:#fdebd7;border-color:#f4c894;color:var(--warn);font-weight:700}\n" +
".modal{position:fixed;inset:0;z-index:40;background:var(--bg);display:none;overflow-y:auto;padding:1rem}\n" +
".modal.open{display:block}\n" +
".modal h2{font-size:1rem;margin:.3rem 0 .8rem}\n" +
".field{margin-bottom:.7rem}\n" +
".field label{display:block;font-size:.78rem;color:var(--sub);margin-bottom:.25rem;font-weight:700}\n" +
".field input,.field select,.field textarea{width:100%;border:1px solid var(--line);border-radius:10px;padding:.6rem .7rem;font-size:16px;background:var(--card);color:var(--ink)}\n" +
".row2{display:grid;grid-template-columns:1fr 1fr;gap:.6rem}\n" +
".overlapwarn{display:none;background:#fdebd7;border:1px solid #f4c894;color:#7a4a00;border-radius:10px;padding:.6rem .7rem;font-size:.82rem;margin-bottom:.7rem;line-height:1.6}\n" +
".overlapwarn.show{display:block}\n" +
".btnrow{display:flex;gap:.6rem;margin-top:1rem}\n" +
".btnrow button{flex:1;border:0;border-radius:10px;padding:.85rem;font-size:.95rem;cursor:pointer}\n" +
".btnrow .save{background:var(--orange);color:#fff;font-weight:700}\n" +
".btnrow .back{background:var(--chip);color:var(--ink)}\n" +
".toast{position:fixed;left:50%;bottom:5.6rem;transform:translateX(-50%);z-index:50;background:var(--navy-deep);color:#fff;border-radius:999px;padding:.55rem 1.1rem;font-size:.85rem;opacity:0;pointer-events:none;transition:opacity .25s}\n" +
".toast.show{opacity:1}\n" +
".loading{text-align:center;color:var(--sub);padding:2rem;font-size:.85rem}\n" +
".panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:.9rem;margin:.7rem 0}\n" +
".panel h3{font-size:.85rem;margin-bottom:.6rem}\n" +
".panel .note{color:var(--sub);font-size:.72rem;margin-top:.6rem;line-height:1.6}\n" +
".fillrow{margin:.55rem 0}\n" +
".fillrow .lbl{display:flex;justify-content:space-between;font-size:.8rem;margin-bottom:.2rem}\n" +
".fillrow .lbl b{font-weight:700}\n" +
".fillrow .track{height:10px;border-radius:999px;background:var(--chip);overflow:hidden}\n" +
".fillrow .bar{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--navy),var(--orange))}\n" +
".funnel{display:flex;flex-direction:column;gap:.4rem}\n" +
".fstep{display:flex;justify-content:space-between;align-items:baseline;border-left:4px solid var(--navy);background:var(--chip);border-radius:8px;padding:.55rem .7rem;font-size:.85rem}\n" +
".fstep b{font-size:1.05rem}\n" +
".fstep .rate{color:var(--orange);font-weight:700}\n" +
"</style></head><body>\n" +
"<header><div class=\"topbar\"><h1>アポ管理<span>コンソール</span></h1>\n" +
"<div class=\"seg\"><button id=\"segDay\" class=\"on\">本日</button><button id=\"segWeek\">週</button><button id=\"segStats\">分析</button></div></div></header>\n" +
"<div class=\"chips\" id=\"chips\"><button class=\"chip\" id=\"chipMine\">自分のアポ</button></div>\n" +
"<div class=\"summary\" id=\"summary\"></div>\n" +
"<main id=\"board\"><div class=\"loading\">読み込み中…</div></main>\n" +
"<button class=\"fab\" id=\"fabNew\">+ 新規アポ</button>\n" +
"<div class=\"sheetback\" id=\"sheetBack\"></div>\n" +
"<div class=\"sheet\" id=\"sheet\">\n" +
"  <h2 id=\"sheetTitle\"></h2>\n" +
"  <div class=\"grid\">\n" +
"    <button data-st=\"確定\">✅ 確定</button>\n" +
"    <button data-st=\"実施済\">🏁 実施済</button>\n" +
"    <button data-st=\"申込み\" class=\"primary\">🎉 申込み</button>\n" +
"    <button data-st=\"再調整中\">🔁 再調整中</button>\n" +
"    <button data-st=\"キャンセル(顧客都合)\" class=\"danger\">❌ キャンセル(顧客都合)</button>\n" +
"    <button data-st=\"キャンセル(自社都合)\" class=\"danger\">❌ キャンセル(自社都合)</button>\n" +
"  </div>\n" +
"  <div class=\"delayrow\"><span style=\"align-self:center;font-size:.85rem\">⏰ 遅れそう:</span>\n" +
"    <button data-delay=\"15\">+15分</button><button data-delay=\"30\">+30分</button><button data-delay=\"60\">+60分</button></div>\n" +
"  <div class=\"btnrow\"><button class=\"back\" id=\"sheetClose\">閉じる</button><button class=\"save\" id=\"sheetEdit\">✏️ 編集</button></div>\n" +
"</div>\n" +
"<div class=\"modal\" id=\"modal\">\n" +
"  <h2 id=\"modalTitle\">新規アポ</h2>\n" +
"  <div class=\"overlapwarn\" id=\"overlapWarn\"></div>\n" +
"  <div class=\"row2\">\n" +
"    <div class=\"field\"><label>日付</label><input type=\"date\" id=\"fDate\"></div>\n" +
"    <div class=\"field\"><label>開始時刻</label><input type=\"time\" id=\"fTime\"></div>\n" +
"  </div>\n" +
"  <div class=\"row2\">\n" +
"    <div class=\"field\"><label>所要分</label><select id=\"fDuration\"><option>30</option><option selected>60</option><option>90</option><option>120</option></select></div>\n" +
"    <div class=\"field\"><label>温度感</label><select id=\"fTemp\"></select></div>\n" +
"  </div>\n" +
"  <div class=\"field\"><label>顧客名</label><input type=\"text\" id=\"fCustomer\" placeholder=\"例: ◯◯株式会社 △△様\"></div>\n" +
"  <div class=\"row2\">\n" +
"    <div class=\"field\"><label>形式</label><select id=\"fFormat\"></select></div>\n" +
"    <div class=\"field\"><label>ステータス</label><select id=\"fStatus\"></select></div>\n" +
"  </div>\n" +
"  <div class=\"field\"><label>場所またはURL</label><input type=\"text\" id=\"fPlace\" placeholder=\"住所・店舗名・会議URL\"></div>\n" +
"  <div class=\"row2\">\n" +
"    <div class=\"field\"><label>担当営業</label><select id=\"fSales\"></select></div>\n" +
"    <div class=\"field\"><label>アポ入れ担当</label><select id=\"fSetter\"></select></div>\n" +
"  </div>\n" +
"  <div class=\"field\"><label>メモ</label><textarea id=\"fMemo\" rows=\"2\" placeholder=\"引き継ぎ事項・注意点\"></textarea></div>\n" +
"  <div class=\"btnrow\"><button class=\"back\" id=\"modalClose\">戻る</button><button class=\"save\" id=\"modalSave\">保存して通知</button></div>\n" +
"</div>\n" +
"<div class=\"toast\" id=\"toast\"></div>\n" +
"<script>\n" +
"var state = { view: 'day', owner: '', mine: false, meName: '', board: null, options: null, editingId: null, selected: null, confirmedOverlap: false };\n" +
"function esc(text) {\n" +
"  return String(text == null ? '' : text).replace(/[&<>\"']/g, function (ch) {\n" +
"    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '\"': '&quot;', \"'\": '&#39;' }[ch];\n" +
"  });\n" +
"}\n" +
"function $(id) { return document.getElementById(id); }\n" +
"function toast(message) {\n" +
"  var el = $('toast'); el.textContent = message; el.classList.add('show');\n" +
"  setTimeout(function () { el.classList.remove('show'); }, 2600);\n" +
"}\n" +
"function todayString() {\n" +
"  var d = new Date();\n" +
"  return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);\n" +
"}\n" +
"function load() {\n" +
"  $('board').innerHTML = '<div class=\"loading\">読み込み中…</div>';\n" +
"  if (state.view === 'stats') {\n" +
"    google.script.run.withSuccessHandler(renderStats).withFailureHandler(fail).getStats();\n" +
"    return;\n" +
"  }\n" +
"  google.script.run.withSuccessHandler(renderBoard).withFailureHandler(fail)\n" +
"    .getBoard({ view: state.view, date: todayString(), owner: effectiveOwner() });\n" +
"}\n" +
"function formatHours(minutes) { return (Math.round(minutes / 6) / 10) + 'h'; }\n" +
"function formatRate(rate) { return rate === null || rate === undefined ? '—' : Math.round(rate * 100) + '%'; }\n" +
"function renderStats(stats) {\n" +
"  $('summary').innerHTML = '<span>本日の埋まり状況+過去30日の転換</span>';\n" +
"  var fill = stats.fill || { owners: [], total: { bookedMinutes: 0, count: 0 } };\n" +
"  var funnel = stats.funnel || { concluded: 0, completed: 0, signups: 0, visitRate: null, signupRate: null };\n" +
"  var html = '<div class=\"panel\"><h3>📊 本日の埋まり状況(営業時間 9:00〜18:00 換算)</h3>';\n" +
"  html += '<div class=\"fillrow\"><div class=\"lbl\"><span>全体</span><b>' + fill.total.count + '件・' + formatHours(fill.total.bookedMinutes) + '</b></div></div>';\n" +
"  fill.owners.forEach(function (entry) {\n" +
"    html += '<div class=\"fillrow\"><div class=\"lbl\"><span>' + esc(entry.owner) + '</span>' +\n" +
"      '<b>' + entry.count + '件・' + formatHours(entry.bookedMinutes) + '(' + Math.round(entry.ratio * 100) + '%)</b></div>' +\n" +
"      '<div class=\"track\"><div class=\"bar\" style=\"width:' + Math.round(entry.ratio * 100) + '%\"></div></div></div>';\n" +
"  });\n" +
"  html += '<div class=\"note\">※空き=キャンセル・再調整中を除いた予約済み時間。評価目的では使いません</div></div>';\n" +
"  html += '<div class=\"panel\"><h3>🔀 転換ファネル(過去30日・' + esc(stats.sinceDate) + '以降・チーム全体)</h3><div class=\"funnel\">';\n" +
"  html += '<div class=\"fstep\"><span>結果が出たアポ</span><b>' + funnel.concluded + '件</b></div>';\n" +
"  html += '<div class=\"fstep\"><span>訪問実施(実施済+申込み)</span><span><span class=\"rate\">' + formatRate(funnel.visitRate) + '</span> <b>' + funnel.completed + '件</b></span></div>';\n" +
"  html += '<div class=\"fstep\"><span>申込み</span><span><span class=\"rate\">' + formatRate(funnel.signupRate) + '</span> <b>' + funnel.signups + '件</b></span></div>';\n" +
"  html += '</div><div class=\"note\">率の母数: 訪問実施率=結果が出たアポ、申込み率=訪問実施。' +\n" +
"    (funnel.concluded < 10 ? '<br>⚠️ 件数が少ないため参考値です(母数10件未満)' : '') +\n" +
"    '<br>※予定・確定・再調整中のアポは結果待ちのため含みません。評価目的では使いません</div></div>';\n" +
"  $('board').innerHTML = html;\n" +
"}\n" +
"function effectiveOwner() { return state.mine ? state.meName : state.owner; }\n" +
"function fail(error) { toast('エラー: ' + (error && error.message ? error.message : error)); }\n" +
"function statusClass(status) {\n" +
"  if (status === 'キャンセル(顧客都合)' || status === 'キャンセル(自社都合)') return 'pill cancel';\n" +
"  return 'pill st-' + status;\n" +
"}\n" +
"function cardHtml(apo) {\n" +
"  var doneClass = (apo['ステータス'] === '実施済' || apo['ステータス'].indexOf('キャンセル') === 0) ? ' done' : '';\n" +
"  return '<div class=\"card' + doneClass + '\" data-id=\"' + esc(apo['アポID']) + '\">' +\n" +
"    '<div class=\"time\"><b>' + esc(apo['開始時刻']) + '</b><small>' + esc(apo['所要分']) + '分</small></div>' +\n" +
"    '<div class=\"body\"><div class=\"cust\">' + esc(apo['顧客名']) + '</div>' +\n" +
"    '<div class=\"meta\">' + esc(apo['形式']) + ' ' + esc(apo['場所またはURL']) + ' / 営業: ' + esc(apo['担当営業']) + '</div>' +\n" +
"    '<div class=\"badges\"><span class=\"' + statusClass(apo['ステータス']) + '\">' + esc(apo['ステータス']) + '</span>' +\n" +
"    '<span class=\"pill temp-' + esc(apo['温度感']) + '\">温度 ' + esc(apo['温度感']) + '</span></div></div></div>';\n" +
"}\n" +
"function renderBoard(board) {\n" +
"  state.board = board; state.meName = board.meName || '';\n" +
"  renderChips(board.salesStaff || []);\n" +
"  var html = '';\n" +
"  if (state.view === 'day') {\n" +
"    var view = board.dayView || { items: [], summary: { total: 0, unconfirmed: 0 } };\n" +
"    $('summary').innerHTML = '<span>本日 <b>' + view.summary.total + '</b>件</span>' +\n" +
"      '<span class=\"unconf\">未確定 <b>' + view.summary.unconfirmed + '</b>件</span>';\n" +
"    html = view.items.length ? view.items.map(cardHtml).join('') :\n" +
"      '<div class=\"empty\">本日のアポはありません。<br>右下の「+ 新規アポ」から登録できます。</div>';\n" +
"  } else {\n" +
"    $('summary').innerHTML = '<span>今日から7日間</span>';\n" +
"    (board.week || []).forEach(function (day) {\n" +
"      html += '<div class=\"daylabel\">' + esc(day.date) + '(' + day.items.length + '件)</div>';\n" +
"      html += day.items.length ? day.items.map(cardHtml).join('') : '<div class=\"empty\" style=\"padding:.4rem\">-</div>';\n" +
"    });\n" +
"  }\n" +
"  $('board').innerHTML = html;\n" +
"  Array.prototype.forEach.call(document.querySelectorAll('.card'), function (el) {\n" +
"    el.addEventListener('click', function () { openSheet(el.getAttribute('data-id')); });\n" +
"  });\n" +
"}\n" +
"function renderChips(salesStaff) {\n" +
"  var container = $('chips');\n" +
"  container.innerHTML = '<button class=\"chip' + (state.mine ? ' on' : '') + '\" id=\"chipMine\">自分のアポ</button>' +\n" +
"    salesStaff.map(function (name) {\n" +
"      return '<button class=\"chip' + (!state.mine && state.owner === name ? ' on' : '') + '\" data-owner=\"' + esc(name) + '\">' + esc(name) + '</button>';\n" +
"    }).join('');\n" +
"  $('chipMine').addEventListener('click', function () { state.mine = !state.mine; state.owner = ''; load(); });\n" +
"  Array.prototype.forEach.call(container.querySelectorAll('[data-owner]'), function (el) {\n" +
"    el.addEventListener('click', function () {\n" +
"      var name = el.getAttribute('data-owner');\n" +
"      state.owner = (state.owner === name) ? '' : name; state.mine = false; load();\n" +
"    });\n" +
"  });\n" +
"}\n" +
"function findApo(apoId) {\n" +
"  var pools = [];\n" +
"  if (state.board && state.board.dayView) pools = pools.concat(state.board.dayView.items);\n" +
"  (state.board && state.board.week || []).forEach(function (day) { pools = pools.concat(day.items); });\n" +
"  return pools.filter(function (a) { return a['アポID'] === apoId; })[0] || null;\n" +
"}\n" +
"function openSheet(apoId) {\n" +
"  var apo = findApo(apoId); if (!apo) return;\n" +
"  state.selected = apo;\n" +
"  $('sheetTitle').textContent = apo['開始時刻'] + ' ' + apo['顧客名'] + '(' + apo['ステータス'] + ')';\n" +
"  $('sheetBack').classList.add('open'); $('sheet').classList.add('open');\n" +
"}\n" +
"function closeSheet() { $('sheetBack').classList.remove('open'); $('sheet').classList.remove('open'); }\n" +
"function ensureOptions(callback) {\n" +
"  if (state.options) { callback(); return; }\n" +
"  google.script.run.withSuccessHandler(function (options) { state.options = options; callback(); })\n" +
"    .withFailureHandler(fail).getFormOptions();\n" +
"}\n" +
"function fillSelect(id, values, current) {\n" +
"  $(id).innerHTML = values.map(function (value) {\n" +
"    return '<option' + (value === current ? ' selected' : '') + '>' + esc(value) + '</option>';\n" +
"  }).join('');\n" +
"}\n" +
"function openModal(apo) {\n" +
"  ensureOptions(function () {\n" +
"    var options = state.options;\n" +
"    state.editingId = apo ? apo['アポID'] : null;\n" +
"    state.confirmedOverlap = false;\n" +
"    $('overlapWarn').classList.remove('show');\n" +
"    $('modalTitle').textContent = apo ? 'アポ編集' : '新規アポ';\n" +
"    $('fDate').value = apo ? apo['日付'] : todayString();\n" +
"    $('fTime').value = apo ? apo['開始時刻'] : '10:00';\n" +
"    $('fDuration').value = apo ? String(apo['所要分'] || 60) : '60';\n" +
"    $('fCustomer').value = apo ? apo['顧客名'] : '';\n" +
"    $('fPlace').value = apo ? apo['場所またはURL'] : '';\n" +
"    $('fMemo').value = apo ? apo['メモ'] : '';\n" +
"    fillSelect('fTemp', options.temperatures, apo ? apo['温度感'] : '中');\n" +
"    fillSelect('fFormat', options.formats, apo ? apo['形式'] : '訪問');\n" +
"    fillSelect('fStatus', options.statuses, apo ? apo['ステータス'] : '予定');\n" +
"    fillSelect('fSales', options.salesStaff, apo ? apo['担当営業'] : (state.meName || ''));\n" +
"    fillSelect('fSetter', options.setterStaff, apo ? apo['アポ入れ担当'] : (state.meName || ''));\n" +
"    $('modal').classList.add('open');\n" +
"  });\n" +
"}\n" +
"function closeModal() { $('modal').classList.remove('open'); }\n" +
"function save() {\n" +
"  if (!$('fCustomer').value.trim()) { toast('顧客名を入力してください'); return; }\n" +
"  var payload = {\n" +
"    'アポID': state.editingId, '日付': $('fDate').value, '開始時刻': $('fTime').value,\n" +
"    '所要分': Number($('fDuration').value), '顧客名': $('fCustomer').value.trim(),\n" +
"    '形式': $('fFormat').value, '場所またはURL': $('fPlace').value.trim(),\n" +
"    '担当営業': $('fSales').value, 'アポ入れ担当': $('fSetter').value,\n" +
"    '温度感': $('fTemp').value, 'ステータス': $('fStatus').value, 'メモ': $('fMemo').value,\n" +
"    confirmedOverlap: state.confirmedOverlap\n" +
"  };\n" +
"  $('modalSave').disabled = true;\n" +
"  google.script.run.withSuccessHandler(function (result) {\n" +
"    $('modalSave').disabled = false;\n" +
"    if (result && result.overlapWarning && result.overlapWarning.length && !result.ok) {\n" +
"      state.confirmedOverlap = true;\n" +
"      var lines = result.overlapWarning.map(function (a) {\n" +
"        return a['開始時刻'] + ' ' + a['顧客名'] + '様';\n" +
"      }).join(' / ');\n" +
"      var warn = $('overlapWarn');\n" +
"      warn.textContent = '⚠️ ' + payload['担当営業'] + 'さんの既存アポと時間帯が重なっています: ' + lines + ' — このまま登録する場合はもう一度「保存して通知」を押してください。';\n" +
"      warn.classList.add('show');\n" +
"      return;\n" +
"    }\n" +
"    closeModal(); closeSheet(); toast('保存しました。Slackに通知済みです'); load();\n" +
"  }).withFailureHandler(function (error) { $('modalSave').disabled = false; fail(error); })\n" +
"    .saveAppointment(payload);\n" +
"}\n" +
"function quickStatus(status) {\n" +
"  if (!state.selected) return;\n" +
"  closeSheet();\n" +
"  google.script.run.withSuccessHandler(function () { toast('「' + status + '」に更新し、Slackへ通知しました'); load(); })\n" +
"    .withFailureHandler(fail).updateStatus(state.selected['アポID'], status);\n" +
"}\n" +
"function reportDelayMinutes(minutes) {\n" +
"  closeSheet();\n" +
"  google.script.run.withSuccessHandler(function (result) {\n" +
"    toast('遅れ連絡を送信しました(影響しうる後続アポ ' + result.targetCount + '件)');\n" +
"  }).withFailureHandler(fail).reportDelay(minutes);\n" +
"}\n" +
"function setView(view, buttonId) {\n" +
"  state.view = view;\n" +
"  ['segDay', 'segWeek', 'segStats'].forEach(function (id) { $(id).classList.remove('on'); });\n" +
"  $(buttonId).classList.add('on');\n" +
"  load();\n" +
"}\n" +
"$('segDay').addEventListener('click', function () { setView('day', 'segDay'); });\n" +
"$('segWeek').addEventListener('click', function () { setView('week', 'segWeek'); });\n" +
"$('segStats').addEventListener('click', function () { setView('stats', 'segStats'); });\n" +
"$('fabNew').addEventListener('click', function () { openModal(null); });\n" +
"$('sheetBack').addEventListener('click', closeSheet);\n" +
"$('sheetClose').addEventListener('click', closeSheet);\n" +
"$('sheetEdit').addEventListener('click', function () { closeSheet(); openModal(state.selected); });\n" +
"$('modalClose').addEventListener('click', closeModal);\n" +
"$('modalSave').addEventListener('click', save);\n" +
"Array.prototype.forEach.call(document.querySelectorAll('[data-st]'), function (el) {\n" +
"  el.addEventListener('click', function () { quickStatus(el.getAttribute('data-st')); });\n" +
"});\n" +
"Array.prototype.forEach.call(document.querySelectorAll('[data-delay]'), function (el) {\n" +
"  el.addEventListener('click', function () { reportDelayMinutes(Number(el.getAttribute('data-delay'))); });\n" +
"});\n" +
"load();\n" +
"</script></body></html>";
  }

  var api = { buildApoAppHtml: buildApoAppHtml };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.ApoPage = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
