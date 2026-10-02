#!/bin/bash

# Block 2 統合テスト実行スクリプト
# Issue #5-8: 統合テスト全体を自動実行

set -e

BASE_URL="${BASE_URL:-http://localhost:3000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
# 各テストの結果JSON(ワークフローの Parse test results が読む)。前回分が混ざらないよう毎回作り直す
RESULTS_DIR="${RESULTS_DIR:-$SCRIPT_DIR/results}"
rm -rf "$RESULTS_DIR" && mkdir -p "$RESULTS_DIR"

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

    if python3 "$SCRIPT_DIR/$test_script" --base-url "$BASE_URL" --results-dir "$RESULTS_DIR" $test_args; then
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
# Playwright の JSON レポートを results/ui.json に変換する。実行できない場合も「未実行=不合格」として記録を残す
write_ui_result() {
    python3 - "$SCRIPT_DIR" "$RESULTS_DIR" "$1" "$2" <<'PY'
import json, sys
from pathlib import Path
script_dir, results_dir, report_path, reason = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
sys.path.insert(0, str(script_dir))
import results_writer as rw
try:
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
except json.JSONDecodeError:
    report = {}
summary = rw.summarize_playwright(report)
rw.write_result(results_dir, "ui", reason=reason, **summary)
PY
}

if (cd "$SCRIPT_DIR" && npx --no-install playwright --version) &> /dev/null; then
    echo -e "${YELLOW}📋 テスト実行: UI統合テスト${NC}"
    echo "  コマンド: npx playwright test ui-integration-tests.ts --reporter=json"
    echo ""

    UI_REPORT="$RESULTS_DIR/ui-playwright-report.json"
    if (cd "$SCRIPT_DIR" && BASE_URL="$BASE_URL" npx playwright test ui-integration-tests.ts --reporter=json > "$UI_REPORT"); then
        echo -e "${GREEN}✅ UI統合テスト: 成功${NC}\n"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        TEST_RESULTS+=("✅ UI統合テスト (Playwright)")
        write_ui_result "$UI_REPORT" "playwright 実行"
    else
        echo -e "${RED}❌ UI統合テスト: 失敗${NC}\n"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        TEST_RESULTS+=("❌ UI統合テスト (Playwright)")
        write_ui_result "$UI_REPORT" "playwright 実行(失敗あり)"
    fi
else
    echo -e "${YELLOW}⚠️  Playwright がインストールされていません。UI テストは未実行(不合格扱い)として記録します${NC}"
    echo "  インストール: (cd $SCRIPT_DIR && npm install && npx playwright install --with-deps chromium)"
    echo ""
    TESTS_FAILED=$((TESTS_FAILED + 1))
    TEST_RESULTS+=("❌ UI統合テスト (Playwright 未インストール・未実行)")
    write_ui_result "/dev/null" "playwright 未インストールのため未実行"
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
