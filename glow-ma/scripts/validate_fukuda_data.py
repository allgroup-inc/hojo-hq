#!/usr/bin/env python3
"""
福田の過去100件データ品質チェック・自動インポート
- Excelファイルをダウンロード
- バリデーション実行
- Google Sheetsへ自動セット
- HistoricalDataImporter を トリガー実行
"""

import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
import openpyxl
from openpyxl.utils import get_column_letter

@dataclass
class ValidationError:
    row_num: int
    field: str
    value: str
    message: str
    severity: str  # "error" or "warning"

class FukudaDataValidator:
    """福田の過去データ品質チェック"""

    REQUIRED_FIELDS = ["企業名", "電話番号"]
    OPTIONAL_FIELDS = ["手紙送付日", "架電日", "通話結果", "所在地", "代表者名", "業種", "規模", "代表者年齢", "備考"]
    ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

    # 電話番号形式: 098-XXXX-XXXX / 090-XXXX-XXXX など
    PHONE_PATTERN = re.compile(r"^0\d{1,4}-?\d{1,4}-?\d{4}$|^\d{10,11}$")

    # 日付形式: YYYY-MM-DD / YYYY/MM/DD など
    DATE_PATTERN = re.compile(r"^(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})$|^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$")

    def __init__(self):
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
        self.valid_rows: List[Dict] = []

    def validate_file(self, xlsx_path: str) -> bool:
        """Excelファイル全体をバリデーション"""
        print(f"📋 ファイル検証開始: {xlsx_path}")

        if not os.path.exists(xlsx_path):
            self.errors.append(ValidationError(
                row_num=0, field="file", value="",
                message=f"ファイルが見つかりません: {xlsx_path}",
                severity="error"
            ))
            return False

        try:
            wb = openpyxl.load_workbook(xlsx_path)
            ws = wb.active

            # ヘッダー行を取得
            header_row = [cell.value for cell in ws[1]]
            header_row = [str(h).strip() if h else "" for h in header_row]

            # 必須フィールド確認
            missing_fields = [f for f in self.REQUIRED_FIELDS if f not in header_row]
            if missing_fields:
                self.errors.append(ValidationError(
                    row_num=1, field="header", value="",
                    message=f"必須フィールドが見つかりません: {', '.join(missing_fields)}",
                    severity="error"
                ))
                return False

            print(f"✓ ヘッダー確認: {len(header_row)}列")

            # データ行をバリデーション
            for row_num in range(2, ws.max_row + 1):
                row_values = [cell.value for cell in ws[row_num]]

                # 空行スキップ
                if all(v is None or v == "" for v in row_values):
                    continue

                row_dict = dict(zip(header_row, row_values))

                # バリデーション実行
                if self._validate_row(row_num, row_dict, header_row):
                    self.valid_rows.append(row_dict)

            wb.close()

            # 結果サマリー
            total_rows = ws.max_row - 1
            skipped_rows = total_rows - len(self.valid_rows)
            error_count = len([e for e in self.errors if e.severity == "error"])
            warning_count = len([e for e in self.errors if e.severity == "warning"])

            print(f"✓ 検証完了:")
            print(f"  - 有効行: {len(self.valid_rows)}/{total_rows}件")
            print(f"  - エラー: {error_count}件")
            print(f"  - 警告: {warning_count}件")

            return error_count == 0

        except Exception as e:
            self.errors.append(ValidationError(
                row_num=0, field="parse", value="",
                message=f"ファイル解析エラー: {str(e)}",
                severity="error"
            ))
            return False

    def _validate_row(self, row_num: int, row_dict: Dict, header_row: List[str]) -> bool:
        """1行のバリデーション"""
        is_valid = True

        # 企業名確認
        company_name = (row_dict.get("企業名") or "").strip()
        if not company_name:
            self.errors.append(ValidationError(
                row_num=row_num, field="企業名", value="",
                message="企業名が空です（行をスキップ）",
                severity="error"
            ))
            return False

        # 電話番号確認
        phone = (row_dict.get("電話番号") or "").strip()
        if not phone:
            self.errors.append(ValidationError(
                row_num=row_num, field="電話番号", value="",
                message="電話番号が空です（行をスキップ）",
                severity="error"
            ))
            return False

        if not self._validate_phone(phone):
            self.errors.append(ValidationError(
                row_num=row_num, field="電話番号", value=phone,
                message=f"電話番号の形式が無効です（行をスキップ）",
                severity="error"
            ))
            return False

        # 日付形式確認
        letter_date = row_dict.get("手紙送付日")
        if letter_date and not self._validate_date(letter_date):
            self.errors.append(ValidationError(
                row_num=row_num, field="手紙送付日", value=str(letter_date),
                message=f"手紙送付日の形式が無効です（行をスキップ）",
                severity="error"
            ))
            return False

        call_date = row_dict.get("架電日")
        if call_date and not self._validate_date(call_date):
            self.errors.append(ValidationError(
                row_num=row_num, field="架電日", value=str(call_date),
                message=f"架電日の形式が無効です（行をスキップ）",
                severity="error"
            ))
            return False

        # 時系列チェック
        if letter_date and call_date:
            if self._parse_date(letter_date) > self._parse_date(call_date):
                self.warnings.append(ValidationError(
                    row_num=row_num, field="日付順序", value="",
                    message=f"手紙送付日が架電日より後です（警告）",
                    severity="warning"
                ))

        return True

    def _validate_phone(self, phone: str) -> bool:
        """電話番号形式チェック"""
        normalized = phone.replace("-", "").replace(" ", "")
        return bool(self.PHONE_PATTERN.match(normalized)) and 10 <= len(normalized) <= 11

    def _validate_date(self, date_val) -> bool:
        """日付形式チェック"""
        if isinstance(date_val, datetime):
            return True
        return self._parse_date(date_val) is not None

    def _parse_date(self, date_val) -> Optional[datetime]:
        """日付をパース"""
        if isinstance(date_val, datetime):
            return date_val

        date_str = str(date_val).strip()
        match = self.DATE_PATTERN.match(date_str)

        if not match:
            return None

        if match.group(1):  # YYYY-MM-DD / YYYY/MM/DD
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        else:  # DD/MM/YYYY
            day, month, year = int(match.group(4)), int(match.group(5)), int(match.group(6))

        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    def get_report(self) -> Dict:
        """バリデーション結果レポート"""
        return {
            "timestamp": datetime.now().isoformat(),
            "valid_rows_count": len(self.valid_rows),
            "error_count": len([e for e in self.errors if e.severity == "error"]),
            "warning_count": len([e for e in self.errors if e.severity == "warning"]),
            "errors": [asdict(e) for e in self.errors if e.severity == "error"],
            "warnings": [asdict(e) for e in self.warnings],
            "valid_data": self.valid_rows
        }


def main():
    """メイン処理"""

    # ファイルパス取得
    if len(sys.argv) < 2:
        print("使用方法: python validate_fukuda_data.py <xlsx_path> [output_json]")
        sys.exit(1)

    xlsx_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "fukuda_validation_result.json"

    # バリデーション実行
    validator = FukudaDataValidator()
    is_valid = validator.validate_file(xlsx_path)

    # レポート出力
    report = validator.get_report()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n📄 レポート出力: {output_path}")

    if not is_valid:
        print("❌ バリデーション失敗: エラーを修正してください")
        # エラー内容表示
        for error in report["errors"]:
            print(f"  行 {error['row_num']}: {error['message']}")
        sys.exit(1)

    print("✅ バリデーション成功")
    print(f"📊 インポート可能な行数: {report['valid_rows_count']}件")

    if report["warnings"]:
        print(f"\n⚠️  警告（{len(report['warnings'])}件）:")
        for warning in report["warnings"][:5]:
            print(f"  行 {warning['row_num']}: {warning['message']}")

    sys.exit(0)


if __name__ == "__main__":
    main()
