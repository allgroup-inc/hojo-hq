#!/usr/bin/env python3
"""
Block 2 統合テスト: 業務軸 ❶❂❸ の双方向連携検証
Issue #6, #7, #8 を自動化

【テスト対象】
❶入口システム(アポ生成) → KAKEHASHI APO管理 → ❂訪問管理 / ❸保全CRM
"""

import json
import requests
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import Dict, List, Any, Tuple

class BusinessAxisIntegrationTest:
    def __init__(self, base_url="http://localhost:3000", api_key=None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key or "test-api-key"
        self.jwt_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.jwt_token}',
            'X-Request-ID': str(uuid.uuid4()),
            'Content-Type': 'application/json'
        })
        self.test_results = {'passed': [], 'failed': [], 'blocked': []}
        self.test_data = {}

    def _make_request(self, method: str, endpoint: str, data=None, params=None) -> Tuple[int, Dict]:
        """HTTP要求共通処理"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method == 'GET':
                resp = self.session.get(url, params=params, timeout=10)
            elif method == 'POST':
                resp = self.session.post(url, json=data, timeout=10)
            elif method == 'PATCH':
                resp = self.session.patch(url, json=data, timeout=10)
            else:
                resp = self.session.request(method, url, json=data, timeout=10)

            return resp.status_code, resp.json() if resp.text else {}
        except requests.exceptions.RequestException as e:
            return 0, {'error': str(e)}

    def test_axis_1_appointment_ingestion(self):
        """
        ❶入口 → KAKEHASHI: 新規アポイントメント取り込みテスト
        Issue #6: ❶入口システム連携テスト
        """
        print("\n🧪 [Test 1] 業務軸❶ → KAKEHASHI: 新規アポ取り込み")

        appointment_payload = {
            "customerId": f"KM-{uuid.uuid4().hex[:5].upper()}",
            "customerName": "テスト顧客❶",
            "scheduledDateTime": (datetime.now() + timedelta(days=7)).isoformat() + "+09:00",
            "estimatedDuration": 60,
            "location": "沖縄県那覇市",
            "source": "apogen_system",
            "assignedSalesRepId": None,
            "notes": "❶入口からの自動生成アポ"
        }

        # POST /api/v1/appointments
        status, response = self._make_request('POST', '/api/v1/appointments', data=appointment_payload)

        if status == 201:
            self.test_results['passed'].append("✅ ❶→KAKEHASHI: アポ登録成功 (201 Created)")
            self.test_data['appointment_id'] = response.get('id', '')
            self.test_data['customer_id'] = appointment_payload['customerId']
            print(f"   → APO-ID: {self.test_data['appointment_id']}")
            return True
        else:
            self.test_results['failed'].append(f"❌ ❶→KAKEHASHI: アポ登録失敗 (Status {status})")
            print(f"   → Status: {status}, Response: {response}")
            return False

    def test_round_robin_assignment(self):
        """
        ❶入口 → KAKEHASHI: ラウンドロビン振り分けテスト
        Issue #6: 新規アポが営業マンに正しく割り当てられるか
        """
        print("\n🧪 [Test 2] ❶→KAKEHASHI: ラウンドロビン振り分け")

        # GET /api/v1/sales-reps/round-robin
        target_date = datetime.now().date().isoformat()
        target_time = "14:00"
        status, response = self._make_request(
            'GET',
            '/api/v1/sales-reps/round-robin',
            params={'date': target_date, 'time': target_time}
        )

        if status == 200 and 'id' in response:
            self.test_results['passed'].append(f"✅ ❶→KAKEHASHI: ラウンドロビン振り分け成功 (営業マン: {response['id']})")
            self.test_data['assigned_rep_id'] = response['id']
            print(f"   → 割当営業マン: {response['name']} ({response['id']})")
            return True
        else:
            self.test_results['failed'].append(f"❌ ❶→KAKEHASHI: ラウンドロビン失敗 (Status {status})")
            return False

    def test_appointment_notification(self):
        """
        KAKEHASHI → ❂訪問管理: アポ通知テスト
        Issue #6: Slack通知送信確認
        """
        print("\n🧪 [Test 3] KAKEHASHI→❂: Slack通知送信")

        if not self.test_data.get('appointment_id'):
            self.test_results['blocked'].append("⏭️  KAKEHASHI→❂: Slack通知テスト スキップ (前提条件未満たし)")
            return False

        # POST /api/v1/notifications/slack-webhook
        notification_payload = {
            "channel": "#apo-notifications",
            "message": f"新規アポが登録されました: {self.test_data['customer_id']}",
            "appointmentId": self.test_data['appointment_id']
        }

        status, response = self._make_request('POST', '/api/v1/notifications/slack-webhook', data=notification_payload)

        if status == 200:
            self.test_results['passed'].append("✅ KAKEHASHI→❂: Slack通知送信成功 (200)")
            print(f"   → Message ID: {response.get('message_id', 'N/A')}")
            return True
        else:
            self.test_results['failed'].append(f"❌ KAKEHASHI→❂: Slack通知失敗 (Status {status})")
            return False

    def test_visit_completion_notification(self):
        """
        ❂訪問管理 → KAKEHASHI: 訪問完了通知テスト
        Issue #7: ❂から訪問完了を KAKEHASHI が受け取れるか
        """
        print("\n🧪 [Test 4] ❂→KAKEHASHI: 訪問完了通知")

        if not self.test_data.get('appointment_id'):
            self.test_results['blocked'].append("⏭️  ❂→KAKEHASHI: 訪問完了テスト スキップ (前提条件未満たし)")
            return False

        visit_completion_payload = {
            "appointmentId": self.test_data['appointment_id'],
            "actualDuration": 45,
            "result": "商品説明完了、購入予定なし",
            "nextActionDate": (datetime.now() + timedelta(days=7)).isoformat()
        }

        status, response = self._make_request('POST', '/api/visits/completed', data=visit_completion_payload)

        if status == 200:
            self.test_results['passed'].append("✅ ❂→KAKEHASHI: 訪問完了通知受信 (200)")
            print(f"   → 処理ID: {response.get('processing_id', 'N/A')}")
            return True
        else:
            self.test_results['failed'].append(f"❌ ❂→KAKEHASHI: 訪問完了通知失敗 (Status {status})")
            return False

    def test_visit_cancellation_notification(self):
        """
        ❂訪問管理 → KAKEHASHI: 訪問キャンセル通知テスト
        Issue #7: エラーケースの処理
        """
        print("\n🧪 [Test 5] ❂→KAKEHASHI: 訪問キャンセル通知")

        if not self.test_data.get('appointment_id'):
            self.test_results['blocked'].append("⏭️  ❂→KAKEHASHI: 訪問キャンセルテスト スキップ (前提条件未満たし)")
            return False

        cancel_payload = {
            "appointmentId": self.test_data['appointment_id'],
            "cancelReason": "顧客が急遽キャンセル"
        }

        status, response = self._make_request('POST', '/api/visits/cancelled', data=cancel_payload)

        if status == 200:
            self.test_results['passed'].append("✅ ❂→KAKEHASHI: 訪問キャンセル通知受信 (200)")
            return True
        else:
            self.test_results['failed'].append(f"❌ ❂→KAKEHASHI: 訪問キャンセル失敗 (Status {status})")
            return False

    def test_kpi_aggregation(self):
        """
        KAKEHASHI → ❂❸: KPI自動集計テスト
        Issue #7: 訪問完了後のKPI更新確認
        """
        print("\n🧪 [Test 6] KAKEHASHI→❂❸: KPI自動集計")

        target_date = datetime.now().date().isoformat()
        status, response = self._make_request('GET', '/api/v1/kpi/daily-summary', params={'date': target_date})

        if status == 200 and 'appointments' in response:
            self.test_results['passed'].append(f"✅ KAKEHASHI→❂❸: KPI集計成功 (訪問数: {response.get('completed_count', 0)})")
            print(f"   → 本日実績: {response.get('completed_count', 0)}件 / {response.get('scheduled_count', 0)}件予定")
            return True
        else:
            self.test_results['failed'].append(f"❌ KAKEHASHI→❂❸: KPI集計失敗 (Status {status})")
            return False

    def test_monthly_performance_report(self):
        """
        KAKEHASHI → ❸保全CRM: 月間パフォーマンスレポート
        Issue #7: 保全CRMが営業活動実績を参照可能か
        """
        print("\n🧪 [Test 7] KAKEHASHI→❸: 月間パフォーマンスレポート")

        now = datetime.now()
        status, response = self._make_request(
            'GET',
            '/api/v1/kpi/monthly-performance',
            params={'year': now.year, 'month': now.month}
        )

        if status == 200 and 'sales_reps' in response:
            total_appointments = sum(rep.get('appointment_count', 0) for rep in response.get('sales_reps', []))
            self.test_results['passed'].append(f"✅ KAKEHASHI→❸: 月間レポート生成成功 (アポ件数: {total_appointments})")
            print(f"   → 今月実績: {total_appointments}件 (営業マン数: {len(response.get('sales_reps', []))}名)")
            return True
        else:
            self.test_results['failed'].append(f"❌ KAKEHASHI→❸: 月間レポート失敗 (Status {status})")
            return False

    def test_sales_rep_free_slots(self):
        """
        KAKEHASHI: 営業マン空き時間取得テスト
        Issue #8: UI で営業マンの実時間スケジュール確認可能か
        """
        print("\n🧪 [Test 8] KAKEHASHI: 営業マン空き時間取得")

        if not self.test_data.get('assigned_rep_id'):
            self.test_results['blocked'].append("⏭️  KAKEHASHI: 営業マン空き時間テスト スキップ (前提条件未満たし)")
            return False

        target_date = (datetime.now() + timedelta(days=1)).date().isoformat()
        status, response = self._make_request(
            'GET',
            f"/api/v1/sales-reps/{self.test_data['assigned_rep_id']}/free-slots",
            params={'date': target_date}
        )

        if status == 200 and 'slots' in response:
            self.test_results['passed'].append(f"✅ KAKEHASHI: 空き時間取得成功 ({len(response.get('slots', []))}スロット)")
            print(f"   → 明日の空き枠: {len(response.get('slots', []))}個")
            return True
        else:
            self.test_results['failed'].append(f"❌ KAKEHASHI: 空き時間取得失敗 (Status {status})")
            return False

    def test_appointment_update(self):
        """
        KAKEHASHI: アポイントメント更新テスト
        Issue #8: UI から営業マンの日程変更が可能か
        """
        print("\n🧪 [Test 9] KAKEHASHI: アポ日程変更")

        if not self.test_data.get('appointment_id'):
            self.test_results['blocked'].append("⏭️  KAKEHASHI: アポ変更テスト スキップ (前提条件未満たし)")
            return False

        new_datetime = (datetime.now() + timedelta(days=1, hours=2)).isoformat() + "+09:00"
        update_payload = {
            "scheduledDateTime": new_datetime,
            "assignedSalesRepId": self.test_data.get('assigned_rep_id'),
            "status": "CONFIRMED"
        }

        status, response = self._make_request(
            'PATCH',
            f"/api/v1/appointments/{self.test_data['appointment_id']}",
            data=update_payload
        )

        if status == 200:
            self.test_results['passed'].append("✅ KAKEHASHI: アポ日程変更成功 (200)")
            print(f"   → 新しい日程: {new_datetime}")
            return True
        else:
            self.test_results['failed'].append(f"❌ KAKEHASHI: アポ日程変更失敗 (Status {status})")
            return False

    def test_appointment_cancellation(self):
        """
        KAKEHASHI: アポイントメントキャンセルテスト
        Issue #8: UI からのキャンセル機能
        """
        print("\n🧪 [Test 10] KAKEHASHI: アポキャンセル")

        if not self.test_data.get('appointment_id'):
            self.test_results['blocked'].append("⏭️  KAKEHASHI: アポキャンセルテスト スキップ (前提条件未満たし)")
            return False

        status, response = self._make_request(
            'POST',
            f"/api/v1/appointments/{self.test_data['appointment_id']}/cancel"
        )

        if status == 200:
            self.test_results['passed'].append("✅ KAKEHASHI: アポキャンセル成功 (200)")
            return True
        else:
            self.test_results['failed'].append(f"❌ KAKEHASHI: アポキャンセル失敗 (Status {status})")
            return False

    def run_all_tests(self):
        """すべてのテストを実行"""
        print("=" * 70)
        print("🚀 Block 2 統合テスト: 業務軸 ❶❂❸ 双方向連携検証")
        print("=" * 70)

        self.test_axis_1_appointment_ingestion()
        self.test_round_robin_assignment()
        self.test_appointment_notification()
        self.test_visit_completion_notification()
        self.test_visit_cancellation_notification()
        self.test_kpi_aggregation()
        self.test_monthly_performance_report()
        self.test_sales_rep_free_slots()
        self.test_appointment_update()
        self.test_appointment_cancellation()

        self._print_summary()
        return len(self.test_results['failed']) == 0

    def _print_summary(self):
        """テスト結果サマリー出力"""
        print("\n" + "=" * 70)
        print("📊 テスト結果サマリー")
        print("=" * 70)

        if self.test_results['passed']:
            print(f"\n✅ 成功 ({len(self.test_results['passed'])}件):")
            for msg in self.test_results['passed']:
                print(f"   {msg}")

        if self.test_results['failed']:
            print(f"\n❌ 失敗 ({len(self.test_results['failed'])}件):")
            for msg in self.test_results['failed']:
                print(f"   {msg}")

        if self.test_results['blocked']:
            print(f"\n⏭️  スキップ ({len(self.test_results['blocked'])}件):")
            for msg in self.test_results['blocked']:
                print(f"   {msg}")

        total = len(self.test_results['passed']) + len(self.test_results['failed'])
        success_rate = (len(self.test_results['passed']) / total * 100) if total > 0 else 0
        print(f"\n🎯 総合スコア: {success_rate:.0f}% ({len(self.test_results['passed'])}/{total})")

        if len(self.test_results['failed']) == 0 and total > 0:
            print("\n🎉 全テスト合格! Block 2 統合準備完了")
        else:
            print(f"\n⚠️  {len(self.test_results['failed'])}件の失敗があります")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Block 2 統合テスト実行")
    parser.add_argument('--base-url', default='http://localhost:3000', help='API ベースURL')
    parser.add_argument('--api-key', help='API キー (オプション)')
    parser.add_argument('--results-dir', default=str(Path(__file__).parent / 'results'),
                        help='結果JSON(business-axis.json)の出力先')

    args = parser.parse_args()

    tester = BusinessAxisIntegrationTest(base_url=args.base_url, api_key=args.api_key)
    success = tester.run_all_tests()

    import results_writer
    results_writer.write_result(
        args.results_dir, 'business-axis', passed=success,
        passed_count=len(tester.test_results['passed']),
        failed_count=len(tester.test_results['failed']),
        blocked_count=len(tester.test_results['blocked']),
        total=len(tester.test_results['passed']) + len(tester.test_results['failed']),
        base_url=args.base_url,
    )

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
