#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沖縄企業のミカタ(サイト本体) Plausible ファネル自動取り込み。
fetch_plausible_funnel.py(もらいわすれ堂用)と同じ設計を、サイト本体の
3段ファネル(診断開始→診断実行→LINE誘導タップ)向けに適用したもの。
data/hojo/funnel.json を生成する。

- PLAUSIBLE_API_KEY 未設定なら何も書かず exit 0(週次レポは未接続表示にフォールバック)
- 集計値のみ。個人識別子は扱わない。APIキーはログに出さない。
- LINEタップは site/go/shindan/ が送る line_redirect(channel=shindan) を使う。
  channel を絞らずに event:name だけで集計すると、もらいわすれ堂などの
  他チャネルの line_redirect まで混ざるため、必ず channel フィルタをかける。

使い方:
  PLAUSIBLE_API_KEY=xxx python scripts/fetch_hojo_funnel.py   # 取得して funnel.json 生成
  python scripts/fetch_hojo_funnel.py --self-test             # build_funnel を golden で検証
"""
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import date

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(BASE, "data", "hojo", "funnel.json")
GOLDEN = os.path.join(BASE, "tests", "golden_hojo_funnel.json")

FUNNEL = [
    ("hojo_shindan_start", "診断開始"),
    ("hojo_shindan_complete", "診断実行(結果表示)"),
    ("line_tap", "LINE誘導タップ"),
]
LINE_TAP_EVENT = "line_redirect"
LINE_TAP_CHANNEL = "shindan"


def build_funnel(counts):
    """{event_name: count} から stages/key_rates/worst_drop を組む(純粋関数)。"""
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

    start = g("hojo_shindan_start")
    complete = g("hojo_shindan_complete")
    tap = g("line_tap")
    key_rates = {
        "complete_rate": (complete / start) if start > 0 else None,
        "line_cvr": (tap / complete) if complete > 0 else None,
    }

    worst = None
    for i, s in enumerate(stages):
        if s["drop_rate"] is None:
            continue
        if worst is None or s["drop_rate"] > worst["drop_rate"]:
            worst = {"stage": s["key"],
                     "label": stages[i - 1]["label"] + "→" + s["label"],
                     "drop_rate": s["drop_rate"]}

    return {"stages": stages, "key_rates": key_rates, "worst_drop": worst}


def fetch_counts(api_key, site_id, period, api_base):
    """Plausible Stats API から診断イベント2種(event:name)と、
    line_redirect(channel=shindan に絞った件数)を取得する。"""
    h = {"Authorization": "Bearer " + api_key}

    qs1 = urllib.parse.urlencode({
        "site_id": site_id, "period": period,
        "property": "event:name", "metrics": "events", "limit": "100",
    })
    req1 = urllib.request.Request(
        api_base.rstrip("/") + "/api/v1/stats/breakdown?" + qs1, headers=h)
    with urllib.request.urlopen(req1, timeout=30) as r:
        data1 = json.load(r)
    counts = {}
    for row in data1.get("results", []):
        name = row.get("name")
        if name in ("hojo_shindan_start", "hojo_shindan_complete"):
            counts[name] = int(row.get("events", 0) or 0)

    qs2 = urllib.parse.urlencode({
        "site_id": site_id, "period": period,
        "property": "event:props:channel", "metrics": "events", "limit": "100",
        "filters": "event:name==" + LINE_TAP_EVENT,
    })
    req2 = urllib.request.Request(
        api_base.rstrip("/") + "/api/v1/stats/breakdown?" + qs2, headers=h)
    with urllib.request.urlopen(req2, timeout=30) as r:
        data2 = json.load(r)
    tap = 0
    for row in data2.get("results", []):
        if row.get("channel") == LINE_TAP_CHANNEL:
            tap = int(row.get("events", 0) or 0)
    counts["line_tap"] = tap
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
            "complete_rate": _r(fn["key_rates"]["complete_rate"]),
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
        print("[info] PLAUSIBLE_API_KEY 未設定: ファネル取得をスキップ(週次レポは未接続表示にフォールバック)")
        return 0
    site_id = os.environ.get("PLAUSIBLE_SITE_ID", "allgroup-inc.github.io")
    period = os.environ.get("PLAUSIBLE_PERIOD", "7d")
    api_base = os.environ.get("PLAUSIBLE_API_BASE", "https://plausible.io")
    try:
        counts = fetch_counts(api_key, site_id, period, api_base)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:500]
        except Exception:
            pass
        print(f"[warn] Plausible Stats API {e.code} {e.reason}: {body}")
        print("[info] ファネル取得をスキップ(週次レポは未接続表示にフォールバック)")
        return 0
    fn = build_funnel(counts)
    out = {"schema_version": 1, "updated_at": date.today().isoformat(),
           "period": period, "source": "plausible-stats-api"}
    out.update(fn)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    ws = fn["worst_drop"]["stage"] if fn["worst_drop"] else "-"
    print(f"funnel.json 生成: 段数{len(fn['stages'])} / 最大離脱段={ws}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
