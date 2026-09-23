#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ programmatic SEO 第三弾 — ライフイベント別ページ自動生成(ヒロメ/ケンサク)
data/fukugiiro/seido.json の life_events から「沖縄で◯◯のとき」ページを
site/fukugiiro/life/<slug>/index.html に生成する。fetch後に毎回再生成。

狙い(進捗ループ 2026-08-17): ❶流入の検索受け皿。「沖縄 出産 給付金」
「沖縄 ひとり親 手当」のような "状況×制度" 検索は市町村別(area)では拾えない。
方針は area/kit と同じ: 断定表現なし・一次ソースリンク必須・CVはLINE単一(/go/経由)。
"""
import json
import os
import shutil
import sys
from datetime import timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from fg_seo import HIDDEN_MUNIS, breadcrumb_jsonld, canonical_tag, faq_jsonld, ogp_tags

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "fukugiiro", "seido.json")
OUT_DIR = os.path.join(BASE, "site", "fukugiiro", "life")

# slug / 対象life_events(OR条件) / 見出しの「とき」表現 / 検索者が打つ言葉(title・description用)
EVENTS = [
    ("shussan",  ["妊娠・出産"],           "妊娠・出産のとき",   "出産・妊娠"),
    ("kosodate", ["子育て"],               "子育て中",           "子育て"),
    ("nyugaku",  ["入園・入学"],           "入園・入学のとき",   "入学・就学"),
    ("iryo",     ["病気・けが"],           "病気・けがのとき",   "医療費"),
    ("seikatsu", ["低所得・生活苦"],       "家計が苦しいとき",   "生活支援"),
    ("shitsugyo", ["失業", "就職・転職"],  "失業・転職のとき",   "失業・休業"),
    ("sumai",    ["住宅取得・引越"],       "引っ越し・住まいのこと", "住宅・引っ越し"),
    ("shogai",   ["障がい"],               "障がいのある方・ご家族", "障がい"),
    ("kaigo",    ["介護"],                 "介護がはじまったとき", "介護"),
]

STYLE = """
h1,h2,h3{font-family:"Shippori Mincho","Hiragino Mincho ProN",serif;font-weight:600;word-break:auto-phrase;overflow-wrap:anywhere}
.wrap{max-width:680px;margin:0 auto;padding:28px 20px 64px}
h1{font-size:1.4rem;margin-bottom:8px;line-height:1.5}
.btn{display:block;max-width:440px;margin:20px auto;padding:17px 24px;min-height:44px;background:var(--fg-primary);color:#fff;text-align:center;text-decoration:none;border-radius:999px;font-weight:700;font-size:1.05rem;box-shadow:var(--fg-shadow)}
.btn:active{background:var(--fg-primary-deep)}
.card{background:var(--fg-card);border:1px solid var(--fg-line);border-radius:16px;padding:18px;margin:14px 0;box-shadow:var(--fg-shadow)}
.card h2{font-size:1.05rem;margin-bottom:4px}
.trust{background:#EFF5F0;border:1px solid #D5E5DA;border-radius:12px;padding:12px 14px;font-size:.9rem;color:#1F4534;margin:12px 0}
.windows{display:grid;gap:10px;margin:12px 0}
.wcard{background:var(--fg-card,#fff);border:1px solid var(--fg-line,#EEE1D0);border-radius:12px;padding:12px 14px}
.wcard h3{font-size:.98rem;margin:0 0 6px;display:flex;align-items:baseline;gap:8px;word-break:auto-phrase}
.wcard h3 span{font-size:.78rem;color:var(--fg-muted,#7A6B5D);font-weight:400}
.wcard p{margin:0;font-size:.88rem;line-height:1.7;color:var(--fg-ink,#3B322B)}
.linebtn{display:block;max-width:460px;margin:18px auto;padding:16px 22px;min-height:44px;background:var(--fg-cta);color:#fff;text-align:center;text-decoration:none;border-radius:999px;font-weight:700;box-shadow:var(--fg-shadow)}
.linebtn span{display:block;font-size:.8rem;font-weight:600;opacity:.95;margin-top:2px}
.disclaimer{background:#F6EADB;border-radius:12px;padding:14px;font-size:.85rem;color:var(--fg-muted);margin-top:24px}
ul.seidolist{list-style:none}
ul.seidolist li{margin:0;border-bottom:1px dashed var(--fg-line);break-inside:avoid}
ul.seidolist a{display:block;padding:8px 0}
.card a{display:inline-block;padding:4px 0;white-space:nowrap}
ul.lifelist{list-style:none}
ul.lifelist li{margin-bottom:8px}
ul.lifelist a{display:block;padding:10px 2px;border-bottom:1px dashed var(--fg-line)}
.cardgrid{display:grid;gap:14px}
@media(min-width:900px){.wrap{max-width:900px}.cardgrid{grid-template-columns:1fr 1fr}ul.seidolist{columns:2;column-gap:28px}}
"""

HEADER = '''<header class="siteheader">
  <a class="hlogo" href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/"><img src="https://allgroup-inc.github.io/hojo-hq/fukugiiro/assets/icon.svg" alt="" width="30" height="30">もらいわすれ堂</a>
  <nav>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/shindan/">3分診断</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/area/">市町村</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/kit/">準備シート</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/go/fg-life/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack('line_add_click')">LINE登録</a>
    <a class="ignav" href="https://www.instagram.com/moradou.okinawa/" target="_blank" rel="noopener" aria-label="Instagram(新しいタブで開きます)" onclick="if(window.fgTrack)fgTrack('ig_click',{pos:'header'})"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="2.5" y="2.5" width="19" height="19" rx="5.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="17.3" cy="6.7" r="1.3" fill="currentColor" stroke="none"/></svg></a>
  </nav>
</header>'''


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def life_jsonld(heading, items):
    """CollectionPage + ItemList(GovernmentService)。事実のみ・未確定値は入れない。"""
    elements = []
    for pos, it in enumerate(items, 1):
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
    data = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": f"沖縄で{heading}に使える可能性のある給付金・手当",
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(elements), "itemListElement": elements},
    }
    return ('<script type="application/ld+json">\n'
            + json.dumps(data, ensure_ascii=False) + "\n</script>")


def page(title, desc, body, updated, depth=2, head_extra="", canon_path=None):
    rel = "../" * depth
    if depth == 1:
        footer_links = '<p style="margin-top:16px" class="footlinks"><a href="../index.html">もらいわすれ堂 トップへ</a></p><p style="margin-top:4px"><a class="iglink" href="https://www.instagram.com/moradou.okinawa/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack(\'ig_click\')">Instagramで最新情報を見る ›</a></p>'
    else:
        footer_links = '<p style="margin-top:16px" class="footlinks"><a href="../index.html">ライフイベント一覧へ</a> ・ <a href="../../index.html">もらいわすれ堂 トップへ</a></p><p style="margin-top:4px"><a class="iglink" href="https://www.instagram.com/moradou.okinawa/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack(\'ig_click\')">Instagramで最新情報を見る ›</a></p>'
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


def match(it, events):
    return any(e in (it.get("life_events") or []) for e in events)


# 申請窓口の分類。「同じ窓口で一度に聞けるもの」をまとめるために使う。
# 官公庁のページは自分の窓口のことしか書けないので、横断してまとめられるのは
# こちら側の強み(2026-09-23 議事: 勝てるクエリへの絞り直し)。
# 断定はしない。あくまで登録済みの how_to_apply を束ねているだけ。
WINDOWS = [
    ("ハローワーク", ("ハローワーク", "公共職業安定所")),
    ("加入している健康保険(協会けんぽ・国保など)", ("健康保険", "協会けんぽ", "国民健康保険", "保険者")),
    ("年金事務所・年金機構", ("年金事務所", "年金機構", "国民年金")),
    ("お住まいの市区町村の窓口", ("市区町村", "市役所", "町村役場", "役場", "自治体")),
    ("くらしの相談窓口(自立相談支援機関・パーソナルサポートセンター)",
     ("自立相談", "パーソナルサポート", "生活困窮", "さぽんちゅ", "生活支援", "福祉事務所")),
    ("社会福祉協議会", ("社会福祉協議会", "社協")),
    ("労働基準監督署", ("労働基準監督署", "労働局")),
    ("学校・教育委員会", ("学校", "教育委員会")),
]


def window_of(it):
    """制度の申請窓口を粗く分類する。どれにも当たらなければ None(個別に案内)。"""
    text = f"{it.get('how_to_apply','')} {it.get('issuer','')}"
    for label, keys in WINDOWS:
        if any(k in text for k in keys):
            return label
    return None


def window_section(hits):
    """「どこに行けばいいか」を窓口別にまとめる。

    39件の一覧を渡されても、失業した直後の人は動けない。同じ窓口で一度に聞けるものが
    分かれば、行く回数が減る。離島や、仕事を探しながらの人ほど効く。
    """
    # 制度名を並べるのは全国・県のものだけにする。市町村独自の制度をそのまま並べると、
    # 那覇の人に石垣市の制度が見えてしまい、かえって分かりにくい。
    # 市町村分は「お住まいの市町村にもあります(N市町村)」と件数で示す。
    groups, muni = {}, {}
    for it in hits:
        w = window_of(it)
        if not w:
            continue
        if it["area"] in ("全国", "沖縄県"):
            groups.setdefault(w, []).append(it)
        else:
            muni.setdefault(w, set()).add(it["area"])
    labels = [w for w, _ in WINDOWS if len(groups.get(w, [])) >= 2 or len(muni.get(w, ())) >= 3]
    if not labels:
        return []
    out = ['<h2 style="font-size:1.1rem;margin-top:24px">どこに行けばいいか(窓口別)</h2>',
           '<p class="note">同じ窓口で一度に聞けるものをまとめました。'
           '窓口に行くとき、この見出しごと見せていただいてかまいません。'
           '対象になるかどうかは窓口でご確認ください。</p>',
           '<div class="windows">']
    for label in sorted(labels, key=lambda w: -(len(groups.get(w, [])) + len(muni.get(w, ())))):
        its = groups.get(label, [])
        towns = muni.get(label, set())
        parts = []
        if its:
            names = "、".join(esc(i["name"]) for i in its[:8])
            parts.append(names + (f"ほか{len(its) - 8}件" if len(its) > 8 else ""))
        if towns:
            parts.append(f"このほか、お住まいの市町村にも同じ窓口で扱う制度があります"
                         f"({len(towns)}市町村で確認)")
        cnt = len(its) + (1 if towns else 0)
        out.append(f'<div class="wcard"><h3>{esc(label)}<span>{cnt}件</span></h3>'
                   f"<p>{'。'.join(parts)}</p></div>")
    out.append("</div>")
    return out


def life_page(slug, events, heading, kw, items, updated):
    hits = [it for it in items if match(it, events)]
    national = [it for it in hits if it["area"] == "全国"]
    pref = [it for it in hits if it["area"] == "沖縄県"]
    local = [it for it in hits if it["area"] not in ("全国", "沖縄県")]
    total = len(hits)
    verified_n = sum(1 for it in hits if it.get("verified") is True)
    line_cta = (
        '<a class="linebtn" href="https://allgroup-inc.github.io/hojo-hq/go/fg-life/" '
        'target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack(\'line_add_click\')">'
        f'💬 {esc(kw)}の制度の締切をLINEで受け取る'
        '<span>締切の約1か月前にお知らせ・新しい制度が増えたときも(無料)</span></a>'
    )
    examples = [it["name"] for it in (national + pref)][:3]
    ex_txt = "・".join(esc(x) for x in examples)
    body = [
        f"<h1>沖縄で{esc(heading)}に使える可能性のある給付金・手当({total}件)</h1>",
        f'<p class="note">国の制度{len(national)}件・沖縄県{len(pref)}件・市町村{len(local)}件から、'
        f'{esc(heading)}のご家庭にかかわるものをまとめています。お住まいの市町村や世帯の状況によって'
        '対象は変わるため、3分診断でしぼり込むのが近道です。</p>',
    ]
    if verified_n:
        body.append(
            f'<div class="trust">✓ このうち <strong>{verified_n}件</strong> は、'
            '国・県・市町村の公式ページと照合して掲載しています(確認済み)。'
            '金額など一部「要確認」の項目は、公式ページのリンクからご確認いただけます。</div>'
        )
    body.append('<a class="btn" href="../../shindan/">3分でもらい忘れ診断をはじめる</a>')
    # 一覧の前に「どこに行けばいいか」。件数の多い一覧をいきなり見せても人は動けない
    body += window_section(hits)
    # 国・県=カード(このページの主コンテンツ)
    for label, group in ((f"国の制度({len(national)}件)", national), (f"沖縄県の制度({len(pref)}件)", pref)):
        if not group:
            continue
        body.append(f"<h2 style='font-size:1.1rem;margin-top:20px'>{esc(label)}</h2>")
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
                # 窓口行は載せない(準備シート側に地図・電話つきの窓口情報あり。
                # 2026-09-08 掲載97件でサイズ予算超過したため一覧は対象+リンクに絞る)
                f'<p style="display:flex;gap:16px;flex-wrap:wrap;margin:0">'
                f'<a href="{esc(it["source_url"])}" rel="noopener">公式ページで確認する</a>'
                f'<a href="../../kit/{esc(it["id"])}/">申請準備シート</a></p>'
                "</div>"
            )
        body.append('</div>')
    # 市町村独自の制度=市町村名つきリンクリスト(市町村ページ・準備シートに詳細を集約)
    if local:
        body.append(f"<h2 style='font-size:1.1rem;margin-top:20px'>市町村の制度({len(local)}件)</h2>")
        body.append('<p class="note">お住まいの市町村のものだけが対象です。'
                    '<a href="../../area/">市町村別まとめ</a>からも確認できます。</p>')
        body.append('<ul class="seidolist">')
        for it in local:
            mark = "✓ " if it.get("verified") is True else ""
            body.append(f'<li><a href="../../kit/{esc(it["id"])}/">{mark}{esc(it["area"])}: {esc(it["name"])}</a></li>')
        body.append('</ul>')
    body.append(
        f'<p class="note" style="margin-top:22px;text-align:center">'
        f'{esc(kw)}の新しい制度が増えたときや、締切が近づいたときに、LINEでそっとお知らせします。</p>'
    )
    body.append(line_cta)
    # 受け取ったあとの報告導線。単一CV(LINE登録)と競合させないため、
    # ボタンではなく控えめな一文にする(絶対ルール4)。
    body.append(
        '<p class="note" style="margin-top:18px;text-align:center">'
        'もう受け取れた制度はありますか? '
        '<a href="../../houkoku/" onclick="if(window.fgTrack)'
        "fgTrack('jukyu_report_link_life')\">"
        '受け取れたことを教えてください(匿名・任意)</a><br>'
        '制度名とおおよその金額だけで大丈夫です。お名前や口座番号はうかがいません。</p>'
    )
    title = f"沖縄の{kw}の給付金・手当まとめ({total}件)|{heading}|もらいわすれ堂"
    desc = (f"沖縄で{heading}に使える可能性のある給付金・手当{total}件のまとめ。"
            + (f"{ex_txt}など、" if ex_txt else "")
            + "国・沖縄県・市町村の制度を公式ページと照合して掲載。無料・匿名の3分診断つき。")
    faq = faq_jsonld([
        (f"沖縄で{heading}にもらえる給付金にはどんなものがありますか?",
         f"国の制度{len(national)}件・沖縄県{len(pref)}件・市町村{len(local)}件の計{total}件を掲載しています。"
         "お住まいの市町村や世帯の状況で対象は変わるため、各制度の公式ページと3分診断でご確認ください。"),
        ("申請はどこでできますか?",
         "多くはお住まいの市町村の窓口や、加入している健康保険・ハローワークなどです。"
         "各制度の「申請準備シート」に持ち物と窓口でのひとことをまとめています(申請代行は行っていません)。"),
    ])
    ld = life_jsonld(heading, national + pref)
    crumbs = breadcrumb_jsonld([("もらいわすれ堂", ""), ("ライフイベント別まとめ", "life/"), (heading, None)])
    return page(title, desc, "\n".join(body), updated, head_extra=faq + "\n" + ld + "\n" + crumbs,
                canon_path=f"life/{slug}/")


def index_page(items, updated):
    lis = []
    for slug, events, heading, kw in EVENTS:
        n = sum(1 for it in items if match(it, events))
        lis.append(f'<li><a href="{slug}/">{esc(heading)}({n}件)</a></li>')
    body = (
        "<h1>ライフイベント別 給付金・手当まとめ</h1>"
        '<p class="note">いまのご家庭の状況に近いものを選んでください。'
        '<a href="../area/">市町村別まとめ</a>からも探せます。</p>'
        f'<ul class="lifelist">{"".join(lis)}</ul>'
        '<a class="btn" href="../shindan/">3分でもらい忘れ診断をはじめる</a>'
    )
    return page(
        "沖縄の給付金・手当をライフイベント別に探す|もらいわすれ堂",
        "出産・子育て・入学・医療費・生活支援・失業・引っ越し・障がい・介護 — いまの状況から、沖縄で使える可能性のある給付金・手当を探せます。公式ページと照合して掲載。無料・匿名の3分診断つき。",
        body, updated, depth=1,
        head_extra=breadcrumb_jsonld([("もらいわすれ堂", ""), ("ライフイベント別まとめ", None)]),
        canon_path="life/")


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
    for slug, events, heading, kw in EVENTS:
        d = os.path.join(OUT_DIR, slug)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(life_page(slug, events, heading, kw, items, updated))
    print(f"生成完了: ライフイベント{len(EVENTS)}ページ+一覧1ページ(制度{len(items)}件から)")


if __name__ == "__main__":
    main()
