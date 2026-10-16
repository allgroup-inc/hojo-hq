"""PR-B B2: design-system-hojo の公開安全性是正の検査。

公開情報だけで書く。非公開の語・識別子・社内の色値・社内の名称は、このファイルに一切置かない。
禁止語は check_repo_scope.FORBIDDEN_CONTENT(公開の一覧)だけを使う。
構造の検査は、削除したブロックが別名で戻ってきていないことも確認する(社内向けの見出し・色・語の再混入)。
"""
import datetime as dt
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from check_repo_scope import FORBIDDEN_CONTENT, find_content_violations  # noqa: E402

REL = ".claude/skills/design-system-hojo/SKILL.md"
SKILL = ROOT / REL
REFERRERS = [
    ".claude/skills/figma-use-hojo/SKILL.md",
    ".claude/skills/slide-deck-hojo/SKILL.md",
    ".claude/skills/user-research-hojo/SKILL.md",
    ".claude/skills/writing-plans-hojo/SKILL.md",
]
BUSINESSES = ("ミカタ", "もらいわすれ堂")

# 公開済みのブランド色の値(事業 A・B のみ)。この集合と完全に一致することを確認する。
# 色値は公開の配色であり、機密ではない。社内の色値は含めない。
BRAND_VALUES = {
    "00335C", "F88800", "002240", "F5F8FB", "E07600", "FFF5E6",
    "333333", "DDDDDD", "FFFFFF", "FF6B6B", "51CF66", "4C6EF5",
    "B9502F", "A03D1A", "FFF0E6", "F2B705", "D99B00", "FFF8E6",
    "FFFBF4", "1F2A2E", "E0D5C7", "E63946", "6AB04C", "7209B7",
}


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _description(text: str) -> str:
    m = re.search(r'^description:\s*"(.*)"\s*$', text, re.M)
    assert m, "description が frontmatter に無い"
    return m.group(1)


def _h3_lines(text: str) -> list:
    return [line for line in text.split("\n") if line.startswith("### ")]


def test_no_forbidden_word_in_any_spelling():
    folded = _fold(_text())
    found = [i for i, w in enumerate(FORBIDDEN_CONTENT) if w and w.casefold() in folded]
    assert found == [], f"禁止語が残っている: FORBIDDEN_CONTENT{found}"


def test_repo_scope_does_not_flag_the_skill():
    assert not find_content_violations(REL, _text()), "repo-scope の本文検査に当たる"


def test_description_meets_design_constraints():
    desc = _description(_text())
    assert 40 <= len(desc) <= 160, f"description の長さ: {len(desc)}(40〜160 字。160 字は注入の上限)"
    assert all(b in desc for b in BUSINESSES), "description に事業名 2 件が揃っていない"
    assert not any(w.casefold() in _fold(desc) for w in FORBIDDEN_CONTENT if w)


def test_business_sections_present_and_internal_block_absent():
    text = _text()
    assert "### **事業 A" in text, "事業 A の見出しが無い"
    assert "### **事業 B" in text, "事業 B の見出しが無い"
    assert "事業 C" not in text, "削除した事業ブロックの見出しが残っている(別名での再導入を含む)"


def test_palette_headings_are_exactly_the_two_brands():
    headings = [h for h in _h3_lines(_text()) if "カラーパレット" in h]
    assert len(headings) == 2, f"パレットの見出し(###)は 2 件のはず: {len(headings)}"
    assert all(any(b in h for b in BUSINESSES) for h in headings), "パレット見出しが事業名と対応していない"


def test_color_values_are_exactly_the_public_brand_values():
    found = {m.upper() for m in re.findall(r"#([0-9A-Fa-f]{6})\b", _text())}
    # 失敗メッセージに色値を出さない(社内の値が CI ログに出ないように、件数だけを書く)
    assert found == BRAND_VALUES, (
        f"色値が公開の集合と一致しない。余分: {len(found - BRAND_VALUES)} 件 / 欠落: {len(BRAND_VALUES - found)} 件"
    )


def test_this_test_file_contains_only_public_colour_values():
    """テスト自身に、公開値以外の色値を書いていない(自己点検)。"""
    own = {m.upper() for m in re.findall(r"\b([0-9A-Fa-f]{6})\b", Path(__file__).read_text(encoding="utf-8"))}
    assert own <= BRAND_VALUES | {"FFFFFF"}, f"テストに公開値以外の色値らしき語がある: {len(own - BRAND_VALUES)} 件"


def test_internal_naming_is_not_reintroduced():
    """社内向けの語が、削除前の位置以外に戻っていない(件数で確認し、語は書かない)。"""
    text = _text()
    assert text.count("社内") == 2, f"「社内」の出現は 2 件(一般化した 2 行)のはず: {text.count('社内')}"


def test_referral_example_is_generic():
    text = _text()
    for word in ("会計士", "税理士"):
        assert word not in text, f"紹介元の職業例が具体名のまま残っている: {word}"
    assert "支援者" in text, "紹介元の例が一般表現に置き換わっていない"


def test_structure_sections_are_kept():
    text = _text()
    assert len(re.findall(r"^## Stage \d+:", text, re.M)) == 5, "Stage の節が 5 つ無い"
    for heading in ("## 注意点", "## 関連スキル"):
        assert text.count(heading) == 1, f"{heading} が 1 つ無い"


def test_no_doubled_divider():
    lines = _text().split("\n")
    dividers = [i for i, l in enumerate(lines) if l.strip() == "---"]
    for a, b in zip(dividers, dividers[1:]):
        between = lines[a + 1:b]
        assert any(l.strip() for l in between), f"区切り線が二重になっている(行 {a + 1} と {b + 1})"


def test_code_fences_are_balanced():
    fences = [l for l in _text().split("\n") if l.lstrip().startswith("```")]
    assert len(fences) % 2 == 0, "コードフェンスが閉じていない"


def test_no_empty_h3_section():
    lines = _text().split("\n")
    for i, line in enumerate(lines):
        if not line.startswith("### "):
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        assert j < len(lines) and not lines[j].startswith("#"), f"空の見出し: 行 {i + 1}"


def test_no_private_repository_shape():
    """非公開リポジトリ名の型(英数字とハイフンの組み)を、名前を書かずに確認する。"""
    text = _text()
    assert not re.search(r"[a-z0-9]+-private\b", text), "非公開リポジトリ名の型が残っている"


def test_referring_skills_still_point_to_brands_only():
    for rel in REFERRERS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "design-system-hojo" in text, f"{rel} が本 Skill を参照していない"


def test_referenced_repo_paths_exist():
    text = _text()
    refs = set(re.findall(r"(?<![\w/])((?:docs|scripts|site|tests|reports|data)/[^\s`'\")\]　-〿]+?\.(?:md|py|html|json|yml|sh|css|js|png|jpg|jpeg|svg|webp))", text))
    missing = sorted(r for r in refs if not (ROOT / r).exists())
    assert missing == [], f"存在しない参照先: {len(missing)} 件"


def test_referenced_skills_exist():
    text = _text()
    names = set(re.findall(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`", text))
    existing = {p.name for p in (ROOT / ".claude" / "skills").iterdir() if (p / "SKILL.md").exists()}
    skill_like = {
        n for n in names
        if n in existing or n.endswith("-hojo")
        or any(e != n and (e.endswith("-" + n) or e.startswith(n + "-")) for e in existing)
    }
    missing = sorted(n for n in skill_like if n not in existing)
    assert missing == [], f"存在しないスキルへの参照: {len(missing)} 件"


def test_no_future_dated_achievements():
    today = dt.date.today()
    text = _text()
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
    assert bad == [], f"未来日付の実績らしき記述: {len(bad)} 件"
