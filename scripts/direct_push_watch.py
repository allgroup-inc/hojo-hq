#!/usr/bin/env python3
"""main への「PR を経由しない直接 commit」が守りの範囲を変えたかを判定する(決裁 #26 S1)。

守りの範囲 = `.github/CODEOWNERS` に書かれたパス(Trust Boundary と `docs/wiki/`)+
正式な Wiki `docs/wiki/*.md`(直下だけ。`_candidates/` `_archive/` は候補・退役なので対象外)。

判定・重複計画・重複解消はこのファイルの純粋関数に閉じ込め、workflow
(`.github/workflows/main-direct-push-watch.yml`)は GitHub API で材料を集めてここに渡すだけにする。
本番設定(ruleset)は変えない。検知して Issue に残すところまで。

使い方:
  python3 scripts/direct_push_watch.py --selftest
  python3 scripts/direct_push_watch.py --files-from changed.txt [--has-pr]
      → 該当パスを 1 行ずつ出力。該当があれば exit 3、無ければ exit 0。
  python3 scripts/direct_push_watch.py --plan --existing titles.txt --shas shas.txt
      → 各 SHA(先頭 9 桁)について `reuse <sha9>` か `new <sha9>` を出力(既存 Issue の title に含まれるか)。
  python3 scripts/direct_push_watch.py --dups --issues issues.json
      → 同じ SHA の Issue が複数あれば、最も古い番号を残して閉じるべき番号を `close <番号> <sha9> keep=<番号>` で出力。
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEOWNERS = ".github/CODEOWNERS"
OFFICIAL_WIKI_GLOB = "docs/wiki/*.md"  # 直下だけ(fnmatch の * は / に一致しないよう別途判定)
EXIT_MATCHED = 3
SHA9 = re.compile(r"\b[0-9a-f]{9}\b")


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


def plan(existing_titles, shas) -> list[tuple[str, str]]:
    """各 SHA を `reuse`(既存 Issue の title に先頭 9 桁がある)か `new` に振り分ける。

    同じ run の中で同じ SHA が 2 回出ても 1 回だけ `new` にする(2 回目は reuse)。
    """
    seen = {m for t in existing_titles for m in SHA9.findall(t)}
    out: list[tuple[str, str]] = []
    for sha in shas:
        sha9 = sha.strip()[:9]
        if not sha9:
            continue
        if sha9 in seen:
            out.append(("reuse", sha9))
        else:
            out.append(("new", sha9))
            seen.add(sha9)
    return out


def duplicates(issues) -> list[tuple[int, str, int]]:
    """同じ SHA(title の先頭 9 桁)を持つ Issue が複数あれば、最も若い番号を残し、それ以外を返す。

    issues: [{"number": int, "title": str}, ...]
    返り値: [(閉じる番号, sha9, 残す番号), ...](閉じる番号の昇順)
    """
    by_sha: dict[str, list[int]] = {}
    for it in issues:
        for sha9 in set(SHA9.findall(it.get("title", ""))):
            by_sha.setdefault(sha9, []).append(int(it["number"]))
    out: list[tuple[int, str, int]] = []
    for sha9, nums in by_sha.items():
        nums = sorted(set(nums))
        keep = nums[0]
        out.extend((n, sha9, keep) for n in nums[1:])
    return sorted(out)


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
        use = pats if "候補" not in name else ["scripts/memory_bootstrap.py"]
        got = classify(files, has_pr, use)
        ok = got == expected
        failed += 0 if ok else 1
        print(("OK " if ok else "NG ") + name + ("" if ok else f" → {got} (期待 {expected})"))
    real = codeowners_paths()
    ok = "docs/wiki/" in real and "scripts/memory_bootstrap.py" in real and len(real) >= 20
    failed += 0 if ok else 1
    print(("OK " if ok else "NG ") + f"CODEOWNERS を読めた({len(real)} 件)")
    # 重複計画: 既存 title にある SHA は reuse、無ければ new、同 run 内の 2 回目は reuse
    got = plan(["⚠️ … : 123456789"], ["123456789abc", "abcdef012345", "abcdef012345"])
    ok = got == [("reuse", "123456789"), ("new", "abcdef012"), ("reuse", "abcdef012")]
    failed += 0 if ok else 1
    print(("OK " if ok else "NG ") + f"重複計画 reuse/new → {got}")
    # 重複解消: 同じ SHA の Issue が 2 つなら新しい方を閉じる(競合で二重起票した場合の自己修復)
    got = duplicates([{"number": 12, "title": "x 123456789"}, {"number": 10, "title": "y 123456789"}, {"number": 11, "title": "z abcdef012"}])
    ok = got == [(12, "123456789", 10)]
    failed += 0 if ok else 1
    print(("OK " if ok else "NG ") + f"重複解消 → {got}")
    total = len(cases) + 3
    print(f"自己点検{'OK' if not failed else 'NG'}({total} 件)")
    return 0 if not failed else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--files-from", help="変更ファイル一覧(1 行 1 パス)")
    ap.add_argument("--has-pr", action="store_true", help="この commit が PR に紐づく")
    ap.add_argument("--plan", action="store_true", help="既存 Issue の title と SHA 一覧から reuse/new を決める")
    ap.add_argument("--existing", help="既存 Issue の title(1 行 1 件)")
    ap.add_argument("--shas", help="対象 SHA(1 行 1 件)")
    ap.add_argument("--dups", action="store_true", help="同じ SHA の Issue が複数あれば閉じる番号を出す")
    ap.add_argument("--issues", help="Issue 一覧 JSON([{number,title}])")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.plan:
        if not (a.existing and a.shas):
            ap.error("--plan には --existing と --shas が要る")
        existing = Path(a.existing).read_text(encoding="utf-8").splitlines()
        shas = [l for l in Path(a.shas).read_text(encoding="utf-8").splitlines() if l.strip()]
        for kind, sha9 in plan(existing, shas):
            print(kind, sha9)
        return 0
    if a.dups:
        if not a.issues:
            ap.error("--dups には --issues が要る")
        issues = json.loads(Path(a.issues).read_text(encoding="utf-8"))
        for close, sha9, keep in duplicates(issues):
            print("close", close, sha9, f"keep={keep}")
        return 0
    if not a.files_from:
        ap.error("--selftest / --files-from / --plan / --dups のどれかが要る")
    files = [l.strip() for l in Path(a.files_from).read_text(encoding="utf-8").splitlines() if l.strip()]
    hits = classify(files, a.has_pr)
    for h in hits:
        print(h)
    return EXIT_MATCHED if hits else 0


if __name__ == "__main__":
    sys.exit(main())
