#!/usr/bin/env python3
"""WikiSkill Phase 1 Task 4: Memory Bootstrap(関連情報だけを取り出す・stdlib のみ)。

新しいセッションに、今の作業(ブランチ名・直近 commit・変更ファイル・最初の指示)に
関係する過去の知識だけを渡す。wiki 全体は流し込まない。

区分(信頼階層順・出典ラベル付き):
    [D] 議事(Decision) > [未解決] 決裁キュー > [FK] 失敗台帳 > [再発防止] CLAUDE.md
    > [Wiki] 承認済みの Official Wiki(docs/wiki/*.md・人が承認) > [Skill] 現在有効な Skill
    > [Exp] Experience(低信頼・参考)

照合(語単位):
    検索語は文字種の切れ目で「語」に分ける(英数字の語 / カタカナ語 / 漢字などの語。ひらがなは捨てる)。
    英数字の語は文書の英数字トークンと完全一致で、日本語の語は bigram の6割以上(2個以下なら全部)が
    文書にあれば一致。score = 一致した語の数(+ 見出し・名前で一致すれば +1。この加点は並び順にだけ使う)。
    min_score = min(2, 語の数)。見出しの加点を除いた一致数がこれに届かないものは出さない
    (Skill だけは名前での一致も1語に数える。名前は識別子なので、語がそのまま入っていれば関連が強い。
    ただし段1では数えず、段2では最初の指示の語が名前に当たったときだけ数える。手動 query は従来どおり)。
    同義語表(docs/wiki/_synonyms.txt)の同じ行の語は1つの語として扱う(どれか1つが当たれば1語)。
    区分ごとに、その区分の25%を超える項目(かつ3件以上)に当たる語は「ありふれた語」として照合に使わない。
    ハッシュ・乱数らしい語(16進の6文字以上 / 数字2つ以上を含む英数6文字)と .claude/experience の
    ファイル名は検索語にしない。段2は「最初の指示 + ブランチ名の語」で探す(指示から語が2つ取れなければ段1の語も使う)。

使い方:
    python3 scripts/memory_bootstrap.py hook SessionStart       # 段1: ブランチ・直近commitから(stdin に hook JSON)
    python3 scripts/memory_bootstrap.py hook UserPromptSubmit   # 段2: 最初の指示から(セッションに1回だけ)
    python3 scripts/memory_bootstrap.py query "<語> <語>"        # 手動確認用(停止スイッチは見ない)

規律: root(このリポジトリ)の外は読まない。private の Experience 行は出さない(audit に残す)。
[Wiki] は docs/wiki/ 直下の approved(visibility がリポの公開性と一致)だけ。_candidates/ と _archive/ は開かない。
.claude/wiki.off があれば [Wiki] だけ止める(.claude/memory.off は従来どおり全体を止める)。
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
    current_branch,
    disabled,
    emit,
    group_session_files,
    project_dir,
    read_hook_input,
    session_id_of,
)

if __name__ == "__main__":  # wiki_schema.decision_conflicts の `import memory_bootstrap` が2つ目の複製を読まない
    sys.modules.setdefault("memory_bootstrap", sys.modules[__name__])

try:  # 読めなくても Bootstrap 全体は止めない([Wiki] と同義語だけ無しになり、audit に残す)
    import wiki_schema as _ws  # noqa: E402
    _WS_ERROR = ""
except Exception as _e:  # noqa: BLE001
    _ws = None
    _WS_ERROR = f"{type(_e).__name__}: {_e}"

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
    ("wiki", "[Wiki]", "## 承認済みの知識 [Wiki](Official Wiki・人が承認)"),
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
DF_RATIO = 0.25           # 区分の項目のこの割合を超えて当たる語は、その区分では照合に使わない
DF_MIN_COUNT = 3          # ただし当たる項目がこの数未満なら「ありふれた語」とは見なさない(小さな区分を守る)
NOTE_SHOWN = 60           # session_end の無いセッションの [Exp] 行に出す note の長さ
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
WIKI_KNOWLEDGE_CHARS = 600  # [Wiki] の照合に使う「## 知識」の先頭の長さ
WIKI_SUMMARY_SHOWN = getattr(_ws, "SHOWN_SUMMARY", 160)
WIKI_OFF_PATH = getattr(_ws, "WIKI_OFF", ".claude/wiki.off")
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
# 表の見出し・節の見出しから拾った「ベッカイ(別解)」だけのラベル(先頭に並んだものを落とす。「ベッカイの案」は残す)
_HEADING_LABEL_RE = {
    "ベッカイ": re.compile(r"^(?:[-*・\s]*ベッカイ(?:[(（][^)）]*[)）])?(?=\s|$)\s*)+"),
}
_PIPE_RE = re.compile(r"(?<!\\)\|")
# ハッシュ・乱数らしい英数字の語(検索語にしない): 16進の6文字以上(数字と a-f を両方含む)/
# 数字2つ以上と英字を含む6文字(ブランチ名の末尾 3mbx56 など)
_HEX_UNIT_RE = re.compile(r"^(?=.*\d)(?=.*[a-f])[0-9a-f]{6,}$")
_RANDOM_UNIT_RE = re.compile(r"^(?=(?:.*\d){2})(?=.*[a-z])[a-z0-9]{6}$")
_STATUS_LABEL = {"deferred": "[D:保留]", "rejected": "[D:却下]"}
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

def _branch(root: Path) -> str:
    """今のブランチ名(detached HEAD なら origin の唯一の一致。決められなければ "unknown")。"""
    return current_branch(lambda *a: _git(root, *a))


def _filter_terms(raw: list[str]) -> list[str]:
    """空白を落とし、2文字未満・定型語・重複を除く(順序は保つ)。"""
    terms: list[str] = []
    for t in raw:
        t = t.strip()
        if len(t) < 2 or t.lower() in STOP_TERMS or t in terms:
            continue
        terms.append(t)
    return terms


def branch_terms(root: Path) -> list[str]:
    """ブランチ名の語(ブランチが決められなければ空)。"""
    branch = _branch(root)
    return _filter_terms(re.split(r"[-_/]", branch)) if branch != "unknown" else []


def build_query(root: Path, prompt: str | None = None) -> list[str]:
    """ブランチ名の語 → 変更ファイルの basename → このブランチだけの commit 件名(新しい順) → prompt。

    commit は `origin/main..HEAD`(最大10件)。空(main 上・origin/main 不明)なら直近5件。
    件名は先頭60字だけから語を取る。語の単位(語)は合計40個まで(先頭から残す)。定型語は除く。
    .claude/experience/ の下のファイル名(session-<id>.jsonl)は検索語にしない(関係のない記録の雑音)。
    """
    raw: list[str] = list(branch_terms(root))
    names = _git(root, "diff", "--name-only", "origin/main...HEAD")
    if names is None:
        names = _git(root, "diff", "--name-only", f"HEAD~{MAX_COMMITS}..HEAD") or ""
    files = [n.strip() for n in names.splitlines() if not n.strip().startswith(EXPERIENCE_DIR + "/")]
    raw.extend(posixpath.basename(n) for n in files[:MAX_FILES])
    log = _git(root, "log", "origin/main..HEAD", "--format=%s", f"-{MAX_COMMITS}") or ""
    if not log.strip():
        log = _git(root, "log", f"-{FALLBACK_COMMITS}", "--format=%s") or ""
    for subject in log.splitlines():
        raw.append(_COMMIT_PREFIX_RE.sub("", subject.strip())[:SUBJECT_MAX])
    if prompt:
        raw.append(str(prompt).strip()[:PROMPT_MAX])
    terms = _filter_terms(raw)
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
                    if _HEX_UNIT_RE.match(run) or _RANDOM_UNIT_RE.match(run):
                        continue  # commit の SHA・セッション ID・ブランチ名の乱数部分
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


def _syn_key(word: str) -> str:
    return _ws.normalize(word) if _ws is not None else word


def query_groups(terms: list[str], synonyms: list[frozenset[str]] | None = None
                 ) -> list[tuple[tuple[str, str, frozenset], ...]]:
    """query_units(terms) の各語に、同義語表で同じ行の語(query_units([語]) で1単位になるもの)を束ねる。

    返り値は語ごとの tuple(先頭が検索語そのもの)。同じ行の語が検索語に2つあっても1つの tuple にまとめる
    (1語として数える)。同義語が無ければ query_units の各単位を1つずつ包んだものと同じ。
    """
    index: dict[str, frozenset[str]] = {}
    for group in synonyms or ():
        for w in group:
            index.setdefault(w, group)
    groups: list[tuple[tuple[str, str, frozenset], ...]] = []
    used: set[tuple[str, str]] = set()
    for unit in query_units(terms):
        key = (unit[0], unit[1])
        if key in used:
            continue
        used.add(key)
        bundle = [unit]
        own = _syn_key(unit[1]) if index else ""
        for w in sorted(index.get(own, frozenset()) - {own}):
            extra = query_units([w])
            if len(extra) != 1:
                continue  # 2単位以上に割れる語は「どれか1つ」の言い換えにならない
            k = (extra[0][0], extra[0][1])
            if k in used:
                continue
            used.add(k)
            bundle.append(extra[0])
        groups.append(tuple(bundle))
    return groups


def _group_matches(group, feats: set[str]) -> bool:
    """group のどれか1つの語が当たれば True(1語として数える)。"""
    return any(_unit_matches(u, feats) for u in group)


def _units_line(groups) -> str:
    """検索語の行: 正規化後の語を `, ` で連結(同義語は `マージ(=merge)`)。TERMS_SHOWN で切る。"""
    words = [g[0][1] + (f"(={'='.join(u[1] for u in g[1:])})" if len(g) > 1 else "") for g in groups]
    return _trunc(", ".join(words) or "(なし)", TERMS_SHOWN)


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


def _decision_line(d: dict, title: str, kind_label: str = "[D]") -> str:
    """欄はそれぞれ自分の出典からだけ作る(読み替えない)。前の欄と同じ内容は出さない(ウタガイは例外で必ず出す)。700字まで。

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
        if label in _HEADING_LABEL_RE:
            text = _HEADING_LABEL_RE[label].sub("", text).strip()
        if not text:
            continue
        # 前の欄と同じ内容は出さない。ただしウタガイ(反対理由)は重複に見えても必ず出す
        if label != "ウタガイ" and any(text[:80] in s for s in shown):
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
        return f"- {kind_label} {d.get('date') or '????-??-??'} {head_title[0]}" + (" — " + " / ".join(parts) if parts else "") + tail

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


_DECISIONS_CACHE: dict[str, list[dict]] = {}


def _decisions_cached(root: Path) -> list[dict]:
    """load_decisions(root) の1プロセス内 memo([D] と [Wiki] の needs_review 判定が共有)。失敗は memo しない。"""
    key = str(Path(root).resolve())
    if key not in _DECISIONS_CACHE:
        _DECISIONS_CACHE[key] = load_decisions(root)
    return _DECISIONS_CACHE[key]


def _decisions(root: Path) -> list[Source]:
    out = []
    for d in _decisions_cached(root):
        path = d["path"]
        if path.startswith("/") or path.startswith(".."):
            continue  # root の外(シンボリックリンク経由など)は出さない
        if d.get("status") == "superseded":
            continue  # 置き換えられた決定は出さない(後継の議事が出る)
        if any(str(t).strip().lower() == "test" for t in d.get("tags") or []):
            continue  # 試験用の記録は本物の決定として扱わない
        label = _STATUS_LABEL.get(d.get("status") or "", "[D]")
        title = _TITLE_PREFIX_RE.sub("", _clean(d["title"]))
        line = _decision_line(d, title, label)
        out.append(_src("decision", label, path, path, title, line, line, d.get("date") or "",
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


_WIKI_OFF_AUDITED: set[str] = set()


_NEEDS_REVIEW_AUDITED: set[tuple[str, str]] = set()


def _wiki_needs_review(w: dict, decisions: list[dict], synonyms: list[frozenset[str]] | None = None) -> list[str]:
    """承認後の新しい Decision と矛盾する Wiki の Decision id(非空なら注入しない)。

    wiki_schema.needs_review の例外は ["error"](判定できない Wiki は注入しない = fail-closed)。
    """
    try:
        return list(_ws.needs_review(w, decisions, synonyms))
    except Exception:  # noqa: BLE001
        return ["error"]


def _wiki_line(w: dict) -> str:
    def count(key: str) -> int:
        v = w.get(key)
        return len(v) if isinstance(v, list) else 0

    title = _clean(w.get("title") or "")
    summary = _clean(w.get("summary") or "")[:WIKI_SUMMARY_SHOWN]
    return (f"- [Wiki] {title} — {summary} / 根拠: Exp {count('source_experience')}・"
            f"Decision {count('source_decision')}・FK {count('source_failure')} / "
            f"承認: {_clean(w.get('approved_by') or '')} {_clean(w.get('approved_at') or '')} → {w['_path']}")


def _wiki(root: Path) -> list[Source]:
    """docs/wiki/ 直下の approved だけ(visibility がリポの公開性と一致・needs_review でない)。

    needs_review(approved_at より新しい adopted Decision と矛盾・判定の例外を含む)の Wiki は出さず、
    audit に `wiki: needs_review <wiki_id> <decision_id>` を1ページ1プロセスに1回。

    _candidates/ と _archive/ は開かない(iter_wiki の official は直下だけ + `docs/wiki/_` で始まるパスを捨てる)。
    .claude/wiki.off があれば [] (audit は1プロセスに1回)。どんな失敗も [] + audit(fail closed)。
    """
    root = Path(root)
    try:
        if (root / WIKI_OFF_PATH).exists():
            key = str(root.resolve())
            if key not in _WIKI_OFF_AUDITED:
                _WIKI_OFF_AUDITED.add(key)
                audit(root, _COMPONENT, "wiki: disabled by wiki.off")
            return []
        if _ws is None:
            audit(root, _COMPONENT, f"wiki: wiki_schema unavailable ({_WS_ERROR}); [Wiki] skipped")
            return []
        out: list[Source] = []
        visibility = decisions = None
        unreadable = hidden = 0
        for w in _ws.iter_wiki(root, "official"):
            path = str(w.get("_path") or "")
            if (not path.startswith(_ws.WIKI_DIR + "/") or path.startswith(_ws.WIKI_DIR + "/_")
                    or "/" in path[len(_ws.WIKI_DIR) + 1:] or w.get("_place") != "official"):
                continue  # 候補・置き換え済み・root の外は出さない(二重の除外)
            if "_error" in w:
                unreadable += 1
                continue
            if w.get("review_status") != "approved":
                continue
            if visibility is None:
                # root がリポジトリの最上位でなければ(外側のリポの remote を読まないよう)private 扱い
                visibility = _ws.repo_visibility(root) if _git_ready(root) else "private"
            if w.get("visibility") != visibility:
                hidden += 1
                continue
            if decisions is None:
                decisions = _decisions_cached(root)
            review = _wiki_needs_review(w, decisions, _synonyms(root))
            if review:
                wid = _clean(str(w.get("wiki_id") or path))
                key = (str(root.resolve()), wid)
                if key not in _NEEDS_REVIEW_AUDITED:  # 1ページ1プロセスに1回
                    _NEEDS_REVIEW_AUDITED.add(key)
                    audit(root, _COMPONENT, f"wiki: needs_review {wid} {','.join(review)}")
                continue
            title = _clean(w.get("title") or "")
            summary = _clean(w.get("summary") or "")
            sections = w.get("_sections") if isinstance(w.get("_sections"), dict) else {}
            knowledge = _clean(sections.get("## 知識") or "")[:WIKI_KNOWLEDGE_CHARS]
            out.append(_src("wiki", "[Wiki]", str(w.get("wiki_id") or path), path, title, summary, _wiki_line(w),
                            _clean(w.get("approved_at") or ""), f"{title} {summary} {knowledge}", title))
        if unreadable:
            audit(root, _COMPONENT, f"wiki: skipped {unreadable} unreadable page(s)")
        if hidden:
            audit(root, _COMPONENT, f"wiki: hidden {hidden} page(s) whose visibility differs from the repo")
        return out
    except Exception as e:  # noqa: BLE001 — [Wiki] の不具合で他の区分・hook を止めない
        audit(root, _COMPONENT, f"wiki: {type(e).__name__}: {e}")
        return []


_SYN_CACHE: dict[str, tuple[tuple, list[frozenset[str]]]] = {}


def _clear_caches() -> None:
    """1プロセス内の memo(Decision・同義語・Decision 側の矛盾判定 features・audit 1回の記録)を空にする(テスト用)。"""
    _DECISIONS_CACHE.clear()
    _SYN_CACHE.clear()
    _WIKI_OFF_AUDITED.clear()
    _NEEDS_REVIEW_AUDITED.clear()
    if _ws is not None and hasattr(_ws, "_clear_conflict_cache"):
        _ws._clear_conflict_cache()


def _synonyms(root: Path) -> list[frozenset[str]]:
    """同義語表(1プロセス内 memo。表の stat が変われば読み直す)。読めなければ空 + audit。"""
    try:
        if _ws is None:
            return []
        path = Path(root) / _ws.SYNONYMS_PATH
        try:
            st = path.stat()
            stamp = (st.st_mtime_ns, st.st_size)
        except OSError:
            return []
        key = str(Path(root).resolve())
        hit = _SYN_CACHE.get(key)
        if hit and hit[0] == stamp:
            return hit[1]
        _inside(root, path)  # シンボリックリンクで root の外を読まない
        groups = _ws.load_synonyms(Path(root))  # V14 違反の行は load_synonyms が捨てて audit する
        _SYN_CACHE[key] = (stamp, groups)
        return groups
    except Exception as e:  # noqa: BLE001
        audit(root, _COMPONENT, f"synonyms: {type(e).__name__}: {e}; no synonyms")
        return []


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


def _tail_from(fh) -> list[str]:
    """開いたファイルの末尾の完全な行だけを返す(既定 4KB。末尾の行が窓より長く切れていたら 64KB で読み直す)。"""
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


def _tail_lines(path: Path) -> list[str]:
    with open(path, "rb") as fh:
        return _tail_from(fh)


def _read_ends(path: Path, tail: bool = True) -> tuple[str, list[str]]:
    """1回だけ開いて (先頭の1行, 末尾の完全な行) を返す。tail=False なら先頭の1行だけ。"""
    with open(path, "rb") as fh:
        first = fh.readline().decode("utf-8", errors="replace").rstrip("\r\n")
        return first, (_tail_from(fh) if tail else [])


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _ts_of(line: str) -> str:
    """JSONL の1行の ts(読めなければ空文字。並び順にだけ使うので壊れていても数えない)。"""
    try:
        ev = json.loads(line)
    except ValueError:
        return ""
    return str(ev.get("ts") or "") if isinstance(ev, dict) else ""


def _all_events(files: list[Path]) -> list[dict]:
    events = []
    for f in files:
        with open(f, "rb") as fh:
            for raw in fh.read().decode("utf-8", errors="replace").split("\n"):
                if not raw.strip():
                    continue
                try:
                    ev = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(ev, dict):
                    events.append(ev)
    return events


def _current_session(root: Path) -> str:
    """Experience Logger が SessionStart で置く「今のセッション」(自分自身の記録は [Exp] に出さない)。"""
    try:
        return (Path(root) / LOCAL_DIR / "current_session").read_text(encoding="utf-8").strip()[:200]
    except (OSError, ValueError):
        return ""


def _experience(root: Path) -> list[Source]:
    """同じブランチの直近のセッション(public のみ)を新しい順に最大3件。スコアは使わない。

    1セッション = session-<sid>.jsonl + session-<sid>.part<N>.jsonl(番号順)。並び順は各セッションの
    先頭行の ts(更新時刻は checkout で変わるので使わない)。各セッションの最後のファイルの末尾だけを読み、
    最新の session_end があればそれを、無ければ(commit の後に終了したセッション)最新の行を使う。
    今のブランチが決められない(detached HEAD で origin の一致が無い/複数)ときはブランチで絞らない。
    月フォルダを新しい順に見て、3件そろった月より古い月は開かない。開くファイルは合計50まで。
    今のセッション(_local/current_session)は出さない。
    """
    base = Path(root) / EXPERIENCE_DIR
    if not base.is_dir():
        return []
    branch = _branch(root)
    by_branch = branch != "unknown"
    me = _current_session(root)
    months = sorted((d for d in base.iterdir() if d.is_dir() and _MONTH_RE.match(d.name)),
                    key=lambda d: d.name, reverse=True)
    rows = []
    hidden = malformed = scanned = 0
    for month in months:
        if len(rows) >= EXPERIENCE_MAX or scanned >= EXPERIENCE_MAX_FILES:
            break
        groups = group_session_files(month.glob("session-*.jsonl"))
        # どのセッションから開くか(上限50ファイルに収める順)は更新時刻→名前。表示の並びは先頭行の ts
        order = sorted(groups.items(), key=lambda kv: (max(_mtime(p) for p in kv[1]), kv[0]), reverse=True)
        for sid_name, files in order:
            if scanned >= EXPERIENCE_MAX_FILES:
                break
            if me and sid_name == _safe_id(me):
                continue
            try:
                files = [f for f in files if _inside(root, f)]
            except ValueError:
                continue
            if not files:
                continue
            first, tail = _read_ends(files[0], tail=len(files) == 1)
            scanned += 1
            if len(files) > 1:
                _f, tail = _read_ends(files[-1])
                scanned += 1
            end_ev = latest = None
            for raw in reversed(tail):
                if not raw.strip():
                    continue
                try:
                    ev = json.loads(raw)
                except ValueError:
                    ev = None
                if not isinstance(ev, dict):
                    if "session_end" in raw:
                        malformed += 1
                    continue
                if latest is None:
                    latest = ev
                if ev.get("event") == "session_end":
                    end_ev = ev
                    break
            ev = end_ev or latest
            if ev is None:
                continue
            if by_branch and ev.get("branch") != branch:
                continue
            if ev.get("visibility") != "public":
                hidden += 1
                continue
            rows.append((_ts_of(first) or str(ev.get("ts") or ""), ev, end_ev is not None, files))
    if hidden:
        audit(root, _COMPONENT, f"experience: hidden {hidden} private/non-public session row(s) on branch {branch}")
    if malformed:
        audit(root, _COMPONENT, f"experience: skipped {malformed} malformed session_end row(s)")
    rows.sort(key=lambda r: r[0], reverse=True)
    out = []
    for first_ts, ev, ended, files in rows[:EXPERIENCE_MAX]:
        ts = str(ev.get("ts") or first_ts)
        sid = str(ev.get("session_id") or "?")
        date = ts[:10] or "????-??-??"
        if ended:
            commits = ev.get("commits") if isinstance(ev.get("commits"), list) else []
            skills = ev.get("skills") if isinstance(ev.get("skills"), list) else []
            skill_text = ", ".join(str(s) for s in skills) or "-"
            line = f"- [Exp] {date} session-{sid}: commits {len(commits)} / skills: {skill_text}"
        else:
            # session_end が無い(commit・push の後に終了した)セッション: 件数と最新の note だけ
            events = _all_events(files)
            notes = [e for e in events if e.get("event") == "note" and isinstance(e.get("text"), str)]
            line = f"- [Exp] {date} session-{sid}: events {len(events)}"
            if notes:
                line += f" / note: {_clean(notes[-1]['text'])[:NOTE_SHOWN]}"
        rel = files[-1].relative_to(Path(root)).as_posix()
        out.append(_src("experience", "[Exp]", f"exp:{sid}:{ts}", rel, f"session-{sid}", line[2:], line,
                        ts[:10], "", ""))
    return out


COLLECTORS = [
    ("decision", _decisions),
    ("queue", _queue),
    ("failure", _failures),
    ("prevention", _preventions),
    ("wiki", _wiki),
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
    """候補の特徴量(1プロセス内で使い回す)。

    Skill の text は「名前 + 空白 + 説明」なので、名前と説明の特徴量の和集合と等しい(区切りの空白を
    またぐ bigram・英数字の語は無い)。説明だけの特徴量(_body_feats)も使うので、両方を1回ずつ作って合わせる。
    """
    if "_f" not in s:
        s["_tf"] = features(s["match_title"]) if s.get("match_title") else set()
        if s["kind"] == "skill" and s["text"] == f"{s['match_title']} {s['body']}":
            s["_f"] = s["_tf"] | _body_feats(s)
        else:
            s["_f"] = features(s["text"])
    return s["_f"], s["_tf"]


def _body_feats(s: Source) -> set[str]:
    """Skill の説明(名前を除く)の特徴量。名前だけの一致を数えない段1・段2の照合に使う。"""
    if "_bf" not in s:
        s["_bf"] = features(s["body"])
    return s["_bf"]


def _select(sources: list[Source], terms: list[str], per_kind: int = PER_KIND, min_score: int = MIN_SCORE,
            exclude: frozenset | set = frozenset(), name_terms: list[str] | None = None,
            synonyms: list[frozenset[str]] | None = None) -> dict[str, list[Source]]:
    """区分ごとに score 降順 → 日付降順で per_kind 件。exclude の id は順位付けの前に除く。

    照合の単位は query_groups(同義語表の同じ行の語は1語)。区分ごとに、項目の DF_RATIO を超えて
    (かつ DF_MIN_COUNT 件以上に)当たる語はその区分では使わない。見出しの加点は並び順にだけ使い、
    min_score の判定は加点を除いた一致数で行う。Skill の名前(識別子)での一致は例外で1語に数えるが、
    それは name_terms の語が名前に当たったときだけ(None = 全語: 手動 query・retrieve の従来の挙動 /
    [] = 数えない: 段1)。name_terms を渡したときは、name_terms 以外の語の一致は説明の本文だけで見る。
    """
    groups = query_groups(terms, synonyms)
    need = max(min(min_score, len(groups)), 1)
    if name_terms is None:
        name_idx = frozenset(range(len(groups)))
    else:
        name_keys = {(k, w) for k, w, _g in query_units(list(name_terms))}
        name_idx = frozenset(i for i, g in enumerate(groups) if any((u[0], u[1]) in name_keys for u in g))
    picked: dict[str, list[Source]] = {k: [] for k in KIND_ORDER}
    rows: dict[str, list[tuple[Source, frozenset]]] = {k: [] for k in KIND_ORDER}
    for s in sources:
        if s["kind"] == "experience":
            if s["id"] not in exclude:
                picked["experience"].append(s)
            continue
        if not groups:
            continue
        f, _tf = _feats(s)
        if s["kind"] == "skill" and name_terms is not None:
            bf = _body_feats(s)
            matched = frozenset(i for i, g in enumerate(groups)
                                if _group_matches(g, bf) or (i in name_idx and _group_matches(g, f)))
        else:
            matched = frozenset(i for i, g in enumerate(groups) if _group_matches(g, f))
        rows[s["kind"]].append((s, matched))
    for kind, entries in rows.items():
        df: dict[int, int] = {}
        for _s, matched in entries:
            for i in matched:
                df[i] = df.get(i, 0) + 1
        common = {i for i, c in df.items() if c >= DF_MIN_COUNT and c > DF_RATIO * len(entries)}
        for s, matched in entries:
            if s["id"] in exclude:
                continue
            effective = matched - common
            _f, tf = _feats(s)
            titled = effective & name_idx if kind == "skill" else effective
            bonus = 1 if titled and tf and any(_group_matches(groups[i], tf) for i in titled) else 0
            # 見出しの加点は並び順だけ。ただし Skill の名前(識別子)での一致は1語として数える
            # (名前に語がそのまま入っている Skill は、説明に1語しか無くても関連が強い)
            counted = len(effective) + (bonus if kind == "skill" else 0)
            if counted < need:
                continue
            picked[kind].append({**s, "score": len(effective) + bonus})
    for kind in KIND_ORDER:
        if kind == "experience":
            picked[kind] = picked[kind][:EXPERIENCE_MAX]
        else:
            picked[kind] = sorted(picked[kind], key=lambda s: (s["score"], s.get("date") or ""),
                                  reverse=True)[:per_kind]
    return picked


def _render(picked: dict[str, list[Source]], terms_lines: list[str] | None, heading: str,
            budget_chars: int) -> tuple[str, set[str]]:
    """固定形で出力し、(本文, 実際に表示した項目の id) を返す。

    terms_lines は見出しの直後に置く検索語の行(`検索語: …` 等。None なら出さない: 手動 query の語は再掲しない)。
    """
    items = {k: list(picked.get(k, [])) for k in KIND_ORDER}
    trimmed = {k: False for k in KIND_ORDER}

    def build() -> str:
        parts = [heading]
        if terms_lines is not None:
            parts.extend(terms_lines)
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
    """区分ごとに score 降順で per_kind 件(min(min_score, 語の数) 未満は落とす)。合計 budget_chars 以内。

    手動 query 用: Skill の名前一致は従来どおり全語で数える(name_terms=None)。同義語表は使う。
    """
    picked = _select(collect_sources(root), list(terms), per_kind, min_score, synonyms=_synonyms(root))
    return _render(picked, None, STAGE1_HEADING, budget_chars)[0]


# ---------------------------------------------------------------- hook / CLI

def _stage1_render(root: Path, sources: list[Source], terms: list[str]) -> tuple[str | None, set[str]]:
    """段1: ブランチ・commit の語で探す。Skill の名前だけの一致は数えない(name_terms=[])。"""
    synonyms = _synonyms(root)
    picked = _select(sources, terms, name_terms=[], synonyms=synonyms)
    if not any(picked.values()):
        return None, set()
    return _render(picked, ["検索語: " + _units_line(query_groups(terms, synonyms))], STAGE1_HEADING, BUDGET_CHARS)


def _stage1(root: Path) -> str | None:
    return _stage1_render(root, collect_sources(root), build_query(root))[0]


def _stage2(root: Path, prompt: str) -> str | None:
    """最初の指示 + ブランチ名の語。指示から語が2つ取れなければ、段1の検索語 + 指示。

    段1で実際に表示した項目は順位付けの前に除く。新しい項目が無ければ None。
    """
    stage1_terms = build_query(root)
    sources = collect_sources(root)
    _text, shown = _stage1_render(root, sources, stage1_terms)
    prompt = str(prompt or "").strip()[:PROMPT_MAX]
    prompt_terms = [prompt] if len(prompt) >= 2 else []
    if len(query_units(prompt_terms)) >= 2:
        context_terms = branch_terms(root)
        terms = prompt_terms + [t for t in context_terms if t not in prompt_terms]
    else:
        context_terms = stage1_terms
        terms = stage1_terms + [t for t in prompt_terms if t not in stage1_terms]
    synonyms = _synonyms(root)
    # Skill の名前一致は、最初の指示の語が名前に当たったときだけ1語に数える
    picked = _select(sources, terms, exclude=shown, name_terms=prompt_terms, synonyms=synonyms)
    if not any(picked.values()):
        return None
    # 指示の本文は出力に再掲しない(検索に使った語だけを出す)
    prompt_groups = query_groups(prompt_terms, synonyms)
    seen = {(u[0], u[1]) for g in prompt_groups for u in g}
    context_groups = [g for g in query_groups(context_terms, synonyms) if (g[0][0], g[0][1]) not in seen]
    lines = ["検索語(指示から): " + _units_line(prompt_groups),
             "検索語(ブランチから): " + _units_line(context_groups)]
    return _render(picked, lines, STAGE2_HEADING, BUDGET_CHARS)[0]


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
