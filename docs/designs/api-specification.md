# REST API仕様設計（Task 6）

**10個のエンドポイント:**

1. `GET /api/dashboard/today` - 本日のダッシュボード情報
2. `GET /api/appointments/by-date/:date` - 指定日のアポ一覧（営業マン別）
3. `GET /api/appointments/by-week/:year/:week` - 週単位のアポ一覧
4. `GET /api/appointments/by-month/:year/:month` - 月単位のアポ一覧
5. `POST /api/appointments` - アポ新規作成
6. `PUT /api/appointments/:id` - アポ編集
7. `DELETE /api/appointments/:id` - アポ削除（キャンセル）
8. `GET /api/appointments/:id/free-times` - 営業マンの次の空き時間検出
9. `POST /api/appointments/round-robin` - ラウンドロビン提案（1週間の最適分配）
10. `GET /api/analytics/kpi` - KPI集計データ取得

**認証:**
- JWT トークン（Authorization: Bearer <token>）
- Entra ID OAuth 2.0フロー
- トークン有効期限: 1時間、リフレッシュトークン: 7日

**レート制限:**
- アポ入れ人: 100リクエスト/分
- 営業マン: 50リクエスト/分
- 管理者: 無制限

**レスポンス例 (GET /api/dashboard/today):**
```json
{
  "date": "2026-09-28",
  "appointmentsCount": 12,
  "completedCount": 8,
  "cancelledCount": 1,
  "pendingCount": 3,
  "salesRepStatus": [
    {
      "userId": "uuid-1",
      "name": "営業太郎",
      "nextAppointment": {
        "id": "APO-001",
        "time": "14:30",
        "customer": "サンプル商店",
        "location": "那覇市中央"
      },
      "timeToNext": 45,
      "completedToday": 3
    }
  ]
}
```
