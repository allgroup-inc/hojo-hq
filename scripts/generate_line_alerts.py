#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq LINE部(ツナグさん) — 締切アラート自動生成
data/subsidies.json から「締切まで7日以内」の募集中制度を抽出し、
LINE配信用の下書きを生成する。update.yml で毎日自動実行。

出力:
  posts/line/alerts_latest.md ... 配信用文面(LINE Official Account Manager にコピペ)
  data/line_alerts.json       ... 構造化データ(将来の Power Automate / Messaging API 連携用)

制約(CLAUDE.md 絶対ルール#1):
- 締切・金額は原文通り。誇大表現なし。各制度に出典URL。
- 配信の実行は人(ツナグさん運用担当)が行う。本スクリプトは下書きまで。
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "subsidies.json")
OUT_MD = os.path.join(BASE_DIR, "..", "posts", "line", "alerts_latest.md")
OUT_JSON = os.path.join(BASE_DIR, "..", "data", "line_alerts.json")
SITE_URL = "https://allgroup-inc.github.io/hojo-hq/?utm_source=line&utm_medium=message&utm_campaign=deadline_alert"

ALERT_DAYS = 7   # 締切までこれ以内をアラート対象
MAX_ITEMS = 8    # 1配信に載せる最大件数(多すぎると読まれない)


def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def amount_text(v):
    if not v:
        return None
    if v >= 100_000_000:
        oku = f"{v / 100_000_000:.1f}".rstrip("0").rstrip(".")
        return f"上限{oku}億円"
    if v >= 10000:
        return f"上限{v // 10000:,}万円"
    return f"上限{v:,}円"


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    today = datetime.now(JST).date()

    hits = []
    for it in data.get("items", []):
        d = parse_date(it.get("deadline"))
        if not d:
            continue
        days = (d - today).days
        if 0 <= days <= ALERT_DAYS and it.get("status") == "募集中":
            hits.append({**it, "_days": days})
    hits.sort(key=lambda x: (x["_days"], x.get("name", "")))
    shown = hits[:MAX_ITEMS]
    omitted = len(hits) - len(shown)

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)

    # ── 配信用md ──
    lines = [
        "# LINE配信下書き: 締切アラート",
        "",
        f"- 生成日: {today}(毎日自動更新)",
        f"- 対象: 締切{ALERT_DAYS}日以内の募集中制度 {len(hits)}件"
        + (f"(うち{MAX_ITEMS}件を掲載, 残り{omitted}件は一覧参照)" if omitted > 0 else ""),
        "- 使い方: 下の本文をそのまま LINE Official Account Manager のメッセージ配信へ。",
        "",
        "---",
        "",
        "## 本文(コピペ用)",
        "```",
    ]
    if shown:
        body = ["⏰【締切が近い補助金】"]
        for it in shown:
            d = it["_days"]
            when = "本日締切!" if d == 0 else f"残り{d}日({it['deadline']})"
            amt = amount_text(it.get("max_amount"))
            body.append("")
            body.append(f"■ {it['name']}")
            body.append(f"　締切: {when}" + (f" / {amt}" if amt else ""))
            body.append(f"　詳細: {it['source_url']}")
        body += [
            "",
            "※要件・締切は必ず原文でご確認ください。",
            f"制度一覧はこちら → {SITE_URL}",
        ]
        lines += body
    else:
        lines += [
            "(本日は締切7日以内の制度がありません — 配信不要)",
        ]
    lines += ["```", ""]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ── 構造化JSON(Power Automate / Messaging API 連携用) ──
    payload = {
        "generated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "alert_days": ALERT_DAYS,
        "count": len(hits),
        "items": [
            {
                "id": it["id"],
                "name": it["name"],
                "deadline": it["deadline"],
                "days_left": it["_days"],
                "max_amount": it.get("max_amount"),
                "source_url": it["source_url"],
                "tag": it.get("tag"),
            }
            for it in hits
        ],
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    print(f"[ok] 締切{ALERT_DAYS}日以内: {len(hits)}件 → posts/line/alerts_latest.md, data/line_alerts.json")
    for it in shown:
        print(f"  - 残り{it['_days']}日 | {it['name'][:40]}")


if __name__ == "__main__":
    main()
