"""WikiSkill M3 / Component E: Skill Metrics の集計(合成データ・外部接続なし)。

一時的な git リポジトリ(公開リポの remote を付ける)に Experience の記録と SKILL.md の変更を作って検査する。
- 数えるもの: 公開リポ・visibility public の skill イベント、session 単位の件数、commit との同時発生
- 出さないもの: commit の件名・セッションID・記録に無い数値(null で、理由を付ける)
- 書き込まないこと: リポジトリの中身も監査ログも変わらない
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import skill_metrics as sm  # noqa: E402

PUBLIC_URL = "https://github.com/allgroup-inc/hojo-hq.git"
PUBLIC_REPO = "allgroup-inc/hojo-hq"
SECRET_SUBJECT = "秘密の件名テキスト"
SECRET_SID = "sess-SECRET-42"


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})


def _commit(root, msg, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", msg)


def _event(kind, sid, ts, repo=PUBLIC_REPO, visibility="public", **kw):
    return {"ts": ts, "session_id": sid, "event": kind, "repo": repo, "visibility": visibility,
            "branch": "main", **kw}


def _write_session(root, month, sid, events, part=None):
    name = f"session-{sid}.jsonl" if part is None else f"session-{sid}.part{part}.jsonl"
    d = root / ".claude" / "experience" / month
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")


def _repo(tmp_path, url=PUBLIC_URL, name="hojo"):
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    if url:
        _git(root, "remote", "add", "origin", url)
    _commit(root, "init", {
        ".claude/skills/writing-plans/SKILL.md": "---\nname: writing-plans\n---\n本文 v1\n",
        ".claude/skills/ad-creative/SKILL.md": "---\nname: ad-creative\n---\n本文 v1\n",
    })
    return root


@pytest.fixture
def repo(tmp_path):
    root = _repo(tmp_path)
    _write_session(root, "2026-10", "s1", [
        _event("session_start", "s1", "2026-10-03T01:00:00Z", source="startup", head="a" * 40),
        _event("skill", "s1", "2026-10-03T01:05:00Z", skill="writing-plans"),
        _event("skill", "s1", "2026-10-03T01:20:00Z", skill="writing-plans"),
        _event("session_end", "s1", "2026-10-03T02:00:00Z",
               commits=[{"sha": "abc1234", "subject": SECRET_SUBJECT}], skills=["writing-plans"], duration_s=3600),
    ])
    _write_session(root, "2026-10", "s1", [
        _event("skill", "s1", "2026-10-04T01:05:00Z", skill="writing-plans"),
    ], part=1)
    _write_session(root, "2026-10", "s2", [
        _event("skill", "s2", "2026-10-05T03:00:00Z", skill="writing-plans"),
        _event("session_end", "s2", "2026-10-05T04:00:00Z", commits=[], skills=["writing-plans"]),
    ])
    _write_session(root, "2026-10", SECRET_SID, [
        _event("skill", SECRET_SID, "2026-10-06T03:00:00Z", skill="ad-creative"),
    ])
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "記録を追加")
    return root


def _row(report, skill, period="2026-10"):
    return next(r for r in report["rows"] if r["skill"] == skill and r["period"] == period)


def test_counts_invocations_and_distinct_sessions_across_parts(repo):
    rep = sm.collect(repo)
    wp = _row(rep, "writing-plans")
    assert wp["total_invocations"] == 4          # 本体2件 + part1の1件 + s2の1件
    assert wp["sessions"] == 2                   # s1 と s2(part は同じセッションに数える)
    assert wp["first_seen"] == "2026-10-03" and wp["last_seen"] == "2026-10-05"
    assert _row(rep, "ad-creative")["total_invocations"] == 1


def test_unrecorded_metrics_are_null_and_explained(repo):
    rep = sm.collect(repo)
    wp = _row(rep, "writing-plans")
    for key in sm.NULL_FIELDS:
        assert wp[key] is None, key
    for key in ("success_count", "failure_count", "retry_count", "avg_duration_seconds", "versions_used"):
        assert key in rep["not_recorded"] and rep["not_recorded"][key]


def test_sessions_with_commits_counts_cooccurrence_only(repo):
    wp = _row(sm.collect(repo), "writing-plans")
    assert wp["sessions_with_session_end"] == 2
    assert wp["sessions_with_commits"] == 1      # s1 だけ commit がある(s2 は無い)


def test_commit_subjects_and_session_ids_never_in_output(repo):
    rep = sm.collect(repo)
    text = sm.render_json(rep) + sm.render_jsonl(rep)
    assert SECRET_SUBJECT not in text
    assert "abc1234" not in text
    assert SECRET_SID not in text
    assert all("session_id" not in r for r in rep["rows"])  # 行にセッションIDの欄は無い


def test_rows_from_other_repo_private_or_unknown_are_excluded(tmp_path):
    root = _repo(tmp_path)
    _write_session(root, "2026-10", "x1", [
        _event("skill", "x1", "2026-10-03T01:00:00Z", skill="writing-plans"),                       # 数える
        _event("skill", "x1", "2026-10-03T01:01:00Z", skill="writing-plans", visibility="private"),  # 除く
        _event("skill", "x1", "2026-10-03T01:02:00Z", skill="writing-plans", repo="example-org/other"),  # 除く
        _event("skill", "x1", "2026-10-03T01:03:00Z", skill="writing-plans", repo="unknown", visibility="public"),  # 除く
    ])
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "記録")
    rep = sm.collect(root)
    assert _row(rep, "writing-plans")["total_invocations"] == 1
    assert rep["totals"]["rows_excluded"] == 3


def test_unsafe_skill_names_become_unknown_and_plugin_refs_external(tmp_path):
    root = _repo(tmp_path)
    _write_session(root, "2026-10", "y1", [
        _event("skill", "y1", "2026-10-03T01:00:00Z", skill="../../etc/passwd"),
        _event("skill", "y1", "2026-10-03T01:01:00Z", skill="superpowers:brainstorming"),
        _event("skill", "y1", "2026-10-03T01:02:00Z", skill="removed-skill"),
    ])
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "記録")
    rep = sm.collect(root)
    names = {r["skill"]: r["source"] for r in rep["rows"]}
    assert names["<unknown>"] == "unknown"
    assert names["superpowers:brainstorming"] == "external"
    assert names["removed-skill"] == "unregistered"
    assert "../../etc/passwd" not in sm.render_json(rep)


def test_skill_changes_come_from_skill_md_commits_only(tmp_path):
    root = _repo(tmp_path)
    _commit(root, "改善", {".claude/skills/writing-plans/SKILL.md": "---\nname: writing-plans\n---\n本文 v2\n"})
    _commit(root, "参考資料だけ", {".claude/skills/writing-plans/references/x.md": "メモ\n"})
    rep = sm.collect(root)
    changes = _row(rep, "writing-plans", period=_current_month(root))["skill_changes"]
    assert [c["date"] for c in changes] == sorted(c["date"] for c in changes)
    assert len(changes) == 2                      # 初版 + v2。references の変更は数えない
    assert all(set(c) == {"sha", "date"} for c in changes)


def _current_month(root):
    out = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%ad", "--date=short"],
                         capture_output=True, text=True, check=True).stdout.strip()
    return out[:7]


def test_jsonl_rows_are_valid_and_carry_the_schema(repo):
    rep = sm.collect(repo)
    lines = [json.loads(line) for line in sm.render_jsonl(rep).splitlines() if line.strip()]
    assert lines and all(row["schema"] == sm.SCHEMA for row in lines)
    assert {"period", "skill", "source", "total_invocations", "sessions"} <= set(lines[0])


def test_period_filter_limits_rows(repo):
    assert {r["period"] for r in sm.collect(repo, period="2026-10")["rows"]} == {"2026-10"}
    assert {r["period"] for r in sm.collect(repo, period="2026-09")["rows"]} <= {"2026-09"}


def test_not_a_git_repository_is_safe(tmp_path):
    root = tmp_path / "plain"
    _write_session(root, "2026-10", "p1", [_event("skill", "p1", "2026-10-03T01:00:00Z", skill="writing-plans")])
    rep = sm.collect(root)
    assert rep["totals"]["git_available"] is False
    assert _row(rep, "writing-plans")["skill_changes"] == []
    assert _row(rep, "writing-plans")["total_invocations"] == 1


def test_empty_repository_is_safe(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "remote", "add", "origin", PUBLIC_URL)
    rep = sm.collect(root)
    assert rep["rows"] == [] and rep["totals"]["sessions_scanned"] == 0


def test_unreadable_file_is_skipped_and_counted(repo, monkeypatch):
    real = sm._read_events

    def flaky(path):
        if path.name.endswith("part1.jsonl"):
            raise OSError("読めない")
        return real(path)

    monkeypatch.setattr(sm, "_read_events", flaky)
    rep = sm.collect(repo)
    assert rep["totals"]["files_unreadable"] == 1
    assert _row(rep, "writing-plans")["total_invocations"] == 3  # part1 の1件が抜ける


def _tree_digest(root):
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if ".git" in p.parts or "__pycache__" in p.parts or not p.is_file():
            continue
        h.update(str(p.relative_to(root)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def test_collect_writes_nothing(repo):
    before = _tree_digest(repo)
    sm.collect(repo)
    sm.collect(repo, period="2026-10")
    assert _tree_digest(repo) == before
    assert not (repo / ".claude" / "experience" / "_audit.log").exists()


def test_cli_rejects_bad_period_and_prints_json(repo, capsys):
    with pytest.raises(SystemExit):
        sm.main(["--root", str(repo), "--period", "2026/10"])
    assert sm.main(["--root", str(repo), "--period", "2026-10"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["schema"] == sm.SCHEMA and out["rows"]


def test_real_repo_smoke_is_well_formed():
    rep = sm.collect(ROOT)
    assert rep["schema"] == sm.SCHEMA and "totals" in rep and "not_recorded" in rep
    for row in rep["rows"]:
        assert row["source"] in {"project", "external", "unregistered", "unknown"}
