#!/usr/bin/env python3
"""[4] サイト生成: data/public/items.json から site/index.html を生成する。

デザインは site/ 直下のこのテンプレート文字列を編集すれば自由に変更できる。
外部CSS/JSに依存しない単一HTMLなので、GitHub Pagesにそのまま載る。
"""
import html
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_FILE = ROOT / "data" / "public" / "items.json"
SITE_DIR = ROOT / "site"

SITE_TITLE = "情報まとめサイト"  # ← サイト名をここで変更
SITE_DESCRIPTION = "毎日自動更新の情報まとめ"

PAGE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<style>
  :root {{ --accent: #00335C; --bg: #f7f8fa; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: "Noto Sans JP", "Hiragino Sans", Meiryo, sans-serif;
         background: var(--bg); color: #1a1a1a; line-height: 1.7; }}
  header {{ background: var(--accent); color: #fff; padding: 24px 16px; }}
  header h1 {{ margin: 0; font-size: 1.4rem; }}
  header p {{ margin: 4px 0 0; opacity: .85; font-size: .85rem; }}
  main {{ max-width: 860px; margin: 0 auto; padding: 24px 16px 64px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 18px 20px; margin-bottom: 14px;
           box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .card h2 {{ margin: 0 0 6px; font-size: 1.05rem; }}
  .card h2 a {{ color: var(--accent); text-decoration: none; }}
  .card h2 a:hover {{ text-decoration: underline; }}
  .meta {{ font-size: .8rem; color: #666; margin-bottom: 8px; }}
  .meta span {{ margin-right: 12px; }}
  .badge {{ display: inline-block; background: #eef3f8; color: var(--accent);
            border-radius: 4px; padding: 1px 8px; font-size: .75rem; }}
  .warn {{ color: #b25000; }}
  footer {{ text-align: center; font-size: .75rem; color: #888; padding: 24px; }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <p>{description} | 最終更新: {updated}</p>
</header>
<main>
{cards}
</main>
<footer>
  掲載情報は自動収集・自動整形しています。正確な内容は必ずリンク先の原文をご確認ください。<br>
  「要確認」表示は原文から確定できなかった項目です。
</footer>
</body>
</html>
"""

CARD = """<article class="card">
  <h2><a href="{url}" target="_blank" rel="noopener">{title}</a></h2>
  <div class="meta">
    <span class="badge">{category}</span>
    <span>日付: {date}</span>
    <span>金額: {amount}</span>
    <span>対象: {target}</span>
    <span>出典: {source}</span>
  </div>
  <p>{summary}</p>
</article>
"""


def esc(value: str) -> str:
    text = html.escape(str(value))
    if text == "要確認":
        return '<span class="warn">要確認</span>'
    return text


def main() -> int:
    items = json.loads(PUBLIC_FILE.read_text(encoding="utf-8")) if PUBLIC_FILE.exists() else []
    cards = "".join(
        CARD.format(
            url=html.escape(item.get("url", "#")),
            title=esc(item.get("title", "")),
            category=esc(item.get("category", "")),
            date=esc(item.get("date", "")),
            amount=esc(item.get("amount", "")),
            target=esc(item.get("target", "")),
            source=esc(item.get("source_name", "")),
            summary=esc(item.get("summary", "")),
        )
        for item in items
    ) or "<p>まだ掲載情報がありません。次回の自動収集をお待ちください。</p>"

    jst_now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(
        PAGE.format(title=html.escape(SITE_TITLE), description=html.escape(SITE_DESCRIPTION),
                    updated=jst_now, cards=cards),
        encoding="utf-8")
    print(f"サイト生成: {len(items)} 件 → site/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
