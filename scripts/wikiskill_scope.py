#!/usr/bin/env python3
"""wikiskill-tests の対象パス(決裁 #26 S2 PR-A2)。

`.github/workflows/wikiskill-tests.yml` は全 PR で起動し(S7a で必須 status check にするため)、
PR の変更ファイルがここの PATTERNS に 1 つも当たらなければテストを省略して緑で終わる。
push 起動の paths フィルタは同じ一覧を使う(`--check-workflow` で一致を検査する)。

パターンの意味は GitHub Actions の paths フィルタと同じ:
  `*`  … `/` 以外の 0 文字以上   `**` … `/` を含む 0 文字以上   `?` … `/` 以外の 1 文字
  それ以外はそのままの文字。パス全体に一致させる。

使い方:
  python3 scripts/wikiskill_scope.py --selftest
  python3 scripts/wikiskill_scope.py --files-from changed.txt     # 該当パスを出力。該当あり exit 3 / 無し exit 0
  python3 scripts/wikiskill_scope.py --check-workflow .github/workflows/wikiskill-tests.yml
                                                                  # push: paths が PATTERNS と一致しなければ exit 1
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ".github/workflows/wikiskill-tests.yml"
EXIT_MATCHED = 3

# wikiskill-tests.yml の push: paths と同じ 27 件(順序も同じ)。変えるときは両方を変える。
PATTERNS = [
    "scripts/wikiskill_common.py",
    "scripts/experience_log.py",
    "scripts/decision_memory.py",
    "scripts/memory_bootstrap.py",
    "scripts/check_experience_privacy.py",
    "scripts/experience_archive.py",
    "scripts/baseline_debt.py",
    ".claude/hooks/wikiskill-hook.sh",
    "tests/scripts/test_*.py",
    "tests/integration/test_wikiskill_memory_e2e.py",
    "tests/integration/test_wikiskill_wiki_e2e.py",
    ".github/workflows/wikiskill-tests.yml",
    "CLAUDE.md",
    "docs/**",
    ".claude/skills/**",
    ".claude/settings.json",
    ".gitignore",
    "scripts/check_repo_scope.py",
    "scripts/wiki_schema.py",
    "scripts/wiki_validate.py",
    "docs/wiki/**",
    "scripts/wikiskill_lock.py",
    "scripts/knowledge_extract.py",
    ".github/workflows/knowledge-extract.yml",
    ".github/workflows/repo-scope.yml",
    ".github/CODEOWNERS",
    "scripts/wiki_guard.py",
]


def to_regex(pattern: str) -> re.Pattern:
    """GitHub Actions の paths パターンを、パス全体に一致する正規表現にする。"""
    out, i = [], 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return re.compile("^" + "".join(out) + "$")


_COMPILED = [(p, to_regex(p)) for p in PATTERNS]


def matches(path: str, patterns=None) -> bool:
    comp = _COMPILED if patterns is None else [(p, to_regex(p)) for p in patterns]
    return any(rx.match(path) for _, rx in comp)


def in_scope(paths, patterns=None) -> list[str]:
    """対象パターンに当たるパスを返す(追加・削除・変更・リネーム前後のどのパスでも、当たれば対象)。"""
    return sorted({p for p in paths if p and matches(p, patterns)})


def workflow_push_paths(text: str) -> list[str]:
    """wikiskill-tests.yml の `push:` ブロックの paths を文字列処理で取り出す(PyYAML に依存しない)。"""
    m = re.search(r"^  push:\n    paths:\n((?:      - '.*'\n)+)", text, re.M)
    if not m:
        return []
    return re.findall(r"^      - '(.*)'$", m.group(1), re.M)


def workflow_pull_request_has_paths(text: str) -> bool:
    return re.search(r"^  pull_request:\n    paths:", text, re.M) is not None


def selftest() -> int:
    cases = [
        # (path, 期待)
        ("docs/議事/議事_20261008_x.md", True),
        ("docs/wiki/W001.md", True),
        ("docs/x.md", True),
        ("docs2/x.md", False),
        ("tests/scripts/test_wiki_schema.py", True),
        ("tests/scripts/sub/test_x.py", False),   # `*` は `/` に一致しない
        ("tests/scripts/helper.py", False),
        ("CLAUDE.md", True),
        ("README.md", False),
        ("scripts/wiki_schema.py", True),
        ("scripts/fg_seo.py", False),
        (".claude/skills/humanizer/SKILL.md", True),
        (".claude/commands/brief.md", False),
        (".gitignore", True),
        ("site/index.html", False),
        ("data/subsidies.json", False),
    ]
    failed = 0
    for path, expected in cases:
        got = matches(path)
        ok = got == expected
        failed += 0 if ok else 1
        print(("OK " if ok else "NG ") + f"{path} → {got}")
    wf = (ROOT / WORKFLOW).read_text(encoding="utf-8")
    sync = workflow_push_paths(wf) == PATTERNS
    failed += 0 if sync else 1
    print(("OK " if sync else "NG ") + f"workflow の push: paths と PATTERNS が一致({len(PATTERNS)} 件)")
    print(f"自己点検{'OK' if not failed else 'NG'}({len(cases) + 1} 件)")
    return 0 if not failed else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--files-from", help="変更ファイル一覧(1 行 1 パス)")
    ap.add_argument("--check-workflow", help="push: paths が PATTERNS と一致するか検査する yml")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.check_workflow:
        got = workflow_push_paths(Path(a.check_workflow).read_text(encoding="utf-8"))
        if got != PATTERNS:
            print("NG: workflow の push: paths と PATTERNS が一致しません", file=sys.stderr)
            print(" workflow:", got, file=sys.stderr)
            print(" PATTERNS:", PATTERNS, file=sys.stderr)
            return 1
        print(f"OK: push: paths {len(got)} 件が PATTERNS と一致")
        return 0
    if not a.files_from:
        ap.error("--selftest / --files-from / --check-workflow のどれかが要る")
    paths = [l.strip() for l in Path(a.files_from).read_text(encoding="utf-8").splitlines()]
    hits = in_scope(paths)
    for h in hits:
        print(h)
    return EXIT_MATCHED if hits else 0


if __name__ == "__main__":
    sys.exit(main())
