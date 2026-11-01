"""PR-B B1: 汎用化した 3 スキルが公開リポジトリに置ける内容だけで構成されていることの機械検査。

対象: slide-deck-hojo / user-research-hojo(+ tests.md)/ figma-use-hojo。
禁止語(check_repo_scope.FORBIDDEN_CONTENT)が無いこと、存在しない参照先、未来日付の「実績」を機械で止める。
非公開側を推測させる語の照合は、公開リポジトリに語の一覧(平文・ハッシュを問わず)を置かないため、このファイルには含めない。
人の全文目視(完了条件 ②)の代わりではなく、その前段の網。禁止語の実文字列はこのファイルに書かない。
"""
import datetime as dt
import re
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from check_repo_scope import FORBIDDEN_CONTENT  # noqa: E402

SKILLS = ["slide-deck-hojo", "user-research-hojo", "figma-use-hojo"]
FILES = [ROOT / ".claude" / "skills" / s / "SKILL.md" for s in SKILLS] + [
    ROOT / ".claude" / "skills" / "user-research-hojo" / "tests.md",
]
BUSINESSES = ("ミカタ", "もらいわすれ堂", "GLOW")


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _frontmatter(text: str) -> dict:
    lines = text.split("\n")
    assert lines[0].strip() == "---", "frontmatter が無い"
    end = next(i for i, l in enumerate(lines[1:], start=1) if l.strip() == "---")
    fm = {}
    for l in lines[1:end]:
        m = re.match(r"^(\w+)\s*:\s*(.*)$", l)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm


@pytest.mark.parametrize("path", FILES, ids=[f"{p.parent.name}/{p.name}" for p in FILES])
def test_no_forbidden_word_in_any_spelling(path):
    folded = _fold(path.read_text(encoding="utf-8"))
    found = [i for i, w in enumerate(FORBIDDEN_CONTENT) if w and w.casefold() in folded]
    assert found == [], f"禁止語が残っている: FORBIDDEN_CONTENT{found}"


@pytest.mark.parametrize("skill", SKILLS)
def test_description_is_public_and_names_the_businesses(skill):
    fm = _frontmatter((ROOT / ".claude" / "skills" / skill / "SKILL.md").read_text(encoding="utf-8"))
    desc = fm.get("description", "")
    assert fm.get("name") == skill
    assert 40 <= len(desc) <= 400, len(desc)
    assert any(b in desc for b in BUSINESSES), "description に ミカタ / もらいわすれ堂 / GLOW のいずれも無い"
    folded = _fold(desc)
    assert not any(w.casefold() in folded for w in FORBIDDEN_CONTENT if w)


@pytest.mark.parametrize("path", FILES, ids=[f"{p.parent.name}/{p.name}" for p in FILES])
def test_referenced_repo_paths_exist(path):
    """本文が案内する docs/… .md・scripts/… .py・site/… .html・画像は実在する(再発防止メモ: 参照先の実在確認)。"""
    text = path.read_text(encoding="utf-8")
    refs = set(re.findall(r"(?<![\w/])((?:docs|scripts|site|tests|reports|data)/[^\s`'\")\]　-〿]+?\.(?:md|py|html|json|yml|sh|css|js|png|jpg|jpeg|svg|webp))", text))
    missing = sorted(r for r in refs if not (ROOT / r).exists())
    assert missing == [], f"存在しない参照先: {missing}"


@pytest.mark.parametrize("path", FILES, ids=[f"{p.parent.name}/{p.name}" for p in FILES])
def test_referenced_skills_exist(path):
    """`xxx-hojo` などスキル名として書かれた参照は .claude/skills/ に実在する。"""
    text = path.read_text(encoding="utf-8")
    names = set(re.findall(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`", text))
    existing = {p.name for p in (ROOT / ".claude" / "skills").iterdir() if (p / "SKILL.md").exists()}
    # スキル名らしいもの: 実在する / -hojo で終わる / 実在スキル名の前後を欠いた形(例: `lighthouse-triage`)
    skill_like = {
        n for n in names
        if n in existing or n.endswith("-hojo")
        or any(e != n and (e.endswith("-" + n) or e.startswith(n + "-")) for e in existing)
    }
    missing = sorted(n for n in skill_like if n not in existing)
    assert missing == [], f"存在しないスキルへの参照(実在スキル名の一部だけを書いていないか): {missing}"


@pytest.mark.parametrize("path", FILES, ids=[f"{p.parent.name}/{p.name}" for p in FILES])
def test_no_future_dated_achievements(path):
    """未来の日付に「完了・達成・実績・効果」を書いていない(架空の実績を残さない)。"""
    today = dt.date.today()
    text = path.read_text(encoding="utf-8")
    bad = []
    for m in re.finditer(r"(20\d{2})[-/年](\d{1,2})(?:[-/月](\d{1,2}))?", text):
        y, mo = int(m.group(1)), int(m.group(2))
        d = int(m.group(3) or 1)
        try:
            when = dt.date(y, mo, min(d, 28))
        except ValueError:
            continue
        if when <= today:
            continue
        window = text[max(0, m.start() - 40): m.end() + 40]
        if re.search(r"完了|(?<!未)達成|実績|効果|成功|削減|向上|改善した", window):
            bad.append(window.replace("\n", " "))
    assert bad == [], f"未来日付の実績らしき記述: {bad[:3]}"


def test_check_repo_scope_no_longer_flags_the_three():
    from check_repo_scope import find_content_violations
    flagged = []
    for p in FILES:
        rel = str(p.relative_to(ROOT))
        if find_content_violations(rel, p.read_text(encoding="utf-8")):
            flagged.append(rel)
    assert flagged == [], flagged
