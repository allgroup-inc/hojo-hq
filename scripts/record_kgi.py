#!/usr/bin/env python3
"""KGI(LINE友だち数)の日次記録。

背景: KGI=LINE登録1,000社/12ヶ月 なのに、実測値がリポジトリのどこにも
残らない(weekly_report.py はLINEにpush送信するだけで使い捨て)。
本スクリプトは LINE Insight API の友だち数を data/kpi/line_followers.json に
毎日追記し、週20社ペースの検証と早期警報(閾値割れ検知)の土台を作る。

必要な環境変数: LINE_CHANNEL_ACCESS_TOKEN(update.yml から渡す)
任意: LINE_ADMIN_USER_ID(あれば、実測が3日以上取れないとき管理者へ警報push)
未接続・集計待ちのときも last_status に明記する(静かに欠損させない)。
さらに ready が3日以上途切れたら警報を1回だけ送る(計測の無言停止対策)。
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


def alert_if_stale(data, now):
    """ready が3日以上途切れていたら管理者LINEへ1回だけ警報(無言停止対策)。"""
    last_ready = data.get("last_ready_date")
    if not last_ready or data.get("stale_alerted"):
        return
    days = (now.date() - datetime.strptime(last_ready, "%Y-%m-%d").date()).days
    if days < 3:
        return
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    to = os.environ.get("LINE_ADMIN_USER_ID", "")
    data["stale_alerted"] = True
    if not (token and to):
        print(f"record_kgi: 警報対象(ready途絶{days}日)だが通知先未設定")
        return
    text = (f"⚠️ KGI計測が{days}日間取得できていません(最終成功 {last_ready})。\n"
            "LINE Insight APIかトークンの状態を確認してください。\n"
            "詳細: data/kpi/line_followers.json の last_status")
    payload = json.dumps({"to": to, "messages": [{"type": "text", "text": text}]}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push", data=payload, method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30)
        print(f"record_kgi: 計測途絶{days}日の警報を送信")
    except Exception as e:  # noqa: BLE001
        print(f"record_kgi: 警報送信も失敗 {e}")


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
        alert_if_stale(data, now)
        save(data)
        print(f"record_kgi: 取得不可 {e}")
        return

    if body.get("status") != "ready":
        data["last_status"] = f"集計待ち(status={body.get('status')})"
        alert_if_stale(data, now)
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
    data["last_ready_date"] = now.strftime("%Y-%m-%d")
    data["stale_alerted"] = False

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
