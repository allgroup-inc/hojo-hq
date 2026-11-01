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


# ---------------------------------------------------------------- fix round 1(取り合い・時計ずれ・マーカー名)

import json  # noqa: E402

import wikiskill_lock  # noqa: E402


def _holder(sid, at):
    return {"session_id": sid, "host": "other-host", "pid": 999999, "acquired_at": at, "heartbeat_at": at}


def test_holder_replaced_between_decision_and_unlink_is_held(tmp_path, monkeypatch):
    acquire(tmp_path, "x", "S", now=T0)
    ended_marker(tmp_path, "S")  # S の分は stale_safe と判定される
    real = wikiskill_lock._classify
    newer = _holder("R", "2026-10-07T09:31:00Z")

    def classify_then_replace(root, holder, now):
        out = real(root, holder, now)
        lock_path(tmp_path, "x").write_text(json.dumps(newer), encoding="utf-8")  # 判定の直後に R が取った
        return out

    monkeypatch.setattr(wikiskill_lock, "_classify", classify_then_replace)
    e = raises(LockHeld, acquire, tmp_path, "x", "T", now=T0 + timedelta(minutes=31))
    assert e.holder["session_id"] == "R"
    assert json.loads(lock_path(tmp_path, "x").read_text(encoding="utf-8"))["session_id"] == "R"  # R のロックは消さない
    assert "stale lock released" not in audit_text(tmp_path)


def test_heartbeat_does_not_overwrite_a_changed_file(tmp_path, monkeypatch):
    l = acquire(tmp_path, "x", "S", now=T0)
    real, calls = wikiskill_lock._read, []
    other = _holder("R", "2026-10-07T09:05:00Z")

    def read_then_replace(path):
        calls.append(1)
        if len(calls) == 2:  # 1回目(持ち主の確認)と書き換え直前の読み直しの間に、R が取った
            path.write_text(json.dumps(other), encoding="utf-8")
        return real(path)

    monkeypatch.setattr(wikiskill_lock, "_read", read_then_replace)
    raises(LockHeld, heartbeat, tmp_path, "x", l, now=T0 + timedelta(minutes=1))
    assert json.loads(lock_path(tmp_path, "x").read_text(encoding="utf-8"))["session_id"] == "R"
    assert l["heartbeat_at"] == "2026-10-07T09:00:00Z"
    assert not list((tmp_path / ".claude/locks").glob(".*.tmp"))


def test_future_heartbeat_from_clock_skew_is_held(tmp_path):
    acquire(tmp_path, "x", "S", now=T0)
    assert lock_state(tmp_path, "x", now=T0 - timedelta(minutes=5)) == "held"
    raises(LockHeld, acquire, tmp_path, "x", "T", now=T0 - timedelta(minutes=5))
    assert lock_state(tmp_path, "x", now=T0 - timedelta(minutes=31)) == "stale_unsure"  # 30分以上も未来は信用しない


def test_ended_marker_name_matches_session_end(tmp_path):
    from experience_log import _safe_id
    acquire(tmp_path, "x", "a/b c", now=T0)
    ended_marker(tmp_path, _safe_id("a/b c"))  # SessionEnd(_mark_ended)と同じ名前
    assert lock_state(tmp_path, "x", now=T0 + timedelta(minutes=31)) == "stale_safe"
