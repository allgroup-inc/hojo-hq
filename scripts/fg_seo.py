#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂 SEOメタ共通モジュール(2026-08-10 三名体制裁定・第1着手)

canonical / OGP / BreadcrumbList / FAQPage を生成テンプレートへ一元供給する。
独自ドメイン移行が決裁されたら SITE_BASE を1箇所書き換えるだけで
全ページの canonical・OGP・パンくずURLが追従する(ウタガイ条件: URL基底の一元管理)。
"""
import json

# ★独自ドメイン移行時はここだけ変更(例: "https://fukugiiro.com")
SITE_BASE = "https://allgroup-inc.github.io/hojo-hq/fukugiiro"

OGP_IMAGE = f"{SITE_BASE}/assets/ogp.jpg"

# 市町村マスタ(名前→slug)。area/kit両ジェネレータで共有
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
MUNI_SLUG = dict(MUNIS)

# 一時非公開の市町村(2026-08-18 小柳さん指示・クレーム等ではない・後ほど復活予定。
# 議事_20260818_沖縄市うるま市一時非公開.md)。市独自制度の掲載(fetch_fukugiiro)に加え、
# 市町村ページの生成・一覧・診断の選択肢からも除外する。
# 戻すときはこのリストを空にして fukugiiro-fetch を再実行(+診断のMUNIS配列を復元)。
HIDDEN_MUNIS = []  # 2026-08-19 小柳さん最終指示: 沖縄市・うるま市とも公開(一時非公開は全解除)
# 公開対象の市町村(ジェネレーターはこちらを使う)
VISIBLE_MUNIS = [(n, s) for n, s in MUNIS if n not in HIDDEN_MUNIS]


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def canonical_tag(path):
    """path: SITE_BASE からの相対パス(例 "kit/fk-xxx/")。末尾スラッシュ形式で統一。"""
    url = f"{SITE_BASE}/{path}" if path else f"{SITE_BASE}/"
    return f'<link rel="canonical" href="{url}">'


def ogp_tags(title, desc, path, og_type="article"):
    url = f"{SITE_BASE}/{path}" if path else f"{SITE_BASE}/"
    return "\n".join([
        f'<meta property="og:title" content="{_esc(title)}">',
        f'<meta property="og:description" content="{_esc(desc)}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:image" content="{OGP_IMAGE}">',
        '<meta property="og:site_name" content="もらいわすれ堂">',
        '<meta name="twitter:card" content="summary_large_image">',
    ])


def breadcrumb_jsonld(crumbs):
    """crumbs: [(名前, SITE_BASEからの相対パス or None=現在地)] のリスト。"""
    items = []
    for i, (name, path) in enumerate(crumbs, 1):
        item = {"@type": "ListItem", "position": i, "name": name}
        if path is not None:
            item["item"] = f"{SITE_BASE}/{path}" if path else f"{SITE_BASE}/"
        items.append(item)
    data = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}
    return ('<script type="application/ld+json">\n'
            + json.dumps(data, ensure_ascii=False) + "\n</script>")


def faq_jsonld(qa_pairs):
    """qa_pairs: [(質問, 回答プレーンテキスト)]。本文と同一内容のみ渡すこと(正確性最優先)。"""
    data = {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in qa_pairs
        ],
    }
    return ('<script type="application/ld+json">\n'
            + json.dumps(data, ensure_ascii=False) + "\n</script>")
