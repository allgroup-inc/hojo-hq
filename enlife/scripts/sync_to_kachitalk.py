#!/usr/bin/env python3
"""
エンライフ営業成績データ → カチトーク同期スクリプト

Google Sheetの営業成績データをカチトーク（kakei-crm）の営業メトリクスAPIへ同期します。
月別・営業マン別のKPI実績データを自動取得し、カチトークの状況確認ダッシュボードから確認できるようにします。
"""

import json
import requests
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from pathlib import Path

# エンライフスタッフ名（Google Sheetと同じ順序）
STAFF_NAMES = [
    '前原　芳乃',
    '奈須　章',
    '下地　健太',
    '幸良　妃奈代',
    '徳元　孝樹',
    '喜納　礼奈',
    '名嘉山　望',
    '狩俣　亜希乃',
]

# KPI指標（Google Sheetと同じ順序）
KPI_HEADERS = [
    'ANP実績',
    '契約件数',
    '契約世帯',
    '世帯取り',
    '世帯単価',
    '世帯率',
    '落ち率',
    '新規訪問',
    '再アポ訪問',
    'その他訪問',
    '合計訪問',
    '自己アポ作成',
    '自己アポ訪問実績',
    '供給アポ実績'
]

MONTHS = ['5月', '6月', '7月', '8月', '9月']
JST = timezone(timedelta(hours=9))


class KachiTalkSyncer:
    """カチトークとのデータ同期を担当するクラス"""

    def __init__(self, api_endpoint: str, api_token: str, verify_ssl: bool = True):
        """
        初期化

        Args:
            api_endpoint: カチトークAPIエンドポイント（例：https://kachitalk-line-enlife.azurewebsites.net）
            api_token: カチトークAPI認証トークン
            verify_ssl: SSL証明書の検証（開発環境ではFalseも可）
        """
        self.api_endpoint = api_endpoint.rstrip('/')
        self.api_token = api_token
        self.verify_ssl = verify_ssl
        self.headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json',
        }

    def _request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict:
        """APIリクエストを実行"""
        url = f"{self.api_endpoint}/api{path}"

        try:
            if method == 'GET':
                resp = requests.get(url, headers=self.headers, verify=self.verify_ssl, timeout=30)
            elif method == 'POST':
                resp = requests.post(url, headers=self.headers, json=data, verify=self.verify_ssl, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")

            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.exceptions.RequestException as e:
            print(f"✗ APIリクエスト失敗: {e}")
            raise

    def test_connection(self) -> bool:
        """カチトークへの接続確認"""
        try:
            result = self._request('GET', '/me')
            if 'display_name' in result:
                print(f"✓ カチトーク接続確認: {result.get('display_name')} ({result.get('layer')}層)")
                return True
        except Exception as e:
            print(f"✗ カチトーク接続失敗: {e}")
        return False

    def post_sales_performance(self, staff_name: str, month: str, kpi_data: Dict[str, any], reason: str = "営業成績同期") -> bool:
        """
        営業成績データをカチトークへ送信

        Args:
            staff_name: 営業マン名
            month: 月（例：'5月'）
            kpi_data: KPI値の辞書（{KPI指標名: 値}）
            reason: 操作理由

        Returns:
            送信成功の有無
        """
        # カチトークには「営業成績データ」として保存
        # 既存のmetricsテーブルを利用するか、新しいテーブルを作成するか
        # 暫定的には、カスタムメトリクスとして保存

        payload = {
            "staff": staff_name,
            "month": month,
            "metrics": kpi_data,
            "reason": reason
        }

        try:
            # /api/sales-performance エンドポイントへ送信（要実装）
            self._request('POST', '/sales-performance', payload)
            print(f"✓ {staff_name} ({month}): カチトークへ送信完了")
            return True
        except Exception as e:
            print(f"✗ {staff_name} ({month}): 送信失敗 - {e}")
            return False

    def get_sales_performance(self, staff_name: Optional[str] = None, month: Optional[str] = None) -> List[Dict]:
        """
        カチトークから営業成績データを取得

        Args:
            staff_name: 営業マン名（Noneの場合は全員）
            month: 月（Noneの場合は全月）

        Returns:
            営業成績データのリスト
        """
        params = []
        if staff_name:
            params.append(f"staff={staff_name}")
        if month:
            params.append(f"month={month}")

        path = '/sales-performance' + ('?' + '&'.join(params) if params else '')

        try:
            result = self._request('GET', path)
            if isinstance(result, dict) and 'items' in result:
                return result['items']
            elif isinstance(result, list):
                return result
            return []
        except Exception as e:
            print(f"✗ データ取得失敗: {e}")
            return []


def read_google_sheets_csv(csv_file: str) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Google Sheets形式のCSVファイルを読み込む
    形式: 営業マン, 月, KPI1, KPI2, ...

    Returns:
        {月: {営業マン: {KPI: 値}}}
    """
    import csv

    data = {}

    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            header = next(reader)  # ヘッダー行をスキップ

            for row in reader:
                if len(row) < 2:
                    continue

                staff_name = row[0].strip()
                month = row[1].strip()

                if staff_name not in STAFF_NAMES or month not in MONTHS:
                    continue

                if month not in data:
                    data[month] = {}
                if staff_name not in data[month]:
                    data[month][staff_name] = {}

                # KPI値を抽出（列2以降）
                for col_idx, kpi_header in enumerate(KPI_HEADERS):
                    col = col_idx + 2
                    if col < len(row):
                        try:
                            value = float(row[col]) if row[col].strip() else None
                            if value is not None:
                                data[month][staff_name][kpi_header] = value
                        except (ValueError, IndexError):
                            pass

        print(f"✓ CSV読み込み完了: {csv_file}")
        return data
    except FileNotFoundError:
        print(f"✗ ファイルが見つかりません: {csv_file}")
        return {}
    except Exception as e:
        print(f"✗ CSV読み込みエラー: {e}")
        return {}


def sync_to_kachitalk(csv_file: str, api_endpoint: str, api_token: str) -> bool:
    """
    Google Sheetの営業成績データをカチトークへ同期

    Args:
        csv_file: Google Sheets形式のCSVファイルパス
        api_endpoint: カチトークAPIエンドポイント
        api_token: カチトークAPI認証トークン

    Returns:
        同期成功の有無
    """
    print("=" * 80)
    print("エンライフ営業成績 → カチトーク同期")
    print("=" * 80)

    # カチトークへの接続確認
    syncer = KachiTalkSyncer(api_endpoint, api_token)
    if not syncer.test_connection():
        print("✗ カチトークへの接続に失敗しました")
        return False

    print()

    # CSVを読み込む
    data = read_google_sheets_csv(csv_file)
    if not data:
        print("✗ データが見つかりません")
        return False

    print()

    # カチトークへ送信
    success_count = 0
    total_count = 0

    for month in MONTHS:
        if month not in data:
            continue

        for staff_name in STAFF_NAMES:
            if staff_name not in data[month]:
                continue

            kpi_data = data[month][staff_name]
            total_count += 1

            if syncer.post_sales_performance(staff_name, month, kpi_data):
                success_count += 1

    print()
    print("=" * 80)
    print(f"【同期結果】")
    print(f"  成功: {success_count}/{total_count}件")
    print(f"  失敗: {total_count - success_count}件")

    if success_count == total_count and total_count > 0:
        print("\n✓ すべてのデータをカチトークへ同期しました")
        print(f"✓ カチトークの状況確認URLで確認してください")
        return True
    else:
        print("\n⚠ 一部のデータの同期に失敗しました")
        return success_count > 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description='エンライフ営業成績 → カチトーク同期')
    parser.add_argument('--csv', default='/tmp/sales_performance_for_sheets.csv',
                       help='Google Sheets形式のCSVファイル（デフォルト: /tmp/sales_performance_for_sheets.csv）')
    parser.add_argument('--endpoint', required=True,
                       help='カチトークAPIエンドポイント（例：https://kachitalk-line-enlife.azurewebsites.net）')
    parser.add_argument('--token', required=True,
                       help='カチトークAPI認証トークン')
    parser.add_argument('--no-verify-ssl', action='store_true',
                       help='SSL証明書検証を無効化（開発環境のみ）')

    args = parser.parse_args()

    success = sync_to_kachitalk(
        csv_file=args.csv,
        api_endpoint=args.endpoint,
        api_token=args.token
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
