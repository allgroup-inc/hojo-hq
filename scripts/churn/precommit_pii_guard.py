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

# 中身の検知(⑤): 顧客データの"列見出し"に固有の語。1行に3個以上並べば顧客レコードの貼付を疑う。
# 単発の言及(prose)や通常コードでは並ばないので誤検知が低い高シグナル判定。
_CUSTOMER_HEADER_TOKENS = (
    "現ステータス", "受注日", "契約日", "生年月日", "住所", "保険料", "払込経路",
    "申込方法", "市町村", "保険会社", "リスト種類", "顧客ID", "氏名", "解約日",
    "証券番号", "被保険者", "電話番号",
)
_HEADER_HIT_THRESHOLD = 3
# 中身走査の対象外(設計文書・テスト・コード・既存サイト・行政データは該当語が正当に並ぶため)
_CONTENT_EXEMPT_PREFIXES = (
    "docs/", "site/", "posts/", "reports/", "data/", "tests/", "scripts/",
    ".claude/", ".github/",
)


def scan_content(path, text):
    """テキストが顧客データの列見出しらしき行を含むなら理由、無ければ None。

    設計文書やコードで語が並ぶ誤検知を避けるため、対象パスを絞る(_CONTENT_EXEMPT_PREFIXES)。
    """
    p = path.replace("\\", "/")
    if any(p.startswith(pre) for pre in _CONTENT_EXEMPT_PREFIXES):
        return None
    for line in text.splitlines()[:10]:
        hits = sum(1 for t in _CUSTOMER_HEADER_TOKENS if t in line)
        if hits >= _HEADER_HIT_THRESHOLD:
            return f"顧客データの列見出しらしき行を検知(個人情報の恐れ・該当列名 {hits} 個)"
    return None


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


def _read_text(path):
    """テキストとして先頭だけ安全に読む(バイナリ/巨大/欠損は空)。"""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(65536)
    except OSError:
        return ""


def _content_blocked(paths, allow):
    """中身の検知(⑤)。パスblockと重複しないものだけ走査する。"""
    allowset = set(allow)
    out = []
    for p in paths:
        if p in allowset or _reason(p):  # 許可済み or 既にパスでblock済みはスキップ
            continue
        reason = scan_content(p, _read_text(p))
        if reason:
            out.append((p, reason))
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    allow = [p for p in os.environ.get("CHURN_PII_GUARD_ALLOW", "").split(",") if p]
    # 引数でパスを渡せばそれを検査(CI用)、無ければステージ済みを検査(pre-commitフック用)
    paths = argv if argv else _staged_paths()
    blocked = find_blocked_paths(paths, allow) + _content_blocked(paths, allow)
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
