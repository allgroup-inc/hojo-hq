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
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "fukugiiro", "seido.json")
OUT_DIR = os.path.join(BASE, "site", "fukugiiro", "area")

MUNIS = [
    ("那覇市", "naha"), ("宜野湾市", "ginowan"), ("石垣市", "ishigaki"), ("浦添市", "urasoe"),
    ("名護市", "nago"), ("糸満市", "itoman"), ("沖縄市", "okinawa"), ("豊見城市", "tomigusuku"),
    ("うるま市", "uruma"), ("宮古島市", "miyakojima"), ("南城市", "nanjo"), ("国頭村", "kunigami"),
    ("大宜味村", "ogimi"), ("東村", "higashi"), ("今帰仁村", "nakijin"), ("本部町", "motobu"),
    ("恩納村", "onna"), ("宜野座村", "ginoza"), ("金武町", "kin"), ("伊江村", "ie"),
    ("読谷村", "yomitan"), ("嘉手納町", "kadena"), ("北谷町", "chatan"), ("北中城村", "kitanakagusuku"),
    ("中城村", "nakagusuku"), ("西原町", "nishihara"), ("与那原町", "yonabaru"), ("南風原町", "haebaru"),
    ("渡嘉敷村", "tokashiki"), ("座間味村", "zamami"), ("粟国村", "aguni"), ("渡名喜村", "tonaki"),
    ("南大東村", "minamidaito"), ("北大東村", "kitadaito"), ("伊平屋村", "iheya"), ("伊是名村", "izena"),
    ("久米島町", "kumejima"), ("八重瀬町", "yaese"), ("多良間村", "tarama"), ("竹富町", "taketomi"),
    ("与那国町", "yonaguni"),
]

STYLE = """
:root{--fg-primary:#B9502F;--fg-accent:#F2B705;--fg-deep:#1A6B52;--fg-ink:#1F2A2E;--fg-bg:#FFFBF4;--fg-card:#fff;--fg-muted:#5C6B70;--fg-line:#EBE2D4}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;font-size:18px;line-height:1.8;color:var(--fg-ink);background:var(--fg-bg)}
.wrap{max-width:680px;margin:0 auto;padding:28px 20px 64px}
h1{font-size:1.35rem;margin-bottom:8px}
.note{font-size:.85rem;color:var(--fg-muted)}
.btn{display:block;max-width:420px;margin:20px auto;padding:16px 24px;min-height:44px;background:var(--fg-primary);color:#fff;text-align:center;text-decoration:none;border-radius:999px;font-weight:700}
.card{background:var(--fg-card);border:1px solid var(--fg-line);border-radius:12px;padding:18px;margin:14px 0}
.card h2{font-size:1.05rem;margin-bottom:4px}
.card a{color:var(--fg-primary)}
.status{font-size:.8rem;background:#fff3cd;border-radius:4px;padding:1px 8px;color:#7a5b00}
.disclaimer{background:#f4f1e8;border-radius:10px;padding:14px;font-size:.85rem;color:var(--fg-muted);margin-top:24px}
ul.areas{list-style:none;columns:2;gap:12px}
ul.areas li{margin-bottom:8px}
a{color:var(--fg-primary)}
.siteheader{position:sticky;top:0;z-index:50;background:rgba(255,251,244,.96);border-bottom:1px solid var(--fg-line);display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 14px;flex-wrap:wrap}
.siteheader .hlogo{display:flex;align-items:center;gap:8px;font-weight:800;color:var(--fg-primary);text-decoration:none;font-size:1rem}
.siteheader .hlogo img{width:30px;height:30px}
.siteheader nav{display:flex;gap:4px;align-items:center;flex-wrap:wrap}
.siteheader nav a{font-size:.8rem;color:var(--fg-ink);text-decoration:none;padding:6px 8px;border-radius:6px}
.siteheader nav a.hline{background:#06C755;color:#fff;font-weight:700}
"""

HEADER = '''<header class="siteheader">
  <a class="hlogo" href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/"><img src="https://allgroup-inc.github.io/hojo-hq/fukugiiro/assets/icon.svg" alt="" width="30" height="30">もらいわすれ堂</a>
  <nav>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/shindan/">3分診断</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/area/">市町村</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/kit/">準備シート</a>
    <a class="hline" href="https://lin.ee/7fH7vDQ" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack('line_add_click')">LINE登録</a>
  </nav>
</header>'''


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def page(title, desc, body, updated, depth=2):
    rel = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="icon" type="image/svg+xml" href="{rel}assets/icon.svg">
<style>{STYLE}</style>
</head>
<body>
<script src="{rel}analytics-config.js"></script>
<script src="{rel}assets/fg-analytics.js"></script>
{HEADER}
<div class="wrap">
{body}
<div class="disclaimer">掲載内容は各制度の公式ページと照合していますが、最終的な受給の可否は各窓口の判断となります。「要確認」表示の制度は内容の最終確認中です。金額・要件は必ず公式ページでご確認ください。申請手続きの代行は行っていません。<br>最終更新: {esc(updated)}(毎日自動更新)/ もらいわすれ堂(運営: 株式会社フクギイロ)</div>
<p style="margin-top:16px"><a href="../index.html">市町村一覧へ</a> ・ <a href="../../index.html">もらいわすれ堂 トップ</a></p>
</div>
</body>
</html>
"""


def muni_page(muni, items, updated):
    local = [it for it in items if it["area"] == muni]
    pref = [it for it in items if it["area"] == "沖縄県"]
    national = [it for it in items if it["area"] == "全国"]
    body = [
        f"<h1>{esc(muni)}にお住まいの方が使える可能性のある給付金・手当</h1>",
        f'<p class="note">国・県・{esc(muni)}の制度から、ご家庭向けのものをまとめています。あなたの世帯にあてはまるものは3分診断でしぼり込めます。</p>',
        '<a class="btn" href="../../shindan/">3分でもらい忘れ診断をはじめる</a>',
    ]
    sections = [(f"{muni}の制度", local), ("沖縄県の制度", pref), ("全国(国)の制度", national)]
    for label, group in sections:
        if not group and label.startswith(muni):
            body.append(f"<h2 style='font-size:1.1rem;margin-top:20px'>{esc(label)}</h2>")
            body.append(f'<p class="note">{esc(muni)}独自の制度は現在、掲載準備中です(確認がとれたものから順に追加します)。</p>')
            continue
        if not group:
            continue
        body.append(f"<h2 style='font-size:1.1rem;margin-top:20px'>{esc(label)}({len(group)}件)</h2>")
        for it in group:
            badge = ' <span class="status">要確認</span>' if it.get("status") == "要確認" else ""
            body.append(
                '<div class="card">'
                f"<h2>{esc(it['name'])}{badge}</h2>"
                f'<p class="note">{esc(it["target_household"])}</p>'
                f'<p class="note">窓口: {esc(it["how_to_apply"])}</p>'
                f'<a href="{esc(it["source_url"])}" rel="noopener">公式ページで確認する</a>'
                f' ・ <a href="../../kit/{esc(it["id"])}/">申請準備シート</a>'
                "</div>"
            )
    title = f"{muni}の給付金・手当まとめ | もらいわすれ堂"
    desc = f"{muni}にお住まいの世帯が使える可能性のある給付金・手当のまとめ。3分の無料診断で、あなたの世帯にあてはまる制度がわかります。"
    return page(title, desc, "\n".join(body), updated)


def index_page(updated):
    lis = "\n".join(
        f'<li><a href="{slug}/">{esc(name)}</a></li>' for name, slug in MUNIS
    )
    body = (
        "<h1>市町村別 給付金・手当まとめ</h1>"
        '<p class="note">お住まいの市町村を選んでください。</p>'
        f'<ul class="areas">{lis}</ul>'
        '<a class="btn" href="../shindan/">3分でもらい忘れ診断をはじめる</a>'
    )
    return page("沖縄県 市町村別の給付金・手当まとめ | もらいわすれ堂", "沖縄県41市町村別の給付金・手当まとめ。", body, updated, depth=1)


def main():
    with open(DATA, encoding="utf-8") as f:
        db = json.load(f)
    items = [it for it in db["items"]]
    updated = db.get("updated_at", "")

    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_page(updated))
    for name, slug in MUNIS:
        d = os.path.join(OUT_DIR, slug)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(muni_page(name, items, updated))
    print(f"生成完了: 市町村{len(MUNIS)}ページ+一覧1ページ(制度{len(items)}件から)")


if __name__ == "__main__":
    main()
