#!/usr/bin/env bash
#
# update-skills.sh — 全リポジトリの vendored スキルを一括更新する
#
# 更新対象(第三者スキルのみ):
#   - Superpowers 14スキル (obra/superpowers, MIT)
#   - marketingskills 48スキル (coreyhaines31/marketingskills, MIT) ※マーケ系repoのみ
# 触らないもの(手書き資産):
#   - ALLGROUP カスタムスキル (hojo-* / hikari-* / kakei-* / report-* / go-*)
#   - .agents/product-marketing.md
#   - .claude/hooks / .claude/settings.json / .claude/tools
#
# 前提: 対象リポジトリが $BASE 配下に clone 済みで、main が checkout され push 権限があること。
#       (Claude Code on the web では各リポジトリを add_repo → clone してから実行する)
#
# 使い方:
#   BASE=/workspace bash scripts/update-skills.sh            # 全repo更新
#   BASE=/workspace DRY_RUN=1 bash scripts/update-skills.sh  # commitせず差分だけ確認
#
set -uo pipefail

BASE="${BASE:-/workspace}"
DRY_RUN="${DRY_RUN:-0}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# repo名 → ローカルパス(hojo-hq は主作業ディレクトリにある場合が多い)
resolve() { local r="$1"; [ -d "$BASE/$r/.git" ] && echo "$BASE/$r" || echo "/home/user/$r"; }

# マーケ系(Superpowers + marketing 48)。他は Superpowers のみ。
MARKETING_REPOS=(hojo-hq hikari-hq hikari-lp hikari-report kakei-hq)
INFRA_REPOS=(report-hq go allgroup-site)

echo "==> cloning upstreams"
git clone --depth 1 https://github.com/obra/superpowers.git "$TMP/sp" 2>/dev/null
git clone --depth 1 https://github.com/coreyhaines31/marketingskills.git "$TMP/mktg" 2>/dev/null

# marketing skills bundle (evals を除外)
mkdir -p "$TMP/mktg-skills"
cp -r "$TMP/mktg/skills/." "$TMP/mktg-skills/"
find "$TMP/mktg-skills" -type d -name evals -prune -exec rm -rf {} + 2>/dev/null
cp "$TMP/mktg/LICENSE" "$TMP/mktg-skills/MARKETINGSKILLS-LICENSE"
SP_NAMES=$(ls "$TMP/sp/skills")
MKTG_NAMES=$(ls "$TMP/mktg-skills" | grep -v -E 'LICENSE|README')

update_repo() {
  local repo="$1" with_mktg="$2" D; D="$(resolve "$repo")"
  [ -d "$D/.git" ] || { echo "[$repo] SKIP (not cloned at $D)"; return; }
  echo "[$repo] updating in $D (marketing=$with_mktg)"
  git -C "$D" fetch origin main -q && git -C "$D" checkout main -q && git -C "$D" reset --hard origin/main -q
  mkdir -p "$D/.claude/skills"
  # Superpowers(常に)
  while IFS= read -r n; do [ -n "$n" ] && { rm -rf "$D/.claude/skills/$n"; cp -r "$TMP/sp/skills/$n" "$D/.claude/skills/$n"; }; done <<< "$SP_NAMES"
  # marketing(マーケ系のみ)
  if [ "$with_mktg" = "1" ]; then
    while IFS= read -r n; do [ -n "$n" ] && { rm -rf "$D/.claude/skills/$n"; cp -r "$TMP/mktg-skills/$n" "$D/.claude/skills/$n"; }; done <<< "$MKTG_NAMES"
    cp "$TMP/mktg-skills/MARKETINGSKILLS-LICENSE" "$D/.claude/skills/MARKETINGSKILLS-LICENSE"
  fi
  git -C "$D" add .claude/skills
  if git -C "$D" diff --cached --quiet; then echo "[$repo] up to date"; return; fi
  if [ "$DRY_RUN" = "1" ]; then echo "[$repo] DRY_RUN: $(git -C "$D" diff --cached --name-only | wc -l) files changed"; git -C "$D" reset -q; return; fi
  git -C "$D" commit -q -m "chore: update vendored skills (superpowers + marketingskills)"
  local d=2; for a in 1 2 3 4 5; do git -C "$D" push origin main -q && { echo "[$repo] pushed"; return; }; git -C "$D" fetch origin main -q; git -C "$D" rebase origin/main -q || git -C "$D" rebase --abort -q; sleep $d; d=$((d*2)); done
  echo "[$repo] PUSH FAILED"
}

for r in "${MARKETING_REPOS[@]}"; do update_repo "$r" 1; done
for r in "${INFRA_REPOS[@]}";     do update_repo "$r" 0; done
echo "==> done"
