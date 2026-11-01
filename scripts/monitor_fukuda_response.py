#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
福田さんからの返信メール監視・自動対応スクリプト

機能:
1. 福田さんからのメール返信を検出
2. セットアップ完了状況を確認
3. 必要に応じて自動返信を送信
4. 進捗状況をログに記録

実行: python3 scripts/monitor_fukuda_response.py
"""

import os
import sys
import json
import re
from datetime import datetime

# Gmail APIを使用するための準備
# 実際の運用ではGmail MCP serverを経由して実行

FUKUDA_EMAILS = [
    'takashi_fukuda@en-life.co.jp',
    'glowfukuda@gmail.com'
]

class FukudaResponseMonitor:
    """福田さんからの返信を監視・処理するクラス"""

    def __init__(self):
        self.log_file = 'docs/fukuda_response_log.md'
        self.status_file = 'docs/fukuda_integration_status.md'

    def log_entry(self, status, message):
        """ログに記録"""
        timestamp = datetime.now().isoformat()
        entry = f"\n### {timestamp}\n**Status**: {status}\n**Message**: {message}\n"

        if os.path.exists(self.log_file):
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(entry)
        else:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write("# 福田さん返信監視ログ\n")
                f.write(entry)

    def check_for_response(self):
        """
        福田さんからの返信をチェック

        注: 実際の運用では Gmail MCP server を経由して実行
        ここはスケルトン実装
        """
        print("🔍 福田さんからの返信をチェック中...")
        self.log_entry("CHECK", "返信メール監視開始")

        # 実際の実装では Gmail API で検索
        # query: from:takashi_fukuda@en-life.co.jp OR from:glowfukuda@gmail.com
        #        subject:GLOW企業リレーション管理システム
        #        after:2026-10-03

        return None  # 返信が見つかった場合はメール内容を返す

    def parse_response_content(self, email_body):
        """
        メール本文から情報を抽出

        確認項目:
        - Web画面アクセス成功の報告
        - データ形式の確定
        - ファイル提供方法の指定
        """
        result = {
            'web_access_ok': False,
            'data_format_confirmed': False,
            'data_format': None,
            'file_ready': False,
            'additional_notes': ''
        }

        # Web画面アクセス確認
        if re.search(r'(企業一覧|管理画面.*表示|アクセス.*成功|OK)', email_body):
            result['web_access_ok'] = True

        # データ形式の確定
        if re.search(r'(Excel|エクセル)', email_body):
            result['data_format'] = 'Excel'
            result['data_format_confirmed'] = True
        elif re.search(r'(スプレッドシート|Google Sheets|Sheets)', email_body):
            result['data_format'] = 'Google Sheets'
            result['data_format_confirmed'] = True
        elif re.search(r'(BlueBean|ブルービーン)', email_body):
            result['data_format'] = 'BlueBean'
            result['data_format_confirmed'] = True
        elif re.search(r'(手書き|ノート)', email_body):
            result['data_format'] = '手書き'
            result['data_format_confirmed'] = True

        return result

    def generate_auto_response(self, response_data):
        """
        福田さんの返信内容に応じた自動レスポンスを生成
        """
        if response_data['web_access_ok'] and response_data['data_format_confirmed']:
            return {
                'status': 'SETUP_COMPLETE',
                'next_step': '10月6日のデータ受領待機',
                'message': f"""福田さんへの返信:

セットアップ完了のご報告ありがとうございます！

✅ Web管理画面アクセス: 成功
✅ データ形式: {response_data['data_format']}

システム側の準備も完了しております。
以下のスケジュールで進めさせていただきます:

【次のステップ】
1. 2026-10-06: 100件ファイルのご提供をお待ちしております
   - 形式: {response_data['data_format']}
   - ファイル名: 福田_過去100件_YYYYMMDD.{get_extension(response_data['data_format'])}

2. 2026-10-06～10-07: データ品質チェック実施
   - 企業名・電話番号の必須項目確認
   - 日付形式の統一確認
   - 既存企業との重複検出

3. 2026-10-08: チェック結果をご報告します

ご質問やご不明な点がございましたら、いつでもお気軽にお声がけください。

よろしくお願いいたします。"""
            }
        elif response_data['web_access_ok']:
            return {
                'status': 'WEB_OK_WAITING_DATA_FORMAT',
                'next_step': 'データ形式確定待機',
                'message': """福田さんへの確認:

Web管理画面へのアクセス成功をご報告いただき、ありがとうございます！

次に、100件の過去データの形式についてご確認させていただきたいのですが、
以下のどちらの形式で準備していただけますでしょうか？

【データ形式の確認】
□ Excel ファイル（ファイル名: ______）
□ Google スプレッドシート（シート名: ______）
□ BlueBean のログ出力
□ その他（: ______）

ご返信をお待ちしております。"""
            }
        else:
            return {
                'status': 'AWAITING_RESPONSE',
                'next_step': '完全なセットアップ完了待機',
                'message': None
            }

    def process_response(self, email_content):
        """
        受け取った返信を処理・進捗を更新
        """
        print("📧 返信内容を解析中...")

        parsed = self.parse_response_content(email_content)
        auto_response = self.generate_auto_response(parsed)

        self.log_entry(
            auto_response['status'],
            f"Web画面: {'✅' if parsed['web_access_ok'] else '⏳'}, "
            f"データ形式: {parsed['data_format'] or '未確定'}"
        )

        return auto_response

    def run(self):
        """メイン実行ロジック"""
        print("\n" + "="*60)
        print("🔔 福田さん返信監視システム")
        print("="*60)

        response = self.check_for_response()

        if response:
            print(f"\n✉️ 福田さんからの返信を検出しました\n")
            result = self.process_response(response)

            print(f"📊 ステータス: {result['status']}")
            print(f"📋 次のステップ: {result['next_step']}")

            if result['message']:
                print(f"\n📝 自動レスポンス案:\n{result['message']}")
                return result
            else:
                print("\n⏳ セットアップ完了待機中")
                return None
        else:
            print("\n⏳ 福田さんからの返信はまだ届いていません")
            print("   定期的にチェック継続中...\n")
            return None


def get_extension(data_format):
    """ファイル形式に応じた拡張子を返す"""
    extensions = {
        'Excel': 'xlsx',
        'Google Sheets': 'csv',
        'BlueBean': 'csv',
        '手書き': 'xlsx'
    }
    return extensions.get(data_format, 'xlsx')


if __name__ == '__main__':
    monitor = FukudaResponseMonitor()
    monitor.run()
