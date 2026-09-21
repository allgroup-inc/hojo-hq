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
import json, os, re, shutil, subprocess, sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seeds_yamanashi import YMN_PREF_SEEDS  # noqa: E402

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
    # ヘッダーの読みやすさ・押しやすさは点検2026-09-03 🟡6 と同じ基準(.95rem・タップ44px相当)。
    # fg-base.css は沖縄版と共用のためここで山梨版だけ上書きする
    return f'''<style>p,li{{word-break:auto-phrase;text-wrap:pretty}}h1,h2,h3{{text-wrap:balance}}.siteheader nav a{{font-size:.95rem;padding:10px 12px}}.siteheader .hlogo{{font-size:1.1rem}}</style>
<header class="siteheader">
  <a class="hlogo" href="{p}index.html"><img src="{p}assets/icon.svg" alt="" width="30" height="30">もらいわすれ堂 <span style="font-size:.78rem;color:var(--fg-muted);font-weight:400">山梨版</span></a>
  <nav>
    <a href="{p}shindan/">3分診断</a>
    <a href="{p}area/">市町村</a>
    <a href="{p}kit/">準備シート</a>
  </nav>
</header>'''

def must_replace(s, old, new, label):
    assert old in s, f"置換対象が見つからない: {label}"
    return s.replace(old, new)

def _pref_items(now):
    """山梨県の制度シードを、全国制度と同じ形に整えて返す(第2段階)。

    守り部審査(docs/守り部審査記録_山梨版_2026-09-20.md)でA区分=個別ページへの
    リンク可と判定された山梨県分のみ。金額・締切は原文の逐語照合が済むまで
    status="要確認" / verified=False のままにする(絶対ルール1)。
    """
    out = []
    for seed in YMN_PREF_SEEDS:
        it = dict(seed)
        it.setdefault("amount_note", "要確認(公式ページでご確認ください)")
        it.setdefault("deadline_type", "要確認")
        it.setdefault("deadline", None)
        it.update({
            "verified": False,
            "verified_at": None,
            "verified_by": None,
            "status": "要確認",
            "notes": "出典: " + seed["issuer"].split("(")[0] + "ウェブサイト",
            "fetched_at": now,
        })
        out.append(it)
    return out


def build_data():
    src = json.load(open(os.path.join(BASE,"data","fukugiiro","seido.json"),encoding="utf-8"))
    items = src["items"]
    nat = [dict(i) for i in items if i.get("area") == "全国"]
    for i in nat:
        assert "沖縄" not in json.dumps(i, ensure_ascii=False), i["id"]
    pref = _pref_items(src["updated_at"])
    for i in pref:
        # 沖縄版からの取り違えを機械で止める(全国制度と同じ守り)
        assert "沖縄" not in json.dumps(i, ensure_ascii=False), i["id"]
        assert i["area"] == "山梨県", i["id"]
    merged = nat + pref
    ids = [i["id"] for i in merged]
    assert len(ids) == len(set(ids)), "IDが重複している"
    data = {"region":"yamanashi","updated_at": src["updated_at"],
            "count": len(merged), "items": merged,
            "note": "国の制度(沖縄版で公式照合済みの全国制度を流用)+山梨県の制度。"
                    "市町村独自の制度は守り部の論点(営利サイト可否・トップページ限定)の決裁後に追加"}
    os.makedirs(os.path.dirname(DATA_OUT), exist_ok=True)
    with open(DATA_OUT,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=1); f.write("\n")
    return merged

YMN_EVENT_PREFIX_JS = '\n\n/* 山梨版のみ: イベント名に ymn_ を付けて沖縄版と数字を分ける(2026-09-20 追加)。\n   既に ymn_ が付いているもの(市町村・準備シート・ライフイベントの各ジェネレーター出力)は二重に付けない。 */\n(function () {\n  "use strict";\n  var orig = window.fgTrack;\n  if (typeof orig !== "function") return;\n  window.fgTrack = function (name, props) {\n    var n = typeof name === "string" && name.indexOf("ymn_") !== 0 ? "ymn_" + name : name;\n    return orig(n, props);\n  };\n})();\n'


def build_assets():
    os.makedirs(os.path.join(OUT,"assets"), exist_ok=True)
    for fn in ("fg-base.css","fg-analytics.js","icon.svg"):
        shutil.copy(os.path.join(SRC,"assets",fn), os.path.join(OUT,"assets",fn))
    # 山梨版は沖縄版と同一のGA4プロパティを使うため、イベント名が同じだと
    # 沖縄のKGI(診断ファネル・LINE誘導・受給報告)に山梨の数字が混ざる。
    # 沖縄から変換してくるページ(トップ・診断・報告・訂正・privacy)は沖縄の
    # イベント名をそのまま持ってくるため、ここで一律 ymn_ を付けて分離する。
    # shindan_step_q* のように実行時に組み立てる名前も確実に捕まえるので、
    # 個別の書き換えではなく fgTrack を包む方式にしている。
    with open(os.path.join(OUT,"assets","fg-analytics.js"),"a",encoding="utf-8") as f:
        f.write(YMN_EVENT_PREFIX_JS)
    with open(os.path.join(OUT,"analytics-config.js"),"w",encoding="utf-8") as f:
        f.write('''/* 山梨版 計測設定。GA4は沖縄版と同一プロパティ(page_pathで判別)。
   LINEは山梨版公式アカウント @630pbjqq(2026-09-03 小柳さんが開設)。
   ボタンは /go/ymn-* 経由(lin.ee直貼り禁止・channelで沖縄版と分けて集計)。
   Instagramは準備中のため設定しない(入口を勝手に作らない=約束5) */
window.FG_ANALYTICS = {provider: "ga4", measurementId: "G-TQMX3MPFSR", domain: "allgroup-inc.github.io"};
window.FG_LINE_URL = "https://allgroup-inc.github.io/hojo-hq/go/ymn-shindan/";
window.FG_LINE_OA_ID = "630pbjqq";
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
    # 市町村→slug(市町村ページが第2段階で公開されたため復活。fg_yamanashi.py と同一の表)
    sys.path.insert(0, os.path.join(BASE, "scripts"))
    from fg_yamanashi import MUNI_SLUG as Y_MUNI_SLUG
    slug_js = json.dumps(Y_MUNI_SLUG, ensure_ascii=False)
    s = re.sub(r'var MUNI_SLUG = \{.*?\};', f'var MUNI_SLUG = {slug_js};', s, count=1, flags=re.S)
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
    # コピー案内文はLINE開設済みのため沖縄版の原文(LINEトークに貼ると保存できる)をそのまま使う
    # 医療バナー: 市町村ページ(準備中)ではなくライフイベント別「医療」へ
    s = must_replace(s, 'var areaHref = areaSlug ? ("../area/" + areaSlug + "/") : "../area/";',
                     'var areaHref = "../life/iryo/";', "areaHref")
    s = must_replace(s, 'var areaLabel = areaSlug ? (state.municipality + "の給付金・手当を見る") : "お住まいの市町村のページを見る";',
                     'var areaLabel = "医療・健康の制度一覧を見る";', "areaLabel")
    s = must_replace(s, 'text:"症状などをおたずねしない方針のためです。お住まいの市町村のページで、医療費助成を含む全制度をまとめて確認できます。"',
                     'text:"症状などをおたずねしない方針のためです。ライフイベント別の一覧で、医療費に関する制度をまとめて確認できます。"', "medBanner text")
    s = must_replace(s, '<a href=\\"" + areaHref + "\\">お住まいの市町村のページ</a>',
                     '<a href=\\"../life/\\">ライフイベント別の一覧</a>', "disclaimer link")
    # 準備シート53ページを生成済みのため、結果カードの準備シートリンクは沖縄版のまま生かす(第2段階・2026-09-20)
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
            f'<a class="src" href="{esc(it["source_url"])}" rel="noopener">公式ページで確認する ›</a> ・ '
            f'<a href="../../kit/{esc(it["id"])}/">申請準備シート(持ち物・窓口での言い方)</a> '
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
        # 単一CV(LINE登録・@630pbjqq)。締切は「約1か月前」表現で統一(3層ルール準拠)。
        # ライフイベント別ページは「もらい忘れ」が最も起きる場面なのに導線が無かった(2026-09-20 追加)
        body.append(
            f'<p class="note" style="margin-top:22px;text-align:center">'
            f'{esc(heading)}に関する制度が増えたときや、締切が近づいたときに、LINEでそっとお知らせします。</p>'
            '<a class="linebtn" href="https://allgroup-inc.github.io/hojo-hq/go/ymn-life/" '
            'target="_blank" rel="noopener" onclick="if(window.fgTrack)fgTrack(\'ymn_line_add_click\')">'
            '💬 締切をLINEで受け取る'
            '<span>締切の約1か月前にお知らせ(配信は順次開始)・新しい制度が増えたときも(無料)</span></a>'
        )
        # 受け取ったあとの報告導線。単一CVと競合させないため控えめな一文にする(絶対ルール4)
        body.append(
            '<p class="note" style="margin-top:18px;text-align:center">'
            'もう受け取れた制度はありますか? '
            '<a href="../../houkoku/" onclick="if(window.fgTrack)fgTrack(\'ymn_jukyu_report_link_life\')">'
            '受け取れたことを教えてください(匿名・任意)</a><br>'
            '制度名とおおよその金額だけで大丈夫です。お名前や口座番号はうかがいません。</p>'
        )
        os.makedirs(os.path.join(OUT,"life",slug), exist_ok=True)
        html = PAGE_SHELL.format(title=heading, desc=f"山梨県にお住まいの方向け。{heading}に使える可能性のある給付金・手当のご案内(要確認含む)。",
                                 canonical=f"{Y_BASE_URL}life/{slug}/", updot="../", header=header(2), body="\n".join(body))
        open(os.path.join(OUT,"life",slug,"index.html"),"w",encoding="utf-8").write(html)
        links.append(f'<div class="card"><h2><a href="{slug}/">{heading}</a></h2><p class="sub">{len(sel)}件</p></div>')
    idx = PAGE_SHELL.format(title="ライフイベント別の一覧", desc="山梨県にお住まいの方向け。出産・子育て・入学・失業などの場面別に、給付金・手当をまとめています。",
                            canonical=f"{Y_BASE_URL}life/", updot="", header=header(1),
                            body="<h1>ライフイベント別の一覧</h1>\n" + "\n".join(links))
    open(os.path.join(OUT,"life","index.html"),"w",encoding="utf-8").write(idx)

def build_kit_and_area():
    """第2段階(2026-09-20 一本化): 申請準備シート53+市町村27ページは専用ジェネレーターが生成する。
    市町村ページ(area/)の一覧もそちらが書くため、本スクリプトでは作らない。"""
    for script in ("generate_yamanashi_kit_pages.py", "generate_yamanashi_area_pages.py"):
        subprocess.run([sys.executable, os.path.join(BASE, "scripts", script)], check=True)

def main():
    os.makedirs(OUT, exist_ok=True)
    items = build_data()
    build_assets()
    build_shindan()
    build_static()
    build_life(items)
    build_kit_and_area()
    nat = sum(1 for i in items if i["area"] == "全国")
    pref = sum(1 for i in items if i["area"] == "山梨県")
    print(f"[ok] 山梨版ビルド完了: 制度{len(items)}件(国{nat}+県{pref}) / life9+一覧 / shindan / houkoku / privacy / teisei / kit53+一覧 / area27+一覧")

if __name__ == "__main__":
    main()
