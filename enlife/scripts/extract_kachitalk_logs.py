#!/usr/bin/env python3
"""
Extract KachiTalk call logs and analyze against 6-step sales process checklist

Usage:
  python3 extract_kachitalk_logs.py --month "8月" --output ./kachitalk_logs.csv
  python3 extract_kachitalk_logs.py --month "9月" --format sheets
"""

import sys
import json
import csv
import argparse
from datetime import datetime
from typing import List, Dict, Tuple

# Sales team (8 members)
STAFF_NAMES = [
    '前原　芳乃',
    '奈須　章',
    '下地　健太',
    '幸良　妃奈代',
    '徳元　孝樹',
    '喜納　礼奈',
    '名嘉山　望',
    '狩俣　亜希乃'
]

# 6-step sales process checklist
SALES_PROCESS_STEPS = {
    '①アプローチ': {
        'name': 'アプローチ（名乗り/自己紹介）',
        'keywords': ['名乗り', '自己紹介', 'こんにちは', '申し遅れました', '本日は'],
        'purpose': '顧客との信頼構築・緊張緩和'
    },
    '②ヒアリング': {
        'name': 'ヒアリング（前回のおさらい）',
        'keywords': ['前回', 'いくつかお聞き', 'どのような', 'ご状況', 'お困りですか'],
        'purpose': '顧客の問題解決ニーズ把握'
    },
    '③提案': {
        'name': '提案',
        'keywords': ['このような保障', 'お勧めしたいのは', 'いかがでしょう', '保障内容'],
        'purpose': 'ご意向に沿った提案'
    },
    '④クロージング': {
        'name': 'クロージング',
        'keywords': ['申込', '次回', '手続き', '契約', '進めさせていただく'],
        'purpose': '申込への案内'
    },
    '⑤申込契約': {
        'name': '申込・契約',
        'keywords': ['申込完了', '契約しました', '署名', '捺印'],
        'purpose': '申込手続き完了'
    },
    '⑥紹介入手': {
        'name': '紹介入手',
        'keywords': ['紹介', 'お知り合い', 'ご親戚', '立替', 'どなたか'],
        'purpose': '紹介顧客獲得'
    }
}

class KachiTalkLogAnalyzer:
    def __init__(self):
        self.logs = []
        self.month = None

    def extract_from_kachitalk(self, month: str, api_key: str = None) -> List[Dict]:
        """
        Extract logs from KachiTalk admin API

        Note: This is a template. Actual implementation requires:
        1. KachiTalk API credentials
        2. API endpoint configuration
        3. OAuth2 or API key authentication

        Current flow:
        1. Load sample data from kachitalk_sample_logs.json (if exists)
        2. OR manually paste CSV data from KachiTalk admin dashboard
        """

        self.month = month

        # Try to load sample data
        try:
            with open('/home/user/hojo-hq/enlife/data/kachitalk_sample_logs.json', 'r', encoding='utf-8') as f:
                self.logs = json.load(f)
            print(f'✓ サンプルデータを読み込みました: {len(self.logs)}件')
            return self.logs
        except FileNotFoundError:
            print('※ データが見つかりません')
            print('   1. KachiTalk管理画面(https://kachitalk-line-enlife.azurewebsites.net/admin)から')
            print('   2. ログを自社CSVとしてエクスポート')
            print('   3. enlife/data/kachitalk_sample_logs.json に配置してください')
            return []

    def analyze_call_quality(self, log_entry: Dict) -> Tuple[Dict, float]:
        """
        Analyze single call against 6-step checklist

        Returns:
          (step_results: dict, quality_score: float)
        """

        transcript = str(log_entry.get('transcript_summary', '') or '')

        step_results = {}
        matched_steps = 0

        for step_id, step_info in SALES_PROCESS_STEPS.items():
            # Check if keywords appear in transcript (Japanese text, exact match)
            found = any(kw in transcript for kw in step_info['keywords'])
            step_results[step_id] = found
            if found:
                matched_steps += 1

        # Calculate quality score
        # Base: number of steps executed / 6
        # Bonus: call duration (longer = better, up to 20 minutes)
        duration = log_entry.get('duration_minutes', 0) or 0
        duration_bonus = min((duration / 20) * 20, 20)  # Max 20 points for duration

        quality_score = (matched_steps / 6) * 80 + duration_bonus
        quality_score = min(100, max(0, quality_score))

        return step_results, round(quality_score, 1)

    def process_logs(self) -> List[Dict]:
        """
        Process all logs and add quality analysis
        """

        analyzed_logs = []

        for log in self.logs:
            if log.get('staff_name') not in STAFF_NAMES:
                continue

            step_results, quality_score = self.analyze_call_quality(log)

            # Format for Google Sheets
            analyzed = {
                '営業マン': log.get('staff_name', ''),
                '日時': log.get('date', ''),
                '顧客名': log.get('customer_name', ''),
                '通話時間（分）': log.get('duration_minutes', 0),
                '通話内容_要約': log.get('transcript_summary', '')[:100],  # First 100 chars
                '①アプローチ_実施': '○' if step_results.get('①アプローチ') else '',
                '②ヒアリング_実施': '○' if step_results.get('②ヒアリング') else '',
                '③提案_実施': '○' if step_results.get('③提案') else '',
                '④クロージング_実施': '○' if step_results.get('④クロージング') else '',
                '⑤申込契約_実施': '○' if step_results.get('⑤申込契約') else '',
                '⑥紹介入手_実施': '○' if step_results.get('⑥紹介入手') else '',
                '品質スコア': quality_score,
                'メモ': log.get('notes', '')
            }

            analyzed_logs.append(analyzed)

        return analyzed_logs

    def export_to_csv(self, output_path: str):
        """Export analyzed logs to CSV for Google Sheets import"""

        if not self.logs:
            print('✗ ログデータが見つかりません')
            return False

        analyzed = self.process_logs()

        if not analyzed:
            print('✗ 対象営業マンのログがありません')
            return False

        fieldnames = [
            '営業マン', '日時', '顧客名', '通話時間（分）', '通話内容_要約',
            '①アプローチ_実施', '②ヒアリング_実施', '③提案_実施',
            '④クロージング_実施', '⑤申込契約_実施', '⑥紹介入手_実施',
            '品質スコア', 'メモ'
        ]

        try:
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(analyzed)

            print(f'✓ データをエクスポートしました: {output_path}')
            print(f'  - レコード数: {len(analyzed)}')
            print(f'  - 対象営業マン: {len(set(log["営業マン"] for log in analyzed))}')
            return True
        except Exception as e:
            print(f'✗ エクスポートエラー: {e}')
            return False

    def print_summary(self):
        """Print analysis summary to console"""

        if not self.logs:
            return

        analyzed = self.process_logs()

        # Aggregate by salesperson
        by_staff = {}
        for log in analyzed:
            staff = log['営業マン']
            if staff not in by_staff:
                by_staff[staff] = {
                    'calls': [],
                    'total_score': 0,
                    'step_counts': {step: 0 for step in SALES_PROCESS_STEPS.keys()}
                }

            by_staff[staff]['calls'].append(log)
            by_staff[staff]['total_score'] += log['品質スコア']

            for step in SALES_PROCESS_STEPS.keys():
                col = f'{step}_実施'
                if log.get(col) == '○':
                    by_staff[staff]['step_counts'][step] += 1

        # Print summary
        print('\n【KachiTalk 品質分析サマリー】')
        print(f'集計期間: {self.month}')
        print(f'総通話件数: {len(analyzed)}\n')

        for staff in STAFF_NAMES:
            if staff not in by_staff:
                print(f'{staff}: データなし')
                continue

            data = by_staff[staff]
            num_calls = len(data['calls'])
            avg_score = data['total_score'] / num_calls if num_calls > 0 else 0

            print(f'{staff}')
            print(f'  通話件数: {num_calls}')
            print(f'  平均品質スコア: {avg_score:.1f}')

            # Step execution rates
            for step_id, step_info in SALES_PROCESS_STEPS.items():
                count = data['step_counts'].get(step_id, 0)
                rate = (count / num_calls * 100) if num_calls > 0 else 0
                print(f'  {step_id} {step_info["name"]}: {rate:.0f}%')

            print()

def main():
    parser = argparse.ArgumentParser(
        description='KachiTalkログを6段階営業プロセス対応チェックリストで分析'
    )
    parser.add_argument('--month', default='9月', help='集計対象月 (例: "8月", "9月")')
    parser.add_argument('--output', default='/tmp/kachitalk_logs_for_sheets.csv', help='出力CSVファイル')
    parser.add_argument('--api-key', help='KachiTalk API キー（オプション）')
    parser.add_argument('--summary-only', action='store_true', help='サマリー表示のみ')

    args = parser.parse_args()

    analyzer = KachiTalkLogAnalyzer()

    # Extract logs
    logs = analyzer.extract_from_kachitalk(args.month, args.api_key)

    if not logs:
        print('✗ ログの抽出に失敗しました')
        sys.exit(1)

    # Print summary
    analyzer.print_summary()

    # Export to CSV
    if not args.summary_only:
        analyzer.export_to_csv(args.output)
        print(f'\n【次のステップ】')
        print(f'1. Google Sheetsを開く')
        print(f'2. "カチトークログ"シートを選択')
        print(f'3. {args.output} のデータをコピー＆ペースト')
        print(f'4. Apps Scriptで analyzeKachiTalkQuality("9月") を実行')

if __name__ == '__main__':
    main()
