#!/usr/bin/env python3
"""
営業成績データ抽出スクリプト
Excelファイルから5月〜9月の営業成績データを抽出し、Google Sheets用の形式に整形
"""

import openpyxl
import csv
import sys
from pathlib import Path

# 営業マン名一覧（2つのファイルで取得）
STAFF_NAMES = [
    '前原　芳乃',
    '奈須　章',
    '下地　健太',
    '幸良　妃奈代',
    '徳元　孝樹',
    '喜納　礼奈',
    '名嘉山　望',
    '狩俣　亜希乃',
]

KPI_HEADERS = [
    'ANP実績',
    '契約件数',
    '契約世帯',
    '世帯取り',
    '世帯単価',
    '世帯率',
    '落ち率',
    '新規訪問',
    '再アポ訪問',
    'その他訪問',
    '合計訪問',
    '自己アポ作成',
    '自己アポ訪問実績',
    '供給アポ実績'
]

MONTHS = ['5月', '6月', '7月', '8月', '9月']

def extract_monthly_data(file_path, sheet_name, month):
    """
    月別シートからデータを抽出
    戻り値: {営業マン: {KPI: 値}}
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb[sheet_name]

    data = {}

    # 営業マンデータ行を探す（行11から開始、最初の営業マンを見つけるまでループ）
    for row in range(11, 25):
        staff_name_cell = ws.cell(row, 5).value
        if not staff_name_cell:
            continue

        # 営業マン名の候補を確認
        found_staff = None
        for staff in STAFF_NAMES:
            if staff in str(staff_name_cell):
                found_staff = staff.strip()
                break

        if not found_staff:
            continue

        data[found_staff] = {}

        # KPI値を抽出（列6以降）
        for col, header in enumerate(KPI_HEADERS, start=6):
            value = ws.cell(row, col).value
            if value is not None:
                try:
                    data[found_staff][header] = float(value)
                except (ValueError, TypeError):
                    data[found_staff][header] = value

    wb.close()
    return data

def extract_cumulative_average_data(file_path):
    """
    3ヶ月累計平均データを抽出（File2から）
    戻り値: {営業マン: {KPI: 値}}
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb['Sheet1']

    data = {}

    # 3ヶ月累計平均（行4〜12）
    for row, staff_name in enumerate(STAFF_NAMES, start=4):
        data[staff_name] = {}

        for col, header in enumerate(KPI_HEADERS, start=3):
            value = ws.cell(row, col).value
            if value is not None:
                try:
                    data[staff_name][header] = float(value)
                except (ValueError, TypeError):
                    data[staff_name][header] = value

    wb.close()
    return data

def extract_monthly_data_from_file2(file_path):
    """
    File2から月別データを抽出（8月・9月）
    戻り値: {月: {営業マン: {KPI: 値}}}
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb['Sheet1']

    data = {}

    # 各月のセクション（例：9月は行16〜25、8月は行29〜38、7月は行41〜50）
    sections = {
        '9月': range(16, 26),
        '8月': range(29, 39),
        '7月': range(41, 51),
    }

    for month, row_range in sections.items():
        data[month] = {}

        for row in row_range:
            staff_name_cell = ws.cell(row, 5).value
            if not staff_name_cell:
                continue

            found_staff = None
            for staff in STAFF_NAMES:
                if staff in str(staff_name_cell):
                    found_staff = staff.strip()
                    break

            if not found_staff:
                continue

            data[month][found_staff] = {}

            for col, header in enumerate(KPI_HEADERS, start=6):
                value = ws.cell(row, col).value
                if value is not None:
                    try:
                        data[month][found_staff][header] = float(value)
                    except (ValueError, TypeError):
                        data[month][found_staff][header] = value

    wb.close()
    return data

def export_google_sheets_format(all_data, output_file):
    """
    Google Sheets用形式（営業マン × 月 × KPI）で CSV出力
    """
    rows = []

    # ヘッダー行
    header = ['営業マン', '月'] + KPI_HEADERS
    rows.append(header)

    # データ行
    for staff in STAFF_NAMES:
        for month in MONTHS:
            if month in all_data and staff in all_data[month]:
                row = [staff, month]
                for kpi in KPI_HEADERS:
                    value = all_data[month][staff].get(kpi, '')
                    row.append(value)
                rows.append(row)

    # CSVファイルに出力
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"✓ Google Sheets用形式で出力: {output_file}")

def main():
    # ファイルパス
    file1 = "/root/.claude/uploads/429fbfda-8cda-5d6f-b14f-f253462a154a/7faea010-___3__________.xlsx"
    file2 = "/root/.claude/uploads/429fbfda-8cda-5d6f-b14f-f253462a154a/e7617513-_3_______.xlsx"

    print("=" * 80)
    print("営業成績データ抽出 - Google Sheets形式")
    print("=" * 80)

    # File1から5月〜7月を抽出
    all_data = {}
    for month in ['5月', '6月', '7月']:
        print(f"\n📊 {month}のデータを抽出中...")
        try:
            monthly_data = extract_monthly_data(file1, month, month)
            if not all_data.get(month):
                all_data[month] = {}
            all_data[month].update(monthly_data)
            print(f"  ✓ {month}: {len(monthly_data)}名分のデータを取得")
        except Exception as e:
            print(f"  ✗ エラー: {e}")

    # File2から8月〜9月と累計平均を抽出
    print(f"\n📊 8月・9月のデータを抽出中...")
    try:
        file2_monthly = extract_monthly_data_from_file2(file2)
        for month in ['8月', '9月']:
            if month in file2_monthly:
                all_data[month] = file2_monthly[month]
                print(f"  ✓ {month}: {len(file2_monthly[month])}名分のデータを取得")
    except Exception as e:
        print(f"  ✗ エラー: {e}")

    # 出力
    print("\n" + "=" * 80)
    output_file = "/tmp/sales_performance_for_sheets.csv"
    export_google_sheets_format(all_data, output_file)

    print("\n【使い方】")
    print(f"1. {output_file} をテキストエディタで開く")
    print("2. 全ての行をコピー")
    print("3. Google Sheetの「営業成績（月別）」シートの A1 セルに貼り付け")
    print("4. Apps Scriptエディタで updatePerformanceAnalysis() を実行")
    print("\n✓ 営業成績管理システムが最新データで更新されます")

if __name__ == '__main__':
    main()
