"""check_public_exposure.py(公開情報検査・警告モード)のテスト。

すべて合成データ。完成した値をこのファイルに書かないよう、値は実行中に組み立てる
(書くと、このテスト自体が公開情報検査に引っかかるため)。
一時リポジトリ(git init)の中で CLI を実際に動かし、CI と同じ「ファイルを直に実行」する経路も確かめる。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_public_exposure.py"
sys.path.insert(0, str(ROOT / "scripts"))

import check_public_exposure as cpe  # noqa: E402

AT = "@"
SYN = {
    "R1": "https://script.google.com/macros/s/" + "AKfy" + "q" * 30 + "/exec",
    "R2": "https://docs.google.com/spreadsheets/d/" + "1Z" + "k" * 30 + "/edit",
    "R3": "jiro.synthetic" + AT + "gmail.com",
    "R4": "saburo.synthetic" + AT + "g-low.co.jp",
    "R5": "080-" + "7531" + "-" + "8642",
    "R6": "U" + "7c2e" * 8,
    "R7": "x" + "ox" + "b-" + "9" * 14,
    "R8": "-----BEGIN " + "PRIVATE KEY-----",
    "R9": "https://someone:" + "pass" + AT + "example.org/path",
    "R10": "Bear" + "er " + "w" * 24,
    "R11": "https://hooks.slack.com/services/" + "T1/B1/" + "y" * 20,
}


def rules_of(text):
    return {rid for rid, _ in cpe.scan_text(text)}


@pytest.mark.parametrize("rid", sorted(SYN, key=lambda r: int(r[1:])))
def test_each_rule_detects_its_synthetic_value(rid):
    assert rules_of("前の文 " + SYN[rid] + " 後の文") == {rid}


def test_every_rule_has_a_positive_case():
    # 規則を足したのにテストを足し忘れると、その規則は検査されないまま通る
    assert set(SYN) == set(cpe.RULE_NAMES)


@pytest.mark.parametrize("text", [
    "info" + AT + "g-low.co.jp",                              # 窓口用
    "noreply" + AT + "g-low.co.jp",
    "090-" + "1111" + "-" + "2222",                            # 同じ数字の繰り返し
    "080" + "1234" + "5678",                                   # 1234・5678
    "U" + "0123456789abcdef" * 2,                              # 連番
    "U" + "a" * 32,
    "法人番号 3" + "070" + "97531864" + "2",                    # 13桁の数字の一部
    "https://script.google.com/home",                          # 識別子の無いURL
    "https://docs.google.com/spreadsheets/d/<台帳ID>/edit",     # 伏せ字
    "max-width:100%; 締切の約1か月前から",                       # FK-001 の型
    "沖縄県の企業、補助金・助成金の情報です。",                    # 日本語の本文(2026-09-25 の型)
    "taro" + AT + "example.com",                               # 個人向けサービスではない
])
def test_does_not_flag_synthetic_or_unrelated_text(text):
    assert rules_of(text) == set()


def test_free_mail_domain_must_end_there():
    assert rules_of("a" + AT + "gmail.com.example.net") == set()


def test_line_numbers_are_reported_not_values():
    text = "1行目\n2行目 " + SYN["R3"] + "\n3行目\n4行目 " + SYN["R5"] + "\n"
    assert sorted(cpe.scan_text(text)) == [("R3", 2), ("R5", 4)]


def test_compare_separates_new_existing_and_decreased():
    findings = {"docs/a.md": {"R3": [1, 5, 9]}, "docs/b.md": {"R1": [2]}}
    baseline = {"docs/a.md": {"R3": 2}, "docs/gone.md": {"R4": 1}}
    new, existing, decreased = cpe.compare_with_baseline(findings, baseline)
    assert [(p, r, n) for p, r, n, _ in new] == [("docs/a.md", "R3", 1), ("docs/b.md", "R1", 1)]
    assert existing == []
    assert decreased == [("docs/gone.md", "R4", 1)]


def test_skip_classification_is_explicit():
    assert cpe.classify_path("docs/note.md") is None
    assert "data/" in cpe.classify_path("data/list.json")
    assert cpe.classify_path(".claude/experience/2026-10/session-x.jsonl") is not None
    assert cpe.classify_path("site/guide.PDF") is not None


# ---- 一時リポジトリで CLI を動かす ----

def make_repo(tmp_path, files):
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    return tmp_path


def run_cli(repo, *args, env_extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GITHUB_")}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], cwd=repo,
                          capture_output=True, text=True, env=env)


def all_values():
    return list(SYN.values())


def assert_no_values(text):
    for value in all_values():
        assert value not in text


def test_cli_warn_mode_reports_new_but_exits_zero(tmp_path):
    repo = make_repo(tmp_path, {"docs/memo.md": "連絡先 " + SYN["R3"] + "\n"})
    r = run_cli(repo)
    assert r.returncode == 0
    assert "新規の一致: 1件" in r.stdout
    assert "BASELINE" in r.stdout and "すべての一致を新規として扱います" in r.stdout
    assert "docs/memo.md" in r.stdout
    assert_no_values(r.stdout + r.stderr)


def test_cli_strict_mode_fails_only_on_new(tmp_path):
    repo = make_repo(tmp_path, {"docs/memo.md": SYN["R3"] + "\n"})
    assert run_cli(repo, "--strict").returncode == 1
    assert run_cli(repo, "--write-baseline").returncode == 0
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    r = run_cli(repo, "--strict")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "新規の一致: 0件 / 既存の一致: 1件" in r.stdout
    # 既存と同じファイルに1件増えたら新規
    (repo / "docs/memo.md").write_text(SYN["R3"] + "\n" + SYN["R3"] + "\n", encoding="utf-8")
    r = run_cli(repo, "--strict")
    assert r.returncode == 1
    assert "+1件" in r.stdout
    assert_no_values(r.stdout + r.stderr)


def test_baseline_file_contains_counts_only(tmp_path):
    repo = make_repo(tmp_path, {"docs/a.md": SYN["R3"] + " " + SYN["R1"] + "\n"})
    assert run_cli(repo, "--write-baseline").returncode == 0
    raw = (repo / cpe.BASELINE_PATH).read_text(encoding="utf-8")
    assert_no_values(raw)
    data = json.loads(raw)
    assert data["schema"] == 1
    assert data["counts"] == {"docs/a.md": {"R1": 1, "R3": 1}}


def test_skipped_files_are_reported_as_unchecked_not_clean(tmp_path):
    repo = make_repo(tmp_path, {
        "docs/ok.md": "本文\n",
        "data/list.json": '{"tel": "' + SYN["R5"] + '"}',
        "site/guide.pdf": b"%PDF-1.4 " + SYN["R3"].encode(),
        "img/x.bin": b"\x00\x01" + SYN["R3"].encode(),
    })
    r = run_cli(repo)
    assert r.returncode == 0
    assert "新規の一致: 0件" in r.stdout
    assert "[未検査]" in r.stdout and "安全とは判断していません" in r.stdout
    assert "対象外の場所(data/)" in r.stdout
    assert "画像・PDF" in r.stdout
    assert "バイナリ" in r.stdout
    assert_no_values(r.stdout)


def test_decreased_is_reported(tmp_path):
    repo = make_repo(tmp_path, {"docs/a.md": SYN["R4"] + "\n"})
    run_cli(repo, "--write-baseline")
    (repo / "docs/a.md").write_text("(非公開側を参照)\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    r = run_cli(repo, "--strict")
    assert r.returncode == 0
    assert "[減少]" in r.stdout and "-1件" in r.stdout


def test_zero_scanned_files_is_an_error(tmp_path):
    repo = make_repo(tmp_path, {"site/only.png": b"\x89PNG\r\n"})
    r = run_cli(repo)
    assert r.returncode == 2
    assert "0件" in r.stderr


def test_broken_baseline_is_an_error_not_a_pass(tmp_path):
    repo = make_repo(tmp_path, {"docs/a.md": "本文\n",
                                cpe.BASELINE_PATH: json.dumps({"schema": 1, "counts": {"docs/a.md": {"R99": 1}}})})
    r = run_cli(repo)
    assert r.returncode == 2
    assert "BASELINE" in r.stderr


def test_outside_git_is_an_error(tmp_path):
    (tmp_path / "a.md").write_text("本文\n", encoding="utf-8")
    r = run_cli(tmp_path)
    assert r.returncode == 2


def test_actions_annotations_and_summary_have_no_values(tmp_path):
    repo = make_repo(tmp_path, {"docs/x,y.md": "a\n" + SYN["R1"] + "\n"})
    summary = tmp_path / "summary.md"
    env = {"GITHUB_ACTIONS": "true", "GITHUB_STEP_SUMMARY": str(summary)}
    r = run_cli(repo, env_extra=env)
    assert r.returncode == 0
    assert "::warning file=docs/x%2Cy.md,line=2::" in r.stdout
    r_strict = run_cli(repo, "--strict", env_extra=env)
    assert "::error file=" in r_strict.stdout
    body = summary.read_text(encoding="utf-8")
    assert "公開情報検査" in body
    assert_no_values(r.stdout + r_strict.stdout + body)


def test_selftest_passes_when_run_as_a_file():
    r = subprocess.run([sys.executable, "-I", str(SCRIPT), "--selftest"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "自己点検OK" in r.stdout


def test_new_files_of_this_change_do_not_trip_the_check():
    paths = ["scripts/check_public_exposure.py", "tests/scripts/test_check_public_exposure.py",
             ".github/workflows/public-exposure.yml"]
    os.chdir(ROOT)
    findings, skipped, scanned = cpe.scan_paths([p for p in paths if (ROOT / p).exists()])
    assert scanned >= 2
    assert findings == {}
