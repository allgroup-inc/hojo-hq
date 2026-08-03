#!/usr/bin/env python3
"""❸ もらいわすれ堂 Instagram フォロワー数の記録。

目標: もらいわすれ堂 Instagram(@moradou.okinawa)フォロワー1,000人/12ヶ月。
実測値をリポジトリに残し、週20人ペースの検証・早期警報の土台を作る。

2通りで動く(トークンは Secret 登録待ちのため、手動の受け皿も用意):
  1) 自動: 環境変数 MORADOU_IG_USER_ID と MORADOU_IG_TOKEN があれば
     Instagram Graph API から followers_count を取得して追記。
  2) 手動: `python scripts/record_ig_followers.py --set 42`
     で今日のフォロワー数を手入力で記録(トークン接続前の暫定運用)。

未接続・取得不可のときも last_status に明記して静かに欠損させない。
CIから毎日呼んでも落ちないよう、常に終了コード0で返す。
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "kpi", "moradou_ig_followers.json")
GRAPH = "https://graph.facebook.com/v21.0"


def load():
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            return json.load(f)
    return {
        "note": "❸ もらいわすれ堂 Instagram(@moradou.okinawa)フォロワー数。"
                "target=1,000人(公開から12ヶ月)。定常ペース目標は週20人。",
        "target": 1000,
        "account": "@moradou.okinawa",
        "last_checked": None,
        "last_status": "未記録",
        "weekly_net_increase": None,
        "history": [],
    }


def save(data):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def record(data, day, followers, source):
    entry = {"date": day, "followers": followers, "source": source}
    hist = [h for h in data["history"] if h.get("date") != day]
    hist.append(entry)
    data["history"] = sorted(hist, key=lambda h: h["date"])
    # 週次ペース(約7日前との差)。履歴が足りなければ null。
    now = datetime.now(JST)
    week_ago = (now - timedelta(days=8)).strftime("%Y-%m-%d")
    past = [h for h in data["history"] if h["date"] <= week_ago and h.get("followers") is not None]
    if past and followers is not None:
        data["weekly_net_increase"] = followers - past[-1]["followers"]
    else:
        data["weekly_net_increase"] = None


def main():
    p = argparse.ArgumentParser(description="もらいわすれ堂 IGフォロワー数を記録")
    p.add_argument("--set", type=int, default=None, metavar="N",
                   help="フォロワー数を手動で記録(トークン接続前の暫定運用)")
    p.add_argument("--date", default=None, help="記録日 YYYY-MM-DD(既定: 今日)")
    args = p.parse_args()

    data = load()
    now = datetime.now(JST)
    data["last_checked"] = now.strftime("%Y-%m-%d %H:%M")
    day = args.date or now.strftime("%Y-%m-%d")

    # 手動モード
    if args.set is not None:
        record(data, day, args.set, "manual")
        data["last_status"] = "manual"
        save(data)
        print(f"record_ig_followers: {day} フォロワー{args.set}人 を手動記録")
        return

    # 自動モード
    ig_id = os.environ.get("MORADOU_IG_USER_ID", "")
    token = os.environ.get("MORADOU_IG_TOKEN", "")
    if not ig_id or not token:
        data["last_status"] = "未接続(MORADOU_IG_USER_ID / MORADOU_IG_TOKEN なし)。--set で手動記録可"
        save(data)
        print("record_ig_followers: 未接続のため記録スキップ(状態は明記済み)")
        return

    q = urllib.parse.urlencode({"fields": "followers_count,username", "access_token": token})
    req = urllib.request.Request(f"{GRAPH}/{ig_id}?{q}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
    except Exception as e:  # noqa: BLE001
        data["last_status"] = f"取得不可({type(e).__name__})"
        save(data)
        print(f"record_ig_followers: 取得不可 {e}")
        return

    followers = body.get("followers_count")
    if followers is None:
        data["last_status"] = f"取得不可(followers_count なし: {body})"
        save(data)
        print("record_ig_followers: followers_count が取れませんでした")
        return

    record(data, day, followers, "graph-api")
    data["last_status"] = "ready"
    save(data)
    print(f"record_ig_followers: {day} フォロワー{followers}人 を記録")


if __name__ == "__main__":
    main()
