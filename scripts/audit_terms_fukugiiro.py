#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ 守り部(マモリさん)利用規約 自動監査(第2段)
各収集対象ドメインのトップページから「利用規約/サイトポリシー/著作権/リンク」系ページを探し、
本文抜粋を docs/フクギイロ_利用規約監査結果.md に出力する。

- robots監査(audit_sources_fukugiiro.py)の次段。実行環境は GitHub Actions。
- これは「規約本文をマモリさんの目の前に並べる」ための収集。承認判定は
  マモリさん+人間承認が docs/守り部審査記録.md で行う。
- 礼儀: 連絡先付きUA・リクエスト間隔1.5秒・1ドメインあたり最大4ページ(トップ+規約系3)。
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

JST = timezone(timedelta(hours=9))
UA = "hojo-hq-bot/1.0 (+https://allgroup-inc.github.io/hojo-hq; contact: bot@en-life.co.jp)"
BASE = os.path.join(os.path.dirname(__file__), "..")
OUT_MD = os.path.join(BASE, "docs", "フクギイロ_利用規約監査結果.md")
OUT_JSON = os.path.join(BASE, "data", "fukugiiro", "terms_audit.json")

DOMAINS = [
    ("こども家庭庁", "www.cfa.go.jp"),
    ("厚生労働省", "www.mhlw.go.jp"),
    ("協会けんぽ", "www.kyoukaikenpo.or.jp"),
    ("文部科学省", "www.mext.go.jp"),
    ("JASSO", "www.jasso.go.jp"),
    ("国土交通省", "www.mlit.go.jp"),
    ("内閣府", "www.cao.go.jp"),
    ("内閣府防災", "www.bousai.go.jp"),
    ("全国社会福祉協議会", "www.shakyo.or.jp"),
    ("那覇市", "www.city.naha.okinawa.jp"),
    ("沖縄市", "www.city.okinawa.okinawa.jp"),
    ("うるま市", "www.city.uruma.lg.jp"),
    ("浦添市", "www.city.urasoe.lg.jp"),
    ("宜野湾市", "www.city.ginowan.lg.jp"),
]

# 検索で特定済みの規約ページ(トップからリンク発見できないサイト用の直指定)
EXTRA_PAGES = {
    "www.cfa.go.jp": [
        "https://www.cfa.go.jp/site-policy",
        "https://www.cfa.go.jp/copyright-policy",
    ],
    "www.mext.go.jp": [
        "https://www.mext.go.jp/b_menu/1351168.htm",
        "https://www.mext.go.jp/b_menu/about_link.htm",
    ],
    "www.cao.go.jp": [
        "https://www.cao.go.jp/notice/rule.html",
    ],
}

# リンク未発見サイトで試すよくあるパス(404は無視)
COMMON_PATHS = ["/site-policy", "/sitepolicy.html", "/policy.html", "/riyou.html",
                "/disclaimer.html", "/link.html", "/about/", "/site/rule/"]

# リンクテキスト/URLに含まれていたら規約系とみなすキーワード
LINK_KEYWORDS = ["利用規約", "サイトポリシー", "著作権", "リンクについて", "リンク・著作権",
                 "免責", "このサイトについて", "ご利用に", "ご利用ガイド", "サイトの使い方",
                 "policy", "copyright", "terms", "about_site", "sitepolicy", "site-policy", "riyou"]
# 抜粋時に重要箇所を優先するキーワード
BODY_KEYWORDS = ["著作権", "転載", "引用", "複製", "リンク", "無断", "許可", "承諾", "出典", "免責"]


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []       # (href, text)
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._text).strip()))
            self._href = None
            self._text = []


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as res:
        raw = res.read(500000)
    for enc in ("utf-8", "shift_jis", "euc-jp", "cp932"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def strip_html(html):
    # 本文領域(main/article/#main/#content)があればそこを優先し、ナビ汚染を減らす
    for pat in (r"<main[^>]*>(.*?)</main>", r"<article[^>]*>(.*?)</article>",
                r'<div[^>]+id="(?:main|content|contents)"[^>]*>(.*)'):
        m = re.search(pat, html, flags=re.S | re.I)
        if m:
            html = m.group(1)
            break
    html = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_terms_links(home_html, base_url):
    parser = LinkCollector()
    try:
        parser.feed(home_html)
    except Exception:
        pass
    found, seen = [], set()
    for href, text in parser.links:
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        target = (text or "") + " " + href
        if any(k.lower() in target.lower() for k in LINK_KEYWORDS):
            full = urllib.parse.urljoin(base_url, href)
            if urllib.parse.urlparse(full).netloc != urllib.parse.urlparse(base_url).netloc:
                continue
            if full not in seen:
                seen.add(full)
                found.append((full, text.strip() or href))
    return found[:3]


def excerpt(text, limit=1200):
    """重要キーワード周辺を優先して抜粋"""
    hits = []
    for kw in BODY_KEYWORDS:
        i = text.find(kw)
        if i >= 0:
            hits.append(max(0, i - 60))
    if not hits:
        return text[:limit]
    start = min(hits)
    return text[start:start + limit]


def main():
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    results = []
    for label, domain in DOMAINS:
        entry = {"label": label, "domain": domain, "pages": [], "error": None}
        base_url = f"https://{domain}/"
        try:
            home = fetch(base_url)
            time.sleep(1.5)
            links = find_terms_links(home, base_url)
            for extra in EXTRA_PAGES.get(domain, []):
                if extra not in [u for u, _ in links]:
                    links.append((extra, "検索特定ページ"))
            if not links:
                # よくあるパスを試す(404は無視)
                for path in COMMON_PATHS:
                    if len(links) >= 2:
                        break
                    try:
                        cand = base_url.rstrip("/") + path
                        fetch(cand)
                        links.append((cand, f"候補パス{path}"))
                    except Exception:
                        pass
                    time.sleep(1.5)
            if not links:
                entry["error"] = "規約系ページを発見できず — 手動確認要"
            for url, text in links[:4]:
                try:
                    page = fetch(url)
                    body = strip_html(page)
                    entry["pages"].append({"url": url, "link_text": text, "excerpt": excerpt(body)})
                except Exception as e:
                    entry["pages"].append({"url": url, "link_text": text, "excerpt": f"(取得失敗: {type(e).__name__})"})
                time.sleep(1.5)
        except Exception as e:
            entry["error"] = f"トップページ取得失敗: {type(e).__name__}"
        results.append(entry)
        print(f"{label}: {len(entry['pages'])}ページ / {entry['error'] or 'OK'}")

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"audited_at": now, "results": results}, f, ensure_ascii=False, indent=1)

    lines = [
        "# フクギイロ 利用規約 自動監査結果(規約本文の抜粋収集)",
        "",
        f"最終実行: {now} JST / スクリプト: scripts/audit_terms_fukugiiro.py(GitHub Actions実行)",
        "",
        "> 抜粋は「著作権・転載・リンク」等の重要キーワード周辺を優先。**承認判定はマモリさん+人間承認が守り部審査記録で行う。**",
        "> 判定観点: ①事実+リンクのみの索引掲載が規約に抵触しないか ②リンクポリシー(事前連絡要否) ③その他特記",
        "",
    ]
    for r in results:
        lines.append(f"## {r['label']} ({r['domain']})")
        if r["error"]:
            lines.append(f"- ⚠ {r['error']}")
        for p in r["pages"]:
            lines.append(f"### [{p['link_text']}]({p['url']})")
            lines.append("```")
            lines.append(p["excerpt"])
            lines.append("```")
        lines.append("")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"レポート出力: {OUT_MD}")


if __name__ == "__main__":
    main()
