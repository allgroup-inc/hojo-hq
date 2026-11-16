#!/usr/bin/env python3
"""
完全版: KachiTalk全ログ × 営業成績の相関分析
- 6段階営業プロセスの完全性スコア
- 成約・失注・保留の詳細分類
- 営業スタイルの自動認識
- 次のアクション提案の自動生成

Usage:
  python3 kachitalk_full_correlation_analysis.py --source api --output results.json
  python3 kachitalk_full_correlation_analysis.py --source csv --file logs.csv --output results.json
"""

import json
import csv
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from statistics import mean, stdev, median
from collections import defaultdict

# 営業8名
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

# 6段階営業プロセス（キーワードマッピング）
SALES_PROCESS_KEYWORDS = {
    '①アプローチ': [
        '名乗り', '申し遅れました', 'こんにちは', '本日は', '申します',
        '申し上げたい', '名乗り遅れました', 'お疲れ様', 'お忙しい', 'ご来店',
        'ご来社', 'いつも', 'お世話'
    ],
    '②ヒアリング': [
        '前回', 'おさらい', 'いくつかお聞き', 'どのような', 'ご状況',
        'お困り', 'お過ごし', '問題', 'ニーズ', 'ご意向', 'お困りですか',
        'どのようなお困りごと', 'ご状況いかがでしょう'
    ],
    '③提案': [
        'このような保障', 'お勧め', 'いかがでしょう', '保障内容', '提案',
        'ご意向に沿った', 'このような内容', 'お勧めしたい', 'ご提案',
        'お勧めできます', 'ご説明'
    ],
    '④クロージング': [
        '申込', '手続き', '契約', '進める', '署名', '捺印',
        '進めさせていただく', '手続きをお願い', '進めさせていただけますか',
        'ご同意', '了承'
    ],
    '⑤申込契約': [
        '申込完了', '契約しました', '申込いたします', '申込させていただく',
        '契約書に署名', '申込が完了', '完了いたします'
    ],
    '⑥紹介入手': [
        '紹介', 'お知り合い', 'ご親戚', 'ご友人', 'どなたか', 'ご知人',
        'ご紹介', '何かご存じ', 'どなたか保険が必要'
    ]
}

# 下地の営業チェックリスト（7項目）
SHIMOJI_CHECKLIST = {
    '①推奨理由説明': [
        '推奨', '理由をお伝え', 'なぜこの保険', 'この保険が適切', 'おすすめする理由',
        'こちらの保障が必要', 'お役に立つ', 'ぴったり', 'この内容が最適'
    ],
    '②書面交付・口頭説明': [
        'ご契約のしおり', 'しおり', '約款', '書面', '契約書', '口頭説明',
        'ご説明', 'お約束', 'ご確認', '内容確認'
    ],
    '③公的保険情報提供': [
        '公的保険', '社会保障', '公的制度', '健康保険', '公的', '国民健康保険',
        '会社の保険', '健康診断', '給付', '保障内容の確認'
    ],
    '④検討時間確保': [
        '検討', '考えておく', 'じっくり', 'お考えいただく', 'ご検討',
        '考えていただく', 'ご確認', 'お時間', '次回', 'またの機会'
    ],
    '⑤高齢者募集ルール遵守': [
        '年齢', '高齢', 'シニア', '70代', '80代', '90代', 'ご高齢', 'ご年齢',
        '定年', '退職'
    ],
    '⑥適合性確認': [
        '適合', 'お手伝い', 'お力になれる', '最適', 'ご状況に合わせた', 'ニーズ',
        'ご要望', 'ぴったり', 'マッチ', 'こちらが最適'
    ],
    '⑦意向相違確認': [
        '最初', '当初', '予定', '変わった', '追加', '変更', '当初とは',
        'さらに', '今回', '新たに', '別のご希望'
    ]
}

class KachiTalkFullAnalyzer:
    def __init__(self):
        self.logs = []
        self.analysis_results = {}
        self.correlation_metrics = {}
        self.timestamp = datetime.now().isoformat()

    def load_logs_from_json(self, file_path: str) -> bool:
        """Load call logs from JSON file (sample or exported)"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.logs = json.load(f)
            print(f'✓ JSON から {len(self.logs)} 件のログを読み込みました')
            return True
        except Exception as e:
            print(f'✗ JSON読込エラー: {e}')
            return False

    def load_logs_from_csv(self, file_path: str) -> bool:
        """Load call logs from CSV export (KachiTalk admin CSV)"""
        try:
            logs = []
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Map CSV columns to standard format
                    log = {
                        'staff_name': row.get('営業マン') or row.get('staff_name', ''),
                        'date': row.get('日時') or row.get('date', ''),
                        'customer_name': row.get('顧客名') or row.get('customer_name', ''),
                        'duration_minutes': self._parse_duration(row.get('通話時間（分）') or row.get('duration_minutes', 0)),
                        'transcript_summary': row.get('通話内容_要約') or row.get('transcript_summary', ''),
                        'notes': row.get('メモ') or row.get('notes', '')
                    }
                    if log['staff_name'] in STAFF_NAMES:
                        logs.append(log)

            self.logs = logs
            print(f'✓ CSV から {len(logs)} 件のログを読み込みました')
            return True
        except Exception as e:
            print(f'✗ CSV読込エラー: {e}')
            return False

    def _parse_duration(self, value) -> int:
        """Convert duration value to minutes"""
        try:
            return int(float(str(value).strip()) or 0)
        except:
            return 0

    def analyze_process_steps(self, transcript: str) -> Tuple[Dict[str, bool], List[str]]:
        """Analyze 6-step process completion from transcript"""
        steps_executed = {}
        step_order = []

        for step_id, keywords in SALES_PROCESS_KEYWORDS.items():
            found = any(kw in transcript for kw in keywords)
            steps_executed[step_id] = found
            if found:
                step_order.append(step_id)

        return steps_executed, step_order

    def calculate_process_completeness(self, steps_executed: Dict) -> float:
        """Calculate process completeness score (0-100)"""
        count = sum(1 for v in steps_executed.values() if v)
        return (count / 6) * 100

    def analyze_outcome(self, notes: str) -> str:
        """Determine call outcome: 成約/失注/保留"""
        notes_str = str(notes or '')
        if any(x in notes_str for x in ['成約', '申込', '完了', '契約']):
            return '成約'
        elif any(x in notes_str for x in ['失注', '今回は', '失礼', '結構', 'では今回']):
            return '失注'
        else:
            return '保留'

    def analyze_shimoji_checklist(self, transcript: str, notes: str) -> Tuple[Dict[str, bool], float]:
        """Analyze 下地's 7-item compliance checklist from transcript and notes"""
        combined_text = f"{transcript} {notes}"
        items_executed = {}

        for item_id, keywords in SHIMOJI_CHECKLIST.items():
            found = any(kw in combined_text for kw in keywords)
            items_executed[item_id] = found

        # Calculate compliance score (0-100)
        count = sum(1 for v in items_executed.values() if v)
        score = (count / 7) * 100

        return items_executed, score

    def correlate_with_sales_metrics(self):
        """Main analysis function: correlate call quality with sales performance"""
        print("\n" + "="*100)
        print("KachiTalk全ログ分析 × 営業成績の相関")
        print("="*100 + "\n")

        # Group logs by staff
        logs_by_staff = defaultdict(list)
        for log in self.logs:
            staff = log.get('staff_name', '')
            if staff in STAFF_NAMES:
                logs_by_staff[staff].append(log)

        # Analyze each staff member
        for staff_name in sorted(STAFF_NAMES):
            staff_logs = logs_by_staff.get(staff_name, [])
            if not staff_logs:
                print(f"⚠ {staff_name}: ログなし")
                continue

            self._analyze_individual_staff(staff_name, staff_logs)

        # Cross-staff analysis
        self._cross_staff_classification()

    def _analyze_individual_staff(self, staff_name: str, logs: List):
        """Detailed analysis for individual staff member"""
        print(f"\n📊 {staff_name}")
        print("-" * 100)

        # Initialize metrics
        process_scores = []
        outcomes = {'成約': 0, '失注': 0, '保留': 0}
        call_durations = []
        process_steps_by_outcome = defaultdict(lambda: defaultdict(int))
        process_completeness_by_outcome = {'成約': [], '失注': [], '保留': []}

        # Shimoji checklist metrics
        shimoji_scores = []
        shimoji_items_by_outcome = defaultdict(lambda: defaultdict(int))
        shimoji_checklist_data = []

        # Analyze each call
        for i, log in enumerate(logs, 1):
            date = log.get('date', '')
            customer = log.get('customer_name', '')
            duration = log.get('duration_minutes', 0)
            transcript = log.get('transcript_summary', '')
            notes = log.get('notes', '')

            # Analyze process
            steps, step_order = self.analyze_process_steps(transcript)
            completeness = self.calculate_process_completeness(steps)
            outcome = self.analyze_outcome(notes)

            # Analyze Shimoji checklist
            shimoji_items, shimoji_score = self.analyze_shimoji_checklist(transcript, notes)

            # Collect metrics
            process_scores.append(completeness)
            outcomes[outcome] += 1
            call_durations.append(duration)
            process_completeness_by_outcome[outcome].append(completeness)
            shimoji_scores.append(shimoji_score)
            shimoji_checklist_data.append({
                'date': date,
                'customer': customer,
                'items': shimoji_items,
                'score': shimoji_score,
                'outcome': outcome
            })

            # Record steps by outcome
            for step_id, executed in steps.items():
                if executed:
                    process_steps_by_outcome[outcome][step_id] += 1

            # Detailed call output
            if i <= 3 or i > len(logs) - 3:  # Show first 3 and last 3
                print(f"  {date} {i}: {customer}（{duration}分）")
                print(f"    結果: {outcome} / {notes}")
                print(f"    プロセス完全性: {completeness:.0f}点")

                executed_steps = [s for s, v in steps.items() if v]
                if executed_steps:
                    print(f"    実施: {', '.join(executed_steps)}")

            if i == 3 and len(logs) > 6:
                print(f"  ... ({len(logs) - 6} 件省略)")

        # Aggregate analysis
        print(f"\n【統計分析】")
        print(f"  総通話件数: {len(logs)}件")
        print(f"  平均通話時間: {mean(call_durations):.1f}分" if call_durations else "  データなし")
        if len(process_scores) > 1:
            print(f"  平均プロセス完全性: {mean(process_scores):.1f}点")
            print(f"  最小/最大: {min(process_scores):.0f}〜{max(process_scores):.0f}点")

        print(f"  成約: {outcomes['成約']}件（{outcomes['成約']/len(logs)*100:.0f}%）")
        print(f"  失注: {outcomes['失注']}件（{outcomes['失注']/len(logs)*100:.0f}%）")
        print(f"  保留: {outcomes['保留']}件（{outcomes['保留']/len(logs)*100:.0f}%）")

        # Process execution rates
        print(f"\n【6段階プロセス実施率】")
        total_by_step = defaultdict(int)
        for step_id in SALES_PROCESS_KEYWORDS.keys():
            for outcome_logs in process_completeness_by_outcome.values():
                total_by_step[step_id] = sum(1 for log in self.logs
                    if any(kw in log.get('transcript_summary', '')
                        for kw in SALES_PROCESS_KEYWORDS[step_id]))

        for step_id in sorted(SALES_PROCESS_KEYWORDS.keys()):
            step_count = sum(process_steps_by_outcome[outcome][step_id]
                           for outcome in outcomes.keys())
            rate = (step_count / len(logs) * 100) if len(logs) > 0 else 0
            print(f"  {step_id}: {rate:.0f}%（{step_count}件）")

        # Shimoji compliance checklist
        print(f"\n【下地チェックリスト実施率（コンプライアンス検証）】")
        shimoji_item_totals = defaultdict(int)
        for data in shimoji_checklist_data:
            for item_id, executed in data['items'].items():
                if executed:
                    shimoji_item_totals[item_id] += 1

        for item_id in sorted(SHIMOJI_CHECKLIST.keys()):
            item_count = shimoji_item_totals.get(item_id, 0)
            rate = (item_count / len(logs) * 100) if len(logs) > 0 else 0
            print(f"  {item_id}: {rate:.0f}%（{item_count}件）")

        if shimoji_scores:
            avg_shimoji_score = mean(shimoji_scores)
            print(f"\n  平均チェックリスト実行スコア: {avg_shimoji_score:.1f}点")

        # Sales style classification
        print(f"\n【営業スタイル判定】")
        style_markers = []

        avg_duration = mean(call_durations) if call_durations else 0
        avg_completeness = mean(process_scores) if process_scores else 0
        contract_rate = outcomes['成約'] / len(logs) if len(logs) > 0 else 0

        if contract_rate >= 0.20:
            style_markers.append("✨ 高成約率営業（20%以上）")
        elif contract_rate >= 0.15:
            style_markers.append("◎ 良好成約率（15%以上）")
        else:
            style_markers.append("△ 成約率改善型（15%未満）")

        if avg_duration < 15:
            style_markers.append("⚡ 短時間効率営業（<15分）")
        elif avg_duration > 18:
            style_markers.append("🕐 じっくり対応型（>18分）")
        else:
            style_markers.append("💼 標準フロー型（15-18分）")

        if avg_completeness > 75:
            style_markers.append("📋 教科書的プロセス実行型")
        elif avg_completeness < 60:
            style_markers.append("🎯 ショートカット型（プロセススキップで成約）")

        if contract_rate > 0 and process_completeness_by_outcome['成約']:
            high_completeness_contracts = sum(1 for s in process_completeness_by_outcome['成約']
                                            if s >= 67)
            if high_completeness_contracts == 0:
                style_markers.append("🚀 プロセス無視型成約")

        for marker in style_markers:
            print(f"  {marker}")

        # Store results
        self.analysis_results[staff_name] = {
            'call_count': len(logs),
            'avg_duration': avg_duration,
            'avg_completeness': avg_completeness,
            'contract_rate': contract_rate,
            'contract_count': outcomes['成約'],
            'process_scores': process_scores,
            'style_markers': style_markers,
            'outcomes': outcomes,
            'shimoji_checklist': {
                'avg_score': mean(shimoji_scores) if shimoji_scores else 0,
                'item_execution_rates': {
                    item_id: (shimoji_item_totals.get(item_id, 0) / len(logs) * 100) if len(logs) > 0 else 0
                    for item_id in SHIMOJI_CHECKLIST.keys()
                },
                'detailed_logs': shimoji_checklist_data
            }
        }

        print("-" * 100)

    def _cross_staff_classification(self):
        """Cross-staff classification and benchmarking"""
        print("\n" + "="*100)
        print("営業スタイル横断分類 ＆ ベンチマーク")
        print("="*100 + "\n")

        # Sort by contract rate
        sorted_staff = sorted(
            self.analysis_results.items(),
            key=lambda x: x[1]['contract_rate'],
            reverse=True
        )

        print("【成約率ランキング】")
        for rank, (staff_name, metrics) in enumerate(sorted_staff, 1):
            rate = metrics['contract_rate'] * 100
            completeness = metrics['avg_completeness']
            marker = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else "  "
            print(f"{marker} {rank}位: {staff_name}")
            print(f"     成約率: {rate:.1f}% ({metrics['contract_count']}/{metrics['call_count']}件)")
            print(f"     プロセス完全性: {completeness:.1f}点")
            print(f"     通話時間: {metrics['avg_duration']:.1f}分")

        print("\n【成約率と品質の相関パターン】")
        high_rate_high_quality = []
        high_rate_low_quality = []
        low_rate_high_quality = []
        low_rate_low_quality = []

        for staff_name, metrics in self.analysis_results.items():
            rate = metrics['contract_rate']
            completeness = metrics['avg_completeness']

            if rate >= 0.15 and completeness >= 70:
                high_rate_high_quality.append(staff_name)
            elif rate >= 0.15 and completeness < 70:
                high_rate_low_quality.append(staff_name)
            elif rate < 0.15 and completeness >= 70:
                low_rate_high_quality.append(staff_name)
            else:
                low_rate_low_quality.append(staff_name)

        print(f"\n◎ パターン①：高成約率 × 高品質（理想的）")
        if high_rate_high_quality:
            for name in high_rate_high_quality:
                print(f"  - {name}")
            print("  → 推奨: このメンバーの営業手法をチーム内で共有")
        else:
            print("  → 該当者なし（改善の目標値として設定）")

        print(f"\n△ パターン②：高成約率 × 低品質（属人性が高い）")
        if high_rate_low_quality:
            for name in high_rate_low_quality:
                print(f"  - {name}")
            print("  → 推奨: プロセス実行の定着支援（持続性向上）")
        else:
            print("  → 該当者なし（品質向上の余地あり）")

        print(f"\n◆ パターン③：低成約率 × 高品質（潜在能力あり）")
        if low_rate_high_quality:
            for name in low_rate_high_quality:
                print(f"  - {name}")
            print("  → 推奨: クロージング後の『紹介入手』強化")
        else:
            print("  → 該当者なし")

        print(f"\n✗ パターン④：低成約率 × 低品質（要改善）")
        if low_rate_low_quality:
            for name in low_rate_low_quality:
                print(f"  - {name}")
            print("  → 推奨: ①②③の基本プロセスの定着支援（集中訓練）")
        else:
            print("  → 該当者なし")

    def export_results(self, output_path: str):
        """Export analysis results to JSON"""
        output = {
            'timestamp': self.timestamp,
            'log_count': len(self.logs),
            'staff_analysis': self.analysis_results,
            'analysis_version': '1.0'
        }

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            print(f"\n✓ 分析結果をエクスポート: {output_path}")
            return True
        except Exception as e:
            print(f"✗ エクスポートエラー: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(
        description='KachiTalk全ログ × 営業成績の完全相関分析'
    )
    parser.add_argument(
        '--source',
        choices=['json', 'csv'],
        default='json',
        help='データソース: json (sample) または csv (KachiTalk admin export)'
    )
    parser.add_argument(
        '--file',
        default='/home/user/hojo-hq/enlife/data/kachitalk_sample_logs.json',
        help='入力ファイルパス'
    )
    parser.add_argument(
        '--output',
        default='/tmp/kachitalk_analysis_results.json',
        help='結果出力ファイル'
    )

    args = parser.parse_args()

    analyzer = KachiTalkFullAnalyzer()

    # Load data
    if args.source == 'json':
        if not analyzer.load_logs_from_json(args.file):
            sys.exit(1)
    elif args.source == 'csv':
        if not analyzer.load_logs_from_csv(args.file):
            sys.exit(1)

    if not analyzer.logs:
        print('✗ ログデータが見つかりません')
        sys.exit(1)

    # Run analysis
    analyzer.correlate_with_sales_metrics()

    # Export results
    analyzer.export_results(args.output)

    print("\n✓ 分析完了")

if __name__ == '__main__':
    main()
