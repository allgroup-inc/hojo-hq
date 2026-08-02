#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — Kindle年鑑「沖縄補助金白書(年版)」原稿ジェネレータ(収益構造v2)
(決裁: 2026-08-02 小柳さん承認 / docs/note収益化_運営計画.md v2)

data/subsidies.json と data/gone_archive.json から、KDP(Kindle出版)用の
原稿Markdownと出版設定メモを books/kindle/ に生成する。
出版操作(KDPアカウント・表紙・アップロード)は人間が行う。

方針(CLAUDE.md 絶対ルール#1 / KDPのAIコンテンツ申告義務):
- 書籍は賞味期限が長いため、巻頭と付録に「YYYY-MM-DD時点のスナップショット」を明記し、
  必ず最新情報の確認先(サイト)を案内する
- 個別制度の掲載は締切30日以上のもののみ・締切日と出典URLを併記
- AI利用申告文・出版設定メモを同時生成し、申告漏れを防ぐ

使い方:
  python scripts/generate_kindle_annual.py            # 原稿+設定メモ生成
  python scripts/generate_kindle_annual.py --dry-run  # 標準出力のみ
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from generate_note import (  # noqa: E402
    BASE, DATA_PATH, DISCLAIMER, JST, PROMOTE_MIN_DAYS, TAG_PRIORITY,
    area_label, days_left, fmt_amount, load_json, potential_sum,
)
from generate_monthly_report import AMOUNT_BANDS, CATEGORIES, categorize  # noqa: E402

OUT_DIR = os.path.join(BASE, "books", "kindle")
ARCHIVE_PATH = os.path.join(BASE, "data", "gone_archive.json")
SITE_URL = "https://allgroup-inc.github.io/hojo-hq/?utm_source=kindle&utm_medium=book&utm_campaign=annual"

AI_DISCLOSURE = (
    "本書の本文は、著者(沖縄企業のミカタ AI編集部/運営: ALLGROUP)が構築した"
    "制度データベースをもとにAIが生成し、人間スタッフが内容を確認・編集したものです。"
    "KDPのコンテンツガイドラインに基づき、AI生成コンテンツであることを申告しています。"
)


def build_manuscript(data, gone_items, today):
    items = data.get("items", [])
    year = today.year
    dstr = today.strftime("%Y年%m月%d日")
    listable = [
        i for i in items
        if (dl := days_left(i.get("deadline"), today)) is not None and dl >= PROMOTE_MIN_DAYS
    ]
    total_amt, inc_n, over_n, unknown_n = potential_sum(items)
    okinawa_n = sum(1 for i in items if i.get("tag") == "okinawa")

    L = []
    L.append(f"# 沖縄補助金白書 {year}年版")
    L.append("")
    L.append("## AIが毎日見張っている、沖縄の企業が使えるお金の記録")
    L.append("")
    L.append("---")
    L.append("")
    L.append("## はじめに — 本書の読み方(必ずお読みください)")
    L.append("")
    L.append(
        f"本書は、国(jGrants)と沖縄県・市町村の補助金・助成金をAIが毎日巡回して集めている"
        f"データベースの、**{dstr}時点のスナップショット**です。"
    )
    L.append("")
    L.append(
        "補助金は毎週、生まれては締め切られていきます。本書に載っている個別の制度は、"
        "お読みになる時点では締め切られている可能性があります。本書の価値は個別の制度情報そのもの"
        "ではなく、**「沖縄の企業が使えるお金の全体構造」を一冊で俯瞰できること**に置いています。"
    )
    L.append("")
    L.append(f"最新の制度情報は、毎日更新している無料サイトでご確認ください: {SITE_URL}")
    L.append("")
    L.append(DISCLAIMER)
    L.append("")
    L.append("---")
    L.append("")

    L.append("## 第1章 全体像 — 沖縄の企業が使えるお金は、いま何件あるか")
    L.append("")
    L.append(f"{dstr}時点でデータベースに掲載中の制度は**{len(items)}件**。")
    L.append(f"うち沖縄県・市町村が出している制度が{okinawa_n}件、残りの大半は沖縄の企業も使える全国公募です。")
    L.append("")
    L.append("### 上限額の分布")
    L.append("")
    L.append("| 上限額の帯 | 件数 |")
    L.append("|---|---|")
    for label, lo, hi in AMOUNT_BANDS:
        n = sum(1 for i in items if lo < (i.get("max_amount") or 0) <= hi)
        L.append(f"| {label} | {n}件 |")
    L.append(f"| 上限額 非公表(要確認) | {unknown_n}件 |")
    L.append("")
    L.append(
        f"注目すべきは「非公表」の多さです。上限額が公表されていない制度が{unknown_n}件——"
        "金額欄だけを見て応募先を選ぶと、候補の約半分を最初から捨てることになります。"
    )
    L.append("")
    L.append(
        f"中小企業の現実的なレンジ(上限1億円以下・公表分)は{inc_n}件で、その公募上限額を単純合計すると"
        f"**{fmt_amount(total_amt)}**になります(理論値であり受給額・採択を保証するものではありません。"
        f"1億円超の大型公募{over_n}件は含めていません)。"
    )
    L.append("")

    L.append("## 第2章 目的別マップ — 自社に関係する棚はどこか")
    L.append("")
    L.append("制度は「何のためのお金か」で見ると探しやすくなります。以下は本書時点の分野別の棚卸しです。")
    L.append("")
    cat_labels = [c[0] for c in CATEGORIES] + ["その他"]
    by_cat = {c: [] for c in cat_labels}
    for it in listable:
        by_cat[categorize(it)].append(it)
    for cat in cat_labels:
        group = sorted(
            by_cat[cat],
            key=lambda i: (TAG_PRIORITY.get(i.get("tag"), 9), days_left(i.get("deadline"), today) or 9999),
        )
        L.append(f"### {cat}({len(group)}件)")
        L.append("")
        if group:
            for it in group[:3]:
                L.append(
                    f"- **{it.get('name', '(名称不明)')}** — {area_label(it)} / "
                    f"締切: {it.get('deadline', '要確認')} / 上限: {fmt_amount(it.get('max_amount'))}"
                )
                L.append(f"  - 原文: {it.get('source_url', '')}")
            if len(group) > 3:
                L.append(f"- ほか{len(group) - 3}件(巻末付録に全件掲載)")
        else:
            L.append("- 本書時点で締切に余裕のある該当制度はありません")
        L.append("")

    L.append("## 第3章 消えていった制度の記録")
    L.append("")
    if gone_items:
        L.append(
            "本章は、締切日を迎えてデータベースから姿を消した制度の記録です。"
            "「知っていれば出せたのに」を来年減らすための、失われた選択肢のリストです。"
        )
        L.append("")
        for g in gone_items[:50]:
            L.append(f"- {g.get('name', '(名称不明)')}(締切: {g.get('deadline', '不明')})")
        if len(gone_items) > 50:
            L.append(f"- ほか{len(gone_items) - 50}件")
    else:
        L.append(
            "定点観測は始まったばかりで、本書の版では消えた制度の蓄積がまだ多くありません。"
            "来年版では、1年分の「消えた制度」の記録をここに収める予定です。"
        )
    L.append("")

    L.append("## 第4章 もらい損ねを防ぐ3つの習慣")
    L.append("")
    L.append("データベースを毎日動かしてわかった、実務的な結論は3つだけです。")
    L.append("")
    L.append("**1. 探すのを月1回のイベントにしない。** 制度は毎週入れ替わります。自分で毎日見るのが難しければ、毎日見ている仕組みを使ってください。")
    L.append("")
    L.append("**2. 金額欄が空欄でも捨てない。** 上限額非公表の制度が約半分あります。「要確認」の制度こそ、公募要領を1枚めくる価値があります。")
    L.append("")
    L.append("**3. 締切30日を切ったら、次回公募の準備に回す。** 駆け込み申請は書類の質が落ちます。gBizID(国の電子申請アカウント)の取得だけ先に済ませておくのが一番の近道です。")
    L.append("")

    L.append("## 付録 掲載制度一覧(本書時点・締切30日以上のもの)")
    L.append("")
    L.append(f"※{dstr}時点。締切順。お読みの時点では終了している場合があります。")
    L.append("")
    for it in sorted(listable, key=lambda i: i.get("deadline") or "9999"):
        L.append(
            f"- {it.get('deadline')} | {it.get('name', '(名称不明)')}"
            f"({area_label(it)} / 上限: {fmt_amount(it.get('max_amount'))})"
        )
    L.append("")
    L.append("---")
    L.append("")
    L.append("## おわりに・本書について")
    L.append("")
    L.append(AI_DISCLOSURE)
    L.append("")
    L.append(f"最新情報・無料の締切アラート(締切の約1か月前から): {SITE_URL}")
    L.append("")
    L.append(f"© {year} ALLGROUP / 沖縄企業のミカタ AI編集部")
    L.append("")
    return "\n".join(L)


def build_kdp_memo(today):
    year = today.year
    return f"""# KDP出版設定メモ — 沖縄補助金白書 {year}年版
(このメモは出版操作をする人間用。決裁: 2026-08-02 小柳さん)

| 項目 | 設定値(案) |
|---|---|
| タイトル | 沖縄補助金白書 {year}年版 |
| サブタイトル | AIが毎日見張っている、沖縄の企業が使えるお金の記録 |
| 著者名 | 沖縄企業のミカタ AI編集部 |
| 出版者 | ALLGROUP |
| 価格 | 980円(KDPセレクト登録・印税70%) |
| カテゴリ | ビジネス・経済 > 中小企業経営 / 起業・開業 |
| キーワード | 沖縄, 補助金, 助成金, 中小企業, 資金調達, 事業承継, AI |
| **AIコンテンツ申告** | **「AI生成コンテンツを含む」を必ず申告する**(本文はAI生成+人間編集。KDP規約上の義務) |

## 出版手順(小柳さん or たかしくん)
1. kdp.amazon.co.jp でアカウント作成(振込先・税務情報の登録が必要)
2. 「+電子書籍」→ 上記の設定を入力(AI申告を忘れない)
3. 原稿: books/kindle/{year}_hakusho_genko.md をWord等に貼り付けてアップロード(またはEPUB変換)
4. 表紙: Canvaで作成(ネイビー#00335C×オレンジ#F88800のブランド配色)。ご依頼いただければ文言・構成案を出します
5. 審査(通常72時間以内)→ 出版

## 位置づけ(v2計画)
- 直接収益は小さくても可。「Amazonに白書がある」ことがパートナー版白書(B2B)の営業ツールになる
- まず本書1冊で反応を見る。四半期化・来年版の判断は実売とB2B営業での使われ方を見て再議論(見直し: 2026-11-30)
"""


def main():
    dry_run = "--dry-run" in sys.argv
    today = datetime.now(JST).date()
    data = load_json(DATA_PATH)
    archive = load_json(ARCHIVE_PATH) if os.path.exists(ARCHIVE_PATH) else {"items": []}

    manuscript = build_manuscript(data, archive.get("items", []), today)
    memo = build_kdp_memo(today)

    if dry_run:
        print(manuscript[:3000])
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    p1 = os.path.join(OUT_DIR, f"{today.year}_hakusho_genko.md")
    p2 = os.path.join(OUT_DIR, f"{today.year}_hakusho_kdp_memo.md")
    with open(p1, "w", encoding="utf-8") as f:
        f.write(manuscript)
    with open(p2, "w", encoding="utf-8") as f:
        f.write(memo)
    print(f"[ok] {p1}\n[ok] {p2}")


if __name__ == "__main__":
    main()
