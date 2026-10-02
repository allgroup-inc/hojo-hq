#!/usr/bin/env python3
"""
Block 2 パフォーマンスベースライン計測
Issue #8, #14: 本番環境への負荷テスト・応答時間計測

【計測対象】
- APIレスポンス時間 (p50, p95, p99)
- 同時接続数に対する応答時間変化
- スループット (RPS: requests per second)
- エラー率
"""

import json
import requests
import time
import threading
import uuid
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import mean, median, stdev
from typing import Dict, List, Tuple
import sys
from pathlib import Path

class PerformanceBaseline:
    def __init__(self, base_url="http://localhost:3000"):
        self.base_url = base_url.rstrip('/')
        self.jwt_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test"
        self.results = {
            'response_times': [],
            'errors': 0,
            'success_count': 0,
            'total_requests': 0
        }

    def _make_request(self, endpoint: str, method: str = 'GET', data=None) -> Tuple[int, float]:
        """単一リクエスト実行"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.jwt_token}',
            'X-Request-ID': str(uuid.uuid4()),
            'Content-Type': 'application/json'
        }

        start_time = time.time()
        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, timeout=10)
            elif method == 'POST':
                resp = requests.post(url, json=data, headers=headers, timeout=10)
            else:
                resp = requests.request(method, url, json=data, headers=headers, timeout=10)

            elapsed = time.time() - start_time
            return resp.status_code, elapsed
        except Exception as e:
            elapsed = time.time() - start_time
            return 0, elapsed

    def test_endpoint_performance(self, endpoint: str, method: str = 'GET',
                                  concurrent_users: int = 1,
                                  requests_per_user: int = 10) -> Dict:
        """エンドポイントのパフォーマンス計測"""

        results = {
            'endpoint': endpoint,
            'method': method,
            'concurrent_users': concurrent_users,
            'total_requests': concurrent_users * requests_per_user,
            'response_times': [],
            'errors': 0,
            'success_count': 0
        }

        def worker():
            for _ in range(requests_per_user):
                status, elapsed = self._make_request(endpoint, method)

                if 200 <= status < 300:
                    results['response_times'].append(elapsed)
                    results['success_count'] += 1
                else:
                    results['errors'] += 1

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(worker) for _ in range(concurrent_users)]
            for future in as_completed(futures):
                future.result()

        total_time = time.time() - start_time
        results['total_time'] = total_time
        results['rps'] = results['success_count'] / total_time if total_time > 0 else 0

        return results

    def calculate_statistics(self, response_times: List[float]) -> Dict:
        """応答時間統計計算"""
        if not response_times:
            return {}

        sorted_times = sorted(response_times)
        n = len(sorted_times)

        return {
            'count': n,
            'min_ms': min(sorted_times) * 1000,
            'max_ms': max(sorted_times) * 1000,
            'mean_ms': mean(sorted_times) * 1000,
            'median_ms': median(sorted_times) * 1000,
            'p95_ms': sorted_times[int(n * 0.95)] * 1000 if n > 1 else 0,
            'p99_ms': sorted_times[int(n * 0.99)] * 1000 if n > 1 else 0,
            'stdev_ms': stdev(sorted_times) * 1000 if n > 1 else 0
        }

    def run_baseline_suite(self):
        """ベースライン計測スイート実行"""
        print("=" * 80)
        print("⚡ Block 2 パフォーマンスベースライン計測")
        print("=" * 80)

        # テスト対象エンドポイント
        test_cases = [
            # (endpoint, method, description)
            ('/api/v1/appointments', 'GET', 'アポ一覧取得'),
            ('/api/v1/sales-reps', 'GET', '営業マン一覧取得'),
            ('/api/v1/kpi/daily-summary', 'GET', '日次KPI取得'),
            ('/api/v1/kpi/monthly-performance', 'GET', '月間パフォーマンス取得'),
        ]

        # 負荷シナリオ
        load_scenarios = [
            (1, 10, "ベースライン: 1ユーザー x 10リクエスト"),
            (5, 10, "軽負荷: 5ユーザー x 10リクエスト"),
            (10, 10, "中負荷: 10ユーザー x 10リクエスト"),
            (20, 5, "高負荷: 20ユーザー x 5リクエスト"),
        ]

        all_results = []

        for concurrent_users, requests_per_user, scenario_name in load_scenarios:
            print(f"\n{'='*80}")
            print(f"📊 {scenario_name}")
            print(f"{'='*80}")

            for endpoint, method, description in test_cases:
                print(f"\n🧪 {description} ({method} {endpoint})")

                result = self.test_endpoint_performance(
                    endpoint,
                    method,
                    concurrent_users,
                    requests_per_user
                )

                stats = self.calculate_statistics(result['response_times'])
                all_results.append({'scenario': scenario_name, **result, **stats})

                # 結果出力
                if stats:
                    print(f"  ✓ 成功: {result['success_count']}/{result['total_requests']}")
                    print(f"  ✗ 失敗: {result['errors']}")
                    print(f"  ⏱️  平均応答時間: {stats['mean_ms']:.0f}ms")
                    print(f"  ⏱️  中央値: {stats['median_ms']:.0f}ms")
                    print(f"  ⏱️  P95: {stats['p95_ms']:.0f}ms")
                    print(f"  ⏱️  P99: {stats['p99_ms']:.0f}ms")
                    print(f"  ⏱️  スループット: {result['rps']:.1f} RPS")
                else:
                    print(f"  ⚠️  データ不足またはエラーが発生しました")

        self._print_detailed_report(all_results)
        self._print_recommendations(all_results)
        return all_results

    def _print_detailed_report(self, results: List[Dict]):
        """詳細レポート出力"""
        print(f"\n{'='*80}")
        print("📈 詳細パフォーマンスレポート")
        print(f"{'='*80}")

        # エンドポイント別サマリー
        print("\n【エンドポイント別応答時間】")
        endpoints = {}
        for result in results:
            endpoint = result['endpoint']
            if endpoint not in endpoints:
                endpoints[endpoint] = []
            if 'mean_ms' in result:
                endpoints[endpoint].append(result['mean_ms'])

        for endpoint, times in sorted(endpoints.items()):
            if not times:
                print(f"  {endpoint:<40} 計測なし(全リクエスト失敗)")
                continue
            avg_time = sum(times) / len(times)
            print(f"  {endpoint:<40} 平均 {avg_time:>6.0f}ms")

        # シナリオ別サマリー
        print("\n【負荷シナリオ別の平均応答時間】")
        scenarios = {}
        for result in results:
            scenario = result['scenario']
            if scenario not in scenarios:
                scenarios[scenario] = []
            if 'mean_ms' in result:
                scenarios[scenario].append(result['mean_ms'])

        for scenario, times in sorted(scenarios.items()):
            if not times:
                print(f"  {scenario:<50} 計測なし(全リクエスト失敗)")
                continue
            avg_time = sum(times) / len(times)
            rps_values = [r.get('rps', 0) for r in results if r.get('scenario') == scenario]
            avg_rps = sum(rps_values) / len(rps_values) if rps_values else 0
            print(f"  {scenario:<50} 平均 {avg_time:>6.0f}ms ({avg_rps:>5.1f} RPS)")

    def _print_recommendations(self, results: List[Dict]):
        """推奨事項出力"""
        print(f"\n{'='*80}")
        print("💡 パフォーマンス推奨事項")
        print(f"{'='*80}")

        # 基準値
        P95_THRESHOLD = 1000  # 1秒
        P99_THRESHOLD = 2000  # 2秒
        ERROR_THRESHOLD = 0.01  # 1%

        issues = []

        # P95応答時間チェック
        for result in results:
            if result.get('p95_ms', 0) > P95_THRESHOLD:
                issues.append(f"⚠️  {result['endpoint']} の P95 応答時間が {result['p95_ms']:.0f}ms (基準値: {P95_THRESHOLD}ms)")

        # P99応答時間チェック
        for result in results:
            if result.get('p99_ms', 0) > P99_THRESHOLD:
                issues.append(f"⚠️  {result['endpoint']} の P99 応答時間が {result['p99_ms']:.0f}ms (基準値: {P99_THRESHOLD}ms)")

        # エラー率チェック
        for result in results:
            if result['total_requests'] > 0:
                error_rate = result['errors'] / result['total_requests']
                if error_rate > ERROR_THRESHOLD:
                    issues.append(f"❌ {result['endpoint']} のエラー率が {error_rate*100:.1f}% (基準値: {ERROR_THRESHOLD*100:.1f}%)")

        if issues:
            for issue in issues:
                print(f"\n{issue}")
            print("\n【改善提案】")
            print("1. ✅ 全15エンドポイントの応答時間が基準値を満たしているか確認")
            print("2. ✅ データベースインデックスが適切に設定されているか確認")
            print("3. ✅ キャッシュレイヤー (Redis等) の導入検討")
            print("4. ✅ API呼び出し時のバッチ処理最適化")
            print("5. ✅ 本番環境での負荷テスト (1000 RPS以上)")
        else:
            print("\n✅ すべてのパフォーマンス基準を満たしています")
            print("✅ 本番環境への展開準備が整っています")

    def run_stress_test(self, duration_seconds: int = 60, max_concurrent: int = 50):
        """ストレステスト (持続負荷)"""
        print(f"\n{'='*80}")
        print(f"💥 ストレステスト ({duration_seconds}秒間、最大{max_concurrent}ユーザー)")
        print(f"{'='*80}")

        response_times = []
        errors = 0
        success = 0
        start_time = time.time()

        def stress_worker():
            nonlocal errors, success
            while time.time() - start_time < duration_seconds:
                status, elapsed = self._make_request('/api/v1/appointments', 'GET')
                if 200 <= status < 300:
                    response_times.append(elapsed)
                    success += 1
                else:
                    errors += 1

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = [executor.submit(stress_worker) for _ in range(max_concurrent)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    errors += 1

        total_time = time.time() - start_time
        stats = self.calculate_statistics(response_times)

        print(f"\n✅ 成功: {success}件")
        print(f"❌ 失敗: {errors}件")
        print(f"⏱️  総実行時間: {total_time:.1f}秒")
        print(f"🚀 スループット: {success/total_time:.1f} RPS")

        if stats:
            print(f"📊 応答時間:")
            print(f"   平均: {stats['mean_ms']:.0f}ms")
            print(f"   中央値: {stats['median_ms']:.0f}ms")
            print(f"   P95: {stats['p95_ms']:.0f}ms")
            print(f"   P99: {stats['p99_ms']:.0f}ms")

        error_rate = errors / (success + errors) if (success + errors) > 0 else 0
        print(f"📈 エラー率: {error_rate*100:.2f}%")

        return error_rate <= 0.01  # エラー率1%以下で合格

def main():
    import argparse
    parser = argparse.ArgumentParser(description="パフォーマンスベースライン計測")
    parser.add_argument('--base-url', default='http://localhost:3000', help='ベースURL')
    parser.add_argument('--stress-test', action='store_true', help='ストレステストも実行')
    parser.add_argument('--duration', type=int, default=60, help='ストレステスト期間 (秒)')
    parser.add_argument('--results-dir', default=str(Path(__file__).parent / 'results'),
                        help='結果JSON(performance.json)の出力先')

    args = parser.parse_args()

    baseline = PerformanceBaseline(base_url=args.base_url)

    # ベースライン計測。G1 基準(P95 ≤ 1000ms / エラー率 ≤ 1%)は results_writer で判定する。
    # 計測途中で落ちても「不合格の記録」は必ず残す
    import results_writer
    import traceback
    error = None
    all_results = []
    try:
        all_results = baseline.run_baseline_suite() or []
    except Exception:
        error = traceback.format_exc()
        print(error, file=sys.stderr)

    summary = results_writer.summarize_performance(all_results)
    if error:
        summary['passed'] = False
        summary['error'] = error.strip().splitlines()[-1]
    results_writer.write_result(args.results_dir, 'performance', base_url=args.base_url, **summary)

    # ストレステスト（オプション）
    if args.stress_test:
        stress_ok = baseline.run_stress_test(duration_seconds=args.duration)
        sys.exit(0 if (summary['passed'] and stress_ok) else 1)
    else:
        sys.exit(0 if summary['passed'] else 1)

if __name__ == "__main__":
    main()
