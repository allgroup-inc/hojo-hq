"""公開物の台帳設定(assets/ledger-config.js)が固定スタブと完全一致することを検査する(C4)。

update.yml の Guard (C4) から、upload-pages-artifact の前に実行する。
- 固定スタブと一致しない・存在しない場合は exit 1(公開を止める)。
- Apps Script の URL 形式・非空の台帳設定は警告のみ(正当な利用の有無を確認するまで止めない)。
- 秘密の値は扱わない。判定はバイト列の sha256 だけで、値も sha256 の全体も表示しない。

使い方:
  python scripts/check_ledger_stub.py --selftest
  python scripts/check_ledger_stub.py --root /tmp/pages-deploy
"""
import argparse
import hashlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER_REL = "assets/ledger-config.js"
# 固定スタブの sha256。site/assets/ledger-config.js(追跡中の空設定)と一致する。
# スタブを正当に変えるときは、この値と議事を同時に更新する(変更は必ず議事を伴う)。
EXPECTED_STUB_SHA256 = "3920793f8192fcd9e4f4b8576e8a2c57f79f3b72a98ab233347a2f57672ae3da"

# 警告のみの表現(誤検知の確認が済むまで公開は止めない)
WARN_PATTERNS = {
    "apps_script_url": re.compile(r"script\.google\.com/macros/"),
    "ledger_nonempty": re.compile(r"MIKATA_LEDGER\s*=\s*\{[^}]*endpoint\s*:\s*['\"][^'\"]"),
}
TEXT_SUFFIXES = {".html", ".htm", ".js", ".json", ".md", ".txt", ".xml", ".css", ".svg"}


def stub_problem(data: bytes):
    """固定スタブと一致すれば None。不一致なら理由(値は含めない)。"""
    if hashlib.sha256(data).hexdigest() != EXPECTED_STUB_SHA256:
        return "固定スタブと一致しない"
    return None


def warnings_in(data: bytes) -> list:
    text = data.decode("utf-8", errors="replace")
    return [name for name, pat in WARN_PATTERNS.items() if pat.search(text)]


def check_tree(root: Path, quiet: bool = False) -> int:
    path = root / LEDGER_REL
    if not path.is_file():
        if not quiet:
            print(f"::error::C4: {LEDGER_REL} が公開物にない。公開を中止")
        return 1
    problem = stub_problem(path.read_bytes())
    if problem:
        if not quiet:
            print(f"::error::C4: {LEDGER_REL} が{problem}。公開を中止")
        return 1
    print(f"C4 OK: {LEDGER_REL} は固定スタブと一致")
    for file in sorted(root.rglob("*")):
        if not file.is_file() or file.suffix.lower() not in TEXT_SUFFIXES:
            continue
        hits = warnings_in(file.read_bytes())
        if hits:
            rel = file.relative_to(root).as_posix()
            print(f"::warning::C4: {rel} に確認が必要な表現: {', '.join(hits)}")
    return 0


def selftest() -> int:
    failures = []

    def expect(label, cond):
        if not cond:
            failures.append(label)

    tracked = (REPO_ROOT / "site" / LEDGER_REL).read_bytes()
    expect("追跡中のスタブが固定値と一致", stub_problem(tracked) is None)
    expect("末尾の改行が1つ増えると不一致", stub_problem(tracked + b"\n") is not None)
    expect("空のファイルは不一致", stub_problem(b"") is not None)
    # 注入の形(値は架空の文字列。実値ではない)
    injected = b'window.MIKATA_LEDGER={endpoint:"https://dummy.invalid/x",token:"DUMMY-NOT-A-SECRET"};\n'
    expect("ダミーの注入は不一致", stub_problem(injected) is not None)
    expect("ダミーの注入は警告で検出", set(warnings_in(injected)) == {"ledger_nonempty"})
    expect("Apps Script URL は警告で検出", "apps_script_url" in warnings_in(
        b"fetch('https://script.google.com/macros/s/DUMMY/exec')"))
    expect("追跡中のスタブは警告にならない", warnings_in(tracked) == [])
    expect("別の script.google.com パスは警告にならない", warnings_in(
        b"<a href='https://script.google.com/home'>x</a>") == [])
    expect("存在しない公開物は失敗", check_tree(Path("/nonexistent-ledger-check-root"), quiet=True) == 1)

    if failures:
        for f in failures:
            print(f"::error::selftest FAIL: {f}")
        return 1
    print("selftest OK")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="公開物の台帳設定が固定スタブと一致することを検査する(C4)")
    ap.add_argument("--root", help="検査する公開物のディレクトリ(例: /tmp/pages-deploy)")
    ap.add_argument("--selftest", action="store_true", help="自己テストを実行する")
    args = ap.parse_args(argv)
    if args.selftest:
        rc = selftest()
        if rc or not args.root:
            return rc
    if not args.root:
        ap.error("--root か --selftest のどちらかが必要")
    return check_tree(Path(args.root))


if __name__ == "__main__":
    sys.exit(main())
