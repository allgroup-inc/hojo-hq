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

  // 家計の見直しやさんロゴ(2026-08-14 小柳さん提供画像を元にSVGで描き起こした再現版)。
  // 公式のロゴデータ(高解像度PNG/SVG)を入手したら、このbase64データURIを差し替えるだけでよい。
  var KAKEIPO_LOGO_DATA_URI = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj4KICA8ZGVmcz4KICAgIDxjbGlwUGF0aCBpZD0iYyI+PGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgcj0iNDMiLz48L2NsaXBQYXRoPgogIDwvZGVmcz4KICA8IS0tIOS6jOmHjeODquODs+OCsDog6buE44Oq44Oz44KwK+eZveOBrumamemWkyvpu4Tjg4fjgqPjgrnjgq8gLS0+CiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgcj0iNTAiIGZpbGw9IiNGNkM4M0UiLz4KICA8Y2lyY2xlIGN4PSI1MCIgY3k9IjUwIiByPSI0NS41IiBmaWxsPSIjZmZmZmZmIi8+CiAgPGNpcmNsZSBjeD0iNTAiIGN5PSI1MCIgcj0iNDMiIGZpbGw9IiNGNkM4M0UiLz4KICA8ZyBjbGlwLXBhdGg9InVybCgjYykiPgogICAgPHBhdGggZD0iTS01IDg4IFE1MCA2MiAxMDUgODggTDEwNSAxMDUgTC01IDEwNSBaIiBmaWxsPSIjZmZmZmZmIi8+CiAgICA8cGF0aCBkPSJNMjQgOTAuNSBRNTAgOTUuNSA3NiA4OC41IiBmaWxsPSJub25lIiBzdHJva2U9IiNGNkM4M0UiIHN0cm9rZS13aWR0aD0iMi40IiBzdHJva2UtbGluZWNhcD0icm91bmQiLz4KICA8L2c+CiAgPCEtLSDlpKrpmb0o44GK44GG44Gh44Gu5b6M44KN44Gr5o+P44GPPeWxi+agueOBp+S4gOmDqOmaoOOCjOOCiykgLS0+CiAgPGcgc3Ryb2tlPSIjMjIxRDExIiBmaWxsPSJub25lIj4KICAgIDxjaXJjbGUgY3g9IjY4IiBjeT0iMTgiIHI9IjUiIHN0cm9rZS13aWR0aD0iMiIvPgogICAgPGcgc3Ryb2tlLXdpZHRoPSIxLjciIHN0cm9rZS1saW5lY2FwPSJyb3VuZCI+CiAgICAgIDxsaW5lIHgxPSI2OCIgeTE9IjciICB4Mj0iNjgiIHkyPSIxMC42Ii8+CiAgICAgIDxsaW5lIHgxPSI2OCIgeTE9IjI1LjQiIHgyPSI2OCIgeTI9IjI5Ii8+CiAgICAgIDxsaW5lIHgxPSI1NyIgeTE9IjE4IiB4Mj0iNjAuNiIgeTI9IjE4Ii8+CiAgICAgIDxsaW5lIHgxPSI3NS40IiB5MT0iMTgiIHgyPSI3OSIgeTI9IjE4Ii8+CiAgICAgIDxsaW5lIHgxPSI2MC4yIiB5MT0iMTAuMiIgeDI9IjYyLjgiIHkyPSIxMi44Ii8+CiAgICAgIDxsaW5lIHgxPSI3My4yIiB5MT0iMjMuMiIgeDI9Ijc1LjgiIHkyPSIyNS44Ii8+CiAgICAgIDxsaW5lIHgxPSI2MC4yIiB5MT0iMjUuOCIgeDI9IjYyLjgiIHkyPSIyMy4yIi8+CiAgICAgIDxsaW5lIHgxPSI3My4yIiB5MT0iMTIuOCIgeDI9Ijc1LjgiIHkyPSIxMC4yIi8+CiAgICA8L2c+CiAgPC9nPgogIDwhLS0g44GK44GG44GhKOeZveWhl+OCiuOBruS6lOinkuW9oivou5Ljga7lh7rjgZ/lsYvmoLnnt5opIC0tPgogIDxwYXRoIGQ9Ik01MCAxMiBMNzggMzcuNSBMNzggNzMgTDIyIDczIEwyMiAzNy41IFoiIGZpbGw9IiNmZmZmZmYiLz4KICA8ZyBzdHJva2U9IiMyMjFEMTEiIHN0cm9rZS13aWR0aD0iMi44IiBzdHJva2UtbGluZWpvaW49InJvdW5kIiBzdHJva2UtbGluZWNhcD0icm91bmQiIGZpbGw9Im5vbmUiPgogICAgPHBhdGggZD0iTTIyIDM3LjUgTDIyIDczIEw3OCA3MyBMNzggMzcuNSIvPgogICAgPHBhdGggZD0iTTE0IDQ0IEw1MCAxMiBMODYgNDQiLz4KICA8L2c+CiAgPCEtLSDjgYvjgYogLS0+CiAgPGcgc3Ryb2tlPSIjMjIxRDExIiBzdHJva2Utd2lkdGg9IjIuOCIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBmaWxsPSJub25lIj4KICAgIDxsaW5lIHgxPSIzNCIgeTE9IjM4LjUiIHgyPSI2NiIgeTI9IjM4LjUiLz4KICAgIDxsaW5lIHgxPSI0NC41IiB5MT0iNDYiIHgyPSI0NC41IiB5Mj0iNTEiLz4KICAgIDxsaW5lIHgxPSI1NS41IiB5MT0iNDYiIHgyPSI1NS41IiB5Mj0iNTEiLz4KICAgIDxwYXRoIGQ9Ik0zOSA1NS41IFE1MCA2NyA2MSA1NS41Ii8+CiAgPC9nPgogIDx0ZXh0IHg9IjUwIiB5PSI4MiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZm9udC1mYW1pbHk9IidIaXJhZ2lubyBTYW5zJywnTm90byBTYW5zIEpQJyxNZWlyeW8sc2Fucy1zZXJpZiIgZm9udC1zaXplPSI3LjYiIGZvbnQtd2VpZ2h0PSI4MDAiIGZpbGw9IiMyMjFEMTEiPuWutuioiOOBruimi+ebtOOBl+OChOOBleOCkzwvdGV4dD4KPC9zdmc+Cg==";

  function buildLogoHtml_() {
    if (KAKEIPO_LOGO_DATA_URI) {
      return "<img class=\"logoimg\" src=\"" + KAKEIPO_LOGO_DATA_URI + "\" alt=\"家計の見直しやさん\">";
    }
    return "<span class=\"logomark\">🏠</span>";
  }

  function buildApoAppHtml() {
    return "<!doctype html>\n" +
"<html lang=\"ja\"><head><meta charset=\"utf-8\">\n" +
"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n" +
"<title>家計のポっ</title>\n" +
"<style>\n" +
"/* v2.0 設計方針(2026-08-14 小柳さん): 白基調・余白8/16/32/64・ブランド色#F6C83Eは\n" +
"   送信ボタン/フォーカス枠/現在地メニューの3箇所のみ・グラデーション禁止 */\n" +
":root{--brand:#F6C83E;--ink:#1A1A1A;--sub:#6B6B6B;--line:#E8E8E8;--bad:#D64533}\n" +
"*{box-sizing:border-box;margin:0;padding:0}\n" +
"html{background:#FFFFFF}\n" +
"body{font-family:-apple-system,BlinkMacSystemFont,\"Hiragino Sans\",\"Noto Sans JP\",Meiryo,sans-serif;background:#FFFFFF;color:var(--ink);font-size:14px;line-height:1.6}\n" +
".wrap{max-width:900px;margin:0 auto;padding:0 24px}\n" +
"header{border-bottom:1px solid var(--line);background:#FFFFFF;position:sticky;top:0;z-index:20}\n" +
".topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;padding-top:8px;padding-bottom:8px}\n" +
".brand{display:flex;align-items:center;gap:8px;min-width:0}\n" +
".logoimg{flex:none;width:32px;height:32px;border-radius:999px;object-fit:contain}\n" +
".logomark{flex:none;width:32px;height:32px;border-radius:8px;border:1px solid var(--line);display:flex;align-items:center;justify-content:center}\n" +
"header h1{font-size:15px;font-weight:700;line-height:1.2}\n" +
"header h1 span{font-weight:700}\n" +
".brandsub{font-size:10px;color:var(--sub);letter-spacing:.06em}\n" +
".seg{display:flex;gap:8px}\n" +
".seg button{border:0;background:none;color:var(--sub);padding:10px 8px 8px;font-size:14px;cursor:pointer;border-bottom:2px solid transparent;min-height:44px}\n" +
".seg button.on{color:var(--ink);font-weight:700;border-bottom-color:var(--brand)}\n" +
".toolbar{display:flex;align-items:center;gap:8px;margin-top:16px}\n" +
".chips{display:flex;gap:8px;overflow-x:auto;-webkit-overflow-scrolling:touch;flex:1}\n" +
".chip{flex:none;border:1px solid var(--line);background:#FFFFFF;color:var(--ink);border-radius:6px;padding:8px 12px;font-size:12px;cursor:pointer;min-height:36px}\n" +
".chip.on{background:var(--ink);border-color:var(--ink);color:#FFFFFF}\n" +
".btn-new{flex:none;margin-left:auto;border:1px solid var(--ink);background:#FFFFFF;color:var(--ink);border-radius:6px;padding:10px 16px;font-size:13px;font-weight:700;cursor:pointer;min-height:44px}\n" +
".summary{margin-top:16px;color:var(--sub);font-size:12px}\n" +
".summary b{color:var(--ink);font-size:14px}\n" +
".summary .unconf b{color:var(--bad)}\n" +
"main{margin-top:16px;padding-bottom:64px}\n" +
"main.dim{opacity:.45;pointer-events:none}\n" +
".daylabel{margin-top:32px;margin-bottom:8px;font-size:12px;color:var(--sub);font-weight:700}\n" +
".row{display:flex;align-items:center;gap:16px;padding:8px 0;border-bottom:1px solid var(--line);cursor:pointer}\n" +
".row:hover{background:#FAFAFA}\n" +
".row .time{flex:none;width:52px;font-weight:700;font-variant-numeric:tabular-nums}\n" +
".row .time small{display:block;font-weight:400;color:var(--sub);font-size:11px}\n" +
".row .main{flex:1;min-width:0}\n" +
".row .cust{font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n" +
".row .meta{color:var(--sub);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n" +
".row .owner{flex:none;width:72px;font-size:12px;color:var(--sub);text-align:left}\n" +
".row .temp{flex:none;width:44px;font-size:12px;color:var(--sub)}\n" +
".row .temp.hot{color:var(--ink);font-weight:700}\n" +
".row .st{flex:none;width:112px;font-size:12px;text-align:right;color:var(--sub)}\n" +
".row .st.signed{color:var(--ink);font-weight:700}\n" +
".row .st.cancel{color:var(--bad)}\n" +
".row.done{opacity:.55}\n" +
".empty{color:var(--sub);padding:32px 0;font-size:13px}\n" +
"@media (max-width:640px){.row .owner{display:none}.row .st{width:96px}}\n" +
"/* 分析 */\n" +
".panel{margin-top:64px}\n" +
".panel:first-child{margin-top:32px}\n" +
".panel h3{font-size:14px;font-weight:700;margin-bottom:16px}\n" +
".panel .note{color:var(--sub);font-size:11px;margin-top:16px;line-height:1.7}\n" +
".fillrow{margin-top:8px}\n" +
".fillrow .lbl{display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px}\n" +
".track{height:8px;border-radius:4px;background:#F0F0F0;overflow:hidden}\n" +
".bar{height:100%;border-radius:4px;background:#8F8F8F}\n" +
".fstep{display:flex;justify-content:space-between;align-items:baseline;padding:8px 0;border-bottom:1px solid var(--line);font-size:13px}\n" +
".fstep b{font-size:15px;font-variant-numeric:tabular-nums}\n" +
".fstep .rate{color:var(--ink);font-weight:700;margin-right:8px}\n" +
".temprow{display:flex;align-items:center;gap:16px;margin-top:8px}\n" +
".temprow .tlabel{flex:none;width:56px;font-size:12px;font-weight:700}\n" +
".temprow .track{flex:1}\n" +
".temprow .tval{flex:none;min-width:88px;text-align:right;font-size:12px;color:var(--sub)}\n" +
".temprow .tval b{color:var(--ink);font-size:13px}\n" +
"/* アクションシート */\n" +
".sheetback{position:fixed;inset:0;background:rgba(0,0,0,.35);z-index:30;display:none}\n" +
".sheetback.open{display:block}\n" +
".sheet{position:fixed;left:0;right:0;bottom:0;z-index:31;background:#FFFFFF;border-top:1px solid var(--line);padding:16px 24px 32px;transform:translateY(105%);transition:transform .2s ease}\n" +
"@media (prefers-reduced-motion: reduce){.sheet{transition:none}}\n" +
".sheet.open{transform:translateY(0)}\n" +
".sheet .inner{max-width:640px;margin:0 auto}\n" +
".sheet h2{font-size:14px;font-weight:700;margin-bottom:16px}\n" +
".sheet .grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}\n" +
".sheet button{border:1px solid var(--line);background:#FFFFFF;color:var(--ink);border-radius:6px;padding:0 8px;min-height:44px;font-size:13px;cursor:pointer}\n" +
".sheet button.strong{font-weight:700;border-color:var(--ink)}\n" +
".sheet .dangerzone{margin-top:32px;display:grid;grid-template-columns:1fr 1fr;gap:8px}\n" +
".sheet .dangerzone button{color:var(--bad);border-color:#F3CFC9}\n" +
".sheet .delayrow{margin-top:32px;display:flex;align-items:center;gap:8px}\n" +
".sheet .delayrow .dlabel{font-size:12px;color:var(--sub);flex:none}\n" +
".sheet .delayrow button{flex:1}\n" +
".sheet .footrow{margin-top:32px;display:flex;gap:16px}\n" +
"/* フォーム(Stripe式) */\n" +
".modal{position:fixed;inset:0;z-index:40;background:#FFFFFF;display:none;overflow-y:auto}\n" +
".modal.open{display:block}\n" +
".modal .inner{max-width:640px;margin:0 auto;padding:32px 24px 64px}\n" +
".modal h2{font-size:16px;font-weight:700;margin-bottom:32px}\n" +
".group{margin-top:32px}\n" +
".group:first-of-type{margin-top:0}\n" +
".glabel{font-size:12px;color:var(--sub);font-weight:700;margin-bottom:16px}\n" +
".field{margin-top:16px}\n" +
".field:first-child{margin-top:0}\n" +
".field label{display:block;font-size:12px;color:var(--ink);font-weight:600;margin-bottom:8px}\n" +
".req{display:inline-block;margin-left:8px;font-size:10px;color:var(--bad);border:1px solid var(--bad);border-radius:3px;padding:0 4px;vertical-align:1px}\n" +
".field input,.field select,.field textarea{width:100%;min-height:44px;border:1px solid #D9D9D9;border-radius:6px;padding:10px 12px;font-size:16px;background:#FFFFFF;color:var(--ink)}\n" +
".field textarea{min-height:64px}\n" +
".field input:focus,.field select:focus,.field textarea:focus{outline:none;border-color:var(--brand);box-shadow:0 0 0 3px rgba(246,200,62,.28)}\n" +
".row2{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:end;margin-top:16px}\n" +
".row2:first-child{margin-top:0}\n" +
".row2 .field{margin-top:0}\n" +
".field label{min-height:20px}\n" +
".err{display:none;color:var(--bad);font-size:12px;margin-top:8px}\n" +
".err.show{display:block}\n" +
".formfoot{margin-top:32px;display:flex;gap:16px;align-items:center}\n" +
".btn-primary{border:0;border-radius:6px;background:var(--brand);color:var(--ink);font-size:14px;font-weight:700;padding:0 24px;min-height:44px;cursor:pointer}\n" +
".btn-ghost{border:1px solid var(--line);border-radius:6px;background:#FFFFFF;color:var(--ink);font-size:14px;padding:0 16px;min-height:44px;cursor:pointer}\n" +
".toast{position:fixed;left:50%;bottom:32px;transform:translateX(-50%);z-index:50;background:var(--ink);color:#FFFFFF;border-radius:6px;padding:10px 16px;font-size:13px;opacity:0;pointer-events:none;transition:opacity .2s}\n" +
".toast.show{opacity:1}\n" +
"</style></head><body>\n" +
"<header><div class=\"wrap topbar\"><div class=\"brand\">" + buildLogoHtml_() + "<div>" +
"<h1>家計の<span>ポっ</span></h1><div class=\"brandsub\">家計の見直しやさん アポ管理</div></div></div>\n" +
"<nav class=\"seg\"><button id=\"segDay\" class=\"on\">本日</button><button id=\"segWeek\">週</button><button id=\"segStats\">分析</button></nav></div></header>\n" +
"<div class=\"wrap\">\n" +
"<div class=\"toolbar\"><div class=\"chips\" id=\"chips\"><button class=\"chip\" id=\"chipMine\">自分のアポ</button></div>" +
"<button class=\"btn-new\" id=\"fabNew\">＋ 新規アポ</button></div>\n" +
"<div class=\"summary\" id=\"summary\"></div>\n" +
"<main id=\"board\"><div class=\"empty\">読み込み中…</div></main>\n" +
"</div>\n" +
"<div class=\"sheetback\" id=\"sheetBack\"></div>\n" +
"<div class=\"sheet\" id=\"sheet\"><div class=\"inner\">\n" +
"  <h2 id=\"sheetTitle\"></h2>\n" +
"  <div class=\"grid\">\n" +
"    <button data-st=\"確定\">確定</button>\n" +
"    <button data-st=\"実施済\">実施済</button>\n" +
"    <button data-st=\"申込み\" class=\"strong\">申込み</button>\n" +
"    <button data-st=\"再調整中\">再調整中</button>\n" +
"  </div>\n" +
"  <div class=\"delayrow\"><span class=\"dlabel\">遅れそう:</span>\n" +
"    <button data-delay=\"15\">+15分</button><button data-delay=\"30\">+30分</button><button data-delay=\"60\">+60分</button></div>\n" +
"  <div class=\"dangerzone\">\n" +
"    <button data-st=\"キャンセル(顧客都合)\">キャンセル(顧客都合)</button>\n" +
"    <button data-st=\"キャンセル(自社都合)\">キャンセル(自社都合)</button>\n" +
"  </div>\n" +
"  <div class=\"footrow\"><button class=\"btn-ghost\" id=\"sheetEdit\">編集</button><button class=\"btn-ghost\" id=\"sheetClose\">閉じる</button></div>\n" +
"</div></div>\n" +
"<div class=\"modal\" id=\"modal\"><div class=\"inner\">\n" +
"  <h2 id=\"modalTitle\">新規アポ</h2>\n" +
"  <div class=\"group\"><div class=\"glabel\">日時</div>\n" +
"    <div class=\"row2\">\n" +
"      <div class=\"field\"><label>日付<span class=\"req\">必須</span></label><input type=\"date\" id=\"fDate\"></div>\n" +
"      <div class=\"field\"><label>開始時刻<span class=\"req\">必須</span></label><input type=\"time\" id=\"fTime\"></div>\n" +
"    </div>\n" +
"    <div class=\"row2\"><div class=\"field\"><label>所要分</label><select id=\"fDuration\"><option>30</option><option selected>60</option><option>90</option><option>120</option></select></div><div></div></div>\n" +
"    <div class=\"err\" id=\"overlapWarn\"></div>\n" +
"  </div>\n" +
"  <div class=\"group\"><div class=\"glabel\">お客様</div>\n" +
"    <div class=\"field\"><label>顧客名<span class=\"req\">必須</span></label><input type=\"text\" id=\"fCustomer\" placeholder=\"例: ◯◯株式会社 △△様\">\n" +
"      <div class=\"err\" id=\"custErr\">顧客名を入力してください。</div></div>\n" +
"    <div class=\"row2\">\n" +
"      <div class=\"field\"><label>形式</label><select id=\"fFormat\"></select></div>\n" +
"      <div class=\"field\"><label>温度感</label><select id=\"fTemp\"></select></div>\n" +
"    </div>\n" +
"    <div class=\"field\"><label>場所またはURL</label><input type=\"text\" id=\"fPlace\" placeholder=\"住所・店舗名・会議URL\"></div>\n" +
"  </div>\n" +
"  <div class=\"group\"><div class=\"glabel\">担当</div>\n" +
"    <div class=\"row2\">\n" +
"      <div class=\"field\"><label>担当営業<span class=\"req\">必須</span></label><select id=\"fSales\"></select></div>\n" +
"      <div class=\"field\"><label>アポ入れ担当</label><select id=\"fSetter\"></select></div>\n" +
"    </div>\n" +
"  </div>\n" +
"  <div class=\"group\"><div class=\"glabel\">その他</div>\n" +
"    <div class=\"field\"><label>ステータス</label><select id=\"fStatus\"></select></div>\n" +
"    <div class=\"field\"><label>メモ</label><textarea id=\"fMemo\" rows=\"2\" placeholder=\"引き継ぎ事項・注意点\"></textarea></div>\n" +
"  </div>\n" +
"  <div class=\"formfoot\"><button class=\"btn-primary\" id=\"modalSave\">保存して通知</button><button class=\"btn-ghost\" id=\"modalClose\">戻る</button></div>\n" +
"</div></div>\n" +
"<div class=\"toast\" id=\"toast\"></div>\n" +
"<script>\n" +
"var state = { view: 'day', owner: '', mine: false, meName: '', board: null, options: null, editingId: null, selected: null, confirmedOverlap: false, loaded: false };\n" +
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
"  // 読み込み中は全体を隠さず、一覧部分だけ薄くする(初回のみ文言表示)\n" +
"  if (state.loaded) { $('board').classList.add('dim'); }\n" +
"  else { $('board').innerHTML = '<div class=\"empty\">読み込み中…</div>'; }\n" +
"  if (state.view === 'stats') {\n" +
"    google.script.run.withSuccessHandler(renderStats).withFailureHandler(fail).getStats();\n" +
"    return;\n" +
"  }\n" +
"  google.script.run.withSuccessHandler(renderBoard).withFailureHandler(fail)\n" +
"    .getBoard({ view: state.view, date: todayString(), owner: effectiveOwner() });\n" +
"}\n" +
"function doneLoading() { state.loaded = true; $('board').classList.remove('dim'); }\n" +
"function effectiveOwner() { return state.mine ? state.meName : state.owner; }\n" +
"function fail(error) { doneLoading(); toast('エラー: ' + (error && error.message ? error.message : error)); }\n" +
"function statusClass(status) {\n" +
"  if (status.indexOf('キャンセル') === 0) return 'st cancel';\n" +
"  if (status === '申込み') return 'st signed';\n" +
"  return 'st';\n" +
"}\n" +
"function rowHtml(apo) {\n" +
"  var doneClass = (apo['ステータス'] === '実施済' || apo['ステータス'].indexOf('キャンセル') === 0) ? ' done' : '';\n" +
"  var hotClass = apo['温度感'] === '高' ? ' hot' : '';\n" +
"  return '<div class=\"row' + doneClass + '\" data-id=\"' + esc(apo['アポID']) + '\" tabindex=\"0\">' +\n" +
"    '<div class=\"time\">' + esc(apo['開始時刻']) + '<small>' + esc(apo['所要分']) + '分</small></div>' +\n" +
"    '<div class=\"main\"><div class=\"cust\">' + esc(apo['顧客名']) + '</div>' +\n" +
"    '<div class=\"meta\">' + esc(apo['形式']) + ' ' + esc(apo['場所またはURL']) + '</div></div>' +\n" +
"    '<div class=\"owner\">' + esc(apo['担当営業']) + '</div>' +\n" +
"    '<div class=\"temp' + hotClass + '\">' + esc(apo['温度感']) + '</div>' +\n" +
"    '<div class=\"' + statusClass(apo['ステータス']) + '\">' + esc(apo['ステータス']) + '</div></div>';\n" +
"}\n" +
"function renderBoard(board) {\n" +
"  state.board = board; state.meName = board.meName || '';\n" +
"  renderChips(board.salesStaff || []);\n" +
"  var html = '';\n" +
"  if (state.view === 'day') {\n" +
"    var view = board.dayView || { items: [], summary: { total: 0, unconfirmed: 0 } };\n" +
"    $('summary').innerHTML = '<span>本日 <b>' + view.summary.total + '</b>件</span> ' +\n" +
"      '<span class=\"unconf\">未確定 <b>' + view.summary.unconfirmed + '</b>件</span>';\n" +
"    html = view.items.length ? view.items.map(rowHtml).join('') :\n" +
"      '<div class=\"empty\">本日のアポはありません。「＋ 新規アポ」から登録できます。</div>';\n" +
"  } else {\n" +
"    $('summary').innerHTML = '<span>今日から7日間</span>';\n" +
"    (board.week || []).forEach(function (day) {\n" +
"      html += '<div class=\"daylabel\">' + esc(day.date) + '(' + day.items.length + '件)</div>';\n" +
"      html += day.items.length ? day.items.map(rowHtml).join('') : '';\n" +
"    });\n" +
"  }\n" +
"  $('board').innerHTML = html;\n" +
"  doneLoading();\n" +
"  Array.prototype.forEach.call(document.querySelectorAll('.row'), function (el) {\n" +
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
"function formatHours(minutes) { return (Math.round(minutes / 6) / 10) + 'h'; }\n" +
"function formatRate(rate) { return rate === null || rate === undefined ? '—' : Math.round(rate * 100) + '%'; }\n" +
"function renderStats(stats) {\n" +
"  $('summary').innerHTML = '<span>本日の埋まり状況+過去30日の転換</span>';\n" +
"  var fill = stats.fill || { owners: [], total: { bookedMinutes: 0, count: 0 } };\n" +
"  var funnel = stats.funnel || { concluded: 0, completed: 0, signups: 0, visitRate: null, signupRate: null };\n" +
"  var html = '<div class=\"panel\"><h3>本日の埋まり状況(営業時間 9:00〜18:00 換算)</h3>';\n" +
"  html += '<div class=\"fillrow\"><div class=\"lbl\"><span>全体</span><b>' + fill.total.count + '件・' + formatHours(fill.total.bookedMinutes) + '</b></div></div>';\n" +
"  fill.owners.forEach(function (entry) {\n" +
"    html += '<div class=\"fillrow\"><div class=\"lbl\"><span>' + esc(entry.owner) + '</span>' +\n" +
"      '<b>' + entry.count + '件・' + formatHours(entry.bookedMinutes) + '(' + Math.round(entry.ratio * 100) + '%)</b></div>' +\n" +
"      '<div class=\"track\"><div class=\"bar\" style=\"width:' + Math.round(entry.ratio * 100) + '%\"></div></div></div>';\n" +
"  });\n" +
"  html += '<div class=\"note\">空き=キャンセル・再調整中を除いた予約済み時間。評価目的では使いません</div></div>';\n" +
"  html += '<div class=\"panel\"><h3>転換ファネル(過去30日・' + esc(stats.sinceDate) + '以降・チーム全体)</h3>';\n" +
"  html += '<div class=\"fstep\"><span>結果が出たアポ</span><b>' + funnel.concluded + '件</b></div>';\n" +
"  html += '<div class=\"fstep\"><span>訪問実施(実施済+申込み)</span><span><span class=\"rate\">' + formatRate(funnel.visitRate) + '</span><b>' + funnel.completed + '件</b></span></div>';\n" +
"  html += '<div class=\"fstep\"><span>申込み</span><span><span class=\"rate\">' + formatRate(funnel.signupRate) + '</span><b>' + funnel.signups + '件</b></span></div>';\n" +
"  html += '<div class=\"note\">率の母数: 訪問実施率=結果が出たアポ、申込み率=訪問実施。' +\n" +
"    (funnel.concluded < 10 ? '<br>件数が少ないため参考値です(母数10件未満)。' : '') +\n" +
"    '<br>予定・確定・再調整中のアポは結果待ちのため含みません。評価目的では使いません</div></div>';\n" +
"  var lowTempSample = false;\n" +
"  html += '<div class=\"panel\"><h3>温度感別の申込み率(過去30日・チーム全体)</h3>';\n" +
"  (stats.byTemperature || []).forEach(function (row) {\n" +
"    if (row.completed > 0 && row.completed < 10) lowTempSample = true;\n" +
"    var percent = row.rate === null ? 0 : Math.round(row.rate * 100);\n" +
"    html += '<div class=\"temprow\"><span class=\"tlabel\">温度 ' + esc(row.temperature) + '</span>' +\n" +
"      '<div class=\"track\"><div class=\"bar\" style=\"width:' + percent + '%\"></div></div>' +\n" +
"      '<span class=\"tval\"><b>' + formatRate(row.rate) + '</b> ' + row.signups + '/' + row.completed + '件</span></div>';\n" +
"  });\n" +
"  html += '<div class=\"note\">母数=その温度感の訪問実施(実施済+申込み)。' +\n" +
"    (lowTempSample ? '<br>母数10件未満の行は参考値です。' : '') +\n" +
"    '<br>どんなアポを取れば決まりやすいかの改善用。評価目的では使いません</div></div>';\n" +
"  $('board').innerHTML = html;\n" +
"  doneLoading();\n" +
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
"    $('custErr').classList.remove('show');\n" +
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
"    $('fDate').focus();\n" +
"  });\n" +
"}\n" +
"function closeModal() { $('modal').classList.remove('open'); }\n" +
"function save() {\n" +
"  if (!$('fCustomer').value.trim()) {\n" +
"    $('custErr').classList.add('show'); $('fCustomer').focus(); return;\n" +
"  }\n" +
"  $('custErr').classList.remove('show');\n" +
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
"      warn.textContent = payload['担当営業'] + 'さんの既存アポと時間帯が重なっています(' + lines + ')。このまま保存するにはもう一度「保存して通知」を押してください。';\n" +
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
"  $('fabNew').style.display = (view === 'stats') ? 'none' : '';\n" +
"  state.loaded = false;\n" +
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
