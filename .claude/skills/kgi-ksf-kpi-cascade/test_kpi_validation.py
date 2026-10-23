#!/usr/bin/env python3
"""
KGI-KSF-KPI-Cascade スキル の検証テスト

数式検算・マイルストーン検査・KSF妥当性診断を実装
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
import json


class KPIValidator:
    """KPI検証・検算クラス"""

    def __init__(self, project_name: str, kgi_target: int, kgi_period_months: int):
        """
        Args:
            project_name: プロジェクト名（例: "沖縄企業のミカタ"）
            kgi_target: KGI最終目標値（例: 1000）
            kgi_period_months: KGI達成期間（月）（例: 12）
        """
        self.project_name = project_name
        self.kgi_target = kgi_target
        self.kgi_period_months = kgi_period_months
        self.kgi_monthly = kgi_target / kgi_period_months
        self.errors = []
        self.warnings = []

    # ========== Test 1: 検算テスト ==========
    def test_channel_kpi_summation(self, channel_targets: Dict[str, int]) -> bool:
        """
        チャネル別KPI内訳がKGIと一致するか検査

        Args:
            channel_targets: チャネル別目標値（例: {"existing": 300, "sns": 300, ...}）

        Returns:
            合算が KGI と一致: True / 不一致: False
        """
        kpi_total = sum(channel_targets.values())

        if kpi_total != self.kgi_target:
            self.errors.append(
                f"❌ チャネル別KPI内訳の合算が KGI と不一致: "
                f"合算={kpi_total}, KGI={self.kgi_target}"
            )
            return False

        self.warnings.append(
            f"✓ チャネル別KPI検算: 合算={kpi_total} == KGI={self.kgi_target}"
        )
        return True

    def test_exit_conversion_kpi(self, exit_targets: Dict[str, int]) -> bool:
        """
        出口転換KPI（相談・面談件数）の内訳検査

        Args:
            exit_targets: 出口別目標値（例: {"line": 5, "partner": 5}）

        Returns:
            合算が妥当: True / 不妥当: False
        """
        exit_total = sum(exit_targets.values())

        # 相談・面談月10件が基準（CLAUDE.md による）
        expected_exit = 10

        if exit_total != expected_exit:
            self.errors.append(
                f"❌ 出口転換KPI内訳が不一致: "
                f"合算={exit_total}, 期待値={expected_exit}"
            )
            return False

        self.warnings.append(
            f"✓ 出口転換KPI検算: 合算={exit_total} (LINE={exit_targets.get('line', 0)}, "
            f"提携={exit_targets.get('partner', 0)})"
        )
        return True

    def test_kpi_formula_consistency(
        self,
        monthly_registrations: int,
        monthly_exit: int
    ) -> bool:
        """
        「月当たりKPI × 12ヶ月 = KGI」の数式一貫性検査

        Args:
            monthly_registrations: 月当たり登録数目標（例: 83）
            monthly_exit: 月当たり出口転換目標（例: 10）

        Returns:
            数式が成立: True / 不成立: False
        """
        calculated_annual_registrations = monthly_registrations * self.kgi_period_months
        calculated_annual_exit = monthly_exit * self.kgi_period_months

        reg_ok = abs(calculated_annual_registrations - self.kgi_target) < self.kgi_target * 0.05  # 5%許容

        if not reg_ok:
            self.errors.append(
                f"❌ KPI数式不一致（登録）: "
                f"月{monthly_registrations}社×12ヶ月={calculated_annual_registrations}, "
                f"KGI={self.kgi_target}"
            )
            return False

        self.warnings.append(
            f"✓ KPI数式一貫性: 月{monthly_registrations}社×12={calculated_annual_registrations} ≈ KGI{self.kgi_target}"
        )
        return True

    # ========== Test 2: マイルストーン検査 ==========
    def test_milestone_dates(
        self,
        milestones: Dict[int, Dict[str, Any]],  # month -> {"date": "YYYY-MM-DD", "target": N}
        reference_date: datetime = None
    ) -> bool:
        """
        マイルストーン日付が過去になっていないか、目標値が現実的か検査

        Args:
            milestones: マイルストーン定義（月数 -> {date, target}）
            reference_date: 参照日付（デフォルト: 本日）

        Returns:
            すべてのマイルストーン有効: True / 期限切れあり: False
        """
        if reference_date is None:
            reference_date = datetime.now()

        all_valid = True

        for month, data in sorted(milestones.items()):
            try:
                m_date = datetime.fromisoformat(data["date"])
            except (ValueError, KeyError):
                self.errors.append(f"❌ マイルストーン{month}ヶ月: 日付形式不正 ({data.get('date')})")
                all_valid = False
                continue

            is_past = m_date < reference_date
            target = data.get("target", 0)

            # 目標値が達成期限に対して現実的か（月当たり進捗で判定）
            expected_by_month = (self.kgi_target / self.kgi_period_months) * month
            is_realistic = target >= expected_by_month * 0.9  # 10%の改善余地

            if is_past:
                self.errors.append(
                    f"❌ マイルストーン{month}ヶ月 ({data['date']}) は本日より過去。再議論が必要"
                )
                all_valid = False
            elif not is_realistic:
                self.warnings.append(
                    f"⚠️  マイルストーン{month}ヶ月: 目標{target}は月当たり{expected_by_month:.0f}より現実的か確認"
                )
            else:
                days_remaining = (m_date - reference_date).days
                self.warnings.append(
                    f"✓ マイルストーン{month}ヶ月 ({data['date']}): 残り{days_remaining}日, 目標{target}"
                )

        return all_valid

    def test_review_period_expiry(
        self,
        review_deadline: str,  # "YYYY-MM-DD"
        reference_date: datetime = None
    ) -> bool:
        """
        KPI見直し期限（最長6ヶ月）が切れていないか検査

        Args:
            review_deadline: 見直し期限日付
            reference_date: 参照日付

        Returns:
            期限内: True / 期限切れ: False
        """
        if reference_date is None:
            reference_date = datetime.now()

        try:
            deadline = datetime.fromisoformat(review_deadline)
        except ValueError:
            self.errors.append(f"❌ 見直し期限: 日付形式不正 ({review_deadline})")
            return False

        is_expired = deadline < reference_date
        days_remaining = (deadline - reference_date).days

        if is_expired:
            self.errors.append(
                f"❌ 見直し期限切れ: {review_deadline} (経過{abs(days_remaining)}日)"
            )
            return False
        else:
            self.warnings.append(
                f"✓ 見直し期限: 残り{days_remaining}日 ({review_deadline})"
            )
            return True

    # ========== Test 3: KSF妥当性診断 ==========
    def test_ksf_validity(
        self,
        actual_monthly_registrations: int,
        actual_monthly_exit: int,
        monthly_target_registrations: int = None,
        monthly_target_exit: int = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        「KPI達成してもKGIに近づかない」パターンを検出
        → KSF見誤りを指摘

        Args:
            actual_monthly_registrations: 当月LINE登録実績
            actual_monthly_exit: 当月出口転換実績
            monthly_target_registrations: 月当たり登録目標（デフォルト: KGI/12）
            monthly_target_exit: 月当たり出口目標（デフォルト: 10）

        Returns:
            (妥当性判定, 詳細情報)
        """
        if monthly_target_registrations is None:
            monthly_target_registrations = self.kgi_monthly
        if monthly_target_exit is None:
            monthly_target_exit = 10

        # KPI達成判定
        kpi_reg_ok = actual_monthly_registrations >= monthly_target_registrations
        kpi_exit_ok = actual_monthly_exit >= monthly_target_exit

        # KGI進捗への寄与（12ヶ月累積予測）
        projected_annual_registrations = actual_monthly_registrations * self.kgi_period_months
        kgi_registrations_on_track = projected_annual_registrations >= self.kgi_target * 0.9

        # 診断結果
        details = {
            "kpi_registrations_ok": kpi_reg_ok,
            "kpi_exit_ok": kpi_exit_ok,
            "kgi_on_track": kgi_registrations_on_track,
            "projected_annual": projected_annual_registrations,
            "issues": []
        }

        is_valid = True

        # 失敗パターン①: KPI達成しているのにKGIに進まない
        if kpi_reg_ok and not kgi_registrations_on_track:
            details["issues"].append({
                "pattern": "KSF見誤り（チャネル多様性）",
                "symptom": f"LINE登録は月{actual_monthly_registrations}件達成 → 年{projected_annual_registrations}社（KGI{self.kgi_target}に届かない）",
                "root_cause": "KSF①「チャネル確保」の前提が不足。既存顧客・SNS・紹介の内訳が不明確",
                "improvement": "チャネル別内訳を CLAUDE.md に明記。各チャネル責任部門を設定"
            })
            is_valid = False

        # 失敗パターン②: 出口転換が進まない
        if not kpi_exit_ok:
            details["issues"].append({
                "pattern": "KSF見誤り（出口転換率）",
                "symptom": f"出口転換は月{actual_monthly_exit}件（目標{monthly_target_exit}）",
                "root_cause": "KSF②「出口転換」の要因が「登録数」だけでなく「登録者の質」に依存。スクリーニング・配信の精度不足",
                "improvement": "診断ツール・AI スクリーニング・リード配信優先度付けを強化"
            })
            is_valid = False

        if is_valid:
            self.warnings.append(
                f"✓ KSF妥当性: KPI達成(登録{actual_monthly_registrations}件, 出口{actual_monthly_exit}件)が KGI進捗に反映"
            )

        return is_valid, details

    # ========== 結果出力 ==========
    def report(self) -> Dict[str, Any]:
        """検証結果をJSON形式で返却"""
        return {
            "project": self.project_name,
            "kgi": self.kgi_target,
            "kgi_period_months": self.kgi_period_months,
            "kgi_monthly": round(self.kgi_monthly, 2),
            "errors": self.errors,
            "warnings": self.warnings,
            "has_errors": len(self.errors) > 0
        }

    def print_report(self):
        """検証結果を標準出力に表示"""
        report = self.report()

        print(f"\n{'='*70}")
        print(f"KPI検証レポート: {report['project']}")
        print(f"KGI={report['kgi']}, 期間={report['kgi_period_months']}ヶ月, 月当たり={report['kgi_monthly']}")
        print(f"{'='*70}\n")

        if report["errors"]:
            print("[エラー] 改善が必須:")
            for err in report["errors"]:
                print(f"  {err}\n")

        if report["warnings"]:
            print("[情報・警告]:")
            for warn in report["warnings"]:
                print(f"  {warn}\n")

        if not report["has_errors"]:
            print("✅ すべての検証に合格しました")

        print(f"{'='*70}\n")


# ========== テストケース ==========

def test_case_okinawa_kikai():
    """沖縄企業のミカタ の検証テストケース"""

    print("\n\n" + "="*70)
    print("TEST CASE: 沖縄企業のミカタ")
    print("="*70)

    validator = KPIValidator(
        project_name="沖縄企業のミカタ",
        kgi_target=1000,
        kgi_period_months=12
    )

    # Test 1: チャネル別KPI検算
    print("\n[Test 1] チャネル別KPI内訳検算")
    channel_targets = {
        "existing_customer": 300,
        "instagram_sns": 300,
        "referral": 200,
        "organic_other": 200
    }
    validator.test_channel_kpi_summation(channel_targets)

    # Test 1-2: 出口転換KPI検算
    print("\n[Test 1-2] 出口転換KPI検算")
    exit_targets = {
        "line": 5,
        "partner": 5
    }
    validator.test_exit_conversion_kpi(exit_targets)

    # Test 1-3: KPI数式一貫性
    print("\n[Test 1-3] KPI数式一貫性検査")
    validator.test_kpi_formula_consistency(
        monthly_registrations=83,  # 1000 / 12
        monthly_exit=10  # LINE5 + 提携5
    )

    # Test 2: マイルストーン検査
    print("\n[Test 2] マイルストーン日付・目標値検査")
    milestones = {
        3: {"date": "2026-12-31", "target": 100},   # 例: 開始が2026-10-05なら約3ヶ月後
        6: {"date": "2027-03-31", "target": 300},
        9: {"date": "2027-06-30", "target": 600},
        12: {"date": "2027-09-30", "target": 1000}
    }
    reference_date = datetime(2026, 10, 5)  # 本日相当
    validator.test_milestone_dates(milestones, reference_date)

    # Test 2-2: 見直し期限検査
    print("\n[Test 2-2] KPI見直し期限検査")
    validator.test_review_period_expiry(
        review_deadline="2026-11-06",  # 最長6ヶ月ルール
        reference_date=reference_date
    )

    # Test 3: KSF妥当性診断（正常ケース）
    print("\n[Test 3] KSF妥当性診断（正常ケース）")
    is_valid, details = validator.test_ksf_validity(
        actual_monthly_registrations=85,  # 目標83達成
        actual_monthly_exit=10  # 目標10達成
    )
    if details["issues"]:
        for issue in details["issues"]:
            print(f"  パターン: {issue['pattern']}")
            print(f"  症状: {issue['symptom']}")
            print(f"  根本原因: {issue['root_cause']}")
            print(f"  改善: {issue['improvement']}\n")

    # Test 3-2: KSF妥当性診断（失敗ケース①）
    print("\n[Test 3-2] KSF妥当性診断（失敗パターン①: 登録は達成しているが KGI に進まない）")
    validator2 = KPIValidator("沖縄企業のミカタ", 1000, 12)
    is_valid2, details2 = validator2.test_ksf_validity(
        actual_monthly_registrations=40,  # 目標83の半分のみ
        actual_monthly_exit=10
    )
    if details2["issues"]:
        for issue in details2["issues"]:
            print(f"  パターン: {issue['pattern']}")
            print(f"  症状: {issue['symptom']}")
            print(f"  根本原因: {issue['root_cause']}")
            print(f"  改善: {issue['improvement']}\n")

    # Test 3-3: KSF妥当性診断（失敗ケース②）
    print("\n[Test 3-3] KSF妥当性診断（失敗パターン②: 出口転換が進まない）")
    validator3 = KPIValidator("沖縄企業のミカタ", 1000, 12)
    is_valid3, details3 = validator3.test_ksf_validity(
        actual_monthly_registrations=85,
        actual_monthly_exit=4  # 目標10に対し未達
    )
    if details3["issues"]:
        for issue in details3["issues"]:
            print(f"  パターン: {issue['pattern']}")
            print(f"  症状: {issue['symptom']}")
            print(f"  根本原因: {issue['root_cause']}")
            print(f"  改善: {issue['improvement']}\n")

    # 最終レポート
    print("\n[最終結果]")
    validator.print_report()


def test_case_milestone_expiry():
    """マイルストーン期限切れケース"""

    print("\n\n" + "="*70)
    print("TEST CASE: マイルストーン期限切れ検出")
    print("="*70)

    validator = KPIValidator("test_project", 1000, 12)

    # 期限切れマイルストーン
    milestones = {
        3: {"date": "2026-07-01", "target": 100},   # 過去
        6: {"date": "2026-10-05", "target": 300},   # 本日
        9: {"date": "2027-01-05", "target": 600},   # 未来
    }
    reference_date = datetime(2026, 10, 5)

    validator.test_milestone_dates(milestones, reference_date)
    validator.print_report()


def test_case_formula_mismatch():
    """数式不一致ケース"""

    print("\n\n" + "="*70)
    print("TEST CASE: KPI数式不一致の検出")
    print("="*70)

    validator = KPIValidator("test_project", 1000, 12)

    # 数式が合わないケース: 月60社 × 12 = 720社 ≠ 1000社
    validator.test_kpi_formula_consistency(
        monthly_registrations=60,
        monthly_exit=10
    )

    validator.print_report()


def test_case_channel_mismatch():
    """チャネル別内訳が KGI と合わないケース"""

    print("\n\n" + "="*70)
    print("TEST CASE: チャネル別KPI内訳が KGI と不一致")
    print("="*70)

    validator = KPIValidator("test_project", 1000, 12)

    # 内訳の合算が 900 → KGI 1000 と不一致
    channel_targets = {
        "existing": 300,
        "sns": 300,
        "referral": 200,
        "organic": 100  # 本来200のはずが100に
    }
    validator.test_channel_kpi_summation(channel_targets)

    validator.print_report()


if __name__ == "__main__":
    # すべてのテストケースを実行
    test_case_okinawa_kikai()
    test_case_milestone_expiry()
    test_case_formula_mismatch()
    test_case_channel_mismatch()

    print("\n" + "="*70)
    print("全テストケース実行完了")
    print("="*70)
