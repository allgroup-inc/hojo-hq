#!/usr/bin/env python3
"""WikiSkill Phase 1 Task 4: Memory Bootstrap(関連情報だけを取り出す・stdlib のみ)。

新しいセッションに、今の作業(ブランチ名・直近 commit・変更ファイル・最初の指示)に
関係する過去の知識だけを渡す。wiki 全体は流し込まない。

区分(信頼階層順・出典ラベル付き):
    [D] 議事(Decision) > [未解決] 決裁キュー > [FK] 失敗台帳 > [再発防止] CLAUDE.md
    > [Skill] 現在有効な Skill > [Exp] Experience(低信頼・参考)

使い方:
    python3 scripts/memory_bootstrap.py hook SessionStart       # 段1: ブランチ・直近commitから(stdin に hook JSON)
    python3 scripts/memory_bootstrap.py hook UserPromptSubmit   # 段2: 最初の指示から(セッションに1回だけ)
    python3 scripts/memory_bootstrap.py query "<語> <語>"        # 手動確認用(停止スイッチは見ない)

規律: root(このリポジトリ)の外は読まない。private の Experience 行は出さない(audit に残す)。
1区分の読み込み失敗は audit して `- 該当なし` にし、他の区分は出す。hook は必ず JSON を出し exit 0。
"""
from __future__ import annotations

import json
import os
import posixpath
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decision_memory import load_decisions  # noqa: E402
from wikiskill_common import (  # noqa: E402
    EXPERIENCE_DIR,
    LOCAL_DIR,
    audit,
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
# 英文の Skill 説明にほぼ必ず出る語(一致しても関連の証拠にならない)
_ENGLISH_COMMON = frozenset(
    "the and for with use when you your this that from are not but can has have will into its "
    "per via all any how what who why was were used using also only more than then them they "
    "their there here out new one see each etc should would about which".split()
)
EXPERIENCE_MAX = 3
MAX_COMMITS = 10
MAX_FILES = 30
PROMPT_MAX = 500
TERMS_SHOWN = 200
NONE_LINE = "- 該当なし"
TRIMMED_LINE = "- (文字数上限のため省略)"

QUEUE_PATH = "docs/決裁キュー.md"
FAILURE_PATH = "docs/失敗台帳.md"
PREVENTION_PATH = "CLAUDE.md"
SKILLS_GLOB = ".claude/skills/*/SKILL.md"

_SPLIT_RE = re.compile(r"[\W_]+")
_ASCII_WORD_RE = re.compile(r"[a-z0-9]+")
_COMMIT_PREFIX_RE = re.compile(r"^[A-Za-z]+(?:\([^)]*\))?!?\s*[:：]\s*")
_QUEUE_ITEM_RE = re.compile(r"^\s*\d+(?:\.\d+)*[a-z]?[.)]\s")
_TITLE_PREFIX_RE = re.compile(r"^議事\s*[:：]\s*")
_BEKKAI_LABEL_RE = re.compile(r"[-*・\s]*ベッカイ(?:[(（][^)）]*[)）])?\s*[:：]?\s*")
_PIPE_RE = re.compile(r"(?<!\\)\|")
_BLOCK_SCALARS = {"", ">", ">-", ">+", "|", "|-", "|+"}


# ---------------------------------------------------------------- 小さな部品

def _git(root: Path, *args: str) -> str | None:
    """git の stdout(失敗は None)。日本語ファイル名をエスケープさせない。"""
    try:
        r = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args], cwd=str(root),
            capture_output=True, text=True, errors="replace", timeout=5,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


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


# ---------------------------------------------------------------- 検索語・採点

def build_query(root: Path, prompt: str | None = None) -> list[str]:
    """ブランチ名の語 + 直近10 commit の件名 + 変更ファイルの basename + prompt。定型語は除く。"""
    raw: list[str] = []
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch != "HEAD":
        raw.extend(re.split(r"[-_/]", branch))
    log = _git(root, "log", f"-{MAX_COMMITS}", "--format=%s") or ""
    for subject in log.splitlines():
        raw.append(_COMMIT_PREFIX_RE.sub("", subject.strip()))
    names = _git(root, "diff", "--name-only", "origin/main...HEAD")
    if names is None:
        names = _git(root, "diff", "--name-only", f"HEAD~{MAX_COMMITS}..HEAD") or ""
    raw.extend(posixpath.basename(n.strip()) for n in names.splitlines()[:MAX_FILES])
    if prompt:
        raw.append(str(prompt).strip()[:PROMPT_MAX])
    terms: list[str] = []
    for t in raw:
        t = t.strip()
        if len(t) < 2 or t.lower() in STOP_TERMS or t in terms:
            continue
        terms.append(t)
    return terms


def bigrams(text: str) -> set[str]:
    """空白・記号で区切った各断片の文字 bigram(小文字・NFKC)。

    除外: 助詞(の は を に が と で て)だけでできた bigram。英数字だけの bigram も
    ここでは作らない(ほぼ全英文に一致して雑音になるため。英数字は features() で語として扱う)。
    """
    out: set[str] = set()
    norm = unicodedata.normalize("NFKC", str(text)).lower()
    for chunk in _SPLIT_RE.split(norm):
        for a, b in zip(chunk, chunk[1:]):
            if a.isascii() and b.isascii():
                continue
            if a in PARTICLES and b in PARTICLES:
                continue
            out.add(a + b)
    return out


def features(text: str) -> set[str]:
    """採点に使う特徴量: bigrams() + 3文字以上の英数字の語(数字だけの語・ごく一般的な英単語は除く)。"""
    out = bigrams(text)
    norm = unicodedata.normalize("NFKC", str(text)).lower()
    for word in _ASCII_WORD_RE.findall(norm):
        if len(word) >= 3 and not word.isdigit() and word not in _ENGLISH_COMMON:
            out.add(word)
    return out


def score(query_terms: list[str], text: str) -> int:
    """query の特徴量と text の特徴量の共通数。"""
    return len(features(" ".join(query_terms)) & features(text))


# ---------------------------------------------------------------- 区分ごとの読み込み

def _decisions(root: Path) -> list[Source]:
    out = []
    for d in load_decisions(root):
        path = d["path"]
        if path.startswith("/") or path.startswith(".."):
            continue  # root の外(シンボリックリンク経由など)は出さない
        title = _TITLE_PREFIX_RE.sub("", _clean(d["title"]))
        why = d.get("why") or ""
        if not why and d.get("legacy"):
            # 過去の議事は「なぜ」節が無いことが多い。ベッカイ(前提を疑う役)の論点で代える
            why = _BEKKAI_LABEL_RE.sub(" ", _flat(d.get("bekkai") or "")).strip()
            if len(why) < 10:  # 見出し「ベッカイ(別解)」だけ等、中身が無い
                why = ""
        fields = []
        for label, value in (("裁定", d.get("outcome")), ("なぜ", why),
                             ("前提", d.get("premises")), ("ウタガイ", d.get("utagai"))):
            value = _flat(value or "")
            if value:
                fields.append(f"{label}: {_trunc(value, 160)}")
        if d.get("review_by"):
            mark = " **(期限切れ・再議論対象)**" if d.get("review_status") == "expired" else ""
            fields.append(f"見直し: {d['review_by']}{mark}")
        date = d.get("date") or "????-??-??"
        body = " / ".join(fields)
        line = f"- [D] {date} {title}" + (f" — {body}" if body else "") + f" → {path}"
        bonus = (0 if d.get("legacy") else 2) + (1 if d.get("status") == "adopted" else 0)
        out.append({"kind": "decision", "label": "[D]", "id": path, "path": path, "title": title,
                    "body": body, "line": line, "date": d.get("date") or "",
                    "text": d.get("text_head") or title, "bonus": bonus, "score": 0})
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
        out.append({"kind": "queue", "label": "[未解決]", "id": f"{QUEUE_PATH}#L{i}", "path": QUEUE_PATH,
                    "title": body[:60], "body": body, "line": f"- [未解決] {_trunc(body, 200)}",
                    "date": "", "text": body, "bonus": 0, "score": 0})
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
        out.append({"kind": "failure", "label": "[FK]", "id": f"{FAILURE_PATH}#{fid}", "path": FAILURE_PATH,
                    "title": title, "body": body, "line": f"- [{fid}] {date} {cat} — {body}",
                    "date": date, "text": " ".join([title, fact, cause, measure]), "bonus": 0, "score": 0})
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
            out.append({"kind": "prevention", "label": "[再発防止]", "id": f"{PREVENTION_PATH}#L{i}",
                        "path": PREVENTION_PATH, "title": text[:60], "body": text,
                        "line": f"- [再発防止] {_trunc(text, 200)}", "date": "", "text": text,
                        "bonus": 0, "score": 0})
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
        out.append({"kind": "skill", "label": "[Skill]", "id": rel, "path": rel, "title": name,
                    "body": desc, "line": f"- [Skill] {name} — {_trunc(desc, 160)}", "date": "",
                    "text": f"{name} {desc}", "bonus": 0, "score": 0})
    return out


def _experience(root: Path) -> list[Source]:
    """同じブランチの session_end 行(public のみ)を新しい順に最大3件。スコアは使わない。"""
    base = Path(root) / EXPERIENCE_DIR
    if not base.is_dir():
        return []
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    rows = []
    hidden = 0
    for f in base.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]/session-*.jsonl"):
        try:
            _inside(root, f)
        except ValueError:
            continue
        for raw in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if "session_end" not in raw:
                continue
            try:
                ev = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(ev, dict) or ev.get("event") != "session_end" or ev.get("branch") != branch:
                continue
            if ev.get("visibility") != "public":
                hidden += 1
                continue
            rows.append((str(ev.get("ts") or ""), ev, f))
    if hidden:
        audit(root, _COMPONENT, f"experience: hidden {hidden} private/non-public session_end row(s) on branch {branch}")
    rows.sort(key=lambda r: r[0], reverse=True)
    out = []
    for ts, ev, f in rows[:EXPERIENCE_MAX]:
        sid = str(ev.get("session_id") or "?")
        commits = ev.get("commits") if isinstance(ev.get("commits"), list) else []
        skills = ev.get("skills") if isinstance(ev.get("skills"), list) else []
        skill_text = ", ".join(str(s) for s in skills) or "-"
        line = f"- [Exp] {ts[:10] or '????-??-??'} session-{sid}: commits {len(commits)} / skills: {skill_text}"
        rel = f.relative_to(base.parent.parent).as_posix()
        out.append({"kind": "experience", "label": "[Exp]", "id": f"exp:{sid}:{ts}", "path": rel,
                    "title": f"session-{sid}", "body": line[2:], "line": line, "date": ts[:10],
                    "text": "", "bonus": 0, "score": 0})
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

def _select(sources: list[Source], terms: list[str], per_kind: int, min_score: int) -> dict[str, list[Source]]:
    qf = features(" ".join(terms)) if terms else set()
    # 検索語が短く特徴量が min_score 個に満たないときは「全部一致」を条件にする(例: 北極星 → 2個)
    threshold = min(min_score, len(qf))
    picked: dict[str, list[Source]] = {k: [] for k in KIND_ORDER}
    for s in sources:
        if s["kind"] == "experience":
            picked["experience"].append(s)
            continue
        if not qf:
            continue
        base = len(qf & features(s["text"]))
        if base < threshold:
            continue
        picked[s["kind"]].append({**s, "score": base + s.get("bonus", 0)})
    for kind in KIND_ORDER:
        if kind == "experience":
            picked[kind] = picked[kind][:EXPERIENCE_MAX]
        else:
            picked[kind] = sorted(picked[kind], key=lambda s: (s["score"], s.get("date") or ""),
                                  reverse=True)[:per_kind]
    return picked


def _render(picked: dict[str, list[Source]], terms_line: str | None, heading: str, budget_chars: int) -> str:
    """固定形で出力する。terms_line が None なら検索語の行は出さない(手動 query の語は再掲しない)。"""
    lines = {k: [s["line"] for s in picked.get(k, [])] for k in KIND_ORDER}
    trimmed = {k: False for k in KIND_ORDER}

    def build() -> str:
        parts = [heading]
        if terms_line is not None:
            parts.append("検索語: " + _trunc(terms_line or "(なし)", TERMS_SHOWN))
        for kind, _label, head in KINDS:
            parts.append(head)
            if lines[kind]:
                parts.extend(lines[kind])
            else:
                parts.append(TRIMMED_LINE if trimmed[kind] else NONE_LINE)
        return "\n".join(parts) + "\n"

    out = build()
    while len(out) > budget_chars:
        candidates = [k for k in KIND_ORDER if lines[k]]
        if not candidates:
            return out[:budget_chars]
        # 件数の多い区分の末尾から削る(同数なら信頼の低い区分から)
        kind = max(candidates, key=lambda k: (len(lines[k]), KIND_ORDER.index(k)))
        lines[kind].pop()
        trimmed[kind] = True
        out = build()
    return out


def retrieve(root: Path, terms: list[str], budget_chars: int = 6000, per_kind: int = 5, min_score: int = 3) -> str:
    """区分ごとにスコア降順で per_kind 件(min_score 未満は落とす)。合計 budget_chars 以内。"""
    picked = _select(collect_sources(root), list(terms), per_kind, min_score)
    return _render(picked, None, STAGE1_HEADING, budget_chars)


# ---------------------------------------------------------------- hook / CLI

def _stage1(root: Path) -> str | None:
    terms = build_query(root)
    picked = _select(collect_sources(root), terms, 5, 3)
    if not any(picked.values()):
        return None
    return _render(picked, ", ".join(terms), STAGE1_HEADING, 6000)


def _stage2(root: Path, prompt: str) -> str | None:
    """段1の検索語 + 最初の指示。段1で出す項目(同じ id)は除く。新しい項目が無ければ None。"""
    stage1_terms = build_query(root)
    sources = collect_sources(root)
    already = {s["id"] for items in _select(sources, stage1_terms, 5, 3).values() for s in items}
    prompt = str(prompt or "").strip()[:PROMPT_MAX]
    prompt_terms = [prompt] if len(prompt) >= 2 and prompt not in stage1_terms else []
    picked = _select(sources, stage1_terms + prompt_terms, 5, 3)
    fresh = {k: [s for s in items if s["id"] not in already] for k, items in picked.items()}
    if not any(fresh.values()):
        return None
    # 指示の本文は出力に再掲しない(検索にだけ使う)
    return _render(fresh, "最初の指示 + " + ", ".join(stage1_terms), STAGE2_HEADING, 6000)


def _hook(event: str) -> int:
    root = project_dir()
    try:
        payload = read_hook_input()
        if disabled(root):
            emit(event)
            return 0
        if event == "SessionStart":
            emit(event, additional_context=_stage1(root))
        elif event == "UserPromptSubmit":
            sid = session_id_of(payload)
            if sid.startswith("unknown-"):
                # セッションを特定できないと「1回だけ」を守れない(毎回注入になる)。注入せず記録だけ残す
                audit(root, _COMPONENT, "UserPromptSubmit: session_id missing; stage 2 skipped")
                emit(event)
                return 0
            marker = Path(root) / LOCAL_DIR / f"{_safe_id(sid)}.bootstrapped"
            if marker.exists():
                emit(event)
                return 0
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()  # 先に置く(失敗しても毎回の指示で繰り返し注入しない)
            prompt = payload.get("prompt")
            emit(event, additional_context=_stage2(root, prompt if isinstance(prompt, str) else ""))
        else:
            emit(event)
    except Exception as e:  # noqa: BLE001 — hook は作業を止めない。ただし silent にもしない
        reason = f"{type(e).__name__}: {e}"
        try:
            audit(root, _COMPONENT, f"{event} failed: {reason}")
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
