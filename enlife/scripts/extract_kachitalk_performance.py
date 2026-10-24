#!/usr/bin/env python3
"""
Extract KachiTalk performance data (訪問記録・営業成績)
Supports both Excel export and API modes

Usage:
  python3 extract_kachitalk_performance.py --mode excel --file kachitalk_export.xlsx
  python3 extract_kachitalk_performance.py --mode api --api-key <key>
"""

import sys
import json
import csv
import argparse
from datetime import datetime
from typing import List, Dict, Optional
import openpyxl  # For Excel reading

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

class KachiTalkPerformanceAnalyzer:
    def __init__(self):
        self.performance_data = []
        self.monthly_stats = {}

    def load_from_excel(self, file_path: str) -> List[Dict]:
        """Load performance data from Excel export"""
        try:
            wb = openpyxl.load_workbook(file_path)
            ws = wb.active

            data = []
            headers = None

            for row_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
                if row_idx == 1:
                    headers = row
                    continue

                if not row[0]:  # Skip empty rows
                    continue

                # Parse row data
                record = {
                    'date': str(row[0]),
                    'staff_name': str(row[1]) if row[1] else '',
                    'visit_type': str(row[2]) if row[2] else '',
                    'score': int(row[3]) if row[3] else 0,
                    'completion_rate': int(row[4]) if row[4] else 0,
                    'status': str(row[5]) if row[5] else '',
                    'report_id': str(row[6]) if len(row) > 6 and row[6] else '',
                    'notes': str(row[7]) if len(row) > 7 and row[7] else ''
                }

                if record['staff_name'] in STAFF_NAMES:
                    data.append(record)

            self.performance_data = data
            print(f'✓ Excel から {len(data)} 件のデータを読み込みました')
            return data

        except FileNotFoundError:
            print(f'✗ ファイルが見つかりません: {file_path}')
            return []
        except Exception as e:
            print(f'✗ Excel 読み込みエラー: {e}')
            return []

    def load_from_api(self, api_key: str) -> List[Dict]:
        """
        Load performance data from KachiTalk API

        Note: This is a template. Actual implementation requires:
        1. KachiTalk API endpoint
        2. Authentication method
        3. API response parsing
        """
        print('※ KachiTalk API mode: requires API endpoint configuration')
        print('   Placeholder for future API integration')
        return []

    def aggregate_by_staff_and_month(self) -> Dict[str, Dict]:
        """Aggregate performance data by staff member and month"""

        stats = {}

        for record in self.performance_data:
            staff = record['staff_name']
            date_str = record['date']

            # Parse month (YYYY-MM)
            try:
                month = date_str[:7]  # Assume YYYY-MM-DD format
            except:
                month = 'unknown'

            key = f"{staff}_{month}"

            if key not in stats:
                stats[key] = {
                    'staff_name': staff,
                    'month': month,
                    'visit_count': 0,
                    'avg_score': 0,
                    'avg_completion_rate': 0,
                    'ok_count': 0,
                    'total_score': 0,
                    'total_completion': 0
                }

            stats[key]['visit_count'] += 1
            stats[key]['total_score'] += record['score']
            stats[key]['total_completion'] += record['completion_rate']
            if record['status'] == 'OK':
                stats[key]['ok_count'] += 1

        # Calculate averages
        for key in stats:
            count = stats[key]['visit_count']
            if count > 0:
                stats[key]['avg_score'] = round(stats[key]['total_score'] / count, 1)
                stats[key]['avg_completion_rate'] = round(stats[key]['total_completion'] / count, 1)

        self.monthly_stats = stats
        return stats

    def export_to_csv(self, output_path: str) -> bool:
        """Export aggregated performance data to CSV"""

        if not self.monthly_stats:
            self.aggregate_by_staff_and_month()

        fieldnames = [
            '営業マン',
            '対象月',
            '訪問件数',
            '平均スコア',
            '平均完了率',
            'OK件数'
        ]

        try:
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for key in sorted(self.monthly_stats.keys()):
                    stat = self.monthly_stats[key]
                    writer.writerow({
                        '営業マン': stat['staff_name'],
                        '対象月': stat['month'],
                        '訪問件数': stat['visit_count'],
                        '平均スコア': stat['avg_score'],
                        '平均完了率': stat['avg_completion_rate'],
                        'OK件数': stat['ok_count']
                    })

            print(f'✓ CSV にエクスポートしました: {output_path}')
            print(f'  - レコード数: {len(self.monthly_stats)}')
            return True

        except Exception as e:
            print(f'✗ エクスポートエラー: {e}')
            return False

    def export_raw_to_csv(self, output_path: str) -> bool:
        """Export raw performance records to CSV for Google Sheets import"""

        if not self.performance_data:
            print('✗ パフォーマンスデータがありません')
            return False

        fieldnames = [
            '日付',
            '営業マン',
            '訪問種別',
            'スコア',
            '完了率',
            'ステータス',
            'レポートID',
            'メモ'
        ]

        try:
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for record in self.performance_data:
                    writer.writerow({
                        '日付': record['date'],
                        '営業マン': record['staff_name'],
                        '訪問種別': record['visit_type'],
                        'スコア': record['score'],
                        '完了率': record['completion_rate'],
                        'ステータス': record['status'],
                        'レポートID': record['report_id'],
                        'メモ': record['notes']
                    })

            print(f'✓ 詳細データをエクスポートしました: {output_path}')
            print(f'  - レコード数: {len(self.performance_data)}')
            return True

        except Exception as e:
            print(f'✗ エクスポートエラー: {e}')
            return False

    def print_summary(self):
        """Print summary to console"""

        if not self.monthly_stats:
            self.aggregate_by_staff_and_month()

        print('\n【KachiTalk 営業成績分析サマリー】')
        print(f'総訪問件数: {len(self.performance_data)}')
        print(f'対象営業マン数: {len(set(s["staff_name"] for s in self.performance_data))}')

        print('\n【営業マン別月次成績】')
        for key in sorted(self.monthly_stats.keys()):
            stat = self.monthly_stats[key]
            print(f'{stat["staff_name"]} ({stat["month"]})')
            print(f'  訪問件数: {stat["visit_count"]}')
            print(f'  平均スコア: {stat["avg_score"]}')
            print(f'  平均完了率: {stat["avg_completion_rate"]}%')
            print(f'  OK件数: {stat["ok_count"]}')
            print()

def main():
    parser = argparse.ArgumentParser(
        description='KachiTalk営業成績データを抽出・分析'
    )
    parser.add_argument('--mode', default='excel', choices=['excel', 'api'],
                        help='データ取得モード (excel or api)')
    parser.add_argument('--file', help='Excel ファイルパス (mode=excel の場合)')
    parser.add_argument('--api-key', help='KachiTalk API キー (mode=api の場合)')
    parser.add_argument('--output', default='/tmp/kachitalk_performance.csv',
                        help='出力 CSV ファイルパス')
    parser.add_argument('--raw', action='store_true',
                        help='詳細データ(未集約)をエクスポート')
    parser.add_argument('--summary-only', action='store_true',
                        help='サマリー表示のみ')

    args = parser.parse_args()

    analyzer = KachiTalkPerformanceAnalyzer()

    # Load data
    if args.mode == 'excel':
        if not args.file:
            print('✗ --file を指定してください')
            sys.exit(1)
        analyzer.load_from_excel(args.file)
    elif args.mode == 'api':
        if not args.api_key:
            print('✗ --api-key を指定してください')
            sys.exit(1)
        analyzer.load_from_api(args.api_key)

    if not analyzer.performance_data:
        print('✗ データの読み込みに失敗しました')
        sys.exit(1)

    # Print summary
    analyzer.print_summary()

    # Export
    if not args.summary_only:
        if args.raw:
            analyzer.export_raw_to_csv(args.output)
        else:
            analyzer.export_to_csv(args.output)
        print(f'\n【次のステップ】')
        print(f'1. Google Sheets を開く')
        print(f'2. 「営業成績データ」シートを選択')
        print(f'3. {args.output} のデータをコピー＆ペースト')

if __name__ == '__main__':
    main()
