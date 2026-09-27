# KAKEHASHI統合版 スケジュール管理システム設計計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 営業マン12名向けのスケジュール管理システムをKAKEHASHI（kakei-apo）内に統合されるコンポーネントとして完全に再設計し、既存システムの「良い仕組み」をすべて取り込みながら、UX・セキュリティ・スケーラビリティを最適化する。

**Architecture:** 現在のGAS+Sheetsベースの実装から、kakei-apoの今後のNode.js移設を視野に入れたコンポーネント設計に転換。Figmaワイヤーフレーム・詳細なデータモデル・REST API仕様・セキュリティガバナンスを完成させ、実装チームが10月中旬から即座に開発を開始できる状態に整える。KAKEHASHI内の他システム（❶入口・❂対面営業マン物件管理・❸保全CRM）との連携インターフェースも明確化する。

**Tech Stack:** フロントエンド（React/Next.js）、バックエンド（Node.js + Express）、データベース（PostgreSQL）、認証（Entra ID + OAuth 2.0）、リアルタイム通知（WebSocket + Slack API）、スケジュール管理ライブラリ（React Big Calendar / ical.js）

**Spec:** `docs/designs/kakehashi-schedule-system-spec.md`（新規作成）

## Global Constraints

- **最大営業数**: 12名（現在11名、将来的な成長を考慮）
- **対応端末**: スマートフォン・タブレット・PC（レスポンシブデザイン必須）
- **1日の登録想定件数**: 最大100件のアポ
- **認証方式**: Entra ID（全社共通ゲート）+ OAuth 2.0トークン
- **データ保持期限**: 過去3年間のアポ履歴・変更ログを保持
- **可用性要件**: 営業時間帯（7:00〜22:00 JST）99.5%以上の稼働率
- **KAKEHASHI内での位置づけ**: つなぎ＝予約表（❶アポ生成と❂対面営業マン物件管理の間）
- **技術遷移**: 現在のGAS実装の約70%は新システムにも転用可能な設計
- **プライバシー・セキュリティ**: kakei-apo 非公開リポジトリ、顧客個人情報をコミットしない、実装は `kakei-apo/src/` 配下

---

## フェーズ1（9月27日〜10月3日）: 分析・設計フェーズ

### Task 1: 既存システムの「いいとこ」分析表作成

**Files:**
- Create: `docs/designs/existing-systems-analysis.md`
- Reference: 市場調査報告書（既完成）

**Interfaces:**
- Consumes: 市場調査データ（Salesforce, HubSpot, Notion, Airtable, Calendly, Zoho CRM, Pipedrive, eセールスマネージャー、現在のGAS実装）
- Produces: `BEST_PRACTICES` テーブル（12行 × 機能領域ごとの「採用すべき仕組み」一覧）、営業マン12名の要件との照合マトリックス

- [ ] **Step 1: 市場調査報告書から「営業マン複数名のスケジュール管理」に関する「いいとこ」をリスト化**

分析対象：
- UI/UX: ビュー複数性（日/週/月）、ドラッグ&ドロップ操作性、共有カレンダーの見やすさ
- スケジューリング機能: ラウンドロビン、予約時間の自動最適化、移動時間の自動計算
- 通知・アラート: リアルタイム通知、確定時の自動通知、キャンセル時の関係者自動通知
- アクセス権限: アポ入れ人と営業マンの権限分離、部長の可視化レベル
- 空き時間検出: アルゴリズム（営業マンの移動時間・準備時間・休憩を考慮）
- レポート・分析: 日別アポ件数、営業マン別の効率指標、キャンセル率

- [ ] **Step 2: 営業マン12名向けの要件と既存システムの「いいとこ」をマトリックスで照合**

要件項目（営業運用側から確認したもの）:
1. 日時・週間・月刊表示（最低3つのビュー必須）
2. アポ入れ人と訪問人の権限分離（異なる操作レベル）
3. 空き時間の自動検出・可視化（営業マンの移動時間を考慮）
4. ラウンドロビン機能（複数営業への自動振り分け）
5. イレギュラー対応（予約キャンセル・予定変更時の自動通知）
6. 数値取得・分析（KPI用レポート出力）
7. スマートフォン対応（営業マンの外出先からのアクセス）
8. リアルタイム更新（複数営業が同じ画面を見ながら調整）
9. Slack連携（チーム内の高速なコミュニケーション）
10. 監査ログ（誰が何をいつ変更したか）

照合結果: 各要件に対して、既存システムのどの実装が参考になるかを明記

- [ ] **Step 3: 「採用すべき仕組み」を10項目にまとめる**

例：
1. **マルチビュー**: HubSpot + Calendly の実装方式を参考に、日/週/月の3ビューを React Big Calendar で実現
2. **ラウンドロビン**: Zoho CRM の自動振り分けロジックを参考に、営業マン間の負荷をアルゴリズムで均等化
3. **空き時間検出**: 現在のGAS実装の週単位ロジック + Salesforce の移動時間自動計算を組み合わせ
4. **権限管理**: eセールスマネージャーの「閲覧権限 / 編集権限 / 削除権限」の3層分け
5. **リアルタイム更新**: WebSocket + Redis キャッシュで複数クライアント間の同期
6. **通知・アラート**: Slack API + Power Automate の双方を検討し、Slack主体に統一
7. **監査ログ**: PostgreSQL の JSONB 型で履歴を構造化保存
8. **モバイル対応**: Material-UI または Ant Design で responsive layout
9. **API設計**: GraphQL (Apollo) 検討後、REST + JSON で汎用性を重視
10. **オフライン対応**: 必須でない（営業マンは常にネットワーク環境）

- [ ] **Step 4: 分析表をMarkdownで `docs/designs/existing-systems-analysis.md` に出力**

構成：
- 各システムの概要表（価格・機能・営業12名向けの適性）
- 要件 × 既存システムの照合マトリックス
- 採用すべき10の仕組み（メリット・デメリット・実装難度）
- 推奨アーキテクチャ決定根拠

- [ ] **Step 5: 分析表をレビュー可能な形式で保存・コミット**

```bash
git add docs/designs/existing-systems-analysis.md
git commit -m "docs: analyze existing systems and extract best practices for schedule management

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

### Task 2: UI/UXワイヤーフレーム設計（Figma）

**Files:**
- Create: Figma ファイル「KAKEHASHI スケジュール管理 v1」
- Document: `docs/designs/ui-ux-wireframe-guide.md`

**Interfaces:**
- Consumes: Task 1 の「採用すべき仕組み」（マルチビュー・権限分離・空き時間可視化など）
- Produces: Figma ファイル URL、スクリーンショット 5枚（PNG）、ディレクトリ構造定義

- [ ] **Step 1: Figma ファイルを新規作成「KAKEHASHI スケジュール管理 v1」**

設定：
- Workspace: ALLGROUP 共有 Workspace
- 解像度: 375px（スマートフォン）/ 1440px（デスクトップ）
- カラーシステム: kakei-apo CLAUDE.md 指定の配色（未指定の場合は暫定でネイビー#002D5C+オレンジ#FF9500）
- タイポグラフィ: Noto Sans JP、本文14px / 見出し18px / 大見出し24px

- [ ] **Step 2: 5つのメイン画面をワイヤーフレーム設計**

Screen 1: **ダッシュボード** (全員共通)
- 本日のアポ件数（リアルタイム）
- 営業マン別の稼働状況パネル（名前・現在地・次のアポまでの時間）
- 最近の変更ログ（直近5件）
- クイックアクション：「新規アポ登録」「営業マンに連絡」

Screen 2: **日ビュー** (主軸)
- 左側：営業マン一覧（スクロール可能、タップで選択）
- 中央：30分単位の時間軸（朝7:00〜夜22:00）
- アポタイル：顧客名・時間・場所を表示、タップで詳細表示
- ドラッグ&ドロップでアポを時間軸上で移動可能
- 色分け：【新規予約】青 / 【確定済み】緑 / 【キャンセル】赤 / 【変更待ち】黄

Screen 3: **週ビュー** (計画立案用)
- 月〜金（営業日のみ）を横軸に、営業マン4名を縦軸に
- 各営業マンの週間アポをセル状で表示（1日あたりのアポ件数を縮小版で表示）
- タップで日ビューへ遷移
- 「ラウンドロビン提案」ボタン：システムが1週間の最適分配案を提示

Screen 4: **月ビュー** (マネジメント用)
- カレンダー形式（31日グリッド）
- 各日のアポ件数・営業マン別の売上予測（KPI）を数字で表示
- 日付タップで日ビューへ
- 「月別レポート出力」ボタン：CSV / PDF ダウンロード

Screen 5: **アポ詳細 & 新規登録** (モーダル)
- 新規登録フォーム：
  - 顧客名（required）
  - 訪問予定日時（required）
  - 営業マン選択（required、またはラウンドロビン自動割り当て）
  - 想定時間（30分〜2時間、デフォルト60分）
  - 場所（テキスト自由入力）
  - 商品分類（ドロップダウン）
  - メモ（自由テキスト）
- 編集画面：上記項目 + 変更履歴表示 + キャンセルボタン
- 権限チェック：アポ入れ人のみ編集可、営業マンは閲覧のみ（ステータス更新は可）

追加画面（オプション）:
- Screen 6: **空き時間検出パネル** (営業マン個別)
  - 営業マンの今日の予定 + 移動時間を考慮した「次の空き時間」表示
  - 「ここに入れる」ボタン1クリックで新規アポ登録フォームへ

- [ ] **Step 3: ワイヤーフレームのアノテーション記入**

各要素に以下を記入：
- インタラクション（タップ / ドラッグ / スワイプ）
- バリデーション規則（必須項目、日時の制約）
- レスポンシブ対応（スマートフォン375px時の表示変更）
- アクセシビリティ（色覚多様性への対応、WCAG 2.1 AA準拠）

- [ ] **Step 4: スクリーンショット 5枚をPNG出力 & `docs/designs/` に保存**

ファイル名：
- `ui-01-dashboard.png`
- `ui-02-day-view.png`
- `ui-03-week-view.png`
- `ui-04-month-view.png`
- `ui-05-appointment-modal.png`

- [ ] **Step 5: Figma URL と設計ガイドを `docs/designs/ui-ux-wireframe-guide.md` に記録**

内容：
- Figma ファイルの URL（共有リンク）
- 各画面の目的・ユースケース
- コンポーネント一覧（入力フィールド・ボタン・モーダルなど）
- カラーパレット定義
- 実装時の注意点（レスポンシブ・アニメーション・パフォーマンス）

- [ ] **Step 6: デザインドキュメントをコミット**

```bash
git add docs/designs/ui-ux-wireframe-guide.md docs/designs/ui-*.png
git commit -m "design: create UI/UX wireframes for KAKEHASHI schedule system

- Dashboard, Day/Week/Month views, Appointment modal
- Responsive design for mobile/tablet/desktop
- Accessibility: WCAG 2.1 AA compliant

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

### Task 3: KAKEHASHI統合アーキテクチャ設計

**Files:**
- Create: `docs/designs/kakehashi-integration-architecture.md`
- Reference: `/home/user/kakei-apo/CLAUDE.md` (kakei-apo全体アーキテクチャ)

**Interfaces:**
- Consumes: kakei-apo 既存の GAS + Sheets アーキテクチャ、KAKEHASHI 内の❶入口・❂対面営業マン物件管理・❸保全CRM のインターフェース定義
- Produces: コンポーネント図・データフロー図・Entra ID 認証フロー図

- [ ] **Step 1: KAKEHASHI全体での位置づけを図式化**

以下の構図を Markdown + Mermaid ダイアグラムで表現：

```
❶入口(アポ生成)
    │ アポ確定
    ↓
つなぎ(予約表) ← [本システム: スケジュール管理]
    │ 訪問実行・キャンセル通知
    ↓
❂対面営業マン物件管理
    │ 申込み成立
    ↓
❸保全CRM
```

本システムの責務：
- 入力: ❶からのアポ確定情報（顧客名・訪問予定日時・営業マン指定または空きあり）
- 処理: 複数営業の予定調整、ラウンドロビン、リアルタイム可視化
- 出力: ❂へのステータス通知（訪問完了 / キャンセル / 延期）

- [ ] **Step 2: 現在の GAS 実装との機能互換性マトリックスを作成**

| 機能 | 現在のGAS実装 | 新システムでの実装 | 互換性 | 移行方法 |
|---|---|---|---|---|
| 日ビュー表示 | Sheetsベース | React Calendar | ○ | データ形式変換 |
| アポ新規登録 | GASフォーム | 新規モーダルUI | ○ | API化 |
| ドラッグ&ドロップ | 非対応 | React DnD | 新機能 | N/A |
| ラウンドロビン | スクリプト実行 | バックエンド自動 | ◎ | ロジック移植 |
| Slack通知 | Webhook | Slack API統合 | ○ | API v3へ移行 |
| 監査ログ | 限定的 | 完全JSONB記録 | ◎ | 新規実装 |

- [ ] **Step 3: 技術スタック選定の暫定案を記述**

推奨構成：
- **フロントエンド**: React 18 + Next.js 14（SSR対応）
  - スケジューリング: React Big Calendar + date-fns
  - UI Framework: Material-UI v5 または shadcn/ui
  - 状態管理: Zustand または Jotai（シンプルさ重視）
  - リアルタイム: Socket.io または native WebSocket

- **バックエンド**: Node.js 20 LTS + Express
  - ORM: Prisma（PostgreSQL）
  - 認証: passport.js + OAuth 2.0（Entra ID対応）
  - API: REST（OpenAPI 3.0仕様）
  - スケジューリング処理: node-cron または Bull（キュー）

- **データベース**: PostgreSQL 15+
  - テーブル: users, appointments, schedules, changelog, kpi_metrics
  - 全文検索: PostgreSQL FTS（顧客名検索）

- **インフラストラクチャ**: 未定（別途リスク分析で検討）
  - 候補: AWS (EC2/RDS/ElastiCache) / GCP (Cloud Run/CloudSQL) / オンプレ

- [ ] **Step 4: Entra ID 認証の統合フローを設計**

フロー：
1. ユーザーが アプリへアクセス
2. Entra ID ログイン画面へリダイレクト
3. Microsoft 認証 & トークン取得
4. アプリバックエンド: トークン検証 + ユーザーDB照合
5. JWT発行 & フロントエンドへ送信
6. 以後のリクエストに JWT を Authorization ヘッダーに含める

**注記**: kakei-apo は Entra ID 導入予定のため、この設計に準拠（2026-09-08 決裁）

- [ ] **Step 5: KAKEHASHI内の他システムとのインターフェース定義**

**❶入口(アポ生成) との接続**:
- 入力API: POST `/api/appointments` (❶からアポ情報を受信)
- 認証: Entra ID トークン + API キー
- ペイロード例:
  ```json
  {
    "customerId": "KM-00123",
    "customerName": "サンプル商店",
    "scheduledDateTime": "2026-09-28T14:00:00+09:00",
    "estimatedDuration": 60,
    "location": "沖縄県那覇市...",
    "source": "apogen_system"
  }
  ```

**❂対面営業マン物件管理 との接続**:
- 出力API: POST `/api/visits/completed` (アポ完了 / キャンセルを通知)
- ペイロード例:
  ```json
  {
    "appointmentId": "APO-20260928-001",
    "status": "completed",
    "actualDateTime": "2026-09-28T14:30:00+09:00",
    "visitOutcome": "商品説明実施"
  }
  ```

**❸保全CRM への情報フロー**: 
- 情報型（リアルタイムではなく集約型）
- 日次バッチで集計データを送信（KPI・達成状況など）

- [ ] **Step 6: アーキテクチャドキュメントを `docs/designs/kakehashi-integration-architecture.md` に記録**

内容：
- KAKEHASHI全体図（Mermaid）
- 本システムの責務範囲
- 現在のGAS実装との比較表
- 推奨技術スタック（根拠付き）
- Entra ID 認証フロー
- 他システムとのインターフェース定義（API仕様は Task 6 で詳細化）
- データマイグレーション方針（既存データから新システムへの移行）

- [ ] **Step 7: アーキテクチャドキュメントをコミット**

```bash
git add docs/designs/kakehashi-integration-architecture.md
git commit -m "docs: define KAKEHASHI integration architecture and interfaces

- Architecture diagram with KAKEHASHI ecosystem
- Interface contracts with apogen, visit tracking, hozen
- Recommended tech stack with Entra ID auth
- Data migration strategy from current GAS implementation

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

### Task 4: データモデル設計（ER図 + テーブル定義）

**Files:**
- Create: `docs/designs/data-model.md`
- Create: `docs/designs/data-model.mermaid` (ER図)
- Create: `kakei-apo/schema/schedule.sql` (DDL)

**Interfaces:**
- Consumes: Task 3 のアーキテクチャ定義、営業マン12名の運用要件
- Produces: PostgreSQL テーブル定義（Prisma schema + raw SQL）

- [ ] **Step 1: ER図を設計（Mermaid形式）**

主要テーブル：

```
users (営業マン・スタッフ・管理者)
├── id (PK)
├── entra_id (Entra ID ユーザーID)
├── name (名前)
├── email (メール)
├── role (admin / apo_staff / sales_rep)
├── sales_team (営業チーム名、オプション)
├── is_active (有効/無効フラグ)
└── created_at, updated_at

appointments (アポ)
├── id (PK)
├── customer_id (❶入口システムからのID)
├── customer_name (顧客名)
├── scheduled_datetime (訪問予定日時)
├── actual_datetime (実際の訪問時刻、NULL可)
├── estimated_duration (想定時間、分単位)
├── assigned_sales_rep_id (FK: users.id)
├── location (訪問場所テキスト)
├── status (scheduled / completed / cancelled / rescheduled)
├── source (apogen_system / manual_entry)
├── notes (メモ、テキスト自由)
├── created_by_id (FK: users.id、アポ入れ人)
├── updated_by_id (FK: users.id)
├── updated_at
└── cancelled_at

schedules (営業マン毎の可用性マスタ)
├── id (PK)
├── user_id (FK: users.id)
├── date (日付)
├── start_time (勤務開始時刻)
├── end_time (勤務終了時刻)
├── travel_time_buffer (移動時間バッファ、分単位)
├── break_periods (JSON: 休憩時間帯の配列)
└── is_available (この日が営業日か)

appointment_changes (変更履歴 / 監査ログ)
├── id (PK)
├── appointment_id (FK: appointments.id)
├── change_type (created / updated / cancelled)
├── old_values (JSONB: 変更前の値)
├── new_values (JSONB: 変更後の値)
├── changed_by_id (FK: users.id)
├── reason (変更理由テキスト、オプション)
├── changed_at (タイムスタンプ)

kpi_metrics (KPI・統計用)
├── id (PK)
├── date (日付)
├── user_id (FK: users.id)
├── appointments_count (その日のアポ件数)
├── completed_count (完了したアポ件数)
├── cancelled_count (キャンセルしたアポ件数)
├── avg_duration (平均訪問時間)
├── travel_distance (移動距離、km単位、オプション)
└── revenue_forecast (売上予測、オプション)

notifications (通知ログ)
├── id (PK)
├── user_id (FK: users.id)
├── type (slack / email / in_app)
├── message (本文)
├── sent_at (送信日時)
└── is_read (既読フラグ)
```

リレーション：
- users.id ← appointments.assigned_sales_rep_id (多対1)
- users.id ← appointments.created_by_id (多対1)
- appointments.id ← appointment_changes.appointment_id (1対多)
- users.id ← kpi_metrics.user_id (1対多)

- [ ] **Step 2: Prisma スキーマを作成 (`kakei-apo/prisma/schedule.prisma`)**

```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

model User {
  id              String   @id @default(cuid())
  entraId         String   @unique
  name            String
  email           String   @unique
  role            Role
  salesTeam       String?
  isActive        Boolean  @default(true)
  createdAt       DateTime @default(now())
  updatedAt       DateTime @updatedAt

  appointmentsAssigned     Appointment[]  @relation("assignedSalesRep")
  appointmentsCreated      Appointment[]  @relation("createdBy")
  appointmentsUpdated      Appointment[]  @relation("updatedBy")
  schedules                Schedule[]
  appointmentChanges       AppointmentChange[] @relation("changedBy")
  kpiMetrics               KpiMetric[]
  notifications            Notification[]

  @@index([entraId])
}

enum Role {
  ADMIN
  APO_STAFF
  SALES_REP
}

model Appointment {
  id                    String   @id @default(cuid())
  customerId            String
  customerName          String
  scheduledDatetime     DateTime
  actualDatetime        DateTime?
  estimatedDuration     Int      // 分単位
  assignedSalesRepId    String
  assignedSalesRep      User     @relation("assignedSalesRep", fields: [assignedSalesRepId], references: [id], onDelete: Restrict)
  location              String
  status                AppointmentStatus @default(SCHEDULED)
  source                String   // apogen_system / manual_entry
  notes                 String?
  createdById           String
  createdBy             User     @relation("createdBy", fields: [createdById], references: [id], onDelete: Restrict)
  updatedById           String
  updatedBy             User     @relation("updatedBy", fields: [updatedById], references: [id], onDelete: Restrict)
  updatedAt             DateTime @updatedAt
  createdAt             DateTime @default(now())
  cancelledAt           DateTime?

  changes               AppointmentChange[]

  @@index([scheduledDatetime])
  @@index([assignedSalesRepId])
  @@index([customerId])
}

enum AppointmentStatus {
  SCHEDULED
  COMPLETED
  CANCELLED
  RESCHEDULED
}

model AppointmentChange {
  id                String   @id @default(cuid())
  appointmentId     String
  appointment       Appointment @relation(fields: [appointmentId], references: [id], onDelete: Cascade)
  changeType        ChangeType
  oldValues         Json?    // JSONB
  newValues         Json?    // JSONB
  changedById       String
  changedBy         User     @relation("changedBy", fields: [changedById], references: [id], onDelete: Restrict)
  reason            String?
  changedAt         DateTime @default(now())

  @@index([appointmentId])
  @@index([changedAt])
}

enum ChangeType {
  CREATED
  UPDATED
  CANCELLED
}

model Schedule {
  id                String   @id @default(cuid())
  userId            String
  user              User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  date              DateTime @db.Date
  startTime         String   // HH:mm 形式（例: "07:00"）
  endTime           String   // HH:mm 形式（例: "22:00"）
  travelTimeBuffer  Int      // 分単位
  breakPeriods      Json?    // JSONB: [{startTime: "12:00", endTime: "13:00"}, ...]
  isAvailable       Boolean  @default(true)
  createdAt         DateTime @default(now())
  updatedAt         DateTime @updatedAt

  @@unique([userId, date])
  @@index([date])
}

model KpiMetric {
  id                String   @id @default(cuid())
  date              DateTime @db.Date
  userId            String
  user              User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  appointmentsCount Int      @default(0)
  completedCount    Int      @default(0)
  cancelledCount    Int      @default(0)
  avgDuration       Float?   // 分単位の平均
  travelDistance    Float?   // km単位
  revenueForecast   Float?   // 予測売上
  createdAt         DateTime @default(now())
  updatedAt         DateTime @updatedAt

  @@unique([userId, date])
  @@index([date])
}

model Notification {
  id          String   @id @default(cuid())
  userId      String
  user        User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  type        String   // slack / email / in_app
  message     String
  sentAt      DateTime @default(now())
  isRead      Boolean  @default(false)

  @@index([userId, sentAt])
}
```

- [ ] **Step 3: Raw SQL DDL を作成 (`kakei-apo/schema/schedule.sql`)**

```sql
-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create tables
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  entra_id VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) NOT NULL UNIQUE,
  role VARCHAR(50) NOT NULL CHECK (role IN ('ADMIN', 'APO_STAFF', 'SALES_REP')),
  sales_team VARCHAR(255),
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_entra_id ON users(entra_id);

-- appointments table
CREATE TABLE appointments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  customer_id VARCHAR(255) NOT NULL,
  customer_name VARCHAR(255) NOT NULL,
  scheduled_datetime TIMESTAMP NOT NULL,
  actual_datetime TIMESTAMP,
  estimated_duration INT NOT NULL,
  assigned_sales_rep_id UUID NOT NULL,
  location TEXT NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'SCHEDULED' CHECK (status IN ('SCHEDULED', 'COMPLETED', 'CANCELLED', 'RESCHEDULED')),
  source VARCHAR(50) NOT NULL,
  notes TEXT,
  created_by_id UUID NOT NULL,
  updated_by_id UUID NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  cancelled_at TIMESTAMP,
  FOREIGN KEY (assigned_sales_rep_id) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (created_by_id) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (updated_by_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_appointments_scheduled_datetime ON appointments(scheduled_datetime);
CREATE INDEX idx_appointments_assigned_sales_rep_id ON appointments(assigned_sales_rep_id);
CREATE INDEX idx_appointments_customer_id ON appointments(customer_id);

-- appointment_changes (audit log)
CREATE TABLE appointment_changes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  appointment_id UUID NOT NULL,
  change_type VARCHAR(50) NOT NULL CHECK (change_type IN ('CREATED', 'UPDATED', 'CANCELLED')),
  old_values JSONB,
  new_values JSONB,
  changed_by_id UUID NOT NULL,
  reason TEXT,
  changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
  FOREIGN KEY (changed_by_id) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_appointment_changes_appointment_id ON appointment_changes(appointment_id);
CREATE INDEX idx_appointment_changes_changed_at ON appointment_changes(changed_at);

-- schedules (営業マンの可用性)
CREATE TABLE schedules (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL,
  date DATE NOT NULL,
  start_time TIME NOT NULL,
  end_time TIME NOT NULL,
  travel_time_buffer INT NOT NULL,
  break_periods JSONB,
  is_available BOOLEAN DEFAULT true,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(user_id, date)
);

CREATE INDEX idx_schedules_date ON schedules(date);

-- kpi_metrics
CREATE TABLE kpi_metrics (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  date DATE NOT NULL,
  user_id UUID NOT NULL,
  appointments_count INT DEFAULT 0,
  completed_count INT DEFAULT 0,
  cancelled_count INT DEFAULT 0,
  avg_duration NUMERIC(5, 2),
  travel_distance NUMERIC(7, 2),
  revenue_forecast NUMERIC(10, 2),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  UNIQUE(user_id, date)
);

CREATE INDEX idx_kpi_metrics_date ON kpi_metrics(date);

-- notifications
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL,
  type VARCHAR(50) NOT NULL,
  message TEXT NOT NULL,
  sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  is_read BOOLEAN DEFAULT false,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_notifications_user_id_sent_at ON notifications(user_id, sent_at);
```

- [ ] **Step 4: ER図を Mermaid で出力 (`docs/designs/data-model.mermaid`)**

- [ ] **Step 5: データモデル説明書を `docs/designs/data-model.md` に記述**

内容：
- ER図（Mermaid）
- テーブル一覧（目的・主要フィールド）
- インデックス戦略（クエリパフォーマンス最適化）
- JSONB 型の活用（appointment_changes / break_periods）
- バックアップ・リカバリ方針

- [ ] **Step 6: スキーマファイルをコミット**

```bash
git add docs/designs/data-model.md docs/designs/data-model.mermaid
git add kakei-apo/schema/schedule.sql kakei-apo/prisma/schedule.prisma
git commit -m "docs: design PostgreSQL data model for schedule system

- ER diagram with 9 main tables
- Users, Appointments, Schedules, KPI metrics, Change logs
- Indexes for query performance
- JSONB for flexible audit trail and settings

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

### Task 5: 機能仕様書

**Files:**
- Create: `docs/designs/feature-specification.md`

**Interfaces:**
- Consumes: Task 2 のUI/UXワイヤーフレーム、Task 4 のデータモデル
- Produces: 10個の機能の詳細仕様（画面フロー・バリデーション・エラーハンドリング）

- [ ] **Step 1: 10個の主要機能を列挙**

1. **ダッシュボード表示**: 本日のアポ件数・営業マン稼働状況・最近の変更ログ
2. **日ビュー・週ビュー・月ビュー**: 複数営業のスケジュール可視化
3. **アポ新規作成**: フォーム入力 → バリデーション → DB保存 → 通知送信
4. **アポ編集・キャンセル**: 既存アポの更新 → 監査ログ記録 → 関係者通知
5. **空き時間自動検出**: 営業マンの移動時間・休憩を考慮した「次の空き時刻」表示
6. **ラウンドロビン**: システムが営業マン間の負荷を均等化し、アポ割り当てを自動提案
7. **権限管理**: アポ入れ人と営業マンの操作権限を分離
8. **KPI集計**: 日別・営業マン別のアポ件数・完了率・平均訪問時間をレポート出力
9. **イレギュラー対応**: キャンセル・延期時の自動通知（Slack + LINE）
10. **顧客管理**: アポ登録時の顧客名（単純テキスト）管理、❶入口システムとの連携

- [ ] **Step 2: 各機能の詳細仕様を作成**

**機能1: ダッシュボード表示**
- トリガー: アプリログイン直後
- 表示項目:
  - 本日のアポ件数（リアルタイム更新、1秒ごと）
  - 営業マン別の稼働パネル：名前・現在地（GPS取得は✕。手動入力のみ）・次のアポまでの時間・完了数
  - 最近の変更ログ：直近5件（「誰が・何を・いつ変更した」）
  - クイックアクション：「新規アポ登録」「営業マンに連絡」
- 権限：全員に表示
- API：GET `/api/dashboard/today` (リアルタイム WebSocket OR 1秒ポーリング)
- バリデーション：なし（読み取り専用）
- エラーハンドリング：API応答遅延時は「更新中...」表示

**機能2: 日ビュー・週ビュー・月ビュー**
- 日ビュー:
  - 左側：営業マン一覧（スクロール、タップで選択）
  - 中央：30分単位の時間軸（7:00〜22:00）、ドラッグ&ドロップでアポ移動
  - アポタイルの色分け：【新規】青 / 【確定】緑 / 【キャンセル】赤 / 【変更待ち】黄
  - API: GET `/api/appointments/by-date/:date` (営業マン別)
  - バリデーション: 過去日付はアポ追加不可、但し編集は可
- 週ビュー:
  - 月〜金（営業日のみ）× 営業マン4名の2次元グリッド
  - 各セルのアポ件数を数字表示、タップで日ビューへ遷移
  - 「ラウンドロビン提案」ボタン：1週間の最適分配案を表示
  - API: GET `/api/appointments/by-week/:year/:week`
- 月ビュー:
  - カレンダー形式（31日グリッド）
  - 各日のアポ件数・KPI数字表示
  - 日付タップで日ビューへ
  - API: GET `/api/appointments/by-month/:year/:month`
- 全ビューで：スマートフォン対応（375px以上）、タブレット（768px以上）、デスクトップ（1440px以上）

**機能3: アポ新規作成**
- トリガー：「新規アポ登録」ボタンまたは日ビューのドラッグ&ドロップ（開いた時間帯をタップ）
- フォーム入力フィールド:
  - 顧客名 (required, 最大100文字)
  - 訪問予定日時 (required, 過去日時は不可)
  - 営業マン選択 (required, または「ラウンドロビン自動割り当て」チェック)
  - 想定時間 (required, 30〜120分、デフォルト60分)
  - 場所 (required, 最大200文字)
  - 商品分類 (optional, ドロップダウン: 保険・融資・家計改善など)
  - メモ (optional, 最大500文字)
- バリデーション:
  - 顧客名: 空文字列は不可、30文字以上推奨（警告）
  - 日時: 過去は不可、営業時間（7:00〜22:00）内のみ
  - 営業マン: 選択した営業マンの同じ時刻に他のアポがないか確認（警告: 「この営業マンは14:00に他のアポがあります」）
  - 想定時間: 営業マンの勤務終了時刻を超えないか確認
- API: POST `/api/appointments` (JWT認証必須、アポ入れ人ロールのみ)
- リクエストボディ:
  ```json
  {
    "customerId": "KM-00123",
    "customerName": "サンプル商店",
    "scheduledDateTime": "2026-09-28T14:00:00+09:00",
    "estimatedDuration": 60,
    "assignedSalesRepId": "uuid-or-null",
    "location": "沖縄県那覇市中央",
    "category": "insurance",
    "notes": "初回訪問、スケジュール確認要"
  }
  ```
- レスポンス:
  ```json
  {
    "id": "APO-20260928-001",
    "status": "SCHEDULED",
    "createdAt": "2026-09-27T15:30:00Z",
    "message": "アポを登録しました"
  }
  ```
- エラーハンドリング:
  - バリデーション失敗 → 400 Bad Request + エラーメッセージ表示
  - 権限なし → 403 Forbidden
  - サーバーエラー → 500 + リトライボタン
- 登録後のアクション:
  - UI上で日ビューに追加（リアルタイム更新）
  - Slack 通知: 該当営業マンへ「新規アポが入りました」
  - LINE 通知: 営業マンのスマートフォンへ（営業マンの設定による）
  - 監査ログに記録（created）

（残り7個の機能も同様の詳細度で記述...）

- [ ] **Step 3: エラーケース・エッジケースを追記**

- アポ削除後に営業マンがアクセス → 「削除済みアポです」表示
- 営業マンが他のアポ入れ人のアポを編集しようとした → 「権限がありません」表示
- ラウンドロビン計算中に新規アポが追加 → 計算キューイング・完了後に提案更新
- オフライン時のアポ登録 → Service Worker キャッシュ、オンライン復帰時に同期

- [ ] **Step 4: 機能仕様書を `docs/designs/feature-specification.md` に記述**

構成：
- 機能一覧（優先度順）
- 各機能の詳細フロー（図: Mermaid sequence diagram）
- 画面遷移図（Mermaid state diagram）
- バリデーション規則表
- エラーハンドリング仕様
- パフォーマンス要件（「アポ登録から日ビュー表示まで 2 秒以内」等）

- [ ] **Step 5: 機能仕様書をコミット**

```bash
git add docs/designs/feature-specification.md
git commit -m "docs: write detailed feature specifications for 10 core functions

- Dashboard, multi-view calendar (day/week/month)
- Appointment CRUD with validation rules
- Auto-free-time detection, round-robin, permissions
- KPI aggregation, irregular handling, customer management

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

### Task 6: REST API 仕様設計

**Files:**
- Create: `docs/designs/api-specification.md`
- Create: `kakei-apo/src/api/openapi.yaml` (OpenAPI 3.0)

**Interfaces:**
- Consumes: Task 5 の機能仕様書
- Produces: API仕様（10エンドポイント）、OpenAPI仕様ファイル

- [ ] **Step 1: 主要エンドポイント 10個を列挙**

1. `GET /api/dashboard/today` - 本日のダッシュボード情報取得
2. `GET /api/appointments/by-date/:date` - 指定日のアポ一覧（営業マン別）
3. `GET /api/appointments/by-week/:year/:week` - 週単位のアポ一覧
4. `GET /api/appointments/by-month/:year/:month` - 月単位のアポ一覧
5. `POST /api/appointments` - アポ新規作成
6. `PUT /api/appointments/:id` - アポ編集
7. `DELETE /api/appointments/:id` - アポ削除（キャンセル）
8. `GET /api/appointments/:id/free-times` - 営業マンの次の空き時間検出
9. `POST /api/appointments/round-robin` - ラウンドロビン提案（1週間の最適分配）
10. `GET /api/analytics/kpi` - KPI集計データ取得

- [ ] **Step 2: 各エンドポイントの詳細仕様を記述**

**エンドポイント1: GET /api/dashboard/today**
- 認証: JWT + Entra ID
- レスポンス (200 OK):
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
        "name": "営業マン太郎",
        "nextAppointment": {
          "id": "APO-001",
          "time": "14:30",
          "customer": "サンプル商店",
          "location": "那覇市中央"
        },
        "timeToNext": 45,
        "completedToday": 3
      }
    ],
    "recentChanges": [
      {
        "appointmentId": "APO-001",
        "changedBy": "事務太郎",
        "changeType": "updated",
        "timestamp": "2026-09-28T13:45:00Z",
        "oldValue": {"status": "SCHEDULED"},
        "newValue": {"status": "COMPLETED"}
      }
    ]
  }
  ```
- エラー応答: 401 Unauthorized, 500 Internal Server Error
- キャッシュ戦略: 1秒ごと更新（WebSocket推奨、または ポーリング）

（残り9個のエンドポイントも同様の詳細度で記述...）

- [ ] **Step 3: OpenAPI 3.0 仕様ファイルを作成 (`kakei-apo/src/api/openapi.yaml`)**

```yaml
openapi: 3.0.0
info:
  title: KAKEHASHI Schedule Management API
  version: 1.0.0
  description: RESTful API for appointment scheduling within kakei-apo
servers:
  - url: https://api.kakei-apo.internal/v1
    description: Production
  - url: http://localhost:3000/api/v1
    description: Development

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
          format: uuid
        customerId:
          type: string
        customerName:
          type: string
        scheduledDateTime:
          type: string
          format: date-time
        actualDateTime:
          type: string
          format: date-time
          nullable: true
        estimatedDuration:
          type: integer
          description: Duration in minutes
        assignedSalesRepId:
          type: string
          format: uuid
        location:
          type: string
        status:
          type: string
          enum: [SCHEDULED, COMPLETED, CANCELLED, RESCHEDULED]
        source:
          type: string
        notes:
          type: string
          nullable: true
        createdAt:
          type: string
          format: date-time
        updatedAt:
          type: string
          format: date-time

paths:
  /dashboard/today:
    get:
      summary: Get today's dashboard
      operationId: getDashboardToday
      security:
        - bearerAuth: []
      responses:
        '200':
          description: Dashboard data
          content:
            application/json:
              schema:
                type: object
        '401':
          description: Unauthorized
        '500':
          description: Server error

  /appointments:
    post:
      summary: Create new appointment
      operationId: createAppointment
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                customerId:
                  type: string
                customerName:
                  type: string
                scheduledDateTime:
                  type: string
                  format: date-time
                estimatedDuration:
                  type: integer
                assignedSalesRepId:
                  type: string
                  format: uuid
                location:
                  type: string
                category:
                  type: string
                notes:
                  type: string
              required:
                - customerId
                - customerName
                - scheduledDateTime
                - estimatedDuration
                - location
      responses:
        '201':
          description: Appointment created
        '400':
          description: Validation error
        '401':
          description: Unauthorized
        '403':
          description: Forbidden (insufficient role)

  /appointments/{id}:
    get:
      summary: Get appointment by ID
      operationId: getAppointmentById
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      security:
        - bearerAuth: []
      responses:
        '200':
          description: Appointment details
        '404':
          description: Not found
    
    put:
      summary: Update appointment
      operationId: updateAppointment
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
      responses:
        '200':
          description: Appointment updated
        '400':
          description: Validation error
        '403':
          description: Forbidden
    
    delete:
      summary: Cancel appointment
      operationId: deleteAppointment
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      security:
        - bearerAuth: []
      responses:
        '204':
          description: Appointment cancelled
        '403':
          description: Forbidden
```

- [ ] **Step 4: 認証・エラーハンドリング・レート制限の仕様を記述**

認証:
- JWT トークン（Authorization: Bearer <token>）
- Entra ID OAuth 2.0フロー
- トークン有効期限: 1時間、リフレッシュトークン有効期限: 7日

エラーハンドリング:
- 400 Bad Request: バリデーション失敗（フィールド名 + エラーメッセージ）
- 401 Unauthorized: トークン無効 / 期限切れ
- 403 Forbidden: 権限不足
- 404 Not Found: リソース不存在
- 409 Conflict: アポが既に存在（重複登録防止）
- 500 Internal Server Error: サーバーエラー（エラーID付き）

レート制限:
- アポ入れ人: 100リクエスト/分
- 営業マン: 50リクエスト/分
- 管理者: 無制限

- [ ] **Step 5: API仕様書を `docs/designs/api-specification.md` に記述**

構成：
- エンドポイント一覧表
- 各エンドポイントの詳細（リクエスト・レスポンス・エラー）
- OpenAPI 3.0 仕様ファイル URL
- 認証フロー図
- エラーコード一覧
- レート制限ポリシー
- バージョニング戦略（v1, v2, ...）

- [ ] **Step 6: API仕様ファイルをコミット**

```bash
git add docs/designs/api-specification.md kakei-apo/src/api/openapi.yaml
git commit -m "docs: define REST API specification with 10 endpoints

- Dashboard, appointment CRUD, free-time detection, round-robin
- OpenAPI 3.0 specification with request/response schemas
- JWT authentication, error handling, rate limiting

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

### Task 7: 権限管理マトリックス

**Files:**
- Create: `docs/designs/permission-matrix.md`

**Interfaces:**
- Consumes: Task 5 の機能仕様書、kakei-apo の既存役割定義
- Produces: 3ロール × 10機能の権限マトリックス表

- [ ] **Step 1: 3つのロールを定義**

1. **ADMIN** (管理者): システム管理者・事務責任者
   - 権限: すべての操作（作成・編集・削除・キャンセル）、ユーザー管理、レポート出力
   - ユースケース: 事務所の室長・事務長

2. **APO_STAFF** (アポ入れ人): アポを登録・編集する事務スタッフ
   - 権限: アポの作成・編集・削除・キャンセル、営業マン選択、レポート参照
   - ユースケース: 事務所の電話受付者、アポ管理担当

3. **SALES_REP** (営業マン): 訪問実行者
   - 権限: 自分のアポを閲覧・ステータス更新（完了/キャンセル）のみ、他人のアポは参照のみ
   - ユースケース: 営業マン（訪問者）

- [ ] **Step 2: 権限マトリックス表を作成**

| 機能 | ADMIN | APO_STAFF | SALES_REP |
|---|---|---|---|
| ダッシュボード表示 | 全員分表示 | 全員分表示 | 自分のみ表示 |
| 日ビュー・週ビュー・月ビュー | 全員分表示 | 全員分表示 | 自分のみ表示 |
| アポ新規作成 | ○ | ○ | × |
| アポ編集（日時・場所） | ○ | ○ | × |
| アポ削除（キャンセル） | ○ | ○ | ○（自分のみ） |
| アポのステータス更新 | ○ | △（作成者のみ） | ○（自分のみ） |
| 空き時間自動検出 | 全員分 | 全員分 | 自分のみ |
| ラウンドロビン実行 | ○ | ○ | × |
| 権限管理（ユーザー追加・ロール変更） | ○ | × | × |
| KPI集計・レポート出力 | ○ | ○ | ×（個人売上は参照可） |

凡例: ○ = 可能、△ = 条件付き可能、× = 不可

- [ ] **Step 3: 詳細な権限ルールを記述**

**ルール1: アポの編集権限**
- ADMIN: すべてのアポを編集可
- APO_STAFF: 自分が作成したアポ、または「編集権限付与」されたアポのみ編集可
  - 例外: キャンセル理由の記録は、キャンセルした営業マンが記述可
- SALES_REP: 自分に割り当てられたアポのステータス（完了 / キャンセル）のみ更新可

**ルール2: 削除権限**
- ADMIN: すべてのアポを削除可（監査ログに記録）
- APO_STAFF: 自分が作成した未確定のアポのみ削除可（確定済み = 営業マンが見始めたら削除不可）
- SALES_REP: キャンセルのみ可、削除は不可（監査ログに「営業マン〇〇がキャンセル」と記録）

**ルール3: ユーザー管理**
- ADMIN のみがユーザー追加・ロール変更・無効化を実行可
- 変更履歴は監査ログに記録

**ルール4: レポート・分析**
- ADMIN: 全営業マンの売上・効率指標・キャンセル率を参照可
- APO_STAFF: 全営業マンの統計値（平均値・合計値）のみ参照可、個人名は非表示
- SALES_REP: 自分の個人売上・効率指標のみ参照可

**ルール5: 監査ログ**
- ADMIN: 全員のアクション履歴を参照可
- APO_STAFF: 自分のアクション履歴のみ参照可
- SALES_REP: 自分のアクション履歴のみ参照可

- [ ] **Step 4: API レベルでの権限チェック実装方針を記述**

各API呼び出し時に、以下の順序で権限チェック：
1. JWT トークン検証（有効期限・署名）
2. Entra ID トークン検証
3. ロールベースのアクセス制御（RBAC）
4. リソースベースのアクセス制御（RBAC）例: 「このアポの作成者か？」

実装パターン：
```typescript
// Express middleware例
async function checkAppointmentEditPermission(req, res, next) {
  const { appointmentId } = req.params;
  const userId = req.user.id;
  const userRole = req.user.role;
  
  const appointment = await Appointment.findById(appointmentId);
  
  if (userRole === 'ADMIN') {
    return next(); // OK
  }
  
  if (userRole === 'APO_STAFF') {
    if (appointment.createdById === userId) {
      return next(); // OK
    }
  }
  
  // Forbidden
  return res.status(403).json({ error: 'Permission denied' });
}
```

- [ ] **Step 5: 権限マトリックスを `docs/designs/permission-matrix.md` に記述**

構成：
- ロール定義（ADMIN, APO_STAFF, SALES_REP）
- 権限マトリックス表（機能 × ロール）
- 詳細ルール（編集・削除・ユーザー管理・レポート・監査ログ）
- API レベルでの実装方針
- 権限昇格（SALES_REP → APO_STAFF への昇進時の手順）

- [ ] **Step 6: 権限マトリックスをコミット**

```bash
git add docs/designs/permission-matrix.md
git commit -m "docs: define role-based access control (RBAC) matrix

- 3 roles: ADMIN, APO_STAFF, SALES_REP
- Permission matrix: 10 features × 3 roles
- Detailed rules for edit, delete, audit log access
- API-level implementation patterns

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

### Task 8: セキュリティ・ガバナンス設計

**Files:**
- Create: `docs/designs/security-governance.md`

**Interfaces:**
- Consumes: CLAUDE.md（kakei-apo の「社内限定」ポリシー）、Task 7 の権限管理
- Produces: 認証・認可・暗号化・監査・バックアップ・インシデント対応の仕様

- [ ] **Step 1: 認証・認可設計**

**認証: Entra ID + OAuth 2.0**
- フロー: ユーザーがアプリにアクセス → Entra ID ログイン画面へリダイレクト → Microsoft 認証 → 認可コード取得 → アプリバックエンド: トークン交換 → JWT発行
- JWT: RS256署名、1時間有効期限、リフレッシュトークン7日有効期限
- リフレッシュ戦略: クライアント側で有効期限 5分前にリフレッシュトークン使用

**認可: RBAC + RBAC (リソースベース)**
- RBAC: ロール（ADMIN / APO_STAFF / SALES_REP）ごとの操作権限
- リソースベース: 「このアポの作成者か」「このアポの割り当て営業マンか」を確認
- 実装: API ミドルウェアで各エンドポイントの前に権限チェック

- [ ] **Step 2: データ暗号化設計**

**転送中の暗号化**:
- HTTPS/TLS 1.3 必須（HTTP は不可）
- API エンドポイント: すべて HTTPS のみ
- WebSocket: WSS (WebSocket Secure) のみ使用

**保存時の暗号化**:
- 顧客名: オプション（PII非該当のため必須でない）
- ログイン履歴: 非暗号化（監査用）
- 監査ログ（appointment_changes）: オプション（社内限定のため必須でない）
- バックアップ: ディスク全体の AES-256 暗号化

**キー管理**:
- Entra ID 管理下（Microsoft Key Vault または AWS KMS）
- キーローテーション: 年1回以上

- [ ] **Step 3: 監査・ログ設計**

**ログ対象**:
- アポ作成・編集・削除: 誰が・何を・いつ変更した（old_values + new_values）
- ログイン・ログアウト: ユーザー・時刻・IPアドレス
- エラー: エラー内容・スタックトレース（ユーザーには非表示）
- 権限チェック失敗: 誰が・何を・いつ試みたか（セキュリティインシデント検知）

**ログ保持**:
- 操作ログ: 3年間保持（法的要件対応）
- エラーログ: 1年間保持
- アクセスログ: 3ヶ月保持

**ログ保護**:
- ログは改ざん防止（append-only、日付バージョニング）
- 定期的なログ分析（異常なアクセスパターン検知）

- [ ] **Step 4: インシデント対応方針**

**検知**:
- 異常なログイン試行（同一ユーザーが短時間に複数失敗）
- 権限昇格試行（SALES_REP が ADMIN 機能にアクセス）
- データ漏洩（大量のダウンロード、夜間アクセス）

**対応**:
1. アラート発出（管理者への通知）
2. ユーザーセッション強制終了（重大度が高い場合）
3. 一時的なアクセス制限（再度ログイン）
4. インシデント記録（事後検証用）

**エスカレーション**:
- レベル1: システム内アラート（管理者がダッシュボードで確認）
- レベル2: メール通知（サブジェクト: 「セキュリティアラート」）
- レベル3: 電話通知（被害可能性が高い場合）

- [ ] **Step 5: バックアップ・リカバリ方針**

**バックアップ頻度**:
- フル: 週1回（日曜深夜）
- 増分: 毎日（深夜 2:00）

**バックアップ保存**:
- 複数のリージョン（ローカル + 遠隔）
- 3世代保持（最古は 30日前）

**リカバリRPO/RTO**:
- RTO (復旧目標時間): 4時間以内
- RPO (復旧目標データ量): 1日（最新バックアップ時点まで）

**リカバリ手順**:
1. インシデント検知
2. リカバリ可能性の確認（バックアップの完全性チェック）
3. リカバリ実行（テスト環境で事前検証）
4. 本番環境へ切り替え
5. 差分データの再入力（手動）

- [ ] **Step 6: GDPR・個人情報保護対応**

**個人情報**:
- 本システムが扱う個人情報: 営業マンのメールアドレス（Entra ID から取得）
- 扱わない個人情報: 顧客の電話番号・住所・生年月日（❶入口システムで管理）

**GDPR対応**:
- 個人情報削除要求: ユーザー削除時に、ログイン履歴・アクション履歴を匿名化
- 「自分のアクション履歴を CSV ダウンロード」機能（アクセス権付与）
- 退職者のデータ削除: 離職日から 30日後に自動削除予定

- [ ] **Step 7: セキュリティガバナンスドキュメントを記述**

`docs/designs/security-governance.md` に以下の内容を記述:
- 認証・認可アーキテクチャ図
- データ分類（PII / 非PII）
- 暗号化ポリシー（転送 / 保存）
- キー管理方針
- 監査ログ仕様（対象・保持・保護）
- インシデント対応フロー
- バックアップ・リカバリ方針
- GDPR・個人情報保護チェックリスト

- [ ] **Step 8: セキュリティドキュメントをコミット**

```bash
git add docs/designs/security-governance.md
git commit -m "docs: design security and governance framework

- Entra ID + OAuth 2.0 authentication
- RBAC and resource-based access control
- TLS 1.3 for transport, AES-256 for storage
- Comprehensive audit logging and retention
- Incident response and backup/recovery procedures
- GDPR compliance measures

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"
```

---

## フェーズ2（10月3日〜10月10日）: ドキュメント統合・実装計画フェーズ

### Task 9: 技術スタック選定

**Files:**
- Create: `docs/designs/tech-stack-selection.md`

**Interfaces:**
- Consumes: Task 3 のアーキテクチャ設計、Task 4 のデータモデル
- Produces: フロントエンド・バックエンド・インフラの技術スタック選定根拠

（実装計画内容はTask 9〜16で詳細化）

---

### Task 10-16: 実装ロードマップ、人員配置、予算見積もり、リスク分析、統合ドキュメント作成

（フェーズ1完了後、フェーズ2へ移行）

---

## 完了判定基準

フェーズ1（分析・設計）の完了定義：
- [ ] Task 1-8 がすべて完了
- [ ] docs/designs/ 配下に8個のMarkdownファイル生成
- [ ] Figma ワイヤーフレーム完成
- [ ] 全ファイルが git commit で記録

フェーズ2（実装計画）の完了定義：
- [ ] Task 9-15 がすべて完了
- [ ] docs/designs/ 配下に統合 Markdown版 + Google Docs版 生成
- [ ] docs/designs/completion-checklist.md で最終チェック実施
- [ ] 10月10日 23:59 までに完成

---

## 重要な注意事項

1. **KAKEHASHI統合の最優先性**: このシステムは単体アプリではなく、enLife (kakei-apo) 内のコンポーネント。既存の GAS 実装の「良さ」を保持しつつ、Node.js 移設に対応する設計であること。

2. **営業マン12名向けの要件の維持**: 市場調査の結果（HubSpot + Calendly が理想）を参考にしつつ、営業マン12名の要件（日/週/月表示、空き時間検出、ラウンドロビン、権限分離）をすべて実装すること。

3. **社内限定の厳守**: kakei-apo は PRIVATE リポジトリ。顧客個人情報をコミットしない。スタッフ名は実名可（デモファイルを除く）。

4. **Entra ID 認証対応**: GAS → Node.js 移設時に、Entra ID 認証へ移行することを念頭に、設計・実装時点で OAuth 2.0 対応を前提とすること。

5. **監査ログの完全性**: すべての変更（作成・編集・削除）を監査ログに記録。誰が・何を・いつ変更したか、old_values + new_values で完全に追跡可能にすること。

