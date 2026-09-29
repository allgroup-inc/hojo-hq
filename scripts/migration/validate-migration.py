#!/usr/bin/env python3
"""
マイグレーションデータ検証スクリプト
GAS → PostgreSQL RDS へのマイグレーション後、データ品質を検証

使用法: python3 scripts/migration/validate-migration.py --check-count --check-schema
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import argparse

class MigrationValidator:
    def __init__(self, data_dir="./docs/kakehashi-poc/data"):
        self.data_dir = Path(data_dir)
        self.issues = []
        self.warnings = []
        self.successes = []

    def load_json_file(self, filename):
        """JSON ファイルを読み込む"""
        filepath = self.data_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"{filepath} が見つかりません")
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def check_users_count(self):
        """ユーザー数チェック (12人が必須)"""
        print("🔍 ユーザー数チェック...", end=" ")
        try:
            users = self.load_json_file('users.json')
            count = len(users)

            if count == 12:
                self.successes.append(f"ユーザー数: {count} ✓")
                print("✓")
            else:
                self.issues.append(f"ユーザー数が不正: {count} (期待値: 12)")
                print(f"✗ ({count})")
        except Exception as e:
            self.issues.append(f"ユーザーファイルエラー: {e}")
            print("✗")

    def check_appointments_count(self):
        """アポイントメント数チェック (1,847 ± 5%)"""
        print("🔍 アポイントメント数チェック...", end=" ")
        try:
            appointments = self.load_json_file('appointments.json')
            count = len(appointments)
            expected = 1847
            margin = int(expected * 0.05)  # ±5%

            if expected - margin <= count <= expected + margin:
                self.successes.append(f"アポイントメント数: {count} (期待値: {expected} ± {margin}) ✓")
                print(f"✓ ({count})")
            else:
                self.issues.append(f"アポイントメント数が範囲外: {count} (期待値: {expected} ± {margin})")
                print(f"✗ ({count})")
        except Exception as e:
            self.issues.append(f"アポイントメントファイルエラー: {e}")
            print("✗")

    def check_schema_users(self):
        """ユーザースキーマ検証"""
        print("🔍 ユーザースキーマ検証...", end=" ")
        try:
            users = self.load_json_file('users.json')
            required_fields = {'id', 'name', 'email', 'status'}

            all_valid = True
            for user in users:
                if not required_fields.issubset(user.keys()):
                    missing = required_fields - set(user.keys())
                    self.issues.append(f"ユーザー {user.get('id')} にフィールド欠落: {missing}")
                    all_valid = False

                # Email 形式チェック
                if '@' not in user.get('email', ''):
                    self.warnings.append(f"ユーザー {user['id']} のメール形式が不正")

            if all_valid:
                self.successes.append("ユーザースキーマ: すべてのレコードが有効 ✓")
                print("✓")
            else:
                print("✗")
        except Exception as e:
            self.issues.append(f"スキーマ検証エラー: {e}")
            print("✗")

    def check_schema_appointments(self):
        """アポイントメントスキーマ検証"""
        print("🔍 アポイントメントスキーマ検証...", end=" ")
        try:
            appointments = self.load_json_file('appointments.json')
            required_fields = {'id', 'customerId', 'customerName', 'scheduledDateTime', 'status'}

            all_valid = True
            for appt in appointments:
                if not required_fields.issubset(appt.keys()):
                    missing = required_fields - set(appt.keys())
                    self.issues.append(f"アポ {appt.get('id')} にフィールド欠落: {missing}")
                    all_valid = False

                # ステータス値チェック
                valid_statuses = {'SCHEDULED', 'COMPLETED', 'CANCELLED'}
                if appt.get('status') not in valid_statuses:
                    self.warnings.append(f"アポ {appt['id']} のステータスが不正: {appt['status']}")

            if all_valid:
                self.successes.append("アポイントメントスキーマ: すべてのレコードが有効 ✓")
                print("✓")
            else:
                print("✗")
        except Exception as e:
            self.issues.append(f"スキーマ検証エラー: {e}")
            print("✗")

    def check_status_distribution(self):
        """ステータス分布チェック"""
        print("🔍 ステータス分布チェック...", end=" ")
        try:
            appointments = self.load_json_file('appointments.json')

            distribution = {}
            for appt in appointments:
                status = appt.get('status', 'UNKNOWN')
                distribution[status] = distribution.get(status, 0) + 1

            total = sum(distribution.values())
            report = ", ".join([f"{s}: {c} ({100*c/total:.1f}%)"
                              for s, c in sorted(distribution.items())])
            self.successes.append(f"ステータス分布: {report} ✓")
            print("✓")
        except Exception as e:
            self.issues.append(f"ステータス分布エラー: {e}")
            print("✗")

    def check_date_range(self):
        """日付範囲チェック"""
        print("🔍 日付範囲チェック...", end=" ")
        try:
            appointments = self.load_json_file('appointments.json')

            dates = []
            for appt in appointments:
                dt_str = appt.get('scheduledDateTime', '')
                try:
                    dt = datetime.fromisoformat(dt_str.replace('+09:00', ''))
                    dates.append(dt)
                except:
                    pass

            if dates:
                min_date = min(dates)
                max_date = max(dates)
                days_span = (max_date - min_date).days

                self.successes.append(f"日付範囲: {min_date.date()} ～ {max_date.date()} ({days_span}日間) ✓")
                print(f"✓ ({days_span}日間)")
            else:
                print("✗ (日付をパースできず)")
        except Exception as e:
            self.issues.append(f"日付範囲エラー: {e}")
            print("✗")

    def check_uniqueness(self):
        """ユニーク性チェック"""
        print("🔍 ユニーク性チェック...", end=" ")
        try:
            users = self.load_json_file('users.json')
            appointments = self.load_json_file('appointments.json')

            user_ids = [u['id'] for u in users]
            user_emails = [u['email'] for u in users]
            appt_ids = [a['id'] for a in appointments]

            issues_found = False

            if len(user_ids) != len(set(user_ids)):
                self.issues.append("ユーザーID が重複")
                issues_found = True

            if len(user_emails) != len(set(user_emails)):
                self.issues.append("ユーザーメール が重複")
                issues_found = True

            if len(appt_ids) != len(set(appt_ids)):
                self.issues.append("アポイントメントID が重複")
                issues_found = True

            if not issues_found:
                self.successes.append("ユニーク性: すべてのID/メール が一意 ✓")
                print("✓")
            else:
                print("✗")
        except Exception as e:
            self.issues.append(f"ユニーク性チェックエラー: {e}")
            print("✗")

    def run_all_checks(self):
        """すべてのチェックを実行"""
        print("=" * 60)
        print("📋 データマイグレーション検証 (GAS → PostgreSQL RDS)")
        print("=" * 60)
        print("")

        self.check_users_count()
        self.check_appointments_count()
        self.check_schema_users()
        self.check_schema_appointments()
        self.check_status_distribution()
        self.check_date_range()
        self.check_uniqueness()

        print("")
        print("=" * 60)
        print("📊 検証結果")
        print("=" * 60)

        if self.successes:
            print("\n✅ 成功:")
            for msg in self.successes:
                print(f"   {msg}")

        if self.warnings:
            print("\n⚠️  警告:")
            for msg in self.warnings:
                print(f"   {msg}")

        if self.issues:
            print("\n❌ エラー:")
            for msg in self.issues:
                print(f"   {msg}")
            return False

        print("\n🎉 すべてのチェックに合格!")
        return True

def main():
    parser = argparse.ArgumentParser(description="マイグレーション検証")
    parser.add_argument('--data-dir', default='./docs/kakehashi-poc/data',
                       help="データディレクトリ")

    args = parser.parse_args()

    validator = MigrationValidator(args.data_dir)
    success = validator.run_all_checks()

    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
