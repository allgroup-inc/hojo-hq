#!/usr/bin/env bash
# WikiSkill Phase 1: Claude Code の hook を1本で受けて Experience を記録するラッパ。
#   使い方: wikiskill-hook.sh <SessionStart|UserPromptSubmit|PostToolUse|SessionEnd>   (stdin に hook JSON)
# 規律:
#   - 常に exit 0(既存作業を hook の都合で止めない)。stdout は常に妥当な JSON 1つ。
#   - 停止スイッチ(HOJO_MEMORY_OFF / .claude/memory.off)は Python より前に bash で判定する
#     (Python が壊れていても止められるように)。判定は wikiskill_common.disabled() と同じ。
#   - Python が落ちた/空出力のときは systemMessage で警告する(silent fail 禁止)。
set -uo pipefail

EVENT="${1:-}"
EVENT_SAFE="${EVENT//[^A-Za-z0-9_]/_}"
ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

# --- 停止スイッチ(wikiskill_common.disabled と同じ条件) ---
off="${HOJO_MEMORY_OFF:-}"
off="${off#"${off%%[![:space:]]*}"}"   # 前後の空白を除く
off="${off%"${off##*[![:space:]]}"}"
off="${off,,}"
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

# --- stdin を一度読む(session_id 欠落の audit と Python への受け渡しの両方に使う) ---
input="$(cat 2>/dev/null || true)"

# session_id が payload にも CLAUDE_SESSION_ID にも無い → Python 側は unknown-<時刻> に落ちる。
# 黙って別名で記録しないよう、ここで _audit.log に残す(silent fail 禁止)。
if [ -z "${CLAUDE_SESSION_ID:-}" ] \
   && ! [[ "$input" =~ \"session_id\"[[:space:]]*:[[:space:]]*\"[^\"[:space:]] ]]; then
  if mkdir -p "$ROOT/.claude/experience" 2>/dev/null; then
    printf '%s\twikiskill-hook\t%s: payload に session_id が無い(unknown-<時刻> で記録)\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$EVENT_SAFE" \
      >>"$ROOT/.claude/experience/_audit.log" 2>/dev/null || true
  fi
fi

# --- logger 呼び出し ---
out="$(printf '%s' "$input" | python3 "$ROOT/scripts/experience_log.py" hook "$EVENT")"
code=$?

# 成功条件: exit 0 かつ stdout が JSON オブジェクトの形
trimmed="${out#"${out%%[![:space:]]*}"}"
trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
if [ "$code" -eq 0 ] && [ "${trimmed:0:1}" = "{" ] && [ "${trimmed: -1}" = "}" ]; then
  printf '%s\n' "$trimmed"
else
  printf '{"systemMessage":"⚠ wikiskill hook 失敗: %s exit=%s"}\n' "$EVENT_SAFE" "$code"
fi
exit 0
