#!/usr/bin/env python3
"""wiki-guard(決裁 #26 S2 PR-B): 正式な Wiki を変える PR の「作者」を検査する。

守る対象 = `docs/wiki/` 直下の `*.md`(正式な Wiki。`_candidates/` `_archive/` `_synonyms.txt` は候補・退役・補助なので対象外。
`scripts/direct_push_watch.py` の OFFICIAL_WIKI_GLOB と同じ規則)。

違反 = PR の作者(github.event.pull_request.user.login)が Claude Code 用アカウント(repository variable
`HOJO_CLAUDE_LOGIN`)で、かつ変更ファイルに正式な Wiki を含む。正式な Wiki は小柳さんのアカウントで PR を開く
(docs/wikiskill/Wiki昇格手順.md)。

休眠: `claude_login` が空(variable 未登録)なら**常に違反なし**。S7b(アカウント分離)で小柳さんが variable を
登録するまで、この検査は何も止めない。workflow 側(.github/workflows/repo-scope.yml)も step の `if:` と早期終了で
二重に休眠させている。

他の統制との分担: CODEOWNERS(承認者)/ wiki_validate.py(中身)/ main-direct-push-watch(直接 push の事後記録)。
この検査は「誰が PR を開いたか」だけを見る。commit 単位の作者・直接 push・別アカウントは見ない。

使い方:
  python3 scripts/wiki_guard.py --selftest
  python3 scripts/wiki_guard.py --files-from changed.txt --author <login> --claude-login <login|空>
      → 違反パスを 1 行ずつ出力。違反あり exit 3 / 無し exit 0 / 引数不正 exit 2
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

OFFICIAL_WIKI_DIR = "docs/wiki/"
EXIT_MATCHED = 3


def is_official_wiki(path: str) -> bool:
    """docs/wiki/ 直下の .md だけ(深い階層・_candidates/・_archive/・.md 以外は対象外)。"""
    if not path.startswith(OFFICIAL_WIKI_DIR):
        return False
    rest = path[len(OFFICIAL_WIKI_DIR):]
    return bool(rest) and "/" not in rest and rest.endswith(".md")


def _same_login(a: str, b: str) -> bool:
    """GitHub のログイン名は大文字小文字を区別しない。"""
    return a.strip().casefold() == b.strip().casefold()


def violations(changed_files, pr_author: str | None, claude_login: str | None) -> list[str]:
    """違反する変更パスを返す(空なら通す)。

    - claude_login が空 → 休眠(常に空)
    - pr_author が空(PR 以外のイベント)→ 比較できないので空
    - 作者が Claude 用アカウントでなければ空(小柳さん・App の bot など)
    - 作者が一致 → 変更ファイルのうち正式な Wiki(docs/wiki/*.md 直下)を返す
    """
    if not claude_login or not claude_login.strip():
        return []
    if not pr_author or not pr_author.strip():
        return []
    if not _same_login(pr_author, claude_login):
        return []
    return sorted({f.strip() for f in changed_files if f and f.strip() and is_official_wiki(f.strip())})


def selftest() -> int:
    claude, human = "claude-hojo", "takeshikoyanagi9-lab"
    cases = [
        # (名前, files, author, login, 期待)
        ("正式 Wiki を Claude が変える", ["docs/wiki/W001.md"], claude, claude, ["docs/wiki/W001.md"]),
        ("候補・退役・補助は対象外", ["docs/wiki/_candidates/c.md", "docs/wiki/_archive/old.md", "docs/wiki/_synonyms.txt"], claude, claude, []),
        ("作者が小柳さんなら通す", ["docs/wiki/W001.md"], human, claude, []),
        ("休眠: login 空", ["docs/wiki/W001.md"], claude, "", []),
        ("休眠: login None", ["docs/wiki/W001.md"], claude, None, []),
        ("App の bot は対象外", ["docs/wiki/W001.md"], "hojo-app[bot]", claude, []),
        ("直下だけ(深い階層・他の docs は対象外)", ["docs/wiki/W001.md", "docs/x.md", "docs/wiki/sub/W002.md", "docs/wikis/W003.md"], claude, claude, ["docs/wiki/W001.md"]),
        ("ログイン名は大文字小文字を区別しない", ["docs/wiki/W001.md"], "Claude-Hojo", claude, ["docs/wiki/W001.md"]),
        ("author 空(PR 以外)", ["docs/wiki/W001.md"], "", claude, []),
        ("docs/wiki そのもの・空行は無視", ["docs/wiki/", "", "docs/wiki/.md"], claude, claude, ["docs/wiki/.md"]),
    ]
    failed = 0
    for name, files, author, login, expected in cases:
        got = violations(files, author, login)
        ok = got == expected
        failed += 0 if ok else 1
        print(("OK " if ok else "NG ") + f"{name} → {got}")
    print(f"自己点検{'OK' if not failed else 'NG'}({len(cases)} 件)")
    return 0 if not failed else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--files-from", help="PR の変更ファイル一覧(1 行 1 パス)")
    ap.add_argument("--author", help="PR の作者のログイン名")
    ap.add_argument("--claude-login", help="Claude 用アカウントのログイン名(空なら休眠)")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.files_from or a.author is None or a.claude_login is None:
        ap.error("--selftest か、--files-from と --author と --claude-login の 3 つが要る")
    files = Path(a.files_from).read_text(encoding="utf-8").splitlines()
    hits = violations(files, a.author, a.claude_login)
    for h in hits:
        print(h)
    return EXIT_MATCHED if hits else 0


if __name__ == "__main__":
    sys.exit(main())
