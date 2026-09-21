#!/usr/bin/env python3
"""❸ もらいわすれ堂 Instagram フォロワー数の記録。

目標: もらいわすれ堂 Instagram(@moradou.okinawa)フォロワー1,000人/12ヶ月。
実測値をリポジトリに残し、週20人ペースの検証・早期警報の土台を作る。

2通りで動く(トークンは Secret 登録待ちのため、手動の受け皿も用意):
  1) 自動: 環境変数 MORADOU_IG_TOKEN があれば followers_count を取得して追記。
     MORADOU_IG_USER_ID も併せてあれば Facebook Login 方式(graph.facebook.com)、
     無ければ Instagram Login 方式(graph.instagram.com の /me)とみなす。
     Instagram Login 方式は Facebookページ連携が要らないぶん、開通が早い。
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
# 接続方式は2つある。どちらを使うかは MORADOU_IG_USER_ID の有無で決まる(main参照)。
#  - Instagram Login: Facebookページ連携が不要。graph.instagram.com の /me を叩く
#  - Facebook Login : Facebookページ連携が必要。graph.facebook.com の /{ig-user-id} を叩く
GRAPH_IG = "https://graph.instagram.com/v21.0"
GRAPH_FB = "https://graph.facebook.com/v21.0"


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
    if not token:
        data["last_status"] = "未接続(MORADOU_IG_TOKEN なし)。--set で手動記録可"
        save(data)
        print("record_ig_followers: 未接続のため記録スキップ(状態は明記済み)")
        return

    # IDが無ければ Instagram Login 方式とみなす(この方式は /me で自分を指すのでIDが要らない)。
    if ig_id:
        url, mode = f"{GRAPH_FB}/{ig_id}", "facebook-login"
    else:
        url, mode = f"{GRAPH_IG}/me", "instagram-login"

    q = urllib.parse.urlencode({"fields": "followers_count,username", "access_token": token})
    req = urllib.request.Request(f"{url}?{q}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
    except Exception as e:  # noqa: BLE001
        # 種類名だけだと 401(トークン失効)と 404(ID違い)が同じ HTTPError になり原因が追えない。
        code = getattr(e, "code", None)
        detail = f"{type(e).__name__} {code}" if code else type(e).__name__
        data["last_status"] = f"取得不可({mode} / {detail})"
        save(data)
        print(f"record_ig_followers: 取得不可 {mode} {e}")
        return

    followers = body.get("followers_count")
    if followers is None:
        data["last_status"] = f"取得不可(followers_count なし: {body})"
        save(data)
        print("record_ig_followers: followers_count が取れませんでした")
        return

    record(data, day, followers, mode)
    data["last_status"] = "ready"
    save(data)
    print(f"record_ig_followers: {day} フォロワー{followers}人 を記録")


if __name__ == "__main__":
    main()
