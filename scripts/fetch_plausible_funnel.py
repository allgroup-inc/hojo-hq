#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ Plausible ファネル自動取り込み(計測レポート設計 第2段階)
Stats API からイベント件数を取得し data/fukugiiro/funnel.json を生成する。
- PLAUSIBLE_API_KEY 未設定なら何も書かず exit 0(週次レポは手動フォールバック)
- 集計値のみ。個人識別子は扱わない。APIキーはログに出さない。
使い方:
  PLAUSIBLE_API_KEY=xxx python scripts/fetch_plausible_funnel.py   # 取得して funnel.json 生成
  python scripts/fetch_plausible_funnel.py --self-test             # build_funnel を golden で検証
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(BASE, "data", "fukugiiro", "funnel.json")
GOLDEN = os.path.join(BASE, "tests", "golden_funnel.json")

# 線形ファネル(順序が離脱段の計算に使われる)
FUNNEL = [
    ("shindan_start", "診断開始"),
    ("shindan_step_q2", "Q2到達"),
    ("shindan_step_q3", "Q3到達"),
    ("shindan_step_q4", "Q4到達"),
    ("shindan_step_q5", "Q5到達"),
    ("shindan_complete", "診断完了(1件以上)"),
    ("line_add_click", "LINE誘導クリック"),
]
ENGAGEMENT_KEYS = ["kit_click", "seido_done_mark", "jukyu_report_click", "shindan_zero"]


def build_funnel(counts):
    """{event_name: count} から stages/engagement/key_rates/worst_drop を組む(純粋関数)。"""
    def g(k):
        return int(counts.get(k, 0) or 0)

    stages = []
    prev = None
    for key, label in FUNNEL:
        c = g(key)
        if prev is None or prev <= 0:
            cvr = None
            drop = None
        else:
            cvr = c / prev
            drop = 1 - cvr
        stages.append({"key": key, "label": label, "count": c,
                       "cvr_from_prev": cvr, "drop_rate": drop})
        prev = c

    start = g("shindan_start")
    complete = g("shindan_complete")
    zero = g("shindan_zero")
    line = g("line_add_click")
    finished = complete + zero
    key_rates = {
        "finish_rate": (finished / start) if start > 0 else None,
        "line_cvr": (line / complete) if complete > 0 else None,
        "zero_rate": (zero / finished) if finished > 0 else None,
    }

    worst = None
    for i, s in enumerate(stages):
        if s["drop_rate"] is None:
            continue
        if worst is None or s["drop_rate"] > worst["drop_rate"]:
            worst = {"stage": s["key"],
                     "label": stages[i - 1]["label"] + "→" + s["label"],
                     "drop_rate": s["drop_rate"]}

    engagement = {k: g(k) for k in ENGAGEMENT_KEYS}
    return {"stages": stages, "engagement": engagement,
            "key_rates": key_rates, "worst_drop": worst}


def fetch_counts(api_key, site_id, period, api_base):
    """Plausible Stats API(event:name の breakdown)から {event_name: count} を取得。"""
    qs = urllib.parse.urlencode({
        "site_id": site_id, "period": period,
        "property": "event:name", "metrics": "events", "limit": "100",
    })
    url = api_base.rstrip("/") + "/api/v1/stats/breakdown?" + qs
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + api_key})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    counts = {}
    for row in data.get("results", []):
        name = row.get("name")
        if name is not None:
            counts[name] = int(row.get("events", 0) or 0)
    return counts


def _r(x):
    return None if x is None else round(x, 4)


def self_test():
    with open(GOLDEN, encoding="utf-8") as f:
        golden = json.load(f)
    failed = 0
    for case in golden["cases"]:
        fn = build_funnel(case["counts"])
        exp = case["expect"]
        got_stage = fn["worst_drop"]["stage"] if fn["worst_drop"] else None
        checks = {
            "worst_drop_stage": got_stage,
            "line_cvr": _r(fn["key_rates"]["line_cvr"]),
            "finish_rate": _r(fn["key_rates"]["finish_rate"]),
            "zero_rate": _r(fn["key_rates"]["zero_rate"]),
        }
        for k, want in exp.items():
            if checks.get(k) != want:
                failed += 1
                print(f"[SELFTEST FAIL] {case['name']}: {k} expected {want} got {checks.get(k)}")
    total = len(golden["cases"])
    if failed:
        print(f"自己テスト失敗: {failed} 件")
        return 1
    print(f"自己テスト OK: {total} ケース(集計・離脱段・率が一致)")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    api_key = os.environ.get("PLAUSIBLE_API_KEY")
    if not api_key:
        print("[info] PLAUSIBLE_API_KEY 未設定: ファネル取得をスキップ(週次レポは確認先表示にフォールバック)")
        return 0
    site_id = os.environ.get("PLAUSIBLE_SITE_ID", "allgroup-inc.github.io")
    period = os.environ.get("PLAUSIBLE_PERIOD", "7d")
    api_base = os.environ.get("PLAUSIBLE_API_BASE", "https://plausible.io")
    counts = fetch_counts(api_key, site_id, period, api_base)
    fn = build_funnel(counts)
    out = {"schema_version": 1, "updated_at": date.today().isoformat(),
           "period": period, "source": "plausible-stats-api"}
    out.update(fn)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    ws = fn["worst_drop"]["stage"] if fn["worst_drop"] else "-"
    print(f"funnel.json 生成: 段数{len(fn['stages'])} / 最大離脱段={ws}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
