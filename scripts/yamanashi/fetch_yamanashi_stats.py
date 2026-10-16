#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""もらいわすれ堂 山梨版 週次の数字取り込み(2026-09-23 新設)。

山梨版はもらいわすれ堂プロパティ(G-TQMX3MPFSR = Secrets GA4_PROPERTY_ID)に相乗りし、
イベント名の ymn_ 接頭辞とページパス /hojo-hq/yamanashi/ で沖縄版と数字を分けている
(build_yamanashi.py の fgTrack ラッパー・2026-09-20)。ここではその分離を前提に、

1. ymn_ で始まる全イベントの回数・人数(直近7日と、その前の7日)
2. /hojo-hq/yamanashi/ 配下のページ表示・訪問者
3. /hojo-hq/go/ymn- 転送ページの表示回数(= LINEへ送った数。ymn-top / ymn-shindan 別)

を取り、data/yamanashi/stats.json と docs/山梨版_週次数字.md に書く。

- GA4_SA_JSON / GA4_PROPERTY_ID が無ければ何も書かず exit 0(静かにスキップ)
- 集計値のみ。個人識別子は扱わない。鍵・トークンはログに出さない
- 週次レポのワークフロー(fukugiiro-weekly-report.yml)から呼ぶ。
  生成物2つは同ワークフローの git add リストにも載せてある(再発防止メモ:
  addリストから漏れた生成物は消える)

使い方:
  GA4_SA_JSON='{...}' GA4_PROPERTY_ID=123456789 python3 scripts/yamanashi/fetch_yamanashi_stats.py
  python3 scripts/yamanashi/fetch_yamanashi_stats.py --self-test   # 整形ロジックだけ検証
"""
import json
import os
import sys
from datetime import date, timedelta

BASE = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(BASE, "scripts"))

OUT_JSON = os.path.join(BASE, "data", "yamanashi", "stats.json")
OUT_MD = os.path.join(BASE, "docs", "山梨版_週次数字.md")

SITE_PATH = "/hojo-hq/yamanashi/"
GO_PATH = "/hojo-hq/go/ymn-"

# 週次レポで名前を出す主要イベント(それ以外の ymn_ も all_events に全部残す)。
# ページ表示はここに入れない: GA4の自動 page_view は fgTrack を通らないので
# ymn_page_view は常に0になり、上段の実測PVと並ぶと紛らわしい(2026-09-23 初回実行で確認)
MAIN_EVENTS = [
    ("ymn_shindan_start", "診断を始めた"),
    ("ymn_shindan_complete", "診断の結果を見た"),
    ("ymn_line_add_click", "LINE登録ボタンを押した"),
    ("ymn_line_redirect", "LINEへ進んだ(転送)"),
    ("ymn_jukyu_houkoku_click", "受け取り報告を送った"),
]


def _begins(field, value):
    return {"filter": {"fieldName": field,
                       "stringFilter": {"matchType": "BEGINS_WITH", "value": value}}}


def fetch_window(token, prop, start, end):
    """1週間ぶんの3種の数字を取る。startとendは 'YYYY-MM-DD'。"""
    from ga4_client import run_report  # noqa: PLC0415

    win = {"start": start, "end": end}

    # 1) ymn_ イベント一覧
    data = run_report(token, prop, {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": "eventName"}],
        "metrics": [{"name": "eventCount"}, {"name": "totalUsers"}],
        "dimensionFilter": _begins("eventName", "ymn_"),
        "limit": 200,
    })
    events = {}
    for row in data.get("rows") or []:
        name = row["dimensionValues"][0]["value"]
        events[name] = {"events": int(row["metricValues"][0]["value"]),
                        "users": int(row["metricValues"][1]["value"])}
    win["events"] = events

    # 2) 山梨版ページ全体の表示・訪問者
    data = run_report(token, prop, {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "metrics": [{"name": "screenPageViews"}, {"name": "activeUsers"}],
        "dimensionFilter": _begins("pagePath", SITE_PATH),
    })
    rows = data.get("rows") or []
    vals = rows[0]["metricValues"] if rows else []
    win["pageviews"] = int(vals[0]["value"]) if vals else 0
    win["visitors"] = int(vals[1]["value"]) if len(vals) > 1 else 0

    # 3) /go/ymn-* 転送ページ(= LINEへ送った数。入口別)
    data = run_report(token, prop, {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": "pagePath"}],
        "metrics": [{"name": "screenPageViews"}],
        "dimensionFilter": _begins("pagePath", GO_PATH),
        "limit": 50,
    })
    go = {}
    for row in data.get("rows") or []:
        # "/hojo-hq/go/ymn-top/" → "ymn-top"
        slug = row["dimensionValues"][0]["value"].rstrip("/").rsplit("/", 1)[-1]
        go[slug] = go.get(slug, 0) + int(row["metricValues"][0]["value"])
    win["line_forward"] = go
    return win


def build_markdown(stats):
    """stats.json の中身から人が読む週次メモを組む(数字は断定できる実測のみ)。"""
    this, prev = stats["this_week"], stats["prev_week"]

    def diff(a, b):
        d = a - b
        return f"(前週 {b} / {'+' if d >= 0 else ''}{d})"

    lines = [
        "# もらいわすれ堂 山梨版 週次の数字",
        "",
        f"集計日: {stats['fetched_at']} / 期間: {this['start']}〜{this['end']}(前週: {prev['start']}〜{prev['end']})",
        "出どころ: GA4(もらいわすれ堂プロパティに相乗り。ymn_ 接頭辞と /yamanashi/ パスで山梨だけを数えている)",
        "",
        "## サイト全体",
        "",
        f"- ページが見られた回数: **{this['pageviews']}** {diff(this['pageviews'], prev['pageviews'])}",
        f"- 見に来た人の数: **{this['visitors']}** {diff(this['visitors'], prev['visitors'])}",
        "",
        "## 主要な動き(回数)",
        "",
    ]
    for key, label in MAIN_EVENTS:
        a = this["events"].get(key, {}).get("events", 0)
        b = prev["events"].get(key, {}).get("events", 0)
        lines.append(f"- {label}: **{a}** {diff(a, b)}")

    total_go = sum(this["line_forward"].values())
    prev_go = sum(prev["line_forward"].values())
    lines += ["", "## LINEへ送った数(転送ページ別)", "",
              f"- 合計: **{total_go}** {diff(total_go, prev_go)}"]
    for slug in sorted(set(this["line_forward"]) | set(prev["line_forward"])):
        a = this["line_forward"].get(slug, 0)
        b = prev["line_forward"].get(slug, 0)
        lines.append(f"  - {slug}: {a} {diff(a, b)}")

    film = sorted((k, v["events"]) for k, v in this["events"].items()
                  if k.startswith("ymn_film_scene_"))
    if film:
        lines += ["", "## 冒頭フィルム(写真4枚)がどこまで見られたか", ""]
        for k, v in film:
            lines.append(f"- {k.replace('ymn_film_scene_', '場面 ')}: {v}回")

    lines += ["", "---", "",
              "この数字は毎週月曜の朝に自動で更新されます"
              "(scripts/yamanashi/fetch_yamanashi_stats.py)。",
              ""]
    return "\n".join(lines)


def self_test():
    sample = {
        "fetched_at": "2026-09-23",
        "this_week": {"start": "2026-09-16", "end": "2026-09-22",
                      "pageviews": 76, "visitors": 30,
                      "events": {"ymn_page_view": {"events": 76, "users": 30},
                                 "ymn_shindan_start": {"events": 4, "users": 3},
                                 "ymn_film_scene_s1": {"events": 2, "users": 2}},
                      "line_forward": {"ymn-top": 5, "ymn-shindan": 4}},
        "prev_week": {"start": "2026-09-09", "end": "2026-09-15",
                      "pageviews": 40, "visitors": 18,
                      "events": {"ymn_page_view": {"events": 40, "users": 18}},
                      "line_forward": {"ymn-top": 2}},
    }
    md = build_markdown(sample)
    assert "**76** (前週 40 / +36)" in md, md
    assert "- 診断を始めた: **4** (前週 0 / +4)" in md
    assert "- 合計: **9** (前週 2 / +7)" in md
    assert "場面 s1: 2回" in md
    assert "必ず" not in md  # 禁止語(断定)をこの文書に入れない
    print("[ok] self-test: 週次メモの整形は期待どおり")


def main():
    if "--self-test" in sys.argv:
        self_test()
        return
    if not (os.environ.get("GA4_SA_JSON") and os.environ.get("GA4_PROPERTY_ID")):
        print("[skip] GA4_SA_JSON / GA4_PROPERTY_ID が無いためスキップ(週次レポは前回の数字のまま)")
        return
    from ga4_client import get_token  # noqa: PLC0415
    token = get_token()
    prop = os.environ["GA4_PROPERTY_ID"]

    today = date.today()
    this_start, this_end = today - timedelta(days=7), today - timedelta(days=1)
    prev_start, prev_end = today - timedelta(days=14), today - timedelta(days=8)

    stats = {
        "region": "yamanashi",
        "fetched_at": today.isoformat(),
        "source": "ga4-data-api",
        "this_week": fetch_window(token, prop, this_start.isoformat(), this_end.isoformat()),
        "prev_week": fetch_window(token, prop, prev_start.isoformat(), prev_end.isoformat()),
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(build_markdown(stats))
    print(f"[ok] 山梨版の週次数字を書き出した: PV {stats['this_week']['pageviews']} / "
          f"LINE転送 {sum(stats['this_week']['line_forward'].values())}")


if __name__ == "__main__":
    main()
