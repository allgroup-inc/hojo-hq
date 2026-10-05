#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLOW 世界へ推進LP「売り場のイメージ」用に、沖縄の産品の写真候補を Wikimedia Commons から集める。
自由に使える許諾(CC0・パブリックドメイン・CC BY・CC BY-SA)の写真だけを取り、作者と許諾を credits.json に残す。

  python scripts/glow_fetch_photos.py

出力: site/go/plan-a/assets/images/booth/cand/<名前>-<n>.webp と credits.json
候補から使うものを選んだら、LP・資料に作者と許諾を表示する(CC BY / CC BY-SA の条件)。
"""
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "go", "plan-a", "assets", "images", "booth", "cand")
UA = "GLOW-LP-builder/1.0 (https://github.com/allgroup-inc/hojo-hq; info@g-low.co.jp)"
API = "https://commons.wikimedia.org/w/api.php"
PER = 4
OK_LICENSE = re.compile(r"^(cc0|public domain|pd|cc by(-sa)? [0-9.]+)", re.I)

QUERIES = {
    "awamori": ["awamori bottle", "awamori"],
    "kokuto": ["kokuto brown sugar", "Okinawan brown sugar"],
    "shikuwasa": ["shikuwasa", "Citrus depressa fruit"],
    "mozuku": ["mozuku", "Cladosiphon okamuranus food"],
    "umibudo": ["umibudo", "Caulerpa lentillifera food"],
    "beniimo": ["beni imo tart", "purple sweet potato tart Okinawa"],
    "bingata": ["bingata", "Ryukyu bingata textile"],
    "glass": ["Ryukyu glass", "Ryukyu glassware"],
    "hero": ["Okinawa market products", "Makishi public market"],
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def search(q):
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": "6",
        "gsrsearch": f"{q} filetype:bitmap", "gsrlimit": "15",
        "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": "800",
    }
    data = json.loads(get(API + "?" + urllib.parse.urlencode(params)))
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    out = []
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = (meta.get("LicenseShortName", {}).get("value") or "").strip()
        if not OK_LICENSE.match(lic):
            continue
        if ii.get("width", 0) < 500:
            continue
        artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
        out.append({
            "title": p.get("title"), "thumb": ii.get("thumburl"), "page": ii.get("descriptionurl"),
            "license": lic, "license_url": meta.get("LicenseUrl", {}).get("value", ""), "artist": artist[:120],
        })
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    credits = {}
    for name, qs in QUERIES.items():
        seen, n = set(), 0
        for q in qs:
            try:
                results = search(q)
            except Exception as e:
                print(f"[error] {name} '{q}': {e}")
                continue
            for r in results:
                if n >= PER or r["title"] in seen or not r["thumb"]:
                    continue
                seen.add(r["title"])
                try:
                    im = Image.open(io.BytesIO(get(r["thumb"]))).convert("RGB")
                except Exception as e:
                    print(f"[skip] {r['title']}: {e}")
                    continue
                n += 1
                fn = f"{name}-{n}.webp"
                im.thumbnail((800, 800))
                im.save(os.path.join(OUT, fn), "WEBP", quality=80, method=6)
                credits[fn] = r
                print(f"[ok] {fn} {im.size} {r['license']} {r['title']}")
        if n == 0:
            print(f"[none] {name}")
    with open(os.path.join(OUT, "credits.json"), "w", encoding="utf-8") as f:
        json.dump(credits, f, ensure_ascii=False, indent=1)
    print(f"[done] {len(credits)} 枚")
    if not credits:
        sys.exit(1)


if __name__ == "__main__":
    main()
