#!/usr/bin/env python3
"""WikiSkill Phase 1: Experience 記録の公開可否を検査する(Privacy Boundary の機械検査)。

背景: .claude/experience/ の JSONL は Git にコミットされる。本リポジトリは【公開】なので、
      コミットされた Experience は「そのまま公開してよい」ことを機械で証明できなければならない。
      記録側(scripts/experience_log.py)は何も残さない作りだが、手編集や別経路の混入に備えて
      CI で全行を検査し、違反が1件でもあれば止める。

止めるもの:
  - visibility が public でない / repo が allgroup-inc/hojo-hq でない(他リポ・private の記録)
  - path 系の値(path / files_changed の各要素)が絶対パス・~ 始まり・`..` を含む・Windows ドライブ
    (<external> と <unknown> は許可)
  - note 以外の文字列値が 500 文字超 / note の text が 1,000 文字超(ネストした文字列も対象)
  - 本文が check_repo_scope.FORBIDDEN_CONTENT に触れる(禁止語リストは二重管理しない)
  - program が `^[A-Za-z0-9._+-]{1,32}$` の形でない・鍵の断片らしい(<unknown> と <external> は許可)
  - 未知の event 名 / JSON オブジェクトでない行 / JSON として読めない行

ignore と追跡状態(決裁 #26 S2 PR-D・2026-10-08):
  - 記録パス(.claude/experience/<月>/*.jsonl)が .gitignore で除外されていたら止める。
    2026-10-08 に別セッションの直接 push(802a00cbf)が `.claude/experience/` を ignore に足し、
    記録が Git に残らず、この検査も空振りで緑になった(PR #450 で修復)。CODEOWNERS は承認を求めるだけで
    壊す変更そのものは止めないので、ここで機械的に止める。
  - ローカル限定のもの(_local/ と _audit.log)は ignore 必須。ignore されていない・既に追跡されている、のどちらも止める。
  - 判定は git 自身(`git check-ignore --no-index`)に任せる(.gitignore の文字列検査では別の書き方をすり抜ける)。
    利用者ごとの global excludes は見ない(core.excludesFile を空にする)= コミットされた .gitignore だけを検査する。

使い方:
    python3 scripts/check_experience_privacy.py            # git 管理下の Experience を検査(cwd が対象リポ)
    python3 scripts/check_experience_privacy.py --selftest # 検査ロジック自体の自己点検
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_repo_scope import FORBIDDEN_CONTENT, find_content_violations, read_text  # noqa: E402,F401
from wikiskill_common import PROGRAM_PLACEHOLDERS, valid_program_name  # noqa: E402

PUBLIC_REPO = "allgroup-inc/hojo-hq"
MAX_FIELD = 500
MAX_NOTE = 1000

EXPERIENCE_DIR = ".claude/experience"
VALID_EVENTS = {"session_start", "session_resume", "tool", "skill", "note", "session_end"}
PLACEHOLDERS = {"<external>", "<unknown>"}
_DRIVE = re.compile(r"^[A-Za-z]:")

# ignore と追跡状態の検査対象(パスは存在しなくてよい。git check-ignore はパターンだけで判定する)
RECORD_PROBE = f"{EXPERIENCE_DIR}/2026-01/session-probe.jsonl"   # 記録パス: ignore されてはいけない
MUST_IGNORE = (                                                    # ローカル限定: ignore 必須・追跡禁止
    f"{EXPERIENCE_DIR}/_local/probe",
    f"{EXPERIENCE_DIR}/_audit.log",
)

HINT = """
Experience 記録は【公開リポジトリにそのまま載る】ものです。公開して問題のある内容は残せません。
  - 記録してよいのは hojo-hq の、プロジェクト内の相対パスとプログラム名など、機械が観測した事実だけ
  - 他リポ・private の記録 / 絶対パス / 長い本文 / 禁止語を含む行は、コミットから外してください
  - 該当ファイルを直す(または git rm する)か、記録自体を止めるなら .claude/memory.off を置いてください
  - .gitignore の違反: 記録パス(.claude/experience/<月>/*.jsonl)は除外しない / _local/ と _audit.log は除外する。
    記録自体を止めたいときは .gitignore ではなく .claude/memory.off を使ってください

  詳細: docs/wikiskill/README.md
"""


def _path_problem(value) -> str | None:
    """path 系の値の問題を返す(問題なしは None)。"""
    if not isinstance(value, str):
        return "文字列ではありません"
    if value in PLACEHOLDERS:
        return None
    if value.startswith("/") or value.startswith("\\"):
        return "絶対パスです"
    if value.startswith("~"):
        return "~ で始まります"
    if _DRIVE.match(value):
        return "Windows ドライブのパスです"
    if ".." in re.split(r"[/\\]", value):
        return ".. を含みます"
    return None


def _walk_strings(value, key: str, out: list[tuple[str, str]]) -> None:
    """文字列値を (所属キー, 値) で集める。list/dict は再帰し、所属キーは最上位キーを引き継ぐ。"""
    if isinstance(value, str):
        out.append((key, value))
    elif isinstance(value, list):
        for v in value:
            _walk_strings(v, key, out)
    elif isinstance(value, dict):
        for k, v in value.items():
            _walk_strings(v, key, out)


def check_record(rec, path: str) -> list[str]:
    """1レコードの違反メッセージ一覧(空なら公開してよい)。"""
    if not isinstance(rec, dict):
        return ["レコードが JSON オブジェクトではありません"]
    problems: list[str] = []

    event = rec.get("event")
    if event not in VALID_EVENTS:
        problems.append(f"event が未知です: {str(event)[:40]!r}")
    if rec.get("visibility") != "public":
        problems.append(f"visibility != public ({str(rec.get('visibility'))[:40]!r})")
    if rec.get("repo") != PUBLIC_REPO:
        problems.append(f"repo != {PUBLIC_REPO} ({str(rec.get('repo'))[:80]!r})")

    # path 系: 単独の path キーと files_changed の各要素
    path_values = []
    if "path" in rec:
        path_values.append(("path", rec["path"]))
    fc = rec.get("files_changed")
    if fc is not None:
        if isinstance(fc, list):
            path_values.extend(("files_changed", v) for v in fc)
        else:
            problems.append("files_changed がリストではありません")
    for key, value in path_values:
        why = _path_problem(value)
        if why:
            problems.append(f"{key} がプロジェクト相対パスではありません({why}): {str(value)[:80]!r}")

    # Bash のプログラム名: 記録側(experience_log._program_of)と同じ形だけを通す
    if "program" in rec:
        prog = rec["program"]
        if not (isinstance(prog, str) and (prog in PROGRAM_PLACEHOLDERS or valid_program_name(prog))):
            problems.append(f"program が記録してよい形ではありません: {str(prog)[:40]!r}")

    # 文字列の長さ(ネストも再帰)。text だけ 1,000、他は 500
    strings: list[tuple[str, str]] = []
    for k, v in rec.items():
        _walk_strings(v, k, strings)
    for key, value in strings:
        limit = MAX_NOTE if key == "text" else MAX_FIELD
        if len(value) > limit:
            problems.append(f"{key} の文字列が {limit} 文字を超えています({len(value)} 文字)")

    word = find_content_violations(path, json.dumps(rec, ensure_ascii=False))
    if word:
        problems.append(f"本文の禁止語: {word}")
    return problems


def _tracked_experience(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", EXPERIENCE_DIR],
        cwd=str(root), capture_output=True, text=True, check=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def _is_target(rel: str) -> bool:
    if not rel.endswith(".jsonl"):
        return False
    parts = rel.split("/")
    return "_local" not in parts and parts[-1] != "_audit.log"


def scan(root: Path) -> list[tuple[str, str]]:
    """git 管理下の Experience JSONL を全行検査し、(パス, 理由) を違反ごとに返す。"""
    root = Path(root)
    hits: list[tuple[str, str]] = []
    for rel in _tracked_experience(root):
        if not _is_target(rel):
            continue
        text = read_text(str(root / rel))
        if text is None:
            hits.append((rel, "テキストとして読めません(バイナリ/読込失敗)"))
            continue
        # "\n" だけで分ける(str.splitlines は U+2028/U+2029/\x85 でも割れ、raw で出力される note を誤検知する)
        for lineno, line in enumerate(text.split("\n"), start=1):
            line = line.rstrip("\r")
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                problems = check_record(rec, rel)
            except RecursionError:
                hits.append((rel, f"{lineno}行目: JSON の入れ子が深すぎます"))
                continue
            except ValueError:
                hits.append((rel, f"{lineno}行目: JSON として読めません"))
                continue
            for problem in problems:
                hits.append((rel, f"{lineno}行目: {problem}"))
    return hits


def _count_targets(root: Path) -> int:
    return sum(1 for rel in _tracked_experience(root) if _is_target(rel))


def _is_local_only(rel: str) -> bool:
    """_local/ 配下と _audit.log は Git に載せないローカル限定(記録側 experience_log.py の約束)。"""
    parts = rel.split("/")
    return "_local" in parts or parts[-1] == "_audit.log"


def _is_ignored(root: Path, rel: str) -> bool | None:
    """git 自身の判定で rel が ignore されるか。True/False、git が答えられなければ None(fail-closed 用)。

    --no-index: 追跡済みでもパターンで判定する(追跡されている _audit.log を「ignore されている」と誤らない)。
    core.excludesFile を空にして、利用者ごとの global excludes ではなくコミットされた .gitignore だけを見る。
    """
    r = subprocess.run(
        ["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "-q", "--no-index", "--", rel],
        cwd=str(root), capture_output=True, text=True,
    )
    if r.returncode == 0:
        return True
    if r.returncode == 1:
        return False
    return None


def check_tracking(root: Path) -> list[tuple[str, str]]:
    """ignore と追跡状態の違反を (パス, 理由) で返す(空なら正常)。

    - 記録パスが ignore されている → 記録が Git に残らず、公開可否の検査が空振りで緑になる
    - ローカル限定のパスが ignore されていない → 一時マーカー・監査ログがコミットされ得る
    - ローカル限定のファイルが既に追跡されている → ignore だけでは外れない(git rm --cached が要る)
    - git が判定できない → 検査できなかったことを「違反なし」にしない
    """
    root = Path(root)
    hits: list[tuple[str, str]] = []
    ig = _is_ignored(root, RECORD_PROBE)
    if ig is None:
        hits.append((RECORD_PROBE, "git check-ignore で判定できません(検査不能)"))
    elif ig:
        hits.append((RECORD_PROBE, ".gitignore が Experience の記録パスを除外しています"
                                   "(記録が Git に残らず、公開可否の検査も素通りします。2026-10-08 の再発)"))
    for rel in MUST_IGNORE:
        ig = _is_ignored(root, rel)
        if ig is None:
            hits.append((rel, "git check-ignore で判定できません(検査不能)"))
        elif not ig:
            hits.append((rel, "ローカル限定のパスが ignore されていません(一時マーカー・監査ログがコミットされ得ます)"))
    for rel in _tracked_experience(root):
        if _is_local_only(rel):
            hits.append((rel, "ローカル限定のファイルが Git に追跡されています(git rm --cached で外してください)"))
    return hits


def selftest() -> int:
    """検査が効いていること(止めるべきものを止める)・誤検知しないこと(通すべきものを通す)を確かめる。"""
    word = FORBIDDEN_CONTENT[0]  # 禁止語の実文字列はソースに書かない
    ok = {
        "ts": "2026-10-06T00:00:00Z", "session_id": "S", "event": "tool",
        "repo": PUBLIC_REPO, "visibility": "public", "branch": "main",
        "tool": "Edit", "path": "docs/a.md",
    }
    end = {
        **{k: v for k, v in ok.items() if k not in ("tool", "path")},
        "event": "session_end", "reason": "other", "duration_s": 5,
        "tools": {"Edit": 1}, "skills": ["brainstorming"],
        "commits": [{"sha": "abc1234", "subject": "feat: x"}],
        "files_changed": ["docs/a.md"],
    }
    # (名前, レコード, 違反として止まるべきか)
    cases = [
        ("private visibility", {**ok, "visibility": "private"}, True),
        ("他リポ", {**ok, "repo": "allgroup-inc/glow-docs-private"}, True),
        ("絶対パス", {**ok, "path": "/home/user/x"}, True),
        ("..を含むパス", {**ok, "path": "docs/../../x"}, True),
        ("~始まり", {**ok, "path": "~/x"}, True),
        ("Windowsドライブ", {**ok, "path": "C:\\x"}, True),
        ("files_changedの絶対パス", {**end, "files_changed": ["/etc/x"]}, True),
        ("501文字の値", {**ok, "branch": "b" * (MAX_FIELD + 1)}, True),
        ("ネストした501文字", {**end, "commits": [{"sha": "a", "subject": "s" * (MAX_FIELD + 1)}]}, True),
        ("note 1001文字", {**ok, "event": "note", "text": "あ" * (MAX_NOTE + 1)}, True),
        ("禁止語を含むnote", {**ok, "event": "note", "text": f"環境変数 {word} を"}, True),
        ("未知のevent", {**ok, "event": "weird"}, True),
        ("JSONオブジェクトでない", ["x"], True),
        ("記号入りのprogram", {**ok, "tool": "Bash", "program": "x)"}, True),
        ("鍵らしいprogram", {**ok, "tool": "Bash", "program": "sk-" + "x" * 24}, True),
        # 通すべきもの
        ("通常のtool", ok, False),
        ("<external>", {**ok, "path": "<external>"}, False),
        ("<unknown>", {**ok, "path": "<unknown>"}, False),
        ("note 1000文字(日本語)", {**ok, "event": "note", "text": "あ" * MAX_NOTE}, False),
        ("session_end(ネストあり)", end, False),
        ("名前に..を含むだけのファイル", {**ok, "path": "docs/a..b.md"}, False),
        ("通常のprogram", {**ok, "tool": "Bash", "program": "python3"}, False),
        ("<external>のprogram", {**ok, "tool": "Bash", "program": "<external>"}, False),
    ]
    failed = []
    for name, rec, should_hit in cases:
        hit = bool(check_record(rec, "selftest.jsonl"))
        if hit != should_hit:
            failed.append(f"  {name}: 期待={should_hit} 実際={hit}")

    if failed:
        print("自己点検に失敗しました:", file=sys.stderr)
        print("\n".join(failed), file=sys.stderr)
        return 2
    print(f"自己点検OK({len(cases)}件)")
    return 0


def _repo_root() -> Path:
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
        ).stdout.strip()
        if top:
            return Path(top)
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd()


def main(argv: list[str]) -> int:
    if argv == ["--selftest"]:
        return selftest()
    if argv:
        print("使い方: check_experience_privacy.py [--selftest]  (引数なしで git 管理下の Experience を検査)", file=sys.stderr)
        return 2
    root = _repo_root()
    try:
        hits = scan(root) + check_tracking(root)
        count = _count_targets(root)
    except (OSError, subprocess.SubprocessError) as e:
        # 検査できなかったことを「違反なし」にしない(fail-closed)
        print(f"Experience記録を検査できませんでした: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if not hits:
        print(f"OK: Experience記録 {count}件・違反なし(ignore・追跡状態 OK)")
        return 0
    print("公開できない Experience 記録があります:\n", file=sys.stderr)
    for path, reason in hits:
        print(f"  {path} → {reason}", file=sys.stderr)
    print(HINT, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
