#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
法人部(アキナイさん)商談前ブリーフ自動生成
data/subsidies.json(企業のミカタDB)から、訪問先企業の業種キーワードに合う制度を抽出し、
「その会社が使える可能性のある制度リスト」をMarkdownで生成する。

使い方:
  python scripts/akinai_brief.py --company "株式会社サンプル" --keywords 飲食 観光 --out docs/brief.md

方針:
- 商談の手土産(これ自体が法人サブスクのレポートのデモ)。全て「可能性」表記+一次ソースリンク
- 締切が近い順に上位を提示。締切7日以内は「急ぎ」マーク
- 生成はL4(自動)、送付はL2(人間承認)— 運用規程どおり
"""
import argparse
import json
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "subsidies.json")

# 業種キーワード → 制度名/対象に含まれがちな関連語(検索の再現性のための静的辞書)
EXPAND = {
    "飲食": ["飲食", "食品", "外食", "インバウンド", "観光", "販路開拓", "省力化", "IT導入"],
    "観光": ["観光", "インバウンド", "宿泊", "旅行"],
    "建設": ["建設", "住宅", "省エネ", "設備", "人材", "安全"],
    "製造": ["ものづくり", "製造", "設備", "省力化", "研究開発", "輸出"],
    "IT": ["IT", "DX", "デジタル", "システム", "研究開発"],
    "小売": ["商店", "販路開拓", "IT導入", "省力化", "インボイス"],
    "農業": ["農業", "食品", "輸出", "6次"],
    "医療福祉": ["医療", "介護", "福祉", "人材", "省力化"],
}
COMMON = ["雇用", "賃上げ", "人材", "事業承継", "創業"]  # 全業種共通で見る領域


def load_items():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)["items"]


def score(item, terms):
    text = (item.get("name", "") + " " + item.get("target_biz", "") + " " + item.get("issuer", ""))
    return sum(1 for t in terms if t in text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", default="(社名)")
    ap.add_argument("--keywords", nargs="+", required=True, help="業種キーワード(飲食/観光/建設/製造/IT/小売/農業/医療福祉 or 自由語)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()

    terms = []
    for k in args.keywords:
        terms += EXPAND.get(k, [k])
    terms = list(dict.fromkeys(terms))

    today = datetime.now(JST).date()
    items = load_items()
    hits = []
    for it in items:
        s = score(it, terms)
        c = score(it, COMMON)
        if s == 0 and c == 0:
            continue
        try:
            dl = datetime.strptime(it.get("deadline", ""), "%Y-%m-%d").date()
            days = (dl - today).days
        except Exception:
            days = 9999
        if days < 0:
            continue
        hits.append((s * 10 + c, days, it))
    hits.sort(key=lambda x: (-x[0], x[1]))
    top = hits[: args.top]

    now = datetime.now(JST).strftime("%Y-%m-%d")
    lines = [
        f"# {args.company} 様向け 補助金・助成金 事前リサーチ({now}時点)",
        "",
        f"株式会社フクギイロ調べ / 業種想定: {' / '.join(args.keywords)}",
        "",
        "> 掲載は「使える可能性のある制度のご案内」です。対象になるかの最終判断は公募要領と申請窓口でご確認ください。",
        "> 申請手続きの代行は行っておりません。必要な場合は提携の専門家(社労士・行政書士)をご紹介します。",
        "",
        "| # | 制度名 | 締切 | 上限額 | 公式 |",
        "|---|---|---|---|---|",
    ]
    for i, (_, days, it) in enumerate(top, 1):
        dl = it.get("deadline", "要確認")
        mark = " ⚠急ぎ" if days <= 7 else ""
        amt = it.get("max_amount") or 0
        amt_s = f"{amt:,}円" if amt else "要確認"
        name = it.get("name", "")[:45]
        lines.append(f"| {i} | {name} | {dl}{mark} | {amt_s} | [公式]({it.get('source_url','')}) |")
    lines += [
        "",
        f"(抽出元: 掲載{len(items)}件・毎日自動更新のデータベース / 該当候補{len(hits)}件から上位{len(top)}件)",
        "",
        "---",
        "毎月の最新版レポート+締切アラートをご希望の場合は、法人向けプランのご案内が可能です。",
    ]
    md = "\n".join(lines) + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"出力: {args.out}({len(top)}件)")
    else:
        print(md)


if __name__ == "__main__":
    main()
