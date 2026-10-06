#!/usr/bin/env python3
"""Baseline Debt(既知の赤)の固定と比較。

背景: WikiSkill Phase 1 の開始時点で、origin/main に既に失敗している検査が2つあった
      (check_repo_scope / tests/skill_validation)。Phase 1 由来ではないが、放置すると
      「Phase 1 が新たな違反を足していないこと」を証明できない。そこで現状を機械比較できる形で
      固定し、以降のタスクは --compare で「増えていない(SAME / IMPROVED)」ことを示す。

使い方:
    python3 scripts/baseline_debt.py --record [--force]   # docs/wikiskill/baseline-debt.json を書く
    python3 scripts/baseline_debt.py --compare [--json]   # 現状と比較。REGRESSION なら exit 1

注意: 記録先の JSON には検査語(禁止語)そのものが入る。そのため check_repo_scope.ALLOWED に登録してある。
"""

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_repo_scope  # noqa: E402

DEFAULT_PATH = ROOT / "docs" / "wikiskill" / "baseline-debt.json"
BASE_REF = "origin/main@04dbc28f4"
NOTE = "Phase 1 開始時点の既知の赤。Phase 1 ではこれを増やさない(小柳さん 2026-10-06 承認)"
CHECK_NAMES = ("check_repo_scope", "skill_validation")

# 検査ごとの固定メタデータ(事実の記録。items だけが実測値)。
CHECK_META = {
    "check_repo_scope": {
        "command": "python3 scripts/check_repo_scope.py",
        "cause": (
            "2026-10-02 に追加された8つの SKILL.md と、2026-10-06 に自動生成された週次の学びが、"
            "check_repo_scope.FORBIDDEN_CONTENT の1語目(kakei-crm 側の統合名)を本文に含む。"
            "repo-scope CI は赤だが、赤でも配布 cron・マージを止める仕組みが無く、"
            "update-skills.sh にも配布前検査が無いため11リポジトリへ拡散した(台帳: FK-006)。"
        ),
        "introduced_by": ["6044bb918", "f065ef5a7", "68343664b"],
        "detected_at": "2026-10-06",
    },
    "skill_validation": {
        "command": "python3 -m pytest tests/skill_validation -q",
        "cause": (
            "2026-10-04 に追加された検査(3a193392b)の新フォーマット(手順節・失敗節・ローカル検証節・番号付き)に、"
            "一部の既存スキルが未準拠で、参照先が存在しないスキル参照も残っている。"
            "CI skill-validation.yml は .claude/skills/** を触る PR でしか走らないため main では露見しない。"
        ),
        "introduced_by": ["3a193392b"],
        "detected_at": "2026-10-06",
    },
}


def parse_failed(output):
    """pytest の -rf 出力から FAILED の nodeid をソート済みで返す(' - ' 以降の理由は捨てる)。"""
    items = set()
    for line in output.splitlines():
        if not line.startswith("FAILED "):
            continue
        items.add(line[len("FAILED "):].split(" - ", 1)[0].strip())
    return sorted(items)


def collect_skill_validation():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/skill_validation", "-q", "-rf",
         "--no-header", "-p", "no:cacheprovider"],
        capture_output=True, text=True, cwd=ROOT,
    )
    # 0=全合格 / 1=テスト失敗。それ以外(収集エラー等)は「失敗0件」と誤読しないよう止める。
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"skill_validation を実行できませんでした(exit {proc.returncode}):\n{proc.stdout}{proc.stderr}"
        )
    items = parse_failed(proc.stdout)
    if proc.returncode == 1 and not items:
        raise RuntimeError(f"失敗行を読み取れませんでした:\n{proc.stdout}")
    return items


def collect():
    """現在の違反を {検査名: ソート済み items} で返す。"""
    paths = check_repo_scope.tracked_files()
    scope = {f"{p}::{pat}" for p, pat in check_repo_scope.find_violations(paths)}
    scope |= {f"{p}::{pat}" for p, pat in check_repo_scope.scan_contents(paths)}
    return {
        "check_repo_scope": sorted(scope),
        "skill_validation": sorted(collect_skill_validation()),
    }


def git_short_head():
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True, cwd=ROOT
    ).stdout.strip()


def record(path):
    path = Path(path)
    current = collect()
    checks = {}
    for name in CHECK_NAMES:
        checks[name] = {
            "command": CHECK_META[name]["command"],
            "failure_count": len(current[name]),
            "items": current[name],
            "cause": CHECK_META[name]["cause"],
            "introduced_by": CHECK_META[name]["introduced_by"],
            "detected_at": CHECK_META[name]["detected_at"],
        }
    data = {
        "schema": 1,
        "recorded_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": git_short_head(),
        "base_ref": BASE_REF,
        "phase1_origin": False,
        "note": NOTE,
        "checks": checks,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def diff_checks(baseline, current):
    """検査ごとの差分 {検査名: {baseline, current, delta, new, removed}}。"""
    result = {}
    for name in CHECK_NAMES:
        base = set(baseline["checks"][name]["items"])
        cur = set(current[name])
        result[name] = {
            "baseline": len(base),
            "current": len(cur),
            "delta": len(cur) - len(base),
            "new": sorted(cur - base),
            "removed": sorted(base - cur),
        }
    return result


def verdict_of(diff):
    if any(d["new"] for d in diff.values()):
        return "REGRESSION"
    if any(d["removed"] for d in diff.values()):
        return "IMPROVED"
    return "SAME"


def compare(baseline, current):
    """(verdict, 人が読める delta 表) を返す。new が1件でもあれば REGRESSION。"""
    diff = diff_checks(baseline, current)
    verdict = verdict_of(diff)
    lines = [f"{'検査名':<20}{'baseline':>9}{'current':>9}{'delta':>7}  新規 / 解消"]
    for name, d in diff.items():
        lines.append(f"{name:<20}{d['baseline']:>9}{d['current']:>9}{d['delta']:>+7}")
        for item in d["new"]:
            lines.append(f"    + 新規: {item}")
        for item in d["removed"]:
            lines.append(f"    - 解消: {item}")
    lines.append(f"verdict: {verdict}")
    return verdict, "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Baseline Debt の固定と比較")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true", help="現状を JSON に記録する")
    mode.add_argument("--compare", action="store_true", help="記録と現状を比較する")
    parser.add_argument("--force", action="store_true", help="--record で既存ファイルを上書きする")
    parser.add_argument("--json", action="store_true", help="--compare の結果を JSON で出す")
    parser.add_argument("--path", default=str(DEFAULT_PATH), help="記録先(既定: docs/wikiskill/baseline-debt.json)")
    args = parser.parse_args(argv)
    path = Path(args.path).resolve()
    os.chdir(ROOT)  # tracked_files() は git ls-files を cwd で実行するため、どこから呼ばれても同じ結果にする

    if args.record:
        if path.exists() and not args.force:
            print(f"既に存在します: {path}(上書きするには --force)", file=sys.stderr)
            return 2
        record(path)
        print(f"記録しました: {path}")
        return 0

    baseline = json.loads(path.read_text(encoding="utf-8"))
    current = collect()
    verdict, table = compare(baseline, current)
    if args.json:
        print(json.dumps(
            {"verdict": verdict, "checks": diff_checks(baseline, current)}, ensure_ascii=False, indent=2
        ))
    else:
        print(table)
    return 1 if verdict == "REGRESSION" else 0


if __name__ == "__main__":
    sys.exit(main())
