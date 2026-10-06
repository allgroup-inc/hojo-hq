#!/usr/bin/env python3
"""WikiSkill Phase 1 Task 4: Memory Bootstrap(関連情報だけを取り出す・stdlib のみ)。

新しいセッションに、今の作業(ブランチ名・直近 commit・変更ファイル・最初の指示)に
関係する過去の知識だけを渡す。wiki 全体は流し込まない。

区分(信頼階層順・出典ラベル付き):
    [D] 議事(Decision) > [未解決] 決裁キュー > [FK] 失敗台帳 > [再発防止] CLAUDE.md
    > [Skill] 現在有効な Skill > [Exp] Experience(低信頼・参考)

照合(語単位):
    検索語は文字種の切れ目で「語」に分ける(英数字の語 / カタカナ語 / 漢字などの語。ひらがなは捨てる)。
    英数字の語は文書の英数字トークンと完全一致で、日本語の語は bigram の6割以上(2個以下なら全部)が
    文書にあれば一致。score = 一致した語の数(+ 見出し・名前で一致すれば +1)。
    min_score = min(2, 語の数)。

使い方:
    python3 scripts/memory_bootstrap.py hook SessionStart       # 段1: ブランチ・直近commitから(stdin に hook JSON)
    python3 scripts/memory_bootstrap.py hook UserPromptSubmit   # 段2: 最初の指示から(セッションに1回だけ)
    python3 scripts/memory_bootstrap.py query "<語> <語>"        # 手動確認用(停止スイッチは見ない)

規律: root(このリポジトリ)の外は読まない。private の Experience 行は出さない(audit に残す)。
1区分の読み込み失敗は audit して `- 該当なし` にし、他の区分は出す。hook は必ず JSON を出し exit 0。
"""
from __future__ import annotations

import json
import math
import os
import posixpath
import re
import subprocess
import sys
import time
import unicodedata
from itertools import groupby
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decision_memory import load_decisions  # noqa: E402
from wikiskill_common import (  # noqa: E402
    EXPERIENCE_DIR,
    LOCAL_DIR,
    audit,
    audit_if_slow,
    disabled,
    emit,
    project_dir,
    read_hook_input,
    session_id_of,
)

Source = dict

_COMPONENT = "bootstrap"
STAGE1_HEADING = "# 🧠 Memory Bootstrap(段1: ブランチ・直近commitから)"
STAGE2_HEADING = "# 🧠 Memory Bootstrap(段2: 最初の指示から)"

# (kind, ラベル, 見出し) — この順が出力順(信頼階層)
KINDS = [
    ("decision", "[D]", "## 関連する決定 [D]（高信頼・議事）"),
    ("queue", "[未解決]", "## 未解決（決裁キュー）"),
    ("failure", "[FK]", "## 過去の失敗 [FK]（失敗台帳）"),
    ("prevention", "[再発防止]", "## 再発防止メモ [再発防止]（CLAUDE.md）"),
    ("skill", "[Skill]", "## 現在有効な関連Skill [Skill]"),
    ("experience", "[Exp]", "## 直近のExperience [Exp]（低信頼・参考。commitされたものだけ見える）"),
]
KIND_ORDER = [k for k, _l, _h in KINDS]

STOP_TERMS = {
    "claude", "main", "origin", "feat", "fix", "docs", "chore", "test", "refactor",
    "merge", "branch", "update", "add", "wip",
}
PARTICLES = frozenset("のはをにがとでて")
# 英文の Skill 説明にほぼ必ず出る語(一致しても関連の証拠にならない)。検索語の側だけで捨てる
_ENGLISH_COMMON = frozenset(
    "the and for with use when you your this that from are not but can has have will into its "
    "per via all any how what who why was were used using also only more than then them they "
    "their there here out new one see each etc should would about which to of in on at by or is it be as an".split()
)
PER_KIND = 5
MIN_SCORE = 2
BUDGET_CHARS = 6000
EXPERIENCE_MAX = 3
EXPERIENCE_MAX_FILES = 50
TAIL_BYTES = 4096
TAIL_BYTES_RETRY = 65536
MAX_COMMITS = 10
FALLBACK_COMMITS = 5      # origin/main..HEAD が空(main 上など)のときに見る直近 commit 数
SUBJECT_MAX = 60          # commit 件名から検索語を取る長さの上限
MAX_QUERY_UNITS = 40      # 検索語の単位(語)の総数の上限(先頭から残す)
SLOW_MS = 500             # hook 1回がこれを超えたら _audit.log に `slow <event> <ms>ms`(画面警告なし)
MAX_FILES = 30
PROMPT_MAX = 500
TERMS_SHOWN = 200
FIELD_MAX = 120
DECISION_LINE_MAX = 700
SHRINK_TO = 60            # 長すぎるとき 前提 → なぜ → 裁定 の順にここまで縮める
UTAGAI_MIN = 80           # 最後の手段でもウタガイはこの長さ(以上)を残す
TITLE_PREFIX_CHARS = 40
NONE_LINE = "- 該当なし"
TRIMMED_LINE = "- (文字数上限のため省略)"

QUEUE_PATH = "docs/決裁キュー.md"
FAILURE_PATH = "docs/失敗台帳.md"
PREVENTION_PATH = "CLAUDE.md"
SKILLS_GLOB = ".claude/skills/*/SKILL.md"

_SPLIT_RE = re.compile(r"[\W_]+")
_ASCII_WORD_RE = re.compile(r"[a-z0-9]+")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_COMMIT_PREFIX_RE = re.compile(r"^[A-Za-z]+(?:\([^)]*\))?!?\s*[:：]\s*")
_QUEUE_ITEM_RE = re.compile(r"^\s*\d+(?:\.\d+)*[a-z]?[.)]\s")
_TITLE_PREFIX_RE = re.compile(r"^議事\s*[:：]\s*")
# ベッカイ欄の先頭にある自分自身のラベル(「- ベッカイ:」)だけを落とす。本文中の語は触らない
_OWN_LABEL_RE = {
    "ベッカイ": re.compile(r"^[-*・\s]*ベッカイ(?:[(（][^)）]*[)）])?\s*[:：]\s*"),
}
_PIPE_RE = re.compile(r"(?<!\\)\|")
_BLOCK_SCALARS = {"", ">", ">-", ">+", "|", "|-", "|+"}


# ---------------------------------------------------------------- 小さな部品

def _git_raw(root: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args], cwd=str(root),
            capture_output=True, text=True, errors="replace", timeout=5,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


_GIT_TOP_OK: dict[str, bool] = {}


def _git_ready(root: Path) -> bool:
    """root 自身が git リポジトリの最上位か。違えば(外側のリポジトリを読まないよう)git を使わない。"""
    try:
        key = str(Path(root).resolve())
    except OSError:
        return False
    if key not in _GIT_TOP_OK:
        top = _git_raw(root, "rev-parse", "--show-toplevel")
        ok = False
        if top:
            try:
                ok = Path(top).resolve() == Path(key)
            except OSError:
                ok = False
        _GIT_TOP_OK[key] = ok
        if not ok:
            audit(root, _COMPONENT, f"git: root is not the top of a git repository (top={top or '-'}); git terms skipped")
    return _GIT_TOP_OK[key]


def _git(root: Path, *args: str) -> str | None:
    """git の stdout(失敗・root がリポジトリの最上位でないときは None)。日本語ファイル名はエスケープさせない。"""
    if not _git_ready(root):
        return None
    return _git_raw(root, *args)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").replace("**", "")).strip()


def _flat(text: str) -> str:
    """議事の節を1行に: 表の区切り行・縦棒・見出し記号を落とす(表示用)。"""
    t = _clean(text)
    t = re.sub(r"\|?(?:\s*:?-{3,}:?\s*\|)+", " ", t)
    t = re.sub(r"#{1,6}\s+", "", t)
    return re.sub(r"\s+", " ", t.replace("|", " ")).strip()


def _trunc(text: str, limit: int) -> str:
    text = _clean(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _inside(root: Path, path: Path) -> Path:
    """path が root 配下(シンボリックリンク解決後)であることを確かめて返す。外なら ValueError。"""
    resolved = path.resolve()
    resolved.relative_to(Path(root).resolve())
    return resolved


def _read_inside(root: Path, rel: str) -> str:
    return _inside(root, Path(root) / rel).read_text(encoding="utf-8", errors="replace")


def _safe_id(session_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(session_id)) or "unknown"


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKC", str(text)).lower()


# ---------------------------------------------------------------- 検索語・採点

def build_query(root: Path, prompt: str | None = None) -> list[str]:
    """ブランチ名の語 → 変更ファイルの basename → このブランチだけの commit 件名(新しい順) → prompt。

    commit は `origin/main..HEAD`(最大10件)。空(main 上・origin/main 不明)なら直近5件。
    件名は先頭60字だけから語を取る。語の単位(語)は合計40個まで(先頭から残す)。定型語は除く。
    """
    raw: list[str] = []
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch != "HEAD":
        raw.extend(re.split(r"[-_/]", branch))
    names = _git(root, "diff", "--name-only", "origin/main...HEAD")
    if names is None:
        names = _git(root, "diff", "--name-only", f"HEAD~{MAX_COMMITS}..HEAD") or ""
    raw.extend(posixpath.basename(n.strip()) for n in names.splitlines()[:MAX_FILES])
    log = _git(root, "log", "origin/main..HEAD", "--format=%s", f"-{MAX_COMMITS}") or ""
    if not log.strip():
        log = _git(root, "log", f"-{FALLBACK_COMMITS}", "--format=%s") or ""
    for subject in log.splitlines():
        raw.append(_COMMIT_PREFIX_RE.sub("", subject.strip())[:SUBJECT_MAX])
    if prompt:
        raw.append(str(prompt).strip()[:PROMPT_MAX])
    terms: list[str] = []
    for t in raw:
        t = t.strip()
        if len(t) < 2 or t.lower() in STOP_TERMS or t in terms:
            continue
        terms.append(t)
    units = query_units(terms)
    if len(units) > MAX_QUERY_UNITS:
        # 上限を超えたら、先頭(ブランチ名の語)から40単位だけを語として残す
        terms = [word for _kind, word, _grams in units[:MAX_QUERY_UNITS]]
    return terms


def bigrams(text: str) -> set[str]:
    """空白・記号で区切った各断片の文字 bigram(小文字・NFKC)。

    除外: 助詞(の は を に が と で て)だけでできた bigram と、英数字だけの bigram
    (英数字は語単位で照合する)。
    """
    out: set[str] = set()
    for chunk in _SPLIT_RE.split(_norm(text)):
        for a, b in zip(chunk, chunk[1:]):
            if a.isascii() and b.isascii():
                continue
            if a in PARTICLES and b in PARTICLES:
                continue
            out.add(a + b)
    return out


def features(text: str) -> set[str]:
    """文書側の特徴量: bigrams() + 英数字トークン(小文字・2文字以上)。"""
    out = bigrams(text)
    out.update(w for w in _ASCII_WORD_RE.findall(_norm(text)) if len(w) >= 2)
    return out


def _char_class(c: str) -> str:
    if c.isascii():
        return "a"
    o = ord(c)
    if 0x30A0 <= o <= 0x30FF:
        return "k"  # カタカナ(長音符ー を含む)
    if 0x3040 <= o <= 0x309F:
        return "h"  # ひらがな(助詞・送り仮名。語にしない)
    return "o"      # 漢字など


def query_units(terms: list[str]) -> list[tuple[str, str, frozenset]]:
    """検索語を照合の単位(語)に分ける: (種類 "a"/"j", 語, 語の bigram)。重複は除く。"""
    units: list[tuple[str, str, frozenset]] = []
    seen: set[tuple[str, str]] = set()
    for term in terms:
        for chunk in _SPLIT_RE.split(_norm(term)):
            for cls, chars in groupby(chunk, key=_char_class):
                run = "".join(chars)
                if cls == "h":
                    continue
                if cls == "a":
                    if len(run) < 2 or run.isdigit() or run in _ENGLISH_COMMON:
                        continue
                    key, grams = ("a", run), frozenset()
                else:
                    grams = frozenset(bigrams(run))
                    if not grams:
                        continue
                    key = ("j", run)
                if key in seen:
                    continue
                seen.add(key)
                units.append((key[0], run, grams))
    return units


def _unit_matches(unit: tuple[str, str, frozenset], feats: set[str]) -> bool:
    kind, word, grams = unit
    if kind == "a":
        return word in feats
    n = len(grams)
    need = n if n <= 2 else max(2, math.ceil(0.6 * n))
    return len(grams & feats) >= need


def _match_score(units, feats: set[str], title_feats: set[str]) -> int:
    matched = sum(1 for u in units if _unit_matches(u, feats))
    if matched and title_feats and any(_unit_matches(u, title_feats) for u in units):
        matched += 1
    return matched


def score(query_terms: list[str], text: str, title: str = "") -> int:
    """一致した語の数(+ title で一致すれば +1)。"""
    return _match_score(query_units(query_terms), features(text), features(title) if title else set())


# ---------------------------------------------------------------- 区分ごとの読み込み

def _src(kind: str, label: str, sid: str, path: str, title: str, body: str, line: str,
         date: str, text: str, match_title: str) -> Source:
    return {"kind": kind, "label": label, "id": sid, "path": path, "title": title, "body": body,
            "line": line, "date": date, "text": text, "match_title": match_title, "score": 0}


def _decision_line(d: dict, title: str) -> str:
    """欄はそれぞれ自分の出典からだけ作る(読み替えない)。前の欄と同じ内容は出さない。700字まで。

    欄ごとに120字まで。全体が長すぎるときは 前提 → なぜ → 裁定 の順に60字へ縮め、まだ長ければ
    前提 → なぜ → ベッカイ の順に落とす。ウタガイ(最低80字)と見直し欄(期限切れ表示を含む)と
    末尾の ` → <path>` は落とさない。
    """
    texts: dict[str, str] = {}
    shown: list[str] = []
    for label, value in (("裁定", d.get("outcome")), ("なぜ", d.get("why")), ("前提", d.get("premises")),
                         ("ウタガイ", d.get("utagai")), ("ベッカイ", d.get("bekkai"))):
        text = _flat(value or "")
        if label in _OWN_LABEL_RE:
            text = _OWN_LABEL_RE[label].sub("", text)
        if not text or any(text[:80] in s for s in shown):
            continue
        shown.append(text)
        texts[label] = text
    caps = {label: FIELD_MAX for label in texts}
    review = ""
    if d.get("review_by"):
        mark = " **(期限切れ・再議論対象)**" if d.get("review_status") == "expired" else ""
        review = f"見直し: {d['review_by']}{mark}"
    head_title = [title]
    tail = f" → {d['path']}"

    def compose() -> str:
        parts = [f"{label}: {_trunc(text, caps[label])}" for label, text in texts.items()]
        if review:
            parts.append(review)
        return f"- [D] {d.get('date') or '????-??-??'} {head_title[0]}" + (" — " + " / ".join(parts) if parts else "") + tail

    def over() -> int:
        return len(compose()) - DECISION_LINE_MAX

    def shrink(label: str, floor: int) -> None:
        excess = over()
        if excess > 0 and label in texts:
            shown_len = min(len(texts[label]), caps[label])
            caps[label] = min(caps[label], max(floor, shown_len - excess))

    for label in ("前提", "なぜ", "裁定"):
        if over() > 0 and label in texts:
            caps[label] = min(caps[label], SHRINK_TO)
    for label in ("前提", "なぜ", "ベッカイ"):
        if over() > 0:
            texts.pop(label, None)
    shrink("ウタガイ", UTAGAI_MIN)  # 最後の手段(それでも80字は残す)
    shrink("裁定", 20)
    if over() > 0:
        head_title[0] = _trunc(title, max(20, len(title) - over()))
    return compose()


def _decisions(root: Path) -> list[Source]:
    out = []
    for d in load_decisions(root):
        path = d["path"]
        if path.startswith("/") or path.startswith(".."):
            continue  # root の外(シンボリックリンク経由など)は出さない
        title = _TITLE_PREFIX_RE.sub("", _clean(d["title"]))
        line = _decision_line(d, title)
        out.append(_src("decision", "[D]", path, path, title, line, line, d.get("date") or "",
                        d.get("text_head") or title, title))
    return out


def _queue(root: Path) -> list[Source]:
    out = []
    parent_done = False
    for i, line in enumerate(_read_inside(root, QUEUE_PATH).splitlines(), 1):
        if not _QUEUE_ITEM_RE.match(line):
            continue
        done = "~~" in line or "✅" in line
        if not line[:1].isspace():
            parent_done = done
        elif parent_done:
            continue  # 完了済み項目の下の手順(字下げした番号行)も完了扱い
        if done:
            continue
        body = _clean(line)
        out.append(_src("queue", "[未解決]", f"{QUEUE_PATH}#L{i}", QUEUE_PATH, body[:60], body,
                        f"- [未解決] {_trunc(body, 200)}", "", body, body[:TITLE_PREFIX_CHARS]))
    return out


def _failures(root: Path) -> list[Source]:
    out = []
    for line in _read_inside(root, FAILURE_PATH).splitlines():
        if not line.startswith("| FK-"):
            continue
        cells = [c.strip() for c in _PIPE_RE.split(line.strip().strip("|"))]
        cells += [""] * (11 - len(cells))
        fid, date, cat, fact, _impact, _found, cause, measure = cells[:8]
        title = f"{fid} {date} {cat}"
        body = f"{_trunc(fact, 200)} / 対策: {_trunc(measure, 160)}"
        out.append(_src("failure", "[FK]", f"{FAILURE_PATH}#{fid}", FAILURE_PATH, title, body,
                        f"- [{fid}] {date} {cat} — {body}", date,
                        " ".join([title, fact, cause, measure]), f"{fid} {cat}"))
    return out


def _preventions(root: Path) -> list[Source]:
    out = []
    in_section = False
    for i, line in enumerate(_read_inside(root, PREVENTION_PATH).splitlines(), 1):
        if line.startswith("## "):
            in_section = line.startswith("## 再発防止メモ")
            continue
        if line.startswith("# "):
            in_section = False
            continue
        if in_section and line.startswith("- "):
            text = _clean(line[2:])
            out.append(_src("prevention", "[再発防止]", f"{PREVENTION_PATH}#L{i}", PREVENTION_PATH,
                            text[:60], text, f"- [再発防止] {_trunc(text, 200)}", "", text,
                            text[:TITLE_PREFIX_CHARS]))
    return out


def _unquote(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def _skill_frontmatter(path: Path) -> dict:
    """SKILL.md の frontmatter から name / description だけ読む(閉じの `---` で読むのをやめる)。"""
    fm: dict = {}
    key = None
    block: list[str] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        if f.readline().strip() != "---":
            return fm
        for raw in f:
            line = raw.rstrip("\n")
            if line.strip() == "---":
                break
            if key and (line.startswith((" ", "\t")) or not line.strip()):
                block.append(line.strip())
                continue
            if key:
                fm[key] = " ".join(b for b in block if b)
                key, block = None, []
            m = re.match(r"^(name|description)\s*:(.*)$", line)
            if not m:
                continue
            value = m.group(2).strip()
            if value in _BLOCK_SCALARS:
                key, block = m.group(1), []
            else:
                fm[m.group(1)] = _unquote(value)
        if key:
            fm[key] = " ".join(b for b in block if b)
    return fm


def _skills(root: Path) -> list[Source]:
    out = []
    base = Path(root)
    for p in sorted(base.glob(SKILLS_GLOB)):
        try:
            _inside(root, p)
        except ValueError:
            continue
        fm = _skill_frontmatter(p)
        name = _clean(fm.get("name") or p.parent.name)
        desc = _clean(fm.get("description") or "")
        rel = p.relative_to(base).as_posix()
        out.append(_src("skill", "[Skill]", rel, rel, name, desc, f"- [Skill] {name} — {_trunc(desc, 160)}",
                        "", f"{name} {desc}", name))
    return out


def _tail_lines(path: Path) -> list[str]:
    """ファイル末尾の完全な行だけを返す(既定 4KB。末尾の行が窓より長く切れていたら 64KB で読み直す)。"""
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        lines: list[str] = []
        for n in (TAIL_BYTES, TAIL_BYTES_RETRY):
            start = max(0, size - n)
            fh.seek(start)
            lines = fh.read(size - start).decode("utf-8", errors="replace").split("\n")
            if start == 0:
                return lines
            partial, lines = lines[0], lines[1:]
            if "session_end" in partial or not any(l.strip() for l in lines):
                # 末尾の1行が窓より長く途中で切れている(event キーは行頭側にあるので見えないことがある)
                if not any("session_end" in l for l in lines):
                    continue
            return lines
        return lines


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _experience(root: Path) -> list[Source]:
    """同じブランチの session_end(public のみ)を新しい順に最大3件。スコアは使わない。

    月フォルダを新しい順、ファイルを新しい順(更新時刻→名前)に見て、各ファイルの末尾だけを読む。
    3件見つかるか 50 ファイル見たら打ち切る(古い月は開かない)。
    """
    base = Path(root) / EXPERIENCE_DIR
    if not base.is_dir():
        return []
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    months = sorted((d for d in base.iterdir() if d.is_dir() and _MONTH_RE.match(d.name)),
                    key=lambda d: d.name, reverse=True)
    rows = []
    hidden = malformed = scanned = 0
    for month in months:
        if len(rows) >= EXPERIENCE_MAX or scanned >= EXPERIENCE_MAX_FILES:
            break
        files = sorted(month.glob("session-*.jsonl"), key=lambda p: (_mtime(p), p.name), reverse=True)
        for f in files:
            if len(rows) >= EXPERIENCE_MAX or scanned >= EXPERIENCE_MAX_FILES:
                break
            scanned += 1
            try:
                _inside(root, f)
            except ValueError:
                continue
            for raw in reversed(_tail_lines(f)):
                if "session_end" not in raw:
                    continue
                try:
                    ev = json.loads(raw)
                except ValueError:
                    malformed += 1
                    continue
                if not isinstance(ev, dict):
                    malformed += 1
                    continue
                if ev.get("event") != "session_end":
                    continue
                # このファイルの最新の session_end だけを見る
                if ev.get("branch") == branch:
                    if ev.get("visibility") == "public":
                        rows.append((str(ev.get("ts") or ""), ev, f))
                    else:
                        hidden += 1
                break
    if hidden:
        audit(root, _COMPONENT, f"experience: hidden {hidden} private/non-public session_end row(s) on branch {branch}")
    if malformed:
        audit(root, _COMPONENT, f"experience: skipped {malformed} malformed session_end row(s)")
    rows.sort(key=lambda r: r[0], reverse=True)
    out = []
    for ts, ev, f in rows[:EXPERIENCE_MAX]:
        sid = str(ev.get("session_id") or "?")
        commits = ev.get("commits") if isinstance(ev.get("commits"), list) else []
        skills = ev.get("skills") if isinstance(ev.get("skills"), list) else []
        skill_text = ", ".join(str(s) for s in skills) or "-"
        line = f"- [Exp] {ts[:10] or '????-??-??'} session-{sid}: commits {len(commits)} / skills: {skill_text}"
        rel = f.relative_to(Path(root)).as_posix()
        out.append(_src("experience", "[Exp]", f"exp:{sid}:{ts}", rel, f"session-{sid}", line[2:], line,
                        ts[:10], "", ""))
    return out


COLLECTORS = [
    ("decision", _decisions),
    ("queue", _queue),
    ("failure", _failures),
    ("prevention", _preventions),
    ("skill", _skills),
    ("experience", _experience),
]


def collect_sources(root: Path) -> list[Source]:
    """全区分の候補(未採点)。1区分の失敗は audit して空扱いにし、他の区分は続ける。"""
    out: list[Source] = []
    for kind, fn in COLLECTORS:
        try:
            out.extend(fn(Path(root)))
        except Exception as e:  # noqa: BLE001 — 1区分の不具合で Bootstrap 全体を止めない
            audit(root, _COMPONENT, f"{kind}: {type(e).__name__}: {e}")
    return out


# ---------------------------------------------------------------- 選択・出力

def _feats(s: Source) -> tuple[set[str], set[str]]:
    """候補の特徴量(1プロセス内で使い回す)。"""
    if "_f" not in s:
        s["_f"] = features(s["text"])
        s["_tf"] = features(s["match_title"]) if s.get("match_title") else set()
    return s["_f"], s["_tf"]


def _select(sources: list[Source], terms: list[str], per_kind: int = PER_KIND, min_score: int = MIN_SCORE,
            exclude: frozenset | set = frozenset()) -> dict[str, list[Source]]:
    """区分ごとに score 降順 → 日付降順で per_kind 件。exclude の id は順位付けの前に除く。"""
    units = query_units(terms)
    need = min(min_score, len(units))
    picked: dict[str, list[Source]] = {k: [] for k in KIND_ORDER}
    for s in sources:
        if s["id"] in exclude:
            continue
        if s["kind"] == "experience":
            picked["experience"].append(s)
            continue
        if not units:
            continue
        f, tf = _feats(s)
        sc = _match_score(units, f, tf)
        if sc < max(need, 1):
            continue
        picked[s["kind"]].append({**s, "score": sc})
    for kind in KIND_ORDER:
        if kind == "experience":
            picked[kind] = picked[kind][:EXPERIENCE_MAX]
        else:
            picked[kind] = sorted(picked[kind], key=lambda s: (s["score"], s.get("date") or ""),
                                  reverse=True)[:per_kind]
    return picked


def _render(picked: dict[str, list[Source]], terms_line: str | None, heading: str,
            budget_chars: int) -> tuple[str, set[str]]:
    """固定形で出力し、(本文, 実際に表示した項目の id) を返す。

    terms_line が None なら検索語の行は出さない(手動 query の語は再掲しない)。
    """
    items = {k: list(picked.get(k, [])) for k in KIND_ORDER}
    trimmed = {k: False for k in KIND_ORDER}

    def build() -> str:
        parts = [heading]
        if terms_line is not None:
            parts.append("検索語: " + _trunc(terms_line or "(なし)", TERMS_SHOWN))
        for kind, _label, head in KINDS:
            parts.append(head)
            if items[kind]:
                parts.extend(s["line"] for s in items[kind])
            else:
                parts.append(TRIMMED_LINE if trimmed[kind] else NONE_LINE)
        return "\n".join(parts) + "\n"

    out = build()
    while len(out) > budget_chars:
        candidates = [k for k in KIND_ORDER if items[k]]
        if not candidates:
            return out[:budget_chars], set()
        # 件数の多い区分の末尾から削る(同数なら信頼の低い区分から)
        kind = max(candidates, key=lambda k: (len(items[k]), KIND_ORDER.index(k)))
        items[kind].pop()
        trimmed[kind] = True
        out = build()
    return out, {s["id"] for k in KIND_ORDER for s in items[k]}


def retrieve(root: Path, terms: list[str], budget_chars: int = BUDGET_CHARS, per_kind: int = PER_KIND,
             min_score: int = MIN_SCORE) -> str:
    """区分ごとに score 降順で per_kind 件(min(min_score, 語の数) 未満は落とす)。合計 budget_chars 以内。"""
    picked = _select(collect_sources(root), list(terms), per_kind, min_score)
    return _render(picked, None, STAGE1_HEADING, budget_chars)[0]


# ---------------------------------------------------------------- hook / CLI

def _stage1_render(root: Path, sources: list[Source], terms: list[str]) -> tuple[str | None, set[str]]:
    picked = _select(sources, terms)
    if not any(picked.values()):
        return None, set()
    return _render(picked, ", ".join(terms), STAGE1_HEADING, BUDGET_CHARS)


def _stage1(root: Path) -> str | None:
    return _stage1_render(root, collect_sources(root), build_query(root))[0]


def _stage2(root: Path, prompt: str) -> str | None:
    """段1の検索語 + 最初の指示。段1で実際に表示した項目は順位付けの前に除く。新しい項目が無ければ None。"""
    stage1_terms = build_query(root)
    sources = collect_sources(root)
    _text, shown = _stage1_render(root, sources, stage1_terms)
    prompt = str(prompt or "").strip()[:PROMPT_MAX]
    prompt_terms = [prompt] if len(prompt) >= 2 and prompt not in stage1_terms else []
    picked = _select(sources, stage1_terms + prompt_terms, exclude=shown)
    if not any(picked.values()):
        return None
    # 指示の本文は出力に再掲しない(検索にだけ使う)
    return _render(picked, "最初の指示 + " + ", ".join(stage1_terms), STAGE2_HEADING, BUDGET_CHARS)[0]


def _hook(event: str) -> int:
    started = time.perf_counter()
    root = project_dir()

    def finish(**kw) -> int:
        """遅かったら audit に1行(監査のみ・画面警告なし)残してから、JSON を1つ出す。"""
        try:
            audit_if_slow(root, _COMPONENT, event, started, SLOW_MS)
        except Exception:  # noqa: BLE001 — 計測の失敗で本来の出力を止めない
            pass
        emit(event, **kw)
        return 0

    try:
        payload = read_hook_input()
        if disabled(root):
            emit(event)
            return 0
        if event == "SessionStart":
            return finish(additional_context=_stage1(root))
        elif event == "UserPromptSubmit":
            sid = session_id_of(payload)
            if sid.startswith("unknown-"):
                # セッションを特定できないと「1回だけ」を守れない(毎回注入になる)。注入せず警告する
                audit(root, _COMPONENT, "UserPromptSubmit: session_id missing; stage 2 skipped")
                return finish(system_message=(
                    f"⚠ Memory Bootstrap: session_id が無いため段2(最初の指示からの検索)を省略しました。"
                    f"audit: {EXPERIENCE_DIR}/_audit.log"))
            marker = Path(root) / LOCAL_DIR / f"{_safe_id(sid)}.bootstrapped"
            if marker.exists():
                return finish()
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()  # 先に置く(失敗しても毎回の指示で繰り返し注入しない)
            prompt = payload.get("prompt")
            return finish(additional_context=_stage2(root, prompt if isinstance(prompt, str) else ""))
        else:
            emit(event)
    except Exception as e:  # noqa: BLE001 — hook は作業を止めない。ただし silent にもしない
        reason = f"{type(e).__name__}: {e}"
        try:
            audit(root, _COMPONENT, f"{event} failed: {reason}")
            audit_if_slow(root, _COMPONENT, event, started, SLOW_MS)
        except Exception:  # noqa: BLE001
            pass
        emit(event, system_message=f"⚠ Memory Bootstrap 失敗: {reason}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "hook":
        return _hook(argv[2])
    if len(argv) >= 3 and argv[1] == "query":
        terms = [t for a in argv[2:] for t in a.split() if t.strip()]
        print(retrieve(project_dir(), terms), end="")
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
