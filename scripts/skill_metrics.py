#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WikiSkill M3 / Component E: Skill Metrics(読み取り専用の集計)。

記録されている数値だけを集計する。記録の無い数値(成功・失敗・再試行・所要時間・版ごとの成績)は
推測せず null にし、理由を not_recorded に書く。何も書き込まない(監査ログも含む)。

入力(既存の記録を再利用する。新しい記録は増やさない):
  - .claude/experience/<月>/session-*.jsonl(本体と part)の skill イベント・session_end イベント
    (PostToolUse の Skill で1回ずつ記録される。成功した呼び出しだけが残る)
  - .claude/skills/<name>/SKILL.md の変更(git log。読むだけ)
出力(stdout のみ): JSON(--format json)または JSONL(--format jsonl。月×Skill の1行。F が読む形)。

公開側への流出を防ぐ規則:
  - 数えるのは visibility が public かつ repo が PUBLIC_REMOTES の行だけ。他リポ・unknown・private は数えない(件数だけ残す)
  - 出すのは Skill 名・件数・日付・短い commit ID。commit の件名・セッションID・本文・パスは出さない
  - Skill 名は英数字と . _ - : の形だけ通す。通らないものは "<unknown>"
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from experience_log import PUBLIC_REMOTES, _read_events  # noqa: E402
from wikiskill_common import EXPERIENCE_DIR, group_session_files, project_dir  # noqa: E402

SCHEMA = "skill-metrics/v1"
UNKNOWN = "<unknown>"
_MONTH_DIR = re.compile(r"^\d{4}-\d{2}$")
_PERIOD = re.compile(r"^\d{4}-\d{2}$")
_TS = re.compile(r"^(\d{4}-\d{2})-(\d{2})T")
_SKILL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SKILL_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")  # プラグインの名前空間付き(例: plugin:skill)
_SHA = re.compile(r"^[0-9a-f]{7,40}$")
_CHANGED = re.compile(r"^\.claude/skills/([^/]+)/SKILL\.md$")
SKILLS_DIR = ".claude/skills"

# 記録されていない数値。値は null で出し、理由をここに書く(推測で埋めない)
NULL_FIELDS = ("success_count", "failure_count", "success_rate", "retry_count",
               "avg_duration_seconds", "versions_used")
NOT_RECORDED = {
    "success_count": "Skill の結果は記録されない(PostToolUse は成功時だけ発火し、PostToolUseFailure は未登録)",
    "failure_count": "失敗した Skill 呼び出しは記録されない(PostToolUseFailure は未登録)",
    "success_rate": "成功・失敗の数が無いため計算できない",
    "retry_count": "再試行は記録されない",
    "avg_duration_seconds": "Skill 単位の所要時間は記録されない(session_end の duration_s はセッション全体)",
    "versions_used": "呼び出し時の版は記録されない(版の変更日は skill_changes に git から出す)",
    "problem_resolution": "問題解決への貢献は記録されない(commit との同時発生は sessions_with_commits で見るだけ)",
}
DEFINITIONS = {
    "total_invocations": "PostToolUse で記録された Skill 呼び出し(成功した呼び出しだけ)",
    "sessions": "その Skill が1回以上呼ばれたセッションの数(セッションIDは出さない)",
    "sessions_with_commits": "同じセッション内で commit が1件以上あったセッションの数。同時発生であって、Skill の成果ではない",
    "skill_changes": "そのSKILL.mdを変えた commit(短いID・日付)。版の番号は持たない",
}


def _valid_ts(ts) -> re.Match | None:
    return _TS.match(ts) if isinstance(ts, str) else None


def _skill_ref(raw, root: Path) -> tuple[str, str]:
    """(表示名, source)。source は project / external / unregistered / unknown。"""
    if not isinstance(raw, str):
        return UNKNOWN, "unknown"
    name = raw.strip()
    if _SKILL_NAME.match(name):
        if (root / SKILLS_DIR / name / "SKILL.md").is_file():
            return name, "project"
        return name, "unregistered"
    if _SKILL_REF.match(name):
        return name, "external"
    return UNKNOWN, "unknown"


def _git_skill_changes(root: Path) -> tuple[bool, dict[str, list[dict]]]:
    """SKILL.md を変えた commit を古い順に返す。git が使えなければ (False, {})。読むだけ。"""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "--format=@@%h %ad", "--date=short", "--name-only",
             "--", SKILLS_DIR],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False, {}
    if out.returncode != 0:
        return False, {}
    changes: dict[str, list[dict]] = {}
    sha = date = None
    for line in out.stdout.splitlines():
        if line.startswith("@@"):
            parts = line[2:].split(" ", 1)
            sha = parts[0] if parts and _SHA.match(parts[0]) else None
            date = parts[1] if len(parts) == 2 and re.match(r"^\d{4}-\d{2}-\d{2}$", parts[1]) else None
            continue
        m = _CHANGED.match(line.strip())
        if m and sha and date and _SKILL_NAME.match(m.group(1)):
            changes.setdefault(m.group(1), []).append({"sha": sha, "date": date})
    for rows in changes.values():
        rows.reverse()  # git log は新しい順。古い順にする
    return True, changes


def _experience_files(root: Path) -> list[Path]:
    base = Path(root) / EXPERIENCE_DIR
    if not base.is_dir():
        return []
    files: list[Path] = []
    for month in sorted(d for d in base.iterdir() if d.is_dir() and _MONTH_DIR.match(d.name)):
        files.extend(month.glob("session-*.jsonl"))
    return files


def collect(root: Path, period: str | None = None) -> dict:
    """集計の本体。副作用なし(読むだけ)。period を渡すと、その月の行だけ作る(YYYY-MM)。"""
    root = Path(root)
    totals = {"sessions_scanned": 0, "files_read": 0, "files_unreadable": 0,
              "rows_read": 0, "rows_excluded": 0, "rows_without_timestamp": 0,
              "git_available": False, "period_filter": period}
    agg: dict[tuple[str, str], dict] = {}
    session_commits: dict[str, bool] = {}
    session_ended: set[str] = set()

    groups = group_session_files(_experience_files(root))
    for sid, paths in groups.items():
        totals["sessions_scanned"] += 1
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
                if kind != "skill":
                    continue
                m = _valid_ts(e.get("ts"))
                if not m:
                    totals["rows_without_timestamp"] += 1
                    continue
                month, day = m.group(1), m.group(2)
                if period and month != period:
                    continue
                name, source = _skill_ref(e.get("skill"), root)
                row = agg.setdefault((month, name), {
                    "source": source, "invocations": 0, "sessions": set(),
                    "first": None, "last": None,
                })
                row["invocations"] += 1
                row["sessions"].add(sid)
                date = f"{month}-{day}"
                row["first"] = min(filter(None, [row["first"], date]))
                row["last"] = max(filter(None, [row["last"], date]))

    git_ok, changes = _git_skill_changes(root)
    totals["git_available"] = git_ok
    for name, items in changes.items():
        for item in items:
            month = item["date"][:7]
            if period and month != period:
                continue
            row = agg.setdefault((month, name), {
                "source": "project" if (root / SKILLS_DIR / name / "SKILL.md").is_file() else "unregistered",
                "invocations": 0, "sessions": set(), "first": None, "last": None,
            })
            row.setdefault("changes", []).append(item)

    rows = []
    for (month, name) in sorted(agg):
        r = agg[(month, name)]
        sessions = r["sessions"]
        changes_here = sorted(r.get("changes", []), key=lambda c: c["date"])
        rows.append({
            "schema": SCHEMA,
            "period": month,
            "skill": name,
            "source": r["source"],
            "total_invocations": r["invocations"],
            "sessions": len(sessions),
            "first_seen": r["first"],
            "last_seen": r["last"],
            "sessions_with_commits": sum(1 for s in sessions if session_commits.get(s)),
            "sessions_with_session_end": sum(1 for s in sessions if s in session_ended),
            **{k: None for k in NULL_FIELDS},
            "skill_changes": changes_here,
        })
    return {
        "schema": SCHEMA,
        "definitions": DEFINITIONS,
        "not_recorded": NOT_RECORDED,
        "totals": totals,
        "rows": rows,
    }


def render_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2)


def render_jsonl(report: dict) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in report["rows"])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Skill の利用実績を読み取り専用で集計する(WikiSkill E)")
    ap.add_argument("--root", default=None, help="対象リポジトリ(既定はこのスクリプトのリポジトリ)")
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
