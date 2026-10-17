#!/usr/bin/env sh
# =============================================================================
# 早期解約リスク保全システム 初回実行スクリプト（B群定数を決めるための1回）
# -----------------------------------------------------------------------------
# これは「統制環境（hojo-churn／アクセス制御された社内マシン）」で動かすもの。
# ⚠️ 公開リポジトリの作業コピーや個人PCで実データを扱わないこと（churn-pii-guard）。
# 出力はすべて private/first_run/ 配下（gitignore）に留まり、コミットされない。
#
# 使い方:
#   sh scripts/churn/run_first_time.sh <実CSV> <column_map.json> <当日YYYY-MM-DD> <分割日YYYY-MM-DD>
# 例:
#   sh scripts/churn/run_first_time.sh private/data.csv private/column_map.json 2026-08-12 2026-02-01
#
# <分割日> はバックテストの学習/検証の区切り。まずは「当日の半年ほど前」を目安に。
# =============================================================================
set -eu

CSV="${1:-}"; CMAP="${2:-}"; ASOF="${3:-}"; SPLIT="${4:-}"
if [ -z "$CSV" ] || [ -z "$CMAP" ] || [ -z "$ASOF" ] || [ -z "$SPLIT" ]; then
  echo "使い方: sh scripts/churn/run_first_time.sh <実CSV> <column_map.json> <当日YYYY-MM-DD> <分割日YYYY-MM-DD>"
  exit 2
fi

OUT="private/first_run"
mkdir -p "$OUT"

echo "==================================================================="
echo "STEP 1/3  preflight（門前チェック・PIIは出ません）"
echo "==================================================================="
# ここで🛑が出たら、column_map の列名が実ファイルと一致しているか・age列があるかを直す
python -m scripts.churn.cli preflight --csv "$CSV" --column-map "$CMAP" --as-of "$ASOF"

echo ""
echo "==================================================================="
echo "STEP 2/3  backtest（当たりの指標＝AUC・較正ECE・精度@キャパ）"
echo "==================================================================="
python -m scripts.churn.cli backtest --csv "$CSV" --column-map "$CMAP" --split "$SPLIT" --as-of "$ASOF"

echo ""
echo "==================================================================="
echo "STEP 3/3  pipeline（AUCゲートは一旦0で全工程を通し、成果物を private に出す）"
echo "==================================================================="
python -m scripts.churn.cli pipeline --csv "$CSV" --column-map "$CMAP" \
  --out-dir "$OUT" --as-of "$ASOF" --split "$SPLIT" --run-date "$ASOF" --auc-min 0.0

echo ""
echo "==================================================================="
echo "完了。B群定数を決めるため、下記の数字を（PIIなしなので）そのまま共有してください:"
echo "  - backtest の行: AUC / ECE / precision@30"
echo "  - $OUT/cohort.html … コホートの確定率と着地見込み"
echo "  - 金額(保険料)の分布ざっくり（AMOUNT_EDGES 調整用）"
echo "成果物は $OUT/ にあります（顧客情報を含むため private のまま・共有しないこと）。"
echo "共有するのは上の集計数字だけでOKです。"
echo "==================================================================="
