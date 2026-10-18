#!/usr/bin/env python3
"""
Google Sheets API統合版: エンライフ営業成績データ直接読み込み

Google Sheets APIを使用して、Google Sheetの「営業成績（月別）」シートから
直接データを読み込み、カチトークへ同期します。

セットアップ手順:
1. Google Cloud Projectでシートとドライブのスコープを有効化
2. Service Accountの認証情報JSONを取得
3. シートの共有設定でService Accountのメールアドレスに編集権限を付与
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# google-auth-oauthlib / google-api-python-client をインストール必須
# pip install --upgrade google-auth-oauthlib google-auth-httplib2 google-api-python-client


def read_from_google_sheets(spreadsheet_id: str, credentials_file: str) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Google Sheets APIを使用して営業成績データを読み込む

    Args:
        spreadsheet_id: Google SheetのID
        credentials_file: Service Account認証情報JSONファイルパス

    Returns:
        {月: {営業マン: {KPI: 値}}}
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.service_account import Credentials
        from google.auth.transport.urllib3 import AuthorizedHttp
        from googleapiclient.discovery import build
    except ImportError:
        print("✗ Google APIクライアントライブラリがインストールされていません")
        print("実行: pip install --upgrade google-auth-oauthlib google-api-python-client")
        return {}

    try:
        # 認証
        credentials = Credentials.from_service_account_file(
            credentials_file,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )

        service = build('sheets', 'v4', credentials=credentials)

        # 「営業成績（月別）」シートを読み込む
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range='営業成績（月別）!A:O'  # A列から O列まで（営業マン、月、KPI14個）
        ).execute()

        values = result.get('values', [])
        if not values:
            print("✗ シートからデータが取得できませんでした")
            return {}

        # データを解析
        data = {}
        header_row = values[0] if values else []

        # 営業マン名とKPI一覧を確認
        STAFF_NAMES = [
            '前原　芳乃', '奈須　章', '下地　健太', '幸良　妃奈代',
            '徳元　孝樹', '喜納　礼奈', '名嘉山　望', '狩俣　亜希乃',
        ]
        MONTHS = ['5月', '6月', '7月', '8月', '9月']

        for row in values[1:]:  # ヘッダー行をスキップ
            if len(row) < 2:
                continue

            staff_name = row[0].strip() if row else None
            month = row[1].strip() if len(row) > 1 else None

            if not staff_name or not month or staff_name not in STAFF_NAMES or month not in MONTHS:
                continue

            if month not in data:
                data[month] = {}

            data[month][staff_name] = {}

            # KPI値を抽出（列2以降、14個）
            kpi_headers = header_row[2:16] if len(header_row) > 15 else []

            for col_idx in range(2, min(16, len(row))):
                kpi_idx = col_idx - 2
                if kpi_idx < len(kpi_headers):
                    kpi_name = kpi_headers[kpi_idx].strip()
                    try:
                        value = float(row[col_idx]) if row[col_idx] else None
                        if value is not None:
                            data[month][staff_name][kpi_name] = value
                    except (ValueError, IndexError, TypeError):
                        pass

        print(f"✓ Google Sheets読み込み完了: {sum(len(m) for m in data.values())}件")
        return data

    except FileNotFoundError:
        print(f"✗ 認証ファイルが見つかりません: {credentials_file}")
        return {}
    except Exception as e:
        print(f"✗ Google Sheets読み込みエラー: {e}")
        import traceback
        traceback.print_exc()
        return {}


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Google Sheets API統合版: 営業成績データ読み込み')
    parser.add_argument('--spreadsheet-id', required=True,
                       help='Google SheetのID（URLから取得可）')
    parser.add_argument('--credentials', required=True,
                       help='Service Account認証情報JSONファイルパス')
    parser.add_argument('--endpoint',
                       help='カチトークAPIエンドポイント（指定時は自動同期）')
    parser.add_argument('--token',
                       help='カチトークAPI認証トークン（指定時は自動同期）')

    args = parser.parse_args()

    # Google Sheetsから読み込む
    data = read_from_google_sheets(args.spreadsheet_id, args.credentials)

    if not data:
        sys.exit(1)

    # データを表示
    print("\n【読み込んだデータ】")
    for month in ['5月', '6月', '7月', '8月', '9月']:
        if month in data:
            print(f"  {month}: {len(data[month])}名")

    # カチトークへ同期（オプション）
    if args.endpoint and args.token:
        from sync_to_kachitalk import KachiTalkSyncer

        syncer = KachiTalkSyncer(args.endpoint, args.token)
        if syncer.test_connection():
            print("\n✓ カチトークへの同期準備完了")
            # 同期処理をここで実装

    sys.exit(0)


if __name__ == '__main__':
    main()
