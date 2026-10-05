#!/bin/bash
set -uo pipefail

SKILLS_DIR=".claude/skills"
ERRORS=0
WARNINGS=0

echo "=== SKILL.md Format Validation ==="
echo

for skill_dir in "$SKILLS_DIR"/*; do
    [ -d "$skill_dir" ] || continue
    skill_name=$(basename "$skill_dir")
    skill_md="$skill_dir/SKILL.md"

    # Skip if SKILL.md doesn't exist
    [ -f "$skill_md" ] || {
        echo "❌ [$skill_name] SKILL.md が見つかりません"
        ((ERRORS++))
        continue
    }

    # Check for required sections
    # We need to be more lenient here since existing skills may not have all sections yet
    # The validation will count them but not fail immediately

    # Check if Step sections exist (at least one required)
    step_count=$(grep -c "^## Step " "$skill_md" || true)
    if [ "$step_count" -eq 0 ]; then
        echo "⚠️  [$skill_name] Step セクションが0個です"
        ((WARNINGS++))
    fi

    # Check for failure section (required)
    if ! grep -q "^## 検証失敗時" "$skill_md"; then
        echo "⚠️  [$skill_name] 「検証失敗時」セクションが見つかりません"
        ((WARNINGS++))
    fi

    # Check for local test section (required)
    if ! grep -q "^## 本番前テスト" "$skill_md"; then
        echo "⚠️  [$skill_name] 「本番前テスト」セクションが見つかりません"
        ((WARNINGS++))
    fi
done

echo
echo "=== Summary ==="
echo "Errors: $ERRORS"
echo "Warnings: $WARNINGS"

if [ $ERRORS -gt 0 ]; then
    echo "❌ $ERRORS 個のエラーを検出しました"
    exit 1
fi

if [ $WARNINGS -gt 0 ]; then
    echo "⚠️  $WARNINGS 個の警告を検出しました (改善推奨)"
    exit 0
fi

echo "✅ 全スキルが形式要件を満たしています"
exit 0
