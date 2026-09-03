#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂 山梨版 守り部(マモリさん)自治体サイト自動監査
山梨県+27市町村の公式サイトについて、①ドメイン本人確認(トップページに自治体名が
あるか) ②robots.txt ③利用規約系ページの本文抜粋 を1回で収集する。

- 実行環境: GitHub Actions(yamanashi-audit.yml)。開発サンドボックスは外部接続不可のため。
- これは「機械による事実確認」。掲載可否の最終判定はマモリさん+人間承認が
  docs/守り部審査記録.md で行う(電話確認が要る自治体はそこで確定する)。
- ドメインは 2026-09-03 にウェブ検索で特定(docs/もらいわすれ堂_山梨版_自治体確認リスト参照)。
  検索由来のため、トップページの名称一致チェックで本人確認してから robots/規約を読む。
- 礼儀: 連絡先付きUA・リクエスト間隔1.5秒・1ドメインあたり最大7ページ。
- 部品は沖縄版(audit_sources_fukugiiro.py / audit_terms_fukugiiro.py)を再利用する。
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from audit_sources_fukugiiro import analyze, fetch_robots  # robots解析
from audit_terms_fukugiiro import (COMMON_PATHS, excerpt, fetch,  # 規約収集
                                   find_terms_links, strip_html)

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
OUT_MD = os.path.join(BASE, "docs", "山梨版_自治体サイト監査結果.md")
OUT_JSON = os.path.join(BASE, "data", "fukugiiro", "yamanashi_site_audit.json")

# (自治体名, ドメイン)。2026-09-03 ウェブ検索で特定。地方公共団体コード順。
TARGETS = [
    ("山梨県", "www.pref.yamanashi.jp"),
    ("甲府市", "www.city.kofu.yamanashi.jp"),
    ("富士吉田市", "www.city.fujiyoshida.yamanashi.jp"),
    ("都留市", "www.city.tsuru.yamanashi.jp"),
    ("山梨市", "www.city.yamanashi.yamanashi.jp"),
    ("大月市", "www.city.otsuki.yamanashi.jp"),
    ("韮崎市", "www.city.nirasaki.lg.jp"),
    ("南アルプス市", "www.city.minami-alps.yamanashi.jp"),
    ("北杜市", "www.city.hokuto.yamanashi.jp"),
    ("甲斐市", "www.city.kai.yamanashi.jp"),
    ("笛吹市", "www.city.fuefuki.yamanashi.jp"),
    ("上野原市", "www.city.uenohara.yamanashi.jp"),
    ("甲州市", "www.city.koshu.yamanashi.jp"),
    ("中央市", "www.city.chuo.yamanashi.jp"),
    ("市川三郷町", "www.town.ichikawamisato.yamanashi.jp"),
    ("早川町", "www.town.hayakawa.yamanashi.jp"),
    ("身延町", "www.town.minobu.lg.jp"),
    ("南部町", "www.town.nanbu.yamanashi.jp"),
    ("富士川町", "www.town.fujikawa.yamanashi.jp"),
    ("昭和町", "www.town.showa.yamanashi.jp"),
    ("道志村", "www.vill.doshi.lg.jp"),
    ("西桂町", "www.town.nishikatsura.yamanashi.jp"),
    ("忍野村", "www.vill.oshino.lg.jp"),
    ("山中湖村", "www.vill.yamanakako.lg.jp"),
    ("鳴沢村", "www.vill.narusawa.yamanashi.jp"),
    ("富士河口湖町", "www.town.fujikawaguchiko.lg.jp"),
    ("小菅村", "www.vill.kosuge.yamanashi.jp"),
    ("丹波山村", "www.vill.tabayama.yamanashi.jp"),
]


def fetch_home(domain):
    """トップページを取得(httpsが駄目なら http を1回だけ試す。小菅村など旧構成対策)"""
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}/"
        try:
            return url, fetch(url)
        except Exception as e:
            err = e
    raise err


def main():
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    results = []
    for label, domain in TARGETS:
        entry = {"label": label, "domain": domain, "identity_ok": None,
                 "robots": None, "robots_mark": None, "pages": [], "error": None}
        # ① ドメイン本人確認
        try:
            base_url, home = fetch_home(domain)
            entry["identity_ok"] = label.replace("山梨県", "山梨") in home or label in home
            time.sleep(1.5)
        except Exception as e:
            entry["error"] = f"トップページ取得失敗: {type(e).__name__} — ドメイン再確認が必要"
            results.append(entry)
            print(f"{label} ({domain}): {entry['error']}")
            continue
        # ② robots.txt
        status, text = fetch_robots(domain)
        comment, ok = analyze(status, text, domain, "/")
        entry["robots"] = {"http_status": status, "machine_check": comment,
                           "excerpt": text[:800]}
        entry["robots_mark"] = ok
        time.sleep(1.5)
        # ③ 利用規約系ページ(トップからリンク探索 → 見つからなければ定番パス)
        try:
            links = find_terms_links(home, base_url)
            if not links:
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
                entry["error"] = "規約系ページを発見できず — 電話確認へ"
            queue = list(links[:4])
            seen_urls = set(u for u, _ in queue)
            MAX_PAGES, MAX_SEEN = 5, 8
            while queue and len(entry["pages"]) < MAX_PAGES:
                url, text2 = queue.pop(0)
                try:
                    page = fetch(url)
                    body = strip_html(page)
                    entry["pages"].append({"url": url, "link_text": text2, "excerpt": excerpt(body)})
                    for sub_url, sub_text in find_terms_links(page, url):
                        if sub_url not in seen_urls and len(seen_urls) < MAX_SEEN:
                            seen_urls.add(sub_url)
                            queue.append((sub_url, sub_text))
                except Exception as e:
                    entry["pages"].append({"url": url, "link_text": text2,
                                           "excerpt": f"(取得失敗: {type(e).__name__})"})
                time.sleep(1.5)
        except Exception as e:
            entry["error"] = f"規約探索失敗: {type(e).__name__}"
        results.append(entry)
        print(f"{label}: 本人確認={entry['identity_ok']} robots={entry['robots_mark']} 規約{len(entry['pages'])}ページ / {entry['error'] or 'OK'}")

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"audited_at": now, "results": results}, f, ensure_ascii=False, indent=1)

    marks = {True: "○", False: "×", None: "?"}
    lines = [
        "# 山梨版 自治体サイト自動監査結果(本人確認+robots+利用規約抜粋)",
        "",
        f"最終実行: {now} JST / 実行: GitHub Actions(yamanashi-audit.yml)/ スクリプト: scripts/audit_yamanashi.py",
        "",
        "> これは機械による事実確認。**掲載可否の最終判定はマモリさん+人間承認が docs/守り部審査記録.md で行う。**",
        "> 本人確認×はドメインの再特定が必要(検索で特定したドメインが別サイトの可能性)。",
        "> 規約が見つからない・リンクに事前連絡が要ると書かれている自治体は、電話確認(台本: docs/もらいわすれ堂_山梨版_残り段取り_2026-09-03.md)へ。",
        "",
        "| 自治体 | ドメイン | 本人確認 | robots | 規約ページ | 特記 |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        ident = marks[r["identity_ok"]]
        rb = marks[r["robots_mark"]]
        lines.append(f"| {r['label']} | {r['domain']} | {ident} | {rb} | {len(r['pages'])}件 | {r['error'] or ''} |")
    lines += ["", "## 利用規約系ページの抜粋", ""]
    for r in results:
        lines.append(f"## {r['label']} ({r['domain']})")
        if r["error"]:
            lines.append(f"- ⚠ {r['error']}")
        if r["robots"]:
            lines.append(f"- robots.txt: HTTP {r['robots']['http_status']} — {r['robots']['machine_check']}")
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
