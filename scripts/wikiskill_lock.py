#!/usr/bin/env python3
"""WikiSkill Phase 2: ローカル実行の排他ロック(stdlib のみ・設計書 7.5 / Decision 8)。

`.claude/locks/<name>.lock`(git-ignored)に JSON `{session_id, host, pid, acquired_at, heartbeat_at}` を置く。
状態:
    free         ロックファイルが無い
    held         最終 heartbeat から TIMEOUT_S 以内
    stale_safe   TIMEOUT_S 超 かつ(持ち主のセッションの ended マーカーがある / 同じ host で pid が死んでいる)
    stale_unsure TIMEOUT_S 超だが、持ち主が終わった証拠が無い(読めないロックファイルもここ)
自動で外してよいのは stale_safe だけ(audit に残す)。stale_unsure は break_stale=True の明示指定でだけ外す。
"""
from __future__ import annotations

import json
import os
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wikiskill_common import LOCAL_DIR, audit, iso, utc_now  # noqa: E402

LOCK_DIR = ".claude/locks"
TIMEOUT_S = 1800
HEARTBEAT_EVERY_S = 60

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_COMPONENT = "lock"


class LockHeld(Exception):
    """ロックを取れない。holder = ロックファイルの中身(読めなければ {})、age_s = 最終 heartbeat からの秒数。"""

    def __init__(self, holder: dict, age_s: int, state: str = "held"):
        self.holder = holder
        self.age_s = age_s
        self.state = state
        sid = holder.get("session_id") if isinstance(holder, dict) else None
        minutes = max(0, age_s) // 60 if age_s >= 0 else "?"
        hint = "(終了済みと確認できないので自動では外しません。確かめてから --break-stale-lock)" \
            if state == "stale_unsure" else ""
        super().__init__(f"{sid or '<不明>'} が実行中(最終 heartbeat {minutes}分前){hint}")


def lock_path(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise ValueError(f"ロック名として使えない: {name!r}")
    return Path(root) / LOCK_DIR / f"{name}.lock"


def _now(now: datetime | None) -> datetime:
    n = now or utc_now()
    return n if n.tzinfo else n.replace(tzinfo=timezone.utc)


def _parse_iso(value) -> datetime | None:
    try:
        return datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _read(path: Path) -> dict | None:
    """ロックファイルの中身。無ければ None、読めない・形が違えば {}(持ち主不明)。"""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError):
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _age_s(holder: dict, now: datetime) -> int:
    ts = _parse_iso(holder.get("heartbeat_at")) or _parse_iso(holder.get("acquired_at"))
    return int((now - ts).total_seconds()) if ts else -1


def _safe_id(session_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(session_id)) or "unknown"


def _pid_dead(pid) -> bool:
    """pid が死んでいると確かめられたときだけ True(権限で確かめられない・不正な値は False)。"""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    except (PermissionError, OSError):
        return False
    return False


def _ended(root: Path, holder: dict) -> bool:
    sid = holder.get("session_id")
    if not isinstance(sid, str) or not sid.strip():
        return False
    return (Path(root) / LOCAL_DIR / f"{_safe_id(sid)}.ended").is_file()


def _classify(root: Path, holder: dict | None, now: datetime) -> tuple[str, int]:
    if holder is None:
        return "free", 0
    age = _age_s(holder, now)
    if age < 0:  # 時刻が読めない = 判断材料なし
        return "stale_unsure", age
    if age <= TIMEOUT_S:
        return "held", age
    same_host_dead = holder.get("host") == socket.gethostname() and _pid_dead(holder.get("pid"))
    if _ended(root, holder) or same_host_dead:
        return "stale_safe", age
    return "stale_unsure", age


def lock_state(root: Path, name: str, now: datetime | None = None) -> str:
    return _classify(root, _read(lock_path(root, name)), _now(now))[0]


def _write_new(path: Path, data: dict) -> bool:
    """O_EXCL で新規作成。既にあれば False。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")
    return True


def _same_owner(a: dict, b: dict) -> bool:
    return all(a.get(k) == b.get(k) for k in ("session_id", "host", "pid", "acquired_at"))


def acquire(root: Path, name: str, session_id: str, *, break_stale: bool = False,
            now: datetime | None = None) -> dict:
    """ロックを取る。取れなければ LockHeld。stale を外したときは audit に残す。"""
    n = _now(now)
    path = lock_path(root, name)
    mine = {"session_id": str(session_id), "host": socket.gethostname(), "pid": os.getpid(),
            "acquired_at": iso(n), "heartbeat_at": iso(n)}
    for _attempt in range(2):
        if _write_new(path, mine):
            return dict(mine)
        holder = _read(path)
        state, age = _classify(root, holder, n)
        if state == "free":
            continue  # 消えた直後。もう一度だけ作る
        if state == "held" or (state == "stale_unsure" and not break_stale):
            raise LockHeld(holder or {}, age, state)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        who = (holder or {}).get("session_id") or "<不明>"
        how = "auto (ended marker or dead pid)" if state == "stale_safe" else "--break-stale-lock"
        audit(root, _COMPONENT, f"{name}: stale lock released ({how}); holder={who} age_s={age} by={session_id}")
    holder = _read(path) or {}
    raise LockHeld(holder, _age_s(holder, n))


def heartbeat(root: Path, name: str, lock: dict, now: datetime | None = None) -> None:
    """自分のロックの heartbeat_at を進める。ロックが他人のもの・消えていれば LockHeld。"""
    path = lock_path(root, name)
    holder = _read(path)
    if not holder or not _same_owner(holder, lock):
        raise LockHeld(holder or {}, _age_s(holder or {}, _now(now)), "lost")
    lock["heartbeat_at"] = iso(_now(now))
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps({**holder, "heartbeat_at": lock["heartbeat_at"]}, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)


def release(root: Path, name: str, lock: dict) -> None:
    """自分のロックだけ消す(他人のロック・既に無いものは触らない)。"""
    path = lock_path(root, name)
    holder = _read(path)
    if holder is None:
        return
    if not _same_owner(holder, lock):
        audit(root, _COMPONENT, f"{name}: release skipped (lock is held by another owner)")
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass
