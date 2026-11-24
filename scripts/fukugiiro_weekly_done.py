#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂の週次(週次レポート+今週のIG投稿案)が、今週分まで作れているかを見る。

2026-11-23、週次の定時(月曜 0:00 UTC)が GitHub の混雑で4時間23分遅れて動いた。
遅れは9月の約1時間半から毎週のびていた。IG投稿案の下書きを作る定期作業は
11:02(日本時間)に起動するため、先週の案のまま下書きを作りかけた。

そこで定時を2本にした(日曜 19:23 UTC = 月曜 4:23 JST が本番、月曜 1:41 UTC = 10:41 JST が予備)。
予備の定時は、今週分がもうできていれば何もしない。このスクリプトがその判定と、
作り終えたあとの確認(今週分ができていなければ失敗にして知らせる)を受け持つ。

使い方:
  python scripts/fukugiiro_weekly_done.py --gate EVENT   # run=true/false を出力(GITHUB_OUTPUT 用)
  python scripts/fukugiiro_weekly_done.py --verify       # 今週分ができていなければ終了コード1
  python scripts/fukugiiro_weekly_done.py --self-test
"""
import argparse
import datetime as dt
import json
import os
import sys
import tempfile

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
JST = dt.timezone(dt.timedelta(hours=9))


def week_tag(now=None):
    """日本時間のISO週(例: 2026-W48)。weekly_report_fukugiiro.py の %G-W%V と同じ。"""
    d = (now or dt.datetime.now(dt.timezone.utc)).astimezone(JST)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def status(base=BASE, now=None):
    """(週, レポートの有無, IG投稿案の週)"""
    w = week_tag(now)
    report = os.path.exists(os.path.join(base, "reports", "fukugiiro", f"{w}_weekly.md"))
    try:
        with open(os.path.join(base, "data", "fukugiiro", "ig_neta.json"), encoding="utf-8") as f:
            neta_week = json.load(f).get("week")
    except (OSError, ValueError):
        neta_week = None
    return w, report, neta_week


def done(base=BASE, now=None):
    w, report, neta_week = status(base, now)
    return report and neta_week == w


def gate(event, base=BASE, now=None):
    """定時の起動だけ、今週分ができていれば止める。手動・push は従来どおり動かす。"""
    return not (event == "schedule" and done(base, now))


def self_test():
    ok = bad = 0

    def check(label, cond):
        nonlocal ok, bad
        if cond:
            ok += 1
        else:
            bad += 1
            print(f"  NG {label}")

    sun_night = dt.datetime(2026, 11, 22, 19, 23, tzinfo=dt.timezone.utc)   # 月曜 4:23 JST
    mon_noon = dt.datetime(2026, 11, 23, 1, 41, tzinfo=dt.timezone.utc)     # 月曜 10:41 JST
    check("日曜の夜(UTC)でも月曜の週番号", week_tag(sun_night) == "2026-W48")
    check("月曜の朝も同じ週", week_tag(mon_noon) == "2026-W48")
    check("日本時間の日曜は前の週", week_tag(dt.datetime(2026, 11, 22, 14, 0, tzinfo=dt.timezone.utc)) == "2026-W47")

    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "reports", "fukugiiro"))
        os.makedirs(os.path.join(tmp, "data", "fukugiiro"))
        neta = os.path.join(tmp, "data", "fukugiiro", "ig_neta.json")

        def put_neta(week):
            with open(neta, "w", encoding="utf-8") as f:
                json.dump({"week": week, "items": []}, f)

        put_neta("2026-W47")
        check("先週の案のままなら未完了", not done(tmp, mon_noon))
        check("未完了なら予備の定時は動く", gate("schedule", tmp, mon_noon))
        open(os.path.join(tmp, "reports", "fukugiiro", "2026-W48_weekly.md"), "w").close()
        check("レポートだけでは未完了(IG案が先週のまま)", not done(tmp, mon_noon))
        put_neta("2026-W48")
        check("両方そろえば完了", done(tmp, mon_noon))
        check("完了なら予備の定時は止まる", not gate("schedule", tmp, mon_noon))
        check("手動実行は完了でも動く", gate("workflow_dispatch", tmp, mon_noon))
        check("push は完了でも動く", gate("push", tmp, mon_noon))
        os.remove(neta)
        check("IG案のファイルが無ければ未完了", not done(tmp, mon_noon))

    print(f"自己テスト: OK {ok} / NG {bad}")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", metavar="EVENT")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.gate:
        run = gate(a.gate)
        w, report, neta_week = status()
        print(f"run={'true' if run else 'false'}")
        print(f"今週={w} レポート={'あり' if report else 'なし'} IG投稿案の週={neta_week}", file=sys.stderr)
        return 0
    if a.verify:
        w, report, neta_week = status()
        if report and neta_week == w:
            print(f"今週分({w})の週次レポートとIG投稿案ができています")
            return 0
        print(f"::error::今週分({w})ができていません: レポート={'あり' if report else 'なし'}"
              f" / IG投稿案の週={neta_week}。予備の定時(月曜10:41 JST)か手動実行で作り直してください")
        return 1
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
