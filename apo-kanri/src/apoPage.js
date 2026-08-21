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

  // ホーム画面アイコン(apple-touch-icon)用のPNG。iOSはSVGを受け付けないため、
  // 上のロゴSVGを180x180で書き出したPNGを別途持つ。
  var KAKEIPO_TOUCH_ICON_DATA_URI = "data:image/png;base64,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";

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
"<link rel=\"apple-touch-icon\" href=\"" + KAKEIPO_TOUCH_ICON_DATA_URI + "\">\n" +
"<link rel=\"icon\" href=\"" + KAKEIPO_TOUCH_ICON_DATA_URI + "\">\n" +
"<meta name=\"apple-mobile-web-app-title\" content=\"家計のポっ\">\n" +
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
"header h1{font-size:15px;font-weight:700;line-height:1.2;display:flex;align-items:center;gap:4px}\n" +
/* 「ポっ」は黄色の丸にオレンジ文字(ブランドの愛称マーク)。文字色は黄色地で読める濃さの
   オレンジを選ぶ(明るいオレンジだとコントラストが足りず読めなくなる) */
"header h1 span{display:inline-flex;align-items:center;justify-content:center;" +
"width:34px;height:34px;border-radius:50%;background:var(--brand);color:#B23C06;" +
"font-size:15px;font-weight:700;letter-spacing:-.06em}\n" +
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
/* 狭い画面では担当者チップが「新規アポ」ボタンに切られて読めなくなるため、
   ボタンを上段・チップを下段に折り返す */
"@media (max-width:640px){.row .owner{display:none}.row .st{width:96px}" +
".toolbar{flex-wrap:wrap}.btn-new{order:1}.chips{order:2;flex-basis:100%;padding-bottom:4px}}\n" +
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
".temprow .tlabel.wide{width:104px}\n" +
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
"    <button data-st=\"アポ確定\">アポ確定</button>\n" +
"    <button data-st=\"訪問済\">訪問済</button>\n" +
"    <button data-st=\"申込\" class=\"strong\">申込</button>\n" +
"    <button data-st=\"スケジュール調整中\">日程を組み直す</button>\n" +
"  </div>\n" +
"  <div class=\"delayrow\"><span class=\"dlabel\">遅れそう:</span>\n" +
"    <button data-delay=\"15\">+15分</button><button data-delay=\"30\">+30分</button><button data-delay=\"60\">+60分</button></div>\n" +
"  <div class=\"dangerzone\">\n" +
"    <button data-st=\"差し戻し\" data-reason=\"顧客都合\">差し戻し(顧客都合)</button>\n" +
"    <button data-st=\"差し戻し\" data-reason=\"自社都合\">差し戻し(自社都合)</button>\n" +
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
"      <div class=\"field\"><label>アポ種別</label><select id=\"fKind\"></select></div>\n" +
"      <div class=\"field\" id=\"referrerField\"><label>紹介元</label><input type=\"text\" id=\"fReferrer\" placeholder=\"例: ◯◯様のご紹介\"></div>\n" +
"    </div>\n" +
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
"  <div class=\"formfoot\"><button class=\"btn-primary\" id=\"modalSave\">保存して通知</button>" +
"<button class=\"btn-ghost\" id=\"modalSaveNext\">保存して続けて登録</button>" +
"<button class=\"btn-ghost\" id=\"modalClose\">戻る</button></div>\n" +
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
"  if (status === '申込') return 'st signed';\n" +
"  return 'st';\n" +
"}\n" +
"function rowHtml(apo) {\n" +
"  var doneClass = (apo['ステータス'] === '訪問済' || apo['ステータス'] === '差し戻し') ? ' done' : '';\n" +
"  var hotClass = apo['温度感'] === '高' ? ' hot' : '';\n" +
"  return '<div class=\"row' + doneClass + '\" data-id=\"' + esc(apo['アポID']) + '\" tabindex=\"0\">' +\n" +
"    '<div class=\"time\">' + esc(apo['開始時刻']) + '<small>' + esc(apo['所要分']) + '分</small></div>' +\n" +
"    '<div class=\"main\"><div class=\"cust\">' + esc(apo['顧客名']) + '</div>' +\n" +
"    '<div class=\"meta\">' + (apo['アポ種別'] ? esc(apo['アポ種別']) + ' / ' : '') +\n" +
"    esc(apo['形式']) + ' ' + esc(apo['場所またはURL']) + '</div></div>' +\n" +
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
"  html += '<div class=\"note\">空き=開始時刻が入っているアポの合計(差し戻しは除く)。評価目的では使いません</div></div>';\n" +
"  html += '<div class=\"panel\"><h3>転換ファネル(過去30日・' + esc(stats.sinceDate) + '以降・チーム全体)</h3>';\n" +
"  html += '<div class=\"fstep\"><span>結果が出たアポ</span><b>' + funnel.concluded + '件</b></div>';\n" +
"  html += '<div class=\"fstep\"><span>訪問実施(訪問済+申込)</span><span><span class=\"rate\">' + formatRate(funnel.visitRate) + '</span><b>' + funnel.completed + '件</b></span></div>';\n" +
"  html += '<div class=\"fstep\"><span>申込</span><span><span class=\"rate\">' + formatRate(funnel.signupRate) + '</span><b>' + funnel.signups + '件</b></span></div>';\n" +
"  html += '<div class=\"note\">率の母数: 訪問実施率=結果が出たアポ、申込率=訪問実施。' +\n" +
"    (funnel.concluded < 10 ? '<br>件数が少ないため参考値です(母数10件未満)。' : '') +\n" +
"    '<br>スケジュール調整中・アポ確定のアポは結果待ちのため含みません。評価目的では使いません</div></div>';\n" +
"  var lowKindSample = false;\n" +
"  html += '<div class=\"panel\"><h3>アポ種別別の申込率(過去30日・チーム全体)</h3>';\n" +
"  (stats.byKind || []).forEach(function (row) {\n" +
"    if (row.completed > 0 && row.completed < 10) lowKindSample = true;\n" +
"    var kindPercent = row.rate === null ? 0 : Math.round(row.rate * 100);\n" +
"    html += '<div class=\"temprow\"><span class=\"tlabel wide\">' + esc(row.kind) + '</span>' +\n" +
"      '<div class=\"track\"><div class=\"bar\" style=\"width:' + kindPercent + '%\"></div></div>' +\n" +
"      '<span class=\"tval\"><b>' + formatRate(row.rate) + '</b> ' + row.signups + '/' + row.completed + '件</span></div>';\n" +
"  });\n" +
"  html += '<div class=\"note\">母数=その種別の訪問実施(訪問済+申込)。' +\n" +
"    (lowKindSample ? '<br>母数10件未満の行は参考値です。' : '') +\n" +
"    '<br>再訪と新規は決まり方が違うため分けて見ます。どこに時間を寄せるかの判断用で、評価目的では使いません</div></div>';\n" +
"  var lowTempSample = false;\n" +
"  html += '<div class=\"panel\"><h3>温度感別の申込率(過去30日・チーム全体)</h3>';\n" +
"  (stats.byTemperature || []).forEach(function (row) {\n" +
"    if (row.completed > 0 && row.completed < 10) lowTempSample = true;\n" +
"    var percent = row.rate === null ? 0 : Math.round(row.rate * 100);\n" +
"    html += '<div class=\"temprow\"><span class=\"tlabel\">温度 ' + esc(row.temperature) + '</span>' +\n" +
"      '<div class=\"track\"><div class=\"bar\" style=\"width:' + percent + '%\"></div></div>' +\n" +
"      '<span class=\"tval\"><b>' + formatRate(row.rate) + '</b> ' + row.signups + '/' + row.completed + '件</span></div>';\n" +
"  });\n" +
"  html += '<div class=\"note\">母数=その温度感の訪問実施(訪問済+申込)。' +\n" +
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
"  // 編集対象の現担当が無効化済みでも選択肢に残す(勝手に別人へ付け替えない)\n" +
"  var list = values.slice();\n" +
"  if (current && list.indexOf(current) === -1) list.unshift(current);\n" +
"  $(id).innerHTML = list.map(function (value) {\n" +
"    return '<option' + (value === current ? ' selected' : '') + '>' + esc(value) + '</option>';\n" +
"  }).join('');\n" +
"}\n" +
"// 日時・担当営業を変えたら重複確認をやり直す(前回の「確認済み」を持ち越さない)\n" +
"['fDate', 'fTime', 'fDuration', 'fSales'].forEach(function (id) {\n" +
"  document.addEventListener('change', function (event) {\n" +
"    if (event.target && event.target.id === id) {\n" +
"      state.confirmedOverlap = false;\n" +
"      $('overlapWarn').classList.remove('show');\n" +
"    }\n" +
"  });\n" +
"});\n" +
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
"    $('fReferrer').value = apo ? (apo['紹介元'] || '') : '';\n" +
"    fillSelect('fKind', options.kinds, apo ? apo['アポ種別'] : options.kinds[0]);\n" +
"    syncReferrerField();\n" +
"    fillSelect('fTemp', options.temperatures, apo ? apo['温度感'] : '中');\n" +
"    fillSelect('fFormat', options.formats, apo ? apo['形式'] : '訪問');\n" +
"    fillSelect('fStatus', options.statuses, apo ? apo['ステータス'] : 'スケジュール調整中');\n" +
"    fillSelect('fSales', options.salesStaff, apo ? apo['担当営業'] : (state.meName || ''));\n" +
"    fillSelect('fSetter', options.setterStaff, apo ? apo['アポ入れ担当'] : (state.meName || ''));\n" +
"    $('modal').classList.add('open');\n" +
"    $('fDate').focus();\n" +
"  });\n" +
"}\n" +
"function closeModal() { $('modal').classList.remove('open'); }\n" +
"// 紹介元は新規のときだけ意味があるので、再訪では隠して入力欄を減らす\n" +
"function syncReferrerField() {\n" +
"  var isNew = $('fKind').value.indexOf('新規') === 0;\n" +
"  $('referrerField').style.visibility = isNew ? '' : 'hidden';\n" +
"  if (!isNew) $('fReferrer').value = '';\n" +
"}\n" +
"document.addEventListener('change', function (event) {\n" +
"  if (event.target && event.target.id === 'fKind') syncReferrerField();\n" +
"});\n" +
/* keepOpen=true で「保存して続けて登録」。日付・担当・形式は引き継ぎ、顧客名・場所・メモだけ
   空にしてフォームを開いたままにする(1日100件入力の連続登録でクリック数を減らすため)。
   引き継いだ日付・担当営業のまま次を登録するので、重複確認フラグは毎回リセットする。 */
"function save(keepOpen) {\n" +
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
"    'アポ種別': $('fKind').value, '紹介元': $('fReferrer').value.trim(),\n" +
"    confirmedOverlap: state.confirmedOverlap\n" +
"  };\n" +
"  setSaveDisabled(true);\n" +
"  google.script.run.withSuccessHandler(function (result) {\n" +
"    setSaveDisabled(false);\n" +
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
"    var notice = result && result.notified ? '保存しました。Slackに通知しました' : '保存しました(Slack通知なし)';\n" +
"    if (keepOpen) {\n" +
"      state.editingId = null;\n" +
"      state.confirmedOverlap = false;\n" +
"      $('overlapWarn').classList.remove('show');\n" +
"      $('modalTitle').textContent = '新規アポ';\n" +
"      ['fCustomer', 'fPlace', 'fMemo', 'fReferrer'].forEach(function (id) { $(id).value = ''; });\n" +
"      $('fStatus').value = 'スケジュール調整中';\n" +
"      $('fCustomer').focus();\n" +
"      toast(notice + ' 続けて登録できます');\n" +
"      load();\n" +
"      return;\n" +
"    }\n" +
"    closeModal(); closeSheet();\n" +
"    toast(notice);\n" +
"    load();\n" +
"  }).withFailureHandler(function (error) { setSaveDisabled(false); fail(error); })\n" +
"    .saveAppointment(payload);\n" +
"}\n" +
"function setSaveDisabled(disabled) {\n" +
"  $('modalSave').disabled = disabled;\n" +
"  $('modalSaveNext').disabled = disabled;\n" +
"}\n" +
"function quickStatus(status, reason) {\n" +
"  if (!state.selected) return;\n" +
"  closeSheet();\n" +
"  google.script.run.withSuccessHandler(function (result) {\n" +
"    if (result && !result.ok && result.overlapWarning) {\n" +
"      toast('時間帯が重なるため更新していません。「編集」から内容を確認してください');\n" +
"      load(); return;\n" +
"    }\n" +
"    toast(result && result.notified ? '「' + status + '」に更新し、Slackへ通知しました'\n" +
"      : '「' + status + '」に更新しました(Slack通知なし)');\n" +
"    load();\n" +
"  }).withFailureHandler(fail).updateStatus(state.selected['アポID'], status, reason || '');\n" +
"}\n" +
"function reportDelayMinutes(minutes) {\n" +
"  var apoId = state.selected ? state.selected['アポID'] : null;\n" +
"  closeSheet();\n" +
"  google.script.run.withSuccessHandler(function (result) {\n" +
"    toast((result && result.notified ? '遅れ連絡を送信しました' : '遅れ連絡を記録しました(Slack通知なし)') +\n" +
"      '(影響しうるアポ ' + result.targetCount + '件)');\n" +
"  }).withFailureHandler(fail).reportDelay(minutes, apoId);\n" +
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
"$('modalSave').addEventListener('click', function () { save(false); });\n" +
"$('modalSaveNext').addEventListener('click', function () { save(true); });\n" +
"Array.prototype.forEach.call(document.querySelectorAll('[data-st]'), function (el) {\n" +
"  el.addEventListener('click', function () { quickStatus(el.getAttribute('data-st'), el.getAttribute('data-reason')); });\n" +
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
