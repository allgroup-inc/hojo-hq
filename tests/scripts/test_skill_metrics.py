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
    # 登録日が履歴に無い: 失敗・再試行・成功率は観測できないので null(0 とは書かない)
    assert wp["failure_observed"] is False
    for key in ("failure_count", "retry_count", "retry_success_count", "success_rate", "avg_duration_seconds"):
        assert wp[key] is None, key
    assert wp["version_key"] is None          # 版の記録の無い古いイベント
    for key in ("failure_count", "retry_count", "success_rate", "avg_duration_seconds"):
        assert rep["not_recorded"][key]
    assert rep["totals"]["failure_firing_confirmed"] is False


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
    pairs = {(r["skill"], r["source"]) for r in rep["rows"]}
    assert ("<unknown>", "unknown") in pairs
    assert ("<external>", "external") in pairs  # プラグイン名と削除済みの名前は、どちらも名前を出さない
    text = sm.render_json(rep)
    assert "../../etc/passwd" not in text
    assert "superpowers:brainstorming" not in text
    assert "removed-skill" not in text


def test_skill_changes_come_from_skill_md_commits_only(tmp_path):
    root = _repo(tmp_path)
    _commit(root, "改善", {".claude/skills/writing-plans/SKILL.md": "---\nname: writing-plans\n---\n本文 v2\n"})
    _commit(root, "参考資料だけ", {".claude/skills/writing-plans/references/x.md": "メモ\n"})
    rep = sm.collect(root)
    versions = [v for v in rep["versions"] if v["skill"] == "writing-plans"]
    assert len(versions) == 2                     # 初版 + v2。references の変更は数えない
    assert all(set(v) == {"skill", "version_key", "commit", "date"} for v in versions)
    assert all(v["version_key"] for v in versions)
    assert versions[0]["version_key"] != versions[1]["version_key"]


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
    (root / ".claude" / "skills" / "writing-plans").mkdir(parents=True)
    (root / ".claude" / "skills" / "writing-plans" / "SKILL.md").write_text("本文\n", encoding="utf-8")
    _write_session(root, "2026-10", "p1", [_event("skill", "p1", "2026-10-03T01:00:00Z", skill="writing-plans")])
    rep = sm.collect(root)
    assert rep["totals"]["git_available"] is False
    assert rep["versions"] == []
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


# ---------------------------------------------------------------- v2: 失敗・再試行・版・所要時間(合成データ)

from experience_log import skill_content_key  # noqa: E402


def _commit_at(root, msg, files, when):
    """コミット日時を指定する(登録日の判定を試すため)。"""
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    _git(root, "add", "-A")
    env = {**os.environ, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=root, check=True, capture_output=True, env=env)


def _registered_repo(tmp_path, when="2026-10-05T00:00:00+09:00"):
    """settings.json に PostToolUseFailure を入れたコミットがある、公開リポの一時リポジトリ。"""
    root = _repo(tmp_path)
    _commit_at(root, "フック登録", {".claude/settings.json": '{"hooks": {"PostToolUseFailure": []}}'}, when)
    return root


def _skill_event(sid, ts, skill="writing-plans", **kw):
    return _event("skill", sid, ts, skill=skill, **kw)


def _failure_event(sid, ts, skill="writing-plans", **kw):
    return _event("skill_failure", sid, ts, skill=skill, **kw)


def test_failures_counted_only_after_registration(tmp_path):
    root = _registered_repo(tmp_path)
    _write_session(root, "2026-10", "r1", [
        _skill_event("r1", "2026-10-03T01:00:00Z"),                # 登録前: 失敗は観測できない
        _skill_event("r1", "2026-10-06T01:00:00Z"),                # 登録後
        _failure_event("r1", "2026-10-06T02:00:00Z"),              # 登録後の失敗
        _skill_event("r1", "2026-10-07T01:00:00Z"),                # 登録後
    ])
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "記録")
    rep = sm.collect(root)
    wp = _row(rep, "writing-plans")
    assert wp["total_invocations"] == 3
    assert wp["failure_observed"] is True
    assert wp["failure_count"] == 1
    assert wp["success_rate"] == round(2 / 3, 3)              # 登録後の成功2・失敗1
    assert rep["totals"]["failure_firing_confirmed"] is True
    assert rep["totals"]["failure_hook_registered_since"].startswith("2026-10-05T00:00:00")


def test_rows_before_registration_stay_null(tmp_path):
    root = _registered_repo(tmp_path, when="2026-10-20T00:00:00+09:00")
    _write_session(root, "2026-10", "r2", [_skill_event("r2", "2026-10-03T01:00:00Z")])
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "記録")
    wp = _row(sm.collect(root), "writing-plans")
    assert wp["failure_observed"] is False
    assert wp["failure_count"] is None and wp["retry_count"] is None and wp["success_rate"] is None


def test_retry_follows_a_failure_of_the_same_skill(tmp_path):
    root = _registered_repo(tmp_path)
    _write_session(root, "2026-10", "r3", [
        _failure_event("r3", "2026-10-06T01:00:00Z"),
        _skill_event("r3", "2026-10-06T01:01:00Z"),    # 失敗の直後の再呼び出し → 再試行(成功)
        _failure_event("r3", "2026-10-06T02:00:00Z"),
        _failure_event("r3", "2026-10-06T02:01:00Z"),  # 失敗の直後の再呼び出し → 再試行(失敗)
        _skill_event("r3", "2026-10-06T03:00:00Z", skill="ad-creative"),  # 別の Skill は数えない
    ])
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "記録")
    rep = sm.collect(root)
    wp = _row(rep, "writing-plans")
    assert wp["retry_count"] == 2
    assert wp["retry_success_count"] == 1
    ac = _row(rep, "ad-creative")                # 登録後に観測済み・失敗なし → 0 と書いてよい
    assert ac["failure_observed"] is True and ac["failure_count"] == 0 and ac["retry_count"] == 0


def test_versions_split_rows_by_content_key_and_join_to_git(tmp_path):
    root = _registered_repo(tmp_path)
    v1 = ("---\nname: writing-plans\nversion: \"1.0\"\n---\n本文 v1\n").encode("utf-8")
    v2 = ("---\nname: writing-plans\nversion: \"1.1\"\n---\n本文 v2\n").encode("utf-8")
    _commit_at(root, "v1", {".claude/skills/writing-plans/SKILL.md": v1}, "2026-10-07T00:00:00+09:00")
    _commit_at(root, "改善", {".claude/skills/writing-plans/SKILL.md": v2}, "2026-10-08T00:00:00+09:00")
    _write_session(root, "2026-10", "r4", [
        _skill_event("r4", "2026-10-09T01:00:00Z", skill_key=skill_content_key(v2), skill_version="1.1"),
        _skill_event("r4", "2026-10-09T02:00:00Z", skill_key=skill_content_key(v2), skill_version="1.1"),
        _skill_event("r4", "2026-10-06T01:00:00Z", skill_key=skill_content_key(v1), skill_version="1.0"),
    ])
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "記録")
    rep = sm.collect(root)
    rows = [r for r in rep["rows"] if r["skill"] == "writing-plans"]
    keys = {r["version_key"]: r for r in rows}
    assert set(keys) >= {skill_content_key(v1), skill_content_key(v2)}
    assert keys[skill_content_key(v2)]["total_invocations"] == 2
    assert keys[skill_content_key(v2)]["version"] == "1.1"
    assert keys[skill_content_key(v2)]["version_label"] and "2026-10-08" in keys[skill_content_key(v2)]["version_label"]
    joined = {v["version_key"] for v in rep["versions"] if v["skill"] == "writing-plans"}
    assert skill_content_key(v1) in joined and skill_content_key(v2) in joined


def test_avg_duration_uses_only_recorded_values(tmp_path):
    root = _registered_repo(tmp_path)
    _write_session(root, "2026-10", "r5", [
        _skill_event("r5", "2026-10-06T01:00:00Z", duration_ms=1000),
        _skill_event("r5", "2026-10-06T01:01:00Z", duration_ms=3000),
        _skill_event("r5", "2026-10-06T01:02:00Z"),
    ])
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "記録")
    assert _row(sm.collect(root), "writing-plans")["avg_duration_seconds"] == 2.0


def test_jsonl_rows_have_the_fields_proposer_reads(tmp_path):
    root = _registered_repo(tmp_path)
    _write_session(root, "2026-10", "r6", [
        _skill_event("r6", "2026-10-06T01:00:00Z", skill_key=skill_content_key(b"x"), skill_version="1.0"),
        _failure_event("r6", "2026-10-06T02:00:00Z", skill_key=skill_content_key(b"x")),
    ])
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "記録")
    rep = sm.collect(root)
    rows = [json.loads(x) for x in sm.render_jsonl(rep).splitlines() if x.strip()]
    required = {"schema", "period", "skill", "source", "version_key", "version_label", "version",
                "total_invocations", "success_count", "failure_count", "success_rate", "retry_count",
                "failure_observed", "sessions", "first_seen", "last_seen", "avg_duration_seconds"}
    assert rows and all(required <= set(r) for r in rows)
    assert all(r["schema"] == "skill-metrics/v2" for r in rows)
    assert all(isinstance(r["failure_observed"], bool) for r in rows)
    assert all(r["success_rate"] is None or 0 <= r["success_rate"] <= 1 for r in rows)
    versions = rep["versions"]
    assert all(set(v) == {"skill", "version_key", "commit", "date"} for v in versions)


def test_failure_firing_flag_false_without_failure_records(repo):
    assert sm.collect(repo)["totals"]["failure_firing_confirmed"] is False
