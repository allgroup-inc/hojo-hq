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
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_fukugiiro import robots_ok  # noqa: E402  収集側と同じ礼儀ルールを使う

JST = timezone(timedelta(hours=9))
UA = "hojo-hq-bot/1.0 (+https://allgroup-inc.github.io/hojo-hq; contact: bot@en-life.co.jp)"
BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "fukugiiro", "seido.json")
OUT = os.path.join(BASE, "docs", "フクギイロ_突合レポート.md")
SUMMARY = os.path.join(BASE, "data", "fukugiiro", "kensho_summary.json")


def describe_error(e):
    """403(遮断)と404(消滅)は意味が全く違うので、必ずコードまで残す。"""
    code = getattr(e, "code", None)
    return f"{type(e).__name__} {code}" if code else type(e).__name__


# バイト列から charset 宣言を拾う(宣言はASCII範囲なので復号前に読める)
_META_CHARSET = re.compile(rb'charset["\s=:]+([A-Za-z0-9_\-]+)', re.I)


def sniff_charset(raw, header_charset=None):
    """宣言されている文字コードを返す。HTTPヘッダ → HTMLのmeta の順。"""
    if header_charset:
        return header_charset
    m = _META_CHARSET.search(raw[:4096])
    return m.group(1).decode("ascii", "ignore") if m else None


def decode_html(raw, header_charset=None):
    """文字化けさせずに復号する。

    以前は utf-8 → shift_jis → cp932 の順に試していたが、**cp932 は EUC-JP の
    バイト列を例外なしに読んでしまう**ため、EUC-JP の自治体サイト(渡名喜村など)が
    文字化けし、突合で「内容不一致(×)」として誤報告されていた(2026-09-22 検知)。
    化けた結果は例外にならないので、候補を順に試すだけでは足りない。

    対策は2つ:
      1. 宣言された charset を最優先する
      2. 復号できた候補を**日本語らしさで採点**して選ぶ(置換文字と私用領域を減点)
    """
    cands = []
    declared = sniff_charset(raw, header_charset)
    if declared:
        cands.append(declared)
    cands += ["utf-8", "euc_jp", "shift_jis", "cp932"]

    best, best_score = None, None
    for enc in cands:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        score = _jp_score(text)
        if best_score is None or score > best_score:
            best, best_score = text, score
        if enc == declared and score > 0:
            break   # 宣言どおりに読めて日本語が出ているなら、それを信じる
    if best is not None:
        return best
    return raw.decode("utf-8", errors="replace")


def _jp_score(text):
    """日本語として読めているかの粗い採点。化けた文字列を弾くために使う。"""
    head = text[:4000]
    if not head:
        return 0
    jp = sum(1 for ch in head
             if 0x3040 <= ord(ch) <= 0x30FF or 0x4E00 <= ord(ch) <= 0x9FFF)
    # 置換文字(U+FFFD)と私用領域は化けの痕跡。強めに減点する
    bad = sum(1 for ch in head
              if ch == "\ufffd" or 0xE000 <= ord(ch) <= 0xF8FF)
    return jp - bad * 5


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as res:
        raw = res.read(500000)
        cs = None
        try:
            cs = res.headers.get_content_charset()
        except Exception:  # noqa: BLE001
            pass
    return decode_html(raw, cs)


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
        "> ○=制度名がページ上で確認できた / △=一部トークンのみ一致 / ×=ページは取得できたが制度名を確認できず(内容が変わった可能性 — 最優先で人間確認) / **-=ページを取得できず判定不能**(UAブロック・一時障害等。掲載の誤りを意味しない)",
        "> **verified=true への昇格は、本レポートをケンショウ+金曜承認バッチで確認してから行う(L2)。機械照合だけで昇格しない。**",
        "",
        "| 制度 | ページタイトル | 照合 | 現status |",
        "|---|---|---|---|",
    ]
    ng = 0
    unreachable = 0
    skipped_known = 0
    skipped_robots = 0
    rows = []
    for it in db.get("items", []):
        url = it["source_url"]
        if not robots_ok(url):
            title, mark = "(未取得: robots.txt が許可していないため)", "◇"
            skipped_robots += 1
            rows.append({"name": it["name"], "url": url, "title": title,
                         "mark": mark, "status": it["status"], "area": it.get("area", "")})
            lines.append(f"| {it['name']} | {title} | {mark} | {it['status']} |")
            print(f"{mark} {it['name']}")
            continue
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
            # 取得できないことは「掲載内容が誤り」の証拠にならない(UAブロック・一時障害・
            # レート制限で起きる)。× と混ぜると健全な掲載まで誤って要対応に見えるため分ける。
            # 2026-09-20: 13件が×として要対応に出たが、11件は検索で現行URLと一致し健在だった。
            if it.get("assume_reachable"):
                # bot遮断(403)が既知で、収集側が assume_reachable を立てている先。
                # 根拠は verified_by に記録された手動確認(WebSearch照合)。要対応には数えない。
                # 取得自体は毎回試す: 213件中の大多数は実際には応答するため、
                # 事前に一律スキップすると健全な照合まで失う。
                basis = f"{it.get('verified_at', '')} {it.get('verified_by', '手動確認')}".strip()
                title = f"(未取得: {describe_error(e)} / bot遮断が既知・手動確認済み {basis[:40]})"
                mark = "◇"
                skipped_known += 1
            else:
                title, mark = f"(取得できず: {describe_error(e)})", "-"
                unreachable += 1
        rows.append({"name": it["name"], "url": url, "title": title[:60],
                     "mark": mark, "status": it["status"], "area": it.get("area", "")})
        lines.append(f"| {it['name']} | {title[:60]} | {mark} | {it['status']} |")
        print(f"{mark} {it['name']}")
        time.sleep(1.5)

    lines += ["", f"×の件数: {ng}(内容を確認できず) / 取得できず判定不能: {unreachable}件 / "
              f"既知のbot遮断(手動確認済み): {skipped_known}件 / robots不許可で未取得: {skipped_robots}件"]

    # 「検証済み」表示なのに原文で確認できない = 絶対ルール1(断定しない)に触れる状態。
    # 従来は260行の表に埋もれて気づけなかったため、最上部に独立した要対応欄として出す。
    risky = [r for r in rows if r["status"] == "検証済み" and r["mark"] in ("×", "△")]
    unresolved = [r for r in rows if r["status"] == "検証済み" and r["mark"] == "-"]
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
    head += [
        "",
        f"### 判定できなかった {len(unresolved)}件(検証済み表示・ページを取得できず)",
        "",
        "**掲載が誤っているという意味ではない。** 取得失敗はUAブロック・一時障害・レート制限でも起きる。"
        "同じURLが次回実行で取得できることも多いため、status は変えず、"
        "連続して取得できない場合にURLの生死を人間が確認する。",
        "",
    ]
    if unresolved:
        head += ["| 制度 | 地域 | 事象 | 原文URL |", "|---|---|---|---|"]
        head += [f"| {r['name']} | {r['area']} | {r['title']} | {r['url']} |" for r in unresolved]
    else:
        head.append("(該当なし)")
    head.append("")
    lines[7:7] = head  # 凡例の直後、全件表の前に差し込む

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    summary = {"updated_at": now, "total": len(rows), "ng": ng,
               "unreachable": unreachable,
               "skipped_known_block": skipped_known, "skipped_robots": skipped_robots,
               "verified_but_unconfirmed": len(risky),
               "verified_but_unreachable": len(unresolved),
               "items": [{k: r[k] for k in ("name", "area", "mark", "url")} for r in risky]}
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"レポート出力: {OUT} / × {ng}件 / 取得できず {unreachable}件 / "
          f"既知の遮断 {skipped_known}件 / robots不許可 {skipped_robots}件 / "
          f"検証済みなのに内容未確認 {len(risky)}件")
    if risky:
        print("[warn] 検証済み表示のまま原文を確認できない制度があります(要対応欄を参照)")


if __name__ == "__main__":
    main()
