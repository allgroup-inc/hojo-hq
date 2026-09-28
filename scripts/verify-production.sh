#!/bin/bash

##############################################################################
# KAKEHASHI Phase 1 本番環境検証 自動化スクリプト
#
# 使用方法:
#   ./scripts/verify-production.sh \
#     --app-url https://kakehashi.example.com \
#     --jwt-token [JWT_TOKEN] \
#     --db-endpoint kakehashi-db.xxxxx.rds.amazonaws.com \
#     --db-username kakehashi_admin \
#     --db-password [PASSWORD]
#
# 出力: verification-report-YYYYMMDD-HHMMSS.json
##############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# パラメータ解析
APP_URL=""
JWT_TOKEN=""
DB_ENDPOINT=""
DB_USERNAME=""
DB_PASSWORD=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --app-url)
            APP_URL="$2"
            shift 2
            ;;
        --jwt-token)
            JWT_TOKEN="$2"
            shift 2
            ;;
        --db-endpoint)
            DB_ENDPOINT="$2"
            shift 2
            ;;
        --db-username)
            DB_USERNAME="$2"
            shift 2
            ;;
        --db-password)
            DB_PASSWORD="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# バリデーション
if [ -z "$APP_URL" ]; then
    log_error "--app-url パラメータが必須です"
    exit 1
fi

# レポートファイル初期化
REPORT_FILE="verification-report-$(date +%Y%m%d-%H%M%S).json"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# JSON レポート作成
cat > $REPORT_FILE << 'EOF'
{
  "timestamp": "TIMESTAMP_PLACEHOLDER",
  "app_url": "APP_URL_PLACEHOLDER",
  "tests": {
    "infrastructure": {},
    "api": {},
    "security": {},
    "performance": {}
  },
  "summary": {
    "total_tests": 0,
    "passed": 0,
    "failed": 0,
    "status": "RUNNING"
  }
}
EOF

# JSON 更新関数
update_json() {
    local key=$1
    local value=$2
    local temp_file="${REPORT_FILE}.tmp"

    jq "$key = $value" $REPORT_FILE > $temp_file && mv $temp_file $REPORT_FILE
}

log_info "================================"
log_info "KAKEHASHI 本番環境検証開始"
log_info "================================"

# JSON 基本情報設定
jq ".timestamp = \"$TIMESTAMP\"" $REPORT_FILE | jq ".app_url = \"$APP_URL\"" > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE

# ========================================
# テスト 1: API ヘルスチェック
# ========================================
log_info "テスト 1: API ヘルスチェック..."
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $APP_URL/health)

if [ "$HEALTH_STATUS" = "200" ]; then
    log_success "ヘルスチェック成功 (HTTP $HEALTH_STATUS)"
    jq ".tests.infrastructure.health_check = true" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
    PASSED=$((PASSED+1))
else
    log_error "ヘルスチェック失敗 (HTTP $HEALTH_STATUS)"
    jq ".tests.infrastructure.health_check = false" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
    FAILED=$((FAILED+1))
fi
TOTAL=$((TOTAL+1))

# ========================================
# テスト 2: JWT トークン検証（オプション）
# ========================================
if [ -n "$JWT_TOKEN" ]; then
    log_info "テスト 2: JWT トークン検証..."
    TOKEN_VERIFY=$(curl -s -X GET \
        -H "Authorization: Bearer $JWT_TOKEN" \
        $APP_URL/auth/verify | jq -r '.email // "null"')

    if [ "$TOKEN_VERIFY" != "null" ]; then
        log_success "JWT トークン検証成功"
        jq ".tests.security.jwt_verification = true" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
        PASSED=$((PASSED+1))
    else
        log_error "JWT トークン検証失敗"
        jq ".tests.security.jwt_verification = false" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
        FAILED=$((FAILED+1))
    fi
    TOTAL=$((TOTAL+1))
fi

# ========================================
# テスト 3: 予約スロット API（オプション）
# ========================================
if [ -n "$JWT_TOKEN" ]; then
    log_info "テスト 3: フリースロット API..."
    SLOTS_RESPONSE=$(curl -s -X GET \
        -H "Authorization: Bearer $JWT_TOKEN" \
        "$APP_URL/api/free-slots/rep-001/2026-10-01" \
        | jq '.slots | length')

    if [ "$SLOTS_RESPONSE" -gt 0 ]; then
        log_success "フリースロット API 成功 ($SLOTS_RESPONSE スロット)"
        jq ".tests.api.free_slots = true" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
        PASSED=$((PASSED+1))
    else
        log_error "フリースロット API 失敗"
        jq ".tests.api.free_slots = false" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
        FAILED=$((FAILED+1))
    fi
    TOTAL=$((TOTAL+1))
fi

# ========================================
# テスト 4: DB 接続（オプション）
# ========================================
if [ -n "$DB_ENDPOINT" ] && command -v pg_isready &> /dev/null; then
    log_info "テスト 4: PostgreSQL 接続..."
    if pg_isready -h $DB_ENDPOINT -U $DB_USERNAME > /dev/null 2>&1; then
        log_success "PostgreSQL 接続成功"
        jq ".tests.infrastructure.database_connection = true" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
        PASSED=$((PASSED+1))
    else
        log_error "PostgreSQL 接続失敗"
        jq ".tests.infrastructure.database_connection = false" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
        FAILED=$((FAILED+1))
    fi
    TOTAL=$((TOTAL+1))
fi

# ========================================
# テスト 5: レスポンスタイム計測
# ========================================
log_info "テスト 5: パフォーマンス計測 (10回リクエスト)..."
TOTAL_TIME=0
for i in {1..10}; do
    RESPONSE_TIME=$(curl -s -o /dev/null -w "%{time_total}" $APP_URL/health)
    TOTAL_TIME=$(echo "$TOTAL_TIME + $RESPONSE_TIME" | bc)
done

AVG_TIME=$(echo "scale=3; $TOTAL_TIME / 10" | bc)
log_success "平均レスポンスタイム: ${AVG_TIME}s"
jq ".tests.performance.avg_response_time = $AVG_TIME" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
PASSED=$((PASSED+1))
TOTAL=$((TOTAL+1))

# ========================================
# レポート完成
# ========================================
jq ".summary.total_tests = $TOTAL" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
jq ".summary.passed = $PASSED" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
jq ".summary.failed = $FAILED" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE

if [ $FAILED -eq 0 ]; then
    jq ".summary.status = \"PASSED\"" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
else
    jq ".summary.status = \"FAILED\"" $REPORT_FILE > ${REPORT_FILE}.tmp && mv ${REPORT_FILE}.tmp $REPORT_FILE
fi

# 完了表示
echo ""
log_success "================================"
log_success "検証完了"
log_success "================================"
echo ""
echo "テスト結果:"
echo "  合格: $PASSED / $TOTAL"
echo "  不合格: $FAILED / $TOTAL"
echo ""
echo "レポート: $REPORT_FILE"
echo ""

# レポート内容表示
jq '.' $REPORT_FILE

exit $FAILED
