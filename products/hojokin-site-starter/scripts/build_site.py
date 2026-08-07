#!/usr/bin/env python3
"""[4] サイト生成: data/public/items.json から site/index.html を生成する。

補助金特化の表示:
- 締切が近い順。30日以内は「締切間近」の強調表示、受付終了は淡色で末尾へ
- 各項目に出典リンク必須。「要確認」は色付きで明示

デザイン方針(テンプレっぽさを避けるための決めごと):
- カードの白い箱を並べない。区切り線と余白で階層を作る編集的なリスト
- 締切・金額など数字は等幅表示(font-variant-numeric)で桁が揃う
- アクセント色は1色だけ(--accent)。ダークモード自動対応
- 外部CSS/JS/フォントに依存しない単一HTML
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

SITE_TITLE = "補助金・支援制度まとめ"       # ← サイト名をここで変更
SITE_DESCRIPTION = "中小企業向けの補助金・助成金情報を毎日自動更新"
ACCENT = "#1D3A6E"                        # ← 基調色(1色だけ)

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

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
    --bg: #faf9f7; --ink: #1c1b1a; --sub: #6b6862; --line: #e3e0da;
    --warn: #a35200; --soon: #9e2b25;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #16181a; --ink: #e8e6e3; --sub: #96938d; --line: #2c2f33;
             --warn: #e09b4c; --soon: #e2726b; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink); line-height: 1.75;
         font-family: "Hiragino Sans", "Noto Sans JP", "Yu Gothic", Meiryo, sans-serif; }}
  .wrap {{ max-width: 820px; margin: 0 auto; padding: 0 20px; }}
  header {{ padding: 56px 0 28px; border-bottom: 2px solid var(--ink); }}
  header h1 {{ margin: 0; font-size: clamp(1.8rem, 5vw, 2.6rem); letter-spacing: -.02em;
               line-height: 1.15; }}
  header p {{ margin: 10px 0 0; color: var(--sub); font-size: .85rem;
              font-variant-numeric: tabular-nums; }}
  main {{ padding: 8px 0 72px; }}
  article {{ padding: 26px 0; border-bottom: 1px solid var(--line); }}
  article.closed {{ opacity: .45; }}
  .status {{ font-size: .78rem; font-weight: 700; letter-spacing: .02em; }}
  .status.soon {{ color: var(--soon); }}
  .status.open {{ color: var(--accent); }}
  .status.closed-label {{ color: var(--sub); font-weight: 600; }}
  article h2 {{ margin: 2px 0 8px; font-size: 1.12rem; line-height: 1.5;
                letter-spacing: -.01em; }}
  article h2 a {{ color: var(--ink); text-decoration: none; }}
  article h2 a:hover {{ color: var(--accent); text-decoration: underline;
                        text-underline-offset: 4px; }}
  dl {{ display: grid; grid-template-columns: 5.5em 1fr; gap: 2px 12px; margin: 0 0 10px;
        font-size: .85rem; font-variant-numeric: tabular-nums; }}
  dt {{ color: var(--sub); }}
  dd {{ margin: 0; font-weight: 600; }}
  @media (min-width: 640px) {{
    dl {{ grid-template-columns: 5.5em 1fr 5.5em 1fr; }}
  }}
  .warn {{ color: var(--warn); }}
  article p {{ margin: 0; font-size: .95rem; max-width: 65ch; }}
  .src {{ margin-top: 8px; font-size: .78rem; }}
  .src a {{ color: var(--sub); }}
  .empty {{ padding: 64px 0; color: var(--sub); }}
  footer {{ border-top: 1px solid var(--line); padding: 24px 0 56px; font-size: .78rem;
            color: var(--sub); }}
  footer strong {{ color: var(--ink); }}
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
  掲載情報は公的情報源から自動収集・自動整形しています。<strong>締切・金額・要件は必ず
  出典リンク先の原文でご確認ください。</strong>「要確認」は原文から確定できなかった項目です。<br>
  申請には書類準備やgBizIDの取得(数週間かかる場合があります)が必要です。
  <strong>準備は締切の約1か月前までに始めることをおすすめします。</strong>
</footer>
</div>
</body>
</html>
"""

CARD = """<article{closed_class}>
  {status_line}
  <h2><a href="{url}" target="_blank" rel="noopener">{title}</a></h2>
  <dl>
    <dt>締切</dt><dd>{date}</dd>
    <dt>上限額</dt><dd>{amount}</dd>
    <dt>補助率</dt><dd>{rate}</dd>
    <dt>対象</dt><dd>{target}</dd>
    <dt>地域</dt><dd>{area}</dd>
    <dt>実施</dt><dd>{agency}</dd>
  </dl>
  <p>{summary}</p>
  <div class="src"><a href="{url}" target="_blank" rel="noopener">出典: {source} の原文を確認する</a></div>
</article>
"""


def esc(value: str) -> str:
    text = html.escape(str(value))
    if text == "要確認":
        return '<span class="warn">要確認</span>'
    return text


def status_line(date_str: str, category: str, today: date) -> tuple:
    """(ステータス行HTML, 終了フラグ) を返す。"""
    cat = html.escape(category or "")
    if not DATE_RE.match(date_str or ""):
        label = "随時受付" if date_str == "随時" else ""
        return f'<div class="status open">{cat}{" / " + label if label else ""}</div>', False
    d = date.fromisoformat(date_str)
    days = (d - today).days
    if days < 0:
        return f'<div class="status closed-label">{cat} / 受付終了</div>', True
    if days <= 30:
        return f'<div class="status soon">{cat} / 締切間近 残り{days}日</div>', False
    return f'<div class="status open">{cat} / 残り{days}日</div>', False


def main() -> int:
    items = json.loads(PUBLIC_FILE.read_text(encoding="utf-8")) if PUBLIC_FILE.exists() else []
    today = datetime.now(timezone(timedelta(hours=9))).date()

    open_cards, closed_cards = [], []
    for item in items:
        status, closed = status_line(item.get("date", ""), item.get("category", ""), today)
        card = CARD.format(
            closed_class=' class="closed"' if closed else "",
            status_line=status,
            url=html.escape(item.get("url", "#")),
            title=esc(item.get("title", "")),
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
        '<p class="empty">まだ掲載情報がありません。次回の自動収集をお待ちください。</p>'

    jst_now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(
        PAGE.format(title=html.escape(SITE_TITLE), description=html.escape(SITE_DESCRIPTION),
                    accent=ACCENT, updated=jst_now, cards=cards),
        encoding="utf-8")
    print(f"サイト生成: 受付中 {len(open_cards)} 件 / 終了 {len(closed_cards)} 件 → site/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
