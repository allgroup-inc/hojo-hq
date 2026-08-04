#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SMTPでメールを送る汎用スクリプト(GitHub Actions send-email.yml から呼ぶ)。

用途: もらいわすれ堂の運用連絡(遥さんへのInstagram投稿依頼など)を、
claude.ai のコネクタに依存せず、リポジトリ側から確実に自動送信する。

必要な環境変数(GitHub Secrets):
  SMTP_HOST   例: xxxx.sakura.ne.jp(さくらのメール SMTPサーバ名)
  SMTP_PORT   587(STARTTLS・既定) または 465(SSL)
  SMTP_USER   info@fukugiiro.com(送信に使うメールアドレス=SMTP認証ユーザー)
  SMTP_PASS   そのメールボックスのパスワード
  SMTP_FROM   任意。差出人アドレス(未指定なら SMTP_USER)

引数:
  --to        宛先(必須)
  --subject   件名(必須)
  --body      本文(短いとき)
  --body-file 本文をファイルから読む(長文・多言語で安全。リポジトリ内パス)
  --attach    添付ファイル(リポジトリ内パス。複数可)
  --from-name 差出人の表示名(既定: もらいわすれ堂 運営)

秘密情報は出力しない。成功時のみ "sent to <to>" を表示する。
"""
import argparse
import mimetypes
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formataddr


def main():
    ap = argparse.ArgumentParser(description="Send an email via SMTP")
    ap.add_argument("--to", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--body", default="")
    ap.add_argument("--body-file", default=None)
    ap.add_argument("--attach", action="append", default=[])
    ap.add_argument("--from-name", default="もらいわすれ堂 運営")
    args = ap.parse_args()

    try:
        host = os.environ["SMTP_HOST"]
        user = os.environ["SMTP_USER"]
        pw = os.environ["SMTP_PASS"]
    except KeyError as e:
        print(f"[error] 必須の環境変数がありません: {e}. GitHub Secrets(SMTP_HOST/SMTP_USER/SMTP_PASS)を設定してください。")
        return 2
    port = int(os.environ.get("SMTP_PORT", "587"))
    sender = os.environ.get("SMTP_FROM", user)

    body = args.body
    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()

    msg = EmailMessage()
    msg["From"] = formataddr((args.from_name, sender))
    msg["To"] = args.to
    msg["Subject"] = args.subject
    msg.set_content(body)

    for p in args.attach:
        if not p:
            continue
        if not os.path.exists(p):
            print(f"[error] 添付が見つかりません: {p}")
            return 3
        ctype, _ = mimetypes.guess_type(p)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with open(p, "rb") as f:
            msg.add_attachment(f.read(), maintype=maintype, subtype=subtype,
                               filename=os.path.basename(p))

    ctx = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
                s.login(user, pw)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(context=ctx)
                s.login(user, pw)
                s.send_message(msg)
    except Exception as e:  # noqa: BLE001
        print(f"[error] 送信に失敗しました: {type(e).__name__}: {e}")
        return 1

    print(f"sent to {args.to}: {args.subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
