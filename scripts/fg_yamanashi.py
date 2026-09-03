#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂 山梨版 SEOメタ共通モジュール(fg_seo.py の山梨版)

canonical / OGP / BreadcrumbList / FAQPage を山梨版ジェネレーターへ供給する。
沖縄版(fg_seo.py)とは URL基底と市町村マスタだけが違う。
山梨版が独自ドメインへ移行するときは SITE_BASE を1箇所書き換えるだけでよい。
"""
import json

# ★山梨版のURL基底(独自ドメイン移行時はここだけ変更)
SITE_BASE = "https://allgroup-inc.github.io/hojo-hq/fukugiiro/yamanashi"

# OGP画像はブランド共通(沖縄版と同じ)
OGP_IMAGE = "https://allgroup-inc.github.io/hojo-hq/fukugiiro/assets/ogp.jpg"

# 山梨県 27市町村マスタ(名前→slug)。全国地方公共団体コード順。
# 「山梨市」は県名と同じため slug を yamanashi-shi にして紛れを防ぐ。
MUNIS = [
    ("甲府市", "kofu"), ("富士吉田市", "fujiyoshida"), ("都留市", "tsuru"),
    ("山梨市", "yamanashi-shi"), ("大月市", "otsuki"), ("韮崎市", "nirasaki"),
    ("南アルプス市", "minami-alps"), ("北杜市", "hokuto"), ("甲斐市", "kai"),
    ("笛吹市", "fuefuki"), ("上野原市", "uenohara"), ("甲州市", "koshu"),
    ("中央市", "chuo"),
    ("市川三郷町", "ichikawamisato"), ("早川町", "hayakawa"), ("身延町", "minobu"),
    ("南部町", "nanbu"), ("富士川町", "fujikawa"), ("昭和町", "showa"),
    ("道志村", "doshi"), ("西桂町", "nishikatsura"), ("忍野村", "oshino"),
    ("山中湖村", "yamanakako"), ("鳴沢村", "narusawa"), ("富士河口湖町", "fujikawaguchiko"),
    ("小菅村", "kosuge"), ("丹波山村", "tabayama"),
]
MUNI_SLUG = dict(MUNIS)
HIDDEN_MUNIS = []
VISIBLE_MUNIS = [(n, s) for n, s in MUNIS if n not in HIDDEN_MUNIS]

# 山梨版LINE(@630pbjqq・2026-09-03開設)。ボタンは /go/ymn-* 経由(lin.ee直貼り禁止)
GO_BASE = "https://allgroup-inc.github.io/hojo-hq/go"

# 全ページ共通ヘッダー(Instagramは準備中のため置かない)
HEADER = f'''<header class="siteheader">
  <a class="hlogo" href="{SITE_BASE}/"><img src="https://allgroup-inc.github.io/hojo-hq/fukugiiro/assets/icon.svg" alt="" width="30" height="30">もらいわすれ堂 <span style="font-size:.78rem;color:var(--fg-muted);font-weight:400">山梨版</span></a>
  <nav>
    <a href="{SITE_BASE}/shindan/">3分診断</a>
    <a href="{SITE_BASE}/area/">市町村</a>
    <a href="{SITE_BASE}/kit/">準備シート</a>
    <a href="{GO_BASE}/ymn-top/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack('ymn_line_add_click')">LINE登録</a>
  </nav>
</header>'''


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
