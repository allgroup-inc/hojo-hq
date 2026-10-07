#!/usr/bin/env python3
"""WikiSkill Phase 2: Knowledge Wiki の共通 schema(stdlib のみ)。

候補(docs/wiki/_candidates/)・正式 Wiki(docs/wiki/ 直下)・置き換え済み(docs/wiki/_archive/)の
frontmatter の読み書き、ID・dedup_key の生成、normalize、同義語表、タイトル類似度、公開性の判定。
検証(V01〜V15)は wiki_validate.py が行う。ここは「形」だけを持つ。

frontmatter の書式(設計書 6.1):
    1行1キー。値はスカラーか1行の JSON(配列・オブジェクト・文字列)。
    `[` `{` `"` で始まる値は json.loads、数字だけの値は float、それ以外は文字列。
    読めないものは WikiFormatError(黙って空扱いにしない)。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import experience_log  # noqa: E402
from wikiskill_common import audit  # noqa: E402

# ---------------------------------------------------------------- 置き場所

WIKI_DIR = "docs/wiki"
CANDIDATES_DIR = "docs/wiki/_candidates"
ARCHIVE_DIR = "docs/wiki/_archive"
SYNONYMS_PATH = "docs/wiki/_synonyms.txt"
WIKI_OFF = ".claude/wiki.off"

PLACES = {"official": WIKI_DIR, "candidates": CANDIDATES_DIR, "archive": ARCHIVE_DIR}

# ---------------------------------------------------------------- キー・本文

REQUIRED_KEYS = ("candidate_id", "title", "summary", "evidence", "confidence", "confidence_basis", "visibility",
                 "repo", "created_at", "proposed_by", "contradictions", "related_wiki", "related_skills",
                 "review_status", "dedup_key", "extract_run")
APPROVED_KEYS = ("wiki_id", "approved_by", "approved_at", "review_by", "review")
SOURCE_KEYS = ("source_experience", "source_decision", "source_failure")
# 上の3組以外に書いてよいキー(設計書 6.2)。ここに無いキーは schema 違反(needs_review は派生状態なので書かない)
OPTIONAL_KEYS = ("duplicate_of", "acknowledged_decisions", "rejected_reason", "supersedes", "superseded_by")
KNOWN_KEYS = frozenset(REQUIRED_KEYS + APPROVED_KEYS + SOURCE_KEYS + OPTIONAL_KEYS)

BODY_SECTIONS = ("## 知識", "## 根拠(Provenance)", "## 反証(ウタガイ)", "## 適用範囲と例外", "## 関連")

STATUS_BY_PLACE = {"candidates": {"candidate", "conflict", "rejected"}, "official": {"approved"},
                   "archive": {"superseded"}}
ALL_STATUSES = frozenset().union(*STATUS_BY_PLACE.values())
VISIBILITIES = ("public", "private")
REVIEW_ROLES = ("スイシン", "ウタガイ", "ベッカイ")

# ---------------------------------------------------------------- 上限・しきい値

MAX_TITLE = 80
MAX_SUMMARY = 200
MAX_QUOTE = 200
MIN_QUOTE = 8  # これより短い引用は「どこにでもある語」で根拠にならない
MAX_REVIEW_DAYS = 183  # 見直し期限は承認から6か月以内(CLAUDE.md 三名体制 規則7)
MAX_EVIDENCE = 10
MAX_BODY = 4000
MAX_KNOWLEDGE = 1500
SHOWN_SUMMARY = 160
DEFAULT_REVIEW_DAYS = 180
DUPLICATE_RATIO = 0.6
CONFLICT_MIN_UNITS = 2

# 同義語表(設計書 V14): 各語 2〜30字・1グループ 8語以内・全体 200行以内
SYN_WORD_MIN = 2
SYN_WORD_MAX = 30
SYN_GROUP_MAX = 8
SYN_LINES_MAX = 200

NEGATION_WORDS = ("禁止", "しない", "却下", "やめる", "不可")
BOT_APPROVERS = frozenset({"claude", "hojo-hq-bot", "github-actions", "github-actions[bot]", "knowledge_extract",
                           "rule-based"})
EMPTY_WORDS = frozenset({"", "-", "なし", "無し", "tbd", "todo", "未記入"})

CANDIDATE_ID_RE = re.compile(r"^K\d{8}-[a-z0-9][a-z0-9-]{0,39}-[0-9a-f]{4,6}$")
WIKI_ID_RE = re.compile(r"^W\d{8}-[a-z0-9][a-z0-9-]{0,39}$")
EXP_SOURCE_RE = re.compile(r"^session-([A-Za-z0-9._-]+)@(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)$")
FK_RE = re.compile(r"^FK-\d{3}$")

_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*):(.*)$")  # `_` 始まりは内部キー(_path 等)なので書かせない
_NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
_SLUG_MAX = 40

Wiki = dict  # frontmatter の全キー + _path / _place / _body / _sections / _section_order / _preamble / _text


class WikiFormatError(ValueError):
    """frontmatter・本文・置き場所を読めない(schema 違反として扱う)。"""


# ---------------------------------------------------------------- frontmatter

def _parse_value(raw: str):
    v = raw.strip()
    if v[:1] in ("[", "{", '"'):
        try:
            return json.loads(v)
        except ValueError as e:
            raise WikiFormatError(f"JSON として読めない値: {e}") from e
    if _NUMBER_RE.match(v):
        return float(v)
    return v


def parse_wiki_frontmatter(text: str) -> tuple[dict, str]:
    """先頭の `---` 〜 `---` を読む。返り値は (frontmatter, 本文)。読めなければ WikiFormatError。"""
    if not isinstance(text, str):
        raise WikiFormatError("本文が文字列ではない")
    lines = text.lstrip("﻿").split("\n")
    if not lines or lines[0].rstrip("\r").strip() != "---":
        raise WikiFormatError("先頭行が --- ではない(frontmatter が無い)")
    end = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r").strip() == "---":
            end = i
            break
    if end is None:
        raise WikiFormatError("frontmatter の閉じ --- が無い")
    fm: dict = {}
    for n, raw in enumerate(lines[1:end], start=2):
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        m = _KEY_RE.match(line)
        if not m:
            raise WikiFormatError(f"{n}行目が `key: value` の形ではない")
        key = m.group(1)
        if key in fm:
            raise WikiFormatError(f"キー {key} が2回ある")
        fm[key] = _parse_value(m.group(2))
    body = "\n".join(l.rstrip("\r") for l in lines[end + 1:]).lstrip("\n")
    return fm, body


def _needs_quote(s: str) -> bool:
    return (s == "" or s != s.strip() or s[:1] in ("[", "{", '"') or bool(_NUMBER_RE.match(s))
            or "\n" in s or "\r" in s)


def _render_value(key: str, value) -> str:
    if isinstance(value, bool) or value is None:
        raise WikiFormatError(f"{key}: 真偽値・null はスカラーに書けない")
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return repr(float(value)) if isinstance(value, float) else str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False) if _needs_quote(value) else value
    raise WikiFormatError(f"{key}: 書けない型 {type(value).__name__}")


def render_wiki(fm: dict, sections: dict[str, str]) -> str:
    """frontmatter(REQUIRED_KEYS → SOURCE_KEYS → 任意キー)+ 本文(BODY_SECTIONS の順 → その他)。"""
    keys = [k for k in REQUIRED_KEYS if k in fm] + [k for k in SOURCE_KEYS if k in fm]
    keys += [k for k in fm if k not in keys and not str(k).startswith("_")]
    out = ["---"]
    for k in keys:
        if not _KEY_RE.match(f"{k}:"):
            raise WikiFormatError(f"キー名として書けない: {k!r}")
        out.append(f"{k}: {_render_value(k, fm[k])}")
    out.append("---")
    heads = [h for h in BODY_SECTIONS if h in sections] + [h for h in sections if h not in BODY_SECTIONS]
    for h in heads:
        out.append("")
        out.append(h)
        content = str(sections[h]).strip("\n")
        if content:
            out.append(content)
    return "\n".join(out) + "\n"


def split_sections(body: str) -> tuple[str, dict[str, str], list[str]]:
    """本文を `## ` 見出しで分ける。返り値は (最初の見出しより前, {見出し: 本文}, 見出しの出現順)。"""
    pre: list[str] = []
    sections: dict[str, list[str]] = {}
    order: list[str] = []
    current = None
    for line in body.split("\n"):
        if line.startswith("## "):
            current = line.rstrip()
            order.append(current)
            sections.setdefault(current, [])
            continue
        (pre if current is None else sections[current]).append(line)
    return "\n".join(pre).strip(), {k: "\n".join(v).strip() for k, v in sections.items()}, order


# ---------------------------------------------------------------- ファイル

def _place_of(path: Path, root: Path) -> str:
    rel = path.resolve().parent.relative_to(Path(root).resolve()).as_posix()
    for place, d in PLACES.items():
        if rel == d:
            return place
    raise WikiFormatError(f"Wiki の置き場所ではない: {rel}")


def _rel(path: Path, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


def load_wiki_file(path: Path, root: Path) -> Wiki:
    """1ファイルを Wiki(dict)にする。読めなければ WikiFormatError / OSError。"""
    path = Path(path)
    if path.is_symlink():
        raise WikiFormatError("シンボリックリンクは置けない")
    text = path.read_text(encoding="utf-8")
    fm, body = parse_wiki_frontmatter(text)
    pre, sections, order = split_sections(body)
    w: Wiki = dict(fm)
    w.update({"_path": _rel(path, root), "_place": _place_of(path, root), "_body": body, "_sections": sections,
              "_section_order": order, "_preamble": pre, "_text": text})
    return w


def iter_wiki(root: Path, place: str) -> list[Wiki]:
    """official = docs/wiki/*.md(直下・`_` 始まりを除く)、candidates / archive = 各ディレクトリ直下の *.md。

    読めないファイルは {"_path", "_place", "_error"} として返す(飛ばさない)。
    """
    if place not in PLACES:
        raise ValueError(f"unknown place: {place}")
    d = Path(root) / PLACES[place]
    if not d.is_dir():
        return []
    out: list[Wiki] = []
    for p in sorted(d.glob("*.md")):
        if place == "official" and p.name.startswith("_"):
            continue
        if not (p.is_file() or p.is_symlink()):
            continue
        try:
            out.append(load_wiki_file(p, root))
        except (OSError, UnicodeDecodeError, ValueError) as e:
            out.append({"_path": _rel(p, root), "_place": place, "_error": f"{type(e).__name__}: {e}"})
    return out


# ---------------------------------------------------------------- 正規化・ID

def normalize(text: str) -> str:
    """NFKC → 小文字 → 文字(L*)と数字(N*)以外(空白・記号・制御文字)を除去。"""
    s = unicodedata.normalize("NFKC", str(text)).lower()
    return "".join(ch for ch in s if unicodedata.category(ch)[0] in ("L", "N"))


def slugify(text: str, fallback: str) -> str:
    """ASCII の英小文字・数字とハイフンだけ、40字まで。空なら fallback(同じ規則で整える)。"""
    def clean(s: str) -> str:
        s = unicodedata.normalize("NFKC", str(s)).lower()
        s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
        return s[:_SLUG_MAX].strip("-")
    return clean(text) or clean(fallback) or "x"


def dedup_key(title: str, source_ids: list[str]) -> str:
    return hashlib.sha1((normalize(title) + "|" + ",".join(sorted(source_ids))).encode("utf-8")).hexdigest()


def make_candidate_id(day: date, slug: str, key: str, taken: set[str]) -> str:
    """K{YYYYMMDD}-{slug}-{key[:4]}。衝突したら key[:5]、key[:6]。それでも衝突なら ValueError。"""
    slug = slugify(slug, "k")
    for n in (4, 5, 6):
        cid = f"K{day:%Y%m%d}-{slug}-{key[:n]}"
        if cid not in taken:
            return cid
    raise ValueError(f"candidate_id が衝突する: K{day:%Y%m%d}-{slug}-{key[:6]}")


def all_source_ids(w: Wiki) -> list[str]:
    """source_experience → source_decision → source_failure の順の id(リスト以外・文字列以外は無視)。"""
    out: list[str] = []
    for k in SOURCE_KEYS:
        v = w.get(k)
        if isinstance(v, list):
            out.extend(x for x in v if isinstance(x, str))
    return out


# ---------------------------------------------------------------- 公開性

def repo_visibility(root: Path) -> str:
    """hojo-hq(PUBLIC_REMOTES)なら public、それ以外(unknown を含む)は private。"""
    return "public" if experience_log.repo_slug(Path(root)) in experience_log.PUBLIC_REMOTES else "private"


def decision_visibility(d: dict, root: Path, repo_vis: str | None = None) -> str:
    """Decision の公開性。private リポなら常に private。議事の任意キー visibility(Task 6)が
    public / private 以外なら private(fail-closed)。キーが無ければリポジトリの公開性。"""
    repo_vis = repo_vis or repo_visibility(root)
    if repo_vis != "public":
        return "private"
    v = d.get("visibility") if isinstance(d, dict) else None
    if v is None or (isinstance(v, str) and not v.strip()):
        return repo_vis
    return v.strip() if isinstance(v, str) and v.strip() in VISIBILITIES else "private"


# ---------------------------------------------------------------- 同義語表

def parse_synonyms(text: str) -> tuple[list[frozenset[str]], list[str]]:
    """1行1グループ(`,` 区切り・`#` 以降はコメント)。返り値は (グループ, 捨てた行の理由)。

    捨てる行: 2語未満 / 語が2〜30字でない / 9語以上 / 前の行のグループに出た語を含む / 200行を超えた分。
    """
    groups: list[frozenset[str]] = []
    reasons: list[str] = []
    seen: set[str] = set()
    count = 0
    for n, raw in enumerate(str(text).split("\n"), start=1):
        line = unicodedata.normalize("NFKC", raw.split("#", 1)[0]).strip()
        if not line:
            continue
        count += 1
        if count > SYN_LINES_MAX:
            reasons.append(f"{n}行目: 同義語表は {SYN_LINES_MAX} 行まで")
            continue
        words = [normalize(w) for w in line.split(",")]
        if any(not w for w in words):
            reasons.append(f"{n}行目: 空の語がある(`,` の前後を確認)")
            continue
        uniq = list(dict.fromkeys(words))
        if len(uniq) < 2:
            reasons.append(f"{n}行目: 2語以上が必要")
            continue
        if len(uniq) > SYN_GROUP_MAX:
            reasons.append(f"{n}行目: 1グループ {SYN_GROUP_MAX} 語まで")
            continue
        bad = [w for w in uniq if not SYN_WORD_MIN <= len(w) <= SYN_WORD_MAX]
        if bad:
            reasons.append(f"{n}行目: 各語は {SYN_WORD_MIN}〜{SYN_WORD_MAX} 字")
            continue
        dup = [w for w in uniq if w in seen]
        if dup:
            reasons.append(f"{n}行目: 前の行と同じ語がある({dup[0]})")
            continue
        seen.update(uniq)
        groups.append(frozenset(uniq))
    return groups, reasons


def load_synonyms(root: Path) -> list[frozenset[str]]:
    """docs/wiki/_synonyms.txt を読む(無ければ空)。V14 違反の行は捨てて audit に残す。"""
    path = Path(root) / SYNONYMS_PATH
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        audit(root, "wiki", f"synonyms unreadable: {type(e).__name__}")
        return []
    groups, reasons = parse_synonyms(text)
    for r in reasons:
        audit(root, "wiki", f"synonyms line dropped: {r}")
    return groups


# ---------------------------------------------------------------- 類似度(V10)

def title_units(text: str) -> set[str]:
    """ASCII 英数の連なりは1語、それ以外の文字・数字の連なりは2文字ずつ(1文字だけならその1文字)。"""
    s = unicodedata.normalize("NFKC", str(text)).lower()
    units: set[str] = set()
    runs: list[tuple[str, str]] = []
    for ch in s:
        if ch.isascii() and ch.isalnum():
            kind = "a"
        elif unicodedata.category(ch)[0] in ("L", "N"):
            kind = "j"
        else:
            kind = ""
        if kind and runs and runs[-1][0] == kind:
            runs[-1] = (kind, runs[-1][1] + ch)
        elif kind:
            runs.append((kind, ch))
        else:
            runs.append(("", ""))
    for kind, run in runs:
        if not run:
            continue
        if kind == "a" or len(run) == 1:
            units.add(run)
        else:
            units.update(run[i:i + 2] for i in range(len(run) - 1))
    return units


def title_similarity(a: str, b: str) -> float:
    """a の語(title_units)のうち b にもある割合。a が空なら 0.0。"""
    ua, ub = title_units(a), title_units(b)
    if not ua:
        return 0.0
    return len(ua & ub) / len(ua)
