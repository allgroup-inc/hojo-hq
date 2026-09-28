# Terraform 実行ガイド

**対象**: KAKEHASHI Phase 1 AWS インフラ構築  
**前提**: AWS / Entra ID セットアップ完了  
**所要時間**: 15 分

---

## ステップ 1: Terraform インストール

### macOS
```bash
brew install terraform

# 確認
terraform version
# Terraform v1.6.x
```

### Windows
```powershell
choco install terraform

# 確認
terraform version
```

### Linux
```bash
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# 確認
terraform version
```

---

## ステップ 2: Terraform ファイル確認

### ファイル構成
```
terraform/
├── main.tf                    # AWS リソース定義
├── terraform.tfvars.example   # 設定テンプレート
├── terraform.tfvars           # 実際の設定値（git にコミットしない）
└── init.sh                    # EC2 自動初期化スクリプト
```

### `terraform/main.tf` 確認
```bash
cd terraform
terraform fmt -check -recursive
# ✅ 成功: フォーマットが正しい
```

---

## ステップ 3: terraform.tfvars 作成

### `terraform/terraform.tfvars` 作成
`terraform.tfvars.example` をコピーして編集：

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

### ファイルの内容編集
```hcl
# AWS リージョン
aws_region = "ap-northeast-1"

# EC2 インスタンス設定
instance_type = "t3.large"
key_name      = "kakehashi-poc"  # 前に作成したキーペア名

# RDS PostgreSQL 設定
db_instance_class    = "db.t3.medium"
db_allocated_storage = 20
db_username          = "kakehashi_admin"
db_password          = "GenerateSecurePassword123!@#"  # 強力なパスワード
db_name              = "kakehashi_prod"

# タグ・環境設定
environment_name = "production"
project_name     = "kakehashi-apo"
```

⚠️ **重要**: `terraform.tfvars` は `.gitignore` に追加し、git にコミットしないこと

---

## ステップ 4: Terraform 初期化

```bash
cd terraform

# Terraform 初期化
terraform init

# 出力例:
# Terraform has been successfully configured!
```

### キャッシュ確認
```bash
ls -la .terraform/
# providers/aws 構成がダウンロードされます
```

---

## ステップ 5: Terraform 検証

```bash
# HCL フォーマット検証
terraform fmt -check -recursive

# 構文検証
terraform validate

# 出力例:
# Success! The configuration is valid.
```

---

## ステップ 6: Terraform プラン実行

```bash
# プラン生成（出力ファイル保存）
terraform plan -out=tfplan

# 出力例:
# Plan: 15 to add, 0 to change, 0 to destroy.
# 
# Saved the plan to: tfplan
```

### プラン内容確認
```bash
# テキスト形式で確認
terraform show tfplan

# 確認ポイント:
# - VPC: 1 個作成（10.0.0.0/16）
# - Subnet: 2 個作成（public/private）
# - EC2: 1 個作成（t3.large）
# - RDS: 1 個作成（PostgreSQL 15）
# - Security Group: 1 個作成
```

---

## ステップ 7: Terraform Apply 実行

⚠️ **注意**: この操作は AWS 本番環境にリソースを作成します。  
確認後に実行してください。

```bash
# リソース作成実行
terraform apply tfplan

# 出力例:
# Apply complete! Resources: 15 added, 0 changed, 0 destroyed.
# 
# Outputs:
# 
# app_public_ip = "54.xxx.xxx.xxx"
# db_endpoint = "kakehashi-db.xxxxx.ap-northeast-1.rds.amazonaws.com:5432"
```

⏱️ **所要時間**: 5-10 分（RDS 起動待機）

---

## ステップ 8: リソース確認

### AWS コンソール確認

#### EC2 インスタンス
```bash
aws ec2 describe-instances \
  --region ap-northeast-1 \
  --filters "Name=tag:Name,Values=kakehashi-apo-instance" \
  --query 'Reservations[0].Instances[0].[PublicIpAddress,State.Name]'
```

#### RDS インスタンス
```bash
aws rds describe-db-instances \
  --region ap-northeast-1 \
  --query 'DBInstances[0].[Endpoint.Address,DBInstanceStatus]'
```

#### VPC・セキュリティグループ
```bash
aws ec2 describe-security-groups \
  --region ap-northeast-1 \
  --filters "Name=group-name,Values=*kakehashi*" \
  --query 'SecurityGroups[0].[GroupId,IpPermissions]'
```

---

## ステップ 9: EC2 ヘルスチェック

### EC2 インスタンス接続テスト

```bash
# EC2 IP 取得
EC2_IP=$(terraform output -raw app_public_ip)

# SSH 接続テスト
ssh -i ~/.ssh/kakehashi-poc.pem ec2-user@$EC2_IP

# EC2 内コマンド実行
sudo systemctl status docker
docker ps
docker-compose logs
```

### EC2 内での手動初期化（オプション）

EC2 内で以下を実行（通常は `init.sh` が自動実行）:

```bash
# Docker インストール確認
docker --version
docker-compose --version

# アプリケーション起動
cd /home/ec2-user/kakehashi-apo-poc
docker-compose up -d

# ログ確認
docker-compose logs -f
```

---

## ステップ 10: RDS 接続テスト

### RDS エンドポイント確認
```bash
DB_ENDPOINT=$(terraform output -raw db_endpoint)
echo $DB_ENDPOINT
# kakehashi-db.xxxxx.ap-northeast-1.rds.amazonaws.com
```

### PostgreSQL 接続テスト（ローカル）
```bash
# pg_isready インストール
brew install postgresql  # macOS
apt-get install postgresql-client  # Linux

# 接続テスト
pg_isready -h $DB_ENDPOINT -p 5432 -U kakehashi_admin

# 出力例:
# kakehashi-db.xxxxx.ap-northeast-1.rds.amazonaws.com:5432 - accepting connections
```

### DB アクセス
```bash
psql -h $DB_ENDPOINT \
     -U kakehashi_admin \
     -d kakehashi_prod \
     -c "SELECT version();"
```

---

## ステップ 11: Entra ID コールバック URL 更新

### EC2 IP 取得
```bash
EC2_IP=$(terraform output -raw app_public_ip)
echo "https://$EC2_IP/auth/callback"
```

### Entra ID ポータルで更新
1. **Entra ID → アプリの登録**
2. **KAKEHASHI (Production)**
3. **認証 → リダイレクト URI**
4. URI 更新:
   ```
   https://54.xxx.xxx.xxx/auth/callback
   ```
5. **保存**

### 環境変数反映
```bash
# Terraform 変数更新（後でカスタムドメイン設定時に使用）
# terraform.tfvars:
# entra_callback_url = "https://54.xxx.xxx.xxx/auth/callback"
```

---

## ステップ 12: GitHub Actions CI/CD テスト

### GitHub ワークフロー確認
```bash
# GitHub Actions ログを確認
# https://github.com/allgroup-inc/hojo-hq/actions
```

### 本番デプロイメント設定
```bash
# GitHub Secrets 確認
# Settings → Secrets and variables → Actions
# 
# 必須:
# - AWS_ACCESS_KEY_ID
# - AWS_SECRET_ACCESS_KEY
# - ENTRA_CLIENT_ID
# - ENTRA_CLIENT_SECRET
```

---

## ステップ 13: セットアップ完了確認チェックリスト

- [ ] Terraform インストール完了
- [ ] `terraform/terraform.tfvars` 作成済み
- [ ] `terraform init` 成功
- [ ] `terraform validate` 成功
- [ ] `terraform plan` 確認済み
- [ ] `terraform apply` 成功（リソース作成）
- [ ] EC2 インスタンス起動確認
- [ ] RDS インスタンス起動確認（5-10 分待機）
- [ ] EC2 SSH 接続テスト成功
- [ ] RDS PostgreSQL 接続テスト成功
- [ ] Entra ID コールバック URL 更新
- [ ] GitHub Actions Secrets 設定完了

✅ **すべてチェック完了**したら、**本番環境検証** に進みます。

---

## Terraform 管理コマンド

### 状態確認
```bash
terraform show
terraform state list
```

### リソース削除（開発環境のみ）
```bash
# 確認
terraform plan -destroy

# 実行
terraform destroy -auto-approve
```

### 状態ファイルのリセット
```bash
rm -rf .terraform terraform.tfstate*
terraform init
```

---

## トラブルシューティング

### エラー: "Error: error acquiring the state lock"
```
原因: Terraform ロックファイルが残っている
解決: rm -rf .terraform.lock.hcl && terraform init
```

### エラー: "Error: MissingRegionError"
```
原因: AWS リージョンが設定されていない
解決: terraform.tfvars で aws_region = "ap-northeast-1" を確認
```

### エラー: "InvalidParameterValue" (RDS パスワード)
```
原因: DB パスワードが要件を満たしていない
解決: 最低 8 文字、大文字・小文字・数字・記号を含める
```

### エラー: "PermissionDenied" (EC2 キーペア)
```
原因: SSH キー権限が 400 になっていない
解決: chmod 400 ~/.ssh/kakehashi-poc.pem
```

---

## 本番環境デプロイ後の追加設定

### カスタムドメイン設定（Route 53）
```bash
# DNS A レコード作成
aws route53 create-resource-record-sets \
  --hosted-zone-id Z1234567890ABC \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "kakehashi.example.com",
        "Type": "A",
        "TTL": 300,
        "ResourceRecords": [{"Value": "54.xxx.xxx.xxx"}]
      }
    }]
  }'
```

### HTTPS / SSL 証明書設定（AWS Certificate Manager）
```bash
aws acm request-certificate \
  --domain-name kakehashi.example.com \
  --validation-method DNS \
  --region ap-northeast-1
```

### Application Load Balancer 設定（Phase 2）
```bash
# ALB 作成でポート 80 → 3000, 443 → フロントエンド にリダイレクト
```

---

## 次のステップ

✅ Terraform 実行完了  
→ **本番環境検証** に進む（VERIFY-PRODUCTION.md）

---

**ドキュメント版**: 1.0  
**最終更新**: 2026-09-28
