#!/bin/bash
# KachiTalk 400+ ログ自動分析パイプライン
# 機能: 管理画面からのCSVエクスポートを監視し、到着時に自動で分析を実行

set -e

# 設定
MONITOR_DIR="/tmp"
EXPORT_PATTERN="kachitalk_logs_full_export*.csv"
ANALYSIS_SCRIPT="/home/user/hojo-hq/enlife/scripts/kachitalk_full_correlation_analysis.py"
OUTPUT_DIR="/tmp"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ログディレクトリ作成
mkdir -p /tmp/kachitalk_logs

# 1. エクスポートファイルを監視して、最新のCSVを検出
echo "🔍 KachiTalk CSV ログを検索中..."
LATEST_CSV=$(ls -t $MONITOR_DIR/$EXPORT_PATTERN 2>/dev/null | head -1)

if [ -z "$LATEST_CSV" ]; then
  echo "⏳ 待機中: KachiTalk admin dashboard から CSV をエクスポートしてください"
  echo "   場所: https://kachitalk-line-enlife.azurewebsites.net/admin"
  echo "   期間: 2026年7月1日～10月31日 / 営業マン: 全8名 / 形式: CSV (UTF-8)"
  echo "   ファイル: kachitalk_logs_full_export_YYYYMMDD.csv"
  echo ""
  echo "💡 このスクリプトを定期実行 (cron) に設定すると、CSV 到着時に自動分析が開始されます"
  exit 0
fi

echo "✓ CSV 検出: $LATEST_CSV"
FILE_SIZE=$(du -h "$LATEST_CSV" | cut -f1)
echo "  ファイルサイズ: $FILE_SIZE"

# 2. 行数を確認 (400+であることを検証)
LINE_COUNT=$(wc -l < "$LATEST_CSV")
DATA_COUNT=$((LINE_COUNT - 1))  # ヘッダー行を除外
echo "  データ件数: $DATA_COUNT 件"

if [ "$DATA_COUNT" -lt 400 ]; then
  echo "⚠️  警告: 400件未満のため、フルスケール分析ではない可能性があります"
fi

# 3. 文字エンコーディングを確認・変換
echo ""
echo "📝 ファイルエンコーディングを確認..."
CHARSET=$(file -bi "$LATEST_CSV" | grep -o 'charset=[^;]*' || echo "charset=unknown")
echo "  検出: $CHARSET"

# UTF-8以外の場合は変換
if ! file "$LATEST_CSV" | grep -q "UTF-8\|ASCII"; then
  echo "  → UTF-8 に変換中..."
  iconv -f SHIFT_JIS -t UTF-8 "$LATEST_CSV" > "${LATEST_CSV%.csv}_utf8.csv"
  LATEST_CSV="${LATEST_CSV%.csv}_utf8.csv"
fi

# 4. Python 分析を実行
echo ""
echo "🚀 Python 分析エンジンを起動..."
OUTPUT_JSON="${OUTPUT_DIR}/kachitalk_analysis_${TIMESTAMP}.json"

python3 "$ANALYSIS_SCRIPT" \
  --source csv \
  --file "$LATEST_CSV" \
  --output "$OUTPUT_JSON"

echo ""
echo "✅ 分析完了"
echo "   結果: $OUTPUT_JSON"

# 5. 結果を整理・保管
echo ""
echo "📊 分析結果を保管中..."

# 結果の統計サマリーを抽出
SUMMARY_FILE="/tmp/kachitalk_analysis_summary_${TIMESTAMP}.txt"
python3 << 'PYTHON_SUMMARY'
import json
import sys

try:
    with open("'"$OUTPUT_JSON"'", 'r', encoding='utf-8') as f:
        results = json.load(f)

    with open("'"$SUMMARY_FILE"'", 'w', encoding='utf-8') as out:
        out.write("=" * 80 + "\n")
        out.write("KachiTalk 分析結果 サマリー\n")
        out.write(f"分析日時: {results.get('timestamp', 'N/A')}\n")
        out.write(f"対象ログ: {results.get('total_logs', 0)} 件\n")
        out.write(f"分析済みスタッフ: {len(results.get('staff_analysis', {}))} 名\n")
        out.write("=" * 80 + "\n\n")

        for staff_name, analysis in results.get('staff_analysis', {}).items():
            out.write(f"📊 {staff_name}\n")
            out.write(f"  通話件数: {analysis.get('call_count', 0)} 件\n")
            out.write(f"  成約率: {analysis.get('contract_rate', 0)*100:.1f}%\n")
            out.write(f"  平均プロセス完全性: {analysis.get('avg_completeness', 0):.1f} 点\n")
            out.write("\n")

    print(f"✓ サマリー保存: {SUMMARY_FILE}")
except Exception as e:
    print(f"⚠️  サマリー生成失敗: {e}")
PYTHON_SUMMARY

# 6. Google Sheets 統合の準備
echo ""
echo "📲 Google Sheets 統合準備"
echo "   glow-ma システムへの自動インポートは、以下で実行:"
echo "   → Apps Script: analyzeKachiTalkCorrelation()"
echo "   → 分析結果ファイル: $OUTPUT_JSON"
echo ""

# 7. 自動化ステップ案内
echo "🔄 今後の自動化:"
echo "   1. このスクリプトを cron に登録: 毎週月曜 9:00 JST"
echo "   2. KachiTalk admin で毎週エクスポート (手動またはAPI)"
echo "   3. 分析が自動で実行 → Google Sheets へ連携"
echo ""

echo "📁 出力ファイル:"
ls -lh $OUTPUT_DIR/kachitalk_analysis_* 2>/dev/null | tail -5 || echo "   (生成待機中)"
echo ""
