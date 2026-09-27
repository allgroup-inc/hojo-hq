#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""もらいわすれ堂 山梨版 検証部突合 — 一次ソース照合レポート(2026-09-27 新設)

kensho_fukugiiro.py(沖縄版)と同じやり方で、山梨版 seido.json の
**山梨県+市町村の制度のみ**を公式ページと機械照合する。
全国の制度52件は沖縄版の突合で毎日照合済みのため、同じURLを二重に叩かない(礼儀)。

- ○=制度名を確認 / △=一部一致 / ×=取得できたが確認できず(最優先で人間確認)
  / -=取得できず判定不能(掲載の誤りを意味しない)
- verified=True への昇格はこのレポートを人間が確認してから(機械照合だけで昇格しない)
- 礼儀: robots.txt 遵守・1.5秒間隔・連絡先付きUA(守り部審査記録_山梨版 §8の遵守条件)
- 実行: fukugiiro-fetch.yml 内(山梨版再生成の後)。出力2つは同ワークフローの
  git add リストにも載せる(再発防止メモ: addリストから漏れた生成物は消える)
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 文字コード判定・照合トークン・エラー表記は沖縄版と完全に同じ挙動を使う
# (同じ対象を扱うスクリプトはロジックを共有する — 再発防止メモの原則)
from kensho_fukugiiro import describe_error, fetch_text, name_tokens, page_title  # noqa: E402
from fetch_fukugiiro import robots_ok  # noqa: E402

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "yamanashi", "seido.json")
OUT = os.path.join(BASE, "docs", "山梨版_突合レポート.md")
SUMMARY = os.path.join(BASE, "data", "yamanashi", "kensho_summary.json")


def target_items(db):
    """照合対象 = 山梨県+市町村の制度のみ(全国は沖縄版の突合が毎日見ている)。"""
    return [it for it in db.get("items", []) if it.get("area") != "全国"]


def self_test():
    ok = True

    def expect(cond, label):
        nonlocal ok
        print(("  ok   " if cond else "  NG   ") + label)
        ok = ok and cond

    db = {"items": [
        {"area": "全国", "name": "児童手当"},
        {"area": "山梨県", "name": "乳幼児医療費の助成"},
        {"area": "北杜市", "name": "子ども医療費助成制度"},
    ]}
    t = target_items(db)
    expect(len(t) == 2, "全国の制度は対象外(沖縄版で照合済み・二重に叩かない)")
    expect({x["area"] for x in t} == {"山梨県", "北杜市"}, "県と市町村だけが対象")
    expect(len(name_tokens("子育て応援金支給事業")) > 0, "name_tokens が空にならない")
    print("self-test:", "OK" if ok else "NG")
    return 0 if ok else 1


def main():
    if "--self-test" in sys.argv:
        return self_test()
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    with open(DATA, encoding="utf-8") as f:
        db = json.load(f)
    items = target_items(db)

    lines = [
        "# もらいわすれ堂 山梨版 一次ソース突合レポート(機械照合)",
        "",
        f"最終実行: {now} JST / スクリプト: scripts/kensho_yamanashi.py",
        f"対象: 山梨県+市町村の制度 {len(items)}件(全国の制度は沖縄版の突合レポートを参照)",
        "",
        "> ○=制度名がページ上で確認できた / △=一部トークンのみ一致 / ×=ページは取得できたが制度名を確認できず(内容が変わった可能性 — 最優先で人間確認) / **-=ページを取得できず判定不能**(掲載の誤りを意味しない)",
        "> **verified=True への昇格は、本レポートを人間が確認してから行う。機械照合だけで昇格しない。**",
        "",
        "| 制度 | 地域 | ページタイトル | 照合 | 現status |",
        "|---|---|---|---|---|",
    ]
    ng = unreachable = skipped_robots = 0
    full_ok = 0
    rows = []
    for it in items:
        url = it["source_url"]
        if not robots_ok(url):
            title, mark = "(未取得: robots.txt が許可していないため)", "◇"
            skipped_robots += 1
        else:
            try:
                html = fetch_text(url)
                title = page_title(html)
                text = re.sub(r"<[^>]+>", " ", html)
                tokens = it.get("match_tokens") or name_tokens(it["name"])
                hit = sum(1 for t in tokens if t in text)
                if hit == len(tokens) and tokens:
                    mark = "○"
                    full_ok += 1
                elif hit > 0:
                    mark = "△"
                else:
                    mark, ng = "×", ng + 1
            except Exception as e:  # noqa: BLE001
                # 取得失敗は「掲載が誤り」の証拠にならない(再発防止メモ)。×と混ぜない
                title, mark = f"(取得できず: {describe_error(e)})", "-"
                unreachable += 1
            time.sleep(1.5)
        rows.append({"name": it["name"], "area": it.get("area", ""), "url": url,
                     "title": title[:60], "mark": mark, "status": it.get("status", "")})
        lines.append(f"| {it['name']} | {it.get('area','')} | {title[:60]} | {mark} | {it.get('status','')} |")
        print(f"{mark} {it.get('area','')} {it['name']}")

    lines += [
        "",
        f"○(全トークン一致): {full_ok}件 / ×(内容を確認できず): {ng}件 / "
        f"取得できず判定不能: {unreachable}件 / robots不許可: {skipped_robots}件",
        "",
        "## 昇格候補(○のもの)",
        "",
        "○の制度は、人間がページ本文を目視確認のうえ `verified=True` へ昇格できる"
        "(シード: scripts/yamanashi/seeds_yamanashi*.py に verified 済み情報を追記して再ビルド)。",
    ]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    summary = {"updated_at": now, "total": len(rows), "full_ok": full_ok, "ng": ng,
               "unreachable": unreachable, "skipped_robots": skipped_robots,
               "items": [{k: r[k] for k in ("name", "area", "mark")} for r in rows]}
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"レポート出力: {OUT} / ○ {full_ok} / × {ng} / 取得できず {unreachable} / robots不許可 {skipped_robots}")


if __name__ == "__main__":
    sys.exit(main() or 0)
