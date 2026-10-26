#!/usr/bin/env python3
"""
KachiTalk admin dashboard から CSV を自動ダウンロードするスクリプト
認証キーを使用して、定期実行向けに設計
"""

import os
import sys
import json
import requests
from datetime import datetime
from pathlib import Path

# 設定
KACHITALK_API_URL = os.getenv(
    "KACHITALK_API_URL",
    "https://kachitalk-line-enlife.azurewebsites.net/api"
)
KACHITALK_AUTH_TOKEN = os.getenv("KACHITALK_AUTH_TOKEN")
EXPORT_DIR = "/tmp"
TIMESTAMP = datetime.now().strftime("%Y%m%d")

def download_csv():
    """KachiTalk admin からCSVをダウンロード"""

    if not KACHITALK_AUTH_TOKEN:
        print("❌ エラー: KACHITALK_AUTH_TOKEN 環境変数が未設定です")
        print("手順:")
        print("1. ブラウザでKachiTalk admin (https://kachitalk-line-enlife.azurewebsites.net/admin) を開く")
        print("2. Developer Tools → Network タブ")
        print("3. CSVエクスポートをクリック")
        print("4. API リクエストのヘッダーから Authorization: Bearer <TOKEN> をコピー")
        print("5. export KACHITALK_AUTH_TOKEN='<TOKEN>' で設定")
        return False

    try:
        print("🔍 KachiTalk admin からCSVをダウンロード中...")

        # ヘッダー設定
        headers = {
            "Authorization": f"Bearer {KACHITALK_AUTH_TOKEN}",
            "Accept": "text/csv"
        }

        # エクスポートリクエスト
        # 期間: 2026年7月1日～10月31日
        # 営業マン: 全8名
        params = {
            "start_date": "2026-07-01",
            "end_date": "2026-10-31",
            "format": "csv"
        }

        response = requests.get(
            f"{KACHITALK_API_URL}/export",
            headers=headers,
            params=params,
            timeout=30
        )

        if response.status_code == 401:
            print("❌ 認証失敗: トークンが無効または期限切れです")
            return False
        elif response.status_code == 403:
            print("❌ 権限なし: このトークンはエクスポート権限を持っていません")
            return False
        elif response.status_code != 200:
            print(f"❌ エラー: ステータス {response.status_code}")
            print(f"レスポンス: {response.text[:200]}")
            return False

        # ファイル保存
        output_file = f"{EXPORT_DIR}/kachitalk_logs_full_export_{TIMESTAMP}.csv"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(response.text)

        # 行数確認
        lines = response.text.strip().split('\n')
        data_count = len(lines) - 1  # ヘッダー除外
        file_size = os.path.getsize(output_file)

        print(f"✅ ダウンロード完了")
        print(f"   ファイル: {output_file}")
        print(f"   データ件数: {data_count} 件")
        print(f"   ファイルサイズ: {file_size / 1024:.1f} KB")

        if data_count < 400:
            print(f"⚠️  警告: 400件未満のため、フルスケール分析ではない可能性があります")

        return True

    except requests.exceptions.Timeout:
        print("❌ タイムアウト: KachiTalk admin への接続がタイムアウトしました")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"❌ 接続エラー: {e}")
        return False
    except Exception as e:
        print(f"❌ エラー: {e}")
        return False

def main():
    success = download_csv()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
