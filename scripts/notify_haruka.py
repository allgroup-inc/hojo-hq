#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遥さんへ「今週のIG投稿案」をLINEでプッシュ通知する(2026-08-11 小柳さん指示)。

送り先(常に終了0):
- **既定は「文面の生成・表示だけ」。自動では送らない**(2026-11-07 小柳さん承認・3段階ルール
  docs/議事/議事_20261106_自動ルーティンの3段階ルール.md「外部送信は事前承認」)
- 送るのは、宛先(遥さん)・内容を確認した個別の承認があるときだけ。承認は、表示した文面の
  承認コード(宛先と本文から計算する)を NOTIFY_HARUKA_APPROVAL に渡すことで行う。文面が
  1文字でも変われば承認コードも変わるので、別の内容・別の回には使い回せない
- 送るときに要るもの: FUKUGIIRO_LINE_CHANNEL_ACCESS_TOKEN + HARUKA_LINE_USER_ID(もらいわすれ堂OAのみ)
  + NOTIFY_HARUKA_APPROVAL(承認コード)。どれかが欠ければ送らない
- トークン・宛先IDの値はログに出さない

**ミカタ(企業のミカタ/GLOW)のLINE OAは使わない**(2026-08-11 小柳さん指摘で撤去。
フクギイロとGLOWは別会社・別ブランドのため、もらいわすれ堂の連絡をミカタOAに流さない)。
内部連絡用のプッシュであり、県民向け配信ではない(CV単一ルールの対象外)。
"""
import hashlib
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
    idx = {(i.get("source_url") or "").rstrip("/"): i for i in items}
    idx.update({i["id"]: i for i in items if i.get("id")})
    return idx


def check_state(it, idx):
    s = idx.get(it.get("seido_id")) or idx.get((it.get("source_url") or "").rstrip("/"))
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


RECIPIENT = "haruka"  # 宛先の名前(承認コードに含める。宛先IDの値は含めない)


def approval_code(text, recipient=RECIPIENT):
    """宛先と本文から承認コードを作る。内容か宛先が変われば別のコードになる。"""
    return hashlib.sha256(f"{recipient}\n{text}".encode("utf-8")).hexdigest()[:16]


def main(env=None, sender=None):
    env = os.environ if env is None else env
    sender = sender or push
    text = build_text()
    code = approval_code(text)
    fg_token = env.get("FUKUGIIRO_LINE_CHANNEL_ACCESS_TOKEN", "")
    haruka = env.get("HARUKA_LINE_USER_ID", "")
    approval = env.get("NOTIFY_HARUKA_APPROVAL", "").strip()
    if approval != code:
        reason = "承認なし" if not approval else "承認コードが今回の文面と一致しない"
        print(f"[info] {reason}のため送信しません(文面の表示のみ・ミカタOAは使わない)。")
        print(f"[info] 宛先: 遥さん(もらいわすれ堂OA) / 承認コード: {code}")
        print("[info] 送る場合は、宛先と下の内容を確認のうえ、この承認コードで個別に承認してください。")
        print(text)
        return 0
    if not (fg_token and haruka):
        print("[info] 承認はあるが、もらいわすれ堂OAのSecretsが未設定のため送信しません。ボード: " + BOARD_URL)
        return 0
    try:
        sender(fg_token, haruka, text)
        print("[ok] 承認に基づき、遥さんへ送りました(もらいわすれ堂OA)")
    except Exception as e:
        # 通知失敗でも週次レポ本体は止めない(ボードは生成済み・URLで見られる)
        print(f"[warn] LINE送信失敗(継続): {type(e).__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
