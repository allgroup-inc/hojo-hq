#!/usr/bin/env bash
# WikiSkill Phase 1: Claude Code の hook を1本で受けて Experience を記録するラッパ。
#   使い方: wikiskill-hook.sh <SessionStart|UserPromptSubmit|PostToolUse|SessionEnd>   (stdin に hook JSON)
# 規律:
#   - 常に exit 0(既存作業を hook の都合で止めない)。stdout は常に妥当な JSON 1つ。
#   - 停止スイッチ(HOJO_MEMORY_OFF / .claude/memory.off)は Python より前に bash で判定する
#     (Python が壊れていても止められるように)。判定は wikiskill_common.disabled() と同じ。
#   - Python が落ちた/空出力/JSON でない出力のときは systemMessage で警告し、_audit.log にも1行残す(silent fail 禁止)。
#   - bash 3.2(macOS 標準)でも動くよう、bash 4 専用構文は使わない。
set -uo pipefail

EVENT="${1:-}"
EVENT_SAFE="${EVENT//[^A-Za-z0-9_]/_}"
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

# ラッパ層の失敗を _audit.log に1行残す(best-effort: 書けなくてもラッパは落とさない)
wrapper_audit() {
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown-time)"
  mkdir -p "$ROOT/.claude/experience" 2>/dev/null || return 0
  printf '%s\thook-wrapper\t%s exit=%s %s\n' "$ts" "$EVENT_SAFE" "${code:-?}" "$1" \
    >>"$ROOT/.claude/experience/_audit.log" 2>/dev/null || true
  return 0
}

# --- 停止スイッチ(wikiskill_common.disabled と同じ条件) ---
off="${HOJO_MEMORY_OFF:-}"
off="${off#"${off%%[![:space:]]*}"}"   # 前後の空白を除く
off="${off%"${off##*[![:space:]]}"}"
if [ -n "$off" ]; then
  off="$(printf '%s' "$off" | tr '[:upper:]' '[:lower:]')"
fi
case "$off" in
  ""|0|false|no|off) ;;
  *) printf '{}\n'; exit 0 ;;
esac
if [ -e "$ROOT/.claude/memory.off" ]; then
  printf '{}\n'
  exit 0
fi

# --- UserPromptSubmit は Task 4 で Bootstrap を足す。それまでは何もしない ---
if [ "$EVENT" = "UserPromptSubmit" ]; then
  cat >/dev/null 2>&1 || true
  printf '{}\n'
  exit 0
fi

# --- logger 呼び出し(stdin はそのまま Python に引き継ぐ) ---
out="$(python3 "$ROOT/scripts/experience_log.py" hook "$EVENT")"
code=$?

# 成功条件: exit 0 かつ stdout が JSON オブジェクトの形
trimmed="${out#"${out%%[![:space:]]*}"}"
trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
reason=""
if [ "$code" -ne 0 ]; then
  reason="python exit non-zero"
elif [ -z "$trimmed" ]; then
  reason="empty stdout"
elif [ "${trimmed:0:1}" != "{" ] || [ "${trimmed: -1}" != "}" ]; then
  reason="non-JSON stdout"
fi

if [ -z "$reason" ]; then
  printf '%s\n' "$trimmed"
else
  wrapper_audit "$reason"
  printf '{"systemMessage":"⚠ wikiskill hook 失敗: %s exit=%s"}\n' "$EVENT_SAFE" "$code"
fi
exit 0
