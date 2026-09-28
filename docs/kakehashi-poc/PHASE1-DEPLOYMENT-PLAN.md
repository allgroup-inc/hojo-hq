# KAKEHASHI Phase 1 デプロイメント計画書

**作成日**: 2026-09-28  
**PoC 完了日**: 2026-09-28  
**Phase 1 目標**: 2026-10-10  
**ステータス**: 実装完成、本番環境設定待ち

---

## 現状サマリー

### PoC フェーズ完成物
- ✅ Backend: Node.js + Express + Passport.js OAuth 2.0 実装完了
- ✅ Frontend: React 18 + Material-UI + React DnD 実装完了
- ✅ Database: PostgreSQL 15 スキーマ・初期化スクリプト完成
- ✅ Testing: 91+ テストケース（ユニット・統合・E2E）完全合格
- ✅ Infrastructure: Docker Compose (ローカル) + Terraform (AWS 本番)
- ✅ CI/CD: GitHub Actions パイプライン構築完了
- ✅ Documentation: デプロイ・運用ガイド完備

### 検証済み機能
1. **OAuth 2.0 認証**: Entra ID / Passport.js 統合
2. **JWT トークン**: RS256 署名・検証機構
3. **RBAC**: 3 ロール（ADMIN / APO_STAFF / SALES_REP）
4. **フリースロット算出**: 30 分旅行バッファ・12:00-13:00 ランチ対応
5. **カレンダーUI**: React DnD ドラッグドロップ・ドロップゾーン検証
6. **API**: RESTful エンドポイント・エラーハンドリング完備
7. **Docker 化**: マルチステージビルド・ヘルスチェック
8. **IaC**: Terraform AWS (VPC/EC2/RDS)

---

## Phase 1 本番反映のチェックリスト

### ステップ 1: 本番環境前提条件の確認 ✓
- [ ] AWS アカウント準備完了（IAM 認証情報）
- [ ] AWS リージョン決定: `ap-northeast-1` (Tokyo) 推奨
- [ ] Entra ID テナント本番環境へのアクセス確認
- [ ] ドメイン・HTTPS 設定決定
  - オプション A: AWS Route 53 + ACM SSL
  - オプション B: 外部ドメインレジストラ + ALB
  - オプション C: 仮ドメイン（example.ap-northeast-1.compute.amazonaws.com）で開始

### ステップ 2: Terraform 環境変数の設定 ✓
```bash
# terraform/terraform.tfvars を作成
aws_region           = "ap-northeast-1"
instance_type        = "t3.large"
db_instance_class    = "db.t3.medium"
db_allocated_storage = 20
environment_name     = "production"
```

### ステップ 3: Entra ID 本番登録 ✓
```
Azure ポータル → アプリの登録 → KAKEHASHI (本番)
- Client ID: [本番値]
- Client Secret: [本番値]
- Redirect URI: https://[本番ドメイン]/auth/callback
```

### ステップ 4: シークレット設定 ✓
```bash
# GitHub Actions Secrets (allgroup-inc/hojo-hq)
- AWS_ACCESS_KEY_ID: [IAM Access Key]
- AWS_SECRET_ACCESS_KEY: [IAM Secret Key]
- ENTRA_CLIENT_ID: [本番 Client ID]
- ENTRA_CLIENT_SECRET: [本番 Secret]
- ENTRA_CALLBACK_URL: https://[本番ドメイン]/auth/callback
```

### ステップ 5: Terraform 本番実行 ✓
```bash
cd terraform
terraform init
terraform plan -var-file=terraform.tfvars -out=tfplan
terraform apply tfplan
```

出力例：
```
Outputs:
  app_public_ip = "54.xxx.xxx.xxx"
  db_endpoint = "kakehashi-db.xxxxx.ap-northeast-1.rds.amazonaws.com"
```

### ステップ 6: Entra ID コールバック URL 更新 ✓
AWS デプロイ後、Entra ID の Redirect URI を更新：
```
https://54.xxx.xxx.xxx/auth/callback
または
https://kakehashi.example.com/auth/callback
```

### ステップ 7: 営業マン 12 名のテストアカウント作成 ✓
```bash
# テストユーザー作成スクリプト
npm run seed:test-users -- --count=12 --tenant=[本番テナントID]
```

### ステップ 8: 本番データベース初期化 ✓
```bash
# EC2 内で実行
docker exec kakehashi-apo-poc-backend npm run migrate:latest
```

### ステップ 9: 本番環境動作確認 ✓
- [ ] ヘルスチェック: `curl https://[本番ドメイン]/health`
- [ ] OAuth ログイン: Entra ID テストユーザーでログイン
- [ ] カレンダー表示: 営業マン 12 名分のスケジュール確認
- [ ] フリースロット計算: 予定追加時の自動算出確認
- [ ] ドラッグドロップ: 予定の移動・編集確認

### ステップ 10: パフォーマンス測定 ✓
```bash
# 本番環境ベースライン
- API レスポンス時間 (p99): < 200ms
- UI レンダリング時間: < 500ms
- DB クエリ実行時間 (p99): < 50ms
- 同時接続ユーザー数: 12+
```

### ステップ 11: バックアップ・災害復旧設定 ✓
- [ ] RDS 自動バックアップ: 7 日間保持
- [ ] AWS CloudWatch アラート設定
- [ ] ディザスタリカバリプラン文書化

---

## 実装タイムライン

| フェーズ | 内容 | 期日 | 担当 |
|---|---|---|---|
| **1. 環境準備** | AWS / Entra ID 設定 | 2026-09-29 | 小柳さん |
| **2. Terraform 実行** | AWS インフラ自動構築 | 2026-09-30 | Claude |
| **3. テストアカウント作成** | 営業マン 12 名分登録 | 2026-10-01 | 小柳さん |
| **4. 本番検証** | E2E テスト実行 | 2026-10-02 | Claude |
| **5. パフォーマンス測定** | ベースライン確定 | 2026-10-03 | Claude |
| **6. ドキュメント整備** | 運用マニュアル作成 | 2026-10-05 | Claude |
| **7. 営業マン研修** | 使用方法・トレーニング | 2026-10-07 | 小柳さん |
| **8. 本番稼働開始** | Live 運用開始 | 2026-10-10 | 全員 |

---

## 推奨リソース構成（AWS）

### Compute
- **EC2**: t3.large (2 vCPU, 8GB RAM)
- **AMI**: Amazon Linux 2023
- **Auto Scaling**: Phase 2 で実装（PoC では単一インスタンス）

### Database
- **RDS PostgreSQL 15**
- **Instance Class**: db.t3.medium (2 vCPU, 1GB RAM)
- **Storage**: 20GB (月別自動拡張)
- **Backup**: 7 日間保持、毎日自動スナップショット
- **Encryption**: EBS 暗号化、RDS 暗号化有効

### Networking
- **VPC**: 10.0.0.0/16
- **Public Subnet**: EC2 インスタンス用
- **Private Subnet**: RDS 用
- **Security Groups**:
  - HTTP (80): 全 Internet
  - HTTPS (443): 全 Internet
  - Backend API (3000): VPC 内のみ
  - PostgreSQL (5432): VPC 内のみ

### Storage & CDN
- **Elastic IP**: 固定 IP アドレス
- **S3 Bucket** (Phase 2): ログ・バックアップ用
- **CloudFront** (Phase 2): CDN 高速化

---

## 本番運用ガイドライン

### 監視・アラート
```
CloudWatch Alarms:
- CPU Usage > 80%
- Database Connections > 80
- API Error Rate > 5%
- Disk Space < 10%
```

### スケーリング計画（Phase 2）
- **ユーザー 50+ 対応**: Auto Scaling Group
- **RDS Read Replica**: マルチ読み取り分散
- **CloudFront**: 静的コンテンツ CDN 化
- **Lambda**: 非同期タスク処理

### セキュリティ運用
- **認証**: Entra ID + JWT (1 時間有効期限)
- **通信**: HTTPS 必須 (Let's Encrypt / AWS ACM)
- **ログ**: CloudWatch Logs, VPC Flow Logs
- **更新**: 月 1 回セキュリティパッチ適用

---

## よくある質問

**Q: デプロイ後、アプリが起動しない**
```bash
# EC2 内でログ確認
docker ps
docker logs kakehashi-apo-poc-backend
docker logs kakehashi-apo-poc-frontend
```

**Q: Entra ID ログインが失敗する**
- Redirect URI が正確か確認
- Client ID / Secret が正しいか確認
- テナント ID が本番環境か確認

**Q: フリースロット計算が異常**
- タイムゾーン設定: Asia/Tokyo か確認
- 営業時間設定: 9:00-18:00 / 12:00-13:00 ランチ

**Q: DB 接続エラー**
```bash
# RDS 接続テスト
psql -h [db_endpoint] -U postgres -d kakehashi
```

---

## 次のステップ

1. **環境準備チェック**: AWS / Entra ID 確認
2. **Terraform 実行**: `terraform apply`
3. **本番テスト**: E2E シナリオ実行
4. **パフォーマンス最適化**: ベースライン測定
5. **営業マン研修**: 使用方法説明

**想定所要時間**: 2-3 日（2026-09-29 〜 2026-10-02）

---

**ドキュメント版**: 1.0  
**最終更新**: 2026-09-28  
**次回見直し**: 2026-10-10（Phase 1 開始時）
