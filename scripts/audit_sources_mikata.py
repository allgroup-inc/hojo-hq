#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沖縄企業のミカタ 守り部(マモリさん)robots.txt 自動監査
収集対象(scripts/fetch_local.py が実際にクロールしているドメイン)について
robots.txt を取得・解析し、監査レポートを docs/企業のミカタ_robots監査結果.md に出力する。

組織総点検2026-08-02で発覚した是正: フクギイロ側は fukugiiro-audit.yml で
週次の自動再監査があるが、企業のミカタ側は2026-07-22等の一回限りの手動レビュー
(docs/守り部審査記録.md)のみで、収集開始後にサイト側の方針が変わっても検知できない
状態だった。フクギイロ側の scripts/audit_sources_fukugiiro.py と同じロジックを
企業のミカタの収集対象ドメインに適用する。

- 実行環境: GitHub Actions(mikata-audit.yml)。開発サンドボックスは外部接続不可のため。
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
OUT_MD = os.path.join(BASE, "docs", "企業のミカタ_robots監査結果.md")
OUT_JSON = os.path.join(BASE, "data", "mikata_robots_audit.json")

# (ラベル, ドメイン, 代表パス=収集で使いそうな入口)
# docs/守り部審査記録.md で条件付き承認済み・scripts/fetch_local.py が実際に使用中のドメインのみ。
TARGETS = [
    ("沖縄県(産業振興)", "www.pref.okinawa.lg.jp", "/shigoto/keizai/1009879/1010143/index.html"),
    ("沖縄県産業振興公社", "okinawa-ric.jp", "/service/subsidy.html"),
    ("那覇市(企業支援)", "www.city.naha.okinawa.jp", "/business/kigyouricchi/kigyoushien/index.html"),
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
        "# 企業のミカタ robots.txt 自動監査結果",
        "",
        f"最終実行: {now} JST / 実行: GitHub Actions(mikata-audit.yml)/ スクリプト: scripts/audit_sources_mikata.py",
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
