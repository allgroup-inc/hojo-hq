"""WikiSkill M3 / Component F: Skill Proposer の検査(合成データ・外部接続なし)。

一時的な git リポジトリに、Skill・失敗台帳・決定・Experience を作って検査する。
- 根拠の数え方(0件・1件・2件以上、種類の数)、公開範囲、未承認の決定、曖昧な名前
- 観測されていない失敗数・成功率を根拠に使わないこと、利用実績0件の明示、版の変更の扱い
- ドライランは書かない。保存は docs/proposals の中の1件だけ。既存は上書きしない
- Skill 本体・既存の記録は変わらない。機密の検査で止まる
"""
import hashlib
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import skill_proposer as sp  # noqa: E402

PUBLIC_URL = "https://github.com/allgroup-inc/hojo-hq.git"
PRIVATE_URL = "https://github.com/example-org/private-sample.git"
TODAY = dt.date(2026, 10, 15)
LEDGER_HEADER = ("# 失敗台帳\n\n| ID | 日付 | 分類 | 事実 | 影響 | 発見 | 原因 | 対策 |\n"
                 "|---|---|---|---|---|---|---|---|\n")


def _git(root, *args, env=None):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com", **(env or {})})


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _skill(root, name, body="確認用の本文。\n"):
    _write(root, f".claude/skills/{name}/SKILL.md", f"---\nname: {name}\ndescription: 確認用\n---\n{body}")


def _ledger(root, rows):
    _write(root, "docs/失敗台帳.md", LEDGER_HEADER + "".join(rows))


def _row(fid, fact, date="2026-10-02"):
    return f"| {fid} | {date} | 手順 | {fact} | 中 | 本人 | 確認不足 | 対策を確認 |\n"


def _decision(root, name, decision_id, title, why="なぜの本文の一文。", status="adopted",
              tags="[計画, 手順]", visibility=None, review_by="2027-04-01"):
    lines = ["---", f"decision_id: {decision_id}", "date: 2026-10-01", f"title: {title}"]
    if status is not None:
        lines.append(f"status: {status}")
    lines += [f"review_by: {review_by}", f"tags: {tags}"]
    if visibility is not None:
        lines.append(f"visibility: {visibility}")
    lines += ["---", f"# 議事: {title}", "", "## なぜ", why, "", "## 裁定", "方針を決めた。", ""]
    _write(root, f"docs/議事_{name}.md", "\n".join(lines))


def _observe(root, failure=True):
    """PostToolUseFailure を登録した履歴(2026-10-01)と、登録後の Skill 呼び出しを作る(公開リポ)。"""
    _write(root, ".claude/settings.json", '{"hooks": {"PostToolUseFailure": []}}\n')
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "フック登録",
         env={"GIT_AUTHOR_DATE": "2026-10-01T00:00:00+09:00", "GIT_COMMITTER_DATE": "2026-10-01T00:00:00+09:00"})
    d = root / ".claude" / "experience" / "2026-10"
    d.mkdir(parents=True, exist_ok=True)
    base = {"session_id": "s-obs", "repo": "allgroup-inc/hojo-hq", "visibility": "public", "branch": "main"}
    events = [
        {**base, "event": "skill", "ts": "2026-10-06T01:00:00Z", "skill": "writing-plans"},
        {**base, "event": "skill", "ts": "2026-10-06T02:00:00Z", "skill": "writing-plans"},
    ]
    if failure:
        events.append({**base, "event": "skill_failure", "ts": "2026-10-06T03:00:00Z", "skill": "writing-plans"})
    (d / "session-s-obs.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events),
                                           encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "記録")


def _base_repo(tmp_path, url=PUBLIC_URL):
    root = tmp_path / "hojo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "remote", "add", "origin", url)
    _skill(root, "writing-plans")
    _skill(root, "review")
    _ledger(root, [])
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _digest(root):
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        rel = p.relative_to(root)
        if ".git" in rel.parts or "__pycache__" in rel.parts or "proposals" in rel.parts or not p.is_file():
            continue
        h.update(str(rel).encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def _is_proposal(out):
    """提案書が出たか(提案書は見出しで始まる。判定不能のときは判定の行だけが出る)。"""
    return out.startswith("# Skill改善提案(未検証)")


def _run(root, *args):
    return sp.main(["--root", str(root), "--date", TODAY.isoformat(), *args])


def test_zero_evidence_is_undecidable_and_writes_nothing(tmp_path, capsys):
    root = _base_repo(tmp_path)
    assert _run(root, "--skill", "writing-plans") == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and "根拠が0件" in out
    assert not (root / "docs" / "proposals").exists()


def test_single_ledger_mention_is_not_enough(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _ledger(root, [_row("FK-101", "writing-plans の計画粒度が粗かった")])
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "台帳")
    assert _run(root, "--skill", "writing-plans") == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and "FK-101" in out and "独立した根拠が1件" in out


def test_ledger_plus_adopted_public_decision_makes_a_proposal(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _ledger(root, [_row("FK-101", "writing-plans の計画粒度が粗かった")])
    _decision(root, "20261001_計画粒度", "D-20261001-01", "writing-plans の計画粒度を上げる")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "台帳と決定")
    assert _run(root, "--skill", "writing-plans") == 0
    out = capsys.readouterr().out
    assert _is_proposal(out)
    assert "FK-101" in out and "D-20261001-01" in out
    assert "原因とは断定しない" in out            # 台帳の本文に名前が出るだけでは原因と断定しない
    assert "未検証" in out and "G(Skill Validator)" in out
    assert "改善効果は確認していません" in out
    assert "2026-10-02" in out                    # 記録日


def test_two_ledger_mentions_of_one_kind_are_undecidable(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _ledger(root, [_row("FK-101", "writing-plans の計画粒度が粗かった"),
                   _row("FK-102", "writing-plans の手順が抜けた")])
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "台帳2件")
    assert _run(root, "--skill", "writing-plans") == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and "根拠の種類が1種類" in out


def test_ambiguous_common_word_is_reference_only(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _ledger(root, [_row("FK-201", "review の観点が抜けた")])
    _decision(root, "20261002_レビュー", "D-20261002-01", "レビューの観点", why="review の方針。")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "曖昧")
    assert _run(root, "--skill", "review") == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and "弱い" in out


def test_private_decision_is_never_shown(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _ledger(root, [_row("FK-101", "writing-plans の計画粒度が粗かった")])
    _decision(root, "20261001_社内", "D-PRIV-77", "社内限定の writing-plans 方針", visibility="private")
    _decision(root, "20261001_公開", "D-20261001-01", "公開の writing-plans 計画粒度方針")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "混在")
    assert _run(root, "--skill", "writing-plans") == 0
    out = capsys.readouterr().out
    assert "D-PRIV-77" not in out and "社内限定" not in out     # 存在も出さない
    assert "D-20261001-01" in out


def test_non_adopted_decisions_are_reference_only(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _ledger(root, [_row("FK-101", "writing-plans の計画粒度が粗かった")])
    _decision(root, "20261003_保留", "D-20261003-01", "保留中の writing-plans 案", status="deferred")
    _decision(root, "20261004_未記入", "D-20261004-01", "状態未記入の writing-plans 案", status=None)
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "未確定")
    assert _run(root, "--skill", "writing-plans") == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out                      # 未確定の決定は根拠に数えない
    assert "状態が『deferred』" in out and "状態が『unknown』" in out


def test_superseded_and_test_tagged_decisions_are_excluded(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _decision(root, "20261005_旧", "D-OLD-01", "旧 writing-plans 方針", status="superseded")
    _decision(root, "20261006_試験", "D-TEST-01", "試験 writing-plans 方針", tags="[test, 計画]")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "除外")
    assert _run(root, "--skill", "writing-plans") == 0
    out = capsys.readouterr().out
    assert "D-OLD-01" not in out and "D-TEST-01" not in out


def test_zero_usage_is_stated_and_unobserved_failures_are_not_used(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _ledger(root, [_row("FK-101", "writing-plans の計画粒度が粗かった")])
    _decision(root, "20261001_計画粒度", "D-20261001-01", "writing-plans の計画粒度を上げる")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "台帳と決定")
    assert _run(root, "--skill", "writing-plans") == 0
    out = capsys.readouterr().out
    assert "利用実績: 0 件" in out
    assert "観測期間なし" in out and "failure_count と success_rate は根拠に使っていません" in out


def test_observed_failure_counts_as_metric_evidence(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _observe(root, failure=True)
    _ledger(root, [_row("FK-101", "writing-plans の計画粒度が粗かった")])
    _decision(root, "20261001_計画粒度", "D-20261001-01", "writing-plans の計画粒度を上げる")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "観測と台帳")
    assert _run(root, "--skill", "writing-plans") == 0
    out = capsys.readouterr().out
    assert _is_proposal(out)
    assert "Skill Metrics(観測済み)" in out and "利用実績: 2 件" in out


def test_no_failure_in_observed_period_is_not_treated_as_zero_failures(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _observe(root, failure=False)                       # 観測はあるが失敗は記録されていない
    _ledger(root, [_row("FK-101", "writing-plans の計画粒度が粗かった")])
    _decision(root, "20261001_計画粒度", "D-20261001-01", "writing-plans の計画粒度を上げる")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "観測のみ")
    assert _run(root, "--skill", "writing-plans") == 0
    out = capsys.readouterr().out
    assert "Skill Metrics(観測済み)" not in out          # 0件の観測を、失敗なしの根拠にしない
    assert _is_proposal(out)                       # 台帳と決定の2種類で成立する


def test_version_history_alone_is_not_evidence(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _skill(root, "writing-plans", body="改善版の本文。\n")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "改善")
    assert _run(root, "--skill", "writing-plans") == 0
    out = capsys.readouterr().out
    assert "判定: **判定不能**" in out and "改善効果の証明にはならない" in out


def test_dry_run_prints_and_writes_nothing(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _ledger(root, [_row("FK-101", "writing-plans の計画粒度が粗かった")])
    _decision(root, "20261001_計画粒度", "D-20261001-01", "writing-plans の計画粒度を上げる")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "台帳と決定")
    before = _digest(root)
    assert _run(root, "--skill", "writing-plans") == 0
    captured = capsys.readouterr()
    assert "# Skill改善提案(未検証): writing-plans" in captured.out
    assert "ドライラン" in captured.err
    assert not (root / "docs" / "proposals").exists()
    assert _digest(root) == before


def test_save_writes_exactly_one_file_under_proposals(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _ledger(root, [_row("FK-101", "writing-plans の計画粒度が粗かった")])
    _decision(root, "20261001_計画粒度", "D-20261001-01", "writing-plans の計画粒度を上げる")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "台帳と決定")
    before = _digest(root)
    assert _run(root, "--skill", "writing-plans", "--save") == 0
    target = root / "docs" / "proposals" / "proposal-20261015-writing-plans.md"
    assert target.is_file()
    assert sorted(p.name for p in (root / "docs" / "proposals").iterdir()) == [target.name]
    assert target.read_text(encoding="utf-8").startswith("# Skill改善提案(未検証): writing-plans")
    assert _digest(root) == before                      # 提案書以外は変わらない


def test_save_refuses_overwrite(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _ledger(root, [_row("FK-101", "writing-plans の計画粒度が粗かった")])
    _decision(root, "20261001_計画粒度", "D-20261001-01", "writing-plans の計画粒度を上げる")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "台帳と決定")
    assert _run(root, "--skill", "writing-plans", "--save") == 0
    target = root / "docs" / "proposals" / "proposal-20261015-writing-plans.md"
    first = target.read_text(encoding="utf-8")
    assert _run(root, "--skill", "writing-plans", "--save") == sp.EXIT_SAVE_REFUSED
    assert target.read_text(encoding="utf-8") == first


def test_save_is_not_done_when_undecidable(tmp_path, capsys):
    root = _base_repo(tmp_path)
    assert _run(root, "--skill", "writing-plans", "--save") == 0
    assert not (root / "docs" / "proposals").exists()
    assert "保存しません" in capsys.readouterr().err


def test_unknown_or_unsafe_skill_names_are_refused(tmp_path, capsys):
    root = _base_repo(tmp_path)
    before = _digest(root)
    assert _run(root, "--skill", "no-such-skill", "--save") == sp.EXIT_USAGE
    assert _run(root, "--skill", "../writing-plans", "--save") == sp.EXIT_USAGE
    assert not (root / "docs" / "proposals").exists()
    assert _digest(root) == before


def test_secret_scan_blocks_and_names_only_the_rule(tmp_path, capsys, monkeypatch):
    root = _base_repo(tmp_path)
    _ledger(root, [_row("FK-101", "writing-plans の計画粒度が粗かった")])
    _decision(root, "20261001_計画粒度", "D-20261001-01", "writing-plans の計画粒度を上げる")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "台帳と決定")
    original = sp.render_proposal
    monkeypatch.setattr(sp, "render_proposal",
                        lambda g, today: original(g, today) + "\n参照: https://example.invalid/leak\n")
    assert _run(root, "--skill", "writing-plans", "--save") == sp.EXIT_SECRET
    err = capsys.readouterr().err
    assert "url" in err and "example.invalid" not in err
    assert not (root / "docs" / "proposals").exists()


def test_scan_text_detects_each_rule_without_echoing(tmp_path):
    assert sp.scan_text("普通の日本語の文章。") == []
    assert "email" in sp.scan_text("連絡先 someone@example.com")
    assert "session_id" in sp.scan_text("session-abc123def")
    assert "ipv4" in sp.scan_text("host 10.1.2.3")
    assert "absolute_path" in sp.scan_text("see /home/user/x")
    assert "token_like" in sp.scan_text("k=" + "A" * 40)


def test_proposal_never_copies_ledger_or_decision_text(tmp_path, capsys):
    root = _base_repo(tmp_path)
    _ledger(root, [_row("FK-101", "秘密の事実テキストが writing-plans にあった")])
    _decision(root, "20261001_計画粒度", "D-20261001-01", "writing-plans の計画粒度を上げる", why="なぜ本文の一文です。")
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "転記しない")
    assert _run(root, "--skill", "writing-plans") == 0
    out = capsys.readouterr().out
    assert _is_proposal(out)
    assert "秘密の事実テキスト" not in out and "なぜ本文の一文" not in out


def test_missing_ledger_is_zero_evidence_not_a_crash(tmp_path, capsys):
    root = _base_repo(tmp_path)
    (root / "docs" / "失敗台帳.md").unlink()
    _git(root, "add", "-A"); _git(root, "commit", "-q", "-m", "台帳なし")
    assert _run(root, "--skill", "writing-plans") == 0
    assert "判定: **判定不能**" in capsys.readouterr().out


def test_word_boundaries_for_skill_names():
    assert sp.mentions("the writing-plans skill", "writing-plans")
    assert not sp.mentions("writing-plans-hojo", "writing-plans")
    assert not sp.mentions("superpowers:writing-plansX", "writing-plans")
    assert sp.mentions("計画は writing-plans で作る", "writing-plans")


def test_real_repo_dry_run_is_read_only_and_well_formed(capsys):
    before = _digest(ROOT)
    assert sp.main(["--root", str(ROOT), "--skill", "writing-plans", "--date", TODAY.isoformat()]) in (0, 3)
    capsys.readouterr()
    assert _digest(ROOT) == before
