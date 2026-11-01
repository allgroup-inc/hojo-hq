#!/usr/bin/env python3
"""
福田データをGoogle Sheetsのステージングタブへ自動アップロード
"""

import argparse
import json
import openpyxl
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

def upload_to_staging_sheet(xlsx_path, sheet_id, creds_json, validation_result_path=None):
    """ExcelデータをGoogle Sheetsにアップロード"""

    # 認証
    creds_dict = json.loads(creds_json) if isinstance(creds_json, str) else creds_json
    creds = Credentials.from_service_account_info(creds_dict)
    service = build('sheets', 'v4', credentials=creds)

    # Excelファイルを読み込み
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active

    # 全データを取得
    all_data = []
    for row in ws.iter_rows(max_row=ws.max_row, max_col=ws.max_column, values_only=True):
        all_data.append(list(row))

    wb.close()

    # ステージングシート名
    staging_sheet_name = "福田_履歴インポート"

    # 既存データをクリア＋新規データを貼り付け
    request_body = {
        'requests': [
            {
                'updateRange': {
                    'range': f"{staging_sheet_name}!A:Z",
                    'values': all_data
                }
            }
        ]
    }

    try:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body=request_body
        ).execute()

        print(f"✓ データをシート「{staging_sheet_name}」にアップロード: {len(all_data)}行")
        return True

    except Exception as e:
        print(f"✗ アップロード失敗: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload Fukuda data to Google Sheets")
    parser.add_argument("--xlsx", required=True, help="XLSX file path")
    parser.add_argument("--sheet-id", required=True, help="Google Sheet ID")
    parser.add_argument("--creds", required=True, help="Service account credentials JSON")
    parser.add_argument("--validation-result", help="Validation result JSON path")

    args = parser.parse_args()

    # 認証情報の読み込み
    with open(args.creds) as f:
        creds_json = f.read()

    success = upload_to_staging_sheet(args.xlsx, args.sheet_id, creds_json, args.validation_result)
    exit(0 if success else 1)
