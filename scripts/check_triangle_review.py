#!/usr/bin/env python3
"""三名体制の議事がgitに保存されているかを検査する(失敗台帳 FK-005 の対策)。

背景:
    CLAUDE.md 三名体制運営規程3 は「ウタガイ役の反対理由が記録されていない議事は無効」
    と定める。2026-08-17の点検で、規程が破られた形は「議事を省略した」ではなく
    「議事は行ったが、消える場所に置いた」だと判明した。実例:

        議事詳細(3役の議論・ウタガイの反対理由)は本セッションの会話記録を参照。

    会話記録はコンテキスト上限で消える。設計書には裁定だけが残り、ウタガイが実際に
    何に反対したのかを後から検証できない。これは context-limit-handoff スキルが
    禁じている「作業状態を会話に置く」そのもの。

検査の範囲(2026-08-17 小柳さん決裁と整合):
    議事が必須なのは①小柳さん決裁が要る事項 ②不可逆な変更 の2類型のみ。よってこの検査は
    「三名体制レビューを実施したと本文で述べている文書」だけを対象にし、可逆な技術作業の
    設計書に議事を要求しない。**やったと言っているのに議事が無い**状態だけを落とす。

正しい保存の型(いずれか):
    A. ペアの議事ファイル `<同名>-triangle-review.md` を置く
    B. 本文から、実在する `*-triangle-review.md` のパスを参照する
    C. 設計書の本文に3役の議論をそのまま残す(ウタガイの反対理由の中身を含むこと)
       軽量版(3役×各1行)でも有効

禁止:
    「会話記録を参照」型。議事の所在が git の外にある時点で、無いのと同じ。

KNOWN_GAPS は2026-08-17時点の既知の未記録。遡って議事を作ると「結論を知った上での
後付けウタガイ」になり規程の趣旨を損なうため、事実として残したうえで許容する。
**このリストに行を足すことは再発を意味する。足す前に失敗台帳に記録すること。**
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "docs" / "superpowers" / "specs"

ROLES = ("スイシン", "ウタガイ", "ベッカイ")
# 議事の所在を会話に置いてしまっている書き方。「議事」と近接している場合のみ該当とする
# (単に会話記録という語が出てくるだけの文書を誤検知しないため)
VOLATILE = re.compile(r"議事[^\n]{0,40}(会話記録|本セッションの記録|チャット履歴)")
# ウタガイの反対理由が「中身つきで」残っているとみなす最小の長さ
UTAGAI_MIN_CHARS = 40

KNOWN_GAPS = {
    # 2026-08-17 点検で検出。台帳 FK-005。
    "2026-07-26-shindan-apply-guidance-brushup-design.md": "議事の保存先なし(規程運用の初期)",
    "2026-08-09-glow-ma-partner-development-design.md": "裁定1〜4のみ転記・議事本体なし",
    "2026-08-09-glow-ma-partner-pipeline-view-design.md": "上流設計書の裁定を参照するのみ",
    "2026-08-09-glow-ma-admin-webapp-phase18a-design.md": "議事を会話記録に委ねた",
    "2026-08-10-glow-ma-phase18b-company-memo-edit-design.md": "議事を会話記録に委ねた",
    "2026-08-11-glow-ma-pre-screening-score-import-design.md": "議事を会話記録に委ねた",
    "2026-08-13-glow-ma-admin-console-v2-design.md": "決定事項のみ転記・議事本体なし",
    # 2026-08-20 main取り込み時に検出(家計のポっチャットの設計書)。当該チャットへ
    # 議事の保存を依頼するまでの暫定。解消したらこの行を消すこと。
    "2026-08-14-apo-kanri-v2-ui-design.md": "他チャットの設計書・議事の所在が未確認",
}


def section_body(text, role):
    """見出し `### <role>` の直後の本文を返す。見出しが無ければ None。"""
    m = re.search(rf"^#+\s*{role}.*$", text, re.MULTILINE)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^#+\s", rest, re.MULTILINE)
    return (rest[: nxt.start()] if nxt else rest).strip()


def has_inline_minutes(text):
    """設計書の本文に3役の議論がそのまま残っているか(型C)。"""
    if not all(r in text for r in ROLES):
        return False
    body = section_body(text, "ウタガイ")
    if body is None:
        # 見出し形式でなくても、ウタガイの指摘内容が地の文にあれば可とする
        m = re.search(r"ウタガイ[^\n]{%d,}" % UTAGAI_MIN_CHARS, text)
        return bool(m)
    return len(body) >= UTAGAI_MIN_CHARS


def has_pair_file(path):
    """型A: `<同名>-triangle-review.md` が隣にあるか。"""
    stem = path.stem
    base = stem[: -len("-design")] if stem.endswith("-design") else stem
    return path.with_name(f"{base}-triangle-review.md").exists()


def has_path_reference(text):
    """型B: 実在する `*-triangle-review.md` へのパス参照があるか。"""
    for ref in re.findall(r"[\w./-]*[\w-]+-triangle-review\.md", text):
        if (ROOT / ref.lstrip("./")).exists() or (SPEC_DIR / Path(ref).name).exists():
            return True
    return False


# 2026-08-17の点検でこの検査自身が付けた注記ブロック。これ自体が「三名体制」の語を
# 含むため、除外しないと注記を付けたこと自体が検出対象になる(自己言及の誤検知)。
ANNOTATION = "> **三名体制の議事について(2026-08-17 点検で追記)**"


def audit(path):
    """問題があれば理由の文字列、無ければ None を返す。"""
    text = path.read_text(encoding="utf-8")
    if ANNOTATION in text:
        text = text[: text.index(ANNOTATION)]

    if path.stem.endswith("-triangle-review"):
        missing = [r for r in ROLES if r not in text]
        if missing:
            return f"議事ファイルなのに3役が不足: {'/'.join(missing)}"
        body = section_body(text, "ウタガイ")
        if body is not None and len(body) < UTAGAI_MIN_CHARS:
            return "ウタガイ節が実質空(反対理由が書かれていない)"
        return None

    if "三名体制" not in text:
        # 議事が必須なのは①小柳さん決裁事項 ②不可逆な変更 の2類型のみ
        # (2026-08-17 小柳さん決裁・CLAUDE.md 三名体制 第8項)。
        # 可逆な技術作業まで一律に要求すると決裁に反して速度を落とすため、
        # レビューに言及していない設計書はこの検査の対象外とする。
        return None

    # 揮発参照は最優先でNG。他に参照があっても、議事本体が会話にある時点で検証できない
    if VOLATILE.search(text):
        return "議事の所在を会話記録に置いている(会話は消える。gitに保存すること)"
    if has_pair_file(path) or has_path_reference(text) or has_inline_minutes(text):
        return None
    return "三名体制レビューに言及しているが、議事本体がgit内に見つからない"


def main():
    if not SPEC_DIR.is_dir():
        print(f"NG: {SPEC_DIR} が見つかりません")
        return 1

    violations, allowed, checked = [], [], 0
    for path in sorted(SPEC_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if not (
            "三名体制" in text
            or path.stem.endswith("-triangle-review")
            or path.stem.endswith("-design")
        ):
            continue
        checked += 1
        problem = audit(path)
        if problem is None:
            continue
        if path.name in KNOWN_GAPS:
            allowed.append(f"  - {path.name}: {KNOWN_GAPS[path.name]} [既知・台帳FK-005]")
        else:
            violations.append(f"  - {path.name}: {problem}")

    print(f"検査対象: {checked}本(三名体制に言及する設計書 + 議事ファイル)")
    if allowed:
        print(f"既知の未記録(台帳管理下・許容): {len(allowed)}件")
        for line in allowed:
            print(line)

    if violations:
        print(f"\nNG: 議事がgitに保存されていないものが {len(violations)}件")
        for line in violations:
            print(line)
        print(
            "\n規程3: ウタガイ役の反対理由が記録されていない議事は無効(結論ごと差し戻し)。\n"
            "裁定だけの転記や「会話記録を参照」は不可。次のいずれかで保存すること:\n"
            "  A. ペアの `<同名>-triangle-review.md` を置く\n"
            "  B. 実在する `*-triangle-review.md` のパスを本文から参照する\n"
            "  C. 設計書の本文に3役をそのまま残す(軽量版=3役×各1行でも可)\n"
            "参照: .claude/skills/hojo-triangle-review / docs/失敗台帳.md FK-005"
        )
        return 1

    print("OK: 議事の保存漏れはありません")
    return 0


if __name__ == "__main__":
    sys.exit(main())
