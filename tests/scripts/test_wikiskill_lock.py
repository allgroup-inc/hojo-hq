"""WikiSkill Phase 2 Task 2: wikiskill_lock.py(抽出の二重実行を止めるロック)。

stale(heartbeat から30分超)でも、自動で外してよいのは「持ち主が終わった証拠」があるときだけ
(SessionEnd の ended マーカー、または同じ host で pid が死んでいる)。証拠が無ければ明示指定を求める。
`ex` fixture は test_knowledge_extract.py から import する(同じ一時リポジトリを使う)。
"""
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from test_knowledge_extract import ex, run_cli  # noqa: E402,F401  (ex は fixture)
from wikiskill_lock import LockHeld, acquire, heartbeat, lock_path, lock_state, release  # noqa: E402

T0 = datetime(2026, 10, 7, 9, 0, 0, tzinfo=timezone.utc)


def raises(exc, fn, *args, **kwargs):
    with pytest.raises(exc) as info:
        fn(*args, **kwargs)
    return info.value


def ended_marker(root, sid):
    p = Path(root) / ".claude/experience/_local" / f"{sid}.ended"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("2026-10-07T09:10:00Z\n", encoding="utf-8")


def audit_text(root):
    p = Path(root) / ".claude/experience/_audit.log"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def test_acquire_and_release(tmp_path):
    l = acquire(tmp_path, "x", "S")
    assert lock_path(tmp_path, "x").exists()
    release(tmp_path, "x", l)
    assert lock_state(tmp_path, "x") == "free"


def test_second_acquire_refused_with_holder_info(tmp_path):
    acquire(tmp_path, "x", "S")
    e = raises(LockHeld, acquire, tmp_path, "x", "T")
    assert e.holder["session_id"] == "S"
    assert isinstance(e.age_s, int)


def test_heartbeat_extends_validity(tmp_path):
    l = acquire(tmp_path, "x", "S", now=T0)
    heartbeat(tmp_path, "x", l, now=T0 + timedelta(minutes=25))
    assert lock_state(tmp_path, "x", now=T0 + timedelta(minutes=40)) == "held"


def test_stale_with_ended_marker_auto_released_and_audited(tmp_path):
    acquire(tmp_path, "x", "S", now=T0)
    ended_marker(tmp_path, "S")
    assert lock_state(tmp_path, "x", now=T0 + timedelta(minutes=31)) == "stale_safe"
    got = acquire(tmp_path, "x", "T", now=T0 + timedelta(minutes=31))
    assert got and got["session_id"] == "T"
    assert "stale" in audit_text(tmp_path)


def test_stale_without_marker_needs_break_flag(tmp_path):
    acquire(tmp_path, "x", "S", now=T0)  # 同じ host・生きている pid(このプロセス)= 判断材料なし
    assert lock_state(tmp_path, "x", now=T0 + timedelta(minutes=31)) == "stale_unsure"
    raises(LockHeld, acquire, tmp_path, "x", "T", now=T0 + timedelta(minutes=31))
    assert acquire(tmp_path, "x", "T", break_stale=True, now=T0 + timedelta(minutes=31))


def test_extract_cli_exit_3_when_locked(ex):
    acquire(ex, "knowledge-extract", "S")
    r = run_cli(ex)
    assert r.returncode == 3
    assert "S" in r.stderr
