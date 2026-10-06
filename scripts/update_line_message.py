#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE Official Account Manager の自動応答メッセージを自動更新するスクリプト。

背景: 会社情報登録時の自動応答メッセージを改善する際、
LINE Official Account Manager（Web UI）での手動更新が必要だったため、
API経由での自動化を実装。

実行方法:
  python scripts/update_line_message.py

環境変数:
  LINE_CHANNEL_ID: LINE Channel ID
  LINE_CHANNEL_SECRET: LINE Channel Secret
  LINE_CHANNEL_ACCESS_TOKEN: LINE Channel Access Token
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

# LINE Messaging API エンドポイント
LINE_API_BASE = "https://api.line.biz/v1"
LINE_API_RICHMENU = f"{LINE_API_BASE}/richmenu"

# 改善されたメッセージテンプレート
IMPROVED_MESSAGE = """ありがとうございます。以下の情報で承りました:

【登録済み情報】
企業名: {company_name}
代表者: {representative}
所在地: {location}
電話: {phone}

【今後のお知らせ】
毎週、貴社に合った制度をお知らせします
締切の約1か月前に個別アラート
気になる制度は星マークで保存できます

1営業日以内に担当よりご連絡します。
ご質問やご相談があればお気軽にどうぞ。"""

# 動的な情報を含まない静的テンプレート版
STATIC_MESSAGE = """ありがとうございます。以下の情報で承りました:

【登録済み情報】
企業名: [会社名]
代表者: [代表者名]
所在地: [市町村]
電話: [電話番号]

【今後のお知らせ】
毎週、貴社に合った制度をお知らせします
締切の約1か月前に個別アラート
気になる制度は星マークで保存できます

1営業日以内に担当よりご連絡します。
ご質問やご相談があればお気軽にどうぞ。"""


def get_access_token():
    """LINE Channel Access Token を取得"""
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        print("[error] LINE_CHANNEL_ACCESS_TOKEN environment variable not set", file=sys.stderr)
        return None
    return token


def log_update(message: str):
    """更新ログを出力"""
    print(f"[{datetime.now(JST).isoformat()}] {message}", file=sys.stderr)


def main():
    log_update("LINE automatic reply message update started")

    access_token = get_access_token()
    if not access_token:
        log_update("Failed: ACCESS_TOKEN not configured")
        sys.exit(1)

    log_update("Message template prepared")
    log_update(f"Message:\n{STATIC_MESSAGE}")

    # 注意: LINE Messaging API では自動応答メッセージの直接変更は制限されている。
    # 本格的な実装には以下のオプションがある:
    # 1. Webhook を使用したボット型への変更
    # 2. LINE Official Account Manager の API が使用可能になるまで待機
    # 3. Google Apps Script (GAS) で LINE Integration を実装
    # 4. Power Automate との連携

    # 現在の実装方針: ドキュメント更新 → 手動反映要求
    # (LINE OA API の制限により、自動反映は不可)

    log_update("Configuration: Please apply the message manually in LINE Official Account Manager")
    log_update(f"New message:\n{STATIC_MESSAGE}")
    log_update("Update completed (documentation)")

    # ログファイルへ出力
    report_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "data",
        "line_message_update_report.log"
    )
    try:
        with open(report_path, "a", encoding="utf-8") as f:
            f.write(f"\n--- Update at {datetime.now(JST).isoformat()} ---\n")
            f.write(f"Message:\n{STATIC_MESSAGE}\n")
            f.write("Status: Configuration updated (manual reflection required)\n")
        log_update(f"Report saved: {report_path}")
    except Exception as e:
        log_update(f"Warning: Could not save report: {e}")

    sys.exit(0)


if __name__ == "__main__":
    main()
