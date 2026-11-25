#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂 申請準備シート自動生成(トドケ管轄・守り部線引き準拠)
data/fukugiiro/seido.json から、制度ごとに「申請を最後までやり切る」伴走シートを
site/fukugiiro/kit/<id>/index.html に生成する。fetch後に毎回再生成。

設計(2026-08-06 三名体制の裁定):
- 画面=一番上に要点(対象・金額・窓口)、その下に「やることは4つ」をたたんで並べる(2026-11-21 利用者の声
  「詰まりすぎ・文字が多すぎ」で組み直し。以前の5ステップ工程表は①〜④と同じ内容の繰り返しだったため外した)。
  印刷=要点+電話台本+持ち物+窓口ひとこと+メモの1枚(たたんだ項目は印刷の直前に開く)。
- 「どこに・何を持って・何と言えば」を、まず電話1本で確定できる台本を最上位に置く(ムダ足をなくす最大レバー)。
- 電話番号・締切・受け取りの時期は断定せず「窓口で"聞くこと"」として設計(正確性最優先)。
- 申請後の「受け取れたか確認」まで導線を伸ばす(受給報告=次の県民の役に立つ)。

守り部の線引き(docs/フクギイロ_申請準備キット_線引き.md):
- 申請書の代筆・代行はしない。書くのは本人。私たちは「迷わない準備」までを提供する
- 持ち物は「よくある例」として提示し、断定しない。窓口での最終確認を全ページで案内
- 公式様式PDFの再配布はしない(版ズレ防止)。必ず公式ページへのリンクで案内
"""
import datetime
import json
import os
import shutil
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from fg_seo import HIDDEN_MUNIS, MUNI_SLUG, breadcrumb_jsonld, canonical_tag, faq_jsonld, ogp_tags
import fg_madoguchi  # 窓口情報(役場住所・電話・開庁時間)2026-09-02
import fg_source_status as fgsrc  # 公式ページが無い(404/410)出典のリンクだけを止める

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "fukugiiro", "seido.json")
OUT_DIR = os.path.join(BASE, "site", "fukugiiro", "kit")

# ほぼ必ず要るもの(どの制度でも共通で聞かれることが多い)
CORE_ITEMS = [
    "本人確認書類(運転免許証・マイナンバーカードなど)",
    "マイナンバーがわかるもの",
    "振込先の口座がわかるもの(通帳・キャッシュカード)",
    "印鑑(不要な市町村もあります)",
]

# ライフイベント別の追加持ち物(よくある例=「あなたの場合、要るかもしれないもの」)
EVENT_ITEMS = {
    "妊娠・出産": ["母子健康手帳", "出産にかかった費用がわかるもの(領収書・明細)"],
    "子育て": ["お子さんの健康保険情報がわかるもの", "世帯の状況がわかる書類(あれば)"],
    "入園・入学": ["在学がわかるもの(学生証・在学証明など)", "学校から配られた案内(あれば)"],
    "失業": ["離職票・雇用保険受給資格者証(お持ちの場合)"],
    "就職・転職": ["勤務先や雇用条件がわかるもの(雇用契約書など)"],
    "病気・けが": ["医療費の領収書", "加入している健康保険がわかるもの"],
    "低所得・生活苦": ["収入がわかる書類(給与明細・課税証明など)"],
    "住宅取得・引越": ["住まいの契約がわかる書類(賃貸契約書など)"],
    "介護": ["介護保険証(お持ちの場合)"],
    "障がい": ["障害者手帳(お持ちの場合)"],
    "災害": ["り災証明書(お持ちの場合・後からでも可の場合あり)"],
}

STYLE = """
h1,h2,h3{font-family:"Shippori Mincho","Hiragino Mincho ProN",serif;font-weight:600;word-break:keep-all;overflow-wrap:anywhere}
.wrap{max-width:680px;margin:0 auto;padding:28px 20px 64px}
h1{font-size:1.35rem;margin-bottom:4px;line-height:1.5}
h2{font-size:1.05rem;margin:24px 0 8px;border-left:6px solid var(--fg-accent);padding-left:.5em}
.box{background:var(--fg-card);border:1px solid var(--fg-line);border-radius:16px;padding:16px 18px;margin:10px 0;box-shadow:var(--fg-shadow)}
/* 一番上の要点(対象・金額・窓口)。2026-11-21 利用者の声「詰まりすぎ・文字が多すぎ」で組み直し */
.kicker{font-size:.85rem;color:var(--fg-muted);margin:0}
.sum{background:var(--fg-card);border:1px solid var(--fg-line);border-radius:16px;padding:2px 16px;margin:12px 0;box-shadow:var(--fg-shadow)}
.sum>div{display:grid;grid-template-columns:3.6em 1fr;gap:10px;padding:11px 0;border-bottom:1px solid var(--fg-line);line-height:1.7}
.sum>div:last-child{border-bottom:none}
.sum dt{font-size:.82rem;font-weight:700;color:var(--fg-muted);padding-top:3px}
.sum dd{margin:0;font-size:.97rem}
.calls{display:flex;gap:8px;margin:10px 0 4px}
.calls a{flex:1;display:block;padding:12px 8px;min-height:44px;border-radius:12px;text-align:center;font-weight:700;text-decoration:none;font-size:.95rem}
.calls .call{background:var(--fg-deep);color:#fff}
.calls .mapbtn{background:#fff;border:1px solid var(--fg-line);color:var(--fg-ink)}
.caution{font-size:.9rem;line-height:1.7;border-radius:10px;padding:10px 12px;margin:8px 0;border:1px solid}
.caution .chip{display:inline-block;font-weight:800;color:#fff;border-radius:4px;padding:0 7px;margin-right:6px;font-size:.8rem}
/* たたんで開ける項目(やること・役場の場所・コンビニ印刷) */
details.fold{background:var(--fg-card);border:1px solid var(--fg-line);border-radius:14px;margin:8px 0;padding:0 16px}
details.fold>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:10px;padding:13px 0;min-height:44px;font-weight:700}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary::after{content:"";margin-left:auto;width:8px;height:8px;min-width:8px;border-right:2px solid var(--fg-muted);border-bottom:2px solid var(--fg-muted);transform:rotate(45deg);transition:transform .2s}
details.fold[open]>summary::after{transform:rotate(-135deg)}
details.fold[open]>summary{border-bottom:1px dashed var(--fg-line)}
details.fold .in{padding:10px 0 14px;font-size:.95rem;line-height:1.75}
details.fold.small>summary{font-size:.92rem;font-weight:600}
.no{width:28px;height:28px;min-width:28px;border-radius:50%;background:var(--fg-accent);display:inline-flex;align-items:center;justify-content:center;font-size:.9rem;font-weight:800}
.cnt{font-size:.8rem;color:var(--fg-muted);font-weight:500;margin-left:auto}
.say{background:#EAF5F0;border-radius:10px;padding:10px 12px;margin:4px 0 8px;color:#0F5138}
.say b,.say strong{color:var(--fg-deep)}
ol.q{padding-left:1.4em;margin:4px 0 6px}
.items h3{font-size:.9rem;margin:12px 0 2px;color:var(--fg-ink)}
ul.check{list-style:none}
ul.check li{border-bottom:1px dashed var(--fg-line)}
ul.check label{display:flex;align-items:flex-start;gap:12px;padding:7px 0;cursor:pointer}
ul.check input[type=checkbox]{width:22px;height:22px;min-width:22px;margin-top:5px;accent-color:var(--fg-primary)}
ul.check input:checked + span{color:var(--fg-muted);text-decoration:line-through}
.ask{list-style:none;margin-top:4px}
.ask li{background:#F4F7F1;border-radius:8px;padding:7px 12px;margin:5px 0}
.mlabel{font-size:.85rem;color:var(--fg-muted);margin-top:8px}
.memo{width:100%;border:none;border-bottom:2px solid var(--fg-line);background:transparent;font:inherit;font-size:1rem;min-height:44px;resize:vertical;padding:6px 2px}  /* 16px未満はiPhoneで画面が勝手に拡大するため(点検2026-09-03) */
.memo:focus{outline:none;border-bottom-color:var(--fg-primary)}
.prog{font-weight:700;color:var(--fg-deep)}
.end{margin:22px 0 8px}
.end .note{text-align:center;margin:4px 0 14px}
.linebtn.sub{background:#fff;color:var(--fg-primary);border:2px solid var(--fg-primary);box-shadow:none}
.fine{font-size:.82rem;color:var(--fg-muted);margin-top:26px;line-height:1.7}
.btns{display:flex;gap:10px;margin:18px 0}
.btns button,.btns a{flex:1;display:block;padding:13px;min-height:44px;border-radius:10px;border:2px solid var(--fg-primary);background:#fff;color:var(--fg-primary);font-size:.95rem;font-weight:700;cursor:pointer;text-align:center;text-decoration:none}
.btns .primary{background:var(--fg-primary);color:#fff}
.linebtn{display:block;max-width:440px;margin:8px auto 0;padding:14px 22px;min-height:44px;background:var(--fg-cta);color:#fff;text-align:center;text-decoration:none;border-radius:999px;font-weight:700;box-shadow:var(--fg-shadow)}
.copybtn{display:inline-block;padding:10px 16px;min-height:44px;border-radius:10px;border:2px solid var(--fg-deep);background:#fff;color:var(--fg-deep);font:inherit;font-size:.92rem;font-weight:700;cursor:pointer}
.copybtn.copied{background:var(--fg-deep);color:#fff}
details.fold ol.conbini{margin:6px 0;padding-left:1.4em}
details.fold ol.conbini li{margin:6px 0}
@media(min-width:900px){.wrap{max-width:820px}}
/* 印刷=要点+電話台本+持ち物+窓口ひとこと+メモの1枚。たたんだ項目は印刷の直前に開く(KIT_JSのbeforeprint)。 */
@media print{.btns,.no-print,.screen-only,.siteheader,.cnt{display:none!important}body{background:#fff;font-size:14px}.wrap{padding:0}.sum,details.fold{break-inside:avoid;box-shadow:none}
  details.fold>summary::after{display:none}
  a[href^="http"]::after{content:" (" attr(href) ")";font-size:.8em;word-break:break-all}
  .memo{min-height:56px;resize:none}}
"""

HEADER = '''<header class="siteheader sh2">
  <a class="hlogo" href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/"><img src="https://allgroup-inc.github.io/hojo-hq/fukugiiro/assets/icon.svg" alt="" width="30" height="30">もらいわすれ堂</a>
  <a class="hcta" href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/shindan/">3分診断</a>
  <details class="hmenu"><summary aria-label="メニューをひらく"><span aria-hidden="true">☰</span></summary>
  <nav>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/shindan/">3分診断</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/area/">市町村</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/kit/">準備シート</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/go/fg-kit/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack('line_add_click')">LINE登録</a>
    <a class="ignav" href="https://www.instagram.com/moradou.okinawa/" target="_blank" rel="noopener" aria-label="Instagram(新しいタブで開きます)" onclick="if(window.fgTrack)fgTrack('ig_click',{pos:'header'})"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="2.5" y="2.5" width="19" height="19" rx="5.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="17.3" cy="6.7" r="1.3" fill="currentColor" stroke="none"/></svg></a>
  </nav></details>
</header><script>(function(){var d=document.querySelector(".sh2 .hmenu");if(!d||!window.matchMedia)return;var m=window.matchMedia("(min-width:760px)");function f(){if(m.matches)d.open=true;}f();if(m.addEventListener)m.addEventListener("change",f);})();</script>'''


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def kit_jsonld(it):
    """制度ページの構造化データ(schema.org GovernmentService)。
    掲載中の事実(制度名・提供元・対象地域・対象者・公式URL)のみ。金額など未確定値は入れない。"""
    data = {
        "@context": "https://schema.org",
        "@type": "GovernmentService",
        "name": it.get("name", ""),
        "serviceType": "給付金・手当・助成制度",
        "provider": {"@type": "GovernmentOrganization", "name": it.get("issuer", "")},
        "areaServed": {"@type": "AdministrativeArea", "name": it.get("area", "全国")},
        "audience": {"@type": "Audience", "audienceType": it.get("target_household", "")},
        "url": fgsrc.jsonld_url(it),
        "serviceUrl": fgsrc.jsonld_url(it),
    }
    if not fgsrc.jsonld_url(it):  # 公式ページを確認中の制度は、開けないURLを構造化データに載せない
        data.pop("url"), data.pop("serviceUrl")
    return ('<script type="application/ld+json">\n'
            + json.dumps(data, ensure_ascii=False, indent=1)
            + "\n</script>")


def page(title, desc, body, depth=2, head_extra="", canon_path=None):
    rel = "../" * depth
    seo = ""
    if canon_path is not None:
        seo = canonical_tag(canon_path) + "\n" + ogp_tags(title, desc, canon_path) + "\n"
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
{seo}<link rel="icon" type="image/svg+xml" href="{rel}assets/icon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;600;700&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet" media="print" onload="this.media='all'"><noscript><link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;600;700&family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet"></noscript>
{head_extra}
<link rel="stylesheet" href="{rel}assets/fg-base.css">
<style>{STYLE}</style>
<link rel="stylesheet" href="{rel}assets/fg-refine.css">
</head>
<body>
<script src="{rel}analytics-config.js"></script>
<script src="{rel}assets/fg-analytics.js"></script>
{HEADER}
<div class="wrap">
{body}
</div>
</body>
</html>
"""


KIT_JS = """
<script>
// シートの定型文コピー(個人のメモ・チェック状態は含めない — 議事_20260817 ウタガイ条件)
var FK_SHEET_TEXT = __SHEET__;
function fkFlash(btn, label){
  var t = btn.textContent;
  btn.textContent = label; btn.classList.add("copied");
  setTimeout(function(){ btn.textContent = t; btn.classList.remove("copied"); }, 1800);
}
function fkCopy(text, btn, ev){
  function done(){ fkFlash(btn, "コピーしました ✓"); if (window.fgTrack) fgTrack(ev); }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done, function(){ fkCopyFallback(text); done(); });
  } else { fkCopyFallback(text); done(); }
}
function fkCopyFallback(text){
  var ta = document.createElement("textarea");
  ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
  document.body.appendChild(ta); ta.select();
  try { document.execCommand("copy"); } catch(e){}
  document.body.removeChild(ta);
}
function fkCopySheet(btn){ fkCopy(FK_SHEET_TEXT, btn, "kit_copy"); }
function fkCopySay(btn){
  var el = document.getElementById("mado-say");
  fkCopy(el ? el.textContent.trim() : "", btn, "kit_copy_say");
}
(function(){
  var KEY = "fk_kit___ID__";
  var saved = {c:[], m:{}, s:[]};
  try { var o = JSON.parse(localStorage.getItem(KEY)); if(o){ saved.c=o.c||[]; saved.m=o.m||{}; saved.s=o.s||[]; } } catch(e){}
  var boxes = Array.prototype.slice.call(document.querySelectorAll("ul.check input[type=checkbox]"));
  var memos = Array.prototype.slice.call(document.querySelectorAll("textarea.memo"));
  var prog = document.getElementById("prog");
  var trackedCheck = false;
  function save(){
    // s は以前の5ステップ工程表の記録。表は無くなったが、戻したときのために消さずに持ち越す
    var data = {c: [], m: {}, s: saved.s};
    boxes.forEach(function(b, i){ if (b.checked) data.c.push(i); });
    memos.forEach(function(t, i){ if (t.value) data.m[i] = t.value.slice(0, 500); });
    try { localStorage.setItem(KEY, JSON.stringify(data)); } catch(e){}
  }
  function updItems(){
    var n = boxes.filter(function(b){ return b.checked; }).length;
    if (prog) prog.textContent = n + " / " + boxes.length + (n === boxes.length && n > 0 ? " そろった ✓" : "");
  }
  function openParent(el){
    var d = el.closest ? el.closest("details") : null;
    if (d) d.open = true;
  }
  boxes.forEach(function(b, i){
    if (saved.c.indexOf(i) >= 0) { b.checked = true; openParent(b); }
    b.addEventListener("change", function(){
      save(); updItems();
      if (!trackedCheck && window.fgTrack) { trackedCheck = true; fgTrack("kit_check"); }
    });
  });
  memos.forEach(function(t, i){
    if (saved.m[i]) { t.value = saved.m[i]; openParent(t); }
    t.addEventListener("input", save);
  });
  updItems();
  // 印刷するときは、たたんだ項目もすべて開く(閉じたままだと持ち物やメモ欄が紙に出ない)。印刷後は元に戻す
  window.addEventListener("beforeprint", function(){
    Array.prototype.forEach.call(document.querySelectorAll("details"), function(d){
      if (!d.open) { d.setAttribute("data-print-open", "1"); d.open = true; }
    });
  });
  window.addEventListener("afterprint", function(){
    Array.prototype.forEach.call(document.querySelectorAll("details[data-print-open]"), function(d){
      d.open = false; d.removeAttribute("data-print-open");
    });
  });
})();
</script>
"""


def kit_page(it, updated):
    verified = it.get("verified") is True
    if verified:
        badge = ' <span class="status ok">✓ 公式と照合済み</span>'
    elif it.get("status") == "要確認":
        badge = ' <span class="status">要確認</span>'
    else:
        badge = ""
    name = esc(it["name"])
    # 照合の印は見出しの上に小さく出す(パンくずの「申請準備シート」と二重にしない)
    kicker = f'<p class="kicker">{badge.strip()}</p>\n' if badge else ""

    # 持ち物: 「ほぼ必ず要るもの」と「あなたの場合、要るかもしれないもの」に2層化
    event_items = []
    for ev in it.get("life_events", []):
        for x in EVENT_ITEMS.get(ev, []):
            if x not in event_items and x not in CORE_ITEMS:
                event_items.append(x)
    idx = 0
    core_html = []
    for x in CORE_ITEMS:
        core_html.append(f'<li><label><input type="checkbox" data-k="{idx}"><span>{esc(x)}</span></label></li>')
        idx += 1
    event_html = []
    for x in event_items:
        event_html.append(f'<li><label><input type="checkbox" data-k="{idx}"><span>{esc(x)}</span></label></li>')
        idx += 1
    event_block = ""
    if event_html:
        event_block = (
            '<div class="items"><h3>あなたの場合、要るかもしれないもの</h3>'
            '<ul class="check">' + "\n".join(event_html) + "</ul></div>"
        )

    # 要確認バナー
    warn = ""
    if not verified and it.get("status") == "要確認":
        warn = ('<div class="caution" style="border-color:#E0B54A;background:#FFF8E6">'
                'この制度は内容の最終確認中です。金額・締切・対象はお出かけ前に必ず公式ページと窓口でご確認ください。</div>')
    if fgsrc.unavailable(it):
        warn += ('<div class="caution" style="border-color:#E0B54A;background:#FFF8E6">'
                 f'<strong>{fgsrc.LABEL}</strong>: {fgsrc.NOTE}</div>')

    # 聞きに行く場所と時間(市町村・県の制度のみ。2026-09-02 小柳さん発案)
    # 役場(本庁)単位の情報。担当課が別庁舎の場合があるため非断定の注意文を必ず添える。
    madoguchi_html = ""
    mg = fg_madoguchi.get(it.get("area"))
    if mg:
        q = urllib.parse.quote(f"{mg['hall']} {mg['address']}")
        map_url = f"https://www.google.com/maps/search/?api=1&query={q}"
        tel_digits = mg["tel"].replace("-", "")
        hours = mg["hours"]
        if hours == "要確認":
            hours_html = "要確認(お出かけ前に代表電話でおたずねください)"
        else:
            hours_html = esc(hours)
            if mg.get("hours_note"):
                hours_html += f'<span class="note">({esc(mg["hours_note"])})</span>'
        madoguchi_html = (
            '<div class="calls screen-only">'
            f'<a class="call" href="tel:{tel_digits}" onclick="if(window.fgTrack)fgTrack(\'kit_tel\')">☎ 役場(代表)に電話</a>'
            f'<a class="mapbtn" href="{map_url}" target="_blank" rel="noopener" '
            'onclick="if(window.fgTrack)fgTrack(\'kit_map\')">📍 地図でひらく</a></div>'
            '<details class="fold small place"><summary>役場の場所・電話・開庁時間</summary><div class="in">'
            f'<p>{esc(mg["hall"])}<br><span class="note">{esc(mg["address"])}</span></p>'
            f'<p style="margin-top:6px">☎ <a href="tel:{tel_digits}" onclick="if(window.fgTrack)fgTrack(\'kit_tel\')">{esc(mg["tel"])}</a>(代表)'
            '<br><span class="note">「この制度について聞きたいです」と伝えれば、担当の課につないでもらえます</span></p>'
            f'<p style="margin-top:6px">🕐 開庁時間の目安: {hours_html}'
            '<br><span class="note">祝日・年末年始はお休みです。担当課が別の建物の場合もあるため、'
            '遠くから行くときは先にお電話で確認すると安心です。</span></p>'
            '</div></details>')

    # 併給・重複の注意(あれば)
    combine_html = ""
    cmb = it.get("combine") or {}
    if cmb.get("note"):
        ctype = cmb.get("type", "exclusive")
        # 「どちらか一方」だけでは何と何のことか分からない(2026-11-21 利用者の声)ため、ほかの制度との関係だと分かる言い方にする
        clabel = {"exclusive": "ほかの制度と併用できない場合あり", "adjust": "ほかの制度との併用に条件あり",
                  "stackable": "ほかの制度と一緒に受けられる"}.get(ctype, "ほかの制度との併用に注意")
        colors = {"exclusive": ("#FBEEE6", "#E8C4AE", "#B9502F"),
                  "adjust": ("#FFF6DB", "#EAD59A", "#7a5b00"),
                  "stackable": ("#E7F4EC", "#B7E0CF", "#0F5138")}
        bg, bd, lc = colors.get(ctype, colors["exclusive"])
        combine_html = (f'<div class="caution" style="background:{bg};border-color:{bd}">'
                        f'<span class="chip" style="background:{lc}">{clabel}</span>'
                        f'{esc(cmb["note"])}</div>')

    src = esc(it["source_url"])
    # 公式ページが無い(404/410)と確かめた出典は、リンクの代わりに「公式ページを確認中」を出す(fg_source_status.py)
    official_btn = fgsrc.link(it, "公式ページで最新を確認",
                              attrs="rel=\"noopener\" onclick=\"if(window.fgTrack)fgTrack('kit_official')\"")
    if fgsrc.unavailable(it):
        phone_src = "公式ページを確認中のため、電話番号はお住まいの市町村の代表番号などでご確認ください"
    else:
        phone_src = f'電話番号は公式ページに載っています → <a href="{src}" rel="noopener">公式ページで電話番号を確認</a>'
    footer_src = fgsrc.link(it, "公式ページ")
    # この制度専用の「情報の訂正」メール導線(件名・本文に制度名を自動で差し込む)
    _sub = urllib.parse.quote(f"[情報の訂正] {it['name']}")
    _bd = urllib.parse.quote(
        f"●制度名：{it['name']}\n●地域：{it.get('area','')}\n"
        f"●気づいた点（古い・違う箇所）：\n●公式ページURL：{it['source_url']}\n"
    )
    report_link = f"mailto:info@fukugiiro.com?subject={_sub}&body={_bd}"
    # kit→area 逆リンク(内部リンクの一方通行解消・2026-08-10 SEO裁定)
    area = it.get("area", "全国")
    if area in MUNI_SLUG:
        area_link = f'<a href="../../area/{MUNI_SLUG[area]}/">{esc(area)}のほかの給付金・手当</a> ・ '
    else:
        area_link = '<a href="../../area/">お住まいの市町村の給付金・手当</a> ・ '
    body = f"""
<p class="note no-print"><a href="../../index.html">もらいわすれ堂</a> › 申請準備シート</p>
{kicker}<h1>{name}</h1>
{warn}
<dl class="sum">
  <div><dt>対象</dt><dd>{esc(it['target_household'])}</dd></div>
  <div><dt>金額</dt><dd>{esc(it['amount_note'])}</dd></div>
  <div><dt>窓口</dt><dd>{esc(it['how_to_apply'])}</dd></div>
</dl>
{madoguchi_html}
{combine_html}
<div class="btns">{official_btn}</div>

<section class="todo">
<h2>やることは4つ</h2>
<details class="fold task" open>
  <summary><span class="no">1</span>電話で3つ聞く</summary>
  <div class="in">
  <div class="say">「<b>{name}</b>の申請をしたいのですが、3つ教えてください」</div>
  <ol class="q">
    <li>受付の<b>時間</b>と、行く<b>場所(窓口)</b></li>
    <li><b>私の場合</b>、何を持っていけばいいか</li>
    <li><b>申請書</b>はあるか・<b>いつまで</b>に出せばいいか</li>
  </ol>
  <p class="note">対象になるか自信がなくても、そのまま聞いて大丈夫です。{phone_src}</p>
  <p class="mlabel">聞いた電話番号・受付時間のメモ:</p>
  <textarea class="memo" data-m="0" rows="1" placeholder="例) 〇〇課 098-000-0000 / 平日8:30-17:15"></textarea>
  </div>
</details>
<details class="fold task">
  <summary><span class="no">2</span>持ち物をそろえる<span class="cnt" id="prog"></span></summary>
  <div class="in">
  <p class="note">よくある例です。市町村やご家庭の状況で変わるので、細かい違いは電話か窓口で確認すれば大丈夫です。</p>
  <div class="items"><h3>ほぼ必ず要るもの</h3>
  <ul class="check">
{chr(10).join(core_html)}
  </ul></div>
  {event_block}
  </div>
</details>
<details class="fold task">
  <summary><span class="no">3</span>窓口でこう言う</summary>
  <div class="in">
  <div class="say" id="mado-say">「<strong>{name}</strong>について教えてください。対象になるか確認したいです」</div>
  <p class="note">これだけ言えば、職員の方が案内してくれます。言葉で伝えにくいときは、この画面を見せても大丈夫です。</p>
  <p class="screen-only" style="margin-top:6px"><button class="copybtn" onclick="fkCopySay(this)">このひとことをコピーする</button></p>
  <p style="margin-top:10px">あわせて聞いておくこと:</p>
  <ul class="ask">
    <li>締切はいつまでですか？</li>
    <li>申請書はこの場で書けますか？ 書き方も教えてください</li>
    <li>受け取れるのは、いつ頃ですか？</li>
  </ul>
  </div>
</details>
<details class="fold task">
  <summary><span class="no">4</span>聞いたことをメモする</summary>
  <div class="in">
  <p class="mlabel">締切(いつまで):</p><textarea class="memo" data-m="1" rows="1"></textarea>
  <p class="mlabel">足りなかった書類・次にやること:</p><textarea class="memo" data-m="2" rows="1"></textarea>
  <p class="mlabel">受け取りは、いつ頃・どう届く:</p><textarea class="memo" data-m="3" rows="1"></textarea>
  </div>
</details>
<p class="note screen-only">チェックとメモはこの端末にだけ残ります。</p>
</section>

<section class="end screen-only">
  <a class="linebtn" href="https://allgroup-inc.github.io/hojo-hq/go/fg-kit/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack('line_add_click')">締切をLINEで受け取る</a>
  <p class="note">締切の約1か月前から・無料・名前の入力は不要</p>
  <a class="linebtn sub" href="../../houkoku/" onclick="if(window.fgTrack)fgTrack('jukyu_report_link_kit')">受け取れたことを報告する(匿名・無料)</a>
  <p class="note">次の県民の「もらい忘れ」を防ぐ力になります</p>
</section>

<section class="no-print">
<h2>持っていく</h2>
<p class="note">スマホで開いたままでも、窓口で使えます。</p>
<div class="btns">
  <button class="primary" onclick="if(window.fgTrack)fgTrack('kit_print');window.print()">印刷する</button>
  <button class="copybtn" id="copy-sheet" onclick="fkCopySheet(this)">コピーして残す</button>
</div>
<details class="fold small" ontoggle="if(this.open&&window.fgTrack)fgTrack('kit_conbini')">
  <summary>プリンターがないとき(コンビニで印刷)</summary>
  <div class="in">
    <ol class="conbini">
      <li>上の「印刷する」を押して、プリンターのかわりに<strong>「PDFとして保存」</strong>を選びます(iPhoneは共有ボタン→「プリント」からでも保存できます)</li>
      <li><strong>セブンイレブン</strong>なら「かんたんnetprint」アプリ(会員登録なしで使えます)、<strong>ファミリーマート・ローソン</strong>なら「ネットワークプリント」アプリに、そのPDFを登録します</li>
      <li>表示された<strong>受付番号</strong>を、お店のコピー機(マルチコピー機)に入力して印刷します。A4白黒で1枚20円前後が目安です(機種や時期で変わることがあります)</li>
    </ol>
    <p class="note">くわしい手順・料金は各サービスの公式ページでご確認ください:
    <a href="https://www.printing.ne.jp/" rel="noopener" target="_blank">netprint(セブンイレブン)</a> ・
    <a href="https://networkprint.ne.jp/" rel="noopener" target="_blank">ネットワークプリント(ファミマ・ローソン)</a></p>
    <p class="note">コピーした内容は、LINEのメモやトークに貼りつけておくと、電波の弱い窓口でもすぐ開けます。</p>
  </div>
</details>
</section>

<p class="fine screen-only">この制度の情報が「古い」「違う」と気づいたら、<a href="{report_link}" onclick="if(window.fgTrack)fgTrack('teisei_mail')">この制度の情報の間違いを知らせる</a>(24時間以内の修正を目指します)。</p>
<div class="disclaimer">このシートは公式情報に基づく「準備のご案内」です。持ち物は一般的な例で、市町村により異なります。受給できるかどうかの最終判断は各窓口で行われます。<br>申請書の作成代行・代筆は行っていません(ご本人が記入します)。<br>専門家のサポートが必要な場合は、提携の専門家(社会保険労務士・行政書士など)をご紹介します。<br>最終更新: {esc(updated)} / もらいわすれ堂(運営: 株式会社フクギイロ)/ 出典: {footer_src}</div>
<p style="margin-top:16px" class="no-print footlinks">{area_link}<a href="../index.html">申請準備シート一覧へ</a> ・ <a href="../../shindan/">3分診断</a> ・ <a href="../../teisei/">情報の訂正</a> ・ <a href="../../index.html">もらいわすれ堂 トップ</a></p>
<p class="no-print" style="margin-top:4px"><a class="iglink" href="https://www.instagram.com/moradou.okinawa/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack('ig_click')">Instagramで最新情報を見る ›</a></p>
"""
    # コピー用の定型文(制度名・持ち物例・セリフ・URLのみ。個人のメモ・チェック状態は含めない)
    sheet_lines = [
        f"【{it['name']} 申請準備シート|もらいわすれ堂】",
        f"▼受け取れるかもしれない方: {it.get('target_household','')}",
        f"▼行き先(窓口): {it.get('how_to_apply','')}",
        "▼持ち物(よくある例・市町村で変わります):",
    ]
    sheet_lines += [f"・{x}" for x in CORE_ITEMS] + [f"・{x}" for x in event_items]
    sheet_lines += [
        "▼窓口でのひとこと:",
        f"「{it['name']}について教えてください。対象になるか確認したいです」",
        "▼行く前に電話で聞く3つ: ①受付時間と場所 ②私の場合の持ち物 ③申請書と締切",
        f"くわしくは: https://allgroup-inc.github.io/hojo-hq/fukugiiro/kit/{it['id']}/",
        "※金額・締切は公式ページと窓口でご確認ください",
    ]
    sheet_text = json.dumps("\n".join(sheet_lines), ensure_ascii=False)
    body += KIT_JS.replace("__ID__", it["id"]).replace("__SHEET__", sheet_text)
    # 制度名が地域名で始まる場合は前置しない(「北谷町 北谷町 こども医療費助成」の二重表記防止)
    if area in MUNI_SLUG and not it["name"].startswith(area):
        title = f"{area} {it['name']}の申請方法・持ち物・窓口|もらいわすれ堂"
    elif area == "沖縄県" and not it["name"].startswith("沖縄"):
        title = f"沖縄県 {it['name']}の申請方法・持ち物・窓口|もらいわすれ堂"
    elif area in MUNI_SLUG or area == "沖縄県":
        title = f"{it['name']}の申請方法・持ち物・窓口|もらいわすれ堂"
    else:
        title = f"{it['name']}の申請方法・持ち物・窓口(沖縄)|もらいわすれ堂"
    desc = (f"{it['name']}の申請に必要な持ち物リスト・窓口での聞き方・電話で確認する3つのこと。"
            "スマホのままでも、印刷しても窓口で使える無料の申請準備シート(代行はせず、準備を伴走します)。")
    faq = faq_jsonld([
        (f"{it['name']}の対象になるのはどんな人ですか?",
         f"{it.get('target_household','')}(最終的に対象かどうかは、公式ページと窓口で確認できます)"),
        (f"{it['name']}はどこに申請しますか?", it.get("how_to_apply", "")),
        ("何を持っていけばいいですか?",
         "よくある例は、本人確認書類・マイナンバーがわかるもの・振込先の口座がわかるもの・印鑑です。"
         "市町村やご家庭の状況で変わるため、行く前に窓口へ電話で確認するのが確実です。"),
    ])
    crumbs = breadcrumb_jsonld([("もらいわすれ堂", ""), ("申請準備シート", "kit/"), (it["name"], None)])
    return page(title, desc, body, head_extra=kit_jsonld(it) + "\n" + faq + "\n" + crumbs,
                canon_path=f"kit/{it['id']}/")


RESUME_JS = r"""<script>
// 前回の続き(この端末に残っている準備シートの記録を読むだけ。書き換え・送信はしない)
(function(){
  var sec = document.getElementById("kit-resume"), ul = document.getElementById("kit-resume-list");
  if (!sec || !ul) return;
  var rows = [];
  try {
    for (var i = 0; i < localStorage.length; i++) {
      var k = localStorage.key(i);
      if (!k || k.indexOf("fk_kit_") !== 0) continue;
      var id = k.slice(7), o = JSON.parse(localStorage.getItem(k) || "null");
      if (!o) continue;
      var n = (o.c || []).length, memo = Object.keys(o.m || {}).length > 0;
      if (!n && !memo) continue;
      var a = document.querySelector('.kitgroup a[href="' + id.replace(/[^\w-]/g, "") + '/"]');
      if (!a) continue;
      rows.push({href: a.getAttribute("href"), name: a.firstChild ? a.firstChild.textContent : a.textContent, n: n, memo: memo});
    }
  } catch (e) { return; }
  if (!rows.length) return;
  rows.slice(0, 5).forEach(function(r){
    var li = document.createElement("li"), link = document.createElement("a");
    link.href = r.href; link.textContent = r.name;
    link.addEventListener("click", function(){ if (window.fgTrack) fgTrack("kit_resume_click"); });
    var info = document.createElement("span"); info.className = "note";
    info.textContent = " 持ち物チェック " + r.n + "件" + (r.memo ? "・メモあり" : "");
    li.appendChild(link); li.appendChild(info); ul.appendChild(li);
  });
  sec.hidden = false;
})();
</script>"""


OPEN_NOW_DAYS = 90


def _md(d):
    """2026-12-18 → 2026年12月18日(年を省くと、来年の締切か何年も先かが分からない)"""
    try:
        y, m, dd = str(d)[:10].split("-")
        return f"{int(y)}年{int(m)}月{int(dd)}日"
    except ValueError:
        return str(d)


def index_page(items, updated):
    # 260件超の一覧で行ごとのインラインstyleを繰り返すとサイズ予算(96KB)を超えるため、
    # 共通スタイルは下のbody内<style>に1回だけ書く(2026-09-11 fetch #254のサイズ超過対応)
    def line(it):
        # 一覧では「照合済み」は✓だけに圧縮(176件の縦の壁と視覚ノイズを減らす・議事_20260817組版)
        if it.get("verified") is True:
            b = '&nbsp;<span class="status ok" title="公式と照合済み">✓</span>'
        elif it.get("status") == "要確認":
            b = '&nbsp;<span class="status">要確認</span>'
        else:
            b = ""
        return f'<li><a href="{esc(it["id"])}/">{esc(it["name"])}{b}</a></li>'
    # 全国/沖縄県/市町村の3区分で表示(160件のフラット一覧は探しにくいため・2026-08-12 小柳さん委任裁定)
    national = [it for it in items if it.get("area") == "全国"]
    pref = [it for it in items if it.get("area") == "沖縄県"]
    muni = sorted([it for it in items if it.get("area") not in ("全国", "沖縄県")],
                  key=lambda it: (it.get("area", ""), it.get("name", "")))
    sections = []
    for label, group, note in [
        ("全国の制度", national, "お住まいがどこでも対象になる可能性があります"),
        ("沖縄県の制度", pref, "沖縄県にお住まいの方向けです"),
        ("市町村の制度", muni, "お住まいの市町村名から探せます(市町村ページからも見られます)"),
    ]:
        if not group:
            continue
        lis = "\n".join(line(it) for it in group)
        sections.append(
            f"<section class='kitgroup'><h2 style='font-size:1.1rem;margin-top:20px'>{label}({len(group)}件)</h2>"
            f"<p class='note'>{note}</p>"
            f"<div class='box'><ul class='kul'>{lis}</ul></div></section>"
        )
    sections_html = "\n".join(sections)

    # いま受け付けている(締切のある)制度を一覧の上に出す。締切を過ぎた制度は収集の段階で外れる
    # (2026-11-25「常に使ってもらえる工夫」: 季節の締切がある制度を、来た人がまず目にする場所へ)
    # 何年も先の期限(例: 2031年まで続く減税)は「いま」の話ではないので、90日以内に締切があるものだけにする
    today = updated[:10]
    horizon = (datetime.date.fromisoformat(today) + datetime.timedelta(days=OPEN_NOW_DAYS)).isoformat()
    open_now = sorted([it for it in items if it.get("deadline_type") == "期限あり"
                       and today <= str(it.get("deadline") or "")[:10] <= horizon],
                      key=lambda it: str(it.get("deadline")))[:5]
    if open_now:
        lis = "".join(
            f'<li><a href="{esc(it["id"])}/">{esc(it["name"])}</a>'
            f'<span class="note"> 締切 {esc(_md(it["deadline"]))}(最新は公式ページでご確認ください)</span></li>'
            for it in open_now)
        open_html = (f'<section class="kitopen"><h2 style="font-size:1.05rem;margin-top:18px">いま受付中・締切がある制度</h2>'
                     f'<div class="box"><ul class="kul">{lis}</ul></div></section>')
    else:
        open_html = ""
    body = f"""
<style>.kul{{list-style:none}}.kul .status{{display:inline}}.kul li{{border-bottom:1px dashed var(--fg-line)}}.kul a{{display:inline-block;padding:9px 0;line-height:1.55}}.kul .status{{font-size:.72rem;padding:1px 7px}}.kul .ok{{font-size:inherit}}</style>
<h1>申請準備シート一覧</h1>
<p class="note">制度ごとに「どこに・何を持って・何と言えば申請できるか」をまとめた申請準備シートを用意しています。まず電話で聞く3つ・持ち物チェック・窓口での会話・受け取りの確認まで。<strong>スマホで開いたまま窓口で使えます</strong>(印刷して持っていくのもOK。プリンターがない方向けにコンビニ印刷の手順も各シートにあります)。どれが自分に合うかわからないときは、3分診断からどうぞ。</p>
<a class="no-print" href="../shindan/" style="display:block;max-width:420px;margin:16px auto;padding:14px 24px;background:var(--fg-primary);color:#fff;text-align:center;text-decoration:none;border-radius:999px;font-weight:700">3分でもらい忘れ診断をはじめる</a>
<label for="kitsearch" class="note">制度名・市町村名でさがす</label>
<input id="kitsearch" class="kitsearch" type="search" placeholder="例: 児童手当、浦添、出産" autocomplete="off">
<p class="note kitsearch-none" id="kitsearch-none">見つかりませんでした。言葉を短くするか、<a href="../shindan/">3分診断</a>をお試しください。</p>
<section class="kitresume" id="kit-resume" hidden><h2 style="font-size:1.05rem;margin-top:18px">前回の続きから</h2>
<p class="note">この端末で途中まで進めた準備シートです(記録はこの端末の中だけにあります)。</p>
<div class="box"><ul class="kul" id="kit-resume-list"></ul></div></section>
{open_html}
{sections_html}
<script>
// 一覧の絞り込み(この端末の中だけで動く。入力した言葉は送信も保存もしない)
(function(){{
  var box = document.getElementById("kitsearch"), none = document.getElementById("kitsearch-none");
  if (!box) return;
  var groups = Array.prototype.slice.call(document.querySelectorAll(".kitgroup"));
  box.addEventListener("input", function(){{
    var q = box.value.trim(), hit = 0;
    groups.forEach(function(g){{
      var n = 0;
      Array.prototype.forEach.call(g.querySelectorAll(".kul li"), function(li){{
        var ok = !q || li.textContent.indexOf(q) >= 0;
        li.style.display = ok ? "" : "none"; if (ok) n++;
      }});
      g.style.display = n ? "" : "none"; hit += n;
    }});
    none.style.display = hit ? "none" : "block";
  }});
}})();
</script>
{RESUME_JS}
<p class="note" style="margin-top:18px;text-align:center">もう受け取れた制度はありますか? <a href="../houkoku/" onclick="if(window.fgTrack)fgTrack('jukyu_report_link_kit',{{pos:'index'}})">受け取れたことを教えてください(匿名・任意)</a><br>制度名とおおよその金額だけで大丈夫です。お名前や口座番号はうかがいません。</p>
<div class="disclaimer">最終更新: {esc(updated)}(毎日自動更新)/ もらいわすれ堂(運営: 株式会社フクギイロ)</div>
<p style="margin-top:16px" class="footlinks"><a href="../index.html">もらいわすれ堂 トップ</a></p>
<p style="margin-top:4px"><a class="iglink" href="https://www.instagram.com/moradou.okinawa/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack('ig_click')">Instagramで最新情報を見る ›</a></p>
"""
    return page(
        "沖縄の給付金・手当の申請準備シート一覧(持ち物・窓口・電話の聞き方)|もらいわすれ堂",
        "沖縄の給付金・手当の申請準備シート一覧。制度ごとに持ち物リスト・窓口での聞き方・電話で確認する3つのことをまとめ、印刷してそのまま窓口へ持っていけます(無料)。",
        body, depth=1,
        head_extra=breadcrumb_jsonld([("もらいわすれ堂", ""), ("申請準備シート", None)]),
        canon_path="kit/")


def main():
    with open(DATA, encoding="utf-8") as f:
        db = json.load(f)
    items = db["items"]
    # 一時非公開市町村の制度は、古いseido.jsonからも漏らさない(二重防御・議事20260818)
    items = [it for it in items if it.get("area") not in HIDDEN_MUNIS]
    updated = db.get("updated_at", "")

    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_page(items, updated))
    for it in items:
        d = os.path.join(OUT_DIR, it["id"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(kit_page(it, updated))
    print(f"生成完了: 申請準備シート{len(items)}ページ+一覧1ページ")


if __name__ == "__main__":
    main()
