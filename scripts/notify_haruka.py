#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遥さんへ「今週のIG投稿案」をLINEでプッシュ通知する(2026-08-11 小柳さん指示)。

送り先(常に終了0):
- 遥さん直送: FUKUGIIRO_LINE_CHANNEL_ACCESS_TOKEN + HARUKA_LINE_USER_ID(もらいわすれ堂OAのみ)
- Secrets未設定の間は本文をログ表示するだけ(ボードURLは常に有効)

**ミカタ(企業のミカタ/GLOW)のLINE OAは使わない**(2026-08-11 小柳さん指摘で撤去。
フクギイロとGLOWは別会社・別ブランドのため、もらいわすれ堂の連絡をミカタOAに流さない)。
内部連絡用のプッシュであり、県民向け配信ではない(CV単一ルールの対象外)。
"""
import json
import os
import sys
import urllib.request

BOARD_URL = "https://allgroup-inc.github.io/hojo-hq/staff/haruka/"
NETA = os.path.join(os.path.dirname(__file__), "..", "data", "fukugiiro", "ig_neta.json")
SEIDO = os.path.join(os.path.dirname(__file__), "..", "data", "fukugiiro", "seido.json")

# 照合の状態を1文字で。遥さんは「投稿前の情報確認に時間がかかる」と言っているので、
# ボードを開く前に「どれが自分で確認しなくていい案か」が分かるようにする(2026-09-24)
MARK = {"ok": "✅", "warn": "⚠️", "unknown": "❓"}


def _seido_index():
    try:
        with open(SEIDO, encoding="utf-8") as f:
            items = json.load(f).get("items", [])
    except Exception:
        return {}
    return {(i.get("source_url") or "").rstrip("/"): i for i in items}


def check_state(it, idx):
    s = idx.get((it.get("source_url") or "").rstrip("/"))
    if not s:
        return "unknown"
    return "ok" if s.get("verified") else "warn"


def build_text():
    try:
        with open(NETA, encoding="utf-8") as f:
            d = json.load(f)
        idx = _seido_index()
        items = d.get("items", [])[:5]
        # 照合ずみを先に。ボードの並びと揃える(2026-09-24)
        order = {"ok": 0, "warn": 1, "unknown": 2}
        items = sorted(items, key=lambda it: (order[check_state(it, idx)], it.get("no", 0)))
        titles = "\n".join(
            f"{MARK[check_state(it, idx)]} 案{it['no']}: {it['title']}" for it in items)
        n_ok = sum(1 for it in items if check_state(it, idx) == "ok")
        week = d.get("week", "")
    except Exception:
        titles, week, n_ok = "(データ読込不可)", "", 0
    return (f"🌈 今週のIG投稿案({week})が届きました\n\n{titles}\n\n"
            f"✅=原文と照合ずみ(確認し直さずに使えます・{n_ok}件) "
            f"⚠️=金額や期限は断定しないでください ❓=未照合なので出典をご確認ください\n\n"
            f"キャプションのコピー・画像の方向性・注意点はこちら👇\n{BOARD_URL}\n\n"
            "投稿したら、毎週の投稿案メールに返信で「案1 投稿した」と一言ください。\n"
            "※LINEはこちらから送る専用で、返信を受け取る仕組みがありません"
            "(2026-09-24 修正。それまで受け取れないLINEへの報告をお願いしていました)。")


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
    try:
        if fg_token and haruka:
            push(fg_token, haruka, text)
            print("[ok] 遥さんへ直送しました(もらいわすれ堂OA)")
        else:
            print("[info] もらいわすれ堂OAのSecrets未設定のため表示のみ(ミカタOAは使わない)。ボード: " + BOARD_URL)
            print(text)
    except Exception as e:
        # 通知失敗でも週次レポ本体は止めない(ボードは生成済み・URLで見られる)
        print(f"[warn] LINE送信失敗(継続): {type(e).__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
