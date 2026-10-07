"""WikiSkill Phase 2 Task 2: knowledge_extract.py(規則ベースの知識抽出器)。

抽出器が「commit 済み・public・hojo-hq の記録だけ」から候補を作り、`docs/wiki/_candidates/` にだけ書くこと。
fixture `ex` = 一時 git リポジトリ(origin = hojo-hq)+ commit 済み Experience:
public 2セッション(同じ Skill・各 commit 1件)/ note 3行(学び: 失敗: 誤関連:)/ private 行1・repo 違い行1・
visibility の無い行1 + 議事2件(adopted / deferred)+ 失敗台帳(FK-002)。
"""
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
SCRIPT = SCRIPTS / "knowledge_extract.py"
sys.path.insert(0, str(SCRIPTS))

import knowledge_extract  # noqa: E402
from knowledge_extract import (  # noqa: E402
    collect_inputs,
    rule_decision_ruling,
    rule_failure_ledger,
    rule_note_prefix,
    rule_skill_success,
    run,
    write_candidate,
)
from wiki_schema import CANDIDATES_DIR, all_source_ids, parse_wiki_frontmatter, render_wiki, split_sections  # noqa: E402
from wiki_validate import validate_tree  # noqa: E402

PUBLIC_URL = "https://github.com/allgroup-inc/hojo-hq.git"
REPO = "allgroup-inc/hojo-hq"
ADOPTED_ID = "D20261001-merge-rule"
DEFERRED_ID = "D20261002-archive-plan"
GIT_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")

LESSON = "学び: 生成物を作り直す前に origin/main を取り込むと新しいデータを消さずに済む"
FAILURE = "失敗: 検査を通さずに配布スクリプトを走らせて禁止語を広げた"
MISRETRIEVAL = "誤関連: 締切の質問で議事の見直し期限が出てきた"

ADOPTED_TEXT = f"""---
decision_id: {ADOPTED_ID}
date: 2026-10-01
title: マージ手順の固定
status: adopted
tags: [merge]
---
# マージ手順の固定

## なぜ
競合の見落としを防ぐ。

## 三名体制の議論
- **ウタガイ**: 手順が増えると速度が落ちる

## 裁定
- マージ前に競合ファイル一覧を必ず確認してからコミットする
"""
DEFERRED_TEXT = f"""---
decision_id: {DEFERRED_ID}
date: 2026-10-02
title: 経験ログの長期保存方式
status: deferred
tags: [experience]
---
# 経験ログの長期保存方式

## なぜ
リポジトリが肥大化するおそれがある。

## 三名体制の議論
- **ウタガイ**: 圧縮すると検索できない

## 裁定
未決。Phase 3 で比較してから決める
"""
FK_ROW = ("| FK-002 | 2026-07-23 | ヒヤリハット+プロセス | mainへのマージで競合ファイル一覧を確認せず既知の2ファイルだけ解決してコミットした"
          " | 実害なし | 自己申告 | 手順が仕組み化されていない | ルール化: コミット前に競合一覧とマーカーを検査する | 横展開 | 監視中 | 2027-01-23 |")
LEDGER = ("# 失敗台帳\n\n| ID | 発生日 | 分類 | 事実経過 | 影響 | 発見経路 | 真因 | 対策(形態) | 横展開 | ステータス | 見直し/クローズ予定 |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|\n" + FK_ROW + "\n")


def git(root, *args):
    env = {k: v for k, v in os.environ.items() if k not in GIT_ENV_DROP}
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, env=env).stdout.strip()


def ev(sid, ts, event, visibility="public", repo=REPO, **extra):
    e = {"ts": ts, "session_id": sid, "event": event, "repo": repo, "visibility": visibility, "branch": "main"}
    if visibility is None:
        e.pop("visibility")
    e.update(extra)
    return e


def write_session(root, sid, events, month="2026-10"):
    p = Path(root) / ".claude/experience" / month / f"session-{sid}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events), encoding="utf-8")
    return p


def commit_all(root, msg="update"):
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", msg)


def s1_events(commits=True):
    return [
        ev("S1", "2026-10-01T01:00:00Z", "session_start", head="0" * 40, source="startup"),
        ev("S1", "2026-10-01T01:01:00Z", "skill", skill="brainstorming"),
        ev("S1", "2026-10-01T01:02:00Z", "note", text=LESSON),
        ev("S1", "2026-10-01T01:30:00Z", "session_end", tools={"Edit": 2}, skills=["brainstorming"],
           commits=[{"sha": "abc1234", "subject": "feat: 抽出器の土台を追加"}] if commits else [], duration_s=1800),
    ]


def s2_events(commits=True):
    return [
        ev("S2", "2026-10-02T01:00:00Z", "session_start", head="1" * 40, source="startup"),
        ev("S2", "2026-10-02T01:01:00Z", "skill", skill="brainstorming"),
        ev("S2", "2026-10-02T01:02:00Z", "note", text=FAILURE),
        ev("S2", "2026-10-02T01:03:00Z", "note", text=MISRETRIEVAL),
        ev("S2", "2026-10-02T01:30:00Z", "session_end", tools={"Bash": 1}, skills=["brainstorming"],
           commits=[{"sha": "def5678", "subject": "fix: 検証器の境界を直す"}] if commits else [], duration_s=1800),
    ]


PUBLIC_ROWS = len(s1_events()) + len(s2_events())


@pytest.fixture
def ex(tmp_path, monkeypatch):
    for k in GIT_ENV_DROP:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    root = tmp_path / "ex"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "t@example.com")
    git(root, "config", "user.name", "t")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "remote", "add", "origin", PUBLIC_URL)
    write_session(root, "S1", s1_events())
    write_session(root, "S2", s2_events())
    write_session(root, "P", [ev("P", "2026-10-03T00:00:00Z", "note", visibility="private",
                                 text="学び: 非公開の側で得た気づきをここに書いた")])
    write_session(root, "O", [ev("O", "2026-10-03T00:00:00Z", "note", repo="allgroup-inc/other",
                                 text="学び: 別のリポジトリで得た気づきをここに書いた")])
    write_session(root, "Q", [ev("Q", "2026-10-03T00:00:00Z", "note", visibility=None,
                                 text="学び: 公開性が分からない行の気づきをここに書いた")])
    (root / "docs/議事").mkdir(parents=True)
    (root / "docs/議事/議事_20261001_マージ手順.md").write_text(ADOPTED_TEXT, encoding="utf-8")
    (root / "docs/議事/議事_20261002_長期保存.md").write_text(DEFERRED_TEXT, encoding="utf-8")
    (root / "docs/失敗台帳.md").write_text(LEDGER, encoding="utf-8")
    (root / CANDIDATES_DIR).mkdir(parents=True)
    (root / CANDIDATES_DIR / ".gitkeep").write_text("")
    commit_all(root, "init")
    return root


# ---------------------------------------------------------------- helpers

def run_cli(root, *args):
    env = {k: v for k, v in os.environ.items() if k not in GIT_ENV_DROP + ("CLAUDE_SESSION_ID",)}
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args], cwd=str(root),
                          capture_output=True, text=True, env=env, timeout=120)


def add_untracked_session(root, sid):
    write_session(root, sid, [ev(sid, "2026-10-04T00:00:00Z", "note", text="学び: 未追跡のセッションに書いた気づき")])


def drop_commits(root, sid):
    assert sid == "S2"
    write_session(root, "S2", s2_events(commits=False))
    commit_all(root, "drop commits")


def add_note(root, text, sid="S3"):
    write_session(root, sid, [ev(sid, "2026-10-05T00:00:00Z", "note", text=text)])
    commit_all(root, "note")


def add_gakubi(root):
    p = Path(root) / "docs/学び/学び_2026-W40.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# 学び 2026-W40\n\n- 生成物を作り直す前に origin/main を取り込むと新しいデータを消さずに済む\n"
                 "- 学びノートだけにある、根拠の無い主張\n", encoding="utf-8")
    commit_all(root, "gakubi")


def load(root, rel):
    return parse_wiki_frontmatter((Path(root) / rel).read_text(encoding="utf-8"))[0]


def has_source(root, rel):
    return bool(all_source_ids(load(root, rel)))


def mark_rejected(root, rel):
    p = Path(root) / rel
    fm, body = parse_wiki_frontmatter(p.read_text(encoding="utf-8"))
    _pre, sections, _order = split_sections(body)
    fm.update(review_status="rejected", rejected_reason="テストで却下")
    p.write_text(render_wiki(fm, sections), encoding="utf-8")


def git_untracked(root):
    out = git(root, "status", "--porcelain", "--untracked-files=all")
    paths = [line[3:] for line in out.splitlines() if line.strip()]
    return [p for p in paths if not p.startswith(".claude/")]  # ロック・audit は実行時ファイル


def seed_approved_and_synonyms(root):
    fm = {"candidate_id": "K20261001-seed-0000", "title": "承認済みの別の知識(種)", "summary": "種。",
          "evidence": [{"ref": "FK-002", "quote": "競合ファイル一覧を確認せず"}], "confidence": 0.7,
          "confidence_basis": "rule=R3", "visibility": "public", "repo": REPO, "created_at": "2026-10-01T00:00:00Z",
          "proposed_by": "人", "contradictions": [], "related_wiki": [], "related_skills": [],
          "review_status": "approved", "dedup_key": "0000" + "a" * 36, "extract_run": "seed",
          "source_failure": ["FK-002"], "wiki_id": "W20261001-seed", "approved_by": "小柳(テスト)",
          "approved_at": "2026-10-01", "review_by": "2027-03-30",
          "review": {"スイシン": "a", "ウタガイ": "急ぎでは重い", "ベッカイ": "c"}}
    secs = {"## 知識": "種", "## 根拠(Provenance)": "- FK-002: 種", "## 反証(ウタガイ)": "種",
            "## 適用範囲と例外": "種", "## 関連": "なし"}
    (Path(root) / "docs/wiki/W20261001-seed.md").write_text(render_wiki(fm, secs), encoding="utf-8")
    (Path(root) / "docs/wiki/_synonyms.txt").write_text("マージ, merge\n", encoding="utf-8")
    commit_all(root, "seed")


def snapshot(root, rel):
    base = Path(root) / rel
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file()}


def unchanged_except_candidates(before, root):
    after = snapshot(root, "docs/wiki")
    for k, v in before.items():
        if after.get(k) != v:
            return False
    return all(k in before or k.startswith(CANDIDATES_DIR + "/") for k in after)


def boom(*a, **k):
    raise AssertionError("network call")


# ---------------------------------------------------------------- 入力の絞り込み

def test_reads_only_public_hojo_hq_rows(ex):
    inp = collect_inputs(ex)
    assert inp["sessions"]
    assert all(e["visibility"] == "public" and e["repo"] == "allgroup-inc/hojo-hq"
               for evs in inp["sessions"].values() for e in evs)


def test_private_and_unknown_rows_not_counted(ex):
    inp = collect_inputs(ex)
    assert inp["counts"]["experience_rows"] == PUBLIC_ROWS
    assert set(inp["sessions"]) == {"S1", "S2"}


def test_untracked_experience_ignored(ex):
    add_untracked_session(ex, "U")
    assert "U" not in collect_inputs(ex)["sessions"]


# ---------------------------------------------------------------- 規則 R1〜R4

def test_r1_needs_two_sessions_with_commits(ex):
    ds = rule_skill_success(collect_inputs(ex))
    assert len(ds) == 1 and ds[0]["related_skills"] == ["brainstorming"] and len(ds[0]["source_experience"]) == 2
    drop_commits(ex, "S2")
    assert rule_skill_success(collect_inputs(ex)) == []


def test_r2_note_prefixes(ex):
    ds = rule_note_prefix(collect_inputs(ex))
    assert len(ds) == 3 and {d["rule"] for d in ds} == {"R2"}
    assert all("Exp のみ" in d["confidence_basis"] for d in ds)


def test_r2_fullwidth_colon(ex):
    add_note(ex, "学び：全角でも拾う")
    assert any("全角" in d["summary"] for d in rule_note_prefix(collect_inputs(ex)))


def test_r3_failure_row_candidate(ex):
    d = rule_failure_ledger(collect_inputs(ex))[0]
    assert d["source_failure"] == ["FK-002"] and d["confidence"] == 0.70


def test_r4_adopted_decision_candidate(ex):
    assert any(d["source_decision"] == [ADOPTED_ID] for d in rule_decision_ruling(collect_inputs(ex)))


def test_r4_deferred_capped_confidence(ex):
    d = [d for d in rule_decision_ruling(collect_inputs(ex)) if d["source_decision"] == [DEFERRED_ID]][0]
    assert d["confidence"] <= 0.30 and "判断根拠にしない" in d["sections"]["## 適用範囲と例外"]


# ---------------------------------------------------------------- run(書込・重複排除)

def test_gakubi_is_evidence_only(ex):
    add_gakubi(ex)
    s = run(ex, include_gakubi=True)
    assert s["written"] and s["inputs"]["gakubi"] == 2
    assert all(has_source(ex, p) for p in s["written"])
    assert not any("根拠の無い主張" in (ex / p).read_text(encoding="utf-8") for p in s["written"])


def test_candidate_id_unique_in_run(ex):
    ids = [Path(p).stem for p in run(ex)["written"]]
    assert ids and len(ids) == len(set(ids))


def test_dedup_against_existing_including_rejected(ex):
    first = run(ex)
    mark_rejected(ex, first["written"][0])
    second = run(ex)
    assert second["written"] == [] and second["skipped_duplicate"] >= 1


def test_writes_only_under_candidates(ex):
    s = run(ex)
    assert s["written"]
    assert all(p.startswith("docs/wiki/_candidates/") for p in git_untracked(ex))


def test_never_touches_approved_or_synonyms(ex):
    seed_approved_and_synonyms(ex)
    before = snapshot(ex, "docs/wiki")
    run(ex)
    assert unchanged_except_candidates(before, ex)


def test_output_passes_validator(ex):
    s = run(ex)
    assert len(s["written"]) == 7 and s["rejected_by_validator"] == []
    assert validate_tree(ex)[0] == []


def test_no_llm_default_makes_no_network_call(ex, monkeypatch):
    monkeypatch.setattr(socket, "create_connection", boom)
    assert run(ex)["written"]


def test_dry_run_writes_nothing(ex):
    s = run(ex, dry_run=True)
    assert s["written"] and not list((ex / "docs/wiki/_candidates").glob("K*.md"))


def test_max_limits_output(ex):
    assert len(run(ex, max_candidates=2)["written"]) == 2


# ---------------------------------------------------------------- 追加の境界(brief 外)

def test_similar_title_in_same_run_gets_duplicate_of(ex):
    # Task 4: 「学び:」と「失敗:」の組は矛盾(conflict)として duplicate_of を付けないので、同じ接頭辞で確かめる
    add_note(ex, "学び: 生成物を作り直す前に origin/main を取り込めば新しいデータを消さない")
    s = run(ex)
    assert s["rejected_by_validator"] == [] and s["duplicate_of_marked"] >= 1
    marked = [load(ex, p) for p in s["written"] if load(ex, p).get("duplicate_of")]
    ids = {Path(p).stem for p in s["written"]}
    assert marked and all(m["duplicate_of"] in ids for m in marked)
    assert validate_tree(ex)[0] == []


def test_write_candidate_refuses_outside_candidates(ex):
    with pytest.raises(ValueError):
        write_candidate(ex, {"candidate_id": "../../x", "_sections": {}})


def test_cli_llm_is_not_implemented_exit_2(ex):
    r = run_cli(ex, "--llm")
    assert r.returncode == 2 and "未実装" in r.stderr


def test_cli_dry_run_prints_summary(ex):
    r = run_cli(ex, "--dry-run", "--max", "3", "--run-id", "t-1")
    assert r.returncode == 0, r.stderr
    s = json.loads(r.stdout)
    assert s["run_id"] == "t-1" and len(s["written"]) == 3 and s["inputs"]["experience_rows"] == PUBLIC_ROWS
    assert not list((ex / CANDIDATES_DIR).glob("K*.md"))


# ---------------------------------------------------------------- fix round 1(commit 済みの議事・台帳だけ・途中でロックを失う)

UNTRACKED_ID = "D20261003-untracked-rule"
UNTRACKED_DECISION = ADOPTED_TEXT.replace(ADOPTED_ID, UNTRACKED_ID).replace(
    "マージ前に競合ファイル一覧を必ず確認してからコミットする", "未追跡の議事に書いた裁定は候補にしない")


def test_untracked_or_uncommitted_decision_not_read(ex):
    (ex / "docs/議事/議事_20261003_未追跡.md").write_text(UNTRACKED_DECISION, encoding="utf-8")
    deferred = ex / "docs/議事/議事_20261002_長期保存.md"
    deferred.write_text(deferred.read_text(encoding="utf-8") + "\n追記(未 commit)\n", encoding="utf-8")
    inp = collect_inputs(ex)
    ids = {d["id"] for d in inp["decisions"]}
    assert ids == {ADOPTED_ID} and inp["counts"]["decisions"] == 1
    assert [d["source_decision"] for d in rule_decision_ruling(inp)] == [[ADOPTED_ID]]
    assert not any(UNTRACKED_ID in (ex / p).read_text(encoding="utf-8") for p in run(ex)["written"])
    commit_all(ex, "commit decisions")
    assert {d["id"] for d in collect_inputs(ex)["decisions"]} == {ADOPTED_ID, DEFERRED_ID, UNTRACKED_ID}


def test_uncommitted_ledger_not_read(ex):
    ledger = ex / "docs/失敗台帳.md"
    ledger.write_text(ledger.read_text(encoding="utf-8") + FK_ROW.replace("FK-002", "FK-003") + "\n", encoding="utf-8")
    inp = collect_inputs(ex)
    assert inp["failures"] == [] and "failures-uncommitted" in inp["errors"]
    assert rule_failure_ledger(inp) == []
    s = run(ex)
    assert "failures-uncommitted" in s["input_errors"] and not any("FK-" in p for p in s["written"])
    commit_all(ex, "commit ledger")
    assert [r["id"] for r in collect_inputs(ex)["failures"]] == ["FK-002", "FK-003"]


def test_untracked_ledger_not_read(ex):
    git(ex, "rm", "-q", "--cached", "docs/失敗台帳.md")
    git(ex, "commit", "-q", "-m", "untrack ledger")  # ファイルは作業ツリーに残る(未追跡)
    assert (ex / "docs/失敗台帳.md").is_file()
    inp = collect_inputs(ex)
    assert inp["failures"] == [] and "failures-uncommitted" in inp["errors"]


def test_lock_lost_mid_run_exits_1_with_partial_summary(ex, monkeypatch, capsys):
    import wikiskill_lock
    from wikiskill_lock import LockHeld

    writes = []
    real_write = knowledge_extract.write_candidate

    def counting_write(root, w):
        writes.append(w["candidate_id"])
        return real_write(root, w)

    def beat(root, name, lock, now=None):
        if writes:  # 1件書いた後で、ロックを他人に取られた
            raise LockHeld({"session_id": "R"}, 0, "lost")

    monkeypatch.setattr(wikiskill_lock, "HEARTBEAT_EVERY_S", 0)
    monkeypatch.setattr(wikiskill_lock, "heartbeat", beat)
    monkeypatch.setattr(knowledge_extract, "write_candidate", counting_write)
    code = knowledge_extract.main(["--root", str(ex)])
    s = json.loads(capsys.readouterr().out)
    assert code == 1 and s["lock_lost"] is True and len(s["written"]) == 1 and len(writes) == 1
    assert any("lock lost" in e for e in s["errors"])
    assert len(list((ex / CANDIDATES_DIR).glob("K*.md"))) == 1


def test_lock_not_lost_reports_false(ex):
    assert run(ex, dry_run=True)["lock_lost"] is False


# ---------------------------------------------------------------- Phase 2 Task 4: 矛盾の事前判定(conflict 付与)

FORBID = "生成物を作り直すときに origin/main を取り込む運用は禁止"  # LESSON と「生成物・origin・main」が重なる
FORBID_ID = "D20261004-regen-rule"
C_ID = "D20261006-no-direct-push"
NOTE_A = "学び: 自動生成した学びノートを main へ直接 push したら、PR 待ちが無く当日中に反映できた"
NOTE_B = "失敗: 自動生成物を main へ直接 push したため、禁止語を含むノートがレビュー前に公開された"
C_OUTCOME = "自動生成物は main へ直接 push しない。必ず PR を通し CI と人が見る"


def add_decision(root, outcome=FORBID, did=FORBID_ID, date_="2026-10-04", title="再生成の進め方"):
    text = (f"---\ndecision_id: {did}\ndate: {date_}\ntitle: {title}\nstatus: adopted\ntags: [wiki]\n---\n"
            f"# {title}\n\n## なぜ\n事故を防ぐ。\n\n## 三名体制の議論\n- **ウタガイ**: 遅くなる\n\n## 裁定\n{outcome}\n")
    (Path(root) / f"docs/議事/議事_{date_.replace('-', '')}_{did}.md").write_text(text, encoding="utf-8")
    commit_all(root, f"decision {did}")


def add_notes(root, *texts, sid="S3"):
    write_session(root, sid, [ev(sid, f"2026-10-05T00:0{i}:00Z", "note", text=t) for i, t in enumerate(texts)])
    commit_all(root, "notes")


def written(root, s):
    return [load(root, p) for p in s["written"]]


def conflicts(s, root=None):
    root = root or s["_root"]
    return [w for w in written(root, s) if w["review_status"] == "conflict"]


def run_ex(root, **kw):
    s = run(root, **kw)
    s["_root"] = root
    return s


def seed_abc(root):
    write_session(root, "A", [ev("A", "2026-10-05T01:00:00Z", "note", text=NOTE_A)])
    write_session(root, "B", [ev("B", "2026-10-05T02:00:00Z", "note", text=NOTE_B)])
    commit_all(root, "A and B")
    add_decision(root, outcome=C_OUTCOME, did=C_ID, date_="2026-10-06", title="自動生成物の公開経路")


def by_note(s, sid):
    root = s["_root"]
    hits = [w for w in written(root, s) if any(r.startswith(f"session-{sid}@") for r in w.get("source_experience", []))]
    assert len(hits) == 1, [w["title"] for w in hits]
    return hits[0]


def test_extractor_marks_conflict_and_records_contradiction(ex):
    add_decision(ex, outcome=FORBID)
    w = written(ex, run(ex))
    assert any(x["review_status"] == "conflict" and x["contradictions"] for x in w)
    lesson = [x for x in w if x["title"].startswith("学び: 生成物")][0]
    assert lesson["review_status"] == "conflict"
    assert {"source": FORBID_ID, "note": lesson["contradictions"][0]["note"]} in lesson["contradictions"]
    assert "Decision が否定(禁止)" in lesson["contradictions"][0]["note"]
    assert validate_tree(ex)[0] == []


def test_opposite_note_prefixes_cross_reference(ex):
    add_notes(ex, "学び: 直接 push で速く反映", "失敗: 直接 push で事故")
    ws_ = conflicts(run_ex(ex))
    assert len(ws_) == 2 and all(w["contradictions"] for w in ws_)
    a, b = ws_
    assert a["candidate_id"] in [c["source"] for c in b["contradictions"]]
    assert b["candidate_id"] in [c["source"] for c in a["contradictions"]]
    assert all("duplicate_of" not in w for w in ws_)
    assert validate_tree(ex)[0] == []


def test_a_success_b_failure_c_forbidden_c_wins(ex):  # 設計書8章の A/B/C
    seed_abc(ex)
    s = run_ex(ex)
    ka, kb_ = by_note(s, "A"), by_note(s, "B")
    assert ka["review_status"] == "conflict" and C_ID in [c["source"] for c in ka["contradictions"]]
    assert kb_["review_status"] == "conflict" and C_ID in [c["source"] for c in kb_["contradictions"]]  # 偽陽性(設計どおり)
    assert ka["candidate_id"] in [c["source"] for c in kb_["contradictions"]]
    assert kb_["candidate_id"] in [c["source"] for c in ka["contradictions"]]
    assert not list((ex / "docs/wiki").glob("*.md"))     # 何も正式にならない(自動統合しない)
    assert s["conflict"] >= 2 and validate_tree(ex)[0] == []


# ---------------------------------------------------------------- Task 4: 追加の境界(brief 外)

def test_same_prefix_notes_are_not_cross_conflict(ex):
    add_notes(ex, "学び: 直接 push で速く反映", "学び: 直接 push で手早く反映")
    assert conflicts(run_ex(ex)) == []


def test_one_unit_shared_notes_are_not_conflict(ex):
    add_notes(ex, "学び: push の前に差分を読む", "失敗: push の後で気づいた")
    assert conflicts(run_ex(ex)) == []


def test_conflict_drops_duplicate_of(ex):
    """矛盾は人が見るもの。似たタイトルの重複(duplicate_of)に畳まない。"""
    add_note(ex, "失敗: 生成物を作り直す前に origin/main を取り込まず新しいデータを消した")
    s = run_ex(ex)
    cs = conflicts(s)
    assert len(cs) == 2 and all("duplicate_of" not in w for w in cs)
    assert s["rejected_by_validator"] == [] and validate_tree(ex)[0] == []


def test_counterpart_over_max_is_referenced_by_its_source(ex):
    """相手の候補が上限で作られないときは、相手の Experience を矛盾の相手として残す(実在しない id を書かない)。"""
    add_notes(ex, "学び: 直接 push で速く反映", "失敗: 直接 push で事故")
    s = run_ex(ex, max_candidates=6)  # 確信度順 R4 → R3 → R2(古い順)。最後の「失敗:」の note があふれる
    ids = {Path(p).stem for p in s["written"]}
    cs = conflicts(s)
    assert len(cs) == 1 and s["over_max"] >= 1
    src = [c["source"] for c in cs[0]["contradictions"]]
    assert all(x in ids or x.startswith("session-") for x in src)
    assert validate_tree(ex)[0] == []


def test_decision_conflict_check_failure_fails_closed(ex, monkeypatch):
    import wiki_schema

    def boom(*a, **k):
        raise RuntimeError("conflict boom")

    monkeypatch.setattr(wiki_schema, "decision_conflicts", boom)
    s = run(ex, dry_run=True)
    assert s["written"] == []  # 判定できない候補は書かない(V12 で検証器が止める)
    assert {"V12"} <= {c for r in s["rejected_by_validator"] for c in r["codes"]}
