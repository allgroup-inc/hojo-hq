#!/usr/bin/env python3
"""WikiSkill Phase 1: Experience Logger(stdlib のみ)。

セッションの「機械が観測できる行動」だけを JSONL に残す。
残すもの: 開始/終了・使ったツール名・Bash のプログラム名(先頭トークンのみ)・
プロジェクト内の編集パス・使った Skill・コミット件名・利用者が明示した note。
残さないもの: 利用者のプロンプト本文・Bash コマンド全文・ツール出力本文・プロジェクト外のパス。

使い方:
    python3 scripts/experience_log.py hook <SessionStart|PostToolUse|SessionEnd>   # stdin に hook JSON
    python3 scripts/experience_log.py note "<text>"                               # 1,000文字で切る

保存先: .claude/experience/YYYY-MM/session-<session_id>.jsonl(Git にコミットする)
失敗は作業を止めず、必ず _audit.log に残し、hook では systemMessage で警告する。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wikiskill_common import (  # noqa: E402
    EXPERIENCE_DIR,
    LOCAL_DIR,
    audit,
    disabled,
    emit,
    iso,
    project_dir,
    read_hook_input,
    session_id_of,
    utc_now,
)

Event = dict

# ここに無い remote は visibility="private"(公開リポジトリは hojo-hq のみ)
PUBLIC_REMOTES = {"allgroup-inc/hojo-hq"}

NOTE_MAX = 1000
EXTERNAL = "<external>"
_COMPONENT = "experience_log"
_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_FILE_TOOLS = {"Edit", "Write", "MultiEdit"}


class ExperienceWriteError(Exception):
    """Experience の書込に失敗した(audit 済み)。hook モードは systemMessage に変える。"""


def _git(root: Path, *args: str) -> str:
    """git を実行して stdout を返す。失敗は空文字(呼び元が既定値で扱う)。"""
    try:
        r = subprocess.run(
            ["git", *args], cwd=str(root), capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def repo_slug(root: Path) -> str:
    """`git remote get-url origin` から owner/name。取れなければ "unknown"(private 扱い)。"""
    url = _git(root, "remote", "get-url", "origin")
    if not url:
        return "unknown"
    parts = [p for p in re.split(r"[/:]", url.strip().rstrip("/")) if p]
    if len(parts) < 2:
        return "unknown"
    name = parts[-1][:-4] if parts[-1].endswith(".git") else parts[-1]
    owner = parts[-2]
    return f"{owner}/{name}" if owner and name else "unknown"


def _visibility(slug: str) -> str:
    return "public" if slug in PUBLIC_REMOTES else "private"


def sanitize_path(p: str, root: Path) -> str:
    """root 配下なら相対パス(posix)、それ以外は "<external>"。"""
    try:
        base = Path(root).resolve()
        target = Path(p)
        if not target.is_absolute():
            target = base / target
        rel = target.resolve().relative_to(base)
    except (OSError, ValueError, TypeError):
        return EXTERNAL
    return rel.as_posix()


def _safe_id(session_id: str) -> str:
    """ファイル名に使える形へ(パス区切り等を潰して root 外への書込を防ぐ)。"""
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(session_id)) or "unknown"


def session_file(root: Path, session_id: str, ts: datetime) -> Path:
    return Path(root) / EXPERIENCE_DIR / ts.strftime("%Y-%m") / f"session-{_safe_id(session_id)}.jsonl"


def _find_session_file(root: Path, session_id: str) -> Path | None:
    """月をまたいだセッションでも1ファイルに寄せるため、既存ファイルを探す。"""
    found = sorted((Path(root) / EXPERIENCE_DIR).glob(f"[0-9][0-9][0-9][0-9]-[0-9][0-9]/session-{_safe_id(session_id)}.jsonl"))
    return found[0] if found else None


def _parse_ts(value) -> datetime:
    try:
        return datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return utc_now()


def _base(root: Path | None, session_id: str, event: str) -> Event:
    if root is None:
        # root 不明なら fail-closed(private 扱い)
        repo, branch = "unknown", "unknown"
    else:
        repo = repo_slug(root)
        branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    return {
        "ts": iso(utc_now()),
        "session_id": session_id,
        "event": event,
        "repo": repo,
        "visibility": _visibility(repo),
        "branch": branch,
    }


def start_event(root: Path, session_id: str, source: str = "startup") -> Event:
    ev = _base(root, session_id, "session_start")
    ev["source"] = str(source)[:40]
    ev["head"] = _git(root, "rev-parse", "HEAD")
    return ev


def note_event(session_id: str, text: str, root: Path | None = None) -> Event:
    ev = _base(root, session_id, "note")
    ev["text"] = str(text)[:NOTE_MAX]
    return ev


def _program_of(command: str) -> str:
    """先頭トークン(プログラム名)だけ。先頭の VAR=値 は値が秘密になり得るので飛ばす。"""
    for tok in str(command).split():
        if _ENV_ASSIGN.match(tok):
            continue
        return os.path.basename(tok.strip("'\"("))[:64] or "<unknown>"
    return "<unknown>"


def build_tool_event(payload: dict, root: Path) -> Event | None:
    name = payload.get("tool_name")
    tin = payload.get("tool_input")
    if not isinstance(tin, dict):
        tin = {}
    if name == "Bash":
        ev = _base(root, session_id_of(payload), "tool")
        ev.update({"tool": "Bash", "program": _program_of(tin.get("command", ""))})
        return ev
    if name in _FILE_TOOLS:
        ev = _base(root, session_id_of(payload), "tool")
        ev.update({"tool": name, "path": sanitize_path(str(tin.get("file_path", "")), root)})
        return ev
    if name == "Skill":
        ev = _base(root, session_id_of(payload), "skill")
        ev["skill"] = str(tin.get("skill", ""))[:100]
        return ev
    return None


def _open_append(path: Path):
    """追記用に開く(テストで差し替え可能な書込の唯一の入口)。"""
    return open(path, "a", encoding="utf-8")


def append_event(root: Path, event: Event) -> Path:
    """1行追記。失敗は audit() してから ExperienceWriteError として投げ直す。"""
    path = None
    try:
        path = _find_session_file(root, event["session_id"]) or session_file(
            root, event["session_id"], _parse_ts(event.get("ts"))
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False) + "\n"
        with _open_append(path) as f:
            f.write(line)
    except Exception as e:  # noqa: BLE001 — 何が起きても audit に残して呼び元へ伝える
        reason = f"{type(e).__name__}: {e}"
        audit(root, _COMPONENT, f"append_event failed: {reason}")
        raise ExperienceWriteError(reason) from e
    return path


def _read_events(path: Path) -> list[Event]:
    events = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            ev = json.loads(raw)
        except ValueError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    return events


def summarize_session(root: Path, session_id: str) -> Event:
    """session の JSONL を集計した session_end イベントを返す(追記は呼び元)。"""
    path = _find_session_file(root, session_id)
    events = _read_events(path) if path else []
    start = next((e for e in events if e.get("event") == "session_start"), {})
    tools: dict[str, int] = {}
    skills: list[str] = []
    for e in events:
        if e.get("event") == "tool" and e.get("tool"):
            tools[e["tool"]] = tools.get(e["tool"], 0) + 1
        elif e.get("event") == "skill" and e.get("skill") and e["skill"] not in skills:
            skills.append(e["skill"])
    commits = []
    head = start.get("head")
    if head:
        out = _git(root, "log", f"{head}..HEAD", "--format=%h%x09%s")
        for line in out.splitlines()[:50]:
            sha, _, subject = line.partition("\t")
            commits.append({"sha": sha, "subject": subject[:200]})
    now = utc_now()
    duration = max(0, int((now - _parse_ts(start["ts"])).total_seconds())) if start.get("ts") else 0
    ev = _base(root, session_id, "session_end")
    ev.update({"commits": commits, "tools": tools, "skills": skills, "duration_s": duration})
    return ev


def _mark_ended(root: Path, session_id: str) -> None:
    marker = Path(root) / LOCAL_DIR / f"{_safe_id(session_id)}.ended"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(iso(utc_now()) + "\n", encoding="utf-8")


def _hook(event_name: str) -> int:
    payload = read_hook_input()
    root = project_dir()
    if disabled(root):
        return 0
    try:
        sid = session_id_of(payload)
        if event_name == "SessionStart":
            append_event(root, start_event(root, sid, str(payload.get("source") or "startup")))
        elif event_name == "PostToolUse":
            ev = build_tool_event(payload, root)
            if ev is not None:
                append_event(root, ev)
        elif event_name == "SessionEnd":
            ev = summarize_session(root, sid)
            ev["reason"] = str(payload.get("reason") or "")[:40]
            append_event(root, ev)
            _mark_ended(root, sid)
        else:
            audit(root, _COMPONENT, f"unknown hook event: {event_name}")
    except Exception as e:  # noqa: BLE001 — hook は作業を止めない。ただし silent にもしない
        if not isinstance(e, ExperienceWriteError):
            audit(root, _COMPONENT, f"{event_name} hook failed: {type(e).__name__}: {e}")
        emit(event_name, system_message=(
            f"⚠ Experience記録に失敗: {type(e).__name__}: {e}。audit: {EXPERIENCE_DIR}/_audit.log"
        ))
    return 0


def _note(text: str) -> int:
    root = project_dir()
    if disabled(root):
        return 0
    sid = os.environ.get("CLAUDE_SESSION_ID", "").strip() or session_id_of({})
    try:
        path = append_event(root, note_event(sid, text, root))
    except ExperienceWriteError as e:
        print(f"Experience記録に失敗: {e}(audit: {EXPERIENCE_DIR}/_audit.log)", file=sys.stderr)
        return 1
    print(f"recorded: {path.relative_to(root).as_posix()}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "hook":
        return _hook(argv[2])
    if len(argv) >= 3 and argv[1] == "note":
        return _note(" ".join(argv[2:]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
