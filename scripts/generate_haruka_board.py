#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遥さん専用 IG投稿案ボード自動生成(SNSレビュー導線・2026-08-11 小柳さん指示)

data/fukugiiro/ig_neta.json(拡充ループの話題スキャンが更新)から、
site/staff/haruka/index.html を生成する。遥さんはこのページを開いて
キャプションをワンタップコピー→Instagramに貼るだけ。承認・却下はLINEで番号を返す。

- /staff/ は robots.txt Disallow + sitemap 除外済みの内部領域(さらに noindex 付与)
- 投稿するかどうかの最終判断は遥さん/小柳さん(絶対ルール5。ここは提案まで)
- 各案の caution(断定禁止・要再照合)を必ずカード内に表示する
"""
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "fukugiiro", "ig_neta.json")
OUT = os.path.join(BASE, "site", "staff", "haruka", "index.html")


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)
    cards = []
    for it in d.get("items", []):
        cap_full = it["caption"] + "\n\n" + it["hashtags"]
        cards.append(f"""
<div class="card">
  <div class="no">案{it['no']}</div>
  <h2>{esc(it['title'])}</h2>
  <div class="cap" id="cap{it['no']}">{esc(cap_full)}</div>
  <button class="copy" data-t="cap{it['no']}">キャプションをコピー</button>
  <p class="hint">🖼 画像の方向性: {esc(it.get('image_hint',''))}</p>
  <p class="caution">⚠️ 投稿前の注意: {esc(it.get('caution',''))}<br>
  出典(発信前にここで最終確認): <a href="{esc(it.get('source_url',''))}" rel="noopener" target="_blank">公式ページを開く</a></p>
</div>""")
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>今週のIG投稿案 | もらいわすれ堂(遥さん専用)</title>
<style>
:root{{--p:#B9502F;--a:#F2C14E;--bg:#FFFBF4;--ink:#3B322B;--line:#EEE1D0;--muted:#6B5D4F}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:"Noto Sans JP","Hiragino Kaku Gothic ProN",Meiryo,sans-serif;background:var(--bg);color:var(--ink);font-size:16px;line-height:1.8;padding:20px 16px 60px}}
.wrap{{max-width:640px;margin:0 auto}}
h1{{font-size:1.2rem;color:var(--p);margin-bottom:4px}}
.sub{{font-size:.85rem;color:var(--muted);margin-bottom:18px}}
.card{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:18px;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
.no{{display:inline-block;background:var(--a);border-radius:999px;padding:2px 12px;font-weight:800;font-size:.85rem;margin-bottom:6px}}
h2{{font-size:1.02rem;margin-bottom:10px;line-height:1.5}}
.cap{{white-space:pre-wrap;background:#FBF5EC;border:1px dashed var(--line);border-radius:10px;padding:12px;font-size:.92rem;margin-bottom:10px}}
.copy{{display:block;width:100%;padding:12px;border-radius:999px;border:none;background:var(--p);color:#fff;font-weight:700;font-size:.95rem;cursor:pointer}}
.copy.done{{background:#0F5138}}
.hint{{font-size:.85rem;color:var(--muted);margin-top:10px}}
.caution{{font-size:.85rem;background:#FFF8E6;border:1px solid #EAD59A;border-radius:8px;padding:10px 12px;margin-top:8px}}
.caution a{{color:var(--p)}}
.howto{{background:#EAF5F0;border:1px solid #B7E0CF;border-radius:12px;padding:14px;font-size:.9rem;margin-bottom:20px}}
</style>
</head>
<body>
<div class="wrap">
<h1>🌈 今週のIG投稿案({esc(d.get('week',''))})</h1>
<p class="sub">更新: {esc(d.get('updated_at',''))} / 毎週月曜に自動更新 / このページは検索に載らない内部ページです</p>
<div class="howto"><strong>遥さんへの使い方</strong><br>
① 使いたい案の「キャプションをコピー」を押す → Instagramに貼る<br>
② 画像は「画像の方向性」を参考に(Canva等)。⚠️の注意だけ守ってください<br>
③ 投稿したら/却下は、LINEで「案1 投稿した」「案4 なし」のように番号で返信</div>
{''.join(cards)}
<p class="sub">投稿の最終判断は遥さん・小柳さんにお任せします(ここは提案まで)。文面の相談はチャットへいつでもどうぞ。</p>
</div>
<script>
document.querySelectorAll('.copy').forEach(function(b){{
  b.addEventListener('click', function(){{
    var t = document.getElementById(b.dataset.t).textContent;
    if (navigator.clipboard) navigator.clipboard.writeText(t).then(function(){{
      b.textContent = 'コピーしました!'; b.classList.add('done');
      setTimeout(function(){{ b.textContent = 'キャプションをコピー'; b.classList.remove('done'); }}, 2000);
    }});
  }});
}});
</script>
</body>
</html>
"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"遥さんボード生成: {len(d.get('items', []))}案 → site/staff/haruka/")


if __name__ == "__main__":
    main()
