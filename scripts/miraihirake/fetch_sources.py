#!/usr/bin/env python3
"""みらいひらけ堂: 原文取得ツール(CI用)。

Claude Codeのリモート環境は外部サイトへ出られないため、原文の取得は
GitHub Actions(ネット接続あり)でこのスクリプトを回して行う。

2モード:
  --audit  各ドメインの robots.txt を取得し、対象URLがクロール許可かを
           data/miraihirake/robots_report.json に書き出す(守り部の審査材料)。
           robots.txt の取得のみで、ページ本文は取らない。
  --fetch  robots_approved=true かつ robots.txt が許可しているURLだけ本文を取得し、
           タグを落としたテキストを data/miraihirake/sources/<id>.txt に保存する。
           検証部はこのテキストと突き合わせて services.json を verified に上げる。

規律(CLAUDE.md 絶対ルール2): robots_approved は守り部が robots_report.json を
確認して手で true にする。未承認URLは --fetch でも絶対に取得しない。
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "data/miraihirake/source_queue.json"
REPORT = ROOT / "data/miraihirake/robots_report.json"
OUTDIR = ROOT / "data/miraihirake/sources"
# HTTPヘッダーは latin-1 しか許されないため UA は必ずASCIIのみ(日本語を入れると
# 全リクエストが UnicodeEncodeError で失敗する。2026-09-06 初回fetchで発生)
UA = "miraihirake-bot/0.1 (+https://github.com/allgroup-inc/hojo-hq; education-info-check)"
DELAY_SEC = 3
TIMEOUT = 20
MAX_BYTES = 1_500_000


def load_queue():
    return json.loads(QUEUE.read_text(encoding="utf-8"))["queue"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read(MAX_BYTES).decode(r.headers.get_content_charset() or "utf-8", "replace")


def robots_for(url):
    base = "{0}://{1}".format(*urlsplit(url)[:2])
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(base + "/robots.txt")
    rp.read()
    return rp


def strip_html(html):
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>|</tr>", "\n", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"[ \t　]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def audit(queue):
    rows = []
    for item in queue:
        row = {"id": item["id"], "url": item["url"], "org": item["org"],
               "checked_at": date.today().isoformat()}
        try:
            rp = robots_for(item["url"])
            row["robots_allows"] = rp.can_fetch(UA, item["url"])
        except Exception as e:  # robots.txt が無い/読めない場合は要人判断
            row["robots_allows"] = "error"
            row["error"] = f"{type(e).__name__}: {e}"
        rows.append(row)
        print(f"[audit] {item['id']}: robots_allows={row['robots_allows']}")
        time.sleep(DELAY_SEC)
    REPORT.write_text(json.dumps(
        {"note": "robots.txt監査結果。守り部はこれと各サイトの利用規約を確認のうえ、"
                 "source_queue.json の robots_approved を true にする。robots_allows=error は"
                 "robots.txt が読めなかった(存在しない場合も含む)ので人が個別確認する。",
         "results": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {REPORT}")


def fetch(queue):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    attempted = ok = 0
    for item in queue:
        if item.get("robots_approved") is not True:
            print(f"[skip] {item['id']}: robots_approved ではない")
            continue
        attempted += 1
        try:
            if not robots_for(item["url"]).can_fetch(UA, item["url"]):
                print(f"[skip] {item['id']}: robots.txt が不許可(承認済みでも取得しない)")
                continue
            text = strip_html(get(item["url"]))
        except Exception as e:
            print(f"[error] {item['id']}: {type(e).__name__}: {e}")
            continue
        header = (f"# source_id: {item['id']}\n# url: {item['url']}\n"
                  f"# org: {item['org']}\n# fetched_at: {date.today().isoformat()}\n"
                  f"# 注意: 機械抽出テキスト。照合の最終根拠は url の原文。\n\n")
        (OUTDIR / f"{item['id']}.txt").write_text(header + text + "\n", encoding="utf-8")
        ok += 1
        print(f"[ok] {item['id']} -> sources/{item['id']}.txt ({len(text)}字)")
        time.sleep(DELAY_SEC)
    print(f"fetch完了: 対象{attempted}件 / 成功{ok}件")
    if attempted and ok == 0:
        print("全件失敗のためジョブを赤にする(成功ゼロは異常)")
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--audit", action="store_true")
    mode.add_argument("--fetch", action="store_true")
    args = ap.parse_args()
    queue = load_queue()
    if args.audit:
        audit(queue)
        return 0
    return fetch(queue)


if __name__ == "__main__":
    sys.exit(main())
