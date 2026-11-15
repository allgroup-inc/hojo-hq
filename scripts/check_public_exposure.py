#!/usr/bin/env python3
"""hojo-hq(公開リポジトリ)に、個人の連絡先・内部の入口URL・認証情報の形をした文字列が無いか検査する。

背景: 2026-10-28〜29 の GLOW 全体統括の調査で、公開の docs/ に管理画面の入口URL・台帳への直接リンク・
      スタッフ個人のメールアドレスが載っていることが分かった(P1 安全対策)。最新のファイルから消しても
      過去の版には残るため、まず「これ以上増やさない」ために機械で見張る。
      議事: docs/議事/議事_20261029_公開情報検査_警告モード追加.md

方針:
- 一致した値そのものは決して出力しない。出すのは規則の番号・名前・ファイル名・行番号だけ
  (公開リポジトリの Actions のログは誰でも読めるため)。
- 既存の一致(BASELINE に記録した件数まで)と、新しく増えた一致を分けて報告する。BASELINE には
  値を書かず、ファイルごと・規則ごとの件数だけを書く。
- 検査しなかったファイル(画像・PDF等・大きすぎる・文字コード不明・対象外の場所)は「未検査」として
  件数を必ず報告する。未検査は「問題なし」ではない。
- 架空の値として通すのは、形で明らかに架空と分かるものだけ(同じ数字の繰り返し等)。「example」等の
  語を含むかどうかでは判断しない(実在の値を見逃すため。2026-10-29 の試算で実測)。

使い方:
    python3 scripts/check_public_exposure.py                  # 警告モード(新規があっても exit 0)
    python3 scripts/check_public_exposure.py --strict         # 新規があれば exit 1
    python3 scripts/check_public_exposure.py --selftest       # 検査ロジック自体の自己点検
    python3 scripts/check_public_exposure.py --write-baseline # 今の件数を BASELINE に記録する

終了コード: 0=検査できた(警告モード) / 1=新規あり(--strict のみ) / 2=検査そのものが成り立たない
(検査したファイルが0件・BASELINE が壊れている・git が使えない)。

規則を緩める・BASELINE を書き直す・警告モードから止めるモードへ切り替えるのは、ルールの変更にあたるため議事が要る。
"""

import json
import os
import re
import subprocess
import sys

BASELINE_PATH = "scripts/public_exposure_baseline.json"
MAX_BYTES = 2_000_000

# 検査しない場所(理由つき)。ここに入れたものは「安全」ではなく「未検査」として数える。
SKIP_PREFIXES = {
    "data/": "公的機関の窓口番号などが多く、誤検知と区別できないため(別途の点検対象)",
    ".claude/experience/": "専用の検査 scripts/check_experience_privacy.py が担当",
}
BINARY_SUFFIXES = (
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svgz", ".mp3", ".mp4", ".m4a",
    ".mov", ".wav", ".zip", ".gz", ".xlsx", ".xls", ".docx", ".pptx", ".woff", ".woff2", ".ttf", ".otf",
)

_FREE_MAIL_DOMAINS = (
    r"gmail\.com|googlemail\.com|yahoo\.co\.jp|ymail\.ne\.jp|icloud\.com|me\.com|mac\.com"
    r"|outlook\.(?:jp|com)|hotmail\.(?:com|co\.jp)|live\.jp"
    r"|docomo\.ne\.jp|ezweb\.ne\.jp|au\.com|softbank\.ne\.jp|i\.softbank\.jp"
)
_ROLE_LOCAL_PARTS = r"info|contact|support|noreply|no-reply"


def _same_or_counting(group):
    return len(set(group)) == 1 or group in ("1234", "5678")


def _dummy_phone(value):
    """090-1111-2222 / 090-1234-5678 のように、4桁ずつが同じ数字の繰り返しか 1234・5678 なら架空とみなす。"""
    digits = re.sub(r"\D", "", value)[3:]
    return len(digits) == 8 and _same_or_counting(digits[:4]) and _same_or_counting(digits[4:])


def _dummy_line_id(value):
    """U のあとの32桁が2種類以下の文字だけ、または 0123456789abcdef の繰り返しなら架空とみなす。"""
    body = value[1:]
    return len(set(body)) <= 2 or body == "0123456789abcdef" * 2


# (番号, 名前, 正規表現, 架空と判定する関数 or None)
RULES = [
    ("R1", "Apps Script の Web アプリURL(識別子つき)",
     re.compile(r"script\.google\.com/macros/s/[A-Za-z0-9_-]{20,}"), None),
    ("R2", "Google のスプレッドシート・文書・ドライブへの直接リンク(識別子つき)",
     re.compile(r"(?:docs\.google\.com/(?:spreadsheets|document|forms|presentation)/d/"
                r"|drive\.google\.com/(?:file/d|drive/folders)/)[A-Za-z0-9_-]{20,}"), None),
    ("R3", "個人向けメールサービスのアドレス",
     re.compile(r"[A-Za-z0-9._%+-]+@(?:" + _FREE_MAIL_DOMAINS + r")(?![A-Za-z0-9.-])", re.I), None),
    ("R4", "会社ドメインの個人名アドレス(窓口用を除く)",
     re.compile(r"(?<![A-Za-z0-9._%+-])(?!(?:" + _ROLE_LOCAL_PARTS + r")@)[A-Za-z0-9._%+-]+@g-low\.co\.jp"
                r"(?![A-Za-z0-9.-])", re.I), None),
    ("R5", "携帯電話番号",
     re.compile(r"(?<![0-9])0[789]0-?[0-9]{4}-?[0-9]{4}(?![0-9])"), _dummy_phone),
    ("R6", "LINE の利用者ID",
     re.compile(r"(?<![A-Za-z0-9])U[0-9a-f]{32}(?![A-Za-z0-9])"), _dummy_line_id),
    ("R7", "API キー・トークンの接頭辞",
     re.compile(r"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}"
                r"|github_pat_[A-Za-z0-9_]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}"
                r"|AIza[0-9A-Za-z_-]{30,})"), None),
    ("R8", "秘密鍵", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), None),
    ("R9", "URL に埋め込まれた資格情報", re.compile(r"https?://[^\s/@:]+:[^\s/@]+@"), None),
    ("R10", "Bearer トークン", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}"), None),
    ("R11", "Slack の通知用URL", re.compile(r"hooks\.slack\.com/services/[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+"), None),
]
RULE_NAMES = {rid: name for rid, name, _, _ in RULES}


def scan_text(text):
    """本文を検査して [(規則番号, 行番号)] を返す。値は返さない。"""
    found = []
    line_starts = [0] + [i + 1 for i, ch in enumerate(text) if ch == "\n"]

    def line_of(pos):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    for rid, _name, pattern, is_dummy in RULES:
        for m in pattern.finditer(text):
            if is_dummy and is_dummy(m.group(0)):
                continue
            found.append((rid, line_of(m.start())))
    return found


def classify_path(path):
    """検査しない理由を返す。検査するなら None。"""
    for prefix, reason in SKIP_PREFIXES.items():
        if path.startswith(prefix):
            return f"対象外の場所({prefix}): {reason}"
    if path.lower().endswith(BINARY_SUFFIXES):
        return "画像・PDF・表計算などのファイル(中身を文字として読めない)"
    return None


def read_text(path):
    """(本文, 未検査の理由) を返す。読めたら理由は None。"""
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None, f"大きすぎるファイル({MAX_BYTES:,}バイト超)"
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None, "読み取れないファイル(リンク切れ・権限など)"
    if b"\0" in data[:8192]:
        return None, "文字のファイルではない(バイナリ)"
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, "UTF-8 として読めないファイル"


def scan_paths(paths):
    """{path: {規則: [行番号...]}} と {未検査の理由: 件数} と 検査したファイル数 を返す。"""
    findings, skipped, scanned = {}, {}, 0
    for path in paths:
        reason = classify_path(path)
        text = None
        if reason is None:
            text, reason = read_text(path)
        if reason is not None:
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        scanned += 1
        for rid, line in scan_text(text):
            findings.setdefault(path, {}).setdefault(rid, []).append(line)
    return findings, skipped, scanned


def compare_with_baseline(findings, baseline_counts):
    """新規(件数が BASELINE を超えた分)と既存・減少を分ける。"""
    new, existing, decreased = [], [], []
    for path in sorted(findings):
        for rid in sorted(findings[path], key=lambda r: int(r[1:])):
            lines = findings[path][rid]
            allowed = baseline_counts.get(path, {}).get(rid, 0)
            if len(lines) > allowed:
                new.append((path, rid, len(lines) - allowed, lines))
            else:
                existing.append((path, rid, len(lines)))
    for path in sorted(baseline_counts):
        for rid, allowed in sorted(baseline_counts[path].items()):
            current = len(findings.get(path, {}).get(rid, []))
            if current < allowed:
                decreased.append((path, rid, allowed - current))
    return new, existing, decreased


def load_baseline(path=BASELINE_PATH):
    """BASELINE の件数表を返す。無ければ None(全部を新規として扱う)。壊れていれば ValueError。"""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    counts = data.get("counts")
    if data.get("schema") != 1 or not isinstance(counts, dict):
        raise ValueError("BASELINE の形式が想定と違います")
    for file_counts in counts.values():
        if not isinstance(file_counts, dict) or not all(
                rid in RULE_NAMES and isinstance(n, int) and n >= 0 for rid, n in file_counts.items()):
            raise ValueError("BASELINE に知らない規則番号か不正な件数があります")
    return counts


def baseline_document(findings, commit):
    counts = {path: {rid: len(lines) for rid, lines in sorted(rules.items())}
              for path, rules in sorted(findings.items())}
    return {
        "schema": 1,
        "note": "既存の一致の件数だけを記録する(値は書かない)。件数を増やす書き直しは議事が要る。",
        "recorded_from": commit,
        "counts": counts,
    }


def tracked_files():
    out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "-z"],
                         capture_output=True, text=True, check=True).stdout
    return [p for p in out.split("\0") if p]


def _annotation_escape(value):
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C")


def report(new, existing, decreased, skipped, scanned, baseline_missing, strict, out=sys.stdout):
    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    lines = []
    lines.append(f"検査したファイル: {scanned}件(値は表示しません。規則の番号・ファイル名・行番号のみ)")
    if baseline_missing:
        lines.append(f"注意: {BASELINE_PATH} が無いため、すべての一致を新規として扱います")
    lines.append(f"新規の一致: {sum(n for _, _, n, _ in new)}件 / 既存の一致: {sum(n for _, _, n in existing)}件"
                 f" / 減った一致: {sum(n for _, _, n in decreased)}件")
    if new:
        lines.append("\n[新規] BASELINE より増えた一致(行は候補。どの行が新しいかは件数でしか判定していない):")
        for path, rid, extra, line_nos in new:
            lines.append(f"  {rid} {RULE_NAMES[rid]}: {path} +{extra}件(行 {', '.join(map(str, line_nos))})")
            if in_actions:
                level = "error" if strict else "warning"
                print(f"::{level} file={_annotation_escape(path)},line={line_nos[0]}::"
                      f"公開情報検査 {rid} {RULE_NAMES[rid]} が {extra} 件増えています(値は表示しません)", file=out)
    if existing:
        by_rule = {}
        for path, rid, n in existing:
            by_rule.setdefault(rid, [0, 0])
            by_rule[rid][0] += n
            by_rule[rid][1] += 1
        lines.append("\n[既存] BASELINE に記録済みの一致(過去の版にも残っている。消しても安全になったとは扱わない):")
        for rid in sorted(by_rule, key=lambda r: int(r[1:])):
            total, files = by_rule[rid]
            lines.append(f"  {rid} {RULE_NAMES[rid]}: {total}件 / {files}ファイル")
    if decreased:
        lines.append("\n[減少] BASELINE より減った一致(BASELINE を書き直すと、減った分が再び増えたときに検知できる):")
        for path, rid, n in decreased:
            lines.append(f"  {rid}: {path} -{n}件")
    lines.append("\n[未検査] 次のファイルは中身を見ていません(安全とは判断していません):")
    if skipped:
        for reason, n in sorted(skipped.items()):
            lines.append(f"  {n}件: {reason}")
    else:
        lines.append("  なし")
    text = "\n".join(lines)
    print(text, file=out)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("## 公開情報検査(警告モード)\n\n```\n" + text + "\n```\n")


def selftest():
    """検査ロジックが効いていること・誤検知しないこと・値を出さないことを確かめる。
    合成の値は実行中に組み立てる(このファイル自体に完成した値を書かないため)。"""
    at = "@"
    ex_free = "taro.synthetic" + at + "gmail.com"
    ex_named = "hanako.synthetic" + at + "g-low.co.jp"
    ex_role = "info" + at + "g-low.co.jp"
    ex_phone = "090-" + "8642" + "-" + "9753"
    ex_dummy_phone = "090-" + "1111" + "-" + "2222"
    ex_dummy_phone2 = "080" + "1234" + "5678"
    ex_line = "U" + "9f3a" * 8
    ex_dummy_line = "U" + "0123456789abcdef" * 2
    ex_key = "gh" + "p_" + "Z" * 24
    ex_url = "https://script.google.com/macros/s/" + "AKfy" + "x" * 30 + "/exec"
    ex_sheet = "https://docs.google.com/spreadsheets/d/" + "1A" + "b" * 30 + "/edit"
    ex_slack = "https://hooks.slack.com/services/" + "T0/B0/" + "z" * 20
    ex_bearer = "Bear" + "er " + "q" * 24
    ex_pem = "-----BEGIN " + "RSA PRIVATE KEY-----"
    ex_urlcred = "https://user:" + "pw" + at + "example.org/"
    cases = [
        (ex_free, {"R3"}), (ex_named, {"R4"}), (ex_role, set()),
        (ex_phone, {"R5"}), (ex_dummy_phone, set()), (ex_dummy_phone2, set()),
        (ex_line, {"R6"}), (ex_dummy_line, set()), (ex_key, {"R7"}),
        (ex_url, {"R1"}), (ex_sheet, {"R2"}), (ex_slack, {"R11"}),
        (ex_bearer, {"R10"}), (ex_pem, {"R8"}), (ex_urlcred, {"R9"}),
        # 誤検知してはいけないもの
        ("法人番号 4" + "090" + "86429753" + "1 の会社", set()),        # 13桁の数字の一部
        ("https://script.google.com/home と <ID> の置き場所", set()),     # 識別子の無いURL
        ("max-width:100%; 締切の約1か月前から", set()),                     # FK-001 の型
        ("連絡は " + ex_role + " へ(窓口用)", set()),
        ("沖縄県の企業、補助金・助成金の情報", set()),                       # 日本語の本文(2026-09-25 の型)
    ]
    failed = []
    for text, expected in cases:
        got = {rid for rid, _ in scan_text(text)}
        if got != expected:
            failed.append(f"  ケース{cases.index((text, expected)) + 1}: 期待={sorted(expected)} 実際={sorted(got)}")

    # 新規と既存の区別
    findings = {"docs/a.md": {"R3": [3, 9]}, "docs/b.md": {"R1": [1]}}
    new, existing, decreased = compare_with_baseline(findings, {"docs/a.md": {"R3": 2}, "docs/c.md": {"R5": 1}})
    if [(p, r, n) for p, r, n, _ in new] != [("docs/b.md", "R1", 1)]:
        failed.append("  新規の判定が想定と違う")
    if existing != [("docs/a.md", "R3", 2)] or decreased != [("docs/c.md", "R5", 1)]:
        failed.append("  既存・減少の判定が想定と違う")

    # 未検査の分類
    if classify_path("site/go/world/glow-guide.pdf") is None or classify_path("data/x.json") is None:
        failed.append("  未検査の分類が効いていない")
    if classify_path("docs/a.md") is not None:
        failed.append("  文書が未検査に分類された")

    # 出力に値が出ないこと
    import io
    buf = io.StringIO()
    report([("docs/a.md", "R3", 1, [3])], [("docs/b.md", "R5", 1)], [], {"理由": 1}, 2, False, False, out=buf)
    if any(v in buf.getvalue() for v in (ex_free, ex_phone, ex_line, ex_key)):
        failed.append("  出力に値が含まれている")

    if failed:
        print("自己点検に失敗しました:", file=sys.stderr)
        print("\n".join(failed), file=sys.stderr)
        return 1
    print(f"自己点検OK({len(cases)}件+区別・分類・出力の確認)")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        return selftest()
    strict = "--strict" in argv
    try:
        paths = tracked_files()
    except (OSError, subprocess.CalledProcessError):
        print("検査できません: git の管理下で実行してください", file=sys.stderr)
        return 2
    findings, skipped, scanned = scan_paths(paths)
    if scanned == 0:
        print("検査できません: 検査したファイルが0件です(空回りを防ぐため失敗にします)", file=sys.stderr)
        return 2

    if "--write-baseline" in argv:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        os.makedirs(os.path.dirname(BASELINE_PATH), exist_ok=True)
        with open(BASELINE_PATH, "w", encoding="utf-8") as f:
            json.dump(baseline_document(findings, commit), f, ensure_ascii=False, indent=2)
            f.write("\n")
        total = sum(len(v) for rules in findings.values() for v in rules.values())
        print(f"BASELINE を書きました: {BASELINE_PATH}({len(findings)}ファイル・{total}件。値は書いていません)")
        return 0

    try:
        baseline = load_baseline()
    except (OSError, ValueError) as error:
        print(f"検査できません: BASELINE を読めません({error})", file=sys.stderr)
        return 2
    new, existing, decreased = compare_with_baseline(findings, baseline or {})
    report(new, existing, decreased, skipped, scanned, baseline is None, strict)
    if strict and new:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
