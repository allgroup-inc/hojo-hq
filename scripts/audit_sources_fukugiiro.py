#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ 守り部(マモリさん)robots.txt 自動監査
収集対象リスト(docs/フクギイロ_収集対象リスト.md)のドメインについて
robots.txt を取得・解析し、監査レポートを docs/フクギイロ_robots監査結果.md に出力する。

- 実行環境: GitHub Actions(fukugiiro-audit.yml)。開発サンドボックスは外部接続不可のため。
- これは「機械による事実確認」であり、収集可否の最終判定はマモリさん(+人間承認)が
  利用規約審査と合わせて docs/守り部審査記録.md で行う。
- 礼儀: 連絡先付きUA・リクエスト間隔1.5秒・robots.txt のみ取得(コンテンツは取得しない)。
"""
import json
import os
import time
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone, timedelta
from io import StringIO

JST = timezone(timedelta(hours=9))
UA = "hojo-hq-bot/1.0 (+https://allgroup-inc.github.io/hojo-hq; contact: bot@en-life.co.jp)"
BASE = os.path.join(os.path.dirname(__file__), "..")
OUT_MD = os.path.join(BASE, "docs", "フクギイロ_robots監査結果.md")
OUT_JSON = os.path.join(BASE, "data", "fukugiiro", "robots_audit.json")

# (ラベル, ドメイン, 代表パス=収集で使いそうな入口)
TARGETS = [
    ("こども家庭庁", "www.cfa.go.jp", "/policies/"),
    ("厚生労働省", "www.mhlw.go.jp", "/stf/"),
    ("協会けんぽ", "www.kyoukaikenpo.or.jp", "/g3/"),
    ("文部科学省", "www.mext.go.jp", "/a_menu/"),
    ("JASSO", "www.jasso.go.jp", "/shogakukin/"),
    ("国土交通省", "www.mlit.go.jp", "/jutakukentiku/"),
    ("内閣府", "www.cao.go.jp", "/"),
    ("内閣府防災", "www.bousai.go.jp", "/"),
    ("全国社会福祉協議会", "www.shakyo.or.jp", "/"),
    ("那覇市", "www.city.naha.okinawa.jp", "/kurashitetuduki/"),
    ("沖縄市", "www.city.okinawa.okinawa.jp", "/"),
    ("うるま市", "www.city.uruma.lg.jp", "/"),
    ("浦添市", "www.city.urasoe.lg.jp", "/"),
    ("宜野湾市", "www.city.ginowan.lg.jp", "/"),
]


def fetch_robots(domain):
    """robots.txt を取得し (status, text) を返す。失敗時 status は文字列のエラー種別"""
    url = f"https://{domain}/robots.txt"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            body = res.read(65536).decode("utf-8", errors="replace")
            return res.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return f"ERR:{type(e).__name__}", ""


def analyze(status, text, domain, sample_path):
    """robots.txt の内容から機械判定コメントを作る"""
    if status == 404:
        return "robots.txt なし(RFC 9309上、クロール制限の指定なし)", True
    if isinstance(status, str) or status >= 500:
        return f"取得失敗({status})— 再実行または手動確認が必要", None
    if status in (401, 403):
        return f"robots.txt がHTTP {status} — サイト側方針の手動確認が必要", None
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(StringIO(text).readlines())
    allowed_root = rp.can_fetch(UA, f"https://{domain}/")
    allowed_sample = rp.can_fetch(UA, f"https://{domain}{sample_path}")
    if not allowed_root and not allowed_sample:
        return "全面 Disallow の可能性 — 自動収集は不可(手動運用へ)", False
    if not allowed_sample:
        return f"代表パス {sample_path} が Disallow — パス個別の確認が必要", None
    return f"代表パス {sample_path} は許可範囲", True


def main():
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    results = []
    for label, domain, sample in TARGETS:
        status, text = fetch_robots(domain)
        comment, ok = analyze(status, text, domain, sample)
        results.append({
            "label": label, "domain": domain, "sample_path": sample,
            "http_status": status, "machine_check": comment, "fetch_ok": ok,
            "robots_excerpt": text[:800],
        })
        print(f"{label} ({domain}): HTTP {status} — {comment}")
        time.sleep(1.5)

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"audited_at": now, "results": results}, f, ensure_ascii=False, indent=1)

    lines = [
        "# フクギイロ robots.txt 自動監査結果",
        "",
        f"最終実行: {now} JST / 実行: GitHub Actions(fukugiiro-audit.yml)/ スクリプト: scripts/audit_sources_fukugiiro.py",
        "",
        "> これは機械による事実確認。**収集可否の最終判定は、利用規約審査と合わせて守り部が docs/守り部審査記録.md で行う。**",
        "> ○=代表パス許可 / ×=不可(手動運用へ) / ?=手動確認要",
        "",
        "| ソース | ドメイン | HTTP | 機械判定 | 印 |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        mark = {True: "○", False: "×", None: "?"}[r["fetch_ok"]]
        lines.append(f"| {r['label']} | {r['domain']} | {r['http_status']} | {r['machine_check']} | {mark} |")
    lines += [
        "",
        "## robots.txt 抜粋(先頭800字)",
        "",
    ]
    for r in results:
        lines.append(f"### {r['label']} ({r['domain']})")
        lines.append("```")
        lines.append(r["robots_excerpt"] or "(空/取得なし)")
        lines.append("```")
        lines.append("")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"レポート出力: {OUT_MD}")


if __name__ == "__main__":
    main()
