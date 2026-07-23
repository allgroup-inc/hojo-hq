#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂 週次レポート初号機(統括ユイさん・達成くんフォーマット準拠)
.claude/agents/yui.md の週次レポート6項目に沿って、リポジトリ内データから
自動で埋まる部分を生成し、Plausible/LINE 由来の指標は「確認先」を案内する。

設計の芯:
- 北極星は「実受給額カウンター」。登録数・PVが伸びても受給が動かなければ「進んでいない」と書く
- 機械が断定できない数字(ファネル転換率・受給報告)は勝手に埋めない。確認先を示し、記入欄を残す
- 生成はL4(自動)。数字の解釈と方針変更は月次のみ(週次で右往左往しない=yui.md判断原則)
出力: reports/fukugiiro/<週>_weekly.md と reports/fukugiiro/latest.md
"""
import json
import os
import re
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
SEIDO = os.path.join(BASE, "data", "fukugiiro", "seido.json")
JUKYU = os.path.join(BASE, "data", "fukugiiro", "jukyu_report.json")  # LINE開設後に蓄積(無ければ0)
DAICHO = os.path.join(BASE, "docs", "失敗台帳.md")
AREA_DIR = os.path.join(BASE, "site", "fukugiiro", "area")
KIT_DIR = os.path.join(BASE, "site", "fukugiiro", "kit")
OUT_DIR = os.path.join(BASE, "reports", "fukugiiro")

KPI_KEISAI = 150  # CLAUDE.md 支持KPI: 掲載制度数 常時150件以上


def load_seido():
    with open(SEIDO, encoding="utf-8") as f:
        return json.load(f)


def load_jukyu():
    """受給報告(LINE開設後に蓄積)。無ければ空。"""
    try:
        with open(JUKYU, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"reports": [], "total_amount": 0, "households": 0}


def daicho_summary():
    """失敗台帳のステータスサマリー行を読む。"""
    try:
        with open(DAICHO, encoding="utf-8") as f:
            txt = f.read()
    except Exception:
        return None
    # 「| 2 | 0 | 2 | 0 | 0 |」形式のサマリー行(記録/分析中/監視中/クローズ/再発)を探す
    m = re.search(r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|", txt)
    if not m:
        return None
    keys = ["記録", "分析中", "監視中", "クローズ", "再発"]
    return dict(zip(keys, (int(x) for x in m.groups())))


def count_dirs(path):
    if not os.path.isdir(path):
        return 0
    return sum(1 for n in os.listdir(path) if os.path.isdir(os.path.join(path, n)))


def freshness(updated_at):
    """updated_at('YYYY-MM-DD HH:MM')から鮮度を判定。KPI: 更新遅延24時間以内。"""
    try:
        dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
    except Exception:
        return "不明", None
    hours = (datetime.now(JST) - dt).total_seconds() / 3600
    label = "✅ 24時間以内" if hours <= 24 else f"⚠ {hours:.0f}時間経過(要確認)"
    return label, hours


def pick_bottleneck(db, jukyu, keisai):
    """今週の単一ボトルネック+単一ネクストアクションを、受給完了への距離で自動判定。
    yui.md『迷ったら受給完了に近づくか?で判断』/『施策は1ヶ月に1つ』に従い最優先を1つだけ返す。"""
    verified = sum(1 for it in db["items"] if it.get("status") == "検証済み")
    line_ready = os.path.exists(os.path.join(BASE, "data", "fukugiiro", "line_state.json"))
    reports = len(jukyu.get("reports", []))

    # 受給完了に一番近い順のゲートで、最初に詰まっている段を返す
    if not line_ready:
        return (
            "受給報告の受け皿(LINE)が未開設で、北極星『実受給額』が構造的に計測できない。"
            "サイトで『受け取れた』が起きても、それを数える場所がまだ無い。",
            "LINE公式アカウントを開設する(手順は docs/フクギイロ_LINE開設パッケージ.md に完備)。"
            "開設後、機械側が友だち追加ボタン実装と受給報告フローを即日稼働できる。",
        )
    if reports == 0:
        return (
            "LINEは開設済みだが受給報告がまだ0件。ファネル最終段(申請着手→受給)の実測が始まっていない。",
            "既存のLINE友だちに『振り込まれたら教えてください』の初回配信を送る(文面は開設パッケージ§5)。",
        )
    if keisai < KPI_KEISAI:
        return (
            f"掲載制度数 {keisai}件がKPI(常時{KPI_KEISAI}件)に未達。診断の当たりが薄く、"
            "特に市町村独自制度が空で『自分の街の制度』が出せていない。",
            "沖縄県・市町村の制度を収集対象に追加する(自治体の規約確認が前提。沖縄市・うるま市へ架電中)。",
        )
    return (
        "主要ゲートは通過。次の律速は『診断→LINE登録率』の改善(M4条件30%)。",
        "診断完了画面のLINE誘導の文言・位置をA/B候補で1つだけ変更し、みがきの会で効果検証する。",
    )


def main():
    now = datetime.now(JST)
    week_tag = now.strftime("%G-W%V")  # ISO週(例: 2026-W30)
    db = load_seido()
    jukyu = load_jukyu()
    items = db["items"]
    keisai = db.get("count", len(items))
    verified = sum(1 for it in items if it.get("status") == "検証済み")
    youkakunin = sum(1 for it in items if it.get("status") == "要確認")
    verified_rate = (verified / keisai * 100) if keisai else 0

    # カテゴリ別内訳
    cats = {}
    for it in items:
        cats[it.get("category", "不明")] = cats.get(it.get("category", "不明"), 0) + 1
    cat_line = " / ".join(f"{k} {v}" for k, v in sorted(cats.items(), key=lambda x: -x[1]))

    fresh_label, _ = freshness(db.get("updated_at", ""))
    n_area = count_dirs(AREA_DIR)
    n_kit = count_dirs(KIT_DIR)
    daicho = daicho_summary()
    total_amount = jukyu.get("total_amount", 0)
    households = jukyu.get("households", 0)
    bottleneck, nextaction = pick_bottleneck(db, jukyu, keisai)

    daicho_txt = (
        f"記録{daicho['記録']} / 監視中{daicho['監視中']} / クローズ{daicho['クローズ']} / **再発{daicho['再発']}**"
        if daicho else "台帳読込不可"
    )

    md = f"""# もらいわすれ堂 週次レポート {week_tag}

生成: {now.strftime('%Y-%m-%d %H:%M')} JST(統括ユイさん・自動生成 / 達成くんフォーマット準拠)
北極星: **実受給額カウンター**。登録・PVが伸びても、この数字が動かなければ「進んでいない」。

---

## 0. 今週の結論(単一ネクストアクション)

> **ボトルネック**: {bottleneck}
>
> **次の一手(今週これだけ)**: {nextaction}

*yui.md原則: 施策は1ヶ月に1つしか変えない / 迷ったら「受給完了に近づくか」で判断。*

## 1. 北極星 — 実受給額 / 支援世帯

| 指標 | 今週 | 状態 |
|---|---|---|
| 実受給額(累計) | {total_amount:,} 円 | {'計測中' if total_amount else '受付開始前(LINE開設待ち)'} |
| 支援世帯数(受給報告) | {households} 世帯 | {'計測中' if households else '受付開始前(LINE開設待ち)'} |

受給報告が入り始めると、この表が自動で埋まります(data/fukugiiro/jukyu_report.json)。

## 2. ファネル(Plausibleで確認 → 数値を記入)

計測は稼働中ですが、外部ダッシュボードの数値は自動取得できないため**確認先**を示します。
ダッシュボード: https://plausible.io/allgroup-inc.github.io

| 段 | イベント名 | 今週の値(手動記入) |
|---|---|---|
| サイト来訪 | pageview | |
| 診断開始 | shindan_start | |
| 診断完了 | shindan_complete | |
| 準備シート表示 | kit_click | |
| 印刷 | kit_print / print_click | |
| 共有 | share_click | |
| 再訪(つづき) | shindan_resume | |
| 受給ずみマーク | seido_done_mark | |

*転換率(完了÷開始、シート÷完了)を毎週ここに残すと、離脱段が一目でわかります。*

## 3. 掲載・データ品質(自動集計)

| 指標 | 値 | KPI | 判定 |
|---|---|---|---|
| 掲載制度数 | {keisai} 件 | 常時{KPI_KEISAI}件以上 | {'✅' if keisai >= KPI_KEISAI else f'🟡 あと{KPI_KEISAI - keisai}件'} |
| 検証済み | {verified} 件({verified_rate:.0f}%) | 誤情報ゼロ | {'✅ 全件検証済み' if youkakunin == 0 else f'要確認 {youkakunin}件'} |
| データ鮮度 | {db.get('updated_at','?')} | 24時間以内 | {fresh_label} |
| 市町村ページ | {n_area} ページ | 41市町村 | {'✅' if n_area >= 41 else '🟡'} |
| 申請準備シート | {n_kit} ページ | 全制度 | {'✅' if n_kit >= keisai else '🟡'} |

カテゴリ別: {cat_line}

## 4. 品質・統制(ニドナシ機構 / eval)

- 失敗台帳: {daicho_txt}
- CI/検査: validate(スキーマ・整合・禁止表現)・check_lp(全ページ可視文言)・node test(診断ロジック9)= マージ必須ゲート
- 自律度: 金・契約=人間のみ / 公開・配信=承認後 / 収集・生成=自動+事後監査

## 5. 資産の積み上がり(再訪しやすさ)

- 診断のつづき機能・受給ずみマーク・準備シートのチェック/メモ保存 = すべて端末内保存(外部送信なし)
- SNS投稿下書き: posts/fukugiiro/(検証済み{verified}件から生成)。Instagram開設後に承認→投稿

## 6. 夫婦の週労働時間(手動記入)

> 今週の合計時間: ____ 時間(先週比 ____)
>
> *増えていたら「自動化の設計ミス」として記録する(yui.md)。数字を追うより仕組みで減らす。*

---

## 人間の次アクション(この週の依頼)

1. 上の**セクション0の一手**を進める(いまは最上位の詰まりを1つだけ)
2. ファネル(§2)の数値をPlausibleから転記(5分)
3. 週労働時間(§6)を記入

*本レポートは自動生成の初号機です。項目の過不足は月次レビューでユイさん+みがきの会が見直します。*
"""

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{week_tag}_weekly.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(OUT_DIR, "latest.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(f"週次レポート生成: {path}")
    print(f"  掲載{keisai}件 / 検証済み{verified}件 / 要確認{youkakunin}件 / 市町村{n_area} / シート{n_kit}")


if __name__ == "__main__":
    main()
