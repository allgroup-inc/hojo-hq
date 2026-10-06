#!/usr/bin/env bash
# WikiSkill Phase 1: Claude Code の hook を1本で受けて Experience を記録し、Memory Bootstrap を注入するラッパ。
#   SessionStart: logger → bootstrap(段1)を実行し、出力 JSON を1つに合成する。
#   UserPromptSubmit: bootstrap(段2)のみ。PostToolUse / SessionEnd: logger のみ。
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

# --- 出力の検査: 成功条件は exit 0 かつ stdout が JSON オブジェクトの形 ---
#   check_output <stdout> <exit code> <ラベル>   結果は CHECKED に入る(失敗時は警告 JSON)。失敗なら return 1
check_output() {
  local out="$1" rc="$2" label="$3" t reason=""
  t="${out#"${out%%[![:space:]]*}"}"
  t="${t%"${t##*[![:space:]]}"}"
  if [ "$rc" -ne 0 ]; then
    reason="python exit non-zero"
  elif [ -z "$t" ]; then
    reason="empty stdout"
  elif [ "${t:0:1}" != "{" ] || [ "${t: -1}" != "}" ]; then
    reason="non-JSON stdout"
  fi
  if [ -z "$reason" ]; then
    CHECKED="$t"
    return 0
  fi
  code="$rc"
  if [ -n "$label" ]; then
    wrapper_audit "$label: $reason"
    CHECKED="$(printf '{"systemMessage":"⚠ wikiskill hook 失敗: %s/%s exit=%s"}' "$EVENT_SAFE" "$label" "$rc")"
  else
    wrapper_audit "$reason"
    CHECKED="$(printf '{"systemMessage":"⚠ wikiskill hook 失敗: %s exit=%s"}' "$EVENT_SAFE" "$rc")"
  fi
  return 1
}

# logger と bootstrap の出力(どちらも検査済みの JSON オブジェクト)を1つにまとめる。
#   hookSpecificOutput は bootstrap 側から、systemMessage は両方の空でないものを " / " で連結。
#   値は argv で渡す(eval しない)。
MERGE_PY='import json, sys
out, msgs = {}, []
for i, raw in enumerate(sys.argv[1:3]):
    try:
        d = json.loads(raw)
    except ValueError:
        d = None
    if not isinstance(d, dict):
        d = {"systemMessage": "⚠ wikiskill hook 失敗: merge input"}
    m = d.get("systemMessage")
    if isinstance(m, str) and m.strip():
        msgs.append(m.strip())
    if i == 1 and isinstance(d.get("hookSpecificOutput"), dict):
        out["hookSpecificOutput"] = d["hookSpecificOutput"]
if msgs:
    out["systemMessage"] = " / ".join(msgs)
print(json.dumps(out))'

case "$EVENT" in
  SessionStart)
    # logger → bootstrap の順。stdin は両方に同じものを渡す
    input="$(cat 2>/dev/null)"
    lout="$(printf '%s' "$input" | python3 "$ROOT/scripts/experience_log.py" hook "$EVENT")"
    lcode=$?
    bout="$(printf '%s' "$input" | python3 "$ROOT/scripts/memory_bootstrap.py" hook "$EVENT")"
    bcode=$?
    check_output "$lout" "$lcode" ""
    lres="$CHECKED"
    check_output "$bout" "$bcode" "bootstrap"
    bres="$CHECKED"
    merged="$(python3 -c "$MERGE_PY" "$lres" "$bres" 2>/dev/null)"
    mcode=$?
    if check_output "$merged" "$mcode" "merge"; then
      printf '%s\n' "$CHECKED"
    else
      printf '{"systemMessage":"⚠ wikiskill hook 失敗: %s exit=%s"}\n' "$EVENT_SAFE" "$lcode"
    fi
    exit 0
    ;;
  UserPromptSubmit)
    # 段2の Bootstrap のみ(logger はプロンプトを記録しない)
    out="$(python3 "$ROOT/scripts/memory_bootstrap.py" hook "$EVENT")"
    code=$?
    check_output "$out" "$code" "bootstrap"
    printf '%s\n' "$CHECKED"
    exit 0
    ;;
esac

# --- logger 呼び出し(stdin はそのまま Python に引き継ぐ) ---
out="$(python3 "$ROOT/scripts/experience_log.py" hook "$EVENT")"
code=$?
check_output "$out" "$code" ""
printf '%s\n' "$CHECKED"
exit 0
