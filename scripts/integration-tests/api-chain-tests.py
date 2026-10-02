#!/usr/bin/env python3
"""
Block 2 API チェーンテスト
Issue #6, #7: エンドツーエンドAPI呼び出し検証

【テストシナリオ】
1. 新規アポ登録
2. ラウンドロビン振り分け
3. Slack通知送信
4. 訪問完了→KPI集計
5. 月間レポート生成
"""

import json
import requests
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import sys
from pathlib import Path

class APIChainTest:
    def __init__(self, base_url="http://localhost:3000"):
        self.base_url = base_url.rstrip('/')
        self.jwt_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.jwt_token}',
            'X-Request-ID': str(uuid.uuid4()),
            'Content-Type': 'application/json'
        })
        self.timings = {}
        self.results = []

    def _request(self, method: str, endpoint: str, data=None, params=None) -> Tuple[int, Dict, float]:
        """HTTP要求実行 + 応答時間計測"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()

        try:
            if method == 'GET':
                resp = self.session.get(url, params=params, timeout=10)
            elif method == 'POST':
                resp = self.session.post(url, json=data, timeout=10)
            elif method == 'PATCH':
                resp = self.session.patch(url, json=data, timeout=10)
            else:
                resp = self.session.request(method, url, json=data, timeout=10)

            elapsed = time.time() - start_time
            response_data = resp.json() if resp.text else {}

            return resp.status_code, response_data, elapsed
        except Exception as e:
            elapsed = time.time() - start_time
            return 0, {'error': str(e)}, elapsed

    def scenario_1_create_appointment(self):
        """シナリオ1: 新規アポ登録"""
        print("\n🔗 [Chain 1] 新規アポ登録")

        payload = {
            "customerId": f"KM-{uuid.uuid4().hex[:5].upper()}",
            "customerName": "チェーンテスト顧客",
            "scheduledDateTime": (datetime.now() + timedelta(days=5)).isoformat() + "+09:00",
            "estimatedDuration": 60,
            "location": "沖縄県那覇市",
            "source": "apogen_system",
            "notes": "チェーンテスト用"
        }

        status, response, elapsed = self._request('POST', '/api/v1/appointments', data=payload)
        self.timings['create_appointment'] = elapsed

        if status == 201:
            appointment_id = response.get('id', '')
            self.results.append({
                'step': 1,
                'action': '新規アポ登録',
                'status': '✅',
                'time_ms': f"{elapsed*1000:.0f}",
                'notes': f"APO-ID: {appointment_id}"
            })
            return True, appointment_id
        else:
            self.results.append({
                'step': 1,
                'action': '新規アポ登録',
                'status': f'❌ ({status})',
                'time_ms': f"{elapsed*1000:.0f}",
                'notes': 'API呼び出し失敗'
            })
            return False, None

    def scenario_2_assign_sales_rep(self):
        """シナリオ2: ラウンドロビン振り分け"""
        print("🔗 [Chain 2] ラウンドロビン振り分け")

        target_date = datetime.now().date().isoformat()
        status, response, elapsed = self._request(
            'GET',
            '/api/v1/sales-reps/round-robin',
            params={'date': target_date, 'time': '14:00'}
        )
        self.timings['round_robin'] = elapsed

        if status == 200 and 'id' in response:
            rep_id = response.get('id', '')
            rep_name = response.get('name', '')
            self.results.append({
                'step': 2,
                'action': 'ラウンドロビン振り分け',
                'status': '✅',
                'time_ms': f"{elapsed*1000:.0f}",
                'notes': f"{rep_name} ({rep_id})"
            })
            return True, rep_id
        else:
            self.results.append({
                'step': 2,
                'action': 'ラウンドロビン振り分け',
                'status': f'❌ ({status})',
                'time_ms': f"{elapsed*1000:.0f}",
                'notes': 'API呼び出し失敗'
            })
            return False, None

    def scenario_3_send_notification(self, appointment_id: str):
        """シナリオ3: Slack通知送信"""
        print("🔗 [Chain 3] Slack通知送信")

        payload = {
            "channel": "#apo-notifications",
            "message": f"新規アポが登録されました: {appointment_id}",
            "appointmentId": appointment_id
        }

        status, response, elapsed = self._request(
            'POST',
            '/api/v1/notifications/slack-webhook',
            data=payload
        )
        self.timings['send_notification'] = elapsed

        if status == 200:
            self.results.append({
                'step': 3,
                'action': 'Slack通知送信',
                'status': '✅',
                'time_ms': f"{elapsed*1000:.0f}",
                'notes': response.get('message_id', 'N/A')
            })
            return True
        else:
            self.results.append({
                'step': 3,
                'action': 'Slack通知送信',
                'status': f'❌ ({status})',
                'time_ms': f"{elapsed*1000:.0f}",
                'notes': '通知送信失敗'
            })
            return False

    def scenario_4_complete_visit(self, appointment_id: str):
        """シナリオ4: 訪問完了→KPI集計"""
        print("🔗 [Chain 4] 訪問完了通知")

        payload = {
            "appointmentId": appointment_id,
            "actualDuration": 45,
            "result": "商品説明完了、購入検討中",
            "nextActionDate": (datetime.now() + timedelta(days=7)).isoformat()
        }

        status, response, elapsed = self._request(
            'POST',
            '/api/visits/completed',
            data=payload
        )
        self.timings['visit_completion'] = elapsed

        if status == 200:
            self.results.append({
                'step': 4,
                'action': '訪問完了通知',
                'status': '✅',
                'time_ms': f"{elapsed*1000:.0f}",
                'notes': response.get('processing_id', 'N/A')
            })
            return True
        else:
            self.results.append({
                'step': 4,
                'action': '訪問完了通知',
                'status': f'❌ ({status})',
                'time_ms': f"{elapsed*1000:.0f}",
                'notes': '通知送信失敗'
            })
            return False

    def scenario_5_fetch_kpi(self):
        """シナリオ5: KPI集計データ取得"""
        print("🔗 [Chain 5] KPI集計データ取得")

        target_date = datetime.now().date().isoformat()
        status, response, elapsed = self._request(
            'GET',
            '/api/v1/kpi/daily-summary',
            params={'date': target_date}
        )
        self.timings['fetch_kpi'] = elapsed

        if status == 200:
            completed = response.get('completed_count', 0)
            scheduled = response.get('scheduled_count', 0)
            self.results.append({
                'step': 5,
                'action': 'KPI集計データ取得',
                'status': '✅',
                'time_ms': f"{elapsed*1000:.0f}",
                'notes': f"実績 {completed}/{scheduled}件"
            })
            return True
        else:
            self.results.append({
                'step': 5,
                'action': 'KPI集計データ取得',
                'status': f'❌ ({status})',
                'time_ms': f"{elapsed*1000:.0f}",
                'notes': 'データ取得失敗'
            })
            return False

    def scenario_6_monthly_report(self):
        """シナリオ6: 月間パフォーマンスレポート"""
        print("🔗 [Chain 6] 月間パフォーマンスレポート生成")

        now = datetime.now()
        status, response, elapsed = self._request(
            'GET',
            '/api/v1/kpi/monthly-performance',
            params={'year': now.year, 'month': now.month}
        )
        self.timings['monthly_report'] = elapsed

        if status == 200:
            total_apos = sum(
                rep.get('appointment_count', 0)
                for rep in response.get('sales_reps', [])
            )
            self.results.append({
                'step': 6,
                'action': '月間レポート生成',
                'status': '✅',
                'time_ms': f"{elapsed*1000:.0f}",
                'notes': f"総アポ数 {total_apos}件"
            })
            return True
        else:
            self.results.append({
                'step': 6,
                'action': '月間レポート生成',
                'status': f'❌ ({status})',
                'time_ms': f"{elapsed*1000:.0f}",
                'notes': 'レポート生成失敗'
            })
            return False

    def run_full_chain(self):
        """全チェーン実行"""
        print("=" * 70)
        print("🔗 Block 2 API チェーンテスト")
        print("=" * 70)

        total_start = time.time()

        # Chain 1: 新規アポ登録
        success, appointment_id = self.scenario_1_create_appointment()
        if not success or not appointment_id:
            print("\n❌ Chain 1 失敗。以降のテストをスキップします")
            self._print_report()
            return False

        # Chain 2: ラウンドロビン振り分け
        success, rep_id = self.scenario_2_assign_sales_rep()

        # Chain 3: Slack通知送信
        if appointment_id:
            self.scenario_3_send_notification(appointment_id)

        # Chain 4: 訪問完了
        if appointment_id:
            self.scenario_4_complete_visit(appointment_id)

        # Chain 5: KPI取得
        self.scenario_5_fetch_kpi()

        # Chain 6: 月間レポート
        self.scenario_6_monthly_report()

        total_elapsed = time.time() - total_start

        self._print_report()
        print(f"\n⏱️  総実行時間: {total_elapsed:.2f}秒")

        failed = sum(1 for r in self.results if '❌' in r['status'])
        return failed == 0

    def _print_report(self):
        """テスト結果レポート出力"""
        print("\n" + "=" * 70)
        print("📊 APIチェーンテスト結果")
        print("=" * 70)
        print(f"{'ステップ':<5} {'アクション':<20} {'ステータス':<10} {'応答時間':<10} {'備考'}")
        print("-" * 70)

        for result in self.results:
            step = result['step']
            action = result['action']
            status = result['status']
            time_ms = result['time_ms']
            notes = result['notes'][:30]  # 30文字まで表示

            print(f"{step:<5} {action:<20} {status:<10} {time_ms:>8}ms  {notes}")

        print("-" * 70)

        # パフォーマンス統計
        if self.timings:
            print("\n⚡ 応答時間統計:")
            total_time = sum(self.timings.values())
            for endpoint, elapsed in sorted(self.timings.items(), key=lambda x: x[1], reverse=True):
                percent = (elapsed / total_time * 100) if total_time > 0 else 0
                print(f"  {endpoint:<30} {elapsed*1000:>7.0f}ms ({percent:>5.1f}%)")

        # サマリー
        passed = sum(1 for r in self.results if '✅' in r['status'])
        failed = sum(1 for r in self.results if '❌' in r['status'])
        print(f"\n🎯 結果: {passed}/{len(self.results)} 成功 ({passed/len(self.results)*100:.0f}%)")

        if failed > 0:
            print(f"⚠️  {failed}個のステップが失敗しました")
        else:
            print("🎉 全ステップ合格! API連携が正常に動作しています")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Block 2 APIチェーンテスト")
    parser.add_argument('--base-url', default='http://localhost:3000', help='ベースURL')
    parser.add_argument('--repeat', type=int, default=1, help='テスト繰り返し回数')
    parser.add_argument('--results-dir', default=str(Path(__file__).parent / 'results'),
                        help='結果JSON(api-chain.json)の出力先')

    args = parser.parse_args()

    for i in range(args.repeat):
        if i > 0:
            print(f"\n{'='*70}\n")
            time.sleep(2)  # 次の実行前に2秒待機

        print(f"実行 {i+1}/{args.repeat}")
        tester = APIChainTest(base_url=args.base_url)
        success = tester.run_full_chain()

        if not success and args.repeat > 1:
            print(f"\n⚠️  {i+1}回目の実行で失敗しました")

    # 最終回の結果を記録する
    import results_writer
    results_writer.write_result(
        args.results_dir, 'api-chain', passed=success,
        passed_count=sum(1 for r in tester.results if '✅' in r['status']),
        failed_count=sum(1 for r in tester.results if '❌' in r['status']),
        total=len(tester.results),
        base_url=args.base_url,
    )

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
