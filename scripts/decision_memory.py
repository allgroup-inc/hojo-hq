#!/usr/bin/env python3
"""WikiSkill Phase 1 Task 3: Decision Memory(議事の機械可読化)。

議事(docs/議事_*.md と docs/議事/*.md)を読み、Decision(dict)の一覧にする。
- 新しい議事は先頭の frontmatter(`---` で囲んだ key: value)を優先して読む。
- 古い議事(frontmatter 無し)は見出し・行の形から推定する(遡及して書き換えない)。
- 読み取り専用。標準ライブラリのみ。どの議事を読んでも例外で止まらない。

使い方:
    python3 scripts/decision_memory.py --check <path...>   # frontmatter付きの議事だけ検査(違反があれば exit 1)
    python3 scripts/decision_memory.py --list [--json]     # 全議事の一覧
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

DECISION_GLOBS = ["docs/議事_*.md", "docs/議事/*.md"]
VALID_STATUS = ("adopted", "rejected", "deferred", "superseded")
REQUIRED_KEYS = ("decision_id", "date", "title", "status")
DEFAULT_REVIEW_DAYS = 180
SECTION_MAX = 600
HEAD_BODY_CHARS = 600

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*[:：]\s*(.*)$")
_FILENAME_DATE_RE = re.compile(r"_(\d{8})_|_(\d{4})-(\d{2})-(\d{2})")
_BODY_DATE_RE = re.compile(r"日付\s*[:：]\s*\**\s*(\d{4}-\d{2}-\d{2})")
_REVIEW_RE = re.compile(r"見直し期限[:：]?\s*\**\s*(\d{4}-\d{2}-\d{2})")
# ウタガイ(担当: ◯◯さん): 本文 / **ウタガイ(反対理由)**: 本文 / ウタガイ: 本文
_UTAGAI_RE = re.compile(r"ウタガイ(?:[(（][^)）]*[)）])?[*\s]*[:：]\s*(.*)$")
_WHY_PREFIXES = ("## なぜ", "## 背景", "## 目的")


# ---------------------------------------------------------------- 基本部品

def _collapse(text: str, limit: int | None = None) -> str:
    out = re.sub(r"\s+", " ", text).strip()
    return out[:limit] if limit else out


def _parse_date(value: str | None) -> dt.date | None:
    if not value or not _DATE_RE.match(value.strip()):
        return None
    try:
        return dt.date.fromisoformat(value.strip())
    except ValueError:
        return None


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _read(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return text.lstrip("﻿")


def _strip_comment(value: str) -> str:
    """` # ...` 形式の行末コメントを落とす(空白に続く # のみ)。"""
    return re.sub(r"\s+#.*$", "", value).strip()


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """先頭の `---` で囲まれた最小 YAML(key: value / tags: [a, b])を読む。

    返り値は (frontmatter の dict, frontmatter を除いた本文)。対応外の YAML
    (入れ子・リスト行・ブロック記法など)や閉じ忘れは「frontmatter 無し」として
    ({}, 元の本文全体)を返す。決して例外を出さない。
    """
    text = text.lstrip("﻿")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm: dict = {}
    for raw in lines[1:end]:
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _KEY_RE.match(line)  # 行頭から。インデント付きは対応外
        if not m:
            return {}, text
        key, value = m.group(1), _strip_comment(m.group(2))
        if value[:1] in ("|", ">", "{", "&", "*", "!") or value.startswith("- "):
            return {}, text
        if value.startswith("["):
            if not value.endswith("]"):
                return {}, text
            inner = value[1:-1]
            fm[key] = [_unquote(t.strip()) for t in re.split(r"[,、]", inner) if t.strip()]
        elif key == "tags":
            fm[key] = [_unquote(t.strip()) for t in re.split(r"[,、]", value) if t.strip()]
        else:
            fm[key] = _unquote(value)
    if not fm:
        return {}, text
    body = "\n".join(lines[end + 1:])
    return fm, body


def _section(lines: list[str], prefixes: tuple[str, ...]) -> str:
    """見出し(## …)が prefixes のどれかで始まる最初の節の本文。次の `## ` まで。"""
    for prefix in prefixes:
        for i, line in enumerate(lines):
            if line.startswith(prefix):
                chunk = []
                for nxt in lines[i + 1:]:
                    if nxt.startswith("## "):
                        break
                    chunk.append(nxt)
                return _collapse(" ".join(chunk), SECTION_MAX)
    return ""


def _utagai_inline(line: str) -> str | None:
    m = _UTAGAI_RE.search(line)
    return m.group(1).strip() if m else None


def _utagai_continuation(lines: list[str], i: int) -> str:
    """ウタガイ行のコロン後が空のとき、続く行(字下げ項目、または見出しの下の本文)を拾う。"""
    heading = lines[i].lstrip().startswith("#")
    chunk = []
    for nxt in lines[i + 1:]:
        if not nxt.strip():
            continue
        if heading:
            if nxt.lstrip().startswith("#"):
                break
        elif not nxt[0].isspace():
            break
        chunk.append(nxt.strip())
    return _collapse(" ".join(chunk), SECTION_MAX)


def _utagai_all(lines: list[str]) -> list[tuple[int, str]]:
    """ウタガイを含む行ごとの (行番号, 反対理由の本文)。本文が無ければ空文字。"""
    found = []
    for i, line in enumerate(lines):
        if "ウタガイ" not in line:
            continue
        inline = _utagai_inline(line)
        if inline is None:
            if line.lstrip().startswith("#"):
                found.append((i, _utagai_continuation(lines, i)))
            else:
                found.append((i, ""))
        elif inline:
            found.append((i, _collapse(inline, SECTION_MAX)))
        else:
            found.append((i, _utagai_continuation(lines, i)))
    return found


def _utagai_text(lines: list[str]) -> str:
    """反対理由の本文。本文を持つ最初のウタガイ行の内容。無ければ空文字。"""
    for _i, text in _utagai_all(lines):
        if text:
            return text
    return ""


def _bekkai_text(lines: list[str]) -> str:
    return _collapse(" ".join(l for l in lines if "ベッカイ" in l), SECTION_MAX)


def _title(fm: dict, lines: list[str], path: Path) -> str:
    if fm.get("title"):
        return fm["title"]
    for line in lines:
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


# ---------------------------------------------------------------- 読み取り

def parse_decision(path: Path, root: Path, today: dt.date | None = None) -> dict:
    """議事1件を Decision(dict)にする。frontmatter 優先、無ければ本文から推定。"""
    today = today or dt.date.today()
    text = _read(path)
    fm, body = parse_frontmatter(text)
    legacy = not fm
    lines = body.split("\n")

    date = _parse_date(fm.get("date")) if not legacy else None
    if date is None:
        m = _FILENAME_DATE_RE.search(path.name)
        if m:
            try:
                if m.group(1):
                    s = m.group(1)
                    date = dt.date(int(s[:4]), int(s[4:6]), int(s[6:]))
                else:
                    date = dt.date(int(m.group(2)), int(m.group(3)), int(m.group(4)))
            except ValueError:
                date = None
    if date is None:
        m = _BODY_DATE_RE.search(body)
        if m:
            date = _parse_date(m.group(1))

    review = _parse_date(fm.get("review_by")) if not legacy else None
    if review is None:
        m = _REVIEW_RE.search(body)
        if m:
            review = _parse_date(m.group(1))
    if review is None and date is not None:
        review = date + dt.timedelta(days=DEFAULT_REVIEW_DAYS)

    if review is None:
        review_status = "unknown"
    else:
        review_status = "active" if review >= today else "expired"

    status = fm.get("status", "")
    if status not in VALID_STATUS:
        status = "unknown"

    tags = fm.get("tags", [])
    if not isinstance(tags, list):
        tags = [tags] if tags else []
    title = _title(fm, lines, path)
    head = " ".join([title, " ".join(tags), body[:HEAD_BODY_CHARS]])

    return {
        "id": fm.get("decision_id") or f"legacy:{path.stem}",
        "path": _rel(path, root),
        "title": title,
        "date": date.isoformat() if date else None,
        "review_by": review.isoformat() if review else None,
        "review_status": review_status,
        "status": status,
        "scope": fm.get("scope", ""),
        "tags": tags,
        "why": _section(lines, _WHY_PREFIXES),
        "premises": _section(lines, ("## 前提",)),
        "alternatives": _section(lines, ("## 代替案",)),
        "utagai": _utagai_text(lines),
        "bekkai": _bekkai_text(lines),
        "outcome": _section(lines, ("## 裁定", "## 結論", "## 決定")),
        "legacy": legacy,
        "text_head": _collapse(head),
    }


def load_decisions(root: Path, today: dt.date | None = None) -> list[dict]:
    """DECISION_GLOBS に合う議事をすべて読む(パス順・重複なし)。"""
    seen: dict[str, Path] = {}
    for pattern in DECISION_GLOBS:
        for p in sorted(Path(root).glob(pattern)):
            if p.is_file():
                seen.setdefault(str(p), p)
    return [parse_decision(p, Path(root), today) for p in seen.values()]


# ---------------------------------------------------------------- 検査

def check_decision(path: Path, root: Path) -> list[str]:
    """frontmatter 付きの議事の書式違反を日本語で返す。frontmatter 無し(過去分)は検査しない。"""
    fm, body = parse_frontmatter(_read(path))
    if not fm:
        return []
    name = _rel(path, root)
    errs: list[str] = []

    for key in REQUIRED_KEYS:
        if not fm.get(key):
            errs.append(f"{name}: frontmatter に必須キー {key} がありません(必須: {'/'.join(REQUIRED_KEYS)})")

    status = fm.get("status")
    if status and status not in VALID_STATUS:
        errs.append(f"{name}: status が許容値ではありません: {status}(許容: {' | '.join(VALID_STATUS)})")

    date = _parse_date(fm.get("date"))
    if fm.get("date") and date is None:
        errs.append(f"{name}: date が YYYY-MM-DD の日付ではありません: {fm['date']}")
    if fm.get("review_by"):
        review = _parse_date(fm["review_by"])
        if review is None:
            errs.append(f"{name}: review_by が YYYY-MM-DD の日付ではありません: {fm['review_by']}")
        elif date is not None and review <= date:
            errs.append(f"{name}: review_by({fm['review_by']})は date({fm['date']})より後の日付にしてください")

    lines = body.split("\n")
    entries = _utagai_all(lines)
    if not entries:
        errs.append(f"{name}: ウタガイ(反対理由)の行がありません。ウタガイの反対理由は必須記録です")
    elif not any(text for _i, text in entries):
        errs.append(f"{name}: ウタガイの反対理由が空です。コロンの後(または直下の字下げ項目)に反対理由を書いてください")

    if not any(re.match(r"##\s*(なぜ|背景)", l) for l in lines):
        errs.append(f"{name}: 見出し `## なぜ` または `## 背景` がありません")
    return errs


# ---------------------------------------------------------------- CLI

def _default_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="議事(Decision)の機械可読化")
    ap.add_argument("--check", nargs="+", metavar="PATH", help="frontmatter付き議事を検査(違反があれば exit 1)")
    ap.add_argument("--list", action="store_true", help="全議事を一覧表示")
    ap.add_argument("--json", action="store_true", help="--list をJSON配列で出力")
    ap.add_argument("--root", default=None, help="リポジトリルート(既定: このスクリプトの親の親)")
    args = ap.parse_args(argv)
    root = Path(args.root) if args.root else _default_root()

    if args.check:
        errors: list[str] = []
        for p in args.check:
            errors.extend(check_decision(Path(p), root))
        for e in errors:
            print(e)
        return 1 if errors else 0

    if args.list:
        decisions = load_decisions(root)
        if args.json:
            print(json.dumps(decisions, ensure_ascii=False, indent=2))
        else:
            for d in decisions:
                print(f"{d['date'] or '-'}  {d['review_status']}  {d['status']}  {d['title']}  {d['path']}")
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
