#!/usr/bin/env python3
"""WikiSkill Phase 1 共通部品(stdlib のみ)。

hook・CLI から使う小さな部品: プロジェクトルート解決、無効化スイッチ、
hook 入力の読み取り、監査ログ(silent fail 禁止)、hook 出力 JSON。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EXPERIENCE_DIR = ".claude/experience"
LOCAL_DIR = ".claude/experience/_local"
AUDIT_LOG = "_audit.log"

_FALSY = {"", "0", "false", "no", "off"}

# Bash のプログラム名として記録してよい形(これ以外は "<unknown>")
PROGRAM_RE = re.compile(r"^[A-Za-z0-9._+-]{1,32}$")
_SECRET_PREFIXES = ("sk-", "ghp_", "gho_", "ghs_", "ghu_", "github_pat_", "xox", "akia", "aiza")
_LONG_RUN_RE = re.compile(r"[A-Za-z0-9]{20,}")
PROGRAM_PLACEHOLDERS = {"<unknown>", "<external>"}

# session-<sid>.jsonl(本体)と session-<sid>.part<N>.jsonl(本体が commit された後の続き)
_SESSION_FILE_RE = re.compile(r"^session-(.+?)(?:\.part([1-9][0-9]*))?\.jsonl$")


def project_dir() -> Path:
    """CLAUDE_PROJECT_DIR → git rev-parse --show-toplevel → cwd の順で解決する。"""
    env = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if env:
        return Path(env)
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout.strip()
        if out:
            return Path(out)
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd()


def disabled(root: Path) -> bool:
    """HOJO_MEMORY_OFF が truthy、または root/.claude/memory.off が存在すれば True。"""
    if os.environ.get("HOJO_MEMORY_OFF", "").strip().lower() not in _FALSY:
        return True
    return (Path(root) / ".claude" / "memory.off").exists()


def read_hook_input() -> dict:
    """stdin の JSON(dict)を返す。空・壊れ・dict 以外は {}。"""
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        data = json.loads(sys.stdin.read() or "")
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def session_id_of(payload: dict) -> str:
    """payload['session_id'] → CLAUDE_SESSION_ID → unknown-<UTC時刻>。"""
    sid = payload.get("session_id") if isinstance(payload, dict) else None
    if isinstance(sid, str) and sid.strip():
        return sid.strip()
    env = os.environ.get("CLAUDE_SESSION_ID", "").strip()
    if env:
        return env
    return "unknown-" + utc_now().strftime("%Y%m%dT%H%M%SZ")


def audit(root: Path, component: str, message: str) -> None:
    """root/.claude/experience/_audit.log に `ISO8601<TAB>component<TAB>message` を追記。

    書けなければ stderr に出す(どちらにも出ない失敗は作らない)。
    """
    clean = " ".join(str(message).split())
    line = f"{iso(utc_now())}\t{component}\t{clean}\n"
    try:
        log = Path(root) / EXPERIENCE_DIR / AUDIT_LOG
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        print(f"[wikiskill audit unwritable: {e}] {line.rstrip()}", file=sys.stderr)


def audit_if_slow(root: Path, component: str, event: str, started: float, limit_ms: int) -> int:
    """started(time.perf_counter() の値)から limit_ms を超えていたら `slow <event> <ms>ms` を audit に残す。

    監査ログのみ(画面警告は出さない)。経過ミリ秒(整数)を返す。
    """
    ms = int(round((time.perf_counter() - started) * 1000))
    if ms > limit_ms:
        audit(root, component, f"slow {event} {ms}ms")
    return ms


def valid_program_name(name) -> bool:
    """記録してよいプログラム名か(PROGRAM_RE に合い、鍵らしい形でない)。"""
    if not isinstance(name, str) or not PROGRAM_RE.match(name):
        return False
    if name.lower().startswith(_SECRET_PREFIXES) or _LONG_RUN_RE.search(name):
        return False  # API キー・トークンの断片らしいもの(sk-… / 20字以上の英数字の連続)
    return True


def current_branch(git) -> str:
    """今のブランチ名。git(*args) は stdout(失敗は空文字か None)を返す関数。

    `git branch --show-current` → 空(detached HEAD。クラウドのセッションはこれで始まる)なら、
    HEAD を指す refs/remotes/origin/* がちょうど1つのときその名前(origin/ を外す)。0件・2件以上は "unknown"。
    """
    name = (git("branch", "--show-current") or "").strip()
    if name:
        return name
    out = git("for-each-ref", "--points-at", "HEAD", "--format=%(refname)", "refs/remotes/origin/") or ""
    prefix = "refs/remotes/origin/"
    names = sorted({
        ref[len(prefix):] for ref in (l.strip() for l in out.splitlines())
        if ref.startswith(prefix) and ref[len(prefix):] and ref[len(prefix):] != "HEAD"
    })
    return names[0] if len(names) == 1 else "unknown"


def session_file_key(name: str) -> tuple[str, int] | None:
    """`session-<sid>.jsonl` → (sid, 0)、`session-<sid>.part<N>.jsonl` → (sid, N)。それ以外は None。"""
    m = _SESSION_FILE_RE.match(name)
    if not m:
        return None
    return m.group(1), int(m.group(2) or 0)


def group_session_files(paths) -> dict[str, list[Path]]:
    """セッションごとに [本体, part1, part2, …] の順に並べる(1セッション = 本体 + 続きのファイル)。"""
    groups: dict[str, list[tuple[int, Path]]] = {}
    for p in paths:
        key = session_file_key(Path(p).name)
        if key is None:
            continue
        groups.setdefault(key[0], []).append((key[1], Path(p)))
    return {sid: [p for _n, p in sorted(items, key=lambda t: t[0])] for sid, items in groups.items()}


class GitError(RuntimeError):
    """commit 済みかどうかを git で確かめられない(呼び元は「commit 済みのものは無い」として fail closed)。"""


_COMMITTED_MODES = ("100644", "100755")
_GIT_TIMEOUT_S = 60


def _git_out(root: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-c", "core.quotePath=false", *args], cwd=str(root), capture_output=True,
                           text=True, encoding="utf-8", errors="strict", timeout=_GIT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        raise GitError(f"git {args[0]} を実行できない: {type(e).__name__}") from e
    if r.returncode != 0:
        raise GitError(f"git {args[0]} が失敗(exit {r.returncode})")
    return r.stdout


def committed_files(root: Path, pathspec: str) -> set[str]:
    """pathspec の下で「commit 済みのまま」のファイル(リポジトリ相対の POSIX パス)。

    条件: git 管理下の通常ファイル(mode 100644/100755。symlink 120000・submodule 160000 は除く)、
    作業ツリーでも symlink でない、`git diff --name-only HEAD` に出ない(作業ツリー・index とも HEAD と同じ)、
    assume-unchanged(`git ls-files -v` の小文字の印)・skip-worktree(`S`)でない(diff が変更を報告しないため)。
    検証器・抽出器・Bootstrap が共有する唯一の判定。root が git リポジトリの最上位でない・git が失敗したら GitError。
    """
    root = Path(root)
    top = _git_out(root, "rev-parse", "--show-toplevel").strip()
    try:
        same = bool(top) and Path(top).resolve() == root.resolve()
    except OSError as e:
        raise GitError(f"リポジトリの最上位を確かめられない: {type(e).__name__}") from e
    if not same:
        raise GitError("root が git リポジトリの最上位ではない")
    tracked: set[str] = set()
    for entry in _git_out(root, "ls-files", "-s", "-v", "-z", "--", pathspec).split("\0"):
        if not entry:
            continue
        meta, _tab, path = entry.partition("\t")
        parts = meta.split(" ")
        if len(parts) < 2 or not path:
            continue
        tag, mode = parts[0], parts[1]
        if tag != tag.upper() or tag == "S":
            continue  # assume-unchanged / skip-worktree: 作業ツリーの変更を git が報告しない
        if mode not in _COMMITTED_MODES or (root / path).is_symlink():
            continue
        tracked.add(path)
    changed = set(_git_out(root, "diff", "--name-only", "-z", "HEAD", "--", pathspec).split("\0"))
    return tracked - changed


_LEDGER_PIPE_RE = re.compile(r"(?<!\\)\|")


def split_ledger_row(line: str) -> list[str]:
    """失敗台帳(Markdown の表)の1行をセルに分ける。`\\|`(エスケープした縦棒)ではセルを切らない。

    前後の空白と両端の `|` を落とし、各セルの前後の空白も落とす(セル内の `\\|` はそのまま残す)。
    """
    return [c.strip() for c in _LEDGER_PIPE_RE.split(str(line).strip().strip("|"))]


def emit(event: str, additional_context: str | None = None, system_message: str | None = None) -> None:
    """hook 出力 JSON を stdout に1回だけ出す。両方 None なら {}。"""
    out: dict = {}
    if additional_context is not None:
        out["hookSpecificOutput"] = {
            "hookEventName": event,
            "additionalContext": additional_context,
        }
    if system_message is not None:
        out["systemMessage"] = system_message
    print(json.dumps(out))
