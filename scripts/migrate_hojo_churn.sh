#!/bin/sh
# 保全システム(scripts/churn 一式)を非公開リポジトリ hojo-churn へ隔離する移設スクリプト(案A)。
# churn-pii-guard 準拠 / 実行の決裁: 小柳さん。
#
# 前提: allgroup-inc/hojo-churn を **private** で作成済み(空でよい)。
#   リポジトリ作成は組織Adminの操作(小柳さん)。エージェント権限では 403 で作れないため人が作る。
#
# 使い方(hojo-hq のルートで実行):
#   sh scripts/migrate_hojo_churn.sh git@github.com:allgroup-inc/hojo-churn.git
# REMOTE を省略すると push せず、ローカル移設ツリーの作成とテストまでで止まる(dry-run)。
#
# private/(顧客個人データ)は移設対象に含めない。移すのはコードとPIIなしのdocs/例のみ。

set -eu
REMOTE="${1:-}"
SRC="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
STG="${TMPDIR:-/tmp}/hojo-churn-migrate"

echo "SRC(hojo-hq)     = $SRC"
echo "STAGING          = $STG"
echo "REMOTE(hojo-churn)= ${REMOTE:-（未指定=dry-run）}"

rm -rf "$STG"
mkdir -p "$STG"/scripts "$STG"/tests "$STG"/docs "$STG"/.github/workflows "$STG"/.githooks "$STG"/.claude/skills

# --- コード・テスト(本体) ---
cp -r "$SRC"/scripts/churn "$STG"/scripts/
cp -r "$SRC"/tests/churn   "$STG"/tests/
# discover のため scripts をパッケージ化
if [ -f "$SRC"/scripts/__init__.py ]; then cp "$SRC"/scripts/__init__.py "$STG"/scripts/; else : > "$STG"/scripts/__init__.py; fi

# --- 誤コミット検知(移設先にも必ず持たせる) ---
cp "$SRC"/.github/workflows/pii-guard.yml "$STG"/.github/workflows/
cp -r "$SRC"/.githooks/* "$STG"/.githooks/
cp -r "$SRC"/.claude/skills/churn-* "$STG"/.claude/skills/

# --- セキュリティ・設計ドキュメント(PIIなし) ---
cp "$SRC"/docs/顧客*.md "$SRC"/docs/守り部審査*.md "$SRC"/docs/コード隔離*.md "$STG"/docs/ 2>/dev/null || true
cp "$SRC"/docs/superpowers/specs/2026-07-2*-*.md "$SRC"/docs/superpowers/plans/2026-07-2*-*.md "$STG"/docs/ 2>/dev/null || true

# --- private/ を最初から除外 ---
printf '\n# 顧客個人データ・モデル・出力はコミットしない\nprivate/\n' > "$STG"/.gitignore

echo "--- 移設ツリー ---"
echo "scripts/churn: $(ls "$STG"/scripts/churn/*.py | wc -l) files"
echo "tests/churn  : $(ls "$STG"/tests/churn/*.py | wc -l) files"
echo "docs         : $(ls "$STG"/docs/*.md | wc -l) files"

echo "--- テスト(移設先が自己完結して緑か) ---"
( cd "$STG" && python -m unittest discover -s tests/churn -t . 2>&1 | tail -3 )

echo "--- 誤コミット検知(移設先で稼働するか) ---"
( cd "$STG" && python -m scripts.churn.precommit_pii_guard docs/*.md >/dev/null && echo "guard OK(PIIなしdocsは通過)" )

if [ -z "$REMOTE" ]; then
  echo ""
  echo "REMOTE 未指定のため push しません(dry-run)。移設ツリーは $STG に作成済み。"
  echo "本番移設は: sh scripts/migrate_hojo_churn.sh git@github.com:allgroup-inc/hojo-churn.git"
  exit 0
fi

echo "--- 初期化して push ---"
cd "$STG"
git init -q
git config core.hooksPath .githooks
git add -A
git commit -q -m "init: 保全システムを非公開リポジトリへ隔離(hojo-hqから移設・案A)"
git branch -M main
git remote add origin "$REMOTE"
git push -u origin main
echo "完了: $REMOTE へ push しました。次は §3後始末(アクセス権を限定・CI確認)へ。"
