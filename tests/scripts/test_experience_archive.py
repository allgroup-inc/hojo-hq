"""WikiSkill Phase 1 Task 6: experience_archive.py の検査。

サイズ監視の閾値、180日超の月の判定、gzip 化で1行も失わないこと、
dry-run が何も変えないこと、失敗時に黙って成功しないことを固定する。
"""
import gzip
import json
import shutil
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


# --- 失敗時の後始末・報告(レビュー指摘への対応) ---

def _partial_rmtree(real):
    """1ファイルだけ消して失敗する rmtree。"""
    def fake(path, *a, **k):
        victim = sorted(os.fspath(p) for p in path.glob("session-*.jsonl"))[0]
        os.remove(victim)
        raise OSError("simulated rmtree failure")
    return fake


def test_rmtree_failure_reports_verified_gz_and_leftovers(repo, monkeypatch):
    lines = write_many(repo, "2026-03")
    monkeypatch.setattr(shutil, "rmtree", _partial_rmtree(shutil.rmtree))
    with pytest.raises(RuntimeError) as ei:
        archive(repo, TODAY)
    msg = str(ei.value)
    assert "検証済みで完全" in msg and "2026-03" in msg
    assert "session-b.jsonl" in msg and "session-c.jsonl" in msg  # 残りの一覧
    assert "session-a.jsonl" not in msg  # 消えたものは載せない
    assert gzip.open(gz_of(repo, "2026-03"), "rt", encoding="utf-8").read().splitlines() == lines
    assert not list((exp(repo) / "archive").glob(".*.tmp"))


def test_rerun_after_rmtree_failure_completes_cleanup(repo, monkeypatch):
    lines = write_many(repo, "2026-03")
    with monkeypatch.context() as m:
        m.setattr(shutil, "rmtree", _partial_rmtree(shutil.rmtree))
        with pytest.raises(RuntimeError):
            archive(repo, TODAY)
    assert (exp(repo) / "2026-03").exists()
    done = archive(repo, TODAY)  # 本物の rmtree で再実行
    assert [p.name for p in done] == ["2026-03.jsonl.gz"]
    assert not (exp(repo) / "2026-03").exists()
    assert gzip.open(gz_of(repo, "2026-03"), "rt", encoding="utf-8").read().splitlines() == lines


def test_rerun_resume_when_gz_exists_and_originals_untouched(repo):
    lines = write_many(repo, "2026-03")
    # 前回: gz 作成まで成功し、フォルダを1つも消せなかった状態
    import experience_archive as ea
    files = sorted((exp(repo) / "2026-03").glob("session-*.jsonl"))
    (exp(repo) / "archive").mkdir()
    ea._write_gzip(gz_of(repo, "2026-03"), ea._month_bytes(files))
    assert [p.name for p in archive(repo, TODAY)] == ["2026-03.jsonl.gz"]
    assert not (exp(repo) / "2026-03").exists()
    assert gzip.open(gz_of(repo, "2026-03"), "rt", encoding="utf-8").read().splitlines() == lines


def test_existing_gz_with_different_content_still_refused_accurately(repo):
    write_many(repo, "2026-03")
    import experience_archive as ea
    (exp(repo) / "archive").mkdir()
    ea._write_gzip(gz_of(repo, "2026-03"), b'{"other":"content"}\n')
    with pytest.raises(RuntimeError) as ei:
        archive(repo, TODAY)
    assert "内容が一致しない" in str(ei.value)
    assert len(list((exp(repo) / "2026-03").glob("session-*.jsonl"))) == 3
    assert gzip.open(gz_of(repo, "2026-03"), "rb").read() == b'{"other":"content"}\n'


def test_gzip_write_failure_leaves_originals_and_no_tmp(repo, monkeypatch):
    write_many(repo, "2026-03")
    before = snapshot(repo)

    def boom(path, data):
        path.write_bytes(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr(experience_archive, "_write_gzip", boom)
    with pytest.raises(OSError):
        archive(repo, TODAY)
    assert not list((exp(repo) / "archive").glob("*"))  # .tmp も gz も残らない
    after = [x for x in snapshot(repo) if "/archive/" not in x[0] and not x[0].endswith("/archive")]
    assert after == [x for x in before if "/archive/" not in x[0] and not x[0].endswith("/archive")]
    assert not gz_of(repo, "2026-03").exists()


def test_gzip_readback_mismatch_leaves_originals_and_no_tmp(repo, monkeypatch):
    write_many(repo, "2026-03")
    real = experience_archive._write_gzip
    monkeypatch.setattr(experience_archive, "_write_gzip", lambda path, data: real(path, data[:-5]))
    with pytest.raises(RuntimeError, match="一致しません"):
        archive(repo, TODAY)
    assert not list((exp(repo) / "archive").glob("*"))
    assert len(list((exp(repo) / "2026-03").glob("session-*.jsonl"))) == 3


def test_gzip_truncated_file_is_runtime_error_and_clean(repo, monkeypatch):
    write_many(repo, "2026-03")
    real = experience_archive._write_gzip

    def trunc(path, data):
        real(path, data)
        raw = path.read_bytes()
        path.write_bytes(raw[:-6])  # gzip 末尾(CRC/サイズ)を欠く

    monkeypatch.setattr(experience_archive, "_write_gzip", trunc)
    with pytest.raises(RuntimeError):
        archive(repo, TODAY)
    assert not list((exp(repo) / "archive").glob("*"))
    assert len(list((exp(repo) / "2026-03").glob("session-*.jsonl"))) == 3


def test_archive_failure_reports_months_already_archived(repo):
    lines02 = write_many(repo, "2026-02")
    write_many(repo, "2026-03")
    (exp(repo) / "2026-03" / "notes.txt").write_text("x")
    with pytest.raises(RuntimeError) as ei:
        archive(repo, TODAY)
    msg = str(ei.value)
    assert "2026-03" in msg and "2026-02.jsonl.gz" in msg and "固め終えた" in msg
    assert gzip.open(gz_of(repo, "2026-02"), "rt", encoding="utf-8").read().splitlines() == lines02
    assert not (exp(repo) / "2026-02").exists()
    assert (exp(repo) / "2026-03").exists()


def test_cli_failure_message_lists_archived_months(repo, capsys):
    write_many(repo, "2026-02")
    write_many(repo, "2026-03")
    (exp(repo) / "2026-03" / "notes.txt").write_text("x")
    assert main(["--archive", "--today", "2026-10-06"], root=repo) == 1
    assert "2026-02.jsonl.gz" in capsys.readouterr().err
    assert "2026-02.jsonl.gz" in (exp(repo) / "_audit.log").read_text(encoding="utf-8")


def test_dry_run_predicts_refusals_and_skips_empty(repo, capsys):
    write_many(repo, "2025-12")                      # 通常: 予定
    mk(repo, "2026-01")                              # 空: 表示しない
    write_many(repo, "2026-02")
    (exp(repo) / "2026-02" / "notes.txt").write_text("x")   # 余計なファイル: 見送り
    write_many(repo, "2026-03")                      # 見送りの後ろ: 未実行
    before = snapshot(repo)
    assert main(["--archive", "--dry-run", "--today", "2026-10-06"], root=repo) == 0
    assert snapshot(repo) == before
    out = capsys.readouterr().out
    assert "2025-12: 3 ファイルを archive/2025-12.jsonl.gz に固める予定" in out
    assert "2026-01" not in out
    assert "2026-02: 見送り(" in out and "notes.txt" in out
    assert "2026-03: 未実行" in out
    assert "見送り 1 か月" in out


def test_dry_run_predicts_gz_exists_refusal_and_resume(repo, capsys):
    import experience_archive as ea
    write_many(repo, "2026-01")
    write_many(repo, "2026-02")
    (exp(repo) / "archive").mkdir()
    ea._write_gzip(gz_of(repo, "2026-01"), b"unrelated\n")                       # 内容違い: 見送り
    files = sorted((exp(repo) / "2026-02").glob("session-*.jsonl"))
    ea._write_gzip(gz_of(repo, "2026-02"), ea._month_bytes(files))               # 一致: 後始末
    main(["--archive", "--dry-run", "--today", "2026-10-06"], root=repo)
    out = capsys.readouterr().out
    assert "2026-01: 見送り(" in out and "内容が一致しない" in out
    assert "2026-02: 未実行" in out


def test_archive_keeps_base_and_part_files_of_a_session_together_in_order(repo):
    # 1セッション = 本体 + part1, part2, part10(ファイル名順ではなく part の番号順に固める)
    d = mk(repo, "2026-03")
    order = ["session-a.jsonl", "session-a.part1.jsonl", "session-a.part2.jsonl",
             "session-a.part10.jsonl", "session-b.jsonl"]
    for name in order:
        (d / name).write_text(f'{{"f":"{name}"}}\n', encoding="utf-8")
    (gz,) = archive(repo, TODAY)
    lines = gzip.decompress(gz.read_bytes()).decode("utf-8").splitlines()
    assert lines == [f'{{"f":"{name}"}}' for name in order]


# --- WikiSkill Phase 2 Task 6: 公式 Wiki が根拠に引用している月は固めない ---------------

def write_official_wiki(repo, wiki_id, refs, name=None):
    d = repo / "docs" / "wiki"
    d.mkdir(parents=True, exist_ok=True)
    refs_line = json.dumps(refs)  # Wiki の frontmatter はリストを JSON で書く
    (d / (name or f"{wiki_id}.md")).write_text(
        f"---\nwiki_id: {wiki_id}\nstatus: approved\nsource_experience: {refs_line}\nsource_decision: []\n---\n## 知識\nx\n",
        encoding="utf-8",
    )


def audit_text(repo):
    p = exp(repo) / "_audit.log"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def test_archive_refuses_month_cited_by_official_wiki(repo, capsys):
    write_many(repo, "2026-01")
    write_official_wiki(repo, "W20260301-cited", ["session-a@2026-01-15T03:04:05Z"])
    before = snapshot(repo)
    assert main(["--archive", "--today", "2026-10-06"], root=repo) == 1
    assert snapshot(repo) == before                       # フォルダも gz も無傷
    assert not gz_of(repo, "2026-01").exists()
    err = capsys.readouterr()
    assert "archive: 月 2026-01 は Wiki W20260301-cited の根拠に引用されているため固めません(--force で強制)" in err.out + err.err


def test_dry_run_also_lists_cited_month_and_exits_1(repo, capsys):
    write_many(repo, "2026-01")
    write_many(repo, "2026-02")
    write_official_wiki(repo, "W20260301-cited", ["session-a@2026-01-15T03:04:05Z"])
    before = snapshot(repo)
    assert main(["--archive", "--dry-run", "--today", "2026-10-06"], root=repo) == 1
    assert snapshot(repo) == before
    out = capsys.readouterr()
    text = out.out + out.err
    assert "月 2026-01 は Wiki W20260301-cited の根拠に引用されているため固めません" in text
    assert "2026-02" in text


def test_archive_refuses_session_whose_file_is_in_cited_sessions_month(repo):
    # 引用の ts は 3月でも、そのセッション(a)のファイルは 1月フォルダにある(本体は最初の月に残る)。
    write_many(repo, "2026-01")
    write_official_wiki(repo, "W20260301-late", ["session-a@2026-03-01T00:00:00Z"])
    before = snapshot(repo)
    assert main(["--archive", "--today", "2026-10-06"], root=repo) == 1
    assert snapshot(repo) == before


def test_force_archives_cited_month_and_audits(repo):
    write_many(repo, "2026-01")
    write_official_wiki(repo, "W20260301-cited", ["session-a@2026-01-15T03:04:05Z"])
    assert main(["--archive", "--force", "--today", "2026-10-06"], root=repo) == 0
    assert gz_of(repo, "2026-01").exists() and not (exp(repo) / "2026-01").exists()
    log = audit_text(repo)
    assert "experience_archive" in log and "forced archive of cited month 2026-01" in log and "W20260301-cited" in log


def test_uncited_month_is_unaffected_by_wiki_guard(repo):
    write_many(repo, "2026-01")
    write_many(repo, "2026-02")
    write_official_wiki(repo, "W20260301-other", ["session-zzz@2026-02-15T03:04:05Z"])
    assert main(["--archive", "--today", "2026-10-06"], root=repo) == 1     # 2026-02 は引用されている
    # 1月だけが対象で、引用されていなければ通常どおり固まる
    (exp(repo) / "2026-02").rename(repo / "moved")
    assert main(["--archive", "--today", "2026-10-06"], root=repo) == 0
    assert gz_of(repo, "2026-01").exists() and "forced" not in audit_text(repo)


def test_no_wiki_dir_means_nothing_is_cited(repo):
    write_many(repo, "2026-01")
    assert main(["--archive", "--today", "2026-10-06"], root=repo) == 0
    assert gz_of(repo, "2026-01").exists()


def test_guard_fails_closed_when_wiki_unreadable(repo, monkeypatch, capsys):
    import wiki_schema
    write_many(repo, "2026-01")
    write_official_wiki(repo, "W20260301-cited", ["session-zzz@2026-05-15T03:04:05Z"])

    def boom(*_a, **_k):
        raise OSError("wiki boom")

    monkeypatch.setattr(wiki_schema, "iter_wiki", boom)
    before = snapshot(repo)
    assert main(["--archive", "--today", "2026-10-06"], root=repo) == 1
    assert snapshot(repo) == before
    assert "Wiki を読めない" in (lambda o: o.out + o.err)(capsys.readouterr())


def test_guard_fails_closed_on_unparseable_official_wiki(repo):
    write_many(repo, "2026-01")
    d = repo / "docs" / "wiki"
    d.mkdir(parents=True)
    (d / "W20260301-broken.md").write_bytes(b"\xff\xfe\x00 not utf-8")
    before = snapshot(repo)
    assert main(["--archive", "--today", "2026-10-06"], root=repo) == 1
    assert snapshot(repo) == before


def test_force_without_archive_is_usage_error(repo):
    assert main(["--check", "--force"], root=repo) == 2
