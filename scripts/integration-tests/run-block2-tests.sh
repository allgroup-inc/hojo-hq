#!/bin/bash

# Block 2 統合テスト実行スクリプト
# Issue #5-8: 統合テスト全体を自動実行

set -e

BASE_URL="${BASE_URL:-http://localhost:3000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}🚀 Block 2 統合テスト自動実行スイート${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo "Base URL: $BASE_URL"
echo "実行時刻: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# テスト結果追跡
TESTS_PASSED=0
TESTS_FAILED=0
TEST_RESULTS=()

# テスト実行函数
run_test() {
    local test_name="$1"
    local test_script="$2"
    local test_args="${3:-}"

    echo -e "${YELLOW}📋 テスト実行: $test_name${NC}"
    echo "  コマンド: python3 $test_script $test_args"
    echo ""

    if python3 "$SCRIPT_DIR/$test_script" --base-url "$BASE_URL" $test_args; then
        echo -e "${GREEN}✅ $test_name: 成功${NC}\n"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        TEST_RESULTS+=("✅ $test_name")
    else
        echo -e "${RED}❌ $test_name: 失敗${NC}\n"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        TEST_RESULTS+=("❌ $test_name")
    fi
}

# Test 1: 業務軸統合テスト
echo -e "${BLUE}------- Test 1: 業務軸 ❶❂❸ 双方向連携テスト -------${NC}"
run_test "業務軸統合テスト (Issue #6, #7, #8)" "business-axis-integration-tests.py"

# Test 2: APIチェーンテスト
echo -e "${BLUE}------- Test 2: エンドツーエンドAPIチェーンテスト -------${NC}"
run_test "APIチェーンテスト (Issue #6, #7)" "api-chain-tests.py"

# Test 3: パフォーマンスベースライン
echo -e "${BLUE}------- Test 3: パフォーマンスベースライン計測 -------${NC}"
run_test "パフォーマンスベースライン (Issue #8, #14)" "performance-baseline.py"

# UI テスト (Playwright が必要)
echo -e "${BLUE}------- Test 4: UI統合テスト (Playwright) -------${NC}"
if command -v npx &> /dev/null; then
    echo -e "${YELLOW}📋 テスト実行: UI統合テスト${NC}"
    echo "  コマンド: npx playwright test ui-integration-tests.ts"
    echo ""

    if npx playwright test ui-integration-tests.ts; then
        echo -e "${GREEN}✅ UI統合テスト: 成功${NC}\n"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        TEST_RESULTS+=("✅ UI統合テスト (Playwright)")
    else
        echo -e "${RED}❌ UI統合テスト: 失敗${NC}\n"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        TEST_RESULTS+=("❌ UI統合テスト (Playwright)")
    fi
else
    echo -e "${YELLOW}⚠️  Playwright がインストールされていません。UI テストをスキップします${NC}"
    echo "  インストール: npm install -D @playwright/test"
    echo ""
fi

# テスト結果サマリー
echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}📊 テスト結果サマリー${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

for result in "${TEST_RESULTS[@]}"; do
    echo "  $result"
done

echo ""
echo -e "成功: ${GREEN}$TESTS_PASSED${NC} / 失敗: ${RED}$TESTS_FAILED${NC}"
echo ""

# ゲートウェイ判定
if [ $TESTS_FAILED -eq 0 ] && [ $TESTS_PASSED -gt 0 ]; then
    echo -e "${GREEN}🎉 Block 2 統合テスト合格! Gateway G1 クリア準備完了${NC}"
    echo ""
    echo "次のステップ:"
    echo "  1. ✅ Issue #5-8 を Close"
    echo "  2. ✅ Gateway G1 判定を実施"
    echo "  3. ✅ Block 3 本番環境準備を開始"
    echo ""
    exit 0
else
    echo -e "${RED}❌ Block 2 統合テスト失敗。改善が必要です${NC}"
    echo ""
    echo "確認項目:"
    echo "  1. ❌ API ベース URL が正しいか確認"
    echo "  2. ❌ API サーバーが起動しているか確認"
    echo "  3. ❌ テストデータが存在するか確認"
    echo "  4. ❌ JWT トークンが有効か確認"
    echo ""
    exit 1
fi
