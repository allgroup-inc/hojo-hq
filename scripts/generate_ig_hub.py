#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq SNS部 — Instagram「まとめページ」(site/ig/index.html) の生成

Instagramは本文・画像・コメントのURLを押せない(押せるのはプロフィール欄のリンクだけ)。
そこでプロフィールのリンク先をこのページにし、投稿で紹介した制度を「タップで飛べる」形で並べる
(2026-10-16 小柳さん決裁・docs/議事_20261016_IGまとめページ化.md)。

- 入力: 投稿素材そのもの(posts/launch/0*_seido.md, 06_shokei.md, posts/carousel/caption.md)。
  data/subsidies.json から選び直さない=投稿に載った制度と必ず一致させる。
- 締切3層ルール: 生成日時点で残り30日未満の制度は載せない。
- 計測: 導線ごとに専用イベント名(ig_hub_line_click / ig_hub_source_click / ig_hub_shindan_click)。
  LINEボタンは既存の /go/ig/ を経由するため line_redirect(channel=ig)も従来どおり計上される。
決定論的出力(同じ入力・同じ日付なら同じHTML)。
"""
import html
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
OUT_PATH = os.path.join(BASE, "site", "ig", "index.html")
MIN_DAYS = 30
GA_ID = "G-TQMX3MPFSR"
SHINDAN_URL = "../?utm_source=instagram&utm_medium=social&utm_campaign=ig_hub#match"
LINE_URL = "../go/ig/"

# キャプションに入れる案内文(generate_sns.py / generate_carousel.py が共通で使う)
HUB_GUIDE = ("📲 本文のURLはタップできません。プロフィールのリンクを開くと、"
             "この投稿の制度ページへそのまま飛べます。")

DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _date(text):
    m = DATE_RE.search(text or "")
    return date(*map(int, m.groups())) if m else None


def _section(text, title):
    m = re.search(rf"## {title}\n(.*?)(?:\n## |\Z)", text, re.S)
    return m.group(1).strip() if m else ""


def parse_launch(path):
    """posts/launch の制度投稿1件 → {name, deadline, amount, url}。制度投稿でなければ None。"""
    text = open(path, encoding="utf-8").read()
    cap = _section(text, "キャプション")
    name = re.search(r"【募集中】(.+)", cap)
    url = re.search(r"https?://\S+", _section(text, "出典"))
    if not (name and url):
        return None
    dl = re.search(r"🗓\s*(.+)", cap)
    amt = re.search(r"💰\s*(.+)", cap)
    return {"name": name.group(1).strip(), "deadline_text": dl.group(1).strip() if dl else "",
            "amount": amt.group(1).strip() if amt else "", "url": url.group(0)}


def parse_carousel(path):
    """posts/carousel/caption.md → 制度リスト(番号行+締切行+出典行)。"""
    text = open(path, encoding="utf-8").read()
    cap = _section(text, "キャプション")
    urls = {}
    for line in _section(text, "出典").splitlines():
        m = re.match(r"-\s*(.+?):\s*(https?://\S+)", line.strip())
        if m:
            urls[m.group(1).strip()] = m.group(2)
    items = []
    lines = cap.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"\d+\.\s*(.+)", line)
        if not m or i + 1 >= len(lines):
            continue
        name = m.group(1).strip()
        if name not in urls:
            continue
        detail = lines[i + 1].strip()
        dl, _, amt = detail.partition(" / ")
        items.append({"name": name, "deadline_text": dl.strip(), "amount": amt.strip(), "url": urls[name]})
    return items


def collect(base=BASE):
    items = []
    car = os.path.join(base, "posts", "carousel", "caption.md")
    if os.path.exists(car):
        items += parse_carousel(car)
    launch_dir = os.path.join(base, "posts", "launch")
    if os.path.isdir(launch_dir):
        for fn in sorted(os.listdir(launch_dir)):
            if fn.endswith(".md") and ("_seido" in fn or "_shokei" in fn):
                it = parse_launch(os.path.join(launch_dir, fn))
                if it:
                    items.append(it)
    seen, out = set(), []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
    return out


def filter_deadline(items, today):
    kept = []
    for it in items:
        d = _date(it["deadline_text"])
        if d is None or (d - today).days >= MIN_DAYS:
            it = dict(it, deadline=d)
            kept.append(it)
    kept.sort(key=lambda x: (x["deadline"] is None, x["deadline"] or date.max))
    return kept


def render(items, today):
    e = html.escape
    cards = []
    for n, it in enumerate(items, start=1):
        d = it["deadline"]
        dl = (f"締切 {d.isoformat()}(残り{(d - today).days}日)" if d else "締切 要確認(原文でご確認ください)")
        amt = f"<span>{e(it['amount'])}</span>" if it["amount"] else ""
        cards.append(f"""<article class="card" id="s{n}">
<h2>{e(it['name'])}</h2>
<p class="meta"><span>{e(dl)}</span>{amt}</p>
<div class="btns">
<a class="src" href="{e(it['url'])}" target="_blank" rel="noopener" data-ev="ig_hub_source_click">公募ページ(原文)を開く</a>
<a class="shindan" href="{SHINDAN_URL}" data-ev="ig_hub_shindan_click">うちで使える?30秒診断</a>
</div>
</article>""")
    body = "\n".join(cards) if cards else (
        '<p class="empty">いま紹介中の制度を準備しています。最新の募集は下の30秒診断からどうぞ。</p>')
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Instagramで紹介中の補助金｜沖縄企業のミカタ</title>
<meta name="description" content="沖縄企業のミカタのInstagramで紹介した補助金・助成金の公募ページへ、タップで移動できます。">
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>
window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}
gtag('js',new Date());gtag('config','{GA_ID}',{{transport_type:'beacon'}});
document.addEventListener('click',function(ev){{var a=ev.target.closest('a[data-ev]');
if(a)gtag('event',a.getAttribute('data-ev'),{{channel:'ig',transport_type:'beacon'}});}});
</script>
<style>
:root{{--navy:#00335C;--kin:#F88800;--ink:#1c2b36;--paper:#f7f9fb;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'Noto Sans JP','Hiragino Kaku Gothic ProN',Meiryo,sans-serif;color:var(--ink);
background:var(--paper);line-height:1.8;overflow-wrap:break-word;}}
header{{background:linear-gradient(160deg,#021c30,#00335c);color:#f7f5f1;padding:28px 16px 24px;text-align:center;}}
h1{{font-size:1.25rem;line-height:1.5;}}
header p{{font-size:.85rem;opacity:.9;margin-top:6px;}}
main{{max-width:640px;margin:0 auto;padding:18px 16px 48px;}}
.line{{display:block;text-align:center;background:#06C755;color:#fff;font-weight:800;
padding:.95em 1em;border-radius:40px;text-decoration:none;margin-bottom:6px;}}
.line-note{{font-size:.8rem;color:#5a6b78;text-align:center;margin-bottom:18px;}}
.card{{background:#fff;border:1px solid #e2e9f0;border-radius:12px;padding:14px 16px;margin-top:12px;}}
.card h2{{font-size:.98rem;color:var(--navy);line-height:1.6;}}
.meta{{display:flex;gap:12px;flex-wrap:wrap;font-size:.82rem;color:#5a6b78;margin:6px 0 10px;}}
.btns{{display:flex;gap:8px;flex-wrap:wrap;}}
.btns a{{flex:1 1 180px;text-align:center;font-weight:700;font-size:.88rem;padding:.7em .8em;
border-radius:10px;text-decoration:none;}}
.src{{background:var(--navy);color:#fff;}}
.shindan{{background:#fff;color:var(--kin);border:2px solid var(--kin);}}
.empty{{background:#fff;border:1px dashed #c8d4de;border-radius:12px;padding:18px;font-size:.9rem;}}
.note{{font-size:.78rem;color:#5a6b78;margin-top:20px;}}
</style>
</head>
<body>
<header>
<h1>Instagramで紹介中の補助金</h1>
<p>制度名の下のボタンから、公募ページへそのまま移動できます({today.isoformat()}更新)</p>
</header>
<main>
<a class="line" href="{LINE_URL}" data-ev="ig_hub_line_click">LINEで締切のお知らせを受け取る(無料)</a>
<p class="line-note">締切の約1か月前から、LINEでお知らせします。</p>
{body}
<p class="note">※要件・締切・金額は必ず原文の公募要領でご確認ください。当ページは申請代行を行いません。</p>
</main>
</body>
</html>
"""


def main():
    today = datetime.now(JST).date()
    items = filter_deadline(collect(), today)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(render(items, today))
    print(f"[ok] site/ig/index.html を生成({len(items)}件・基準日 {today})")
    print(json.dumps([it["name"] for it in items], ensure_ascii=False))


if __name__ == "__main__":
    main()
