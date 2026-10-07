"""WikiSkill Phase 2 Task 8: 自動 E2E(順方向 + 逆方向)。

順方向: Session A の経験(`学び:` の note)→ 抽出器の候補 → 検証器 → 人の承認(frontmatter の編集と `git mv`)
→ まったく別の Session B の段1に、[Wiki] の「何を知っているか」(title・summary)と
「なぜ信頼しているか」(根拠件数・承認者・承認日・パス)が出る。
逆方向: 採用済み Decision と逆向きの経験 → conflict の候補 → 昇格しようとしても検証で止まる → 注入されない。

Phase 1 の world / world_private fixture と hook()(wikiskill-hook.sh を Claude Code と同じ stdin JSON で呼ぶ)を
そのまま使う。抽出器・検証器・Experience Logger は world に複製したスクリプトを subprocess で呼ぶ
(このプロセスに実リポジトリのモジュールを読み込まない)。
実セッション(Claude Code 本体)での A→B→C は docs/wikiskill/Phase2受け入れ記録.md に別途記録する。
"""
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_wikiskill_memory_e2e import (  # noqa: E402,F401 — fixture は名前を取り込めば pytest が使う
    _context,
    git,
    hook,
    read_session,
    world,
    world_private,
    write,
)

TODAY = date.today().isoformat()
APPROVER = "小柳(テスト)"
APPROVED_AT = "2026-10-20"
LESSON = "学び: 生成物を作り直す前に origin/main を取り込むと、新しいデータを消さずに済む"
APPROVED_TITLE = LESSON  # R2 の候補の title は「学び: <本文>」
# 段1の検索語(ブランチ・commit 件名)に Wiki の語(生成物・データ)を載せる。Phase 1 E2E の COMMIT_SUBJECT と同じ考え方
PROMOTE_SUBJECT = "docs: wiki 昇格(生成物を作り直す前に新しいデータを取り込む)"
# 承認済みの Wiki と逆向きの、後から採用された Decision(否定語「しない」+ 生成物・データ・手順が重なる)
OPPOSITE = "生成物を作り直すときに新しいデータを取り込む手順は使わない。この手順は採用しない"
WRONG = "学び: 自動生成物を main へ直接 push したら当日中に反映できた"


# ---------------------------------------------------------------- helpers

def _env(world):
    """hook() と同じく、親セッション(Claude Code / git)由来の環境変数を持ち込まない。"""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("CLAUDE_", "GIT_")) and k not in ("HOJO_MEMORY_OFF", "GITHUB_ACTIONS")}
    env["CLAUDE_PROJECT_DIR"] = str(world)
    return env


def _py(world, script, *args):
    return subprocess.run([sys.executable, f"scripts/{script}", *args], cwd=world, env=_env(world),
                          capture_output=True, text=True, timeout=120)


def note(world, sid, text):
    """`python3 scripts/experience_log.py note "…"`(今のセッションは SessionStart が _local に置いたもの)。"""
    r = _py(world, "experience_log.py", "note", text)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"session-{sid}" in r.stdout, r.stdout        # 今のセッション(sid)に追記された
    return r


def extract(world):
    """抽出器の CLI(--root)。exit 0 と要約(JSON)を返す。"""
    r = _py(world, "knowledge_extract.py", "--root", str(world), "--run-id", "e2e-run")
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def validate(world):
    return _py(world, "wiki_validate.py", "--root", str(world))


def load(world_or_rel, rel=None):
    """候補・Wiki のファイルの frontmatter(world に複製した wiki_schema と同じ書式: 1行1キー・値は JSON かスカラー)。"""
    path = Path(world_or_rel) / rel if rel is not None else Path(world_or_rel)
    lines = path.read_text(encoding="utf-8").split("\n")
    assert lines[0] == "---", path
    fm = {}
    for line in lines[1:lines.index("---", 1)]:
        key, _sep, raw = line.partition(":")
        v = raw.strip()
        if v[:1] in ("[", "{", '"'):
            fm[key] = json.loads(v)
        else:
            try:
                fm[key] = float(v)
            except ValueError:
                fm[key] = v
    return fm


def _note_candidates(world, summary):
    """この実行で書かれた R2(note)の候補のパス。R3(失敗台帳)・R4(Decision)の候補は confidence が高く先に並ぶので、
    要約の順番(written[0])ではなく規則の slug で選ぶ。"""
    return [p for p in summary["written"] if Path(p).stem.split("-")[1] == "note"]


def commit_all(world, subject="chore: wiki"):
    git(world, "add", "-A")
    git(world, "commit", "-q", "-m", subject)


def session_with_note(world, sid, text, subject=None):
    """SessionStart → note → SessionEnd → commit(クラウドでは push まで)。"""
    hook(world, "SessionStart", sid=sid, source="startup")
    note(world, sid, text)
    hook(world, "SessionEnd", sid=sid, reason="exit")
    commit_all(world, subject or f"chore: experience {sid}")


def _tracked(world, rel):
    return bool(git(world, "ls-files", "--", rel).strip())


def _value(v):
    """wiki_schema.render_wiki と同じ書き方(配列・オブジェクトと、読み違えうる文字列は JSON)。"""
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, float):
        return repr(v)
    s = str(v)
    needs_quote = s == "" or s != s.strip() or s[:1] in ("[", "{", '"') or "\n" in s
    try:
        float(s)
        needs_quote = True
    except ValueError:
        pass
    return json.dumps(s, ensure_ascii=False) if needs_quote else s


def _write_fm(path, fm, body):
    lines = ["---"] + [f"{k}: {_value(v)}" for k, v in fm.items()] + ["---"]
    path.write_text("\n".join(lines) + "\n" + body, encoding="utf-8")


def promote(world, cid, utagai, approved_by=APPROVER, approved_at=APPROVED_AT):
    """人の承認の模擬: frontmatter を編集し、commit 済みの候補を `git mv` で docs/wiki/<wiki_id>.md へ。

    2回目(1回目が検証で止まった後の直し)は、既に移した docs/wiki/<wiki_id>.md を編集し直す。
    """
    slug = cid.split("-", 1)[1].rsplit("-", 1)[0]
    wiki_id = f"W{approved_at.replace('-', '')}-{slug}"
    src = world / "docs/wiki/_candidates" / f"{cid}.md"
    dst = world / "docs/wiki" / f"{wiki_id}.md"
    if src.exists():
        assert _tracked(world, f"docs/wiki/_candidates/{cid}.md"), "昇格は commit 済みの候補から"
        git(world, "mv", f"docs/wiki/_candidates/{cid}.md", f"docs/wiki/{wiki_id}.md")
    assert dst.exists(), dst
    text = dst.read_text(encoding="utf-8")
    body = text.split("\n---\n", 1)[1]
    fm = load(dst)
    review_by = (date.fromisoformat(approved_at) + timedelta(days=180)).isoformat()
    fm.update({"review_status": "approved", "wiki_id": wiki_id, "approved_by": approved_by,
               "approved_at": approved_at, "review_by": review_by,
               "review": {"スイシン": "手戻りが減る", "ウタガイ": utagai, "ベッカイ": "取り込みを自動化する"}})
    _write_fm(dst, fm, body)
    return dst


def undo_promote(world):
    """検証で止まった昇格を取り消す(docs/wiki/ を HEAD に戻す。候補は commit 済みなので元に戻る)。"""
    git(world, "reset", "-q", "--", "docs/wiki")
    git(world, "clean", "-fdq", "--", "docs/wiki")
    git(world, "checkout", "-q", "HEAD", "--", "docs/wiki")


def context(proc):
    return _context(proc)


def stage2(world, sid, prompt):
    """段2(最初の指示)。新しい項目が無ければ hook は `{}` を返すので、そのときは空文字。"""
    r = hook(world, "UserPromptSubmit", sid=sid, prompt=prompt)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    return out.get("hookSpecificOutput", {}).get("additionalContext", "")


def section(ctx, label):
    """段1の出力のうち、label を含む見出しの直後から次の見出しまで。"""
    lines = ctx.split("\n")
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## ") and label in ln)
    out = []
    for ln in lines[start + 1:]:
        if ln.startswith("## ") or ln.startswith("# "):
            break
        out.append(ln)
    return "\n".join(out).strip()


def session_recorded(world, sid):
    text = read_session(world, sid)
    return '"event": "session_start"' in text and f'"session_id": "{sid}"' in text


def commit_decision(world, outcome, date=TODAY, title="公開経路の決定", slug="e2e-wiki"):
    """採用済み(adopted)の議事を書いて commit する(test タグなし = 矛盾判定の対象)。"""
    did = f"D{date.replace('-', '')}-{slug}"
    rel = f"docs/議事_{date.replace('-', '')}_{title}.md"
    write(world, rel, f"""---
decision_id: {did}
date: {date}
title: {title}
scope: hojo-hq/基盤
tags: [e2e, wiki]
status: adopted
supersedes:
decided_by: 小柳
---

# 議事 {title}

## なぜ(背景)

生成物の扱いを1つに決める

## 前提

自動生成物は毎日更新される

## 三名体制の議論

- **スイシン(推進)**: 手順を1つにすると迷わない
- **ウタガイ(反対理由・必須記録)**: 急ぎのときに遅くなる
- **ベッカイ(別解・前提を疑う)**: 自動で検査する

## 裁定

{outcome}
""")
    commit_all(world, f"docs: 議事 {title}")
    return did


def seed_approved(world):
    """順方向の流れを最後まで通し、承認済みの Wiki を1件つくって commit する(LESSON)。"""
    session_with_note(world, "A", LESSON)
    s = extract(world)
    [rel] = _note_candidates(world, s)
    commit_all(world, "docs: wiki 候補")
    cid = Path(rel).stem
    dst = promote(world, cid, utagai="データが少ないうちは例外が多い")
    r = validate(world)
    assert r.returncode == 0, r.stdout + r.stderr
    commit_all(world, PROMOTE_SUBJECT)
    assert load(dst)["title"] == APPROVED_TITLE
    return dst


# ---------------------------------------------------------------- 順方向

def test_forward_session_a_to_wiki_to_session_b(world):
    # ---- Session A(経験を残して終了 → commit)----
    hook(world, "SessionStart", sid="A", source="startup")
    note(world, "A", LESSON)
    hook(world, "SessionEnd", sid="A", reason="exit")
    git(world, "add", "-A")
    git(world, "commit", "-q", "-m", "chore: experience A")

    # ---- 抽出 → 候補 → 検証(F2・F3)----
    s = extract(world)
    [rel] = _note_candidates(world, s)
    cid = Path(rel).stem
    cand = load(world, rel)
    assert cand["review_status"] == "candidate" and cand["visibility"] == "public"
    assert cand["source_experience"][0].startswith("session-A@") and cand["title"] == APPROVED_TITLE
    assert validate(world).returncode == 0                                                   # F3
    commit_all(world, "docs: wiki 候補")                                                       # 候補 PR のマージ

    # ---- 人の承認(F4: ウタガイ空は通らない / F5: 直せば通る)----
    promote(world, cid, utagai="")
    r = validate(world)
    assert r.returncode == 1 and "V09" in r.stdout and "ウタガイ" in r.stdout, r.stdout     # F4
    promote(world, cid, utagai="データが少ないうちは例外が多い", approved_by=APPROVER, approved_at=APPROVED_AT)
    r = validate(world)
    assert r.returncode == 0, r.stdout + r.stderr                                             # F5
    git(world, "add", "-A")
    git(world, "commit", "-q", "-m", PROMOTE_SUBJECT)
    assert not list((world / "docs/wiki/_candidates").glob(f"{cid}.md"))                      # 候補は移った

    # ---- Session B(完全に別の session_id)----
    ctx = context(hook(world, "SessionStart", sid="B", source="startup"))
    assert ctx.index("[再発防止]") < ctx.index("[Wiki]") < ctx.index("[Skill]")                  # F6
    wiki = section(ctx, "[Wiki]")
    assert wiki.startswith(f"- [Wiki] {APPROVED_TITLE} — ")                                    # 何を知っているか
    assert "根拠: Exp 1・Decision 0・FK 0" in ctx and "承認: 小柳(テスト) 2026-10-20" in ctx and "→ docs/wiki/" in ctx  # F7
    assert f"→ docs/wiki/W20261020-{cid.split('-', 1)[1].rsplit('-', 1)[0]}.md" in wiki
    print("\n=== Session B STAGE1 additionalContext ===\n" + ctx)


# ---------------------------------------------------------------- 逆方向

def test_reverse_wrong_experience_conflict_never_injected(world):
    did = commit_decision(world, outcome="自動生成物は main へ直接 push しない。必ず PR を通す")     # C
    session_with_note(world, "A", WRONG, subject="chore: experience A(自動生成物を直接 push)")   # A(誤り)
    s = extract(world)
    [rel] = _note_candidates(world, s)
    w = load(world, rel)
    assert w["review_status"] == "conflict"                                                   # R2
    assert [c["source"] for c in w["contradictions"]] == [did]
    assert validate(world).returncode == 0                                                    # conflict の候補は置いてよい
    commit_all(world, "docs: wiki 候補(自動生成物を直接 push)")

    promote(world, w["candidate_id"], utagai="x")
    r = validate(world)
    assert r.returncode == 1 and "V12" in r.stdout and did in r.stdout, r.stdout             # R3
    undo_promote(world)
    assert (world / rel).exists() and validate(world).returncode == 0                         # 候補に戻った

    ctx = context(hook(world, "SessionStart", sid="B", source="startup")) + stage2(world, "B", "直接 push の手順")
    assert "[D] " in ctx                                                                       # 検索語は当たっている(空振りでない)
    assert "当日中に反映" not in ctx and not list((world / "docs/wiki").glob("*.md"))           # R4


def test_candidate_never_injected_before_approval(world):
    session_with_note(world, "A", "学び: 固有語ZQX の手順")
    s = extract(world)
    [rel] = _note_candidates(world, s)
    commit_all(world, "docs: wiki 候補 固有語ZQX の手順")                                       # 検索語に候補の語を載せる
    assert _tracked(world, rel)
    assert "ZQX" not in context(hook(world, "SessionStart", sid="B", source="startup"))
    # 対照: 同じ候補を承認すれば、同じ検索語で [Wiki] に出る(上の不在は検索語の空振りではない)
    promote(world, Path(rel).stem, utagai="固有語は他の作業に当てはまらない")
    assert validate(world).returncode == 0
    commit_all(world, "docs: wiki 昇格 固有語ZQX の手順")
    assert "- [Wiki] 学び: 固有語ZQX の手順" in context(hook(world, "SessionStart", sid="B2", source="startup"))


def test_wiki_off_partial_stop_keeps_other_kinds(world):
    seed_approved(world)
    before = context(hook(world, "SessionStart", sid="C0", source="startup"))
    assert section(before, "[Wiki]").startswith(f"- [Wiki] {APPROVED_TITLE}")                 # 対照: 止める前は出る
    (world / ".claude/wiki.off").touch()
    ctx = context(hook(world, "SessionStart", sid="C", source="startup"))
    assert section(ctx, "[Wiki]") == "- 該当なし" and session_recorded(world, "C")              # F8
    assert section(ctx, "[再発防止]").startswith("- [再発防止] ")                                # 他の区分は動く
    assert section(ctx, "[Exp]").startswith("- [Exp] ")


def test_needs_review_after_new_decision_stops_injection(world):
    seed_approved(world)
    assert APPROVED_TITLE in context(hook(world, "SessionStart", sid="D0", source="startup"))  # 対照: 決定の前は出る
    did = commit_decision(world, date="2026-11-01", outcome=OPPOSITE, title="生成物の取り込み手順", slug="e2e-opposite")
    r = validate(world)
    assert r.returncode == 0 and "needs_review" in r.stdout and did in r.stdout, r.stdout + r.stderr  # 警告のみ
    ctx = context(hook(world, "SessionStart", sid="D", source="startup"))
    assert APPROVED_TITLE not in ctx                                                           # R5
    assert "生成物の取り込み手順" in ctx                                                       # 新しい Decision は出る
    audit = (world / ".claude/experience/_audit.log").read_text(encoding="utf-8")
    assert "needs_review W20261020-" in audit and did in audit


def test_private_world_extracts_nothing_public(world_private):
    session_with_note(world_private, "P", "学び: 非公開側の気づき")
    assert _tracked(world_private, git(world_private, "ls-files", "--", ".claude/experience").split("\n")[0])  # 入力は実在する
    s = extract(world_private)
    assert "repository-not-public" in s["input_errors"]
    assert s["inputs"]["experience_rows"] == 0
    # どちらが起きたかを明示する: 何も書かない(この実装)か、書いたなら全部 private
    assert s["written"] == [] or all(load(world_private, p)["visibility"] == "private" for p in s["written"])
    assert s["written"] == []
    assert not list((world_private / "docs/wiki").glob("*.md"))
    assert not list((world_private / "docs/wiki/_candidates").glob("*.md"))
