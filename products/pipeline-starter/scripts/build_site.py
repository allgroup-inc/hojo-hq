#!/usr/bin/env python3
"""[4] サイト生成: data/public/items.json から site/index.html を生成する。

デザイン方針(テンプレっぽさを避けるための決めごと):
- カードの白い箱を並べない。区切り線と余白で階層を作る編集的なリスト
- 見出しは大きく強く、メタ情報は小さく等幅で。数字・日付は等幅フォント
- アクセント色は1色だけ(--accent)。ダークモード自動対応
- 外部CSS/JS/フォントに依存しない単一HTML(GitHub Pagesにそのまま載る)

SITE_TITLE と --accent を変えるだけで自分のサイトになる。
"""
import html
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_FILE = ROOT / "data" / "public" / "items.json"
SITE_DIR = ROOT / "site"

SITE_TITLE = "情報まとめ"        # ← サイト名をここで変更
SITE_DESCRIPTION = "毎日自動更新"  # ← 説明をここで変更
ACCENT = "#0B5A44"               # ← 基調色(1色だけ。例: 深緑 #0B5A44 / 藍 #1D3A6E / 錆 #A44A2A)

PAGE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<style>
  :root {{
    --accent: {accent};
    --bg: #faf9f7; --ink: #1c1b1a; --sub: #6b6862; --line: #e3e0da; --warn: #a35200;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #16181a; --ink: #e8e6e3; --sub: #96938d; --line: #2c2f33; --warn: #e09b4c; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink); line-height: 1.75;
         font-family: "Hiragino Sans", "Noto Sans JP", "Yu Gothic", Meiryo, sans-serif; }}
  .wrap {{ max-width: 760px; margin: 0 auto; padding: 0 20px; }}
  header {{ padding: 56px 0 28px; border-bottom: 2px solid var(--ink); }}
  header h1 {{ margin: 0; font-size: clamp(1.8rem, 5vw, 2.6rem); letter-spacing: -.02em;
               line-height: 1.15; }}
  header p {{ margin: 10px 0 0; color: var(--sub); font-size: .85rem;
              font-variant-numeric: tabular-nums; }}
  main {{ padding: 8px 0 72px; }}
  article {{ padding: 26px 0; border-bottom: 1px solid var(--line); }}
  article h2 {{ margin: 0 0 6px; font-size: 1.12rem; line-height: 1.5; letter-spacing: -.01em; }}
  article h2 a {{ color: var(--ink); text-decoration: none; }}
  article h2 a:hover {{ color: var(--accent); text-decoration: underline;
                        text-underline-offset: 4px; }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 4px 18px; margin: 0 0 10px; padding: 0;
           list-style: none; font-size: .8rem; color: var(--sub);
           font-variant-numeric: tabular-nums; }}
  .meta b {{ font-weight: 600; color: var(--ink); }}
  .cat {{ color: var(--accent); font-weight: 700; }}
  .warn {{ color: var(--warn); font-weight: 600; }}
  article p {{ margin: 0; font-size: .95rem; max-width: 65ch; }}
  .src {{ margin-top: 8px; font-size: .78rem; }}
  .src a {{ color: var(--sub); }}
  .empty {{ padding: 64px 0; color: var(--sub); }}
  footer {{ border-top: 1px solid var(--line); padding: 24px 0 56px; font-size: .78rem;
            color: var(--sub); }}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>{title}</h1>
  <p>{description}。最終更新 {updated}</p>
</header>
<main>
{cards}
</main>
<footer>
  掲載情報は自動収集・自動整形しています。正確な内容は必ず出典リンク先の原文でご確認ください。
  「要確認」は原文から確定できなかった項目です。
</footer>
</div>
</body>
</html>
"""

CARD = """<article>
  <h2><a href="{url}" target="_blank" rel="noopener">{title}</a></h2>
  <ul class="meta">
    <li class="cat">{category}</li>
    <li>日付 <b>{date}</b></li>
    <li>金額 <b>{amount}</b></li>
    <li>対象 <b>{target}</b></li>
  </ul>
  <p>{summary}</p>
  <div class="src"><a href="{url}" target="_blank" rel="noopener">出典: {source}</a></div>
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
            summary=esc(item.get("summary", "")),
            source=esc(item.get("source_name", "")),
        )
        for item in items
    ) or '<p class="empty">まだ掲載情報がありません。次回の自動収集をお待ちください。</p>'

    jst_now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(
        PAGE.format(title=html.escape(SITE_TITLE), description=html.escape(SITE_DESCRIPTION),
                    accent=ACCENT, updated=jst_now, cards=cards),
        encoding="utf-8")
    print(f"サイト生成: {len(items)} 件 → site/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
