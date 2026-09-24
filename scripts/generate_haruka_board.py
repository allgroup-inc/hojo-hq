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

2026-09-24 追加「確認ずみの事実」:
  遥さんから「ネタ出しより**投稿前の情報確認**に時間がかかる。制度によって自治体ごとに
  内容や条件が異なるので、出典を読んで誤解のない表現に整えてから画像を作っている」との
  回答があった。それまでボードは出典URLを渡して「発信前にここで最終確認」と書くだけで、
  こちらで照合済みの事実を渡していなかった。つまり**こちらが一度やった確認を、
  遥さんにもう一度やらせていた**。
  制度DB(seido.json)と出典URLで突き合わせ、照合済みの事実をカードに載せる。
  ただし照合できていないものを「確認ずみ」と見せるのは絶対ルール1違反なので、
  ①照合済み ②制度DBにあるが未照合 ③制度DBに無い の3つを必ず区別して出す。
"""
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "fukugiiro", "ig_neta.json")
SEIDO = os.path.join(BASE, "data", "fukugiiro", "seido.json")
OUT = os.path.join(BASE, "site", "staff", "haruka", "index.html")

# カードに出す事実。(制度DBのキー, 見出し)
FACT_FIELDS = [
    ("name", "制度名"),
    ("issuer", "どこの制度か"),
    ("target_household", "だれが対象か"),
    ("amount_note", "いくら"),
    ("how_to_apply", "どこへ申し込むか"),
]


def norm_url(u):
    return (u or "").strip().rstrip("/")


def load_seido():
    """出典URL → 制度 の索引。制度DBが無くても止まらない(ボードは出せる)。"""
    try:
        with open(SEIDO, encoding="utf-8") as f:
            items = json.load(f).get("items", [])
    except (OSError, ValueError):
        return {}
    idx = {}
    for i in items:
        idx.setdefault(norm_url(i.get("source_url")), i)
    return idx


def deadline_text(s):
    dl, dt = s.get("deadline"), s.get("deadline_type")
    if dl:
        return f"{dl}まで" + (f"({dt})" if dt else "")
    return dt or ""


def check_state(it, seido_idx):
    """照合の状態。ok=照合ずみ / warn=制度DBにあるが未照合 / unknown=制度DBに無い。"""
    s = seido_idx.get(norm_url(it.get("source_url")))
    if not s:
        return "unknown"
    return "ok" if s.get("verified") else "warn"


def fact_block(it, seido_idx):
    """照合の状態を3つに分けて出す。未照合を「確認ずみ」に見せない(絶対ルール1)。"""
    s = seido_idx.get(norm_url(it.get("source_url")))
    if not s:
        return ('<div class="facts unknown"><b>⚠️ この案は制度DBに載っていません</b>'
                '<p>こちらで照合できていない案です。出典を開いて、対象・金額・締切を'
                'ご確認のうえ投稿してください。</p></div>')

    rows = []
    for key, label in FACT_FIELDS:
        v = s.get(key)
        if v:
            rows.append(f"<dt>{esc(label)}</dt><dd>{esc(str(v))}</dd>")
    dl = deadline_text(s)
    if dl:
        rows.append(f"<dt>いつまで</dt><dd>{esc(dl)}</dd>")
    dl_html = "<dl>" + "".join(rows) + "</dl>" if rows else ""

    if s.get("verified"):
        when = s.get("verified_at") or "(日付不明)"
        note = ("ここに書いてある範囲は、こちらで公式ページと突き合わせています。"
                "改めて読み直さずに使っていただいて大丈夫です。")
        # 照合済みでも、項目の中に「要確認」と書いてあるものは断定できない。
        # 箱の見出しだけ見て「全部確認ずみ」と読まれると、そこが事故になる
        if any("要確認" in str(s.get(k) or "") for k, _l in FACT_FIELDS):
            note += ("<br>ただし<b>「要確認」と書いてある項目だけは断定しないでください</b>"
                     "(制度はあるが、金額や条件までは詰め切れていない、という意味です)。")
        head = f'<b>✅ 原文と照合ずみです({esc(when)}時点)</b><p>{note}</p>'
        cls = "ok"
    else:
        head = ('<b>⚠️ 制度DBにはありますが、金額・締切は未照合です</b>'
                '<p>下の内容は参考です。金額や期限は断定せず、'
                '「詳しくは公式ページで」の形にしてください。</p>')
        cls = "warn"
    return f'<div class="facts {cls}">{head}{dl_html}</div>'


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    with open(DATA, encoding="utf-8") as f:
        d = json.load(f)
    seido_idx = load_seido()
    # 照合ずみを先に出す(2026-09-24 小柳さん承認の選定方針)。
    # 旬のネタは未照合でも渡すが、❓として下に置き、番号は案の番号のまま変えない
    # (メール・LINEと案番号がずれると事故になる)。
    order = {"ok": 0, "warn": 1, "unknown": 2}
    items = sorted(d.get("items", []),
                   key=lambda it: (order[check_state(it, seido_idx)], it.get("no", 0)))
    cards = []
    for it in items:
        cap_full = it["caption"] + "\n\n" + it["hashtags"]
        cards.append(f"""
<div class="card">
  <div class="no">案{it['no']}</div>
  <h2>{esc(it['title'])}</h2>
  <img class="igimg" src="img/ig{it['no']}.png" alt="投稿画像 案{it['no']}">
  <p class="hint">🖼 画像はこのまま使えます: 長押し(PCは右クリック)→保存→Instagramへ</p>
  {fact_block(it, seido_idx)}
  <div class="cap" id="cap{it['no']}">{esc(cap_full)}</div>
  <button class="copy" data-t="cap{it['no']}">キャプションをコピー</button>
  <p class="caution">⚠️ 投稿前の注意: {esc(it.get('caution',''))}<br>
  出典: <a href="{esc(it.get('source_url',''))}" rel="noopener" target="_blank">公式ページを開く</a></p>
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
.facts{{border-radius:10px;padding:12px 14px;margin-bottom:12px;font-size:.88rem}}
.facts.ok{{background:#F1F7F0;border:1px solid #CADFC6}}
.facts.warn{{background:#FDF6E8;border:1px solid #EBD9AE}}
.facts.unknown{{background:#FBEDEA;border:1px solid #E8C7BE}}
.facts b{{display:block;margin-bottom:4px}}
.facts p{{color:var(--muted);margin-bottom:6px}}
.facts dl{{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:0}}
.facts dt{{color:var(--muted);white-space:nowrap}}
.facts dd{{margin:0}}
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
<div class="howto"><strong>遥さんの3分ルーティン(投稿画像も完成品です)</strong><br>
① 画像を長押しで保存 → ② 「キャプションをコピー」→ ③ Instagramに投稿(画像+キャプション貼り付け)<br>
④ 投稿したら、LINEで「案1 投稿した」と番号だけ返信(使わない案は「案4 なし」)<br>
⭐ 目安は<strong>週2本(火・金の20時ごろ)</strong>。⚠️の注意だけ守れば、どの案を選ぶかは遥さんにお任せです<br>
🎨 画像やキャプションを直したいときは、そのままLINEで一言ください(次週から反映します)</div>
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
