#!/bin/bash

# エンライフ営業成績 → カチトーク一括同期スクリプト
# 使用方法: ./sync_all.sh

set -e

# 色付き出力用
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "エンライフ営業成績 → カチトーク同期"
echo "=========================================="
echo ""

# 環境変数チェック
if [ -z "$KACHITALK_ENDPOINT" ] || [ -z "$KACHITALK_API_TOKEN" ]; then
    echo -e "${YELLOW}【警告】環境変数が設定されていません${NC}"
    echo "以下の環境変数を設定してください:"
    echo "  export KACHITALK_ENDPOINT=\"https://kachitalk-line-enlife.azurewebsites.net\""
    echo "  export KACHITALK_API_TOKEN=\"<トークン>\""
    echo ""
    read -p "続行しますか？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# スクリプトの場所
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ステップ1: CSV抽出
echo -e "${GREEN}【ステップ1】Excelからデータを抽出${NC}"
python3 "$SCRIPT_DIR/extract_sales_performance.py"

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ CSV抽出に失敗しました${NC}"
    exit 1
fi

echo ""

# ステップ2: Google Sheetへの貼り付けについて
echo -e "${YELLOW}【ステップ2】Google Sheetへの貼り付け（手動）${NC}"
echo "1. /tmp/sales_performance_for_sheets.csv をテキストエディタで開く"
echo "2. すべての行をコピー"
echo "3. Google Sheetの「営業成績（月別）」シートのA1セルに貼り付け"
echo "4. Apps Scriptエディタで updatePerformanceAnalysis() を実行"
echo ""
read -p "Google Sheetへの貼り付けが完了しましたか？(y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "処理をスキップします"
    exit 0
fi

echo ""

# ステップ3: カチトークへ同期
echo -e "${GREEN}【ステップ3】カチトークへデータを同期${NC}"

if [ -z "$KACHITALK_ENDPOINT" ] || [ -z "$KACHITALK_API_TOKEN" ]; then
    echo -e "${RED}✗ カチトークの認証情報が設定されていません${NC}"
    echo "環境変数を設定して再度実行してください:"
    echo "  export KACHITALK_ENDPOINT=\"https://kachitalk-line-enlife.azurewebsites.net\""
    echo "  export KACHITALK_API_TOKEN=\"<トークン>\""
    exit 1
fi

python3 "$SCRIPT_DIR/sync_to_kachitalk.py" \
    --csv /tmp/sales_performance_for_sheets.csv \
    --endpoint "$KACHITALK_ENDPOINT" \
    --token "$KACHITALK_API_TOKEN"

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ カチトーク同期に失敗しました${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ すべてのステップが完了しました${NC}"
echo ""
echo "【確認】"
echo "カチトークの状況確認URLでデータが表示されているか確認してください:"
echo "  https://kachitalk-line-enlife.azurewebsites.net/admin"
echo ""
