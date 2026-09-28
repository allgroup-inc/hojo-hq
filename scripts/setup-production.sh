#!/bin/bash

##############################################################################
# KAKEHASHI Phase 1 本番デプロイメント 完全自動化スクリプト
#
# 使用方法:
#   ./scripts/setup-production.sh \
#     --aws-region ap-northeast-1 \
#     --entra-client-id [CLIENT_ID] \
#     --entra-client-secret [SECRET] \
#     --entra-tenant-id [TENANT_ID] \
#     --db-password [DB_PASSWORD]
#
# 前提条件:
#   - AWS CLI v2 インストール済み
#   - Terraform v1.6+ インストール済み
#   - jq インストール済み
#   - AWS 認証情報設定済み
##############################################################################

set -e

# カラー出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ログ関数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# パラメータ解析
AWS_REGION="ap-northeast-1"
DB_PASSWORD=""
ENTRA_CLIENT_ID=""
ENTRA_CLIENT_SECRET=""
ENTRA_TENANT_ID=""
SKIP_TERRAFORM=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --aws-region)
            AWS_REGION="$2"
            shift 2
            ;;
        --db-password)
            DB_PASSWORD="$2"
            shift 2
            ;;
        --entra-client-id)
            ENTRA_CLIENT_ID="$2"
            shift 2
            ;;
        --entra-client-secret)
            ENTRA_CLIENT_SECRET="$2"
            shift 2
            ;;
        --entra-tenant-id)
            ENTRA_TENANT_ID="$2"
            shift 2
            ;;
        --skip-terraform)
            SKIP_TERRAFORM=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# バリデーション
if [ -z "$ENTRA_CLIENT_ID" ] || [ -z "$ENTRA_CLIENT_SECRET" ] || [ -z "$ENTRA_TENANT_ID" ] || [ -z "$DB_PASSWORD" ]; then
    log_error "必須パラメータが不足しています"
    echo "使用方法:"
    echo "  $0 --entra-client-id [ID] --entra-client-secret [SECRET] \\"
    echo "     --entra-tenant-id [TENANT_ID] --db-password [PASSWORD]"
    exit 1
fi

log_info "================================"
log_info "KAKEHASHI Phase 1 本番デプロイメント開始"
log_info "================================"
log_info "AWS Region: $AWS_REGION"
log_info "Entra ID Tenant: $ENTRA_TENANT_ID"

# ステップ 1: AWS 認証確認
log_info "ステップ 1/5: AWS 認証情報確認中..."
if ! aws sts get-caller-identity --region $AWS_REGION > /dev/null 2>&1; then
    log_error "AWS 認証に失敗しました"
    log_info "aws configure を実行して認証情報を設定してください"
    exit 1
fi
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
log_success "AWS 認証成功 (Account: $ACCOUNT_ID)"

# ステップ 2: Terraform 変数ファイル生成
log_info "ステップ 2/5: Terraform 設定ファイル生成中..."
cat > terraform/terraform.tfvars << EOF
aws_region           = "$AWS_REGION"
instance_type        = "t3.large"
db_instance_class    = "db.t3.medium"
db_allocated_storage = 20
db_username          = "kakehashi_admin"
db_password          = "$DB_PASSWORD"
db_name              = "kakehashi_prod"
environment_name     = "production"
project_name         = "kakehashi-apo"
EOF
log_success "terraform/terraform.tfvars 生成完了"

# ステップ 3: Terraform 初期化・検証
log_info "ステップ 3/5: Terraform 初期化・検証中..."
cd terraform
terraform init -upgrade > /dev/null 2>&1
terraform fmt -recursive > /dev/null 2>&1
if ! terraform validate > /dev/null 2>&1; then
    log_error "Terraform 検証失敗"
    exit 1
fi
log_success "Terraform 検証成功"

# ステップ 4: Terraform Plan 実行
log_info "ステップ 4/5: Terraform プラン実行中..."
terraform plan -out=tfplan > /dev/null 2>&1
PLAN_RESOURCES=$(terraform show -json tfplan | jq '.resource_changes | length')
log_success "Terraform プラン完了 ($PLAN_RESOURCES リソース作成予定)"

# ステップ 5: Terraform Apply 実行
if [ "$SKIP_TERRAFORM" = false ]; then
    log_info "ステップ 5/5: AWS リソース作成中 (5-10分待機)..."
    terraform apply -auto-approve tfplan > /dev/null 2>&1

    # リソース出力取得
    APP_IP=$(terraform output -raw app_public_ip)
    DB_ENDPOINT=$(terraform output -raw db_endpoint)

    log_success "AWS リソース作成完了"
    log_success "EC2 Public IP: $APP_IP"
    log_success "RDS Endpoint: $DB_ENDPOINT"
else
    log_warning "Terraform Apply スキップ"
fi

cd ..

# ステップ 6: 環境変数ファイル生成
log_info "ステップ 6/7: 環境変数ファイル生成中..."
cat > .env.production << EOF
# AWS
AWS_REGION=$AWS_REGION

# Entra ID
ENTRA_CLIENT_ID=$ENTRA_CLIENT_ID
ENTRA_CLIENT_SECRET=$ENTRA_CLIENT_SECRET
ENTRA_TENANT_ID=$ENTRA_TENANT_ID
ENTRA_CALLBACK_URL=https://\${APP_IP}/auth/callback

# Database
DATABASE_URL=postgresql://kakehashi_admin:${DB_PASSWORD}@${DB_ENDPOINT}/kakehashi_prod

# Application
NODE_ENV=production
PORT=3000
JWT_ALGORITHM=RS256
JWT_EXPIRY=1h
JWT_ISSUER=kakehashi-apo-poc
JWT_AUDIENCE=kakehashi-apo-poc
EOF
log_success ".env.production 生成完了"

# ステップ 7: GitHub Actions Secrets 設定（オプション）
log_info "ステップ 7/7: GitHub Actions Secrets 設定中..."
if command -v gh &> /dev/null; then
    log_info "GitHub CLI detected - Secrets 自動設定..."
    gh secret set AWS_REGION --body "$AWS_REGION" 2>/dev/null || true
    gh secret set ENTRA_CLIENT_ID --body "$ENTRA_CLIENT_ID" 2>/dev/null || true
    gh secret set ENTRA_CLIENT_SECRET --body "$ENTRA_CLIENT_SECRET" 2>/dev/null || true
    gh secret set ENTRA_TENANT_ID --body "$ENTRA_TENANT_ID" 2>/dev/null || true
    log_success "GitHub Actions Secrets 設定完了"
else
    log_warning "GitHub CLI がインストールされていません"
    log_info "手動で GitHub Actions Secrets を設定してください:"
    log_info "  Settings → Secrets and variables → Actions"
fi

# 完了サマリー
echo ""
log_success "================================"
log_success "本番デプロイメント 自動化処理完了"
log_success "================================"
echo ""
echo -e "${GREEN}次のステップ:${NC}"
echo "1. EC2 インスタンス起動確認 (5-10分待機)"
echo "2. Docker コンテナの起動・ログ確認"
echo "3. Entra ID リダイレクト URI 更新"
echo "4. 本番環境検証テスト実行"
echo ""
echo "詳細は docs/kakehashi-poc/VERIFY-PRODUCTION.md を参照"
