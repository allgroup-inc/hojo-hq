# KAKEHASHI統合アーキテクチャ設計

**作成日**: 2026-09-27  
**対象**: kakei-apo（家計のポっ）内へのコンポーネント統合

---

## システム全体図

```
❶入口(アポ生成) [kakei-crm/apps/apogen]
    │ アポ確定＆顧客ID付与
    ↓
つなぎ(予約表) = 家計のポっ ← [本システム: スケジュール管理]
kakei-apo
    │ 訪問完了・キャンセル通知
    ↓
❂対面営業マン物件管理 [enlife-mikomi]
    │ 申込み成立
    ↓
❸保全CRM [kakei-hozen]
```

## 推奨技術スタック

**フロントエンド**:
- React 18 + Next.js 14（SSR）
- React Big Calendar（日/週/月ビュー）
- React DnD（ドラッグ&ドロップ）
- Material-UI v5 または shadcn/ui
- Zustand（状態管理・シンプル）
- Socket.io-client（リアルタイム同期）

**バックエンド**:
- Node.js 20 LTS + Express
- Prisma ORM（PostgreSQL）
- passport.js + OAuth 2.0（Entra ID）
- REST API（OpenAPI 3.0）

**データベース**:
- PostgreSQL 15+（users, appointments, schedules, kpi_metrics, changelog）
- JSONB 型（監査ログ・柔軟保存）

**インフラ**:
- AWS または GCP（未決定、別途リスク分析で検討）
- Redis（キャッシュ・リアルタイム同期）

---

## 他システムとのインターフェース

### **❶入口システム（アポ生成） → つなぎ（スケジュール管理）**

**API: POST /api/v1/appointments**
```json
{
  "customerId": "KM-00123",
  "customerName": "サンプル商店",
  "scheduledDateTime": "2026-09-28T14:00:00+09:00",
  "estimatedDuration": 60,
  "location": "沖縄県那覇市中央",
  "source": "apogen_system",
  "assignedSalesRepId": "uuid-or-null"
}
```

**Response**: 201 Created
```json
{
  "id": "APO-20260928-001",
  "status": "SCHEDULED",
  "createdAt": "2026-09-27T15:30:00Z"
}
```

**認証**: Entra ID トークン + API キー

---

### **つなぎ（スケジュール管理） → ❂対面営業マン物件管理**

**API: POST /api/v1/visits/completed** （訪問完了通知）
```json
{
  "appointmentId": "APO-20260928-001",
  "status": "completed",
  "actualDateTime": "2026-09-28T14:30:00+09:00",
  "visitOutcome": "商品説明実施"
}
```

**API: POST /api/v1/visits/cancelled** （キャンセル通知）
```json
{
  "appointmentId": "APO-20260928-001",
  "status": "cancelled",
  "reason": "顧客都合で延期"
}
```

---

## Entra ID 認証フロー

```
1. ユーザーが アプリへアクセス
   ↓
2. Entra ID ログイン画面へリダイレクト
   ↓
3. Microsoft 認証 & 認可コード取得
   ↓
4. アプリバックエンド: トークン交換（code → access_token）
   ↓
5. JWT 発行（RS256署名、1時間有効期限）
   ↓
6. クライアント: Authorization ヘッダーに JWT を含める
   ↓
7. 以後のリクエスト: JWT 検証 + ロール確認
```

---

## 現在のGAS実装との互換性

| 機能 | 現在のGAS | 新システム | 転用率 |
|---|---|---|---|
| 日ビュー表示 | Sheetsベース | React Calendar | 70% |
| アポ新規登録 | GASフォーム | React モーダル | 80% |
| ドラッグ&ドロップ | 非対応 | React DnD | — |
| ラウンドロビン | スクリプト | Node.js関数 | 90% |
| Slack通知 | Webhook | Slack API | 85% |
| 監査ログ | 限定的 | PostgreSQL JSONB | — |

**全体転用率**: 約70-75%

---

## データマイグレーション方針

**段階1**: 既存GAS Sheetsデータを JSON にエクスポート
**段階2**: JSON データを PostgreSQL にインポート（IDマッピング）
**段階3**: テスト環境で過去3ヶ月分のデータをバリデーション
**段階4**: 本番投入前に本データで最終テスト
