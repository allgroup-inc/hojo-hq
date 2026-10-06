#!/usr/bin/env python3
"""Baseline Debt(既知の赤)の固定と比較。

背景: WikiSkill Phase 1 の開始時点で、origin/main に既に失敗している検査が2つあった
      (check_repo_scope / tests/skill_validation)。Phase 1 由来ではないが、放置すると
      「Phase 1 が新たな違反を足していないこと」を証明できない。そこで現状を機械比較できる形で
      固定し、以降のタスクは --compare で「増えていない(SAME / IMPROVED)」ことを示す。

使い方:
    python3 scripts/baseline_debt.py --record [--force]   # docs/wikiskill/baseline-debt.json を書く
    python3 scripts/baseline_debt.py --compare [--json]   # 現状と比較。REGRESSION なら exit 1

注意: 記録先の JSON に検査語(禁止語)そのものは書かない。項目は "<path>::FORBIDDEN_CONTENT[<i>]"
      (本文の語)/ "<path>::FORBIDDEN[<i>]"(パスの語)と、check_repo_scope のリストの番号で記録する。
      そのため記録ファイルを check_repo_scope.ALLOWED に入れる必要はない(例外を広げない)。
"""

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_repo_scope  # noqa: E402

DEFAULT_PATH = ROOT / "docs" / "wikiskill" / "baseline-debt.json"
BASE_REF = "origin/main@04dbc28f4"
NOTE = "Phase 1 開始時点の既知の赤。Phase 1 ではこれを増やさない(小柳さん 2026-10-06 承認)"
CHECK_NAMES = ("check_repo_scope", "skill_validation", "scripts_tests_preexisting")

# tests/scripts 全体ではなく固定のファイル2本だけを走らせる。
# Phase 1 が tests/scripts に足すタイミング依存のテストでゲートが揺れないようにするため。
SCRIPTS_TESTS_FILES = [
    "tests/scripts/test_generate_ig_posts_mikata.py",
    "tests/scripts/test_verify_mikata_seido.py",
]
SKILL_VALIDATION_FILES = ["tests/skill_validation"]

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
    "scripts_tests_preexisting": {
        "command": "python3 -m pytest " + " ".join(SCRIPTS_TESTS_FILES) + " -q",
        "files": SCRIPTS_TESTS_FILES,
        "cause": "2026-10-06 時点で origin/main でも同一に失敗(worktree で確認)。Phase 1 由来ではない。原因は未調査(別タスク)",
        "introduced_by": [],
        "detected_at": "2026-10-06",
    },
}


class CollectionError(RuntimeError):
    """検査を実行できなかった/結果を読み取れなかった。「0件=改善」と誤読しないよう呼び出し側で止める。"""


SKILL_VALIDATION_TIMEOUT = 300
_SUMMARY_COUNT = re.compile(r"(\d+) (failed|errors?)\b")
_SUMMARY_LINE = re.compile(r"\bin \d+(?:\.\d+)?s\b")


def parse_failed(output):
    """pytest の -rfE 出力から FAILED / ERROR の項目をソート済みで返す(' - ' 以降の理由は捨てる)。

    FAILED は nodeid そのもの、ERROR は "ERROR::<nodeid>"(fixture/setup エラーを FAILED と区別する)。
    """
    items = set()
    for line in output.splitlines():
        if line.startswith("FAILED "):
            items.add(line[len("FAILED "):].split(" - ", 1)[0].strip())
        elif line.startswith("ERROR "):
            items.add("ERROR::" + line[len("ERROR "):].split(" - ", 1)[0].strip())
    return sorted(items)


def summary_counts(output):
    """pytest の最終サマリー行から (failed, errors) の件数を返す。サマリー行が無ければ None。"""
    summary = None
    for line in output.splitlines():
        if _SUMMARY_LINE.search(line):
            summary = line
    if summary is None:
        return None
    failed = errors = 0
    for count, kind in _SUMMARY_COUNT.findall(summary):
        if kind == "failed":
            failed = int(count)
        else:
            errors = int(count)
    return failed, errors


def collect_pytest_failures(label, targets):
    """pytest を targets に対して走らせ、FAILED / ERROR の項目(ソート済み)を返す。"""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *targets, "-q", "-rfE",
             "--no-header", "-p", "no:cacheprovider"],
            capture_output=True, text=True, cwd=ROOT, timeout=SKILL_VALIDATION_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise CollectionError(
            f"{label} が {SKILL_VALIDATION_TIMEOUT} 秒以内に終わりませんでした"
        ) from None
    # 0=全合格 / 1=テスト失敗。それ以外(収集エラー=2、テスト無し=5 等)は「失敗0件」と誤読しないよう止める。
    if proc.returncode not in (0, 1):
        raise CollectionError(
            f"{label} を実行できませんでした(exit {proc.returncode}):\n{proc.stdout}{proc.stderr}"
        )
    items = parse_failed(proc.stdout)
    if proc.returncode == 0:
        if items:
            raise CollectionError(f"exit 0 なのに失敗行があります:\n{proc.stdout}")
        return items
    if not items:
        raise CollectionError(f"失敗行を読み取れませんでした:\n{proc.stdout}")
    # サマリー行の件数と読み取った項目数が合わなければ、取りこぼしがあるので止める。
    counts = summary_counts(proc.stdout)
    n_failed = sum(1 for i in items if not i.startswith("ERROR::"))
    n_errors = len(items) - n_failed
    if counts is None or counts != (n_failed, n_errors):
        raise CollectionError(
            f"サマリー行の件数と読み取った項目数が一致しません"
            f"(サマリー={counts} 項目: failed={n_failed} error={n_errors}):\n{proc.stdout}"
        )
    return items


def collect_skill_validation():
    return collect_pytest_failures("skill_validation", SKILL_VALIDATION_FILES)


def collect_scripts_tests_preexisting():
    return collect_pytest_failures("scripts_tests_preexisting", SCRIPTS_TESTS_FILES)


def tracked_files():
    """git 管理下のパス(ROOT 基準。呼び出し元の cwd に依存しない)。"""
    out = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, text=True, check=True, cwd=ROOT
    ).stdout
    return [p for p in out.split("\0") if p]


def scan_scope_items(paths):
    """check_repo_scope の違反を "<path>::FORBIDDEN[<i>]" / "<path>::FORBIDDEN_CONTENT[<i>]" の集合で返す。

    check_repo_scope.scan_contents は1ファイルにつき最初の1語しか返さない。
    既存の違反ファイルに別の禁止語が足されても隠れないよう、ここでは全パターンを個別に数える。
    語そのものではなくリストの番号で記録するので、記録ファイルに禁止語の実文字列が入らない。
    (check_repo_scope 自体の挙動は変えない)
    """
    items = {
        f"{p}::FORBIDDEN[{check_repo_scope.FORBIDDEN.index(pat)}]"
        for p, pat in check_repo_scope.find_violations(paths)
    }
    for path in paths:
        if path in check_repo_scope.ALLOWED:
            continue
        text = check_repo_scope.read_text(str(ROOT / path))
        if text is None:
            continue
        for i, pattern in enumerate(check_repo_scope.FORBIDDEN_CONTENT):
            if pattern in text:
                items.add(f"{path}::FORBIDDEN_CONTENT[{i}]")
    return items


def collect():
    """現在の違反を {検査名: ソート済み items} で返す。"""
    return {
        "check_repo_scope": sorted(scan_scope_items(tracked_files())),
        "skill_validation": sorted(collect_skill_validation()),
        "scripts_tests_preexisting": sorted(collect_scripts_tests_preexisting()),
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
            **({"files": CHECK_META[name]["files"]} if "files" in CHECK_META[name] else {}),
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
    lines = [f"{'検査名':<27}{'baseline':>9}{'current':>9}{'delta':>7}  新規 / 解消"]
    for name, d in diff.items():
        lines.append(f"{name:<27}{d['baseline']:>9}{d['current']:>9}{d['delta']:>+7}")
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

    if args.record:
        if path.exists() and not args.force:
            print(f"既に存在します: {path}(上書きするには --force)", file=sys.stderr)
            return 2
        try:
            record(path)
        except CollectionError as e:
            print(f"収集に失敗しました: {e}", file=sys.stderr)
            return 1
        print(f"記録しました: {path}")
        return 0

    baseline = json.loads(path.read_text(encoding="utf-8"))
    try:
        current = collect()
    except CollectionError as e:
        print(f"収集に失敗しました: {e}", file=sys.stderr)
        return 1
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
