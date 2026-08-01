#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 月刊「沖縄補助金白書」ジェネレータ(収益軸A/B)
(設計・議事: docs/収益軸拡張_設計.md / 2026-07-31 起案)

data/subsidies.json から2種類の月次レポートを同時生成する。
- 軸A: note有料メンバーシップ向け白書  → posts/note/premium/YYYY-MM_hakusho.md
- 軸B: 士業・金融機関パートナー向け版 → reports/partner/YYYY-MM_partner.md
公開・配布はいずれも人間(たかしくん/ムスブさん)が行い、価格と開始は小柳さん決裁後。

制約(CLAUDE.md 絶対ルール#1 / 締切3層ルール / 議事_総額ポテンシャル表示.md):
- 制度名を出して掲載するのは「締切30日以上先」のみ。30日未満は件数のみ
- 金額・締切はデータの値をそのまま転記。上限未公表(0/None)は「要確認」
- 総額は上限1億円以下・公表分のみの参考値表記+免責
- 有料版でも個別制度の情報は無料サイトと同じ(有料の価値は整理・俯瞰・カレンダー化のみ)

使い方:
  python scripts/generate_monthly_report.py            # 2ファイル生成
  python scripts/generate_monthly_report.py --dry-run  # 標準出力のみ
  python scripts/generate_monthly_report.py --preview  # Actions用: key=value 出力
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from generate_note import (  # noqa: E402
    BASE, DATA_PATH, DISCLAIMER, JST, PROMOTE_MIN_DAYS, TAG_PRIORITY,
    area_label, days_left, fmt_amount, load_json, potential_sum,
)

PREMIUM_DIR = os.path.join(BASE, "posts", "note", "premium")
PARTNER_DIR = os.path.join(BASE, "reports", "partner")

SITE_URL = "https://allgroup-inc.github.io/hojo-hq/?utm_source=note&utm_medium=article&utm_campaign=hakusho"
CALENDAR_MONTHS = 3   # 締切カレンダーの範囲
CAT_PICK_MAX = 3      # 目的別マップの代表制度数

# 目的別マップの分類(制度名のキーワード判定。該当なしは「その他」)
CATEGORIES = [
    ("省エネ・環境", ("省エネ", "環境", "脱炭素", "CO2", "二酸化炭素", "電動", "再エネ", "エネルギー", "廃棄物")),
    ("IT・デジタル", ("IT", "デジタル", "DX", "システム", "EC", "サイバー")),
    ("設備投資・販路開拓", ("設備", "販路", "持続化", "ものづくり", "振興", "投資", "生産性")),
    ("雇用・人材", ("雇用", "人材", "育成", "奨学", "賃上", "研修", "職場", "両立")),
    ("創業・事業承継", ("創業", "起業", "承継", "後継", "スタートアップ")),
]

# パートナー版: カテゴリ別の「顧客への声かけ例」(事実の断定を含まない定型文)
TALK_EXAMPLES = {
    "省エネ・環境": "「電気代の負担、設備の入れ替えで軽くできるかもしれません。いま公募中の省エネ系の制度を一度見てみませんか」",
    "IT・デジタル": "「請求書や在庫の管理、手作業のままですか? IT導入系の制度が使える可能性があります」",
    "設備投資・販路開拓": "「次の設備投資やEC・県外展開のご予定があれば、先に使える制度がないか確認しましょう」",
    "雇用・人材": "「採用や賃上げをお考えなら、人件費まわりの助成が対象になるかもしれません」",
    "創業・事業承継": "「後継ぎの話が少しでも出ているなら、承継系の支援策は準備に時間がかかるので早めが安心です」",
    "その他": "「御社の業種で使える制度があるか、無料のデータベースで一緒に確認できます」",
}

AMOUNT_BANDS = [
    ("〜100万円", 0, 1_000_000),
    ("100万円超〜500万円", 1_000_000, 5_000_000),
    ("500万円超〜1,000万円", 5_000_000, 10_000_000),
    ("1,000万円超〜1億円", 10_000_000, 100_000_000),
    ("1億円超(大型公募)", 100_000_000, float("inf")),
]


def categorize(item) -> str:
    name = item.get("name") or ""
    for label, kws in CATEGORIES:
        if any(k in name for k in kws):
            return label
    return "その他"


def month_of(deadline: str) -> str:
    try:
        return datetime.strptime(deadline, "%Y-%m-%d").strftime("%Y年%m月")
    except (TypeError, ValueError):
        return "要確認"


def item_line(it, today) -> str:
    left = days_left(it.get("deadline"), today)
    return (
        f"- **{it.get('name', '(名称不明)')}**\n"
        f"  - {area_label(it)} / 締切: {it.get('deadline', '要確認')}(残り{left}日)"
        f" / 上限額: {fmt_amount(it.get('max_amount'))}\n"
        f"  - 原文: {it.get('source_url', '')}"
    )


def build(data, today, partner: bool) -> str:
    items = data.get("items", [])
    listable = [
        i for i in items
        if (dl := days_left(i.get("deadline"), today)) is not None and dl >= PROMOTE_MIN_DAYS
    ]
    closing = sum(
        1 for i in items
        if (dl := days_left(i.get("deadline"), today)) is not None and 0 <= dl < PROMOTE_MIN_DAYS
    )
    okinawa_n = sum(1 for i in items if i.get("tag") == "okinawa")
    total_amt, inc_n, over_n, unknown_n = potential_sum(items)
    mstr = today.strftime("%Y年%m月")

    L = []
    if partner:
        L.append(f"# 沖縄補助金白書 パートナー版 {mstr}号")
        L.append("")
        L.append(
            "本資料は「沖縄企業のミカタ」(運営: ALLGROUP)の制度データベースから自動生成した、"
            "提携士業・商工会・金融機関さま向けの月次資料です。"
            "**顧問先・お取引先との会話の話材**としてご利用ください。"
        )
        L.append("")
        L.append("> 取扱い: 提携先さま内部での利用に限ります(そのままの再配布・転売はご遠慮ください)。")
    else:
        L.append(f"# 月刊 沖縄補助金白書 {mstr}号")
        L.append("")
        L.append(
            "沖縄の企業が使える補助金・助成金データベース(毎日自動更新)を、月に一度、"
            "AI編集部が「全体像→分野別→締切カレンダー」の順に整理してお届けする有料版です。"
            "個別の制度情報はすべて無料サイトでもご覧いただけます。"
            "この白書の価値は**整理と俯瞰**にあります。"
        )
    L.append("")

    L.append("## 今月の全体像")
    L.append("")
    L.append(f"- 掲載中の制度: **{len(items)}件**(うち沖縄県・市町村の制度 {okinawa_n}件)")
    L.append(f"- 締切まで30日以上あり、いまから準備が間に合う制度: **{len(listable)}件**")
    L.append(f"- 締切まで30日を切った制度: **{closing}件**(本書には掲載していません。理由は末尾)")
    L.append(
        f"- 公募上限額の合計(参考値): 上限1億円以下・公表分{inc_n}件で **{fmt_amount(total_amt)}**"
        f"(非公表{unknown_n}件・1億円超{over_n}件は含めず)"
    )
    L.append("")

    L.append("## 金額帯の分布(上限額・公表分)")
    L.append("")
    L.append("| 上限額の帯 | 件数 |")
    L.append("|---|---|")
    for label, lo, hi in AMOUNT_BANDS:
        n = sum(1 for i in items if lo < (i.get("max_amount") or 0) <= hi)
        L.append(f"| {label} | {n}件 |")
    L.append(f"| 上限額 非公表(要確認) | {unknown_n}件 |")
    L.append("")

    L.append("## 目的別マップ")
    L.append("")
    cat_labels = [c[0] for c in CATEGORIES] + ["その他"]
    by_cat = {c: [] for c in cat_labels}
    for it in listable:
        by_cat[categorize(it)].append(it)
    for cat in cat_labels:
        # 沖縄の制度を先頭に、次いで締切が近い順(3層ルール内での優先度)
        group = sorted(
            by_cat[cat],
            key=lambda i: (TAG_PRIORITY.get(i.get("tag"), 9), days_left(i.get("deadline"), today) or 9999),
        )
        L.append(f"### {cat}({len(group)}件)")
        L.append("")
        if partner:
            L.append(f"声かけ例: {TALK_EXAMPLES[cat]}")
            L.append("")
        if group:
            for it in group[:CAT_PICK_MAX]:
                L.append(item_line(it, today))
            if len(group) > CAT_PICK_MAX:
                L.append(f"- ほか{len(group) - CAT_PICK_MAX}件(データベースに掲載中)")
        else:
            L.append("- 今月、締切に余裕のある該当制度はありません")
        L.append("")

    L.append(f"## 締切カレンダー(向こう{CALENDAR_MONTHS}ヶ月・締切30日以上の制度のみ)")
    L.append("")
    horizon = 92  # 「向こう3ヶ月」の看板と中身を一致させる(2026-08-01再検証で修正)
    cal = [i for i in listable if (days_left(i.get("deadline"), today) or 0) <= horizon]
    cal.sort(key=lambda i: i.get("deadline") or "9999")
    cur_month = None
    for it in cal:
        m = month_of(it.get("deadline"))
        if m != cur_month:
            L.append(f"### {m} 締切")
            L.append("")
            cur_month = m
        L.append(
            f"- {it.get('deadline')} | {it.get('name', '(名称不明)')}"
            f"({area_label(it)} / 上限: {fmt_amount(it.get('max_amount'))})"
        )
    if not cal:
        L.append("該当期間に締切を迎える制度はありません。")
    L.append("")

    L.append("## 締切30日未満の制度を載せない理由")
    L.append("")
    L.append(
        f"現在{closing}件ありますが、直前のご案内では書類やgBizIDの準備が間に合わないため、"
        "本書では制度名を挙げていません。"
    )
    if partner:
        L.append(
            "お客さまへの個別のご案内が必要な場合は、ALLGROUP提携窓口(ムスブ担当)までご相談ください。"
        )
    else:
        L.append(
            f"LINE登録者の方へは**締切の約1か月前から**個別アラートをお届けしています。"
            f"👉 {SITE_URL}"
        )
    L.append("")
    L.append("---")
    L.append("")
    if partner:
        L.append(
            "本資料は「沖縄企業のミカタ」AI編集部が制度データベースから自動生成し、"
            "人間スタッフが確認のうえお渡ししています。掲載・提携のご相談: ALLGROUP 提携部"
        )
    else:
        L.append(
            "この白書は「沖縄企業のミカタ」(運営: ALLGROUP)のAI編集部が制度データベースから自動生成し、"
            "人間スタッフが内容を確認したうえで公開しています。"
        )
    L.append(DISCLAIMER)
    L.append("")
    return "\n".join(L)


def main():
    dry_run = "--dry-run" in sys.argv
    preview = "--preview" in sys.argv
    today = datetime.now(JST).date()
    data = load_json(DATA_PATH)

    premium = build(data, today, partner=False)
    partner = build(data, today, partner=True)

    if dry_run:
        print(premium)
        print("\n\n========== PARTNER ==========\n\n")
        print(partner)
        return

    ym = today.strftime("%Y-%m")
    os.makedirs(PREMIUM_DIR, exist_ok=True)
    os.makedirs(PARTNER_DIR, exist_ok=True)
    p1 = os.path.join(PREMIUM_DIR, f"{ym}_hakusho.md")
    p2 = os.path.join(PARTNER_DIR, f"{ym}_partner.md")
    with open(p1, "w", encoding="utf-8") as f:
        f.write(premium)
    with open(p2, "w", encoding="utf-8") as f:
        f.write(partner)

    if preview:
        print(f"ym={ym}")
        print(f"premium=posts/note/premium/{ym}_hakusho.md")
        print(f"partner=reports/partner/{ym}_partner.md")
    else:
        print(f"[ok] {p1}\n[ok] {p2}")


if __name__ == "__main__":
    main()
