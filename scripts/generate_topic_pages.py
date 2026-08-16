#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq 収集部×SNS部 — 目的別ページ生成(pSEO・検索流入の種まき)
議事_20260809: 市町村別はデータ不足で却下、目的別6テーマのMVPを採用。

設計基準(docs/pSEO設計基準_taste-skill.md):
- 固有の数字(件数・上限最大・直近締切)+固有のリード文をページごとに持つ
- データはsubsidies.jsonから毎日再生成(update.yml)。空・少数は正直に表示
- CV単一(LINE登録)・締切/金額は原文値・断定なし・出典リンク必須
- 静的HTML・外部依存なし・既存ブランド(#00335C/#F88800/Noto Sans JP)
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "subsidies.json")
OUT_BASE = os.path.join(BASE, "site", "themes")
SITE = "https://allgroup-inc.github.io/hojo-hq"

# slug: (表示名, 名称マッチ正規表現, 固有リード文)
TOPICS = {
    "setsubi": ("設備投資", r"設備|機械|導入促進|生産性",
                "厨房の入れ替え、加工機の導入、店舗の改装。沖縄の会社が設備にお金を使うとき、"
                "国や県の制度で負担を減らせる場合があります。ここでは設備投資に使える"
                "可能性のある募集中の制度だけを毎日更新で並べています。"),
    "it": ("IT・デジタル化", r"IT|デジタル|DX|システム|情報",
           "予約管理、会計ソフト、ECサイト、AIの導入。人手不足の沖縄でこそ、"
           "ITへの投資は補助の対象になりやすい分野です。IT・デジタル化に使える"
           "可能性のある募集中の制度を毎日更新で並べています。"),
    "shoene": ("省エネ・脱炭素", r"省エネ|脱炭素|エネルギー|太陽光|グリーン|水素|CO2",
               "電気代の高さは沖縄の経営の悩みどころ。空調・冷凍冷蔵の更新や太陽光の導入は、"
               "国の省エネ・脱炭素関連の制度が厚い分野です。募集中の制度を毎日更新で並べています。"),
    "koyou": ("雇用・人材", r"雇用|人材|育成|賃上|労働|研修",
              "採用・定着・賃上げ・社員の学び直し。人に関するお金は助成金の得意分野です。"
              "いま募集中のものを毎日更新で並べています(雇用系は通年型も多く、"
              "掲載が少ない時期もあります)。"),
    "sogyo": ("創業・スタートアップ", r"創業|スタートアップ|起業|新規開業",
              "沖縄で会社をつくる・新しい事業を始めるときに使える可能性のある制度です。"
              "創業系は公募時期が限られるため、掲載が少ない時期は"
              "LINE登録で新しい公募の開始をお待ちください。"),
    "shokei": ("事業承継・M&A", r"承継|Ｍ＆Ａ|M&A|後継",
               "会社を譲る・継ぐ・買う。事業承継には専門家への相談費用なども補助対象になる"
               "制度があります。募集中の制度と、承継のご相談窓口をまとめています。"),
}


def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def yen(v):
    if not v:
        return "要確認"
    if v >= 100_000_000:
        o = f"{v / 100_000_000:.1f}".rstrip("0").rstrip(".")
        return f"{o}億円"
    if v >= 10000:
        return f"{v // 10000:,}万円"
    return f"{v:,}円"


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


CSS = """
:root{--navy:#00335C;--kin:#F88800;--ink:#1c2b36;--paper:#f7f9fb;}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Noto Sans JP','Hiragino Kaku Gothic ProN',Meiryo,sans-serif;
 color:var(--ink);background:var(--paper);line-height:1.9;word-break:auto-phrase;overflow-wrap:break-word;}
header{background:linear-gradient(160deg,#021c30,#00335c);color:#f7f5f1;padding:40px 20px 34px;}
.wrap{max-width:860px;margin:0 auto;padding:0 4px;}
.crumb{font-size:.78rem;opacity:.85;margin-bottom:14px;}
.crumb a{color:#f7f5f1;}
h1{font-size:1.5rem;line-height:1.5;}
.lead-nums{margin-top:14px;display:flex;gap:10px;flex-wrap:wrap;font-size:.85rem;}
.lead-nums span{background:rgba(255,255,255,.12);border-radius:20px;padding:5px 14px;}
.lead-nums b{color:var(--kin);font-size:1.05em;}
main{max-width:860px;margin:0 auto;padding:26px 20px 60px;}
.lead{background:#fff;border-left:4px solid var(--kin);border-radius:10px;padding:18px 20px;font-size:.95rem;}
.card{background:#fff;border:1px solid #e2e9f0;border-radius:12px;padding:16px 18px;margin-top:14px;}
.card h2{font-size:1.02rem;color:var(--navy);line-height:1.6;}
.meta{display:flex;gap:14px;flex-wrap:wrap;font-size:.84rem;color:#5a6b78;margin:8px 0 6px;}
.meta b{color:var(--navy);}
.card a{color:var(--kin);font-weight:700;font-size:.88rem;text-decoration:none;}
.empty{background:#fff;border:1px dashed #c8d4de;border-radius:12px;padding:22px;margin-top:14px;
 font-size:.92rem;color:#5a6b78;}
.cta{margin-top:30px;background:linear-gradient(160deg,#021c30,#00335c);color:#f7f5f1;
 border-radius:14px;padding:26px 22px;text-align:center;}
.cta p{font-size:.95rem;}
.cta a{display:inline-block;margin-top:14px;background:var(--kin);color:#fff;font-weight:800;
 padding:.9em 2.2em;border-radius:40px;text-decoration:none;}
.others{margin-top:34px;font-size:.88rem;}
.others h3{font-size:.95rem;color:var(--navy);margin-bottom:8px;}
.others a{display:inline-block;margin:4px 8px 4px 0;color:var(--navy);background:#fff;
 border:1px solid #e2e9f0;border-radius:20px;padding:6px 14px;text-decoration:none;}
.note{margin-top:26px;font-size:.78rem;color:#7a8b99;}
footer{background:#021c30;color:#b0c4d6;text-align:center;padding:22px;font-size:.8rem;}
footer a{color:#f7f5f1;}
"""


def build_page(slug, title, lead, hits, today, all_slugs):
    n = len(hits)
    # 中小向けレンジ(上限1億円以下)のみで最大額を表示。大型公募の混入で
    # 非現実的な数字を見せない(site/index.htmlのSME_CAPと同じ判断)
    amts = [it["max_amount"] for it in hits
            if it.get("max_amount") and it["max_amount"] <= 100_000_000]
    nearest = min((it["deadline"] for it in hits if parse_date(it.get("deadline"))), default=None)
    nums = [f"<span>募集中 <b>{n}件</b></span>"]
    if amts:
        nums.append(f"<span>上限額の最大 <b>{yen(max(amts))}</b>(1億円以下の制度)</span>")
    if nearest:
        nums.append(f"<span>直近の締切 <b>{nearest}</b></span>")
    upd = today.strftime("%Y-%m-%d")

    cards = []
    for it in hits:
        d = parse_date(it.get("deadline"))
        left = f"(残り{(d - today).days}日)" if d else ""
        cards.append(
            f'<article class="card"><h2>{esc(it["name"])}</h2>'
            f'<div class="meta"><span>締切 <b>{esc(it.get("deadline") or "要確認")}</b>{left}</span>'
            f'<span>上限 <b>{yen(it.get("max_amount"))}</b></span>'
            f'<span>{esc((it.get("issuer") or "実施主体 要確認")[:24])}</span></div>'
            f'<a href="{esc(it["source_url"])}" target="_blank" rel="noopener">公式ページで要件を確認 →</a>'
            f'</article>')
    if not cards:
        cards.append('<div class="empty">いま募集中の該当制度はありません。新しい公募が始まったら、'
                     'LINE登録(無料)でお知らせを受け取れます。</div>')

    others = "".join(
        f'<a href="../{s}/">{TOPICS[s][0]}</a>' for s in all_slugs if s != slug)

    itemlist = json.dumps({
        "@context": "https://schema.org", "@type": "ItemList",
        "name": f"沖縄の会社で使える{title}の補助金・助成金",
        "numberOfItems": n,
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": it["name"], "url": it["source_url"]}
            for i, it in enumerate(hits[:20])],
    }, ensure_ascii=False)
    breadcrumb = json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "沖縄企業のミカタ", "item": SITE + "/"},
            {"@type": "ListItem", "position": 2, "name": f"{title}の補助金", "item": f"{SITE}/themes/{slug}/"}],
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>沖縄の会社で使える{esc(title)}の補助金・助成金【{upd}更新・{n}件】｜沖縄企業のミカタ</title>
<meta name="description" content="沖縄の事業者が{esc(title)}に使える可能性のある補助金・助成金を毎日自動更新。いま募集中の{n}件を締切順に掲載。無料の30秒診断とLINE締切アラートも。">
<link rel="canonical" href="{SITE}/themes/{slug}/">
<script type="application/ld+json">{itemlist}</script>
<script type="application/ld+json">{breadcrumb}</script>
<style>{CSS}</style>
</head>
<body>
<header><div class="wrap">
<p class="crumb"><a href="../../">沖縄企業のミカタ</a> › {esc(title)}の補助金</p>
<h1>沖縄の会社で使える<br>{esc(title)}の補助金・助成金</h1>
<div class="lead-nums">{"".join(nums)}<span>更新 {upd}</span></div>
</div></header>
<main>
<p class="lead">{esc(lead)}</p>
{"".join(cards)}
<div class="cta">
<p>この中に貴社で使えるものがあるかは、条件しだいです。<br>会社名の入力なし・30秒の無料診断でお確かめください。</p>
<a href="../../?utm_source=themes&utm_medium=seo&utm_campaign={slug}#match">30秒診断をやってみる(無料)</a>
</div>
<div class="others"><h3>目的別にさがす</h3>{others}</div>
<p class="note">※締切・金額・要件は必ず各制度の原文(公式ページ)でご確認ください。本ページは公開情報を毎日自動収集して整理したもので、申請の代行は行っていません。</p>
</main>
<footer>運営: 株式会社GLOW ｜ <a href="../../">沖縄企業のミカタ</a> — 補助金・助成金の情報で、沖縄の企業にあかりを。</footer>
</body>
</html>
"""


def main():
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)
    today = datetime.now(JST).date()
    items = [it for it in data.get("items", []) if it.get("status") == "募集中"]
    all_slugs = list(TOPICS.keys())
    os.makedirs(OUT_BASE, exist_ok=True)
    for slug, (title, pat, lead) in TOPICS.items():
        hits = [it for it in items if re.search(pat, it.get("name", ""))]
        hits.sort(key=lambda x: (x.get("deadline") or "9999"))
        html = build_page(slug, title, lead, hits, today, all_slugs)
        d = os.path.join(OUT_BASE, slug)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[ok] themes/{slug}/ {title}: {len(hits)}件")


if __name__ == "__main__":
    main()
