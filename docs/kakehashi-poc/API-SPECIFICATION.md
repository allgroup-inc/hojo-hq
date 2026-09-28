# KAKEHASHI スケジュール管理 API仕様書
> **OpenAPI 3.0 + REST設計**

**バージョン**: 1.0.0  
**最終更新**: 2026-09-28  
**ステータス**: 統合実装向け（本番前確定版）

---

## 📌 概要

スケジュール管理システムが提供する REST API。営業12名のアポイントメント・キャンセル・移動時間・KPI を一元管理。

**ベースURL**: `https://kakehashi-api.example.com/api/v1`  
**認証**: Entra ID OAuth 2.0 + JWT（RS256、有効期限1時間）  
**レート制限**: 1000 req/分・ユーザーあたり  

---

## 🔐 認証フロー

```
1. クライアント: Entra ID ログイン
   ↓
2. バックエンド: /auth/callback で認可コード取得
   ↓
3. トークン交換: code → access_token
   ↓
4. JWT発行（RS256署名、exp: 1時間後、iss: kakehashi-apo-poc）
   ↓
5. 以後のリクエスト:
   Authorization: Bearer <JWT>
```

**必須ヘッダー（全エンドポイント共通）**
```
Authorization: Bearer eyJhbGc...（JWT）
X-Request-ID: uuid（トレーシング）
```

---

## 📊 API エンドポイント一覧

### 1️⃣ アポイントメント管理

#### POST /appointments
**説明**: 新規アポイントメント登録（❶入口システムから）

**リクエストボディ**:
```json
{
  "customerId": "KM-00123",
  "customerName": "サンプル商店",
  "scheduledDateTime": "2026-10-15T14:00:00+09:00",
  "estimatedDuration": 60,
  "location": "沖縄県那覇市中央",
  "source": "apogen_system",
  "assignedSalesRepId": "uuid-or-null",
  "notes": "商品説明希望"
}
```

**レスポンス（201 Created）**:
```json
{
  "id": "APO-20261015-001",
  "customerId": "KM-00123",
  "status": "SCHEDULED",
  "scheduledDateTime": "2026-10-15T14:00:00+09:00",
  "createdAt": "2026-09-28T15:30:00Z",
  "createdBy": "rep-001"
}
```

**エラーハンドリング**:
- `400 Bad Request`: 必須フィールド不足 / 日時形式が不正
- `401 Unauthorized`: JWT無効
- `403 Forbidden`: 権限なし（APO_STAFFのみ）
- `409 Conflict`: 営業マンのスケジュール競合

---

#### GET /appointments/{appointmentId}
**説明**: アポイントメント詳細取得

**パラメータ**:
- `appointmentId`（パス）: APO-20261015-001

**レスポンス（200 OK）**:
```json
{
  "id": "APO-20261015-001",
  "customerId": "KM-00123",
  "customerName": "サンプル商店",
  "scheduledDateTime": "2026-10-15T14:00:00+09:00",
  "estimatedDuration": 60,
  "actualDuration": null,
  "location": "沖縄県那覇市中央",
  "status": "SCHEDULED",
  "assignedSalesRepId": "rep-001-uuid",
  "assignedSalesRepName": "営業太郎",
  "source": "apogen_system",
  "notes": "商品説明希望",
  "createdAt": "2026-09-28T15:30:00Z",
  "updatedAt": "2026-09-28T15:30:00Z",
  "cancelledAt": null
}
```

---

#### GET /appointments
**説明**: アポイントメント一覧取得（フィルター・ページネーション対応）

**クエリパラメータ**:
```
?salesRepId=rep-001
&status=SCHEDULED
&fromDate=2026-10-01
&toDate=2026-10-31
&page=1
&limit=50
```

**レスポンス（200 OK）**:
```json
{
  "data": [
    { "id": "APO-20261015-001", ... },
    { "id": "APO-20261015-002", ... }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total": 127,
    "totalPages": 3
  }
}
```

---

#### PATCH /appointments/{appointmentId}
**説明**: アポイントメント更新（日時・営業マン・ステータス変更）

**リクエストボディ**:
```json
{
  "scheduledDateTime": "2026-10-15T15:00:00+09:00",
  "assignedSalesRepId": "rep-002-uuid",
  "notes": "時間変更しました"
}
```

**レスポンス（200 OK）**: 更新後のアポイントメント（GET と同じスキーマ）

**変更ログ自動記録**:
```json
{
  "changeLog": {
    "changedFields": ["scheduledDateTime", "assignedSalesRepId"],
    "changedBy": "rep-admin-uuid",
    "changedAt": "2026-09-28T16:00:00Z",
    "previousValues": {
      "scheduledDateTime": "2026-10-15T14:00:00+09:00",
      "assignedSalesRepId": "rep-001-uuid"
    }
  }
}
```

---

#### POST /appointments/{appointmentId}/cancel
**説明**: アポイントメント キャンセル（❂訪問管理へ通知）

**リクエストボディ**:
```json
{
  "reason": "顧客都合で延期",
  "cancelledBy": "rep-001-uuid"
}
```

**レスポンス（200 OK）**:
```json
{
  "id": "APO-20261015-001",
  "status": "CANCELLED",
  "cancelledAt": "2026-09-28T16:00:00Z",
  "cancelReason": "顧客都合で延期"
}
```

**副作用**:
- Slack通知を `#営業-キャンセル` へ自動送信
- 訪問管理システムへ `POST /api/visits/cancelled` を自動トリガー
- 営業マンのスケジュール該当時間を自動開放

---

### 2️⃣ 営業マン・スケジュール管理

#### GET /sales-reps
**説明**: 営業マン一覧取得（アクティブなメンバー）

**レスポンス（200 OK）**:
```json
{
  "data": [
    {
      "id": "rep-001-uuid",
      "name": "営業太郎",
      "email": "rep-001@company.onmicrosoft.com",
      "role": "SALES_REP",
      "isActive": true,
      "timezone": "Asia/Tokyo",
      "workingHoursStart": "09:00",
      "workingHoursEnd": "18:00",
      "breakTimeStart": "12:00",
      "breakTimeEnd": "13:00",
      "travelTimeBuffer": 30,
      "currentLoad": 5
    },
    ...
  ],
  "total": 12
}
```

---

#### GET /sales-reps/{salesRepId}/free-slots
**説明**: 営業マンの空き時間検出（移動時間・休憩を考慮）

**パラメータ**:
```
GET /sales-reps/rep-001-uuid/free-slots?date=2026-10-15&duration=60
```

**レスポンス（200 OK）**:
```json
{
  "salesRepId": "rep-001-uuid",
  "date": "2026-10-15",
  "requestedDuration": 60,
  "slots": [
    {
      "start": "2026-10-15T09:00:00+09:00",
      "end": "2026-10-15T10:00:00+09:00",
      "available": true
    },
    {
      "start": "2026-10-15T10:30:00+09:00",
      "end": "2026-10-15T11:30:00+09:00",
      "available": true
    },
    {
      "start": "2026-10-15T13:00:00+09:00",
      "end": "2026-10-15T14:00:00+09:00",
      "available": true
    }
  ]
}
```

**計算ロジック**:
- 営業時間: 09:00-18:00
- 固定休憩: 12:00-13:00
- 移動バッファ: 30分（訪問前後）
- 所要時間: requestedDuration + バッファ

---

#### GET /sales-reps/round-robin
**説明**: ラウンドロビン対象の営業マン候補（次の割り当て対象）

**パラメータ**:
```
?date=2026-10-15
&duration=60
&priority=STANDARD
```

**レスポンス（200 OK）**:
```json
{
  "candidates": [
    {
      "rank": 1,
      "salesRepId": "rep-003-uuid",
      "name": "営業花子",
      "availableSlots": 3,
      "currentLoadRatio": 0.42,
      "lastAssignmentTime": "2026-10-14T16:00:00Z",
      "score": 92
    },
    {
      "rank": 2,
      "salesRepId": "rep-001-uuid",
      "name": "営業太郎",
      "availableSlots": 2,
      "currentLoadRatio": 0.58,
      "lastAssignmentTime": "2026-10-14T09:00:00Z",
      "score": 78
    }
  ]
}
```

**スコア計算アルゴリズム**:
```
score = (空きスロット数 × 0.4) 
      + (負荷率の低さ × 0.3)
      + (割り当て間隔の長さ × 0.3)
      - (優先度マッチ度のボーナス)
```

---

### 3️⃣ KPI・レポート管理

#### GET /kpi/daily-summary
**説明**: 日別KPIサマリー（営業12名分集計）

**パラメータ**:
```
?date=2026-10-15
```

**レスポンス（200 OK）**:
```json
{
  "date": "2026-10-15",
  "summary": {
    "totalAppointments": 45,
    "completedAppointments": 42,
    "cancelledAppointments": 2,
    "averageAppointmentDuration": 52,
    "completionRate": 0.9333,
    "cancelRate": 0.0444
  },
  "byRepresentative": [
    {
      "salesRepId": "rep-001-uuid",
      "name": "営業太郎",
      "appointments": 4,
      "completed": 4,
      "cancelled": 0,
      "averageDuration": 55,
      "averageDistance": 12.5
    },
    ...
  ],
  "peakHours": {
    "14:00-15:00": 8,
    "15:00-16:00": 7,
    "10:00-11:00": 6
  }
}
```

---

#### GET /kpi/monthly-performance
**説明**: 月別パフォーマンスレポート

**パラメータ**:
```
?month=2026-10
&salesRepId=rep-001-uuid（オプション）
```

**レスポンス（200 OK）**:
```json
{
  "month": "2026-10",
  "totalAppointments": 450,
  "completionRate": 0.9244,
  "averageAppointmentDuration": 54,
  "appointmentsBySalesRep": [
    {
      "salesRepId": "rep-001-uuid",
      "name": "営業太郎",
      "appointments": 38,
      "completionRate": 0.9737,
      "trend": "📈 +2.1%"
    },
    ...
  ],
  "cancellationReasons": {
    "顧客都合で延期": 15,
    "営業マン急務": 8,
    "天候": 2
  }
}
```

---

### 4️⃣ 通知管理

#### POST /notifications/slack-webhook
**説明**: Slack通知の設定・テスト（アポ確定・キャンセル・リマインダー）

**リクエストボディ**:
```json
{
  "event": "appointment_scheduled",
  "channel": "#営業-スケジュール",
  "template": "APPOINTMENT_SCHEDULED",
  "variables": {
    "appointmentId": "APO-20261015-001",
    "customerName": "サンプル商店",
    "scheduledTime": "2026-10-15T14:00:00+09:00",
    "salesRepName": "営業太郎"
  }
}
```

**レスポンス（200 OK）**:
```json
{
  "messageId": "msg-20260928-001",
  "status": "SENT",
  "sentAt": "2026-09-28T16:00:00Z"
}
```

**対応イベント**:
- `appointment_scheduled`: 新規アポ登録
- `appointment_cancelled`: キャンセル
- `appointment_rescheduled`: 日時変更
- `reminder_1_hour`: 1時間前リマインダー
- `reminder_1_day`: 1日前リマインダー

---

### 5️⃣ 他システム連携（出力）

#### POST /api/visits/completed
**説明**: ❂訪問管理システムへの訪問完了通知

**リクエストボディ**:
```json
{
  "appointmentId": "APO-20261015-001",
  "status": "completed",
  "actualDateTime": "2026-10-15T14:30:00+09:00",
  "actualDuration": 55,
  "visitOutcome": "商品説明実施",
  "notes": "顧客の反応良好"
}
```

**レスポンス（202 Accepted）**: 非同期処理・確認メール後に ❂へ送信

---

#### POST /api/visits/cancelled
**説明**: ❂訪問管理システムへのキャンセル通知

**リクエストボディ**:
```json
{
  "appointmentId": "APO-20261015-001",
  "status": "cancelled",
  "reason": "顧客都合で延期"
}
```

---

## ⚡ エラーハンドリング標準

全エンドポイント共通の標準エラーレスポンス:

```json
{
  "error": {
    "code": "APPOINTMENT_NOT_FOUND",
    "message": "指定されたアポイントメントが見つかりません",
    "statusCode": 404,
    "timestamp": "2026-09-28T16:00:00Z",
    "requestId": "req-12345"
  }
}
```

**主要エラーコード**:
| コード | HTTP | 説明 |
|---|---|---|
| INVALID_REQUEST | 400 | リクエスト形式エラー |
| UNAUTHORIZED | 401 | 認証エラー |
| FORBIDDEN | 403 | 権限エラー |
| NOT_FOUND | 404 | リソース未検出 |
| CONFLICT | 409 | スケジュール競合 |
| RATE_LIMIT_EXCEEDED | 429 | レート制限超過 |
| INTERNAL_SERVER_ERROR | 500 | サーバーエラー |

---

## 🧪 テストシナリオ

### Scenario 1: 入口システムからのアポ自動登録
```
POST /appointments
  ↓
新規アポ登録
  ↓
ラウンドロビン → rep-003 に自動割り当て
  ↓
Slack通知: #営業-スケジュール
  ↓
検証: GET /appointments/APO-20261015-001 で確認
```

### Scenario 2: アポキャンセル時の自動通知
```
POST /appointments/APO-20261015-001/cancel
  ↓
ステータス = CANCELLED
  ↓
Slack通知 + ❂へ POST /api/visits/cancelled
  ↓
営業マンのスケジュール該当時間を自動開放
  ↓
検証: GET /sales-reps/rep-003/free-slots で空き復活
```

### Scenario 3: 営業マン12名の日別KPI集計
```
GET /kpi/daily-summary?date=2026-10-15
  ↓
12名分のアポ・完了・キャンセル・平均時間を集計
  ↓
completionRate・cancelRate・peakHoursを計算
  ↓
ダッシュボード・Slack通知での自動配信
```

---

## 📋 OpenAPI スキーマ（YAML）

```yaml
openapi: 3.0.0
info:
  title: KAKEHASHI Schedule Management API
  version: 1.0.0
  description: Appointment and schedule management for 12 sales representatives

servers:
  - url: https://kakehashi-api.example.com/api/v1

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
  
  schemas:
    Appointment:
      type: object
      properties:
        id:
          type: string
          example: APO-20261015-001
        customerId:
          type: string
        customerName:
          type: string
        scheduledDateTime:
          type: string
          format: date-time
        estimatedDuration:
          type: integer
        status:
          type: string
          enum: [SCHEDULED, COMPLETED, CANCELLED]
        assignedSalesRepId:
          type: string

paths:
  /appointments:
    post:
      summary: Create new appointment
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/Appointment'
      responses:
        '201':
          description: Appointment created
    get:
      summary: List appointments
      security:
        - bearerAuth: []
      responses:
        '200':
          description: Appointments list
```

---

## 🚀 実装チェックリスト

- [ ] 全エンドポイントを実装
- [ ] JWT署名検証を実装
- [ ] エラーハンドリング・バリデーション完成
- [ ] ユニットテスト（100%カバレッジ）
- [ ] 統合テスト（全シナリオ）
- [ ] Postman コレクション作成
- [ ] API文書を SwaggerUI で公開
- [ ] レート制限・ロギング実装
- [ ] 本番環境でのセキュリティスキャン

