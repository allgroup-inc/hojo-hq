#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
月次: Claude Code / Anthropic / MCP エコシステムの直近アップデートを Claude(Web検索
ツール付き)で調べ、ALLGROUP の運用に効くものだけを docs/AI更新ウォッチ_YYYY-MM.md に
書き出す(2026-09-21 導入)。

背景: 「最新アップデートを集めて運用に反映するプロンプト」(2026-09-05 小柳さん)を
毎月自動で回す。判断基準は当時のプロンプトをそのまま採用:
  - 今の運用(CLAUDE.md・.claude/skills・接続済みMCP)に具体的に効くか
  - 「効率が上がる」「今できないことができる」のどちらかか
  - 新しい外部接続で個人情報・機密を扱うなら「小柳さん決裁が必要な提案」扱い
  - 該当なしなら「今回反映すべき新情報なし」と短く書く(水増ししない)

壊れにくい設計: 月ごとの固定ファイル名でべき等 / API失敗は非ゼロ終了で Issue 起票 /
出典URLは本文に必ず残す(AIの言い切りを人が裏取りできるように)。

使い方:
  python scripts/ai_update_watch.py             # docs/AI更新ウォッチ_YYYY-MM.md を生成
  python scripts/ai_update_watch.py --dry-run   # 標準出力のみ
  python scripts/ai_update_watch.py --self-test
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(REPO_ROOT, "docs", "AI更新ウォッチ")  # docs/** は毎朝6時にObsidianへ同期される
MODEL = os.environ.get("AI_WATCH_MODEL", "claude-sonnet-5")
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 8}


def build_prompt(month_label):
    return (
        f"AI業界・Claude Codeエコシステムの最新アップデートを調べて、私が今運用している\n"
        f"ALLGROUPの複数チャット(沖縄企業のミカタ/glow-ma/家計の見直しやさん等)に\n"
        f"反映できるものだけを教えてください。対象月: {month_label}\n\n"
        f"1. 直近1〜2ヶ月のClaude Code・Anthropic・MCPエコシステムのアップデートを\n"
        f"   Web検索で確認する(公式の変更履歴・公式ブログ・信頼できる技術メディア中心。\n"
        f"   出所不明のSNS発の「裏技」系は真偽を裏取りしてから扱う)\n\n"
        f"2. 見つけたアップデートを、次の基準だけでふるいにかける(それ以外は無視):\n"
        f"   - 今の運用(リポジトリのCLAUDE.md・.claude/skills・接続済みMCP、GitHub Actions\n"
        f"     による自動化、Claude APIでの原文照合・要約)に具体的に効果がある変更か\n"
        f"   - 「効率が上がる」「今できないことができる」のどちらかに当てはまるか\n"
        f"   - 新しい外部サービス接続が要る場合、個人情報・機密情報を扱うか\n"
        f"     (扱う場合は導入判断ではなく「小柳さん決裁が必要な提案」として扱う)\n\n"
        f"3. 残ったものだけ、1件につき3行以内で: 何が変わったか / 何に使えるか /\n"
        f"   導入コスト(すぐ試せる・要決裁・様子見)。各件に出典URLを1つ添える\n\n"
        f"4. 該当なしなら「今回反映すべき新情報なし」とだけ簡潔に報告する\n"
        f"   (無理に何か見つけて水増ししない)\n\n"
        f"出力は日本語のMarkdown本文のみ(先頭の見出しは不要)。"
    )


def research(prompt):
    import anthropic

    client = anthropic.Anthropic(max_retries=3)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2500,
        tools=[WEB_SEARCH_TOOL],
        messages=[{"role": "user", "content": prompt}],
    )
    text = "\n".join(
        b.text for b in resp.content if getattr(b, "type", "") == "text" and b.text.strip()
    ).strip()
    if not text:
        raise RuntimeError("Claude から本文が返りませんでした")
    return text


def render(month_label, body):
    now = datetime.now(JST)
    return (
        f"# AI更新ウォッチ {month_label}\n\n"
        f"生成: {now:%Y-%m-%d %H:%M} JST(GitHub Actions `ai-update-watch`・モデル {MODEL}・Web検索付き)\n\n"
        f"判断基準: 今の運用に効く / 効率が上がる・できなかったことができる / 個人情報を扱う接続は決裁扱い。\n"
        f"AIの言い切りは出典で必ず裏取りすること(絶対ルール1と同じ考え方)。\n\n"
        f"{body}\n\n"
        f"---\n"
        f"反映のしかた: 「すぐ試せる」は該当チャットで試す → 効いたら CLAUDE.md か該当スキルに1行足す。\n"
        f"「要決裁」は docs/決裁キュー.md に上申する。「様子見」は翌月のウォッチで再判定。\n"
    )


def out_path(month_label):
    return os.path.join(OUT_DIR, f"{month_label}.md")


def self_test():
    p = build_prompt("2026-09")
    assert "Web検索" in p and "水増し" in p
    r = render("2026-09", "- テスト行")
    assert r.startswith("# AI更新ウォッチ 2026-09") and "- テスト行" in r
    assert out_path("2026-09").endswith(os.path.join("docs", "AI更新ウォッチ", "2026-09.md"))
    print("self-test OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--force", action="store_true", help="同月ファイルがあっても上書き")
    args = ap.parse_args()
    if args.self_test:
        self_test()
        return 0
    month_label = datetime.now(JST).strftime("%Y-%m")
    path = out_path(month_label)
    if os.path.exists(path) and not args.force and not args.dry_run:
        print(f"skip: {os.path.basename(path)} は既に存在(べき等)")
        return 0
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("::warning::ANTHROPIC_API_KEY 未設定のためスキップ")
        return 0
    body = research(build_prompt(month_label))
    doc = render(month_label, body)
    if args.dry_run:
        print(doc)
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"wrote: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
