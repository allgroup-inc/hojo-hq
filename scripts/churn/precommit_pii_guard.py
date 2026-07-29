"""誤コミット自動検知(churn-pii-guard)。

顧客個人情報の恐れがあるファイルのコミットを機械的に止める最後の砦。
公開リポジトリ(allgroup-inc/hojo-hq)にPIIを入れると即・全世界公開&実質恒久になるため、
`.gitignore` 頼みの1点防御に、コミット時の能動的な検知を重ねる。

使い方(git pre-commit フックから):
    python -m scripts.churn.precommit_pii_guard
ステージされたファイルに危険パターンがあれば、理由を表示して exit 1(コミット中断)。
意図的に通す場合のみ、環境変数で許可:
    CHURN_PII_GUARD_ALLOW="path/one,path/two" git commit ...
"""
from __future__ import annotations
import os
import subprocess
import sys

# 顧客データの恐れが高い拡張子(このリポジトリは通常これらを追跡しない)
_RISKY_SUFFIXES = (".csv", ".tsv", ".xlsx", ".xls")


def _reason(path):
    """危険なら日本語の理由、安全なら None。site配下のindex.html等の正規物は検知しない。"""
    p = path.replace("\\", "/")
    base = p.rsplit("/", 1)[-1]
    if p == "private" or p.startswith("private/"):
        return "private/ 配下(顧客データ・モデル・出力の置き場・非コミット)"
    if base.startswith("karte_") and base.endswith(".html"):
        return "顧客カルテ出力(個人情報を含む)"
    if "risk_model" in base and base.endswith(".json"):
        return "リスクモデル(顧客実績由来・非コミット)"
    if base.endswith(_RISKY_SUFFIXES):
        return "表データ(顧客データの恐れ)"
    return None


def find_blocked_paths(staged_paths, allow=()):
    """危険なステージ済みパスと理由の一覧。allow に列挙したパスは除外する。"""
    allowset = set(allow)
    blocked = []
    for p in staged_paths:
        if p in allowset:
            continue
        reason = _reason(p)
        if reason:
            blocked.append((p, reason))
    return blocked


def _staged_paths():
    """追加・変更(A/M)としてステージされたファイルのパス一覧。"""
    res = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
        capture_output=True, text=True)
    return [line for line in res.stdout.splitlines() if line.strip()]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    allow = [p for p in os.environ.get("CHURN_PII_GUARD_ALLOW", "").split(",") if p]
    # 引数でパスを渡せばそれを検査(CI用)、無ければステージ済みを検査(pre-commitフック用)
    paths = argv if argv else _staged_paths()
    blocked = find_blocked_paths(paths, allow)
    if not blocked:
        return 0
    print("⛔ 個人情報の恐れがあるファイルをコミットしようとしています(churn-pii-guard):",
          file=sys.stderr)
    for path, reason in blocked:
        print(f"   - {path}  … {reason}", file=sys.stderr)
    print("これらは private/ 限定・非コミットです。公開リポジトリに入れると全世界へ公開されます。",
          file=sys.stderr)
    print('意図的な場合のみ CHURN_PII_GUARD_ALLOW="<パス>" を付けてコミットしてください。',
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
