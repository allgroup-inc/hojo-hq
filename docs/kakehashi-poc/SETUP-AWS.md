# AWS セットアップガイド

**対象**: KAKEHASHI Phase 1 本番環境  
**リージョン**: ap-northeast-1 (Tokyo)  
**所要時間**: 30 分

---

## ステップ 1: AWS アカウント確認

### 前提条件
- [ ] AWS アカウント作成済み
- [ ] ルートユーザー MFA 有効化済み
- [ ] 請求アラート設定済み

### 確認コマンド
```bash
aws sts get-caller-identity
# 出力例:
# {
#     "UserId": "AIDAI...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/devops"
# }
```

---

## ステップ 2: IAM ユーザー・アクセスキー作成

### AWS コンソール操作
1. **IAM コンソール** → https://console.aws.amazon.com/iam/
2. **ユーザー** → **ユーザーを作成**
3. **ユーザー名**: `kakehashi-terraform` 入力
4. **アクセス権限** → **直接ポリシーをアタッチ**
5. **ポリシー検索**: 以下を選択
   - `AmazonEC2FullAccess`
   - `AmazonRDSFullAccess`
   - `AmazonVPCFullAccess`
   - `IAMFullAccess`
6. **ユーザー作成**

### アクセスキー生成
1. 作成したユーザー `kakehashi-terraform` をクリック
2. **認証情報** → **アクセスキーを作成**
3. **ユースケース**: Terraform 用に設定
4. **説明タグ**: `kakehashi-poc-terraform`
5. **アクセスキーを作成**

### キー保存
```
Access Key ID:     AKIA...
Secret Access Key: xxx...
```

⚠️ **重要**: Secret Key は一度きりしか表示されません。  
CSV をダウンロードして安全に保管してください。

---

## ステップ 3: AWS CLI インストール（ローカル機で実施）

### macOS
```bash
brew install awscli
```

### Windows
```bash
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi
```

### Linux
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

### 確認
```bash
aws --version
# AWS CLI 2.x.x
```

---

## ステップ 4: AWS CLI 認証情報設定

### 方法 A: 対話的設定（推奨）
```bash
aws configure

AWS Access Key ID [None]: AKIA...
AWS Secret Access Key [None]: xxx...
Default region name [None]: ap-northeast-1
Default output format [None]: json
```

**保存される場所**: `~/.aws/credentials` と `~/.aws/config`

### 方法 B: 環境変数設定
```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="xxx..."
export AWS_REGION="ap-northeast-1"
```

### 方法 C: GitHub Actions Secrets 設定（本番デプロイ用）
GitHub リポジトリ → **Settings** → **Secrets and variables** → **Actions**

```
新規シークレット:
- Name: AWS_ACCESS_KEY_ID
  Value: AKIA...
- Name: AWS_SECRET_ACCESS_KEY
  Value: xxx...
```

---

## ステップ 5: AWS 接続テスト

```bash
# 認証情報確認
aws sts get-caller-identity

# 出力例:
{
    "UserId": "AIDAI...",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/kakehashi-terraform"
}
```

✅ **成功**: Account ID が表示されればOK

---

## ステップ 6: Terraform 変数ファイル準備

### ファイル作成: `terraform/terraform.tfvars`

```hcl
# AWS リージョン
aws_region = "ap-northeast-1"

# EC2 インスタンス
instance_type = "t3.large"

# RDS PostgreSQL
db_instance_class    = "db.t3.medium"
db_allocated_storage = 20
db_username          = "kakehashi_admin"
db_password          = "GenerateStrongPassword123!"  # 後で環境変数化
db_name              = "kakehashi_prod"

# 環境タグ
environment_name = "production"
project_name     = "kakehashi-apo"
```

⚠️ **重要**: `db_password` は本番環境では環境変数から取得するよう後で設定します。

---

## ステップ 7: VPC / セキュリティ設定確認

### VPC デフォルト確認
```bash
aws ec2 describe-vpcs --region ap-northeast-1 --query 'Vpcs[0].VpcId'
# 出力例: vpc-xxxxxx
```

### セキュリティグループ事前確認
Terraform が自動作成するセキュリティグループ：

| ルール | プロトコル | ポート | ソース |
|---|---|---|---|
| HTTP | TCP | 80 | 0.0.0.0/0 |
| HTTPS | TCP | 443 | 0.0.0.0/0 |
| Backend API | TCP | 3000 | VPC 内 |
| PostgreSQL | TCP | 5432 | VPC 内 |

---

## ステップ 8: EC2 キーペア作成（オプション）

SSH アクセスが必要な場合：

```bash
# キーペア作成
aws ec2 create-key-pair \
  --key-name kakehashi-poc \
  --region ap-northeast-1 \
  --query 'KeyMaterial' \
  --output text > ~/.ssh/kakehashi-poc.pem

# 権限設定
chmod 400 ~/.ssh/kakehashi-poc.pem

# SSH 接続テスト（インスタンス起動後）
ssh -i ~/.ssh/kakehashi-poc.pem ec2-user@[EC2-IP]
```

---

## ステップ 9: AWS リソース予測コスト確認

### 月額推定費用（東京リージョン）

| リソース | 仕様 | 月額 |
|---|---|---|
| **EC2** | t3.large (24/7) | $50 |
| **RDS** | db.t3.medium (24/7) | $30 |
| **EBS** | 20GB GP3 | $2 |
| **Elastic IP** | 固定IP | $4 |
| **データ転送** | 100GB 推定 | $10 |
| **合計** | | **$96** |

⚠️ **削減方法**:
- 開発環境は t3.micro + db.t3.micro で $20/月
- スポットインスタンス利用で 70% 削減

---

## ステップ 10: セットアップ完了確認チェックリスト

- [ ] AWS アカウント作成済み
- [ ] IAM ユーザー `kakehashi-terraform` 作成済み
- [ ] アクセスキー ID / Secret Key 保管済み
- [ ] AWS CLI インストール済み
- [ ] `aws configure` で認証情報設定済み
- [ ] `aws sts get-caller-identity` が成功
- [ ] GitHub Actions Secrets 設定済み（本番デプロイ用）
- [ ] `terraform/terraform.tfvars` 作成済み
- [ ] EC2 キーペア作成済み（オプション）
- [ ] AWS コスト概算確認済み

✅ **すべてチェック完了**したら、**Entra ID セットアップ** に進みます。

---

## トラブルシューティング

### エラー: "UnauthorizedOperation"
```
原因: IAM 認証情報が無効
解決: aws configure で再度認証情報を入力
```

### エラー: "InvalidParameterValue" (リージョン設定)
```
原因: リージョンが ap-northeast-1 になっていない
解決: aws configure で ap-northeast-1 を設定
```

### エラー: "SignatureDoesNotMatch"
```
原因: Secret Key が間違っている
解決: AWS コンソールで新しいアクセスキーを再生成
```

---

## 次のステップ

✅ AWS セットアップ完了  
→ **Entra ID セットアップ** に進む（SETUP-ENTRA-ID.md）

---

**ドキュメント版**: 1.0  
**最終更新**: 2026-09-28
