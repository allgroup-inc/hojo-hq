#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遥さんへ「今週のIG投稿案」をLINEでプッシュ通知する(2026-08-11 小柳さん指示)。

送り先の優先順位(Secretsの有無で自動フォールバック・常に終了0):
1. 遥さん直送: FUKUGIIRO_LINE_CHANNEL_ACCESS_TOKEN + HARUKA_LINE_USER_ID
2. 小柳さん経由(1タップ転送): LINE_CHANNEL_ACCESS_TOKEN + LINE_ADMIN_USER_ID(ミカタOA・既存)
3. どちらも無ければ本文を標準出力に表示するだけ(ボードURLは常に有効)

内部連絡用のプッシュであり、県民向け配信ではない(CV単一ルールの対象外)。
"""
import json
import os
import sys
import urllib.request

BOARD_URL = "https://allgroup-inc.github.io/hojo-hq/staff/haruka/"
NETA = os.path.join(os.path.dirname(__file__), "..", "data", "fukugiiro", "ig_neta.json")


def build_text():
    try:
        with open(NETA, encoding="utf-8") as f:
            d = json.load(f)
        titles = "\n".join(f"案{it['no']}: {it['title']}" for it in d.get("items", [])[:5])
        week = d.get("week", "")
    except Exception:
        titles, week = "(データ読込不可)", ""
    return (f"🌈 今週のIG投稿案({week})が届きました\n\n{titles}\n\n"
            f"キャプションのコピー・画像の方向性・注意点はこちら👇\n{BOARD_URL}\n\n"
            "使う/使わないはLINEで「案1 投稿した」のように返信してください。")


def push(token, to, text):
    payload = json.dumps({"to": to, "messages": [{"type": "text", "text": text}]}).encode("utf-8")
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push", data=payload, method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token})
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.status


def main():
    text = build_text()
    fg_token = os.environ.get("FUKUGIIRO_LINE_CHANNEL_ACCESS_TOKEN", "")
    haruka = os.environ.get("HARUKA_LINE_USER_ID", "")
    mk_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    admin = os.environ.get("LINE_ADMIN_USER_ID", "")
    try:
        if fg_token and haruka:
            push(fg_token, haruka, text)
            print("[ok] 遥さんへ直送しました(もらいわすれ堂OA)")
        elif mk_token and admin:
            push(mk_token, admin, "【遥さんへ転送お願いします】\n" + text)
            print("[ok] 小柳さんのLINEへ送信(遥さんへ1タップ転送用)")
        else:
            print("[info] LINE未接続のため表示のみ。ボード: " + BOARD_URL)
            print(text)
    except Exception as e:
        # 通知失敗でも週次レポ本体は止めない(ボードは生成済み・URLで見られる)
        print(f"[warn] LINE送信失敗(継続): {type(e).__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
