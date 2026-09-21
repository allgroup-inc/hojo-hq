#!/usr/bin/env bash
# みらいひらけ堂: 試写ファイルを組んで、ブラウザで自動検査するまでを1コマンドで。
#   bash scripts/miraihirake/preview.sh
# 結果: dist/miraihirake/preview.html(そのまま開ける1ファイル)
#       dist/miraihirake/shots/*.png(境目・ロゴの自動撮影)
#       dist/miraihirake/report.json(OK/NGの一覧)
set -euo pipefail
cd "$(dirname "$0")/../.."

python3 scripts/miraihirake/build_preview.py

# playwright はリポジトリ直下(CI)かグローバル(手元)のどちらかにあればよい
if ! node -e "require('playwright')" 2>/dev/null; then
  export NODE_PATH="$(npm root -g)"
fi
node scripts/miraihirake/check_film.js "$@"
