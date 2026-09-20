#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ 検証部(ケンショウ)突合支援 — 一次ソース照合レポート
seido.json の各制度について公式ページを取得し、掲載内容(制度名)がページ上に
実在するかを機械照合して docs/フクギイロ_突合レポート.md に出力する。

- これは「機械にできる範囲の突合」。verified=true への昇格は、このレポートを
  ケンショウ+人間(金曜承認バッチ)が確認した上で行う(L2)
- 実行環境: GitHub Actions(fukugiiro-fetch.yml 内)/ 礼儀ルールは収集と同じ
"""
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
UA = "hojo-hq-bot/1.0 (+https://allgroup-inc.github.io/hojo-hq; contact: bot@en-life.co.jp)"
BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "fukugiiro", "seido.json")
OUT = os.path.join(BASE, "docs", "フクギイロ_突合レポート.md")
SUMMARY = os.path.join(BASE, "data", "fukugiiro", "kensho_summary.json")


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as res:
        raw = res.read(500000)
    for enc in ("utf-8", "shift_jis", "cp932"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def page_title(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def name_tokens(name):
    """制度名から照合用の主要トークンを取る(括弧・記号を除去して分割)"""
    base = re.sub(r"[((].*?[))]", "", name)
    return [t for t in re.split(r"[・\s/]+", base) if len(t) >= 2]


def main():
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    with open(DATA, encoding="utf-8") as f:
        db = json.load(f)

    lines = [
        "# フクギイロ 一次ソース突合レポート(機械照合)",
        "",
        f"最終実行: {now} JST / スクリプト: scripts/kensho_fukugiiro.py",
        "",
        "> ○=制度名がページ上で確認できた / △=一部トークンのみ一致 / ×=確認できず(URL先の内容が変わった可能性 — 最優先で人間確認)",
        "> **verified=true への昇格は、本レポートをケンショウ+金曜承認バッチで確認してから行う(L2)。機械照合だけで昇格しない。**",
        "",
        "| 制度 | ページタイトル | 照合 | 現status |",
        "|---|---|---|---|",
    ]
    ng = 0
    rows = []
    for it in db.get("items", []):
        url = it["source_url"]
        try:
            html = fetch_text(url)
            title = page_title(html)
            text = re.sub(r"<[^>]+>", " ", html)
            # 総合案内ページ等、制度名がページ文言と一致しない項目は match_tokens で照合語を指定できる
            tokens = it.get("match_tokens") or name_tokens(it["name"])
            hit = sum(1 for t in tokens if t in text)
            if hit == len(tokens) and tokens:
                mark = "○"
            elif hit > 0:
                mark = "△"
            else:
                mark, ng = "×", ng + 1
        except Exception as e:
            title, mark = f"(取得失敗: {type(e).__name__})", "×"
            ng += 1
        rows.append({"name": it["name"], "url": url, "title": title[:60],
                     "mark": mark, "status": it["status"], "area": it.get("area", "")})
        lines.append(f"| {it['name']} | {title[:60]} | {mark} | {it['status']} |")
        print(f"{mark} {it['name']}")
        time.sleep(1.5)

    lines += ["", f"×の件数: {ng}(×が出た制度は掲載を「要確認」のまま維持し、人間確認を最優先する)"]

    # 「検証済み」表示なのに原文で確認できない = 絶対ルール1(断定しない)に触れる状態。
    # 従来は260行の表に埋もれて気づけなかったため、最上部に独立した要対応欄として出す。
    risky = [r for r in rows if r["status"] == "検証済み" and r["mark"] in ("×", "△")]
    head = [
        f"## ⚠ 要対応: 「検証済み」表示なのに原文で確認できない {len(risky)}件",
        "",
        "掲載は検証済みと表示しているが、機械照合では原文を確認できていない。"
        "**絶対ルール1(不明なら要確認・断定しない)に触れる状態**のため、"
        "原文URLの差し替えか、status を要確認へ戻すかを人間が判断する。",
        "",
    ]
    if risky:
        head += ["| 制度 | 地域 | 照合 | ページタイトル | 原文URL |", "|---|---|---|---|---|"]
        head += [f"| {r['name']} | {r['area']} | {r['mark']} | {r['title']} | {r['url']} |"
                 for r in risky]
    else:
        head.append("(該当なし)")
    head.append("")
    lines[7:7] = head  # 凡例の直後、全件表の前に差し込む

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    summary = {"updated_at": now, "total": len(rows), "ng": ng,
               "verified_but_unconfirmed": len(risky),
               "items": [{k: r[k] for k in ("name", "area", "mark", "url")} for r in risky]}
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"レポート出力: {OUT} / × {ng}件 / 検証済みなのに未確認 {len(risky)}件")
    if risky:
        print("[warn] 検証済み表示のまま原文を確認できない制度があります(要対応欄を参照)")


if __name__ == "__main__":
    main()
