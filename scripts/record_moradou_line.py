#!/usr/bin/env python3
"""もらいわすれ堂(株式会社フクギイロ)の LINE 公式アカウントの友だち数を記録する(読み取り専用)。

- 記録先: data/kpi/moradou_line_followers.json(もらいわすれ堂専用)
  ※ data/kpi/line_followers.json は沖縄企業のミカタ(株式会社GLOW)用で別物。混ぜない
- 使う API: LINE Messaging API の集計(GET /v2/bot/insight/followers)だけ。
  **メッセージの送信は一切しない**(push・broadcast などの送信用 API は呼ばない)
- 必要な環境変数: FUKUGIIRO_LINE_CHANNEL_ACCESS_TOKEN(もらいわすれ堂の OA。GitHub Secrets から渡す)
  未登録でも失敗にしない。状態を「未接続」と記録して終了 0(週次レポートの他の処理を止めない)
- トークンの値はログ・記録ファイルに出さない。失敗時は種類と HTTP ステータスだけを残す

承認: 2026-11-07 小柳さん「LINE計測の安全修正・Draft PR作成を承認」
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "kpi", "moradou_line_followers.json")
TOKEN_ENV = "FUKUGIIRO_LINE_CHANNEL_ACCESS_TOKEN"
INSIGHT_URL = "https://api.line.me/v2/bot/insight/followers?date={date}"


def load(path=OUT):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {
        "note": "もらいわすれ堂(株式会社フクギイロ)のLINE公式アカウントの友だち数。"
                "LINE Insight API の前日確定値。ミカタ(GLOW)の line_followers.json とは別物。",
        "kgi_target": 10000,
        "last_checked": None,
        "last_status": "未記録",
        "last_success_at": None,
        "history": [],
    }


def save(data, path=OUT):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fetch(token, date, opener=urllib.request.urlopen):
    """集計 API を GET で呼ぶ。送信用の API は呼ばない。"""
    req = urllib.request.Request(INSIGHT_URL.format(date=date), method="GET",
                                 headers={"Authorization": "Bearer " + token})
    with opener(req, timeout=30) as r:
        return json.load(r)


def describe(e):
    """失敗の説明。HTTP ステータスまで残し(403=権限・401=トークン無効)、トークンや URL は出さない。"""
    if isinstance(e, urllib.error.HTTPError):
        return f"取得不可(HTTP {e.code})"
    return f"取得不可({type(e).__name__})"


def record(env=None, now=None, path=OUT, opener=urllib.request.urlopen):
    env = os.environ if env is None else env
    now = now or datetime.now(JST)
    data = load(path)
    data["last_checked"] = now.strftime("%Y-%m-%d %H:%M")
    token = env.get(TOKEN_ENV, "")
    if not token:
        data["last_status"] = "未接続(トークン未登録)"
        save(data, path)
        print("record_moradou_line: トークン未登録のため記録しません(状態は記録済み)")
        return data

    day = now - timedelta(days=1)
    try:
        body = fetch(token, day.strftime("%Y%m%d"), opener)
    except Exception as e:  # noqa: BLE001
        data["last_status"] = describe(e)
        save(data, path)
        print(f"record_moradou_line: {data['last_status']}")
        return data

    if body.get("status") != "ready":
        data["last_status"] = f"集計待ち(status={body.get('status')})"
        save(data, path)
        print(f"record_moradou_line: {data['last_status']}")
        return data

    date = day.strftime("%Y-%m-%d")
    entry = {"date": date, "followers": body.get("followers"),
             "targeted_reaches": body.get("targetedReaches"), "blocks": body.get("blocks")}
    hist = [h for h in data.get("history", []) if h.get("date") != date]
    hist.append(entry)
    data["history"] = sorted(hist, key=lambda h: h["date"])
    data["last_status"] = "ready"
    data["last_success_at"] = now.strftime("%Y-%m-%d %H:%M")
    save(data, path)
    print(f"record_moradou_line: {date} 友だち{entry['followers']}人を記録")
    return data


def summary(path=OUT):
    """週次レポート用の1行。友だち数・取得日時・失敗時の状態を必ず書く。"""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return "未接続(記録なし。もらいわすれ堂のLINEトークン未登録)"
    hist = data.get("history") or []
    status = data.get("last_status") or "未記録"
    checked = data.get("last_checked") or "-"
    if hist:
        last = hist[-1]
        text = f"**{last.get('followers', '?')}人**({last.get('date', '')}時点・取得 {data.get('last_success_at') or '-'})"
        if status != "ready":
            text += f"<br>⚠ 最新の取得: {status}({checked})"
        return text
    return f"未取得: {status}(確認 {checked})"


if __name__ == "__main__":
    record()
    sys.exit(0)
