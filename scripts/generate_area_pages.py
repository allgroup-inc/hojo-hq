#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ programmatic SEO 第一弾 — 41市町村別ページ自動生成(ヒロメ/ケンサク)
data/fukugiiro/seido.json から「◯◯市にお住まいの方が使える可能性のある制度」ページを
site/fukugiiro/area/<slug>/index.html に生成する。fetch後に毎回再生成(データ更新=ページ更新)。

方針:
- 全ページ断定表現なし・一次ソースリンク必須・診断への単一CTA(LP設計と同思想)
- 市町村独自制度は守り部承認後に自動で混ざる(area==市町村名のデータが入れば表示される)
- 検査は check_lp_fukugiiro.py が site/fukugiiro 配下の全HTMLを走査
"""
import json
import os
import shutil
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from fg_seo import HIDDEN_MUNIS, MUNI_SLUG, VISIBLE_MUNIS, breadcrumb_jsonld, canonical_tag, ogp_tags

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "fukugiiro", "seido.json")
OUT_DIR = os.path.join(BASE, "site", "fukugiiro", "area")

STYLE = """
h1,h2,h3{font-family:"Shippori Mincho","Hiragino Mincho ProN",serif;font-weight:600;word-break:auto-phrase;overflow-wrap:anywhere}
.wrap{max-width:680px;margin:0 auto;padding:28px 20px 64px}
h1{font-size:1.4rem;margin-bottom:8px;line-height:1.5}
.btn{display:block;max-width:440px;margin:20px auto;padding:17px 24px;min-height:44px;background:var(--fg-primary);color:#fff;text-align:center;text-decoration:none;border-radius:999px;font-weight:700;font-size:1.05rem;box-shadow:var(--fg-shadow)}
.btn:active{background:var(--fg-primary-deep)}
.card{background:var(--fg-card);border:1px solid var(--fg-line);border-radius:16px;padding:18px;margin:14px 0;box-shadow:var(--fg-shadow)}
.card h2{font-size:1.05rem;margin-bottom:4px}
.card .trust{background:#EFF5F0;border:1px solid #D5E5DA;border-radius:12px;padding:12px 14px;font-size:.9rem;color:#1F4534;margin:12px 0}
.linebtn{display:block;max-width:460px;margin:18px auto;padding:16px 22px;min-height:44px;background:var(--fg-cta);color:#fff;text-align:center;text-decoration:none;border-radius:999px;font-weight:700;box-shadow:var(--fg-shadow)}
.linebtn span{display:block;font-size:.8rem;font-weight:600;opacity:.95;margin-top:2px}
.disclaimer{background:#F6EADB;border-radius:12px;padding:14px;font-size:.85rem;color:var(--fg-muted);margin-top:24px}
ul.areas{list-style:none;columns:2;gap:12px}
ul.areas li{margin-bottom:8px}
ul.seidolist{list-style:none;columns:1}
ul.seidolist li{margin:0;border-bottom:1px dashed var(--fg-line);break-inside:avoid}
ul.seidolist a{display:block;padding:8px 0}
ul.areas a{display:inline-block;padding:8px 4px}
.card a{display:inline-block;padding:4px 0;white-space:nowrap}
@media(min-width:900px){ul.seidolist{columns:2;column-gap:28px}}
.cardgrid{display:grid;gap:14px}
@media(min-width:900px){.wrap{max-width:900px}.cardgrid{grid-template-columns:1fr 1fr}ul.areas{columns:3}}
"""

HEADER = '''<header class="siteheader">
  <a class="hlogo" href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/"><img src="https://allgroup-inc.github.io/hojo-hq/fukugiiro/assets/icon.svg" alt="" width="30" height="30">もらいわすれ堂</a>
  <nav>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/shindan/">3分診断</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/area/">市町村</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/kit/">準備シート</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/go/fg-area/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack('line_add_click')">LINE登録</a>
    <a class="ignav" href="https://www.instagram.com/moradou.okinawa/" target="_blank" rel="noopener" aria-label="Instagram(新しいタブで開きます)" onclick="if(window.fgTrack)fgTrack('ig_click',{pos:'header'})"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="2.5" y="2.5" width="19" height="19" rx="5.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="17.3" cy="6.7" r="1.3" fill="currentColor" stroke="none"/></svg></a>
  </nav>
</header>'''


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def area_jsonld(muni, groups):
    """市町村ページの構造化データ: 掲載制度を CollectionPage + ItemList(GovernmentService)で列挙。
    事実(制度名・提供元・対象地域・公式URL)のみ。金額など未確定値は入れない(正確性最優先)。
    2026-08-10 SEO裁定: ItemListは市町村+県の制度に絞る(全国38件は41ページ共通のため
    重複シグナルを避け、ページ固有性を構造化データ側でも示す)。"""
    elements = []
    pos = 1
    for group in groups:
        for it in group:
            elements.append({
                "@type": "ListItem", "position": pos,
                "item": {
                    "@type": "GovernmentService",
                    "name": it.get("name", ""),
                    "provider": {"@type": "GovernmentOrganization", "name": it.get("issuer", "")},
                    "areaServed": {"@type": "AdministrativeArea", "name": it.get("area", "全国")},
                    "url": it.get("source_url", ""),
                },
            })
            pos += 1
    data = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": f"{muni}にお住まいの方が使える可能性のある給付金・手当",
        "about": {"@type": "AdministrativeArea", "name": muni},
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(elements), "itemListElement": elements},
    }
    return ('<script type="application/ld+json">\n'
            + json.dumps(data, ensure_ascii=False) + "\n</script>")


def page(title, desc, body, updated, depth=2, head_extra="", canon_path=None):
    rel = "../" * depth
    # フッター: depthに応じて正しい相対パスを組む(一覧ページが別ブランドのミカタへ飛ぶバグの修正・2026-08-12)
    if depth == 1:
        footer_links = '<p style="margin-top:16px" class="footlinks"><a href="../index.html">もらいわすれ堂 トップへ</a></p><p style="margin-top:4px"><a class="iglink" href="https://www.instagram.com/moradou.okinawa/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack(\'ig_click\')">Instagramで最新情報を見る ›</a></p>'
    else:
        footer_links = '<p style="margin-top:16px" class="footlinks"><a href="../index.html">市町村一覧へ</a> ・ <a href="../../index.html">もらいわすれ堂 トップへ</a></p><p style="margin-top:4px"><a class="iglink" href="https://www.instagram.com/moradou.okinawa/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack(\'ig_click\')">Instagramで最新情報を見る ›</a></p>'
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
<div class="disclaimer">掲載内容は各制度の公式ページと照合していますが、最終的な受給の可否は各窓口の判断となります。「要確認」表示の制度は内容の最終確認中です。金額・要件は必ず公式ページでご確認ください。申請手続きの代行は行っていません。<br>情報が古い・違うと気づいたら <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/teisei/">こちらから教えてください</a>(24時間以内の修正を目指します)。<br>最終更新: {esc(updated)}(毎日自動更新) / もらいわすれ堂(運営: 株式会社フクギイロ)</div>
{footer_links}
</div>
</body>
</html>
"""


def muni_page(muni, items, updated):
    local = [it for it in items if it["area"] == muni]
    pref = [it for it in items if it["area"] == "沖縄県"]
    national = [it for it in items if it["area"] == "全国"]
    shown = local + pref + national
    verified_n = sum(1 for it in shown if it.get("verified") is True)
    # 単一CV(LINE登録)。締切は「約1か月前」表現で統一(3層ルール準拠)。
    line_cta = (
        '<a class="linebtn" href="https://allgroup-inc.github.io/hojo-hq/go/fg-area/" '
        'target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack(\'line_add_click\')">'
        f'💬 {esc(muni)}で使える制度の締切をLINEで受け取る'
        '<span>締切の約1か月前にお知らせ・新しい制度が増えたときも(無料)</span></a>'
    )
    # 導入文を市町村ごとに固有化(掲載件数・代表制度名入り。41ページの文面重複を下げる)
    examples = [it["name"] for it in (local + pref)][:3]
    ex_txt = "・".join(esc(x) for x in examples)
    total = len(shown)
    if local:
        intro = (f'{esc(muni)}の制度{len(local)}件と沖縄県{len(pref)}件・国{len(national)}件をあわせた'
                 f'計{total}件から、ご家庭向けのものをまとめています。')
    else:
        intro = (f'沖縄県の制度{len(pref)}件と国の制度{len(national)}件の計{total}件から、'
                 f'{esc(muni)}にお住まいのご家庭が使える可能性のあるものをまとめています。')
    body = [
        f"<h1>{esc(muni)}にお住まいの方が使える可能性のある給付金・手当</h1>",
        f'<p class="note">{intro}あなたの世帯にあてはまるものは3分診断でしぼり込めます。</p>',
    ]
    if verified_n:
        body.append(
            f'<div class="trust">✓ このうち <strong>{verified_n}件</strong> は、'
            f'{esc(muni)}や国・県の公式ページと照合して掲載しています(確認済み)。'
            '金額の目安など一部「要確認」の項目は、公式ページのリンクからご確認いただけます。</div>'
        )
    body.append('<a class="btn" href="../../shindan/">3分でもらい忘れ診断をはじめる</a>')
    # 市町村・県の制度=カード(このページの固有コンテンツ)
    sections = [(f"{muni}の制度", local), ("沖縄県の制度", pref)]
    for label, group in sections:
        if not group and label.startswith(muni):
            body.append(f"<h2 style='font-size:1.1rem;margin-top:20px'>{esc(label)}</h2>")
            body.append(f'<p class="note">{esc(muni)}独自の制度は現在、掲載準備中です(確認がとれたものから順に追加します)。</p>')
            continue
        if not group:
            continue
        body.append(f"<h2 style='font-size:1.1rem;margin-top:20px'>{esc(label)}({len(group)}件)</h2>")
        body.append('<div class="cardgrid">')
        for it in group:
            if it.get("verified") is True:
                badge = ' <span class="status ok">✓ 公式と照合済み</span>'
            elif it.get("status") == "要確認":
                badge = ' <span class="status">要確認</span>'
            else:
                badge = ""
            body.append(
                '<div class="card">'
                f"<h2>{esc(it['name'])}{badge}</h2>"
                f'<p class="note">{esc(it["target_household"])}</p>'
                f'<p class="note">窓口: {esc(it["how_to_apply"])}</p>'
                f'<p style="display:flex;gap:16px;flex-wrap:wrap;margin:0">'
                f'<a href="{esc(it["source_url"])}" rel="noopener">公式ページで確認する</a>'
                f'<a href="../../kit/{esc(it["id"])}/">申請準備シート</a></p>'
                "</div>"
            )
        body.append('</div>')
    # 全国(国)の制度=リンクリスト(41ページ共通のため全文カードにせず重複率を下げる。
    # 詳細は各申請準備シートに集約 — 2026-08-10 SEO裁定)
    if national:
        body.append(f"<h2 style='font-size:1.1rem;margin-top:20px'>全国(国)の制度({len(national)}件)</h2>")
        body.append(f'<p class="note">国の制度は全国共通です。それぞれの申請準備シートで、{esc(muni)}の窓口に行く前の準備(持ち物・電話で聞くこと)を確認できます。</p>')
        body.append('<ul class="seidolist">')
        for it in national:
            mark = "✓ " if it.get("verified") is True else ""
            body.append(f'<li><a href="../../kit/{esc(it["id"])}/">{mark}{esc(it["name"])}</a></li>')
        body.append('</ul>')
    # ページ末にもLINE誘導(締切の見逃し防止=登録特典)
    body.append(
        f'<p class="note" style="margin-top:22px;text-align:center">'
        f'{esc(muni)}で新しい制度が増えたときや、締切が近づいたときに、LINEでそっとお知らせします。</p>'
    )
    body.append(line_cta)
    title = f"{muni}の給付金・手当まとめ({total}件)|申請方法と窓口|もらいわすれ堂"
    desc = (f"{muni}にお住まいの世帯が使える可能性のある給付金・手当{total}件のまとめ。"
            + (f"{ex_txt}など、" if ex_txt else "")
            + f"国・沖縄県・{muni}の制度を公式ページと照合して掲載。無料・匿名の3分診断つき。")
    slug = MUNI_SLUG[muni]
    ld = area_jsonld(muni, [local, pref])
    crumbs = breadcrumb_jsonld([("もらいわすれ堂", ""), ("市町村別まとめ", "area/"), (muni, None)])
    return page(title, desc, "\n".join(body), updated, head_extra=ld + "\n" + crumbs,
                canon_path=f"area/{slug}/")


def index_page(updated):
    lis = "\n".join(
        f'<li><a href="{slug}/">{esc(name)}</a></li>' for name, slug in VISIBLE_MUNIS
    )
    body = (
        "<h1>市町村別 給付金・手当まとめ</h1>"
        '<p class="note">お住まいの市町村を選んでください。'
        '状況から探したい方は<a href="../life/">ライフイベント別まとめ</a>もどうぞ。</p>'
        f'<ul class="areas">{lis}</ul>'
        '<a class="btn" href="../shindan/">3分でもらい忘れ診断をはじめる</a>'
    )
    return page(
        f"沖縄県 市町村別の給付金・手当まとめ({len(VISIBLE_MUNIS)}市町村)|もらいわすれ堂",
        "那覇市・宜野湾市・浦添市・名護市など沖縄県の市町村ごとに、こども医療費助成・児童手当・ひとり親支援などの給付金・手当をまとめて確認できます。公式ページと照合して掲載。無料・匿名の3分診断つき。",
        body, updated, depth=1,
        head_extra=breadcrumb_jsonld([("もらいわすれ堂", ""), ("市町村別まとめ", None)]),
        canon_path="area/")


def main():
    with open(DATA, encoding="utf-8") as f:
        db = json.load(f)
    items = [it for it in db["items"]]
    items = [it for it in items if it.get("area") not in HIDDEN_MUNIS]  # 一時非公開(議事20260818)
    updated = db.get("updated_at", "")

    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_page(updated))
    for name, slug in VISIBLE_MUNIS:
        d = os.path.join(OUT_DIR, slug)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(muni_page(name, items, updated))
    print(f"生成完了: 市町村{len(VISIBLE_MUNIS)}ページ+一覧1ページ(制度{len(items)}件から)")


if __name__ == "__main__":
    main()
