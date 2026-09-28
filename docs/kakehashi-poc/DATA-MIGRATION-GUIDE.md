# データマイグレーション・統合ガイド
> **既存GAS Sheets → PostgreSQL への移行手順**

**目的**: 現在のGAS実装で蓄積されたアポイントメント履歴・営業マン情報を、新しいPostgreSQL環境へシームレスに移行  
**対象期間**: 過去3年間（2023年10月 ～ 2026年10月）  
**実行予定日**: 2026-10-08（本番データ最終移行）  

---

## 📊 移行対象データ

### ❶ 営業マンマスタ（users テーブル）

**現在のGAS Sheets構成**:
```
rep-001 | 営業太郎 | rep-001@company.onmicrosoft.com | SALES_REP
rep-002 | 営業二郎 | rep-002@company.onmicrosoft.com | SALES_REP
...
rep-012 | 営業花子 | rep-012@company.onmicrosoft.com | SALES_REP
```

**移行先（PostgreSQL users テーブル）**:
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  entra_id VARCHAR(255) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(255) NOT NULL,
  role VARCHAR(50) NOT NULL,  -- SALES_REP, APO_STAFF, ADMIN
  timezone VARCHAR(100) DEFAULT 'Asia/Tokyo',
  working_hours_start TIME DEFAULT '09:00:00',
  working_hours_end TIME DEFAULT '18:00:00',
  break_time_start TIME DEFAULT '12:00:00',
  break_time_end TIME DEFAULT '13:00:00',
  travel_time_buffer INT DEFAULT 30,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

**移行ロジック**:
- GAS内の `rep-NNN` ID → Entra ID の UUID に変換（マッピングテーブル使用）
- 時間帯設定（営業時間・休憩時間）は固定値で初期化（後で個別調整可能）
- 全ユーザーを `is_active = true` で初期化

**検証**:
- 営業マン12名が全員移行されたか（COUNT = 12）
- メールアドレス重複がないか
- Entra IDが正しくマッピングされたか

---

### ❷ アポイントメント履歴（appointments テーブル）

**現在のGAS Sheets構成**:
```
| 日付 | 時間 | 顧客名 | 営業マン | ステータス | 備考 |
| 2026-10-01 | 14:00 | 商店A | rep-001 | 完了 | 契約成立 |
| 2026-10-02 | 10:00 | 企業B | rep-003 | キャンセル | 顧客都合 |
```

**移行先（PostgreSQL appointments テーブル）**:
```sql
CREATE TABLE appointments (
  id VARCHAR(50) PRIMARY KEY,  -- APO-YYYYMMDD-NNN
  customer_id VARCHAR(255),
  customer_name VARCHAR(255) NOT NULL,
  scheduled_datetime TIMESTAMP NOT NULL,
  actual_datetime TIMESTAMP,
  estimated_duration INT NOT NULL,
  actual_duration INT,
  location VARCHAR(500),
  source VARCHAR(100),  -- apogen_system, manual, etc
  status VARCHAR(50),  -- SCHEDULED, COMPLETED, CANCELLED
  assigned_sales_rep_id UUID REFERENCES users(id),
  created_by UUID REFERENCES users(id),
  cancelled_at TIMESTAMP,
  cancel_reason VARCHAR(500),
  notes TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_appointments_sales_rep ON appointments(assigned_sales_rep_id);
CREATE INDEX idx_appointments_datetime ON appointments(scheduled_datetime);
CREATE INDEX idx_appointments_status ON appointments(status);
```

**移行ロジック**:
1. GASシートから日付・時間・顧客名・営業マン・ステータスを抽出
2. 日付+順序番号 → `APO-YYYYMMDD-NNN` に変換
3. 営業マンID (`rep-NNN`) → PostgreSQL users.id (UUID) に変換
4. 所要時間がない場合 → デフォルト60分
5. キャンセル情報がある場合 → cancel_reason に格納、cancelled_at に時刻設定

**データ品質チェック**:
```
✓ 総レコード数：GAS = PostgreSQL
✓ 営業マン別の件数：一致確認
✓ ステータス分布：COMPLETED / CANCELLED / SCHEDULED の比率が合理的か
✓ 日付の範囲：2023年10月 ～ 2026年10月の範囲内か
✓ 営業マンIDのマッピング：NULLがないか、無効なIDがないか
```

---

### ❸ 監査ログ（変更履歴）の初期化

**既存GAS**:
- 監査ログが限定的（ユーザー操作の完全な履歴がない）

**新システムへの対応**:
```sql
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  appointment_id VARCHAR(50) REFERENCES appointments(id),
  operation VARCHAR(50),  -- CREATE, UPDATE, DELETE, CANCEL
  changed_by UUID REFERENCES users(id),
  changed_fields JSONB,
  previous_values JSONB,
  new_values JSONB,
  changed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_appointment ON audit_logs(appointment_id);
CREATE INDEX idx_audit_logs_date ON audit_logs(changed_at);
```

**マイグレーション時の処理**:
- 既存GASデータは `operation='MIGRATED'`で1件のログを作成
- `changed_by`は `(SELECT id FROM users WHERE name='System')` 
- `previous_values`は空、`new_values`は移行後の最終値

---

## 🔄 移行手順（ステップバイステップ）

### Phase 1: データ抽出・検証（2026-09-29）

#### Step 1.1: GASシートから JSON にエクスポート

**実行者**: データチーム  
**所要時間**: 30分

```bash
# Google Sheets APIを使用（gcloud auth でセッション確立済みの前提）

# users シート抽出
gcloud sheets values get "スケジュール管理" "営業マスタ" \
  --output=json > /tmp/users.json

# appointments シート抽出（過去3年分）
gcloud sheets values get "スケジュール管理" "アポ履歴" \
  --output=json > /tmp/appointments.json
```

**出力形式**:
```json
{
  "users": [
    {"id": "rep-001", "name": "営業太郎", "email": "...", ...},
    ...
  ],
  "appointments": [
    {"date": "2026-10-01", "time": "14:00", "customer": "商店A", ...},
    ...
  ]
}
```

#### Step 1.2: JSON → CSV に変換・クリーニング

**実行者**: エンジニア  
**所要時間**: 1時間

```bash
python3 scripts/migration/transform_gas_to_csv.py \
  --input /tmp/users.json \
  --output /tmp/users_clean.csv \
  --type users

python3 scripts/migration/transform_gas_to_csv.py \
  --input /tmp/appointments.json \
  --output /tmp/appointments_clean.csv \
  --type appointments
```

**クリーニング内容**:
- 空行・ヘッダー行の削除
- 営業マンID形式の正規化（`rep-001` → `rep-001-uuid`へのマッピングテーブル作成）
- 日時形式の統一（ISO 8601）
- 空白文字のトリミング
- 重複行の検出・削除

#### Step 1.3: CSV バリデーション

**実行者**: QA  
**所要時間**: 1時間

```bash
python3 scripts/migration/validate_migration_data.py \
  --users /tmp/users_clean.csv \
  --appointments /tmp/appointments_clean.csv \
  --output /tmp/validation_report.json
```

**バリデーション項目**:
```
✓ users.csv
  - 行数が12であるか（営業マン全員）
  - メールアドレスが重複していないか
  - 必須フィールド（id, name, email）が全て埋まっているか

✓ appointments.csv
  - 日付形式が正しいか（YYYY-MM-DD）
  - 時間形式が正しいか（HH:MM）
  - 営業マンIDが users.csv に存在するか
  - ステータスが (COMPLETED | CANCELLED | SCHEDULED) に属するか
  - 金額フィールドが数値か
```

**結果サンプル**:
```json
{
  "validation_passed": true,
  "summary": {
    "users_total": 12,
    "appointments_total": 1847,
    "date_range": "2023-10-01 to 2026-10-15",
    "errors": [],
    "warnings": ["rep-007 が 2025-06-01 ～ 2025-06-30 の期間データが0件"]
  }
}
```

---

### Phase 2: テスト環境への移行（2026-09-30）

#### Step 2.1: PostgreSQL テスト環境へのロード

**実行者**: インフラ  
**所要時間**: 30分

```bash
# テスト用RDS接続
export PGPASSWORD=$TEST_DB_PASSWORD
psql -h test-rds.example.com -U postgres -d kakehashi_test \
  -f scripts/migration/01_init_schema.sql

# users ロード
\COPY users(id, entra_id, email, name, role, created_at) \
  FROM '/tmp/users_clean.csv' \
  WITH (FORMAT csv, HEADER true, NULL 'NULL');

# appointments ロード
\COPY appointments(...) FROM '/tmp/appointments_clean.csv' \
  WITH (FORMAT csv, HEADER true, NULL 'NULL');
```

#### Step 2.2: データ品質テスト（テスト環境）

**実行者**: QA  
**所要時間**: 2時間

```bash
pytest scripts/migration/test_migration.py -v --tb=short

# テスト内容:
# - users テーブル行数が 12 か
# - appointments テーブル行数が 1847 か
# - 全ユーザーのアポ件数が合計 1847 か
# - 各営業マン別の件数分布が合理的か
# - ステータス別分布 (COMPLETED: 90%, CANCELLED: 5%, SCHEDULED: 5%)
# - 日付順序が正しいか
```

#### Step 2.3: API経由でのデータ取得テスト

**実行者**: QA  
**所要時間**: 1時間

```bash
# テスト環境のAPI (localhost:3000) に対して検証

curl -X GET "http://localhost:3000/api/v1/appointments?limit=10" \
  -H "Authorization: Bearer $TEST_JWT"

# レスポンス確認:
# - 件数: 10件
# - ステータス: 200 OK
# - 日付ソート: 新順（降順）
# - 各フィールドの型が正しいか

curl -X GET "http://localhost:3000/api/v1/sales-reps" \
  -H "Authorization: Bearer $TEST_JWT"

# 営業マン12名が返されるか
```

---

### Phase 3: 本番環境への移行（2026-10-08 早朝）

#### Step 3.1: 本番RDSの最終準備

**実行者**: インフラ  
**所要時間**: 1時間

```bash
# 本番RDSへのスナップショット・バックアップ確認
aws rds describe-db-snapshots \
  --db-instance-identifier kakehashi-prod-rds \
  --region ap-northeast-1

# 最新バックアップから自動復旧テスト実施
# (テスト用RDSインスタンスを一時的に復旧して検証)
```

#### Step 3.2: 本番RDSへのデータロード

**実行者**: インフラ  
**所要時間**: 1時間

```bash
# メンテナンスウィンドウ (2026-10-08 03:00-04:00 JST)
# サービス停止後に実行

export PGPASSWORD=$PROD_DB_PASSWORD
psql -h kakehashi-prod-rds.region.rds.amazonaws.com \
  -U postgres \
  -d kakehashi_prod \
  -f scripts/migration/01_init_schema.sql

# users ロード
\COPY users(...) FROM s3://kakehashi-migrations/users_final.csv \
  WITH (FORMAT csv, HEADER true, NULL 'NULL');

# appointments ロード
\COPY appointments(...) FROM s3://kakehashi-migrations/appointments_final.csv \
  WITH (FORMAT csv, HEADER true, NULL 'NULL');

# ログイン情報の最終同期（Entra IDから）
python3 scripts/migration/sync_entra_id_to_postgres.py \
  --tenant-id $ENTRA_TENANT_ID \
  --client-id $ENTRA_CLIENT_ID \
  --client-secret $ENTRA_CLIENT_SECRET
```

#### Step 3.3: 本番データの検証

**実行者**: QA  
**所要時間**: 30分

```bash
# 本番環境 API に対して同じテストスイートを実行
pytest scripts/migration/test_migration.py \
  --env=production \
  -v --tb=short

# サービス稼働確認
curl -X GET "https://kakehashi-api.example.com/api/v1/health" \
  --insecure  # 自己署名証明書の場合
```

#### Step 3.4: ロールバック手順の確認

**実行者**: 全員  
**所要時間**: 10分

```bash
# ロールバック時の対応手順を事前に確認

# ケース1: マイグレーションエラーの場合
# → RDSをスナップショットから復旧（所要時間: 10分）
# → API再起動
# → Slack通知

# ケース2: API起動エラーの場合
# → テスト環境へ一時的にトラフィック切り替え
# → 原因調査

# ケース3: データ品質問題の場合
# → 本番移行を延期（2026-10-09再実行）
# → テスト環境でのクリーニング再実施
```

---

## ✅ マイグレーション完了チェックリスト

```
本番移行前（2026-10-07まで）
- [ ] GASシートから全データをJSON形式でエクスポート
- [ ] JSONを CSV にクリーニング・変換
- [ ] バリデーションレポートで0エラー確認
- [ ] テスト環境への移行成功
- [ ] API経由でのデータ取得テスト合格
- [ ] QAの署名

本番移行直前（2026-10-08 03:00）
- [ ] 本番RDSバックアップ確認
- [ ] APIサービスを停止
- [ ] 本番RDSへのデータロード実行
- [ ] Entra ID同期実行
- [ ] ロールバック手順確認済み

本番移行後（2026-10-08 06:00）
- [ ] APIサービス再起動
- [ ] ヘルスチェック合格（HTTP 200）
- [ ] 営業マン12名でのログイン確認
- [ ] 過去データが表示されることを確認
- [ ] Slack通知「本番データ移行完了」
- [ ] インシデント対応チーム待機
```

---

## 📊 データサイズの見積もり

| テーブル | 行数 | 推定容量 |
|---|---|---|
| users | 12 | < 1 KB |
| appointments | 1,847 | ~5 MB |
| audit_logs | 10,000（初期） | ~50 MB |
| **合計** | **~11,859** | **~55 MB** |

**RDS db.t3.medium の ストレージ**: 20 GB（十分）  
**バックアップ容量**: 60 GB（7日間保持、RAIDストレージ）

---

## 🆘 トラブルシューティング

### Q1: GASシートから抽出したJSONが不正な形式

**原因**: Google Sheets APIの出力形式が想定と異なる  
**対策**:
```bash
# JSONの構造を確認
cat /tmp/users.json | jq . | head -50

# 形式が異なる場合は scripts/migration/ 内の変換スクリプトを調整
```

### Q2: 営業マンIDのマッピングが失敗

**原因**: Entra ID の UUID取得に失敗 / 「rep-001」がEntra IDに存在しない  
**対策**:
```bash
# Entra ID内のユーザー確認
az ad user list --filter "startsWith(userPrincipalName, 'rep-')" \
  --query "[].{id: id, upn: userPrincipalName}"

# マッピングテーブルの手動作成
# docs/migration/rep-entra-id-mapping.csv を編集
```

### Q3: 本番ロード時に「Unique constraint violation」エラー

**原因**: 既存本番DBに同じメールアドレスが存在  
**対策**:
```bash
# 本番DBで既存ユーザーを確認
SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1;

# 重複を削除または名前を変更
UPDATE users SET email = email || '_old' 
WHERE email IN (...重複メール...);
```

---

## 📞 サポート連絡先

- **データチーム**: 担当者
- **インフラ**: AWS RDS管理者
- **QA**: テスト責任者
- **緊急対応**: 小柳さん（最終判断）

