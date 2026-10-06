"""WikiSkill Phase 1 Task 6: experience_archive.py の検査。

サイズ監視の閾値、180日超の月の判定、gzip 化で1行も失わないこと、
dry-run が何も変えないこと、失敗時に黙って成功しないことを固定する。
"""
import gzip
import os
import sys
from datetime import date

import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS))

import experience_archive  # noqa: E402
from experience_archive import (  # noqa: E402
    archivable_months,
    archive,
    check_size,
    main,
    total_size,
)

MB = 1024 * 1024
TODAY = date(2026, 10, 6)


@pytest.fixture
def repo(tmp_path):
    (tmp_path / ".claude" / "experience").mkdir(parents=True)
    return tmp_path


def exp(repo):
    return repo / ".claude" / "experience"


def mk(repo, month):
    d = exp(repo) / month
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_jsonl(repo, month, nbytes):
    """session-*.jsonl を1つ以上作り、合計およそ nbytes にする。"""
    d = mk(repo, month)
    chunk = 1 * MB
    n, i = nbytes, 0
    while n > 0:
        size = min(chunk, n)
        # 1行 = 改行込みで size バイト(ASCII)
        (d / f"session-s{i}.jsonl").write_text("x" * (size - 1) + "\n", encoding="ascii")
        n -= size
        i += 1
    return d


def write_many(repo, month):
    """複数ファイル・複数行。末尾改行なしの1ファイルと非ASCIIの1行を含む。元の全行を返す。"""
    d = mk(repo, month)
    files = {
        "session-a.jsonl": ['{"e":"start","n":1}', '{"e":"tool","n":2}', '{"e":"end","n":3}'],
        "session-b.jsonl": ['{"e":"start","note":"沖縄企業のミカタ"}', '{"e":"end","n":2}'],
        "session-c.jsonl": ['{"e":"start","n":9}', '{"e":"end","n":10}'],
    }
    lines = []
    for name in sorted(files):
        body = "\n".join(files[name])
        if name != "session-b.jsonl":  # b は末尾改行なし
            body += "\n"
        (d / name).write_text(body, encoding="utf-8")
        lines.extend(files[name])
    return lines


def gz_of(repo, month):
    return exp(repo) / "archive" / f"{month}.jsonl.gz"


def snapshot(repo):
    return sorted(
        (str(p.relative_to(repo)), p.read_bytes() if p.is_file() else None)
        for p in repo.rglob("*")
    )


# --- brief の5テスト ---

def test_check_size_levels(repo, capsys):
    write_jsonl(repo, "2026-10", 4 * MB)
    assert check_size(repo) == 1
    assert "Experience合計 4.0MB(警告 3MB / 上限 10MB)" in capsys.readouterr().out
    write_jsonl(repo, "2026-11", 7 * MB)
    assert check_size(repo) == 2


def test_check_size_ok_when_empty(repo, capsys):
    assert check_size(repo) == 0
    assert capsys.readouterr().out.strip() == "Experience合計 0.0MB(警告 3MB / 上限 10MB)"


def test_archivable_months_boundary(repo):
    mk(repo, "2026-03")
    mk(repo, "2026-05")
    # 2026-04-01 + 180日 = 2026-09-28 <= 10-06 / 2026-06-01 + 180日 = 11-28 > 10-06
    assert [p.name for p in archivable_months(repo, TODAY)] == ["2026-03"]


def test_archivable_months_exact_boundary_day(repo):
    mk(repo, "2026-03")
    assert archivable_months(repo, date(2026, 9, 27)) == []
    assert [p.name for p in archivable_months(repo, date(2026, 9, 28))] == ["2026-03"]


def test_archivable_months_december_rolls_year(repo):
    mk(repo, "2025-12")  # 2026-01-01 + 180日 = 2026-06-30
    assert archivable_months(repo, date(2026, 6, 29)) == []
    assert [p.name for p in archivable_months(repo, date(2026, 6, 30))] == ["2025-12"]


def test_archivable_months_ignores_other_names(repo):
    mk(repo, "2026-03")
    for name in ["_local", "archive", "2026-3", "2026-03-old", "abcd-ef", "202603"]:
        (exp(repo) / name).mkdir()
    (exp(repo) / "2026-02").write_text("file, not dir")
    (exp(repo) / "_audit.log").write_text("x")
    assert [p.name for p in archivable_months(repo, TODAY)] == ["2026-03"]


def test_archive_roundtrip_keeps_every_line(repo):
    lines = write_many(repo, "2026-03")
    done = archive(repo, TODAY)
    gz = gz_of(repo, "2026-03")
    assert gz.exists()
    assert gzip.open(gz, "rt", encoding="utf-8").read().splitlines() == lines
    assert not (exp(repo) / "2026-03").exists()
    assert [p.name for p in done] == ["2026-03.jsonl.gz"]


def test_archive_is_reproducible(repo, tmp_path_factory):
    write_many(repo, "2026-03")
    archive(repo, TODAY)
    first = gz_of(repo, "2026-03").read_bytes()
    other = tmp_path_factory.mktemp("other")
    (other / ".claude" / "experience").mkdir(parents=True)
    write_many(other, "2026-03")
    archive(other, TODAY)
    assert gz_of(other, "2026-03").read_bytes() == first


def test_archive_dry_run_changes_nothing(repo, capsys):
    write_many(repo, "2026-03")
    write_many(repo, "2026-09")
    before = snapshot(repo)
    assert main(["--archive", "--dry-run", "--today", "2026-10-06"], root=repo) == 0
    assert snapshot(repo) == before
    out = capsys.readouterr().out
    assert "2026-03" in out and "2026-09" not in out


def test_archive_skips_local_audit_and_archive_dir(repo):
    write_many(repo, "2026-03")
    (exp(repo) / "_local").mkdir()
    (exp(repo) / "_local" / "session-x.jsonl").write_text("secret\n")
    (exp(repo) / "_audit.log").write_text("log\n")
    (exp(repo) / "archive").mkdir()
    (exp(repo) / "archive" / "2025-01.jsonl.gz").write_bytes(b"keep")
    archive(repo, TODAY)
    assert (exp(repo) / "_local" / "session-x.jsonl").read_text() == "secret\n"
    assert (exp(repo) / "_audit.log").read_text() == "log\n"
    assert (exp(repo) / "archive" / "2025-01.jsonl.gz").read_bytes() == b"keep"
    assert gz_of(repo, "2026-03").exists()
    names = gzip.open(gz_of(repo, "2026-03"), "rt", encoding="utf-8").read()
    assert "secret" not in names


def test_archived_size_counts_toward_total(repo):
    write_jsonl(repo, "2026-03", 2 * MB)
    write_jsonl(repo, "2026-10", 1 * MB)
    local = exp(repo) / "_local"
    local.mkdir()
    (local / "session-z.jsonl").write_text("y" * MB)  # _local は数えない
    assert total_size(repo) == 3 * MB
    archive(repo, TODAY)
    gz = gz_of(repo, "2026-03")
    assert total_size(repo) == 1 * MB + gz.stat().st_size


def test_archive_refuses_unexpected_files_and_keeps_originals(repo):
    lines = write_many(repo, "2026-03")
    (exp(repo) / "2026-03" / "notes.txt").write_text("not a session file")
    with pytest.raises(RuntimeError):
        archive(repo, TODAY)
    assert (exp(repo) / "2026-03" / "notes.txt").exists()
    assert not gz_of(repo, "2026-03").exists()
    assert len(list((exp(repo) / "2026-03").glob("session-*.jsonl"))) == 3
    assert lines  # 原本は残っている


def test_archive_refuses_to_overwrite_existing_gz(repo):
    write_many(repo, "2026-03")
    (exp(repo) / "archive").mkdir()
    gz_of(repo, "2026-03").write_bytes(b"older")
    with pytest.raises(RuntimeError):
        archive(repo, TODAY)
    assert gz_of(repo, "2026-03").read_bytes() == b"older"
    assert (exp(repo) / "2026-03").exists()


# --- CLI ---

def test_cli_check_exit_codes(repo, capsys):
    assert main(["--check"], root=repo) == 0
    write_jsonl(repo, "2026-10", 4 * MB)
    assert main(["--check"], root=repo) == 1
    write_jsonl(repo, "2026-11", 7 * MB)
    assert main(["--check"], root=repo) == 2


def test_cli_unknown_argument_exits_2(repo, capsys):
    assert main(["--bogus"], root=repo) == 2
    err = capsys.readouterr().err
    assert "使い方" in err and len(err.strip().splitlines()) == 1
    assert main([], root=repo) == 2
    assert main(["--check", "--archive"], root=repo) == 2
    assert main(["--dry-run"], root=repo) == 2
    assert main(["--archive", "--today", "not-a-date"], root=repo) == 2


def test_cli_archive_end_to_end(repo, capsys):
    lines = write_many(repo, "2026-03")
    assert main(["--archive", "--today", "2026-10-06"], root=repo) == 0
    assert gzip.open(gz_of(repo, "2026-03"), "rt", encoding="utf-8").read().splitlines() == lines
    assert "2026-03" in capsys.readouterr().out


def test_cli_unexpected_failure_audits_and_exits_1(repo, monkeypatch, capsys):
    write_many(repo, "2026-03")
    (exp(repo) / "2026-03" / "notes.txt").write_text("x")
    assert main(["--archive", "--today", "2026-10-06"], root=repo) == 1
    assert "archive" in capsys.readouterr().err
    log = (exp(repo) / "_audit.log").read_text(encoding="utf-8")
    assert "\tarchive\t" in log

    def boom(*a, **k):
        raise OSError("disk gone")

    monkeypatch.setattr(experience_archive, "total_size", boom)
    assert main(["--check"], root=repo) == 1
