#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq LINE部(ツナグさん) — 締切アラート自動生成
data/subsidies.json から「締切まで約1か月以内」の募集中制度を抽出し、
LINE配信用の下書きを生成する。update.yml で毎日自動実行。

方針(締切3層ルール / .claude/skills/hojo-deadline-alert):
- 30日以上: SNS告知のみ(LINEでは扱わない)
- 7〜29日: LINEアラート対象(書類・gBizID準備が間に合う最後の窓)
- 7日未満: アラートせず「次回公募予告(gBizID啓発)」に切替。急かさない。
- 利用者向け表現は「締切の約1か月前から」で統一。

出力:
  posts/line/alerts_latest.md ... 配信用文面(LINE Official Account Manager にコピペ)
  data/line_alerts.json       ... 構造化データ(Power Automate / Messaging API 連携用)

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

ALERT_MIN = 7    # これ未満は「次回公募予告」へ切替(急かさない)
ALERT_MAX = 29   # これ超はSNS告知のみ(3層ルール)
# 緊急度: (最小日数, 最大日数, 絵文字, 見出し, 掲載上限)
TIERS = [
    (7, 14,  "🟠", "まもなく締切(7〜14日)",  4),
    (15, 29, "🟢", "準備をはじめる(15〜29日)", 4),
]


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
    soon_closed = []  # 7日未満: 予告切替対象(配信では急かさない)
    for it in data.get("items", []):
        d = parse_date(it.get("deadline"))
        if not d:
            continue
        days = (d - today).days
        if it.get("status") != "募集中":
            continue
        if ALERT_MIN <= days <= ALERT_MAX:
            hits.append({**it, "_days": days})
        elif 0 <= days < ALERT_MIN:
            soon_closed.append({**it, "_days": days})
    hits.sort(key=lambda x: (x["_days"], x.get("name", "")))

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)

    # ── 配信用md ──
    lines = [
        "# LINE配信下書き: 締切アラート(約1か月前から / 締切3層ルール準拠)",
        "",
        f"- 生成日: {today}(毎日自動更新)",
        f"- LINEアラート対象(残り{ALERT_MIN}〜{ALERT_MAX}日): {len(hits)}件",
        f"- 7日未満(予告切替・配信で急かさない): {len(soon_closed)}件 → 末尾の予告文を使用",
        "- 使い方: 下の本文をそのまま LINE Official Account Manager のメッセージ配信へ。",
        "",
        "---",
        "",
        "## 本文(コピペ用)",
        "```",
    ]
    if hits:
        body = ["📣【締切が近づいている補助金】", "早めの準備で、間に合わせましょう。"]
        for lo, hi, emoji, label, cap in TIERS:
            tier = [it for it in hits if lo <= it["_days"] <= hi]
            if not tier:
                continue
            body.append("")
            body.append(f"{emoji} {label} — {len(tier)}件")
            for it in tier[:cap]:
                d = it["_days"]
                when = "本日締切" if d == 0 else f"{it['deadline']}(残り{d}日)"
                amt = amount_text(it.get("max_amount"))
                body.append(f"■ {it['name']}")
                body.append(f"　{when}" + (f" / {amt}" if amt else ""))
                body.append(f"　{it['source_url']}")
            if len(tier) > cap:
                body.append(f"　…ほか{len(tier)-cap}件は一覧へ")
        body += [
            "",
            "💡 電子申請には gBizIDプライム が必要な制度が多いです。オンライン申請(マイナンバーカード)なら速やかに、書類の郵送申請は審査に最大1か月かかります。",
            "",
            "準備が間に合うか不安なときは、このLINEに「相談」と一言どうぞ。無料で、担当が状況に合わせてご案内します。",
            "※要件・締切は必ず原文でご確認ください。",
            f"制度一覧 → {SITE_URL}",
        ]
        lines += body
    else:
        lines += [f"(本日は残り{ALERT_MIN}〜{ALERT_MAX}日の制度がありません — アラート配信不要)"]
    # 7日未満: 次回公募予告(急かさず、次に備えてもらう)
    lines += ["```", "", "## 7日未満の制度(予告切替) — 配信で使う場合はこちらの文面", "```"]
    if soon_closed:
        lines += [
            f"⏳ 締切目前の公募が{len(soon_closed)}件あります。",
            "いまから書類を整えるのは大変なので、無理は禁物。",
            "次の公募に備えて【gBizIDプライム】を先に用意しておきましょう(オンライン申請なら速やかに発行、郵送は最大1か月)。",
            f"制度一覧 → {SITE_URL}",
        ]
    else:
        lines += ["(該当なし)"]
    lines += ["```", ""]
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # ── 構造化JSON ──
    def tier_of(days):
        for lo, hi, _, label, _cap in TIERS:
            if lo <= days <= hi:
                return label
        return None

    payload = {
        "generated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "alert_window": [ALERT_MIN, ALERT_MAX],
        "soon_closed_count": len(soon_closed),
        "count": len(hits),
        "items": [
            {
                "id": it["id"],
                "name": it["name"],
                "deadline": it["deadline"],
                "days_left": it["_days"],
                "tier": tier_of(it["_days"]),
                "max_amount": it.get("max_amount"),
                "source_url": it["source_url"],
                "tag": it.get("tag"),
            }
            for it in hits
        ],
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    by_tier = {}
    for it in hits:
        t = tier_of(it["_days"])
        by_tier[t] = by_tier.get(t, 0) + 1
    print(f"[ok] LINE対象(残り{ALERT_MIN}-{ALERT_MAX}日): {len(hits)}件 {by_tier} / 予告切替(7日未満): {len(soon_closed)}件")


if __name__ == "__main__":
    main()
