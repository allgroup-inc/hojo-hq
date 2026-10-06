#!/usr/bin/env python3
"""WikiSkill Phase 1 共通部品(stdlib のみ)。

hook・CLI から使う小さな部品: プロジェクトルート解決、無効化スイッチ、
hook 入力の読み取り、監査ログ(silent fail 禁止)、hook 出力 JSON。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

EXPERIENCE_DIR = ".claude/experience"
LOCAL_DIR = ".claude/experience/_local"
AUDIT_LOG = "_audit.log"

_FALSY = {"", "0", "false", "no", "off"}


def project_dir() -> Path:
    """CLAUDE_PROJECT_DIR → git rev-parse --show-toplevel → cwd の順で解決する。"""
    env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if env:
        return Path(env)
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
        if out:
            return Path(out)
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd()


def disabled(root: Path) -> bool:
    """HOJO_MEMORY_OFF が truthy、または root/.claude/memory.off が存在すれば True。"""
    if os.environ.get("HOJO_MEMORY_OFF", "").strip().lower() not in _FALSY:
        return True
    return (Path(root) / ".claude" / "memory.off").exists()


def read_hook_input() -> dict:
    """stdin の JSON(dict)を返す。空・壊れ・dict 以外は {}。"""
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        data = json.loads(sys.stdin.read() or "")
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def session_id_of(payload: dict) -> str:
    """payload['session_id'] → CLAUDE_SESSION_ID → unknown-<UTC時刻>。"""
    sid = payload.get("session_id") if isinstance(payload, dict) else None
    if isinstance(sid, str) and sid.strip():
        return sid.strip()
    env = os.environ.get("CLAUDE_SESSION_ID", "").strip()
    if env:
        return env
    return "unknown-" + utc_now().strftime("%Y%m%dT%H%M%SZ")


def audit(root: Path, component: str, message: str) -> None:
    """root/.claude/experience/_audit.log に `ISO8601<TAB>component<TAB>message` を追記。

    書けなければ stderr に出す(どちらにも出ない失敗は作らない)。
    """
    clean = " ".join(str(message).split())
    line = f"{iso(utc_now())}\t{component}\t{clean}\n"
    try:
        log = Path(root) / EXPERIENCE_DIR / AUDIT_LOG
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        print(f"[wikiskill audit unwritable: {e}] {line.rstrip()}", file=sys.stderr)


def emit(event: str, additional_context: str | None = None, system_message: str | None = None) -> None:
    """hook 出力 JSON を stdout に1回だけ出す。両方 None なら {}。"""
    out: dict = {}
    if additional_context is not None:
        out["hookSpecificOutput"] = {
            "hookEventName": event,
            "additionalContext": additional_context,
        }
    if system_message is not None:
        out["systemMessage"] = system_message
    print(json.dumps(out))
