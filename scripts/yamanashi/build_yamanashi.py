#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""もらいわすれ堂 山梨版 第1段階ビルド(2026-09-02 小柳さん依頼)

沖縄版(site/fukugiiro)の資産から山梨版(site/yamanashi)を組み立てる。
第1段階の範囲: トップLP(手書き・別ファイル)+3分診断+国の制度53件+ライフイベント別9ページ
+受給報告/プライバシー/訂正+市町村「準備中」ページ。

守るもの(依頼文の5つの約束):
- 制度データは沖縄版で公式照合済みの「全国」制度のみを流用(県・市町村は規約確認後の第2段階)
- 断定表現なし・全件出典リンク・診断は端末内完結・LINEは準備中(入口を勝手に作らない)
- 締切表現は「約1か月前から」ルールのまま流用
"""
import json, os, re, shutil

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
SRC = os.path.join(BASE, "site", "fukugiiro")
OUT = os.path.join(BASE, "site", "yamanashi")
DATA_OUT = os.path.join(BASE, "data", "yamanashi", "seido.json")
Y_BASE_URL = "https://allgroup-inc.github.io/hojo-hq/yamanashi/"

MUNIS = ["甲府市","富士吉田市","都留市","山梨市","大月市","韮崎市","南アルプス市","北杜市","甲斐市","笛吹市","上野原市","甲州市","中央市",
         "市川三郷町","早川町","身延町","南部町","富士川町","昭和町","西桂町","富士河口湖町",
         "道志村","忍野村","山中湖村","鳴沢村","小菅村","丹波山村"]

EVENTS = [
    ("shussan",  ["妊娠・出産"],           "妊娠・出産のとき"),
    ("kosodate", ["子育て"],               "子育て中"),
    ("nyugaku",  ["入園・入学"],           "入園・入学のとき"),
    ("iryo",     ["病気・けが"],           "病気・けがのとき"),
    ("seikatsu", ["低所得・生活苦"],       "家計が苦しいとき"),
    ("shitsugyo", ["失業", "就職・転職"],  "失業・転職のとき"),
    ("sumai",    ["住宅取得・引越"],       "引っ越し・住まいのこと"),
    ("shogai",   ["障がい"],               "障がいのある方・ご家族"),
    ("kaigo",    ["介護"],                 "介護がはじまったとき"),
]

def esc(s):
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def header(depth=1):
    p = "../" * depth
    return f'''<header class="siteheader">
  <a class="hlogo" href="{p}index.html"><img src="{p}assets/icon.svg" alt="" width="30" height="30">もらいわすれ堂 <span style="font-size:.72rem;color:var(--fg-muted);font-weight:400">山梨版</span></a>
  <nav>
    <a href="{p}shindan/">3分診断</a>
    <a href="{p}life/">ライフイベント別</a>
    <a href="{p}area/">市町村</a>
  </nav>
</header>'''

def must_replace(s, old, new, label):
    assert old in s, f"置換対象が見つからない: {label}"
    return s.replace(old, new)

def build_data():
    items = json.load(open(os.path.join(BASE,"data","fukugiiro","seido.json"),encoding="utf-8"))["items"]
    nat = [dict(i) for i in items if i.get("area") == "全国"]
    for i in nat:
        assert "沖縄" not in json.dumps(i, ensure_ascii=False), i["id"]
    data = {"region":"yamanashi","updated_at": json.load(open(os.path.join(BASE,"data","fukugiiro","seido.json"),encoding="utf-8"))["updated_at"],
            "count": len(nat), "items": nat,
            "note": "第1段階=国の制度のみ(沖縄版で公式照合済みの全国制度を流用)。県・市町村は規約確認後に追加"}
    os.makedirs(os.path.dirname(DATA_OUT), exist_ok=True)
    with open(DATA_OUT,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=1); f.write("\n")
    return nat

def build_assets():
    os.makedirs(os.path.join(OUT,"assets"), exist_ok=True)
    for fn in ("fg-base.css","fg-analytics.js","icon.svg"):
        shutil.copy(os.path.join(SRC,"assets",fn), os.path.join(OUT,"assets",fn))
    with open(os.path.join(OUT,"analytics-config.js"),"w",encoding="utf-8") as f:
        f.write('''/* 山梨版 計測設定。GA4は沖縄版と同一プロパティ(page_pathで判別)。
   LINE・Instagramは準備中のため空(入口を勝手に作らない=約束5)。開設決裁後にここへ設定 */
window.FG_ANALYTICS = {provider: "ga4", measurementId: "G-TQMX3MPFSR", domain: "allgroup-inc.github.io"};
window.FG_LINE_URL = "";
window.FG_LINE_OA_ID = "";
''')

def swap_header(s, depth=1):
    return re.sub(r'<header class="siteheader">.*?</header>', header(depth), s, count=1, flags=re.S)

def build_shindan():
    s = open(os.path.join(SRC,"shindan","index.html"),encoding="utf-8").read()
    s = swap_header(s)
    s = must_replace(s, '<link rel="canonical" href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/shindan/">',
                     f'<link rel="canonical" href="{Y_BASE_URL}shindan/">', "canonical")
    s = must_replace(s, '<meta name="description" content="沖縄県にお住まいの世帯向け。',
                     '<meta name="description" content="山梨県にお住まいの世帯向け。', "desc")
    # 市町村リスト
    munis_js = json.dumps(MUNIS + ["県外"], ensure_ascii=False)
    s = re.sub(r'var MUNIS = \[.*?\];', f'var MUNIS = {munis_js};', s, count=1, flags=re.S)
    s = re.sub(r'var MUNI_SLUG = \{.*?\};', 'var MUNI_SLUG = {};', s, count=1, flags=re.S)
    s = must_replace(s, 'fetch("../../data/fukugiiro/seido.json")', 'fetch("../../data/yamanashi/seido.json")', "fetch")
    # Instagram行の削除(山梨は未開設)
    s = re.sub(r'<p style="margin-top:20px;text-align:center"><a class="iglink"[^\n]*</p>\n', '', s, count=1)
    # LINE準備中対応: 既定URLへのフォールバックをやめ、URLが無ければブロック自体を出さない
    s = must_replace(s, 'href:(window.FG_LINE_URL || "https://allgroup-inc.github.io/hojo-hq/go/fg-shindan/")',
                     'href:window.FG_LINE_URL', "topLineBtn fallback")
    s = must_replace(s, 'var lineUrl = window.FG_LINE_URL || "https://allgroup-inc.github.io/hojo-hq/go/fg-shindan/";',
                     'var lineUrl = window.FG_LINE_URL;', "lineUrl fallback")
    s = must_replace(s, '        app.appendChild(topLine);',
                     '        if (window.FG_LINE_URL) app.appendChild(topLine);', "topLine gate")
    s = must_replace(s, '      app.appendChild(lineBox);',
                     '''      if (window.FG_LINE_URL) { app.appendChild(lineBox); }
      else {
        var prep = h("div", {style:"margin:22px 0;padding:14px 16px;background:#F4F1E8;border:1px solid var(--fg-line);border-radius:12px;text-align:center"});
        prep.appendChild(h("p", {class:"note", text:"LINEでの締切お知らせは、山梨版では準備中です。上のコピー機能で結果をメモアプリなどに保存しておけます。"}));
        app.appendChild(prep);
      }''', "lineBox gate")
    s = must_replace(s, 'topCopied.textContent = "結果をコピーしました。LINEで「もらいわすれ堂」のトークに貼り付けると保存できます。";',
                     'topCopied.textContent = "結果をコピーしました。メモアプリなどに貼り付けると保存できます。";', "copy text")
    # 医療バナー: 市町村ページ(準備中)ではなくライフイベント別「医療」へ
    s = must_replace(s, 'var areaHref = areaSlug ? ("../area/" + areaSlug + "/") : "../area/";',
                     'var areaHref = "../life/iryo/";', "areaHref")
    s = must_replace(s, 'var areaLabel = areaSlug ? (state.municipality + "の給付金・手当を見る") : "お住まいの市町村のページを見る";',
                     'var areaLabel = "医療・健康の制度一覧を見る";', "areaLabel")
    s = must_replace(s, 'text:"症状などをおたずねしない方針のためです。お住まいの市町村のページで、医療費助成を含む全制度をまとめて確認できます。"',
                     'text:"症状などをおたずねしない方針のためです。ライフイベント別の一覧で、医療費に関する制度をまとめて確認できます。"', "medBanner text")
    s = must_replace(s, '<a href=\\"" + areaHref + "\\">お住まいの市町村のページ</a>',
                     '<a href=\\"../life/\\">ライフイベント別の一覧</a>', "disclaimer link")
    # 準備シートは第2段階のためリンクを外す
    s = must_replace(s, '''        card.appendChild(h("a", {href: it.source_url, rel:"noopener", class:"cardlink", text:"公式ページで確認する"}));
        card.appendChild(h("span", {class:"linksep", text:" ・ "}));
        var kitLink = h("a", {href:"../kit/" + it.id + "/", class:"cardlink", text:"申請準備シート(持ち物リストつき)"});
        kitLink.addEventListener("click", function(){ if (window.fgTrack) window.fgTrack("kit_click"); });
        card.appendChild(kitLink);''',
                     '        card.appendChild(h("a", {href: it.source_url, rel:"noopener", class:"cardlink", text:"公式ページで確認する"}));', "kit link removal")
    s = must_replace(s, 'text:"💬 受け取れた金額をLINEで報告する(匿名・任意)"',
                     'text:"💬 受け取れたことを報告する(匿名・任意)"', "houkoku link text")
    os.makedirs(os.path.join(OUT,"shindan"), exist_ok=True)
    open(os.path.join(OUT,"shindan","index.html"),"w",encoding="utf-8").write(s)
    shutil.copy(os.path.join(SRC,"shindan","logic.js"), os.path.join(OUT,"shindan","logic.js"))

def build_static():
    # 受給報告
    s = open(os.path.join(SRC,"houkoku","index.html"),encoding="utf-8").read()
    s = swap_header(s)
    s = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{Y_BASE_URL}houkoku/">', s, count=1)
    opts = '<select id="area"><option value="">選択しない</option>' + ''.join(f'<option>{m}</option>' for m in MUNIS) + '</select>'
    s = re.sub(r'<select id="area">.*?</select>', opts, s, count=1, flags=re.S)
    os.makedirs(os.path.join(OUT,"houkoku"), exist_ok=True)
    open(os.path.join(OUT,"houkoku","index.html"),"w",encoding="utf-8").write(s)
    # プライバシー・訂正
    for page in ("privacy","teisei"):
        s = open(os.path.join(SRC,page,"index.html"),encoding="utf-8").read()
        s = swap_header(s)
        s = re.sub(r'<link rel="canonical" href="[^"]*">', f'<link rel="canonical" href="{Y_BASE_URL}{page}/">', s, count=1)
        os.makedirs(os.path.join(OUT,page), exist_ok=True)
        open(os.path.join(OUT,page,"index.html"),"w",encoding="utf-8").write(s)

PAGE_SHELL = '''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} | もらいわすれ堂 山梨版</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<link rel="icon" type="image/svg+xml" href="../{updot}assets/icon.svg">
<link rel="stylesheet" href="../{updot}assets/fg-base.css">
<style>
.wrap{{max-width:680px;margin:0 auto;padding:28px 20px 64px}}
h1{{font-size:1.4rem;margin-bottom:8px;line-height:1.5}}
.card{{background:var(--fg-card);border:1px solid var(--fg-line);border-radius:16px;padding:18px;margin:14px 0;box-shadow:var(--fg-shadow)}}
.card h2{{font-size:1.02rem;margin-bottom:6px}}
.card .sub{{font-size:.9rem;color:var(--fg-muted);margin:4px 0}}
.card a.src{{font-weight:700}}
.btn{{display:block;max-width:440px;margin:20px auto;padding:16px 24px;min-height:44px;background:var(--fg-primary);color:#fff;text-align:center;text-decoration:none;border-radius:999px;font-weight:700;box-shadow:var(--fg-shadow)}}
.status{{margin-left:6px}}
.munis{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;list-style:none;margin:14px 0}}
.munis li{{background:var(--fg-card);border:1px solid var(--fg-line);border-radius:10px;padding:10px 12px;text-align:center;color:var(--fg-muted)}}
</style>
</head>
<body>
{header}
<div class="wrap">
{body}
<div class="disclaimer">掲載内容は「対象となる可能性」のご案内です。金額・締切・要件は必ず各公式ページと窓口でご確認ください。受給の可否は各窓口が判断します。<br>運営: 株式会社フクギイロ</div>
<p style="margin-top:16px"><a href="../{updot}index.html">← トップへもどる</a></p>
</div>
<script src="../{updot}analytics-config.js"></script>
<script src="../{updot}assets/fg-analytics.js"></script>
</body>
</html>
'''

def item_card(it):
    verified = it.get("verified")
    badge = '<span class="status ok">✓ 公式と照合済み</span>' if verified else '<span class="status">要確認</span>'
    cmb = ""
    c = it.get("combine") or {}
    if c.get("note"):
        lbl = {"exclusive":"どちらか一方","adjust":"併用に条件あり","stackable":"一緒に受けられる"}.get(c.get("type"),"併用に注意")
        cmb = f'<p class="sub">⚠ {lbl}: {esc(c["note"])}</p>'
    return (f'<div class="card"><h2>{esc(it["name"])}{badge}</h2>'
            f'<p class="sub">対象: {esc(it.get("target_household",""))}</p>'
            f'<p class="sub">金額の目安: {esc(it.get("amount_note",""))}</p>'
            f'<p class="sub">窓口: {esc(it.get("how_to_apply",""))}</p>'
            f'{cmb}'
            f'<a class="src" href="{esc(it["source_url"])}" rel="noopener">公式ページで確認する ›</a> '
            f'<span class="note">(出典: {esc(it.get("issuer","").split("(")[0])}ウェブサイト)</span></div>')

def build_life(items):
    os.makedirs(os.path.join(OUT,"life"), exist_ok=True)
    links = []
    for slug, evs, heading in EVENTS:
        sel = [i for i in items if any(e in (i.get("life_events") or []) for e in evs)]
        body = [f"<h1>{heading}にもらえる可能性のあるお金(山梨版)</h1>",
                f'<p class="note">国の制度{len(sel)}件を掲載しています。山梨県・市町村の制度は現在準備中です(確認が取れたものから追加します)。</p>',
                '<a class="btn" href="../../shindan/">3分でもらい忘れ診断をはじめる</a>']
        body += [item_card(i) for i in sel]
        os.makedirs(os.path.join(OUT,"life",slug), exist_ok=True)
        html = PAGE_SHELL.format(title=heading, desc=f"山梨県にお住まいの方向け。{heading}に使える可能性のある給付金・手当のご案内(要確認含む)。",
                                 canonical=f"{Y_BASE_URL}life/{slug}/", updot="../", header=header(2), body="\n".join(body))
        open(os.path.join(OUT,"life",slug,"index.html"),"w",encoding="utf-8").write(html)
        links.append(f'<div class="card"><h2><a href="{slug}/">{heading}</a></h2><p class="sub">{len(sel)}件</p></div>')
    idx = PAGE_SHELL.format(title="ライフイベント別の一覧", desc="山梨県にお住まいの方向け。出産・子育て・入学・失業などの場面別に、給付金・手当をまとめています。",
                            canonical=f"{Y_BASE_URL}life/", updot="", header=header(1),
                            body="<h1>ライフイベント別の一覧</h1>\n" + "\n".join(links))
    open(os.path.join(OUT,"life","index.html"),"w",encoding="utf-8").write(idx)

def build_area():
    os.makedirs(os.path.join(OUT,"area"), exist_ok=True)
    lis = "".join(f"<li>{m}</li>" for m in MUNIS)
    body = f'''<h1>市町村別の給付金・手当</h1>
<p class="note">山梨県の27市町村ごとのページは<strong>現在準備中です</strong>。各市町村の公式サイトの利用条件を1つずつ確認しながら、確認が取れたところから順に公開します(勝手に載せない方針のためです)。</p>
<p class="note">それまでのあいだ、全国共通の国の制度は<a href="../life/">ライフイベント別の一覧</a>と<a href="../shindan/">3分診断</a>でご確認いただけます。</p>
<ul class="munis">{lis}</ul>
<a class="btn" href="../shindan/">3分でもらい忘れ診断をはじめる</a>'''
    html = PAGE_SHELL.format(title="市町村別(準備中)", desc="山梨県27市町村の給付金・手当ページは準備中です。国の制度は3分診断・ライフイベント別一覧でご確認いただけます。",
                             canonical=f"{Y_BASE_URL}area/", updot="", header=header(1), body=body)
    open(os.path.join(OUT,"area","index.html"),"w",encoding="utf-8").write(html)

def main():
    os.makedirs(OUT, exist_ok=True)
    items = build_data()
    build_assets()
    build_shindan()
    build_static()
    build_life(items)
    build_area()
    print(f"[ok] 山梨版ビルド完了: 国の制度{len(items)}件 / life9+一覧 / area準備中 / shindan / houkoku / privacy / teisei")

if __name__ == "__main__":
    main()
