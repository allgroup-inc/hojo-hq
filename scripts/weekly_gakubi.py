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

使い方:
  python scripts/weekly_gakubi.py            # docs/学び/学び_YYYY-Www.md を生成
  python scripts/weekly_gakubi.py --dry-run  # 標準出力のみ
  python scripts/weekly_gakubi.py --self-test
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(REPO_ROOT, "docs", "学び")
MODEL_CANDIDATES = [
    os.environ.get("GAKUBI_MODEL", "claude-sonnet-5"),
    "claude-haiku-4-5",
]
MAX_PROMPT_CHARS = 40_000
WATCH_PATHS = ["docs", "reports", "CLAUDE.md", ".claude/skills/README.md"]


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
        "- 見出しは付けず本文の箇条書きのみ(見出しはこちらで付けます)\n\n"
        f"## 対象週\n{week_label}\n\n"
        f"## コミットログ\n{changes['log'] or '(なし)'}\n\n"
        "## 変更ファイル\n" + ("\n".join(changes["changed_files"]) or "(なし)") + "\n\n"
        f"## 決裁キューの差分\n{changes['queue_diff'] or '(変更なし)'}\n\n"
        f"## 最新の週次レポート\n{changes['latest_report'] or '(なし)'}\n"
    )
    return body[:MAX_PROMPT_CHARS]


def summarize(prompt):
    import anthropic  # ワークフローで pip install anthropic 済み

    client = anthropic.Anthropic(max_retries=3)
    last_err = None
    for model in MODEL_CANDIDATES:
        try:
            resp = client.messages.create(
                model=model, max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
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
    if args.dry_run:
        print(f"=== {os.path.basename(path)} (dry-run) ===\n{note}")
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(note)
    print(f"wrote: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
