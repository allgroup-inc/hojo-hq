/* GLOW企業リレーション台帳 管理画面Web AppのHTML/JS組み立て(Phase 18a: 企業一覧・詳細の閲覧)
 * ブラウザ相当のGAS(global.GlowAdminApp)とNode(module.exports)の両方で動くUMD形式。
 * Node側は tests/glow_ma_adminApp.test.mjs で構造面のみ検証される
 * (google.script.run の実際の往復はGAS実行環境が必要なためNodeでは検証できない)。
 *
 * AdminRunner.gs の renderAdminPage_ がこの関数の戻り値を HtmlService.createHtmlOutput
 * に渡してWeb Appのページとして表示する。読み取り専用(Phase 18a)のため、
 * データを変更する google.script.run 呼び出しは一切含まない。
 */
(function (global) {
  "use strict";

  var STYLE = [
    "*{box-sizing:border-box}",
    "body{margin:0;font-family:-apple-system,BlinkMacSystemFont,\"Hiragino Sans\",",
    "\"Noto Sans JP\",Meiryo,sans-serif;color:#11202c;background:#f3f4f0}",
    "header{background:#00335c;color:#fff;padding:0.9rem 1.25rem}",
    "header h1{margin:0;font-size:1.05rem;font-weight:600}",
    ".filters{display:flex;gap:0.6rem;flex-wrap:wrap;padding:0.9rem 1.25rem;background:#fff;",
    "border-bottom:1px solid #d8dee1}",
    ".filters input,.filters select{padding:0.4rem 0.6rem;border:1px solid #d8dee1;",
    "border-radius:0.35rem;font:inherit}",
    "table{width:100%;border-collapse:collapse;background:#fff}",
    "th,td{text-align:left;padding:0.55rem 1rem;border-bottom:1px solid #e5e9eb;font-size:0.88rem}",
    "th{color:#4a5a66;font-weight:600;background:#f7f8f6}",
    "tbody tr{cursor:pointer}",
    "tbody tr:hover{background:#fdf2e2}",
    ".rank{display:inline-block;min-width:1.4rem;text-align:center;border-radius:0.3rem;",
    "padding:0.05rem 0.4rem;font-weight:700;color:#fff;background:#f88800}",
    "#drawer{position:fixed;top:0;right:0;bottom:0;width:min(420px,100%);background:#fff;",
    "box-shadow:-4px 0 16px rgba(17,32,44,0.18);transform:translateX(100%);",
    "transition:transform 0.2s ease;display:flex;flex-direction:column}",
    "#drawer.open{transform:translateX(0)}",
    "#drawerHeader{padding:1rem 1.25rem;border-bottom:1px solid #e5e9eb;display:flex;",
    "justify-content:space-between;align-items:flex-start}",
    "#drawerClose{border:0;background:none;font-size:1.1rem;cursor:pointer;color:#4a5a66}",
    ".tabs{display:flex;border-bottom:1px solid #e5e9eb}",
    ".tabs button{flex:1;padding:0.6rem;border:0;background:none;cursor:pointer;font:inherit;",
    "color:#4a5a66;border-bottom:2px solid transparent}",
    ".tabs button.active{color:#00335c;border-bottom-color:#f88800;font-weight:600}",
    "#drawerBody{overflow-y:auto;padding:1rem 1.25rem;flex:1}",
    ".field{margin-bottom:0.7rem}",
    ".field .label{font-size:0.76rem;color:#7a828a;text-transform:uppercase;letter-spacing:0.03em}",
    ".field .value{font-size:0.92rem;white-space:pre-wrap}",
    ".empty{color:#7a828a;padding:1.5rem;text-align:center}",
    "#overlay{position:fixed;inset:0;background:rgba(17,32,44,0.25);display:none}",
    "#overlay.open{display:block}"
  ].join("");

  var HEADER_AND_FILTERS = [
    "<header><h1>GLOW企業リレーション台帳</h1></header>",
    "<div class=\"filters\">",
    "<input type=\"text\" id=\"searchInput\" placeholder=\"会社名・代表者名で検索\">",
    "<select id=\"filterRank\"><option value=\"\">ランク(すべて)</option>",
    "<option value=\"A\">A</option><option value=\"B\">B</option>",
    "<option value=\"C\">C</option><option value=\"D\">D</option></select>",
    "<select id=\"filterStage\"><option value=\"\">現在ステージ(すべて)</option></select>",
    "<select id=\"filterOwner\"><option value=\"\">担当者(すべて)</option></select>",
    "</div>"
  ].join("");

  var TABLE = [
    "<table><thead><tr><th>会社名</th><th>ランク</th><th>現在ステージ</th>",
    "<th>次回アクション予定日</th><th>担当者</th></tr></thead>",
    "<tbody id=\"companyTableBody\"></tbody></table>",
    "<div class=\"empty\" id=\"emptyState\" style=\"display:none\">該当する企業が見つかりません</div>"
  ].join("");

  var DRAWER = [
    "<div id=\"overlay\"></div>",
    "<div id=\"drawer\">",
    "<div id=\"drawerHeader\"><div><div id=\"drawerCompanyName\" style=\"font-weight:700\"></div>",
    "<div id=\"drawerCompanyId\" style=\"font-size:0.8rem;color:#7a828a\"></div></div>",
    "<button id=\"drawerClose\">&times;</button></div>",
    "<div class=\"tabs\"><button id=\"tabOverviewBtn\" class=\"active\">概要</button>",
    "<button id=\"tabHistoryBtn\">対応履歴</button></div>",
    "<div id=\"drawerBody\">",
    "<div id=\"paneOverview\"></div>",
    "<div id=\"paneHistory\" style=\"display:none\"></div>",
    "</div></div>"
  ].join("");

  var SCRIPT = [
    "var currentFilters = { search: '', rank: '', stage: '', owner: '' };",
    "function escapeHtml(value){return String(value===undefined||value===null?'':value)",
    ".replace(/&/g,'&amp;').replace(/\"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}",

    "function loadFilterOptions(){",
    "google.script.run.withSuccessHandler(function(options){",
    "var stageSelect = document.getElementById('filterStage');",
    "(options.stages||[]).forEach(function(stage){",
    "var opt = document.createElement('option'); opt.value = stage; opt.textContent = stage;",
    "stageSelect.appendChild(opt);});",
    "var ownerSelect = document.getElementById('filterOwner');",
    "(options.owners||[]).forEach(function(owner){",
    "var opt = document.createElement('option'); opt.value = owner; opt.textContent = owner;",
    "ownerSelect.appendChild(opt);});",
    "}).withFailureHandler(function(){}).getFilterOptions();",
    "}",

    "function loadList(){",
    "google.script.run.withSuccessHandler(renderTable).withFailureHandler(function(error){",
    "document.getElementById('companyTableBody').innerHTML = '';",
    "var empty = document.getElementById('emptyState');",
    "empty.style.display = 'block'; empty.textContent = '読み込みに失敗しました。再読み込みしてください。';",
    "}).getCompanyList(currentFilters);",
    "}",

    "function renderTable(rows){",
    "var tbody = document.getElementById('companyTableBody'); tbody.innerHTML = '';",
    "var empty = document.getElementById('emptyState');",
    "if (!rows || rows.length === 0){ empty.style.display = 'block';",
    "empty.textContent = '該当する企業が見つかりません'; return; }",
    "empty.style.display = 'none';",
    "rows.forEach(function(row){",
    "var tr = document.createElement('tr');",
    "tr.innerHTML = '<td>' + escapeHtml(row['会社名']) + '</td>' +",
    "'<td><span class=\"rank\">' + escapeHtml(row['ランク']) + '</span></td>' +",
    "'<td>' + escapeHtml(row['現在ステージ']) + '</td>' +",
    "'<td>' + escapeHtml(row['次回アクション予定日']) + '</td>' +",
    "'<td>' + escapeHtml(row['担当者']) + '</td>';",
    "tr.addEventListener('click', function(){ openDrawer(row['企業ID']); });",
    "tbody.appendChild(tr);});",
    "}",

    "function openDrawer(companyId){",
    "document.getElementById('drawer').classList.add('open');",
    "document.getElementById('overlay').classList.add('open');",
    "document.getElementById('drawerCompanyName').textContent = '読み込み中…';",
    "document.getElementById('drawerCompanyId').textContent = companyId;",
    "google.script.run.withSuccessHandler(renderDrawer).withFailureHandler(function(){",
    "document.getElementById('drawerCompanyName').textContent = '読み込みに失敗しました。再読み込みしてください。';",
    "}).getCompanyDetail(companyId);",
    "}",

    "function renderDrawer(detail){",
    "if (!detail){ document.getElementById('drawerCompanyName').textContent = '該当する企業が見つかりません';",
    "document.getElementById('paneOverview').innerHTML = ''; document.getElementById('paneHistory').innerHTML = ''; return; }",
    "var c = detail.company;",
    "document.getElementById('drawerCompanyName').textContent = c['会社名'] || '(社名未登録)';",
    "document.getElementById('drawerCompanyId').textContent = c['企業ID'];",
    "var fields = [",
    "['業種', c['業種']], ['代表者名', c['代表者名']], ['所在地', c['所在地']],",
    "['電話番号', c['電話番号']], ['窓口担当者名', c['窓口担当者名']], ['携帯番号', c['携帯番号']],",
    "['ランク', c['ランク']], ['初期スコア', c['初期スコア']], ['反応スコア', c['反応スコア']],",
    "['総合スコア', c['総合スコア']], ['現在ステージ', c['現在ステージ']],",
    "['後継者状況', c['後継者状況']], ['関係メモ', c['関係メモ']]",
    "];",
    "document.getElementById('paneOverview').innerHTML = fields.map(function(f){",
    "return '<div class=\"field\"><div class=\"label\">' + escapeHtml(f[0]) + '</div>' +",
    "'<div class=\"value\">' + (escapeHtml(f[1]) || '—') + '</div></div>';",
    "}).join('');",
    "var history = detail.history || [];",
    "document.getElementById('paneHistory').innerHTML = history.length === 0",
    "? '<div class=\"empty\">対応履歴がありません</div>'",
    ": history.map(function(h){",
    "return '<div class=\"field\"><div class=\"label\">' + escapeHtml(h['日付']) + '・' + escapeHtml(h['種別']) + '</div>' +",
    "'<div class=\"value\">' + escapeHtml(h['内容メモ']) + '</div></div>';",
    "}).join('');",
    "}",

    "function closeDrawer(){",
    "document.getElementById('drawer').classList.remove('open');",
    "document.getElementById('overlay').classList.remove('open');",
    "}",

    "function switchTab(target){",
    "var isOverview = target === 'overview';",
    "document.getElementById('tabOverviewBtn').classList.toggle('active', isOverview);",
    "document.getElementById('tabHistoryBtn').classList.toggle('active', !isOverview);",
    "document.getElementById('paneOverview').style.display = isOverview ? 'block' : 'none';",
    "document.getElementById('paneHistory').style.display = isOverview ? 'none' : 'block';",
    "}",

    "document.getElementById('searchInput').addEventListener('input', function(e){",
    "currentFilters.search = e.target.value; loadList(); });",
    "document.getElementById('filterRank').addEventListener('change', function(e){",
    "currentFilters.rank = e.target.value; loadList(); });",
    "document.getElementById('filterStage').addEventListener('change', function(e){",
    "currentFilters.stage = e.target.value; loadList(); });",
    "document.getElementById('filterOwner').addEventListener('change', function(e){",
    "currentFilters.owner = e.target.value; loadList(); });",
    "document.getElementById('drawerClose').addEventListener('click', closeDrawer);",
    "document.getElementById('overlay').addEventListener('click', closeDrawer);",
    "document.getElementById('tabOverviewBtn').addEventListener('click', function(){ switchTab('overview'); });",
    "document.getElementById('tabHistoryBtn').addEventListener('click', function(){ switchTab('history'); });",

    "loadFilterOptions();",
    "loadList();"
  ].join("");

  function buildAdminAppHtml() {
    return "<!doctype html><html lang=\"ja\"><head><meta charset=\"utf-8\">" +
      "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" +
      "<style>" + STYLE + "</style></head><body>" +
      HEADER_AND_FILTERS + TABLE + DRAWER +
      "<script>" + SCRIPT + "<\/script>" +
      "</body></html>";
  }

  var api = {
    buildAdminAppHtml: buildAdminAppHtml
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.GlowAdminApp = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
