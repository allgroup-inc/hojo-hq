#!/usr/bin/env python3
"""hojo-hq(公開リポジトリ)に、家計の見直しやさん(enLife)のシステムが混入していないか検査する。

背景: 2026-08-22、アポ管理システム(家計のポっ)と面談予約表を非公開の allgroup-inc/kakei-crm へ移設した。
      本リポジトリは公開であり、顧客の個人情報を扱うシステムを置かない(kakei-crm/CLAUDE.md 絶対ルール7)。
      移設して終わりにすると同じことが繰り返されるため、機械で止める。

使い方:
    python3 scripts/check_repo_scope.py            # git管理下のファイルを検査
    python3 scripts/check_repo_scope.py --selftest # 検査ロジック自体の自己点検

新しく置いてよいものが増えたときは ALLOWED に足す。
禁止パターンを緩めるのは、置き場所の方針そのものの変更にあたるため議事が要る。
"""

import subprocess
import sys

# 本リポジトリに置いてはいけないパス(部分一致)。
# 家計の見直しやさん(enLife)の営業システム = kakei-crm(非公開)の担当。
FORBIDDEN = [
    "apo-kanri/",                  # アポ管理システム(家計のポっ)
    "apps/appointment/",           # 同上(kakei-crm 側の置き場所。こちらに来たら誤り)
    "tests/apo_kanri_",            # 同上のテスト
    "scripts/build_apo_bundle",    # 同上のビルド
    "scripts/churn/",              # 保全CRM(早期解約リスク)
    "家計のポっ",
    "面談予約表",
    "アポ管理",
    "顧客カルテ",
]

# 例外。移設したことを案内する文書など、名前に禁止語を含むが置いてよいもの。
ALLOWED = {
    "docs/移設済み_アポ管理と営業指名_2026-08-22.md",
    "scripts/check_repo_scope.py",
    ".github/workflows/repo-scope.yml",
}

HINT = """
このリポジトリは【公開】です。家計の見直しやさん(enLife)の営業システムは
allgroup-inc/kakei-crm(非公開)に置いてください。

  経緯・移設先: docs/移設済み_アポ管理と営業指名_2026-08-22.md
  根拠:         kakei-crm/CLAUDE.md 絶対ルール7(2026-08-22 小柳さん決定)

判断に迷う置き場所は、先に非公開側へ置いてください。
文書の中で言及するだけなら問題ありません(検査しているのはファイルのパスだけです)。
"""


def find_violations(paths):
    """禁止パターンに触れるパスを返す。ALLOWED のものは除く。"""
    hits = []
    for path in paths:
        if path in ALLOWED:
            continue
        for pattern in FORBIDDEN:
            if pattern in path:
                hits.append((path, pattern))
                break
    return hits


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files", "-z"], capture_output=True, text=True, check=True
    ).stdout
    return [p for p in out.split("\0") if p]


def selftest():
    """検査ロジックが効いていること・例外が効いていることを確かめる。"""
    cases = [
        ("apo-kanri/src/schema.js", True),
        ("tests/apo_kanri_core.test.mjs", True),
        ("docs/家計のポっ_本番投入手順書.md", True),
        ("docs/面談予約表_指示の出し方ガイド_2026-08-14.md", True),
        ("scripts/churn/score.py", True),
        # 置いてよいもの
        ("docs/移設済み_アポ管理と営業指名_2026-08-22.md", False),
        ("site/index.html", False),
        ("insurance-underwriting-tool.html", False),  # 引受目安は公開ツールとして維持
        ("glow-ma/src/schema.js", False),
        ("docs/決裁キュー.md", False),
    ]
    failed = []
    for path, should_hit in cases:
        hit = bool(find_violations([path]))
        if hit != should_hit:
            failed.append(f"  {path}: 期待={should_hit} 実際={hit}")
    if failed:
        print("自己点検に失敗しました:", file=sys.stderr)
        print("\n".join(failed), file=sys.stderr)
        return 1
    print(f"自己点検OK({len(cases)}件)")
    return 0


def main():
    if "--selftest" in sys.argv:
        return selftest()

    violations = find_violations(tracked_files())
    if not violations:
        print("OK: 家計の見直しやさんのシステムは本リポジトリに含まれていません")
        return 0

    print("本リポジトリに置けないファイルがあります:\n", file=sys.stderr)
    for path, pattern in violations:
        print(f"  {path}\n    → 禁止パターン: {pattern}", file=sys.stderr)
    print(HINT, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
