#!/usr/bin/env python3
"""main への「PR を経由しない直接 commit」が守りの範囲を変えたかを判定する(決裁 #26 S1)。

守りの範囲 = `.github/CODEOWNERS` に書かれたパス(Trust Boundary と `docs/wiki/`)+
正式な Wiki `docs/wiki/*.md`(直下だけ。`_candidates/` `_archive/` は候補・退役なので対象外)。

判定は純粋関数 `classify()` に閉じ込め、workflow(`.github/workflows/main-direct-push-watch.yml`)は
GitHub API で「変更ファイル一覧」と「PR に紐づくか」を取ってこの関数に渡すだけにする。
本番設定(ruleset)は変えない。検知して Issue に残すところまで。

使い方:
  python3 scripts/direct_push_watch.py --selftest
  python3 scripts/direct_push_watch.py --files-from changed.txt [--has-pr]
      → 該当パスを 1 行ずつ出力。該当があれば exit 3、無ければ exit 0。
"""
from __future__ import annotations

import argparse
import fnmatch
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEOWNERS = ".github/CODEOWNERS"
OFFICIAL_WIKI_GLOB = "docs/wiki/*.md"  # 直下だけ(fnmatch の * は / に一致しないよう別途判定)
EXIT_MATCHED = 3


def codeowners_paths(root: Path = ROOT) -> list[str]:
    """CODEOWNERS の各行の先頭(パス)を返す。コメント・空行は飛ばす。"""
    text = (root / CODEOWNERS).read_text(encoding="utf-8")
    out: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s.split()[0].lstrip("/"))
    return out


def _matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if any(ch in pattern for ch in "*?["):
        # 直下だけに一致させる: パターンの残り部分に / を含まない
        head, _, tail = pattern.rpartition("/")
        if "/" in path[len(head) + 1:] if head else "/" in path:
            return False
        return fnmatch.fnmatchcase(path, pattern)
    return path == pattern


def classify(changed_files, has_pull_request: bool, patterns=None) -> list[str]:
    """守りの範囲に当たる変更ファイルを返す。PR に紐づく commit は常に空(対象外)。"""
    if has_pull_request:
        return []
    pats = list(patterns) if patterns is not None else codeowners_paths()
    if OFFICIAL_WIKI_GLOB not in pats:
        pats.append(OFFICIAL_WIKI_GLOB)
    hits = {f for f in changed_files for p in pats if _matches(f, p)}
    return sorted(hits)


def selftest() -> int:
    pats = ["docs/wiki/", "scripts/memory_bootstrap.py", ".github/CODEOWNERS"]
    cases = [
        # (名前, 変更ファイル, PR あり, 期待)
        ("正例: Trust Boundary のスクリプト", ["scripts/memory_bootstrap.py", "README.md"], False, ["scripts/memory_bootstrap.py"]),
        ("正例: 正式 Wiki 直下", ["docs/wiki/W001.md"], False, ["docs/wiki/W001.md"]),
        ("正例: CODEOWNERS 自身", [".github/CODEOWNERS"], False, [".github/CODEOWNERS"]),
        ("負例: PR 経由", ["scripts/memory_bootstrap.py"], True, []),
        ("負例: 無関係なデータ更新", ["data/subsidies.json", "site/index.html"], False, []),
        ("負例: Wiki 候補は対象外(CODEOWNERS に docs/wiki/ が無い場合)", ["docs/wiki/_candidates/c.md"], False, []),
    ]
    failed = 0
    for name, files, has_pr, expected in cases:
        # 最後の負例だけ docs/wiki/ プレフィックスを外した表で判定する(直下判定の確認)
        use = pats if "候補" not in name else ["scripts/memory_bootstrap.py"]
        got = classify(files, has_pr, use)
        ok = got == expected
        failed += 0 if ok else 1
        print(("OK " if ok else "NG ") + name + ("" if ok else f" → {got} (期待 {expected})"))
    # 実際の CODEOWNERS が読めて、docs/wiki/ と Trust Boundary を含むこと
    real = codeowners_paths()
    ok = "docs/wiki/" in real and "scripts/memory_bootstrap.py" in real and len(real) >= 20
    failed += 0 if ok else 1
    print(("OK " if ok else "NG ") + f"CODEOWNERS を読めた({len(real)} 件)")
    print(f"自己点検{'OK' if not failed else 'NG'}({len(cases) + 1} 件)")
    return 0 if not failed else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--files-from", help="変更ファイル一覧(1 行 1 パス)")
    ap.add_argument("--has-pr", action="store_true", help="この commit が PR に紐づく")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.files_from:
        ap.error("--selftest か --files-from が要る")
    files = [l.strip() for l in Path(a.files_from).read_text(encoding="utf-8").splitlines() if l.strip()]
    hits = classify(files, a.has_pr)
    for h in hits:
        print(h)
    return EXIT_MATCHED if hits else 0


if __name__ == "__main__":
    sys.exit(main())
