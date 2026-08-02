#!/usr/bin/env python3
"""KGI(LINE友だち数)の日次記録。

背景: KGI=LINE登録1,000社/12ヶ月 なのに、実測値がリポジトリのどこにも
残らない(weekly_report.py はLINEにpush送信するだけで使い捨て)。
本スクリプトは LINE Insight API の友だち数を data/kpi/line_followers.json に
毎日追記し、週20社ペースの検証と早期警報(閾値割れ検知)の土台を作る。

必要な環境変数: LINE_CHANNEL_ACCESS_TOKEN(update.yml から渡す)
未接続・集計待ちのときも last_status に明記する(静かに欠損させない)。
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "kpi", "line_followers.json")


def load():
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    return {
        "note": "KGI実測: ミカタLINE公式の友だち数(LINE Insight API・前日確定値)。"
                "kgi_target=1,000社(2027-07頃)。定常ペース目標は週20社。",
        "kgi_target": 1000,
        "last_checked": None,
        "last_status": "未記録",
        "history": [],
    }


def save(data):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    data = load()
    now = datetime.now(JST)
    data["last_checked"] = now.strftime("%Y-%m-%d %H:%M")

    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        data["last_status"] = "未接続(LINE_CHANNEL_ACCESS_TOKEN なし)"
        save(data)
        print("record_kgi: 未接続のため記録スキップ(状態は明記済み)")
        return

    date = (now - timedelta(days=1)).strftime("%Y%m%d")
    req = urllib.request.Request(
        f"https://api.line.me/v2/bot/insight/followers?date={date}",
        headers={"Authorization": "Bearer " + token},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
    except Exception as e:  # noqa: BLE001
        data["last_status"] = f"取得不可({type(e).__name__})"
        save(data)
        print(f"record_kgi: 取得不可 {e}")
        return

    if body.get("status") != "ready":
        data["last_status"] = f"集計待ち(status={body.get('status')})"
        save(data)
        print("record_kgi: 集計待ち")
        return

    day = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    entry = {
        "date": day,
        "followers": body.get("followers"),
        "targeted_reaches": body.get("targetedReaches"),
        "blocks": body.get("blocks"),
    }
    hist = [h for h in data["history"] if h.get("date") != day]
    hist.append(entry)
    data["history"] = sorted(hist, key=lambda h: h["date"])
    data["last_status"] = "ready"

    # 週次ペース(直近7日間の純増)。履歴が7日分たまるまでは null。
    week_ago = (now - timedelta(days=8)).strftime("%Y-%m-%d")
    past = [h for h in data["history"] if h["date"] <= week_ago]
    if past and entry.get("followers") is not None and past[-1].get("followers") is not None:
        data["weekly_net_increase"] = entry["followers"] - past[-1]["followers"]
    else:
        data["weekly_net_increase"] = None

    save(data)
    print(f"record_kgi: {day} 友だち{entry['followers']}人 を記録")


if __name__ == "__main__":
    main()
