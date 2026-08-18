#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂 申請準備シート自動生成(トドケ管轄・守り部線引き準拠)
data/fukugiiro/seido.json から、制度ごとに「申請を最後までやり切る」伴走シートを
site/fukugiiro/kit/<id>/index.html に生成する。fetch後に毎回再生成。

設計(2026-08-06 三名体制の裁定):
- 画面=5ステップ工程表で伴走(今どこ/次の一歩が見える)。印刷=電話台本+持ち物+窓口ひとことの1枚に圧縮。
- 「どこに・何を持って・何と言えば」を、まず電話1本で確定できる台本を最上位に置く(ムダ足をなくす最大レバー)。
- 電話番号・締切・振込時期は断定せず「窓口で"聞くこと"」として設計(正確性最優先)。
- 申請後の「振り込まれたか確認」まで導線を伸ばす(受給報告=次の県民の役に立つ)。

守り部の線引き(docs/フクギイロ_申請準備キット_線引き.md):
- 申請書の代筆・代行はしない。書くのは本人。私たちは「迷わない準備」までを提供する
- 持ち物は「よくある例」として提示し、断定しない。窓口での最終確認を全ページで案内
- 公式様式PDFの再配布はしない(版ズレ防止)。必ず公式ページへのリンクで案内
"""
import json
import os
import shutil
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from fg_seo import MUNI_SLUG, breadcrumb_jsonld, canonical_tag, faq_jsonld, ogp_tags

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
.goal{background:linear-gradient(180deg,#FDF5E6 0%,var(--fg-card) 100%);border:1px solid var(--fg-accent);border-radius:12px;padding:16px 18px;margin:12px 0}
.goal p{margin:6px 0}
/* 5ステップ工程表(画面のみ・伴走) */
.track{list-style:none;counter-reset:st}
.track li{position:relative;padding:12px 0 12px 46px;border-bottom:1px dashed var(--fg-line);counter-increment:st}
.track .n::before{content:counter(st)}
.track li:last-child{border-bottom:none}
.track label{display:flex;align-items:flex-start;gap:10px;cursor:pointer}
.track input[type=checkbox]{width:24px;height:24px;min-width:24px;margin-top:3px;accent-color:var(--fg-deep)}
.track .n{position:absolute;left:6px;top:14px;width:28px;height:28px;background:var(--fg-accent);border-radius:50%;text-align:center;line-height:28px;font-weight:800;font-size:.9rem}
.track input:checked ~ .n{background:var(--fg-deep);color:#fff}
.track input:checked + span{color:var(--fg-muted);text-decoration:line-through}
.stepbar{height:8px;background:var(--fg-line);border-radius:99px;overflow:hidden;margin:4px 0 2px}
.stepbar>i{display:block;height:100%;width:0;background:var(--fg-deep);transition:width .3s}
.phone{background:#EAF5F0;border:1px solid #B7E0CF;border-radius:12px;padding:16px 18px;margin:10px 0}
.phone .say{background:#fff;border-radius:8px;padding:10px 12px;margin:8px 0;font-size:1rem}
.phone .say b{color:var(--fg-deep)}
.items h3{font-size:.95rem;margin:12px 0 4px;color:var(--fg-ink)}
ul.check{list-style:none}
ul.check li{border-bottom:1px dashed var(--fg-line)}
ul.check label{display:flex;align-items:flex-start;gap:12px;padding:9px 0;cursor:pointer}
ul.check input[type=checkbox]{width:22px;height:22px;min-width:22px;margin-top:5px;accent-color:var(--fg-primary)}
ul.check input:checked + span{color:var(--fg-muted);text-decoration:line-through}
.madoguchi{font-size:.95rem;background:#EAF5F0;border-radius:8px;padding:12px 14px;color:#0F5138}
.ask{list-style:none;margin-top:6px}
.ask li{background:#fff;border-radius:8px;padding:8px 12px;margin:6px 0;color:#0F5138}
.memo{width:100%;border:none;border-bottom:2px solid var(--fg-line);background:transparent;font:inherit;font-size:.95rem;min-height:44px;resize:vertical;padding:6px 2px}
.memo:focus{outline:none;border-bottom-color:var(--fg-primary)}
.prog{font-weight:700;color:var(--fg-deep)}
.after{background:#F7F3EA;border:1px solid var(--fg-line);border-radius:12px;padding:16px 18px;margin:12px 0}
.btns{display:flex;gap:10px;margin:18px 0}
.btns button,.btns a{flex:1;display:block;padding:13px;min-height:44px;border-radius:10px;border:2px solid var(--fg-primary);background:#fff;color:var(--fg-primary);font-size:.95rem;font-weight:700;cursor:pointer;text-align:center;text-decoration:none}
.btns .primary{background:var(--fg-primary);color:#fff}
.linebtn{display:block;max-width:440px;margin:8px auto 0;padding:14px 22px;min-height:44px;background:var(--fg-cta);color:#fff;text-align:center;text-decoration:none;border-radius:999px;font-weight:700;box-shadow:var(--fg-shadow)}
.smartbox{background:#EAF5F0;border:1px solid #B7E0CF;border-radius:12px;padding:14px 16px;margin:10px 0;color:#0F5138}
.smartbox strong{color:#0F5138}
.copybtn{display:inline-block;padding:10px 16px;min-height:44px;border-radius:10px;border:2px solid var(--fg-deep);background:#fff;color:var(--fg-deep);font:inherit;font-size:.92rem;font-weight:700;cursor:pointer}
.copybtn.copied{background:var(--fg-deep);color:#fff}
details.conbini{background:var(--fg-card);border:1px solid var(--fg-line);border-radius:12px;padding:0;margin:10px 0}
details.conbini summary{cursor:pointer;padding:13px 16px;font-weight:700;color:var(--fg-ink);list-style-position:inside}
details.conbini .inner{padding:0 16px 14px;border-top:1px dashed var(--fg-line)}
details.conbini ol{margin:10px 0 6px;padding-left:1.4em}
details.conbini li{margin:8px 0}
@media(min-width:900px){.wrap{max-width:820px}}
/* 印刷=電話台本+持ち物+窓口ひとこと+メモの1枚に圧縮。工程表・申請後・LINEは画面のみ。 */
@media print{.btns,.no-print,.screen-only,.siteheader{display:none!important}body{background:#fff;font-size:14px}.wrap{padding:0}.box,.phone{break-inside:avoid}
  a[href^="http"]::after{content:" (" attr(href) ")";font-size:.8em;word-break:break-all}
  .memo{min-height:56px;resize:none}}
"""

HEADER = '''<header class="siteheader">
  <a class="hlogo" href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/"><img src="https://allgroup-inc.github.io/hojo-hq/fukugiiro/assets/icon.svg" alt="" width="30" height="30">もらいわすれ堂</a>
  <nav>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/shindan/">3分診断</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/area/">市町村</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/kit/">準備シート</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/go/fg-kit/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack('line_add_click')">LINE登録</a>
    <a class="ignav" href="https://www.instagram.com/moradou.okinawa/" target="_blank" rel="noopener" aria-label="Instagram(新しいタブで開きます)" onclick="if(window.fgTrack)fgTrack('ig_click',{pos:'header'})"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="2.5" y="2.5" width="19" height="19" rx="5.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="17.3" cy="6.7" r="1.3" fill="currentColor" stroke="none"/></svg></a>
  </nav>
</header>'''


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
        "url": it.get("source_url", ""),
        "serviceUrl": it.get("source_url", ""),
    }
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
  var steps = Array.prototype.slice.call(document.querySelectorAll("ol.track input[type=checkbox]"));
  var memos = Array.prototype.slice.call(document.querySelectorAll("textarea.memo"));
  var prog = document.getElementById("prog");
  var stepProg = document.getElementById("stepprog");
  var stepFill = document.getElementById("stepfill");
  var trackedCheck = false, trackedStep = false;
  function save(){
    var data = {c: [], m: {}, s: []};
    boxes.forEach(function(b, i){ if (b.checked) data.c.push(i); });
    steps.forEach(function(b, i){ if (b.checked) data.s.push(i); });
    memos.forEach(function(t, i){ if (t.value) data.m[i] = t.value.slice(0, 500); });
    try { localStorage.setItem(KEY, JSON.stringify(data)); } catch(e){}
  }
  function updItems(){
    var n = boxes.filter(function(b){ return b.checked; }).length;
    if (prog) prog.textContent = "そろったもの: " + n + " / " + boxes.length + (n === boxes.length && n > 0 ? " — 準備かんりょう!" : "");
  }
  function updSteps(){
    var n = steps.filter(function(b){ return b.checked; }).length;
    if (stepProg) stepProg.textContent = n + " / " + steps.length + (n === steps.length && n > 0 ? " ステップ完了 — おつかれさまでした!" : " ステップ完了");
    if (stepFill) stepFill.style.width = (steps.length ? Math.round(n/steps.length*100) : 0) + "%";
  }
  boxes.forEach(function(b, i){
    if (saved.c.indexOf(i) >= 0) b.checked = true;
    b.addEventListener("change", function(){
      save(); updItems();
      if (!trackedCheck && window.fgTrack) { trackedCheck = true; fgTrack("kit_check"); }
    });
  });
  steps.forEach(function(b, i){
    if (saved.s.indexOf(i) >= 0) b.checked = true;
    b.addEventListener("change", function(){
      save(); updSteps();
      if (!trackedStep && window.fgTrack) { trackedStep = true; fgTrack("kit_step"); }
    });
  });
  memos.forEach(function(t, i){
    if (saved.m[i]) t.value = saved.m[i];
    t.addEventListener("input", save);
  });
  updItems(); updSteps();
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
        warn = ('<div class="box" style="border-color:#E0B54A;background:#FFF8E6"><span class="note">'
                'この制度は内容の最終確認中です。金額・締切・対象はお出かけ前に必ず公式ページと窓口でご確認ください。</span></div>')

    # 併給・重複の注意(あれば)
    combine_html = ""
    cmb = it.get("combine") or {}
    if cmb.get("note"):
        ctype = cmb.get("type", "exclusive")
        clabel = {"exclusive": "どちらか一方", "adjust": "併用に条件あり",
                  "stackable": "一緒に受けられる"}.get(ctype, "併用に注意")
        colors = {"exclusive": ("#FBEEE6", "#E8C4AE", "#B9502F"),
                  "adjust": ("#FFF6DB", "#EAD59A", "#7a5b00"),
                  "stackable": ("#E7F4EC", "#B7E0CF", "#0F5138")}
        bg, bd, lc = colors.get(ctype, colors["exclusive"])
        combine_html = (f'<div class="box" style="background:{bg};border-color:{bd}"><p>'
                        f'<span style="display:inline-block;font-weight:800;color:#fff;background:{lc};'
                        f'border-radius:4px;padding:1px 8px;margin-right:6px;font-size:.85rem">{clabel}</span>'
                        f'{esc(cmb["note"])}</p></div>')

    src = esc(it["source_url"])
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
<h1>{name} 申請準備シート{badge}</h1>
<p class="note">「どこに・何を持って・何と言えばいいか」を、この<span style="white-space:nowrap">1枚</span>にまとめました。<br>書くのはご本人ですが、迷わないところまでは、ぜんぶここで終わらせましょう。</p>
{warn}

<div class="goal">
  <p><strong>受け取れるかもしれない方</strong><br>{esc(it['target_household'])}</p>
  <p><strong>金額の目安</strong><br>{esc(it['amount_note'])}</p>
  <p><strong>行き先(窓口)</strong><br>{esc(it['how_to_apply'])}</p>
</div>
{combine_html}

<div class="btns">
  <button class="primary" onclick="if(window.fgTrack)fgTrack('kit_print');window.print()">印刷して持っていく</button>
  <a href="{src}" rel="noopener" onclick="if(window.fgTrack)fgTrack('kit_official')">公式ページで最新を確認</a>
</div>

<div class="smartbox screen-only">
  <p><strong>印刷できなくても、大丈夫です。</strong><br>
  このページをスマホで開いたまま、あなたのメモ代わりに窓口で使えます。チェックとメモはこの端末に残ります。</p>
  <p style="margin-top:10px"><button class="copybtn" id="copy-sheet" onclick="fkCopySheet(this)">このシートをコピーして手元に残す</button></p>
  <p class="note" style="color:#0F5138;margin-top:8px">コピーしたら、LINEのメモやトークに貼りつけておくと、電波の弱い窓口でもすぐ開けます。
  <a href="https://allgroup-inc.github.io/hojo-hq/go/fg-kit/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack('line_add_click')" style="color:#0F5138;font-weight:700">もらいわすれ堂のLINE</a>に貼っていただければ、そのまま締切のお知らせも受け取れます(無料)。</p>
</div>

<details class="conbini no-print screen-only" ontoggle="if(this.open&&window.fgTrack)fgTrack('kit_conbini')">
  <summary>プリンターがないとき — コンビニで印刷するかんたん手順</summary>
  <div class="inner">
    <ol>
      <li>上の「印刷して持っていく」を押して、プリンターのかわりに<strong>「PDFとして保存」</strong>を選びます(iPhoneは共有ボタン→「プリント」からでも保存できます)</li>
      <li><strong>セブンイレブン</strong>なら「かんたんnetprint」アプリ(会員登録なしで使えます)、<strong>ファミリーマート・ローソン</strong>なら「ネットワークプリント」アプリに、そのPDFを登録します</li>
      <li>表示された<strong>受付番号</strong>を、お店のコピー機(マルチコピー機)に入力して印刷します。A4白黒で1枚20円前後が目安です(機種や時期で変わることがあります)</li>
    </ol>
    <p class="note">くわしい手順・料金は各サービスの公式ページでご確認ください:
    <a href="https://www.printing.ne.jp/" rel="noopener" target="_blank">netprint(セブンイレブン)</a> ・
    <a href="https://networkprint.ne.jp/" rel="noopener" target="_blank">ネットワークプリント(ファミマ・ローソン)</a></p>
  </div>
</details>

<section class="screen-only">
<h2>申請までの5ステップ</h2>
<p class="note">チェックすると、この端末に残ります。次に開いたとき「どこまで進んだか」がわかります。</p>
<div class="stepbar"><i id="stepfill"></i></div>
<p class="note"><span class="prog" id="stepprog"></span></p>
<div class="box">
  <ol class="track">
    <li><label><input type="checkbox"><span class="n"></span><span>公式ページで「対象」と<span style="white-space:nowrap">「締切」</span>を見る</span></label></li>
    <li><label><input type="checkbox"><span class="n"></span><span>窓口に電話して「私の場合の持ち物」を聞く(下に台本があります)</span></label></li>
    <li><label><input type="checkbox"><span class="n"></span><span>持ち物をそろえる(全部なくても大丈夫)</span></label></li>
    <li><label><input type="checkbox"><span class="n"></span><span>窓口で申請する(会話はこのとおりでOK)</span></label></li>
    <li><label><input type="checkbox"><span class="n"></span><span>結果と振込を確認する(受け取れたらLINEで報告)</span></label></li>
  </ol>
</div>
</section>

<h2>① まず電話(ムダ足をなくす近道)</h2>
<div class="phone">
  <p class="note">行く前にこの3つを聞いておくと、持ち物不足でのやり直しがなくなります。対象になるか自信がなくても、そのまま聞いて大丈夫です。</p>
  <div class="say">「<b>{name}</b>の申請をしたいのですが、3つ教えてください」</div>
  <div class="say">① 受付の<b>時間</b>と、行く<b>場所(窓口)</b>を教えてください</div>
  <div class="say">② <b>私の場合</b>、何を持っていけばいいですか？</div>
  <div class="say">③ <b>申請書</b>はそちらにありますか？ <b>いつまで</b>に出せばいいですか？</div>
  <p class="note" style="margin-top:10px">電話番号は公式ページに載っています → <a href="{src}" rel="noopener">公式ページで電話番号を確認</a></p>
  <p class="note" style="margin-top:6px">聞いた電話番号・受付時間のメモ:</p>
  <textarea class="memo" data-m="0" rows="1" placeholder="例) 〇〇課 098-000-0000 / 平日8:30-17:15"></textarea>
</div>

<h2>② 持ち物チェックリスト</h2>
<p class="note">市町村やご家庭の状況で変わります。「例」としてそろえて、細かい違いは①の電話か窓口で確認すれば大丈夫です。チェックはこの端末にだけ保存されます。</p>
<div class="box">
  <p class="note screen-only"><span class="prog" id="prog"></span></p>
  <div class="items"><h3>ほぼ必ず要るもの</h3>
  <ul class="check">
{chr(10).join(core_html)}
  </ul></div>
  {event_block}
</div>

<h2>③ 窓口での会話(このとおりでOK)</h2>
<div class="madoguchi">
  <p>まず、こう言います:</p>
  <p style="margin:6px 0;font-size:1.02rem" id="mado-say">「<strong>{name}</strong>について教えてください。対象になるか確認したいです」</p>
  <p class="note" style="color:#0F5138">これだけ言えば、あとは職員の方が案内してくれます。言葉で伝えにくいときは、この画面をそのまま見せても大丈夫です。</p>
  <p class="screen-only" style="margin-top:8px"><button class="copybtn" onclick="fkCopySay(this)">このひとことをコピーする</button></p>
  <p style="margin-top:10px">そして、こちらからこの3つを聞いておきます:</p>
  <ul class="ask">
    <li>締切はいつまでですか？</li>
    <li>申請書はこの場で書けますか？ 書き方も教えてください</li>
    <li>振り込まれるのは、いつ頃ですか？</li>
  </ul>
</div>

<h2>④ 窓口で聞いたことメモ</h2>
<div class="box">
  <p class="note">締切(いつまで):</p><textarea class="memo" data-m="1" rows="1"></textarea>
  <p class="note" style="margin-top:10px">足りなかった書類・次にやること:</p><textarea class="memo" data-m="2" rows="1"></textarea>
  <p class="note" style="margin-top:10px">振込は、いつ頃・どう届く:</p><textarea class="memo" data-m="3" rows="1"></textarea>
</div>

<section class="screen-only">
<h2>申請したあと(振込まで見届ける)</h2>
<div class="after">
  <p>申請してからが本番です。振り込まれるまで、いっしょに見届けましょう。</p>
  <p class="note" style="margin-top:6px">・結果の通知や振込の時期は、④のメモで管理できます。<br>・「振り込まれた」まで確認できたら、下から教えてください。次の県民の「もらい忘れ」を防ぐ力になります。</p>
  <a class="linebtn" style="background:var(--fg-primary)" href="../../houkoku/" onclick="if(window.fgTrack)fgTrack('jukyu_report_link_kit')">受け取れたことを報告する(匿名・無料)</a>
</div>
<div class="after" style="background:#EAF7EE;border-color:#B7E4C7;text-align:center;color:#0F5138">
  締切や新しい制度は、LINEでそっとお知らせします(締切の約1か月前から・無料・名前の入力は不要)
  <a class="linebtn" href="https://allgroup-inc.github.io/hojo-hq/go/fg-kit/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack('line_add_click')">LINEで受け取る</a>
</div>
</section>

<div class="after screen-only" style="text-align:center">
  この制度の情報が「古い」「違う」と気づいたら、教えてください。確認して24時間以内の修正を目指します。<br>
  <a href="{report_link}" onclick="if(window.fgTrack)fgTrack('teisei_mail')" style="display:inline-block;margin-top:8px;color:var(--fg-primary);font-weight:700">この制度の情報の間違いを知らせる</a>
</div>
<div class="disclaimer">このシートは公式情報に基づく「準備のご案内」です。持ち物は一般的な例で、市町村により異なります。受給できるかどうかの最終判断は各窓口で行われます。<br>申請書の作成代行・代筆は行っていません(ご本人が記入します)。<br>専門家のサポートが必要な場合は、提携の専門家(社会保険労務士・行政書士など)をご紹介します。<br>最終更新: {esc(updated)} / もらいわすれ堂(運営: 株式会社フクギイロ)/ 出典: <a href="{src}" rel="noopener">公式ページ</a></div>
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


def index_page(items, updated):
    def line(it):
        # 一覧では「照合済み」は✓だけに圧縮(176件の縦の壁と視覚ノイズを減らす・議事_20260817組版)
        if it.get("verified") is True:
            b = ' <span class="status ok" title="公式と照合済み" style="padding:1px 7px">✓</span>'
        elif it.get("status") == "要確認":
            b = ' <span class="status" style="font-size:.72rem;padding:1px 7px">要確認</span>'
        else:
            b = ""
        return (f'<li style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;'
                f'border-bottom:1px dashed var(--fg-line)">'
                f'<a href="{esc(it["id"])}/" style="display:inline-block;padding:9px 0;line-height:1.55">{esc(it["name"])}</a>{b}</li>')
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
            f"<h2 style='font-size:1.1rem;margin-top:20px'>{label}({len(group)}件)</h2>"
            f"<p class='note'>{note}</p>"
            f"<div class='box'><ul style='list-style:none'>{lis}</ul></div>"
        )
    sections_html = "\n".join(sections)
    body = f"""
<h1>申請準備シート一覧</h1>
<p class="note">制度ごとに「どこに・何を持って・何と言えば申請できるか」をまとめた申請準備シートを用意しています。まず電話で聞く3つ・持ち物チェック・窓口での会話・振込確認まで。<strong>スマホで開いたまま窓口で使えます</strong>(印刷して持っていくのもOK。プリンターがない方向けにコンビニ印刷の手順も各シートにあります)。どれが自分に合うかわからないときは、3分診断からどうぞ。</p>
<a class="no-print" href="../shindan/" style="display:block;max-width:420px;margin:16px auto;padding:14px 24px;background:var(--fg-primary);color:#fff;text-align:center;text-decoration:none;border-radius:999px;font-weight:700">3分でもらい忘れ診断をはじめる</a>
{sections_html}
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
