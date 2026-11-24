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
import re
import sys
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import shipping_gate

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "subsidies.json")

# 出荷ゲート(運用規程1-3)の通過日。**本ファイルの配信文面を書き換えたら必ず更新する。**
# 2026-08-17: accuracy-check(締切・金額・出典URLはdata由来/「必ず原文でご確認ください」を明記)/
#             deadline-alert(3層ルール: 30日以上=SNSのみ・7〜29日=LINE・7日未満=予告切替)/
#             humanizer(急かす表現・過剰な絵文字なし)で確認。
# 2026-11-24: 90日の期限切れ(11/15)で出荷が止まったため再点検。3層の境界(7〜29日)・残り日数の表記・
#             予告側のgBizID案内・禁止表現なしは変わらず合格。直したのは2点(accuracy-check):
#             ①見出し「補助金」→「公募」(jGrantsの対象には国の調査委託の公募も入り、補助金と言い切れない)
#             ②gBizIDの発行日数(「速やかに」「最大1か月」)は今回公式ページで確かめられなかったため数字を外し、
#               「郵送は日数がかかる・公式サイトで確認」にとどめた(確かめていない数字は書かない)
GATE_CHECKED = "2026-11-24"
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


# LINEで扱う公募の範囲(2026-11-24 小柳さん決裁: docs/議事_20261124_LINE締切アラートの対象.md)。
# 沖縄県・県内市町村・事業承継の制度はすべて扱う。全国の公募のうち、沖縄の中小企業が
# そのまま申し込みにくいもの(調査・委託・研究開発、大企業向け、超大型)は LINE では扱わない。
# サイトの制度一覧からは消さない(LINEで知らせないだけ)。
# 迷うものは外さない(外すのは確かに中小企業向けでないものだけ)。独立レビュー(2026-11-24)を受け、
# 従業員要件での除外はやめた(jGrants の「901名以上」は規模の区分で、中小企業が対象外とは限らない)。
SCOPE_ALWAYS_TAGS = {"okinawa", "shokei"}
SCOPE_RESEARCH = re.compile(r"調査|委託|研究開発|技術開発|実証")
SCOPE_SME = re.compile(r"中小企業|小規模|中小")   # 中小企業向けの研究開発支援(Go-Tech 等)は外さない
SCOPE_MAX_AMOUNT = 1_000_000_000       # 上限が10億円を超えるものは、地域の中小企業向けとは言いにくい


def scope_reason(it):
    """LINEで扱わない理由。扱うなら None。"""
    if it.get("tag") in SCOPE_ALWAYS_TAGS:
        return None
    text = f"{it.get('name') or ''} {it.get('issuer') or ''}"
    if SCOPE_SME.search(text):
        return None
    if SCOPE_RESEARCH.search(text):
        return "調査・委託・研究開発"
    if (it.get("max_amount") or 0) > SCOPE_MAX_AMOUNT:
        return "上限10億円超"
    return None


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
    out_of_scope = {}  # LINEで扱わない公募(理由 → 件数)。サイトの一覧には残る
    for it in data.get("items", []):
        d = parse_date(it.get("deadline"))
        if not d:
            continue
        days = (d - today).days
        if it.get("status") != "募集中":
            continue
        if 0 <= days <= ALERT_MAX:
            why = scope_reason(it)
            if why:
                out_of_scope[why] = out_of_scope.get(why, 0) + 1
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
        "- LINEで扱わない公募(サイトの一覧には掲載): "
        + (" / ".join(f"{k} {v}件" for k, v in sorted(out_of_scope.items())) or "なし")
        + "(docs/議事_20261124_LINE締切アラートの対象.md)",
        "- 使い方: 下の本文をそのまま LINE Official Account Manager のメッセージ配信へ。",
        "",
        "---",
        "",
        "## 本文(コピペ用)",
        "```",
    ]
    if hits:
        body = ["📣【締切が近づいている公募】", "早めの準備で、間に合わせましょう。"]
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
            "💡 電子申請には gBizIDプライム が必要な制度が多いです。郵送で申請すると発行まで日数がかかるので、早めの準備がおすすめです(申請方法はgBizIDの公式サイトでご確認ください)。",
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
            "次の公募に備えて【gBizIDプライム】を先に用意しておきましょう(郵送の申請は発行まで日数がかかります。申請方法はgBizIDの公式サイトでご確認ください)。",
            f"制度一覧 → {SITE_URL}",
        ]
    else:
        lines += ["(該当なし)"]
    lines += ["```", ""]

    # ── 出荷ゲート(運用規程1-3)──
    # 配信するのは人(ツナグさん)なので、機械が止められるのは「下書きの見え方」まで。
    # 違反があれば通過記録を付けず、**人が最初に読む先頭**に警告を出す(フェイルクローズ)。
    body_text = "\n".join(lines)
    violations = shipping_gate.check_forbidden(body_text)
    if violations:
        warn = ["> ⚠️ **この下書きは配信しないでください(出荷ゲート未通過)**", ">"]
        warn += [f"> - {v}" for v in violations]
        warn += ["> ", "> 文面を修正し `scripts/generate_line_alerts.py` を実行し直してください。", ""]
        lines = [lines[0], ""] + warn + lines[1:]
    else:
        lines += [shipping_gate.render_stamp(
            "scripts/generate_line_alerts.py(LINE部・ツナグさん)", GATE_CHECKED)]

    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    if violations:
        print(f"[ng] 出荷ゲート未通過({len(violations)}件)。下書き先頭に警告を入れました:")
        for v in violations:
            print(f"  - {v}")

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


def self_test():
    ok = bad = 0

    def check(label, cond):
        nonlocal ok, bad
        if cond:
            ok += 1
        else:
            bad += 1
            print(f"  NG {label}")

    def it(name, tag="nationwide", issuer="", employees="従業員数の制約なし", amount=0):
        return {"name": name, "tag": tag, "issuer": issuer, "employees": employees, "max_amount": amount}

    check("小規模事業者持続化補助金は扱う",
          scope_reason(it("小規模事業者持続化補助金＜創業型＞", employees="20名以下", amount=2_000_000)) is None)
    check("特許動向調査は扱わない", scope_reason(it("「ナトリウムイオン電池に関する技術（特許）動向調査」の公募")) == "調査・委託・研究開発")
    check("研究開発事業(事業名側)は扱わない",
          scope_reason(it("記録レス介護モデルの公募", issuer="ポスト５Ｇ情報通信システム基盤強化研究開発事業")) == "調査・委託・研究開発")
    check("従業員の区分(901名以上)では外さない", scope_reason(it("事業再編計画支援", employees="901名以上")) is None)
    check("上限250億円は扱わない", scope_reason(it("GX地域共創補助金2026", amount=25_000_000_000)) == "上限10億円超")
    check("上限ちょうど10億円は扱う", scope_reason(it("業務用建築物の脱炭素改修加速化事業", amount=1_000_000_000)) is None)
    check("上限5億円は扱う", scope_reason(it("ZEB支援事業", amount=500_000_000)) is None)
    check("中小企業向けの研究開発支援は扱う",
          scope_reason(it("成長型中小企業等研究開発支援事業(Go-Tech事業)")) is None)
    check("沖縄の制度は、調査の語があっても扱う", scope_reason(it("沖縄県 市場調査支援事業", tag="okinawa")) is None)
    check("事業承継の制度は扱う", scope_reason(it("事業承継・引継ぎ補助金", tag="shokei", amount=8_000_000)) is None)
    print(f"自己テスト: OK {ok} / NG {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    main()
