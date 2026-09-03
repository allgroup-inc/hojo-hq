#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂 山梨版 — データ抽出+制度一覧ページ生成(第1段階)

- data/fukugiiro/seido.json から area=「全国」の制度(国の制度)だけを抽出し、
  data/fukugiiro/yamanashi_seido.json を生成する(山梨版のLP・診断が読むデータ)。
- あわせて site/fukugiiro/yamanashi/seido/index.html(国の制度一覧)を再生成する。

方針(沖縄版と同じ):
- 断定表現なし。金額・締切は amount_note のまま(「要確認」を勝手に外さない)。
- 全制度に公式ページ(source_url)リンク必須。source_url の無い項目は掲載しない。
- 山梨県・市町村の制度は第2段階(利用規約確認後)まで載せない。「準備中」と正直に書く。

実行: python scripts/build_yamanashi_site.py
沖縄版の seido.json が更新されたら再実行して両ファイルをコミットする。
"""
import json
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
SRC = os.path.join(BASE, "data", "fukugiiro", "seido.json")
OUT_DATA = os.path.join(BASE, "data", "fukugiiro", "yamanashi_seido.json")
OUT_PAGE = os.path.join(BASE, "site", "fukugiiro", "yamanashi", "seido", "index.html")

# 表示順とページ内アンカー(診断の案内リンクが #iryo 等を使う)
CATEGORIES = [
    ("kosodate", "子育て"),
    ("kyoiku", "教育"),
    ("iryo", "医療・健康"),
    ("seikatsu", "生活支援"),
    ("shigoto", "仕事・失業"),
    ("kaigo", "介護"),
    ("sumai", "住まい"),
    ("sonota", "防災・その他"),
]


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_data():
    db = json.load(open(SRC, encoding="utf-8"))
    items = [it for it in db.get("items", [])
             if it.get("area") == "全国" and it.get("source_url")]
    out = {
        "updated_at": datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "source": "data/fukugiiro/seido.json の area=全国(国の制度)のみを抽出",
        "note": "山梨版 第1段階: 国の制度のみ。山梨県・市町村の制度は利用規約確認後に追加する",
        "count": len(items),
        "items": items,
    }
    with open(OUT_DATA, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


def render_page(db):
    items = db["items"]
    groups = []
    used = set()
    for slug, cat in CATEGORIES:
        rows = [it for it in items if it.get("category") == cat]
        if rows:
            rows.sort(key=lambda it: (not it.get("verified"), it.get("name") or ""))
            groups.append((slug, cat, rows))
            used.add(cat)
    rest = [it for it in items if it.get("category") not in used]
    if rest:
        groups.append(("sonohoka", "そのほか", rest))

    toc = "".join(
        f'<a href="#{slug}">{esc(cat)}({len(rows)})</a>' for slug, cat, rows in groups
    )

    secs = []
    for slug, cat, rows in groups:
        cards = []
        for it in rows:
            badge = ('<span class="status ok">✓ 公式と照合済み</span>' if it.get("verified")
                     else '<span class="status">要確認</span>')
            how = esc((it.get("how_to_apply") or "").replace("市区町村", "市町村"))
            howline = f'<p class="sub">窓口: {how}</p>' if how else ""
            cards.append(
                f'<div class="card">{badge}'
                f'<h3>{esc(it.get("name"))}</h3>'
                f'<p class="sub">対象: {esc(it.get("target_household"))}</p>'
                f'<p class="sub">金額: {esc(it.get("amount_note"))}</p>'
                f'{howline}'
                f'<a href="{esc(it.get("source_url"))}" rel="noopener">公式ページで確認する</a> '
                f'<a href="../kit/{esc(it.get("id"))}/">申請準備シート</a>'
                f'</div>'
            )
        secs.append(
            f'<section id="{slug}"><h2>{esc(cat)}<span class="cnt">{len(rows)}件</span></h2>'
            f'<div class="cards">{"".join(cards)}</div></section>'
        )

    updated = esc(db["updated_at"])
    count = db["count"]
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>国の給付金・手当 一覧(山梨版)| もらいわすれ堂</title>
<link rel="canonical" href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/yamanashi/seido/">
<meta name="description" content="山梨県にお住まいの世帯向け。児童手当・出産育児一時金・高額療養費など、国の給付金・手当{count}本を分野別にまとめました。すべて公式ページへのリンクつき。金額・締切は公式ページでご確認ください。">
<meta name="robots" content="noindex">
<link rel="icon" type="image/svg+xml" href="../../assets/icon.svg">
<link rel="stylesheet" href="../../assets/fg-base.css">
<style>
.wrap{{max-width:680px;margin:0 auto;padding:28px 20px 64px}}
h1{{font-size:1.35rem;margin-bottom:6px}}
h2{{font-size:1.15rem;margin:34px 0 12px;border-left:6px solid var(--fg-accent);padding-left:.5em;scroll-margin-top:70px}}
h2 .cnt{{font-size:.8rem;color:var(--fg-muted);font-weight:400;margin-left:.6em}}
.lead{{background:var(--fg-card);border:1px solid var(--fg-line);border-radius:16px;padding:16px 18px;margin:14px 0;box-shadow:var(--fg-shadow)}}
.prep{{background:#FFF8E6;border:1px solid #EAD59A;border-radius:12px;padding:12px 14px;font-size:.9rem;margin:12px 0}}
.toc{{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}}
.toc a{{display:inline-block;padding:8px 14px;min-height:44px;line-height:28px;background:#fff;border:1.5px solid var(--fg-line);border-radius:999px;text-decoration:none;color:var(--fg-ink);font-size:.9rem}}
.cards{{display:grid;gap:12px}}
.card{{background:var(--fg-card);border:1px solid var(--fg-line);border-radius:14px;padding:16px 18px;box-shadow:var(--fg-shadow)}}
.card h3{{font-size:1.05rem;margin:6px 0 4px}}
.card .sub{{font-size:.88rem;color:var(--fg-muted);margin:2px 0}}
.card a{{display:inline-block;margin-top:6px;padding:6px 0;min-height:32px;font-weight:700;text-decoration:none;color:#1F5C45}}
.card a::after{{content:" ›"}}
@media(min-width:900px){{.wrap{{max-width:900px}}.cards{{grid-template-columns:1fr 1fr}}}}
/* 山梨版: ヘッダーを読みやすく・押しやすく(点検2026-09-03 🟡6) */
.siteheader nav a{{font-size:.95rem;padding:10px 12px}}
.siteheader .hlogo{{font-size:1.1rem}}
</style>
</head>
<body>
<script src="../../analytics-config.js"></script>
<script src="../../assets/fg-analytics.js"></script>
<header class="siteheader">
  <a class="hlogo" href="../"><img src="../../assets/icon.svg" alt="" width="30" height="30">もらいわすれ堂 <span style="font-size:.9rem;color:var(--fg-muted)">山梨版</span></a>
  <nav>
    <a href="../shindan/">3分診断</a>
    <a href="../area/">市町村</a>
    <a href="../kit/">準備シート</a>
    <a href="https://allgroup-inc.github.io/hojo-hq/go/ymn-top/" target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack('ymn_line_add_click')">LINE登録</a>
  </nav>
</header>
<div class="wrap">
<p class="note"><a href="../">もらいわすれ堂 山梨版</a> › 国の制度一覧</p>
<h1>国の給付金・手当 一覧</h1>
<div class="lead">
<p>山梨県にお住まいの方が使える可能性のある、<strong>国の制度{count}本</strong>を分野別にまとめました。<br>掲載内容は各制度の公式ページと照合しています。金額・締切など確認が取れていないものは「要確認」と表示し、断定しません。最終的な受給の可否は各窓口の判断となります。</p>
</div>
<div class="prep">🏗 <strong>山梨県・市町村独自の制度は準備中です。</strong>各自治体に掲載のご了解を確認できたところから順に追加します。<a href="../area/">市町村別ページ</a>では、お住まいの街で使える国の制度をまとめて確認できます。</div>
<div class="toc">{toc}</div>
{"".join(secs)}
<div class="disclaimer">このページは公式情報に基づく「ご案内」です。受給できるかどうかの最終判断は各窓口で行われます。申請手続きの代行は行っていません。<br>出典: こども家庭庁・厚生労働省・文部科学省・内閣府 各ウェブサイト(公共データ利用規約 PDL1.0 に基づく利用)ほか / 最終更新: {updated}<br>古い・違う情報を見つけたら <a href="../../teisei/">訂正窓口</a> から教えてください。<br>運営: 株式会社フクギイロ</div>
<p style="margin-top:16px" class="footlinks"><a href="../area/">市町村別まとめ</a> ・ <a href="../kit/">申請準備シート一覧</a> ・ <a href="../">もらいわすれ堂 山梨版 トップへ</a></p>
</div>
</body>
</html>
"""
    os.makedirs(os.path.dirname(OUT_PAGE), exist_ok=True)
    with open(OUT_PAGE, "w", encoding="utf-8") as f:
        f.write(html)
    return len(html.encode("utf-8"))


def main():
    db = build_data()
    size = render_page(db)
    print(f"data: {OUT_DATA} ({db['count']}件)")
    print(f"page: {OUT_PAGE} ({size}B)")
    if size > 50 * 1024:
        raise SystemExit("[ERROR] seido一覧が50KB予算を超過。表示項目を減らすこと")


if __name__ == "__main__":
    main()
