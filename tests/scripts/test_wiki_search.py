"""WikiSkill M1: 読み取り専用の検索(合成データ・外部接続なし)。

一時的な git リポジトリ(公開リポの remote を付ける)に、議事・失敗台帳・候補 Wiki を作って検査する。
- 出るもの: 公開の採用 Decision、失敗台帳(FK)、承認済みの正式 Wiki
- 出ないもの: private・superseded・試験用の Decision、候補 Wiki、conflict、_archive、_ で始まるページ
- 書き込みをしない(リポジトリの中身も監査ログも変わらない)
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

import memory_bootstrap as mb  # noqa: E402
import wiki_search as wsearch  # noqa: E402

PUBLIC_URL = "https://github.com/allgroup-inc/hojo-hq.git"


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"})


def _decision(root, name, fm_extra, body_title):
    fm = {"decision_id": name.split("_")[1] if "_" in name else name, "date": "2026-01-01",
          "title": body_title, "status": "adopted", "review_by": "2026-12-01",
          "decided_by": "小柳", **fm_extra}
    lines = ["---"] + [f"{k}: {v}" for k, v in fm.items()] + ["---", "",
             f"# {body_title}", "", "## なぜ(背景)", "締切アラートの案内時期を決めるため。", "",
             "## 前提", "利用者はLINE登録済み。", "",
             "## 三名体制の議論", "- **スイシン(推進)**: 進める。",
             "- **ウタガイ(懐疑・反対理由。必須)**: 30日前は早すぎて忘れられる。",
             "- **ベッカイ(別解・前提を疑う)**: 別の時期も検討。", "",
             "## 裁定", "締切の約1か月前から案内する。", "", "## 見直し条件", "件数が変わったら見直す。", ""]
    p = root / "docs" / "議事" / f"議事_{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "hojo-hq"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "remote", "add", "origin", PUBLIC_URL)
    _decision(root, "20260101_締切アラート案内", {"decision_id": "D20260101-deadline",
              "tags": "[アラート, 締切]"}, "締切アラートの案内時期")
    _decision(root, "20260102_社内限定", {"decision_id": "D20260102-internal", "visibility": "private",
              "tags": "[アラート]"}, "社内限定のアラート方針")
    _decision(root, "20260103_旧案", {"decision_id": "D20260103-old", "status": "superseded",
              "tags": "[アラート]"}, "旧アラート案")
    _decision(root, "20260104_試験", {"decision_id": "D20260104-test", "tags": "[test, アラート]"},
              "受け入れ試験: アラート")
    (root / "docs" / "失敗台帳.md").write_text(
        "# 失敗台帳\n\n| ID | 日付 | 分類 | 事実 | 影響 | 発見 | 原因 | 対策 |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| FK-001 | 2026-01-05 | 事故 | 締切アラートの送信ミス | 高 | 本人 | 確認不足 | 送信前に二重確認 |\n",
        encoding="utf-8")
    cand = root / "docs" / "wiki" / "_candidates"
    cand.mkdir(parents=True)
    (cand / "K20260101-deadline-aaaa.md").write_text(
        "---\ncandidate_id: K20260101-deadline-aaaa\ntitle: 候補専用語を含む候補\nstatus: candidate\n---\n"
        "## 知識\n候補専用語のテスト。\n", encoding="utf-8")
    (cand / "K20260102-conflict-bbbb.md").write_text(
        "---\ncandidate_id: K20260102-conflict-bbbb\ntitle: 矛盾の候補\nstatus: conflict\n---\n"
        "## 知識\n矛盾専用語のテスト。\n", encoding="utf-8")
    arch = root / "docs" / "wiki" / "_archive"
    arch.mkdir(parents=True)
    (arch / "W20260101-old.md").write_text("---\ntitle: 退役\n---\n## 知識\n退役専用語。\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture")
    return root


def _ids(report):
    return [r["id"] for r in report["results"]]


def test_finds_adopted_decision_and_failure(repo):
    rep = wsearch.search(repo, "締切 アラート")
    ids = _ids(rep)
    assert "D20260101-deadline" in ids
    assert "FK-001" in ids


def test_failure_only_kind(repo):
    rep = wsearch.search(repo, "送信ミス", kinds=("failure",))
    assert _ids(rep) == ["FK-001"]
    assert all(r["kind"] == "failure" for r in rep["results"])


def test_private_decision_never_returned(repo):
    assert "D20260102-internal" not in _ids(wsearch.search(repo, "社内限定 アラート"))


def test_superseded_and_test_decisions_never_returned(repo):
    ids = _ids(wsearch.search(repo, "旧アラート 試験 アラート", limit=10))
    assert "D20260103-old" not in ids
    assert "D20260104-test" not in ids


def test_candidates_conflicts_and_archive_never_returned(repo):
    assert _ids(wsearch.search(repo, "候補専用語")) == []
    assert _ids(wsearch.search(repo, "矛盾専用語")) == []
    assert _ids(wsearch.search(repo, "退役専用語")) == []


def test_private_repo_hides_every_decision(tmp_path):
    root = tmp_path / "other"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "remote", "add", "origin", "https://github.com/example-org/private-sample.git")
    _decision(root, "20260101_x", {"decision_id": "D20260101-x"}, "非公開リポの決定")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "fixture")
    assert [r for r in wsearch.search(root, "非公開リポ")["results"] if r["kind"] == "decision"] == []


def test_official_wiki_layer_keeps_only_direct_approved_pages(repo, monkeypatch):
    def fake_wiki(root):
        base = {"kind": "wiki", "label": "[Wiki]", "date": "", "text": "共通語 承認", "match_title": "",
                "body": "共通語 承認", "score": 0, "title": "t", "line": "- [Wiki] 共通語"}
        return [{**base, "id": "W1", "path": "docs/wiki/W1-ok.md"},
                {**base, "id": "K1", "path": "docs/wiki/_candidates/K1.md"},
                {**base, "id": "W0", "path": "docs/wiki/_archive/W0.md"},
                {**base, "id": "_d", "path": "docs/wiki/_draft.md"},
                {**base, "id": "W2", "path": "docs/wiki/sub/W2.md"}]
    monkeypatch.setattr(mb, "_wiki", fake_wiki)
    rep = wsearch.search(repo, "共通語", kinds=("wiki",), limit=10)
    assert _ids(rep) == ["W1-ok"]


def test_no_terms_returns_empty_report(repo):
    rep = wsearch.search(repo, "   ")
    assert rep["terms"] == [] and rep["results"] == []


def test_limit_applies_per_kind(repo):
    rep = wsearch.search(repo, "アラート", kinds=("decision",), limit=1)
    assert len([r for r in rep["results"] if r["kind"] == "decision"]) <= 1


def _tree_digest(root):
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if ".git" in p.parts or "__pycache__" in p.parts or not p.is_file():
            continue
        h.update(str(p.relative_to(root)).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def test_search_writes_nothing(repo):
    before = _tree_digest(repo)
    wsearch.search(repo, "締切 アラート")
    wsearch.search(repo, "送信ミス", kinds=("failure",))
    assert _tree_digest(repo) == before
    assert not (repo / ".claude" / "experience" / "_audit.log").exists()


def test_json_output_and_cli_arguments(repo, capsys):
    assert wsearch.main(["締切", "--root", str(repo), "--json", "--limit", "2"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out) >= {"query", "terms", "wiki_available", "results"}


def test_unknown_kind_is_rejected(repo):
    with pytest.raises(SystemExit):
        wsearch.main(["締切", "--root", str(repo), "--kind", "candidate"])


def test_empty_repository_is_safe(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "remote", "add", "origin", PUBLIC_URL)
    rep = wsearch.search(root, "締切")
    assert rep["results"] == []


def test_results_show_human_ids(repo):
    rep = wsearch.search(repo, "締切 アラート 送信ミス", limit=5)
    ids = {r["kind"]: set() for r in rep["results"]}
    for r in rep["results"]:
        ids[r["kind"]].add(r["id"])
    assert "D20260101-deadline" in ids.get("decision", set())
    assert "FK-001" in ids.get("failure", set())
    assert all(not i.startswith("docs/") for i in ids.get("failure", set()))
