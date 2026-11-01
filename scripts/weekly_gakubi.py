#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
週次「学び」ダイジェスト: 直近7日の docs/ と reports/ の変更を Claude で要約し、
docs/学び/学び_YYYY-Www.md に1本書き出す(2026-09-21 導入)。

背景: 「Claude Codeでの学び・決定事項を常にObsidianに溜め続けたい」(2026-08-28 小柳さん)。
Obsidian(allgroup-inc/obsidian-vault)へは、整理担当セッションが作った毎朝6時の全文同期
(docs/Obsidian連携ガイド.md)が docs/** をそのまま写すので、本スクリプトは vault に直接
書かず、このリポジトリの docs/学び/ に置くだけでよい(同期がObsidianへ運ぶ)。
→ 他セッションの仕組みと二重にならず、トークンも不要。

壊れにくい設計(resilient-agent-design):
- べき等: ISO週ごとの固定ファイル名。既にあれば書かない(再実行で増殖しない)
- リトライ: Claude API は SDK の max_retries、モデル改名は候補リストで追従
- 失敗の可視化: API失敗は握りつぶさず非ゼロ終了 → ワークフローが Issue を起票
- 個人情報: 公開リポジトリに置くため、プロンプトで氏名・連絡先の記載を禁止し件数に丸める
- 禁止語ガード(2026-10-12 PR-A / 決裁キュー #22): 材料(コミット件名・差分・週次レポ)の禁止語
  (check_repo_scope.FORBIDDEN_CONTENT)を [非公開名称] にマスクしてから要約し、生成文に
  禁止語が残っていれば書かない・dry-run でも表示しない・非ゼロ終了(fail-closed)。
  ログには禁止語の番号と位置だけを出す。2026-10-06 に学び W41 が禁止語を含んだまま main へ
  直 push され、repo-scope の赤 9 件のうち 1 件になった再発防止

使い方:
  python scripts/weekly_gakubi.py            # docs/学び/学び_YYYY-Www.md を生成
  python scripts/weekly_gakubi.py --dry-run  # 生成して検査するがファイルは書かない。ログにはメタデータ行(+同内容の ::notice::)のみ。本文は出さない
  python scripts/weekly_gakubi.py --self-test
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_repo_scope import FORBIDDEN_CONTENT  # noqa: E402  (禁止語の正本。ここに実文字列は書かない)

JST = timezone(timedelta(hours=9))
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MASK = "[非公開名称]"
OUT_DIR = os.path.join(REPO_ROOT, "docs", "学び")
MODEL_CANDIDATES = [
    os.environ.get("GAKUBI_MODEL", "claude-sonnet-5"),
    "claude-haiku-4-5",
]
MAX_PROMPT_CHARS = 40_000
WATCH_PATHS = ["docs", "reports", "CLAUDE.md", ".claude/skills/README.md"]


def _squash(text):
    """NFKC → casefold → 書式文字(ゼロ幅・ソフトハイフン等)と空白類を除去(wiki_schema.strip_invisible と同じ規則)。"""
    s = unicodedata.normalize("NFKC", str(text)).casefold()
    return "".join(ch for ch in s if ch != "\u00ad" and not unicodedata.category(ch).startswith(("Cf", "Z")))


def _loose_pattern(word):
    """禁止語 1 語を、大小・半角全角の揺れごと拾う正規表現。文全体を正規化せずに済ませるため(①→1 等の副作用を避ける)。"""
    parts = []
    for ch in unicodedata.normalize("NFKC", word):
        alts = {ch, ch.upper(), ch.lower()}
        if 0x21 <= ord(ch) <= 0x7E:  # ASCII の印字文字には全角形(U+FF01〜FF5E)がある
            alts |= {chr(ord(a) + 0xFEE0) for a in list(alts)}
        parts.append("[" + "".join(re.escape(a) for a in sorted(alts)) + "]")
    return "".join(parts)


_LOOSE_PATTERNS = [re.compile(_loose_pattern(w)) for w in FORBIDDEN_CONTENT if w]


def mask_forbidden(text):
    """材料から禁止語を消す(大小・半角全角の揺れも対象)。

    変えるのは禁止語の部分(→ MASK)と、語を分断して隠すのに使えるゼロ幅・ソフトハイフン等の書式文字の除去だけ。
    それ以外の文字(丸数字・全角括弧など)は正規化しない。
    """
    t = "".join(ch for ch in str(text) if ch != "\u00ad" and unicodedata.category(ch) != "Cf")
    for pat in _LOOSE_PATTERNS:
        t = pat.sub(MASK, t)
    return t


def find_forbidden(text):
    """生成文に禁止語が残っていれば (FORBIDDEN_CONTENT の番号, 文字位置, 検査名)。無ければ None。

    原文 → NFKC → NFKC+casefold → 書式文字・空白を除いた形、の順に見る(wiki_validate の V06 と同じ考え方)。
    文字位置は「検査名」の形に直した文の中の位置(空白・書式文字を除いた形では原文より手前にずれる。ログの手がかり用)。
    """
    text = str(text)
    nfkc = unicodedata.normalize("NFKC", text)
    variants = (
        ("raw", text, lambda w: w),
        ("nfkc", nfkc, lambda w: unicodedata.normalize("NFKC", w)),
        ("casefold", nfkc.casefold(), lambda w: unicodedata.normalize("NFKC", w).casefold()),
        ("squashed", _squash(text), _squash),
    )
    for how, hay, needle_of in variants:
        for i, word in enumerate(FORBIDDEN_CONTENT):
            needle = needle_of(word)
            if not needle:
                continue
            pos = hay.find(needle)
            if pos >= 0:
                return i, pos, how
    return None


def run_git(args):
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout


def collect_changes(days=7):
    """直近N日の変更を「人が読む要約の材料」として集める(自分の生成物は除く)。"""
    since = f"{days}.days"
    log = run_git(
        ["log", f"--since={since}", "--pretty=format:%h %ad %s", "--date=short",
         "--", *WATCH_PATHS, f":(exclude){os.path.relpath(OUT_DIR, REPO_ROOT)}"]
    ).strip()
    files = run_git(
        ["log", f"--since={since}", "--name-only", "--pretty=format:", "--", *WATCH_PATHS]
    )
    changed = sorted({f for f in files.splitlines() if f.strip() and not f.startswith("docs/学び/")})
    queue_diff = ""
    try:  # 決裁キューは「何が決まったか」が最も濃いので差分本文も渡す
        queue_diff = run_git(
            ["log", f"--since={since}", "-p", "--pretty=format:%s", "--", "docs/決裁キュー.md"]
        )
    except subprocess.CalledProcessError:
        pass
    latest_report = ""
    rp = os.path.join(REPO_ROOT, "reports", "hojo-mikata", "latest.md")
    if os.path.exists(rp):
        with open(rp, encoding="utf-8") as f:
            latest_report = f.read()
    return {
        "log": log,
        "changed_files": changed,
        "queue_diff": queue_diff[:15_000],
        "latest_report": latest_report[:4_000],
    }


def build_prompt(changes, week_label):
    body = (
        "あなたはALLGROUP(沖縄企業のミカタ/GLOW/家計の見直しやさん等)の運営を手伝うClaude Codeです。\n"
        "以下は hojo-hq リポジトリの直近7日間の変更です。経営者の「第二の脳」(Obsidian)に残す\n"
        "週次の学びノートを日本語で書いてください。\n\n"
        "ルール:\n"
        "- 箇条書き5〜10行。1行は80字以内。長文にしない\n"
        "- 「何が決まったか」「何を学んだか(再発防止・気づき)」「次に効きそうなこと」の順\n"
        "- 事実だけを書く。変更に無いことを推測で足さない。数字は出典(週次レポ等)を添える\n"
        "- 顧客の氏名・連絡先など個人情報は書かない(件数・割合に丸める)。公開リポジトリに置かれる\n"
        "- 大きな進展が無ければ「今週は大きな進展なし」+気づき1〜2行だけにする\n"
        "- 見出しは付けず本文の箇条書きのみ(見出しはこちらで付けます)\n"
        f"- 材料中の「{MASK}」は非公開の名称を伏せた印です。元の名称を推測して書かず、必要なら「非公開側」と書く\n\n"
        f"## 対象週\n{week_label}\n\n"
        f"## コミットログ\n{changes['log'] or '(なし)'}\n\n"
        "## 変更ファイル\n" + ("\n".join(changes["changed_files"]) or "(なし)") + "\n\n"
        f"## 決裁キューの差分\n{changes['queue_diff'] or '(変更なし)'}\n\n"
        f"## 最新の週次レポート\n{changes['latest_report'] or '(なし)'}\n"
    )
    # 材料(件名・ファイル名・差分・週次レポ)に混ざった禁止語は、モデルに渡す前にここで一括マスクする
    return mask_forbidden(body)[:MAX_PROMPT_CHARS]


def summarize(prompt):
    import anthropic  # ワークフローで pip install anthropic 済み

    client = anthropic.Anthropic(max_retries=3)
    last_err = None
    for model in MODEL_CANDIDATES:
        try:
            resp = client.messages.create(
                # 2026-09-21初回本番実行で1200だと本文が文の途中でmax_tokens切れし、
                # 気づかず途中欠けのままファイルへ書かれた(#255直後の実行で発覚)。
                # stop_reasonチェックと合わせて、切れたら書かず失敗扱いにする。
                model=model, max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            if resp.stop_reason == "max_tokens":
                last_err = RuntimeError(
                    f"{model}: max_tokensで本文が途中で切れた(stop_reason=max_tokens)"
                )
                continue
            if text.strip():
                return text.strip(), model
        except anthropic.NotFoundError as e:  # モデル改名・廃止 → 次候補
            last_err = e
    raise RuntimeError(f"要約に失敗(全モデル候補で失敗): {last_err}")


def week_label(now=None):
    now = now or datetime.now(JST)
    iso_year, iso_week, _ = now.isocalendar()
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)
    return f"{iso_year}-W{iso_week:02d}", f"{monday:%Y-%m-%d}〜{sunday:%Y-%m-%d}"


def render_note(label, span, body, model):
    return (
        f"# 学び・決定事項まとめ {label}({span})\n\n"
        f"{body}\n\n"
        f"※ GitHub Actions(weekly-gakubi)が自動生成。モデル: {model}。"
        f"元データ: docs/・reports/ の直近7日間の変更。翌朝6時の同期でObsidianにも写る。\n"
    )


def dry_run_summary(note, path, model):
    """dry-run で公開 Actions ログに出してよいメタデータだけを 1 行にする(本文・断片は含めない)。

    2026-10-12 小柳さん方針(案 A): push 起動の dry-run は合格した本文を公開ログに出さない。
    行数・文字数・sha256(先頭 12 桁)・モデル・[非公開名称] の残存数だけを出す。本文を表示する
    切替(opt-in)は持たない(将来の設定ミスによる再露出経路を作らない)。
    """
    digest = hashlib.sha256(note.encode("utf-8")).hexdigest()[:12]
    return (
        f"dry-run OK: {os.path.basename(path)} lines={len(note.splitlines())} chars={len(note)} "
        f"sha256={digest} model={model} guard=PASS mask_marks={note.count(MASK)}"
    )


def out_path(label):
    return os.path.join(OUT_DIR, f"学び_{label}.md")


def self_test():
    label, span = week_label(datetime(2026, 9, 21, 10, 0, tzinfo=JST))
    assert label == "2026-W39", label
    assert span.startswith("2026-09-21"), span
    p = build_prompt(
        {"log": "abc 2026-09-20 docs: x", "changed_files": ["docs/a.md"], "queue_diff": "", "latest_report": ""},
        label,
    )
    assert "docs/a.md" in p and len(p) <= MAX_PROMPT_CHARS
    note = render_note(label, span, "- テスト", "test-model")
    assert note.startswith("# 学び・決定事項まとめ 2026-W39")
    assert out_path(label).endswith("docs/学び/学び_2026-W39.md")
    # 禁止語ガード: 正例(通る)と負例(止まる)を、実文字列を書かずに check_repo_scope から取って試す
    word = FORBIDDEN_CONTENT[0]
    assert find_forbidden("今週は大きな進展なし。制度 143 件。") is None
    assert find_forbidden(p) is None, "プロンプトの定型文に禁止語が混ざっている"
    for bad in (word, word.upper(), word[:2] + "\u200b" + word[2:], word[:3] + "\u00ad" + word[3:]):
        hit = find_forbidden(f"- 決定: {bad} を移設")
        assert hit is not None and hit[0] == 0, hit
    masked = mask_forbidden(f"abc 2026-10-05 docs: {word.lower()} / {word.upper()} の是正")
    assert MASK in masked and find_forbidden(masked) is None
    assert find_forbidden(build_prompt({"log": f"x {word}", "changed_files": [], "queue_diff": "", "latest_report": ""}, label)) is None
    print("self-test OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    label, span = week_label()
    path = out_path(label)
    if os.path.exists(path) and not args.dry_run:
        print(f"skip: {os.path.basename(path)} は既に存在(べき等)")
        return 0
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("::warning::ANTHROPIC_API_KEY 未設定のため要約をスキップ")
        return 0
    body, model = summarize(build_prompt(collect_changes(args.days), f"{label}({span})"))
    note = render_note(label, span, body, model)
    hit = find_forbidden(note)
    if hit:  # fail-closed: 本文は書かない・表示しない。語そのものはログに出さず番号と位置だけ
        i, pos, how = hit
        print(
            f"::error::生成文に禁止語(check_repo_scope.FORBIDDEN_CONTENT[{i}])が残ったため、"
            f"{os.path.basename(path)} を書きません(dry-run でも本文を表示しません)。"
            f"位置: 文字{pos}(検査: {how})。材料のマスク漏れか要約側の補完が原因。"
        )
        return 1
    if args.dry_run:  # 本文は出さない(公開ログ)。メタデータ 1 行 + ::notice:: のみ
        line = dry_run_summary(note, path, model)
        print(line)
        print(f"::notice::{line}")
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(note)
    print(f"wrote: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
