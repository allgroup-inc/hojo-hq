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
    "apps/retention/",             # 同上(kakei-crm 側の置き場所)
    "atokakunin",                  # 送信型後確認(SMS)
    "apps/confirmation/",          # 同上(kakei-crm 側の置き場所)
    "家計のポっ",
    "面談予約表",
    "アポ管理",
    "顧客カルテ",
    "後確認",
    # 引受目安(2026-08-24 小柳さん決裁で公開終了)。
    # 3社の原本に「代理店様限り」等の取扱制限があり、公開リポジトリに置けない。
    # 移設先は pamphlet-shelf(非公開)。
    "insurance-underwriting-tool",
    "underwriting_full",
    "お引受のめやす",
    "引受けの目安",
]

# 本文に含まれていたら止める語(部分一致)。名前が無害でも中身が kakei-crm の運用仕様なら公開できない。
# 2026-09-29: KAKEHASHI統合検証メモ5点が、名前に禁止語を含まないためパス検査を素通りした。
# 言及ではなく仕様そのものに出る語(APIの入口・権限定数・環境変数名)だけを並べる。
FORBIDDEN_CONTENT = [
    "KAKEHASHI",              # enLife 9システム統合の名称
    "/api/aftercheck/",       # kakei-crm の API 入口
    "/api/retention/",
    "/api/handoffs/",
    "/api/customers/",
    "kakei-crm/api",
    "KAKEI_CRM_",             # kakei-crm の環境変数名
    "LAYER_VIEW",             # kakei-crm の権限層の定数
    "LAYER_EDIT",
]

# 例外。移設したことを案内する文書など、名前に禁止語を含むが置いてよいもの。
ALLOWED = {
    "docs/移設済み_アポ管理と営業指名_2026-08-22.md",
    "scripts/check_repo_scope.py",
    ".github/workflows/repo-scope.yml",
    "docs/wikiskill/baseline-debt.json",  # 検査結果の記録ファイル。検査語を含まざるを得ない(Baseline Debt 固定・FK-006)
}

HINT = """
このリポジトリは【公開】です。家計の見直しやさん(enLife)の営業システムは
allgroup-inc/kakei-crm(非公開)に置いてください。

  経緯・移設先: docs/移設済み_アポ管理と営業指名_2026-08-22.md
  根拠:         kakei-crm/CLAUDE.md 絶対ルール7(2026-08-22 小柳さん決定)

判断に迷う置き場所は、先に非公開側へ置いてください。
文書の中で言及するだけなら問題ありません。ただし API の入口・権限の層・環境変数名など
運用仕様そのものは、ファイル名が無害でも本文で検査して止めます(FORBIDDEN_CONTENT)。
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


def find_content_violations(path, text):
    """本文が FORBIDDEN_CONTENT に触れていれば最初の1語を返す。ALLOWED は除く。"""
    if path in ALLOWED:
        return None
    for pattern in FORBIDDEN_CONTENT:
        if pattern in text:
            return pattern
    return None


def read_text(path):
    """テキストとして読めるファイルだけ返す。バイナリ(NULを含む)と読めないものは None。"""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="ignore")


def scan_contents(paths):
    hits = []
    for path in paths:
        text = read_text(path)
        if text is None:
            continue
        pattern = find_content_violations(path, text)
        if pattern:
            hits.append((path, pattern))
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
        ("scripts/atokakunin_rules.py", True),
        ("docs/後確認SMS_段取り_2026-08-18.md", True),
        ("insurance-underwriting-tool.html", True),   # 2026-08-24 公開終了(代理店限定資料由来)
        ("docs/insurance/underwriting_full.json", True),
        ("【なないろ生命】お引受のめやす(2026.4)公開用 (6).pdf", True),
        # 置いてよいもの
        ("docs/移設済み_アポ管理と営業指名_2026-08-22.md", False),
        ("site/index.html", False),
        ("glow-ma/src/schema.js", False),
        ("docs/決裁キュー.md", False),
    ]
    failed = []
    for path, should_hit in cases:
        hit = bool(find_violations([path]))
        if hit != should_hit:
            failed.append(f"  {path}: 期待={should_hit} 実際={hit}")

    content_cases = [
        ("docs/検証メモ.md", "POST /api/aftercheck/pending を第1層で", True),
        ("docs/統合.md", "# KAKEHASHI 統合検証チェックリスト", True),
        ("docs/手順.md", "環境変数 KAKEI_CRM_CHOICES_URL を投入", True),
        ("docs/権限.md", "actor.layer < schema.LAYER_EDIT", True),
        # 置いてよいもの(言及・無関係のAPI・日本語の本文)
        ("CLAUDE.md", "出口3: 法人保険・家計の見直しやさんへのクロス導線", False),
        ("docs/plan.md", "POST to `/api/meeting-signup` or Google Form", False),
        ("docs/メモ.md", "後確認チャットへ連携メモを送った(詳細は非公開側)", False),
        ("scripts/check_repo_scope.py", "KAKEHASHI /api/aftercheck/", False),
    ]
    for path, text, should_hit in content_cases:
        hit = find_content_violations(path, text) is not None
        if hit != should_hit:
            failed.append(f"  本文 {path}: 期待={should_hit} 実際={hit}")

    if failed:
        print("自己点検に失敗しました:", file=sys.stderr)
        print("\n".join(failed), file=sys.stderr)
        return 1
    print(f"自己点検OK({len(cases) + len(content_cases)}件)")
    return 0


def main():
    if "--selftest" in sys.argv:
        return selftest()

    paths = tracked_files()
    violations = find_violations(paths)
    content_violations = scan_contents(paths)
    if not violations and not content_violations:
        print("OK: 家計の見直しやさんのシステムは本リポジトリに含まれていません")
        return 0

    if violations:
        print("本リポジトリに置けないファイルがあります:\n", file=sys.stderr)
        for path, pattern in violations:
            print(f"  {path}\n    → 禁止パターン: {pattern}", file=sys.stderr)
    if content_violations:
        print("\n本文に kakei-crm の運用仕様を含むファイルがあります:\n", file=sys.stderr)
        for path, pattern in content_violations:
            print(f"  {path}\n    → 本文の禁止語: {pattern}", file=sys.stderr)
    print(HINT, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
