# 本番環境検証ガイド

**対象**: KAKEHASHI Phase 1 本番環境  
**前提**: AWS / Entra ID / Terraform セットアップ完了  
**所要時間**: 30 分

---

## ステップ 1: インフラストラクチャ状態確認

### AWS リソース確認

#### EC2 インスタンス
```bash
aws ec2 describe-instances \
  --region ap-northeast-1 \
  --filters "Name=tag:Name,Values=kakehashi-apo-instance" \
  --query 'Reservations[0].Instances[0].[PublicIpAddress,InstanceType,State.Name]'

# 出力例:
# [
#   "54.123.45.67",
#   "t3.large",
#   "running"
# ]
```

**期待値**:
- ✅ State: `running`
- ✅ InstanceType: `t3.large`
- ✅ PublicIpAddress: 割り当て済み

#### RDS インスタンス
```bash
aws rds describe-db-instances \
  --region ap-northeast-1 \
  --query 'DBInstances[0].[Engine,DBInstanceClass,DBInstanceStatus]'

# 出力例:
# [
#   "postgres",
#   "db.t3.medium",
#   "available"
# ]
```

**期待値**:
- ✅ Engine: `postgres`
- ✅ DBInstanceStatus: `available`
- ✅ DBInstanceClass: `db.t3.medium`

#### VPC・セキュリティグループ
```bash
aws ec2 describe-security-groups \
  --region ap-northeast-1 \
  --filters "Name=group-name,Values=kakehashi-sg" \
  --query 'SecurityGroups[0].[IpPermissions[*].[FromPort,ToPort,IpProtocol]]'

# 出力例:
# [
#   [[80, 80, "tcp"], [443, 443, "tcp"], [3000, 3000, "tcp"], [5432, 5432, "tcp"]]
# ]
```

**期待値**:
- ✅ Port 80 (HTTP) 許可
- ✅ Port 443 (HTTPS) 許可
- ✅ Port 3000 (Backend API) 許可
- ✅ Port 5432 (PostgreSQL) 許可

---

## ステップ 2: EC2 インスタンス接続テスト

### SSH 接続
```bash
# EC2 IP 取得
EC2_IP=$(aws ec2 describe-instances \
  --region ap-northeast-1 \
  --filters "Name=tag:Name,Values=kakehashi-apo-instance" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

# SSH 接続
ssh -i ~/.ssh/kakehashi-poc.pem ec2-user@$EC2_IP

# ✅ 成功: EC2 コマンドラインにアクセス
```

### Docker 状態確認
```bash
# EC2 内で実行
docker ps

# 出力例:
# CONTAINER ID   IMAGE     COMMAND                  STATUS
# abc123...      node:20   "node index.js"          Up 10 minutes
# def456...      nginx     "nginx -g 'daemon off'" Up 10 minutes
# ghi789...      postgres  "postgres"               Up 10 minutes
```

**期待値**:
- ✅ Backend (Node.js) コンテナ: `Up`
- ✅ Frontend (Nginx) コンテナ: `Up`
- ✅ Database (PostgreSQL) コンテナ: `Up`

### ヘルスチェック
```bash
# EC2 内で実行
docker-compose ps

# 出力例:
# NAME              COMMAND                STATUS
# kakehashi_backend "node src/index.js"   Up 10 minutes (healthy)
# kakehashi_frontend "nginx..."           Up 10 minutes (healthy)
# kakehashi_db      "postgres..."        Up 10 minutes (healthy)
```

**期待値**: すべてのコンテナが `healthy` ステータス

---

## ステップ 3: API ヘルスチェック

### Backend ヘルスチェックエンドポイント
```bash
# 外部から確認
curl -s http://$EC2_IP/health | jq .

# 出力例:
# {
#   "status": "OK",
#   "timestamp": "2026-09-30T12:34:56Z"
# }
```

**期待値**:
- ✅ HTTP Status: 200
- ✅ Response: `{"status": "OK"}`

### Frontend ヘルスチェック
```bash
curl -s -o /dev/null -w "%{http_code}" http://$EC2_IP/health

# 出力例:
# 200
```

**期待値**: HTTP Status 200

---

## ステップ 4: RDS データベース接続テスト

### PostgreSQL 接続確認
```bash
# RDS エンドポイント取得
DB_ENDPOINT=$(aws rds describe-db-instances \
  --region ap-northeast-1 \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

# 接続テスト
pg_isready -h $DB_ENDPOINT -U kakehashi_admin

# 出力例:
# kakehashi-db.xxxxx.ap-northeast-1.rds.amazonaws.com:5432 - accepting connections
```

**期待値**: `accepting connections`

### DB スキーマ確認
```bash
psql -h $DB_ENDPOINT \
     -U kakehashi_admin \
     -d kakehashi_prod \
     -c "\dt"

# 出力例:
#           List of relations
# Schema | Name | Type  | Owner
# --------+------+-------+----------------
# public | users | table | kakehashi_admin
# public | appointments | table | kakehashi_admin
```

**期待値**:
- ✅ `users` テーブル存在
- ✅ `appointments` テーブル存在

### DB レコード確認
```bash
psql -h $DB_ENDPOINT \
     -U kakehashi_admin \
     -d kakehashi_prod \
     -c "SELECT COUNT(*) FROM users;"

# 出力例:
#  count
# -------
#     12
# (1 row)
```

**期待値**: テストユーザー 12 名分が登録されている

---

## ステップ 5: OAuth 2.0 Entra ID ログインテスト

### ブラウザからのログインテスト
```bash
# ブラウザで開く
open http://$EC2_IP/auth/login

# または

curl -L http://$EC2_IP/auth/login
```

### ログイン手順
1. **Entra ID ログインページ** に遷移
2. **テストユーザー認証情報** を入力
   ```
   ユーザー: rep-001@company.onmicrosoft.com
   パスワード: [テストユーザーパスワード]
   ```
3. **MFA** (有効な場合は対応)
4. **同意** 画面で承認

**期待値**:
- ✅ Entra ID ログインページ表示
- ✅ 認証成功後、カレンダーページにリダイレクト
- ✅ JWT トークン（`Authorization` ヘッダー）発行

### JWT トークン確認
```bash
# ブラウザ開発者ツール → Application → Local Storage
# キー: `kakehashi_token`
# 値: `eyJhbGciOiJSUzI1NiIs...` (JWT トークン)

# JWT デコード（ローカル）
curl -s http://$EC2_IP/auth/verify \
  -H "Authorization: Bearer [JWT_TOKEN]" | jq .

# 出力例:
# {
#   "sub": "user-id",
#   "email": "rep-001@company.onmicrosoft.com",
#   "role": "SALES_REP",
#   "exp": 1696093200
# }
```

**期待値**:
- ✅ HTTP Status: 200
- ✅ `role` フィールド: `SALES_REP` (営業マン) または `ADMIN`
- ✅ `email` フィールド: ログインユーザー

---

## ステップ 6: API エンドポイント検証

### フリースロット算出 API
```bash
# API リクエスト
curl -s http://$EC2_IP/api/free-slots/rep-001/2026-10-01 \
  -H "Authorization: Bearer [JWT_TOKEN]" | jq .

# 出力例:
# {
#   "repId": "rep-001",
#   "date": "2026-10-01",
#   "slots": [
#     {
#       "startTime": "09:00",
#       "endTime": "12:00",
#       "durationMinutes": 180
#     },
#     {
#       "startTime": "13:00",
#       "endTime": "18:00",
#       "durationMinutes": 300
#     }
#   ],
#   "totalAvailableMinutes": 480
# }
```

**期待値**:
- ✅ HTTP Status: 200
- ✅ `totalAvailableMinutes`: 480 分 (8 時間)
- ✅ ランチ時間 12:00-13:00 が除外されている
- ✅ 営業時間 9:00-18:00 のみ

### RBAC アクセス制御検証
```bash
# SALES_REP トークンで他ユーザーの予定にアクセス
curl -s http://$EC2_IP/api/appointments/rep-002 \
  -H "Authorization: Bearer [SALES_REP_TOKEN]"

# 出力例:
# {
#   "error": "Unauthorized",
#   "message": "You do not have permission to access this resource"
# }
```

**期待値**:
- ✅ HTTP Status: 403 (Forbidden)
- ✅ エラーメッセージ: アクセス拒否

### ADMIN トークンでアクセス（成功）
```bash
# ADMIN トークンで任意ユーザーの予定にアクセス
curl -s http://$EC2_IP/api/appointments/rep-002 \
  -H "Authorization: Bearer [ADMIN_TOKEN]" | jq .

# 出力例:
# {
#   "appointments": [...]
# }
```

**期待値**:
- ✅ HTTP Status: 200
- ✅ アクセス許可

---

## ステップ 7: フロントエンド UI 検証

### ブラウザでのカレンダー表示
```bash
# ブラウザで開く
open http://$EC2_IP

# 確認項目:
```

#### ✅ ページロード
- [ ] Page loads within 3 seconds
- [ ] No console errors (F12 → Console)
- [ ] Responsive design (モバイル・タブレット・デスクトップ)

#### ✅ ログイン後
- [ ] ユーザー名表示（ヘッダー）
- [ ] 月別カレンダー表示
- [ ] フリースロット表示（緑）
- [ ] 既存予定表示（青）

#### ✅ ドラッグドロップ機能
- [ ] フリースロットにドラッグ可能
- [ ] 営業時間外へのドロップで拒否
- [ ] 既存予定と重複時に拒否
- [ ] 成功時に確認ダイアログ表示

#### ✅ データバインディング
- [ ] 予定作成 → API に POST
- [ ] API 応答 → カレンダーで即座に反映
- [ ] 予定削除 → API に DELETE
- [ ] 削除反映 → カレンダーから消去

---

## ステップ 8: パフォーマンス測定

### API レスポンス時間（p99）
```bash
# 複数リクエスト実行
for i in {1..100}; do
  time curl -s http://$EC2_IP/api/free-slots/rep-001/2026-10-01 \
    -H "Authorization: Bearer [JWT_TOKEN]" > /dev/null
done

# 期待値: < 200ms (p99)
```

### UI レンダリング時間
```bash
# ブラウザ開発者ツール → Performance タブ
# 1. ページ読み込み開始
# 2. タイミング記録
# 3. 完全な描画まで測定

# 期待値: < 500ms
```

### Database Query 時間
```bash
# RDS Performance Insights（AWS コンソール）
# または
# EXPLAIN ANALYZE クエリ実行

psql -h $DB_ENDPOINT \
     -U kakehashi_admin \
     -d kakehashi_prod \
     -c "EXPLAIN ANALYZE SELECT * FROM appointments WHERE sales_rep_id='rep-001';"

# 期待値: < 50ms (p99)
```

### 同時接続テスト
```bash
# Apache Bench（ab）でストレステスト
ab -n 100 -c 12 http://$EC2_IP/health

# 出力例:
# Requests per second: 1000.00 [#/sec]
# Failed requests: 0

# 期待値:
# - Concurrent users: 12 ✅
# - Failed requests: 0 ✅
```

---

## ステップ 9: セキュリティ検証

### HTTPS / SSL テスト
```bash
# カスタムドメイン設定時
curl -v https://kakehashi.example.com/health

# 期待値:
# - HTTP Status: 200
# - SSL/TLS 1.2 以上
# - 証明書有効期限確認
```

### JWT 署名検証
```bash
# JWT トークンの署名検証
curl -s http://$EC2_IP/auth/verify \
  -H "Authorization: Bearer [TAMPERED_TOKEN]"

# 期待値:
# - HTTP Status: 401 (Unauthorized)
# - エラー: "Invalid token signature"
```

### CORS / CSRF 対策
```bash
# CORS プリフライトリクエスト
curl -v -X OPTIONS http://$EC2_IP/api/free-slots/rep-001/2026-10-01 \
  -H "Origin: http://attacker.com"

# 期待値:
# - Access-Control-Allow-Origin: [許可ドメインのみ]
# または
# - Access-Control-Allow-Origin: 設定されていない（拒否）
```

---

## ステップ 10: バックアップ・災害復旧テスト

### RDS 自動バックアップ確認
```bash
aws rds describe-db-snapshots \
  --region ap-northeast-1 \
  --query 'DBSnapshots[0].[DBSnapshotIdentifier,SnapshotCreateTime,Status]'

# 出力例:
# [
#   "rds:kakehashi-db-2026-09-30-12-34-00",
#   "2026-09-30T12:34:00Z",
#   "available"
# ]
```

**期待値**:
- ✅ 自動バックアップ: 7 日間保持
- ✅ ステータス: `available`

### ポイントインタイムリカバリ（PITR）テスト
```bash
# AWS コンソール → RDS → Snapshots
# または
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier kakehashi-restore-test \
  --db-snapshot-identifier [SNAPSHOT_ID] \
  --region ap-northeast-1
```

**期待値**: リストア完了、新インスタンス起動

---

## ステップ 11: ロギング・監視設定

### CloudWatch Logs 確認
```bash
# ログストリーム確認
aws logs describe-log-streams \
  --log-group-name /aws/ec2/kakehashi \
  --region ap-northeast-1

# ログ取得
aws logs get-log-events \
  --log-group-name /aws/ec2/kakehashi \
  --log-stream-name instance-logs \
  --region ap-northeast-1 | jq '.events[-5:]'
```

### CloudWatch アラーム確認
```bash
aws cloudwatch describe-alarms \
  --region ap-northeast-1 \
  --query 'MetricAlarms[*].[AlarmName,StateValue]'

# 期待値:
# - CPU Usage: > 80% でアラート
# - Database Connections: > 80 でアラート
# - Disk Space: < 10% でアラート
```

---

## ステップ 12: セットアップ完了確認チェックリスト

**インフラストラクチャ**
- [ ] EC2 インスタンス: `running`
- [ ] RDS インスタンス: `available`
- [ ] セキュリティグループ: ポート許可設定完了
- [ ] VPC: 10.0.0.0/16 構成確認

**接続テスト**
- [ ] EC2 SSH 接続: 成功
- [ ] Docker コンテナ: すべて `healthy`
- [ ] Backend API: ヘルスチェック OK
- [ ] Frontend UI: ロード成功

**認証・API**
- [ ] Entra ID OAuth: ログイン成功
- [ ] JWT トークン: 発行・検証成功
- [ ] RBAC: ロール別アクセス制御確認
- [ ] Free-slots API: 正常動作

**UI・機能**
- [ ] カレンダー表示: 月別表示成功
- [ ] ドラッグドロップ: 予定移動成功
- [ ] 営業時間外: 予定作成拒否
- [ ] リアルタイム更新: API 反映即座

**パフォーマンス**
- [ ] API レスポンス: p99 < 200ms
- [ ] UI レンダリング: < 500ms
- [ ] DB クエリ: p99 < 50ms
- [ ] 同時接続: 12+ ユーザー対応

**セキュリティ**
- [ ] HTTPS/SSL: 有効（本番）
- [ ] JWT 署名: 検証成功
- [ ] CORS: 正しく設定
- [ ] シークレット: 環境変数化

**監視・復旧**
- [ ] CloudWatch Logs: 出力確認
- [ ] CloudWatch Alarms: 設定完了
- [ ] RDS バックアップ: 7 日間保持
- [ ] PITR: テスト成功

✅ **すべてチェック完了**したら、**Phase 1 本番稼働** 開始可能

---

## トラブルシューティング

### API 接続エラー
```
原因: セキュリティグループでポート 3000 が許可されていない
解決: AWS コンソール → EC2 → Security Groups → インバウンドルール確認
```

### JWT トークン検証エラー
```
原因: 秘密鍵 (private-key.pem) が一致していない
解決: EC2 内で `cat ~/.ssh/private-key.pem` と確認、再生成が必要な場合は対応
```

### DB 接続タイムアウト
```
原因: RDS セキュリティグループで PostgreSQL ポート 5432 が許可されていない
解決: セキュリティグループのインバウンドルール確認、VPC ピアリング確認
```

### フロントエンド 404 エラー
```
原因: Nginx が正しくビルドされていない
解決: docker logs kakehashi-apo-poc-frontend で確認、Nginx 設定（nginx.conf）再確認
```

---

## 次のステップ

✅ 本番環境検証完了  
→ **営業マン 12 名向けトレーニング** 開始  
→ **Phase 1 本番稼働: 2026-10-10**

---

**ドキュメント版**: 1.0  
**最終更新**: 2026-09-28
