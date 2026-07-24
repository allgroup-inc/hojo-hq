#!/usr/bin/env bash
# Inject the superpowers "using-superpowers" skill into every session so the
# skills library activates automatically. Adapted from obra/superpowers.
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-.}"
SKILL_FILE="${ROOT}/.claude/skills/using-superpowers/SKILL.md"

content="$(cat "$SKILL_FILE" 2>/dev/null || true)"
[ -z "$content" ] && exit 0

escape_for_json() {
  local s="$1"
  s="${s//\\/\\\\}"; s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"; s="${s//$'\r'/\\r}"; s="${s//$'\t'/\\t}"
  printf '%s' "$s"
}
esc="$(escape_for_json "$content")"
ctx="<EXTREMELY_IMPORTANT>\nYou have superpowers.\n\n**Below is the full content of your 'using-superpowers' skill - your introduction to using skills. For all other skills, use the 'Skill' tool:**\n\n${esc}\n</EXTREMELY_IMPORTANT>"

printf '{\n  "hookSpecificOutput": {\n    "hookEventName": "SessionStart",\n    "additionalContext": "%s"\n  }\n}\n' "$ctx"
exit 0
