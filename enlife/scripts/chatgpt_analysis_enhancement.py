#!/usr/bin/env python3
"""
ChatGPT連携 - KachiTalk分析結果の高度な洞察と改善提案生成

機能:
- 分析結果をChatGPTに送信
- AIによる営業改善提案の自動生成
- パターン認識と異常検知
- チームベストプラクティスの抽出
- 個人別の改善アクションプラン作成

Usage:
  python3 chatgpt_analysis_enhancement.py --analysis-json /tmp/analysis.json
"""

import json
import os
import sys
from typing import Dict, List, Optional
import requests

class ChatGPTAnalysisEnhancer:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('OPENAI_API_KEY')
        if not self.api_key:
            print("⚠️  警告: OPENAI_API_KEY が設定されていません")
            print("   ChatGPT連携をスキップします")
            self.enabled = False
            return

        self.enabled = True
        self.api_url = 'https://api.openai.com/v1/chat/completions'
        self.headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

    def analyze_team_patterns(self, analysis_data: dict) -> Dict:
        """チーム全体のパターン分析と改善提案を生成"""
        if not self.enabled:
            return {}

        # 分析データを整形
        staff_summary = {}
        for staff_name, metrics in analysis_data.get('staff_analysis', {}).items():
            staff_summary[staff_name] = {
                '成約率': f"{metrics.get('contract_rate', 0)*100:.1f}%",
                'プロセス完全性': f"{metrics.get('avg_completeness', 0):.1f}点",
                '通話件数': metrics.get('call_count', 0),
                '下地チェックスコア': f"{metrics.get('shimoji_checklist', {}).get('avg_score', 0):.1f}点"
            }

        prompt = f"""
営業チーム分析レポート（KachiTalk 411通話ログ）に基づいて、以下を分析してください：

【チーム成績データ】
{json.dumps(staff_summary, ensure_ascii=False, indent=2)}

【分析項目】
1. **成約率のばらつき分析**
   - なぜこの成績差が出ているのか
   - 高成約者の共通点は何か

2. **下地チェックリスト実施率の課題**
   - コンプライアンス項目で実施率が低い項目
   - その理由と改善方法

3. **営業スタイルの多様性**
   - 異なるアプローチで成功している事例
   - 個人別の強みを活かした戦略

4. **チーム全体の改善提案**
   - 実装可能な施策トップ3
   - 各施策の期待効果

【出力形式】
JSON形式で以下を含める：
{{
  "team_strengths": ["強み1", "強み2", ...],
  "improvement_areas": ["改善点1", "改善点2", ...],
  "best_practices": [
    {{"practice": "実践例1", "owner": "営業者名", "expected_impact": "期待効果"}},
    ...
  ],
  "action_items": [
    {{"action": "施策1", "priority": "高/中/低", "owner": "推奨担当", "timeline": "実施時期"}},
    ...
  ],
  "alerts": ["注意点1", "注意点2", ...],
  "summary": "総括"
}}
"""

        return self._call_chatgpt(prompt, "team_analysis")

    def generate_individual_improvement_plan(self, staff_name: str, metrics: dict) -> Dict:
        """個人別改善アクションプランを生成"""
        if not self.enabled:
            return {}

        prompt = f"""
営業パーソン「{staff_name}」の個別改善プランを作成してください。

【本人のデータ】
- 成約率: {metrics.get('contract_rate', 0)*100:.1f}%
- 平均通話時間: {metrics.get('avg_duration', 0):.1f}分
- プロセス完全性スコア: {metrics.get('avg_completeness', 0):.1f}点
- 通話件数: {metrics.get('call_count', 0)}件
- 成約件数: {metrics.get('contract_count', 0)}件

【下地チェックリスト実施率】
{json.dumps(metrics.get('shimoji_checklist', {}).get('item_execution_rates', {}), ensure_ascii=False, indent=2)}

【営業スタイル】
{', '.join(metrics.get('style_markers', []))}

【提案内容】
1. **本人の強み** - 活かすべき長所
2. **改善すべき点** - 具体的な課題
3. **実装可能な施策** - 今週から始められる行動
4. **期待される成果** - 3ヶ月後の目標値
5. **チェックポイント** - 進捗確認の指標

【出力形式】
{{
  "staff_name": "{staff_name}",
  "strengths": ["強み1", "強み2", ...],
  "challenges": ["課題1", "課題2", ...],
  "weekly_actions": [
    {{"day": "月", "action": "具体的な行動"}},
    ...
  ],
  "target_metrics": {{"成約率_3ヶ月後": "XX%", "チェックスコア_3ヶ月後": "XX点"}},
  "checkpoints": ["確認項目1", "確認項目2", ...],
  "coaching_points": "コーチング時の要点"
}}
"""

        return self._call_chatgpt(prompt, f"individual_plan_{staff_name}")

    def detect_anomalies(self, analysis_data: dict) -> List[Dict]:
        """異常パターンと改善の可能性を検出"""
        if not self.enabled:
            return []

        # 基本統計を計算
        contract_rates = [m.get('contract_rate', 0) for m in analysis_data.get('staff_analysis', {}).values()]
        avg_rate = sum(contract_rates) / len(contract_rates) if contract_rates else 0

        prompt = f"""
KachiTalk営業ログから異常パターンを検出してください。

【統計サマリー】
- チーム平均成約率: {avg_rate*100:.1f}%
- 成約率の範囲: {min(contract_rates)*100:.1f}% - {max(contract_rates)*100:.1f}%
- 全通話数: {analysis_data.get('log_count', 0)}件

【検出すべき異常パターン】
1. 成約率が著しく高い/低い営業者
2. プロセス完全性スコアと成約率の乖離
3. 通話時間と成約率の相関性外れ値
4. 下地チェックリスト実施率の大きなばらつき
5. 特定のプロセスステップが実施されていない傾向

【改善の可能性】
- 低成約者が高成約者から学べる点
- プロセス改善による見込み効果
- 研修・コーチング効果の予測

【出力形式】
{{
  "anomalies": [
    {{"type": "異常の種類", "details": "具体的な内容", "severity": "高/中/低", "potential_impact": "改善効果"}}
  ],
  "improvement_potential": {{"optimistic": "XX%向上の可能性", "realistic": "YY%が現実的"}},
  "urgent_actions": ["即実施すべき施策1", ...]
}}
"""

        result = self._call_chatgpt(prompt, "anomaly_detection")
        return result.get('anomalies', []) if result else []

    def _call_chatgpt(self, prompt: str, operation_type: str) -> Optional[Dict]:
        """ChatGPT APIを呼び出し"""
        try:
            payload = {
                'model': 'gpt-4o',
                'messages': [
                    {
                        'role': 'system',
                        'content': '営業分析のエキスパート。KachiTalk通話ログから実行可能な改善提案を生成します。JSON形式で応答してください。'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.7,
                'max_tokens': 2000
            }

            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']

                # JSON部分を抽出
                try:
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    if json_start >= 0 and json_end > json_start:
                        json_str = content[json_start:json_end]
                        return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

                print(f"⚠️  {operation_type}: JSON解析失敗")
                return None
            else:
                print(f"✗ ChatGPT API エラー: {response.status_code}")
                print(f"  {response.text}")
                return None

        except Exception as e:
            print(f"✗ ChatGPT連携エラー: {e}")
            return None

    def generate_comprehensive_report(self, analysis_data: dict) -> Dict:
        """総合レポートを生成"""
        if not self.enabled:
            return {}

        print("🤖 ChatGPTで総合分析中...")

        report = {
            'team_analysis': self.analyze_team_patterns(analysis_data),
            'individual_plans': {},
            'anomalies': self.detect_anomalies(analysis_data),
            'generated_at': __import__('datetime').datetime.now().isoformat()
        }

        # 個別改善プランを生成
        print("📋 個別改善プラン生成中...")
        for staff_name, metrics in analysis_data.get('staff_analysis', {}).items():
            plan = self.generate_individual_improvement_plan(staff_name, metrics)
            if plan:
                report['individual_plans'][staff_name] = plan

        return report


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='ChatGPT連携による営業分析の高度化'
    )
    parser.add_argument(
        '--analysis-json',
        required=True,
        help='KachiTalk分析結果JSONファイル'
    )
    parser.add_argument(
        '--output-json',
        default='/tmp/chatgpt_enhancement_report.json',
        help='改善レポート出力ファイル'
    )
    parser.add_argument(
        '--api-key',
        help='OpenAI API キー（環境変数 OPENAI_API_KEY も使用可）'
    )

    args = parser.parse_args()

    # 分析データを読み込む
    try:
        with open(args.analysis_json, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
    except Exception as e:
        print(f'✗ ファイル読込エラー: {e}')
        sys.exit(1)

    # ChatGPT分析を実行
    enhancer = ChatGPTAnalysisEnhancer(args.api_key)

    if not enhancer.enabled:
        print("ℹ️  ChatGPT連携が無効です")
        return

    print("✨ ChatGPT連携分析を開始...")
    report = enhancer.generate_comprehensive_report(analysis_data)

    # レポートを保存
    try:
        with open(args.output_json, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f'✓ レポート保存: {args.output_json}')
    except Exception as e:
        print(f'✗ 保存エラー: {e}')
        sys.exit(1)

    print("✅ ChatGPT連携分析完了")


if __name__ == '__main__':
    main()
