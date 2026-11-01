#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WikiSkill M3 / Component E: Skill Metrics(読み取り専用の集計・schema v2)。

記録されている事実だけを集計する。記録の無い値は推測せず null にする。何も書き込まない。

入力(既存の記録を再利用する。新しい記録は増やさない):
  - .claude/experience/<月>/session-*.jsonl(本体と part)の
      skill          … PostToolUse(Skill)。成功した呼び出し。版(skill_key)・版番号(skill_version)・duration_ms を持つことがある
      skill_failure  … PostToolUseFailure(Skill)。失敗した呼び出し。登録前の期間には存在しない
      session_end    … セッションの commit 一覧(件名は出さない)
  - git: .claude/skills/<name>/SKILL.md の変更(版の対応表)と、PostToolUseFailure を settings.json に入れた日

定義:
  - success: 記録された skill イベント(成功)
  - failure: 記録された skill_failure(失敗)。登録日(git の履歴)以降の行だけ「観測済み」
  - retry: 同じセッションで、同じ Skill の直前の呼び出しが失敗だったもの(セッション内の追記順)
  - failure_observed: 登録日以降のイベントが行にあるか。観測済みでなければ、failure・retry・success_rate は
    記録が無いのか起きなかったのか区別できないので null(0 とは書かない)
  - failure_firing_confirmed: 記録に skill_failure が1件でもあれば true(発火の実証)。無ければ false のまま

出力(stdout のみ): JSON(--format json)または JSONL(--format jsonl。行 = 月 × Skill × 版)。
F(Proposer)は JSONL の行を読む。版の一覧は JSON の versions を version_key で結ぶ。

公開側への流出を防ぐ規則:
  - 数えるのは visibility が public かつ repo が PUBLIC_REMOTES の行だけ
  - Skill 名は、リポジトリの .claude/skills に実在するものだけ出す。それ以外は "<external>"
  - 出すのは件数・日付・内容の短い識別子・短い commit ID。commit の件名・セッションID・パス・error 本文は出さない
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experience_log import EXTERNAL, PUBLIC_REMOTES, _read_events, skill_content_key  # noqa: E402
from wikiskill_common import EXPERIENCE_DIR, group_session_files, project_dir  # noqa: E402

SCHEMA = "skill-metrics/v2"
UNKNOWN = "<unknown>"
SKILLS_DIR = ".claude/skills"
SETTINGS = ".claude/settings.json"
FAILURE_HOOK = "PostToolUseFailure"
_MONTH_DIR = re.compile(r"^\d{4}-\d{2}$")
_PERIOD = re.compile(r"^\d{4}-\d{2}$")
_TS_FULL = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
_SKILL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_CHANGED = re.compile(r"^\.claude/skills/([^/]+)/SKILL\.md$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SKILL_KEY = re.compile(r"^[0-9a-f]{12}$")
_VERSION = re.compile(r"^[0-9A-Za-z._+-]{1,32}$")
_MAX_MS = 24 * 3600 * 1000

NOT_RECORDED = {
    "problem_resolution": "問題解決の成否は記録されない(人手ラベルの仕組みは未実装)",
    "failure_count": "登録日より前の期間は失敗が記録されない。観測済みでない行は null(0 とは書かない)",
    "retry_count": "失敗が観測されていない行の再試行は判定できない。観測済みでない行は null",
    "success_rate": "観測済みで、成功か失敗の記録が1件以上ある行だけ計算する",
    "avg_duration_seconds": "duration_ms が記録された呼び出しだけで平均する。Skill で duration_ms が来るかは未確認",
}
DEFINITIONS = {
    "total_invocations": "記録された成功した Skill 呼び出し(skill イベント)",
    "failure_firing_confirmed": "記録に skill_failure が1件以上あるか。false の間は、失敗0件を『失敗なし』と解釈しない",
    "failure_observed": "登録日(git の履歴)以降のイベントが行にあるか",
    "version_key": "SKILL.md の内容の識別子(sha256 の先頭12桁)。JSON の versions の version_key と結ぶ",
    "sessions_with_commits": "同じセッション内で commit が1件以上あったセッションの数。同時発生であって、Skill の成果ではない",
}


def _parse_ts(ts) -> datetime | None:
    if not isinstance(ts, str) or not _TS_FULL.match(ts):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _skill_ref(raw, root: Path) -> tuple[str, str]:
    """(表示名, source)。実在する Skill だけ名前を出す。source は project / external / unknown。"""
    if not isinstance(raw, str):
        return UNKNOWN, "unknown"
    name = raw.strip()
    if _SKILL_NAME.match(name) and (root / SKILLS_DIR / name / "SKILL.md").is_file():
        return name, "project"
    if ":" in name or _SKILL_NAME.match(name):
        return EXTERNAL, "external"
    return UNKNOWN, "unknown"


def _git(root: Path, *args: str, text: bool = True):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=text,
                          timeout=60, check=False)


def _failure_hook_since(root: Path) -> datetime | None:
    """PostToolUseFailure を settings.json に入れた最初のコミットの時刻。履歴に無い・git が無ければ None。"""
    try:
        out = _git(root, "log", "--format=%cI", "-S", FAILURE_HOOK, "--", SETTINGS)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    dts = [d for d in (_parse_ts(line.strip()) for line in out.stdout.splitlines()) if d]
    return min(dts) if dts else None


def _git_skill_changes(root: Path) -> tuple[bool, list[dict]]:
    """SKILL.md を変えた commit ごとの版(内容の識別子つき)。古い順。git が使えなければ (False, [])。読むだけ。"""
    try:
        out = _git(root, "log", "--format=@@%h %ad", "--date=short", "--name-only", "--", SKILLS_DIR)
    except (OSError, subprocess.SubprocessError):
        return False, []
    if out.returncode != 0:
        return False, []
    entries: list[dict] = []
    sha = date = None
    for line in out.stdout.splitlines():
        if line.startswith("@@"):
            parts = line[2:].split(" ", 1)
            sha = parts[0] if parts and _SHA.match(parts[0]) else None
            date = parts[1] if len(parts) == 2 and _DATE.match(parts[1]) else None
            continue
        m = _CHANGED.match(line.strip())
        if m and sha and date and _SKILL_NAME.match(m.group(1)):
            entries.append({"skill": m.group(1), "commit": sha, "date": date, "_path": line.strip()})
    for e in entries:
        blob = _git(root, "show", f"{e['commit']}:{e['_path']}", text=False)
        e["version_key"] = skill_content_key(blob.stdout) if blob.returncode == 0 else None
        del e["_path"]
    entries.reverse()  # git log は新しい順
    return True, entries


def _experience_files(root: Path) -> list[Path]:
    base = Path(root) / EXPERIENCE_DIR
    if not base.is_dir():
        return []
    files: list[Path] = []
    for month in sorted(d for d in base.iterdir() if d.is_dir() and _MONTH_DIR.match(d.name)):
        files.extend(month.glob("session-*.jsonl"))
    return files


def _event_version(e: dict) -> tuple[str | None, str | None]:
    key = e.get("skill_key")
    ver = e.get("skill_version")
    key = key if isinstance(key, str) and _SKILL_KEY.match(key) else None
    ver = ver if isinstance(ver, str) and _VERSION.match(ver) else None
    return key, ver


def _duration_ms(e: dict) -> int | None:
    v = e.get("duration_ms")
    if isinstance(v, bool) or not isinstance(v, int) or not (0 <= v <= _MAX_MS):
        return None
    return v


def _new_cell(source: str) -> dict:
    return {"source": source, "success_all": 0, "success_post": 0, "failure_all": 0, "failure_post": 0,
            "retry": 0, "retry_success": 0, "post_events": 0, "durations": [], "version": None,
            "sessions": set(), "first": None, "last": None}


def _kept(n: int, observed: bool) -> int | None:
    """0 は観測済みの行でだけ 0 と書く。観測していない行の 0 は null(起きなかったとは言えない)。"""
    return n if (n > 0 or observed) else None


def collect(root: Path, period: str | None = None) -> dict:
    """集計の本体。副作用なし(読むだけ)。period を渡すと、その月の行だけ作る(YYYY-MM)。"""
    root = Path(root)
    since = _failure_hook_since(root)
    git_ok, versions = _git_skill_changes(root)
    totals = {"sessions_scanned": 0, "files_read": 0, "files_unreadable": 0, "rows_read": 0,
              "rows_excluded": 0, "rows_without_timestamp": 0, "git_available": git_ok,
              "failure_hook_registered_since": since.isoformat() if since else None,
              "failure_firing_confirmed": False, "period_filter": period}
    cells: dict[tuple[str, str, str | None], dict] = {}
    session_commits: dict[str, bool] = {}
    session_ended: set[str] = set()

    for sid, paths in group_session_files(_experience_files(root)).items():
        totals["sessions_scanned"] += 1
        seq: list[dict] = []
        for path in paths:
            totals["files_read"] += 1
            try:
                events = _read_events(path)
            except OSError:
                totals["files_unreadable"] += 1  # 読めないファイルは黙って飛ばす(件数だけ残す)
                continue
            for e in events:
                totals["rows_read"] += 1
                if e.get("visibility") != "public" or e.get("repo") not in PUBLIC_REMOTES:
                    totals["rows_excluded"] += 1
                    continue
                kind = e.get("event")
                if kind == "session_end":
                    session_ended.add(sid)
                    if isinstance(e.get("commits"), list) and e["commits"]:
                        session_commits[sid] = True
                    continue
                if kind not in ("skill", "skill_failure"):
                    continue
                ts = _parse_ts(e.get("ts"))
                if ts is None:
                    totals["rows_without_timestamp"] += 1
                    continue
                if kind == "skill_failure":
                    totals["failure_firing_confirmed"] = True
                name, source = _skill_ref(e.get("skill"), root)
                key, ver = _event_version(e)
                seq.append({"kind": kind, "ts": ts, "month": e["ts"][:7], "name": name, "source": source,
                            "key": key, "version": ver, "dur": _duration_ms(e), "retry": False})

        # 再試行: 同じ Skill の直前の呼び出しが失敗だったもの(セッション内の追記順)
        last_kind: dict[str, str] = {}
        for ev in seq:
            ev["retry"] = last_kind.get(ev["name"]) == "skill_failure"
            last_kind[ev["name"]] = ev["kind"]

        for ev in seq:
            if period and ev["month"] != period:
                continue
            cell = cells.setdefault((ev["month"], ev["name"], ev["key"]), _new_cell(ev["source"]))
            post = since is not None and ev["ts"] >= since
            cell["sessions"].add(sid)
            day = ev["ts"].date().isoformat()
            cell["first"] = min(filter(None, [cell["first"], day]))
            cell["last"] = max(filter(None, [cell["last"], day]))
            cell["post_events"] += 1 if post else 0
            if ev["version"] and not cell["version"]:
                cell["version"] = ev["version"]
            if ev["dur"] is not None:
                cell["durations"].append(ev["dur"])
            if ev["kind"] == "skill":
                cell["success_all"] += 1
                cell["success_post"] += 1 if post else 0
            else:
                cell["failure_all"] += 1
                cell["failure_post"] += 1 if post else 0
            if ev["retry"]:
                cell["retry"] += 1
                cell["retry_success"] += 1 if ev["kind"] == "skill" else 0

    version_label = {(v["skill"], v["version_key"]): f"{v['commit']} {v['date']}"
                     for v in versions if v["version_key"]}
    rows = []
    for (month, name, key) in sorted(cells, key=lambda k: (k[0], k[1], k[2] or "")):
        c = cells[(month, name, key)]
        observed = since is not None and c["post_events"] > 0
        attempts = c["success_post"] + c["failure_post"]
        rows.append({
            "schema": SCHEMA,
            "period": month,
            "skill": name,
            "source": c["source"],
            "version_key": key,
            "version_label": version_label.get((name, key)),
            "version": c["version"],
            "total_invocations": c["success_all"],
            "success_count": c["success_all"],
            "failure_count": _kept(c["failure_all"], observed),
            "success_rate": round(c["success_post"] / attempts, 3) if observed and attempts > 0 else None,
            "retry_count": _kept(c["retry"], observed),
            "retry_success_count": _kept(c["retry_success"], observed),
            "failure_observed": observed,
            "sessions": len(c["sessions"]),
            "first_seen": c["first"],
            "last_seen": c["last"],
            "sessions_with_commits": sum(1 for s in c["sessions"] if session_commits.get(s)),
            "sessions_with_session_end": sum(1 for s in c["sessions"] if s in session_ended),
            "avg_duration_seconds": (round(sum(c["durations"]) / len(c["durations"]) / 1000, 3)
                                     if c["durations"] else None),
        })
    listed = [{"skill": v["skill"], "version_key": v["version_key"], "commit": v["commit"], "date": v["date"]}
              for v in versions if not period or v["date"][:7] == period]
    return {
        "schema": SCHEMA,
        "definitions": DEFINITIONS,
        "not_recorded": NOT_RECORDED,
        "totals": totals,
        "versions": listed,
        "rows": rows,
    }


def render_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)


def render_jsonl(report: dict) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in report["rows"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Skill の利用実績を読み取り専用で集計する(WikiSkill E / v2)")
    ap.add_argument("--root", default=None, help="対象リポジトリ(既定は作業中のリポジトリ)")
    ap.add_argument("--period", default=None, help="月(YYYY-MM)。省略で全期間")
    ap.add_argument("--format", choices=("json", "jsonl"), default="json", help="出力の形式(既定 json)")
    a = ap.parse_args(argv)
    if a.period and not _PERIOD.match(a.period):
        ap.error("--period は YYYY-MM の形で指定してください")
    root = Path(a.root) if a.root else project_dir()
    report = collect(root, a.period)
    print(render_jsonl(report) if a.format == "jsonl" else render_json(report), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
