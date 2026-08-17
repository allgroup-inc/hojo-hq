#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sitemap.xml / robots.txt 自動生成(ケンサク/ヒロメ支援・AI-SEO/検索到達)

site/ 配下の公開ページを列挙して site/sitemap.xml を生成する。
- 除外: /go/(LINEリダイレクト), /staff/(内部), /assets/(静的資産)
- lastmod は data/fukugiiro/seido.json の updated_at 日付(データ更新=ページ更新)
- fetch 後に毎回再生成する(掲載制度が増減しても sitemap が追従)

robots.txt は初回のみ生成(存在すれば上書きしない)。/go/・/staff/ を Disallow し、
sitemap の場所を明示する。方針(断定なし・一次ソース)には一切影響しない純メタデータ。
"""
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "..")
SITE = os.path.join(BASE, "site")
DATA = os.path.join(BASE, "data", "fukugiiro", "seido.json")
ORIGIN = "https://allgroup-inc.github.io/hojo-hq"

# 除外するディレクトリ(先頭パス一致)とファイル
EXCLUDE_DIRS = ("go", "staff", "assets")
EXCLUDE_FILES = ("reply.html", "googlef26aa27c645edf08.html")  # 後者=Search Console所有権確認ファイル

# 優先度: パス接頭辞ごとの priority / changefreq
def rank(url_path):
    if url_path == "/":
        return "1.0", "daily"
    if url_path in ("/fukugiiro/", "/fukugiiro/shindan/"):
        return "0.9", "daily"
    if url_path in ("/fukugiiro/area/", "/fukugiiro/kit/", "/fukugiiro/life/"):
        return "0.7", "daily"
    if url_path.startswith("/fukugiiro/area/") or url_path.startswith("/fukugiiro/life/"):
        return "0.6", "weekly"
    if url_path.startswith("/fukugiiro/kit/"):
        return "0.5", "weekly"
    return "0.5", "weekly"


def lastmod():
    try:
        with open(DATA, encoding="utf-8") as f:
            d = json.load(f)
        # "2026-07-27 11:48" or "2026-07-27" → 日付部分のみ
        return (d.get("updated_at", "") or "").split(" ")[0][:10]
    except Exception:
        return ""


def collect_urls():
    urls = []
    for root, dirs, files in os.walk(SITE):
        rel_root = os.path.relpath(root, SITE)
        top = rel_root.split(os.sep)[0] if rel_root != "." else ""
        if top in EXCLUDE_DIRS:
            dirs[:] = []
            continue
        for fn in files:
            if not fn.endswith(".html") or fn in EXCLUDE_FILES:
                continue
            fpath = os.path.join(root, fn)
            # noindex ページは sitemap に載せない(クローラへの矛盾シグナルを避ける)
            try:
                with open(fpath, encoding="utf-8") as fh:
                    head = fh.read(4000)
                if 'name="robots"' in head and "noindex" in head:
                    continue
            except Exception:
                pass
            rel = os.path.relpath(fpath, SITE).replace(os.sep, "/")
            # index.html は末尾スラッシュの正規URLに正規化
            if rel == "index.html":
                url_path = "/"
            elif rel.endswith("/index.html"):
                url_path = "/" + rel[: -len("index.html")]
            else:
                url_path = "/" + rel
            urls.append(url_path)
    return sorted(set(urls))


def build_sitemap(urls, mod):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        pr, cf = rank(u)
        loc = ORIGIN + u
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        if mod:
            lines.append(f"    <lastmod>{mod}</lastmod>")
        lines.append(f"    <changefreq>{cf}</changefreq>")
        lines.append(f"    <priority>{pr}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


ROBOTS = f"""User-agent: *
Allow: /
Disallow: /go/
Disallow: /staff/

Sitemap: {ORIGIN}/sitemap.xml
"""


def main():
    urls = collect_urls()
    mod = lastmod()
    with open(os.path.join(SITE, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(build_sitemap(urls, mod))
    robots_path = os.path.join(SITE, "robots.txt")
    if not os.path.exists(robots_path):
        with open(robots_path, "w", encoding="utf-8") as f:
            f.write(ROBOTS)
        robots_note = "robots.txt 生成"
    else:
        robots_note = "robots.txt 既存(据え置き)"
    print(f"生成完了: sitemap.xml {len(urls)}URL / lastmod={mod or '(なし)'} / {robots_note}")


if __name__ == "__main__":
    main()
