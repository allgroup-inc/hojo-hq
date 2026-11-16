#!/usr/bin/env python3
"""
KachiTalk Admin Site Integration
Sends shimoji checklist analysis results to the KachiTalk admin dashboard

Usage:
  python3 kachitalk_site_integration.py --analysis-json /tmp/analysis.json --api-key <key>
"""

import json
import requests
import argparse
from datetime import datetime

class KachiTalkSiteIntegration:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }

    def send_shimoji_analysis(self, analysis_data: dict):
        """Send shimoji checklist analysis results to KachiTalk site"""

        payload = {
            'analysis_type': 'shimoji_compliance_checklist',
            'timestamp': datetime.now().isoformat(),
            'data': {}
        }

        # Transform analysis data for site display
        for staff_name, metrics in analysis_data.get('staff_analysis', {}).items():
            shimoji = metrics.get('shimoji_checklist', {})

            payload['data'][staff_name] = {
                'avg_score': shimoji.get('avg_score', 0),
                'items': shimoji.get('item_execution_rates', {}),
                'contract_rate': metrics.get('contract_rate', 0),
                'process_completeness': metrics.get('avg_completeness', 0),
                'call_count': metrics.get('call_count', 0)
            }

        try:
            response = requests.post(
                f'{self.api_url}/analysis/shimoji-checklist',
                json=payload,
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 200:
                print(f'✓ KachiTalk サイトへの送信成功')
                return True
            else:
                print(f'✗ 送信失敗: {response.status_code}')
                print(f'  レスポンス: {response.text}')
                return False

        except Exception as e:
            print(f'✗ 通信エラー: {e}')
            return False

    def create_compliance_category(self):
        """Create new category for shimoji compliance checklist on the site"""

        category_config = {
            'name': '下地チェックリスト検証',
            'description': '営業コンプライアンスの7項目実施率を自動分析',
            'items': [
                {
                    'id': '①推奨理由説明',
                    'description': 'お客様に対して、この保険を推奨する理由を明確に説明したか'
                },
                {
                    'id': '②書面交付・口頭説明',
                    'description': '契約前に契約書・約款などの書面を交付し、口頭で説明したか'
                },
                {
                    'id': '③公的保険情報提供',
                    'description': '社会保障・健康保険など公的制度の情報提供をしたか'
                },
                {
                    'id': '④検討時間確保',
                    'description': '顧客に十分な検討時間を確保したか'
                },
                {
                    'id': '⑤高齢者募集ルール遵守',
                    'description': 'シニア世代への契約時に適切なルール対応をしたか'
                },
                {
                    'id': '⑥適合性確認',
                    'description': '顧客のニーズに最適な商品か確認・説明したか'
                },
                {
                    'id': '⑦意向相違確認',
                    'description': '最初の意向と最終的な意向に相違がないか確認したか'
                }
            ],
            'scoring': {
                'excellent': '80-100点',
                'good': '60-79点',
                'fair': '40-59点',
                'poor': '0-39点'
            }
        }

        try:
            response = requests.post(
                f'{self.api_url}/categories/create',
                json=category_config,
                headers=self.headers,
                timeout=30
            )

            if response.status_code == 201:
                print(f'✓ カテゴリ作成成功: 下地チェックリスト検証')
                return True
            else:
                print(f'✗ カテゴリ作成失敗: {response.status_code}')
                return False

        except Exception as e:
            print(f'✗ カテゴリ作成エラー: {e}')
            return False


def main():
    parser = argparse.ArgumentParser(
        description='KachiTalk Admin Site への下地チェックリスト分析結果送信'
    )
    parser.add_argument(
        '--analysis-json',
        required=True,
        help='分析結果JSONファイル'
    )
    parser.add_argument(
        '--api-url',
        default='https://kachitalk-line-enlife.azurewebsites.net/api',
        help='KachiTalk API エンドポイント'
    )
    parser.add_argument(
        '--api-key',
        help='KachiTalk API キー（環境変数 KACHITALK_API_KEY も使用可）'
    )
    parser.add_argument(
        '--create-category',
        action='store_true',
        help='新規カテゴリを作成'
    )

    args = parser.parse_args()

    # Load analysis results
    try:
        with open(args.analysis_json, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
    except Exception as e:
        print(f'✗ 分析ファイル読込エラー: {e}')
        return False

    # Initialize integration
    integration = KachiTalkSiteIntegration(args.api_url, args.api_key)

    # Create category if requested
    if args.create_category:
        print('📋 カテゴリ作成中...')
        integration.create_compliance_category()

    # Send analysis results
    print('📤 分析結果送信中...')
    integration.send_shimoji_analysis(analysis_data)

    print('✓ 完了')


if __name__ == '__main__':
    main()
