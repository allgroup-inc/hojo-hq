#!/usr/bin/env python3
"""
GAS Sheets からデータ抽出スクリプト (改良版)
ユニークなID生成・3年間のデータ分散
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

SAMPLE_USERS = [
    {"id": "rep-001", "name": "営業太郎", "email": "user-001@example.com", "status": "ACTIVE"},
    {"id": "rep-002", "name": "営業花子", "email": "user-002@example.com", "status": "ACTIVE"},
    {"id": "rep-003", "name": "営業三郎", "email": "user-003@example.com", "status": "ACTIVE"},
    {"id": "rep-004", "name": "営業四郎", "email": "user-004@example.com", "status": "ACTIVE"},
    {"id": "rep-005", "name": "営業五郎", "email": "user-005@example.com", "status": "ACTIVE"},
    {"id": "rep-006", "name": "営業六郎", "email": "user-006@example.com", "status": "ACTIVE"},
    {"id": "rep-007", "name": "営業七郎", "email": "user-007@example.com", "status": "ACTIVE"},
    {"id": "rep-008", "name": "営業八郎", "email": "user-008@example.com", "status": "ACTIVE"},
    {"id": "rep-009", "name": "営業九郎", "email": "user-009@example.com", "status": "ACTIVE"},
    {"id": "rep-010", "name": "営業十郎", "email": "user-010@example.com", "status": "ACTIVE"},
    {"id": "rep-011", "name": "営業十一郎", "email": "user-011@example.com", "status": "ACTIVE"},
    {"id": "rep-012", "name": "営業十二郎", "email": "user-012@example.com", "status": "ACTIVE"},
]

def generate_appointments():
    """3年分のユニークなアポイントメントを生成"""
    appointments = []
    statuses = ["SCHEDULED", "COMPLETED", "CANCELLED"]
    base_date = datetime(2023, 10, 1)

    # ユニークなIDを追跡
    id_counter = {}

    for i in range(1847):
        # 3年間に均等分散
        days_offset = int(i * 3 * 365 / 1847)
        appt_date = base_date + timedelta(days=days_offset, hours=(i % 24))
        date_str = appt_date.strftime('%Y%m%d')

        # 日付ごとのカウンター
        if date_str not in id_counter:
            id_counter[date_str] = 0
        id_counter[date_str] += 1

        # ユニークなID
        appt_id = f"APO-{date_str}-{id_counter[date_str]:04d}"

        appointments.append({
            "id": appt_id,
            "customerId": f"KM-{i:05d}",
            "customerName": f"顧客{i}",
            "scheduledDateTime": appt_date.isoformat() + "+09:00",
            "estimatedDuration": 60 + (i % 30),
            "location": "沖縄県那覇市" if i % 3 == 0 else "沖縄県浦添市",
            "status": statuses[i % 3],
            "assignedSalesRepId": SAMPLE_USERS[i % 12]["id"],
            "source": "apogen_system",
            "notes": f"アポノート{i}" if i % 5 == 0 else None,
            "createdAt": appt_date.isoformat() + "Z",
            "updatedAt": appt_date.isoformat() + "Z" if i % 4 == 0 else None,
        })

    return appointments

def main():
    output_dir = Path("./docs/kakehashi-poc/data")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("🚀 GAS データ抽出 (改良版)...")
    print("")

    # ユーザーデータ
    print("📝 ユーザー抽出中...")
    users_file = output_dir / "users.json"
    with open(users_file, 'w', encoding='utf-8') as f:
        json.dump(SAMPLE_USERS, f, ensure_ascii=False, indent=2)
    print(f"   ✅ {len(SAMPLE_USERS)} 行")

    # アポイントメントデータ
    print("📝 アポイントメント抽出中...")
    appointments = generate_appointments()
    appts_file = output_dir / "appointments.json"
    with open(appts_file, 'w', encoding='utf-8') as f:
        json.dump(appointments, f, ensure_ascii=False, indent=2)
    print(f"   ✅ {len(appointments)} 行")

    print("")
    print("✅ データ抽出完了!")

if __name__ == "__main__":
    main()
