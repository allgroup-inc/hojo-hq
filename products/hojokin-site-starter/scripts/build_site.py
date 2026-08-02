#!/usr/bin/env python3
"""[4] サイト生成: data/public/items.json から site/index.html を生成する。

補助金特化の表示:
- 締切が近い順に並べ、残り日数バッジを表示(30日以内は「締切間近」で強調)
- 締切を過ぎた制度は「受付終了」表示で末尾へ(参考情報として残す)
- 各カードに出典リンク必須。「要確認」項目は色付きで明示
"""
import html
import json
import re
import sys
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_FILE = ROOT / "data" / "public" / "items.json"
SITE_DIR = ROOT / "site"

SITE_TITLE = "補助金・支援制度まとめ"  # ← サイト名をここで変更
SITE_DESCRIPTION = "中小企業向けの補助金・助成金情報を毎日自動更新"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

PAGE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<style>
  :root {{ --accent: #00335C; --warn: #b25000; --soon: #c62828; --bg: #f7f8fa; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: "Noto Sans JP", "Hiragino Sans", Meiryo, sans-serif;
         background: var(--bg); color: #1a1a1a; line-height: 1.7; }}
  header {{ background: var(--accent); color: #fff; padding: 24px 16px; }}
  header h1 {{ margin: 0; font-size: 1.4rem; }}
  header p {{ margin: 4px 0 0; opacity: .85; font-size: .85rem; }}
  main {{ max-width: 860px; margin: 0 auto; padding: 24px 16px 64px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 18px 20px; margin-bottom: 14px;
           box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .card.closed {{ opacity: .55; }}
  .card h2 {{ margin: 0 0 6px; font-size: 1.05rem; }}
  .card h2 a {{ color: var(--accent); text-decoration: none; }}
  .card h2 a:hover {{ text-decoration: underline; }}
  .meta {{ font-size: .82rem; color: #555; margin-bottom: 8px; }}
  .meta span {{ margin-right: 12px; white-space: nowrap; }}
  .badge {{ display: inline-block; border-radius: 4px; padding: 1px 8px; font-size: .75rem;
            background: #eef3f8; color: var(--accent); margin-right: 8px; }}
  .badge.soon {{ background: #fdecea; color: var(--soon); font-weight: 700; }}
  .badge.closed {{ background: #eee; color: #777; }}
  .warn {{ color: var(--warn); }}
  .src {{ font-size: .78rem; }}
  footer {{ max-width: 860px; margin: 0 auto; font-size: .75rem; color: #888; padding: 24px 16px; }}
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
  掲載情報は公的情報源から自動収集・自動整形しています。<strong>締切・金額・要件は必ず出典リンク先の原文でご確認ください。</strong>
  「要確認」表示は原文から確定できなかった項目です。<br>
  申請には書類準備やgBizIDの取得(数週間かかる場合があります)が必要です。
  <strong>準備は締切の約1か月前までに始めることをおすすめします。</strong>
</footer>
</body>
</html>
"""

CARD = """<article class="card{closed_class}">
  <h2><a href="{url}" target="_blank" rel="noopener">{title}</a></h2>
  <div class="meta">
    {deadline_badge}<span class="badge">{category}</span><br>
    <span>締切: {date}</span>
    <span>上限額: {amount}</span>
    <span>補助率: {rate}</span><br>
    <span>対象: {target}</span>
    <span>地域: {area}</span>
    <span>実施: {agency}</span>
  </div>
  <p>{summary}</p>
  <div class="src">出典: <a href="{url}" target="_blank" rel="noopener">{source} の原文を確認する</a></div>
</article>
"""


def esc(value: str) -> str:
    text = html.escape(str(value))
    if text == "要確認":
        return '<span class="warn">要確認</span>'
    return text


def deadline_info(date_str: str, today: date) -> tuple:
    """(バッジHTML, 終了フラグ) を返す。"""
    if not DATE_RE.match(date_str or ""):
        if date_str == "随時":
            return '<span class="badge">随時受付</span>', False
        return "", False
    d = date.fromisoformat(date_str)
    days = (d - today).days
    if days < 0:
        return '<span class="badge closed">受付終了</span>', True
    if days <= 30:
        return f'<span class="badge soon">締切間近 残り{days}日</span>', False
    return f'<span class="badge">残り{days}日</span>', False


def main() -> int:
    items = json.loads(PUBLIC_FILE.read_text(encoding="utf-8")) if PUBLIC_FILE.exists() else []
    today = datetime.now(timezone(timedelta(hours=9))).date()

    open_cards, closed_cards = [], []
    for item in items:
        badge, closed = deadline_info(item.get("date", ""), today)
        card = CARD.format(
            closed_class=" closed" if closed else "",
            url=html.escape(item.get("url", "#")),
            title=esc(item.get("title", "")),
            deadline_badge=badge,
            category=esc(item.get("category", "")),
            date=esc(item.get("date", "")),
            amount=esc(item.get("amount", "")),
            rate=esc(item.get("rate", "")),
            target=esc(item.get("target", "")),
            area=esc(item.get("area", "")),
            agency=esc(item.get("agency", "")),
            summary=esc(item.get("summary", "")),
            source=esc(item.get("source_name", "")),
        )
        (closed_cards if closed else open_cards).append(card)

    cards = "".join(open_cards + closed_cards) or \
        "<p>まだ掲載情報がありません。次回の自動収集をお待ちください。</p>"

    jst_now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(
        PAGE.format(title=html.escape(SITE_TITLE), description=html.escape(SITE_DESCRIPTION),
                    updated=jst_now, cards=cards),
        encoding="utf-8")
    print(f"サイト生成: 受付中 {len(open_cards)} 件 / 終了 {len(closed_cards)} 件 → site/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
