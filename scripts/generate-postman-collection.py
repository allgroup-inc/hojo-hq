#!/usr/bin/env python3
"""
API-SPECIFICATION.md から Postman Collection 2.1 自動生成
"""

import json
from datetime import datetime

def generate_postman_collection():
    """Postman Collection を生成"""

    collection = {
        "info": {
            "name": "KAKEHASHI APO Management System",
            "description": "スケジュール管理 API - 営業12名のアポ・KPI一元管理",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "version": "1.0.0"
        },
        "item": [
            # 1. アポイントメント管理
            {
                "name": "📅 アポイントメント管理",
                "item": [
                    {
                        "name": "新規アポ登録",
                        "request": {
                            "method": "POST",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                },
                                {
                                    "key": "X-Request-ID",
                                    "value": "{{$guid}}"
                                },
                                {
                                    "key": "Content-Type",
                                    "value": "application/json"
                                }
                            ],
                            "body": {
                                "mode": "raw",
                                "raw": json.dumps({
                                    "customerId": "KM-00123",
                                    "customerName": "サンプル商店",
                                    "scheduledDateTime": "2026-10-15T14:00:00+09:00",
                                    "estimatedDuration": 60,
                                    "location": "沖縄県那覇市中央",
                                    "source": "apogen_system",
                                    "assignedSalesRepId": None,
                                    "notes": "商品説明希望"
                                }, ensure_ascii=False, indent=2)
                            },
                            "url": {
                                "raw": "{{base_url}}/appointments",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "v1", "appointments"]
                            }
                        }
                    },
                    {
                        "name": "アポ詳細取得",
                        "request": {
                            "method": "GET",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                },
                                {
                                    "key": "X-Request-ID",
                                    "value": "{{$guid}}"
                                }
                            ],
                            "url": {
                                "raw": "{{base_url}}/appointments/APO-20261015-001",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "v1", "appointments", "APO-20261015-001"]
                            }
                        }
                    },
                    {
                        "name": "アポ一覧取得",
                        "request": {
                            "method": "GET",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                },
                                {
                                    "key": "X-Request-ID",
                                    "value": "{{$guid}}"
                                }
                            ],
                            "url": {
                                "raw": "{{base_url}}/appointments?salesRepId=rep-001&status=SCHEDULED&fromDate=2026-10-01&toDate=2026-10-31&page=1&limit=50",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "v1", "appointments"],
                                "query": [
                                    {"key": "salesRepId", "value": "rep-001"},
                                    {"key": "status", "value": "SCHEDULED"},
                                    {"key": "fromDate", "value": "2026-10-01"},
                                    {"key": "toDate", "value": "2026-10-31"},
                                    {"key": "page", "value": "1"},
                                    {"key": "limit", "value": "50"}
                                ]
                            }
                        }
                    },
                    {
                        "name": "アポ更新",
                        "request": {
                            "method": "PATCH",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                },
                                {
                                    "key": "X-Request-ID",
                                    "value": "{{$guid}}"
                                },
                                {
                                    "key": "Content-Type",
                                    "value": "application/json"
                                }
                            ],
                            "body": {
                                "mode": "raw",
                                "raw": json.dumps({
                                    "scheduledDateTime": "2026-10-15T15:00:00+09:00",
                                    "assignedSalesRepId": "rep-002-uuid",
                                    "status": "CONFIRMED"
                                }, ensure_ascii=False, indent=2)
                            },
                            "url": {
                                "raw": "{{base_url}}/appointments/APO-20261015-001",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "v1", "appointments", "APO-20261015-001"]
                            }
                        }
                    },
                    {
                        "name": "アポキャンセル",
                        "request": {
                            "method": "POST",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                },
                                {
                                    "key": "X-Request-ID",
                                    "value": "{{$guid}}"
                                }
                            ],
                            "url": {
                                "raw": "{{base_url}}/appointments/APO-20261015-001/cancel",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "v1", "appointments", "APO-20261015-001", "cancel"]
                            }
                        }
                    }
                ]
            },
            # 2. 営業マン管理
            {
                "name": "👥 営業マン管理",
                "item": [
                    {
                        "name": "営業マン一覧取得",
                        "request": {
                            "method": "GET",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                }
                            ],
                            "url": {
                                "raw": "{{base_url}}/sales-reps",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "v1", "sales-reps"]
                            }
                        }
                    },
                    {
                        "name": "営業マン詳細取得",
                        "request": {
                            "method": "GET",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                }
                            ],
                            "url": {
                                "raw": "{{base_url}}/sales-reps/rep-001-uuid",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "v1", "sales-reps", "rep-001-uuid"]
                            }
                        }
                    },
                    {
                        "name": "営業マンの空き時間取得",
                        "request": {
                            "method": "GET",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                }
                            ],
                            "url": {
                                "raw": "{{base_url}}/sales-reps/rep-001-uuid/free-slots?date=2026-10-15",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "v1", "sales-reps", "rep-001-uuid", "free-slots"],
                                "query": [
                                    {"key": "date", "value": "2026-10-15"}
                                ]
                            }
                        }
                    },
                    {
                        "name": "ラウンドロビン振り分け",
                        "request": {
                            "method": "GET",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                }
                            ],
                            "url": {
                                "raw": "{{base_url}}/sales-reps/round-robin?date=2026-10-15&time=14:00",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "v1", "sales-reps", "round-robin"],
                                "query": [
                                    {"key": "date", "value": "2026-10-15"},
                                    {"key": "time", "value": "14:00"}
                                ]
                            }
                        }
                    }
                ]
            },
            # 3. KPI・レポーティング
            {
                "name": "📊 KPI・レポーティング",
                "item": [
                    {
                        "name": "日次サマリー取得",
                        "request": {
                            "method": "GET",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                }
                            ],
                            "url": {
                                "raw": "{{base_url}}/kpi/daily-summary?date=2026-10-15",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "v1", "kpi", "daily-summary"],
                                "query": [
                                    {"key": "date", "value": "2026-10-15"}
                                ]
                            }
                        }
                    },
                    {
                        "name": "月間パフォーマンス取得",
                        "request": {
                            "method": "GET",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                }
                            ],
                            "url": {
                                "raw": "{{base_url}}/kpi/monthly-performance?year=2026&month=10",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "v1", "kpi", "monthly-performance"],
                                "query": [
                                    {"key": "year", "value": "2026"},
                                    {"key": "month", "value": "10"}
                                ]
                            }
                        }
                    }
                ]
            },
            # 4. 通知・Slack連携
            {
                "name": "🔔 通知・Slack連携",
                "item": [
                    {
                        "name": "Slack通知送信",
                        "request": {
                            "method": "POST",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                },
                                {
                                    "key": "Content-Type",
                                    "value": "application/json"
                                }
                            ],
                            "body": {
                                "mode": "raw",
                                "raw": json.dumps({
                                    "channel": "#apo-notifications",
                                    "message": "新規アポが登録されました",
                                    "appointmentId": "APO-20261015-001"
                                }, ensure_ascii=False, indent=2)
                            },
                            "url": {
                                "raw": "{{base_url}}/notifications/slack-webhook",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "v1", "notifications", "slack-webhook"]
                            }
                        }
                    }
                ]
            },
            # 5. システム連携
            {
                "name": "🔗 システム連携 (❶❂❸)",
                "item": [
                    {
                        "name": "訪問完了通知",
                        "request": {
                            "method": "POST",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                },
                                {
                                    "key": "Content-Type",
                                    "value": "application/json"
                                }
                            ],
                            "body": {
                                "mode": "raw",
                                "raw": json.dumps({
                                    "appointmentId": "APO-20261015-001",
                                    "actualDuration": 45,
                                    "result": "商品説明完了、購入予定なし",
                                    "nextActionDate": "2026-10-22"
                                }, ensure_ascii=False, indent=2)
                            },
                            "url": {
                                "raw": "{{base_url}}/api/visits/completed",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "visits", "completed"]
                            }
                        }
                    },
                    {
                        "name": "訪問キャンセル通知",
                        "request": {
                            "method": "POST",
                            "header": [
                                {
                                    "key": "Authorization",
                                    "value": "Bearer {{jwt_token}}"
                                },
                                {
                                    "key": "Content-Type",
                                    "value": "application/json"
                                }
                            ],
                            "body": {
                                "mode": "raw",
                                "raw": json.dumps({
                                    "appointmentId": "APO-20261015-001",
                                    "cancelReason": "顧客が急遽キャンセル"
                                }, ensure_ascii=False, indent=2)
                            },
                            "url": {
                                "raw": "{{base_url}}/api/visits/cancelled",
                                "protocol": "https",
                                "host": ["{{base_url}}"],
                                "path": ["api", "visits", "cancelled"]
                            }
                        }
                    }
                ]
            }
        ],
        "variable": [
            {
                "key": "base_url",
                "value": "kakehashi-api.example.com",
                "type": "string"
            },
            {
                "key": "jwt_token",
                "value": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "type": "string"
            }
        ]
    }

    return collection

def main():
    print("🚀 Postman Collection 生成中...")
    collection = generate_postman_collection()

    output_file = Path(__file__).parent.parent / "docs/kakehashi-poc/KAKEHASHI-APO-API.postman_collection.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(collection, f, ensure_ascii=False, indent=2)

    print(f"✅ Postman Collection 生成完了")
    print(f"   ファイル: {output_file}")
    print(f"   エンドポイント数: {sum(len(item.get('item', [])) for item in collection['item'])}")
    print("")
    print("📌 Postmanでの使用方法:")
    print("   1. Postman を開く")
    print("   2. Import → Select Files")
    print(f"   3. {output_file} を選択")
    print("   4. Variables タブで base_url, jwt_token を設定")
    print("   5. 各リクエストを実行")
    print("")

if __name__ == "__main__":
    from pathlib import Path
    main()
