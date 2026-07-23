#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂 申請準備シート自動生成(トドケ管轄・守り部線引き準拠)
data/fukugiiro/seido.json から、制度ごとに「印刷して窓口に持っていくだけ」の
準備シートを site/fukugiiro/kit/<id>/index.html に生成する。fetch後に毎回再生成。

守り部の線引き(docs/フクギイロ_申請準備キット_線引き.md):
- 申請書の代筆・代行はしない。書くのは本人。私たちは「迷わない準備」までを提供する
- 持ち物は「よくある例」として提示し、断定しない。窓口での最終確認を全ページで案内
- 公式様式PDFの再配布はしない(版ズレ防止)。必ず公式ページへのリンクで案内
"""
import json
import os
import shutil

BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "fukugiiro", "seido.json")
OUT_DIR = os.path.join(BASE, "site", "fukugiiro", "kit")

# 共通の持ち物(よくある例)
COMMON_ITEMS = [
    "本人確認書類(運転免許証・マイナンバーカードなど)",
    "マイナンバーがわかるもの",
    "振込先の口座がわかるもの(通帳・キャッシュカード)",
    "印鑑(不要な市町村もあります)",
]

# ライフイベント別の追加持ち物(よくある例)
EVENT_ITEMS = {
    "妊娠・出産": ["母子健康手帳", "出産にかかった費用がわかるもの(領収書・明細)"],
    "子育て": ["お子さんの健康保険情報がわかるもの", "世帯の状況がわかる書類(あれば)"],
    "入園・入学": ["在学がわかるもの(学生証・在学証明など)", "学校から配られた案内(あれば)"],
    "失業": ["離職票・雇用保険受給資格者証(お持ちの場合)"],
    "就職・転職": ["勤務先や雇用条件がわかるもの(雇用契約書など)"],
    "病気・けが": ["医療費の領収書", "加入している健康保険がわかるもの"],
    "低所得・生活苦": ["収入がわかる書類(給与明細・課税証明など)"],
    "住宅取得・引越": ["住まいの契約がわかる書類(賃貸契約書など)"],
    "介護": ["介護保険証(お持ちの場合)"],
    "障がい": ["障害者手帳(お持ちの場合)"],
    "災害": ["り災証明書(お持ちの場合・後からでも可の場合あり)"],
}

STYLE = """
:root{--fg-primary:#B9502F;--fg-accent:#F2B705;--fg-deep:#1A6B52;--fg-ink:#1F2A2E;--fg-bg:#FFFBF4;--fg-card:#fff;--fg-muted:#5C6B70;--fg-line:#EBE2D4}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Hiragino Kaku Gothic ProN","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;font-size:18px;line-height:1.8;color:var(--fg-ink);background:var(--fg-bg)}
.wrap{max-width:680px;margin:0 auto;padding:28px 20px 64px}
h1{font-size:1.3rem;margin-bottom:4px}
h2{font-size:1.05rem;margin:22px 0 8px;border-left:6px solid var(--fg-accent);padding-left:.5em}
.note{font-size:.85rem;color:var(--fg-muted)}
.box{background:var(--fg-card);border:1px solid var(--fg-line);border-radius:12px;padding:16px 18px;margin:10px 0}
.status{font-size:.8rem;background:#fff3cd;border-radius:4px;padding:1px 8px;color:#7a5b00}
ul.check{list-style:none}
ul.check li{border-bottom:1px dashed var(--fg-line)}
ul.check label{display:flex;align-items:flex-start;gap:12px;padding:9px 0;cursor:pointer}
ul.check input[type=checkbox]{width:22px;height:22px;min-width:22px;margin-top:5px;accent-color:var(--fg-primary)}
ul.check input:checked + span{color:var(--fg-muted);text-decoration:line-through}
.madoguchi{font-size:.95rem;background:#EAF5F0;border-radius:8px;padding:12px 14px;color:#0F5138}
.memo{width:100%;border:none;border-bottom:2px solid var(--fg-line);background:transparent;font:inherit;font-size:.95rem;min-height:44px;resize:vertical;padding:6px 2px}
.memo:focus{outline:none;border-bottom-color:var(--fg-primary)}
.prog{font-weight:700;color:var(--fg-deep)}
.btns{display:flex;gap:10px;margin:18px 0}
.btns button,.btns a{flex:1;display:block;padding:13px;min-height:44px;border-radius:10px;border:2px solid var(--fg-primary);background:#fff;color:var(--fg-primary);font-size:.95rem;font-weight:700;cursor:pointer;text-align:center;text-decoration:none}
.btns .primary{background:var(--fg-primary);color:#fff}
.disclaimer{background:#f4f1e8;border-radius:10px;padding:14px;font-size:.85rem;color:var(--fg-muted);margin-top:24px}
a{color:var(--fg-primary)}
.steps{list-style:none;counter-reset:s}
.steps li{padding:6px 0 6px 44px;position:relative;counter-increment:s}
.steps li::before{content:counter(s);position:absolute;left:4px;top:8px;width:28px;height:28px;background:var(--fg-accent);border-radius:50%;text-align:center;line-height:28px;font-weight:800;font-size:.9rem}
@media print{.btns,.no-print{display:none!important}body{background:#fff;font-size:14px}.wrap{padding:0}.box{break-inside:avoid}}
"""


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def page(title, desc, body, depth=2):
    rel = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="icon" type="image/svg+xml" href="{rel}assets/icon.svg">
<style>{STYLE}</style>
</head>
<body>
<script src="{rel}analytics-config.js"></script>
<script src="{rel}assets/fg-analytics.js"></script>
<div class="wrap">
{body}
</div>
</body>
</html>
"""


KIT_JS = """
<script>
(function(){
  var KEY = "fk_kit___ID__";
  var saved = {c:[], m:{}};
  try { saved = JSON.parse(localStorage.getItem(KEY)) || saved; } catch(e){}
  var boxes = Array.prototype.slice.call(document.querySelectorAll("ul.check input[type=checkbox]"));
  var memos = Array.prototype.slice.call(document.querySelectorAll("textarea.memo"));
  var prog = document.getElementById("prog");
  var trackedCheck = false;
  function upd(){
    var n = boxes.filter(function(b){ return b.checked; }).length;
    if (prog) prog.textContent = "そろったもの: " + n + " / " + boxes.length + (n === boxes.length && n > 0 ? " — 準備かんりょう!" : "");
  }
  function save(){
    var data = {c: [], m: {}};
    boxes.forEach(function(b, i){ if (b.checked) data.c.push(i); });
    memos.forEach(function(t, i){ if (t.value) data.m[i] = t.value.slice(0, 500); });
    try { localStorage.setItem(KEY, JSON.stringify(data)); } catch(e){}
  }
  boxes.forEach(function(b, i){
    if (saved.c && saved.c.indexOf(i) >= 0) b.checked = true;
    b.addEventListener("change", function(){
      save(); upd();
      if (!trackedCheck && window.fgTrack) { trackedCheck = true; fgTrack("kit_check"); }
    });
  });
  memos.forEach(function(t, i){
    if (saved.m && saved.m[i]) t.value = saved.m[i];
    t.addEventListener("input", save);
  });
  upd();
})();
</script>
"""


def kit_page(it, updated):
    badge = ' <span class="status">要確認</span>' if it.get("status") == "要確認" else ""
    items = list(COMMON_ITEMS)
    for ev in it.get("life_events", []):
        for x in EVENT_ITEMS.get(ev, []):
            if x not in items:
                items.append(x)
    checks = "\n".join(
        f'<li><label><input type="checkbox" data-k="{i}"><span>{esc(x)}</span></label></li>'
        for i, x in enumerate(items)
    )
    warn = ""
    if it.get("status") == "要確認":
        warn = '<div class="box" style="border-color:#E0B54A;background:#FFF8E6"><span class="note">この制度は現在、内容の最終確認中です。お出かけ前に必ず公式ページと窓口でご確認ください。</span></div>'
    body = f"""
<p class="note no-print"><a href="../../index.html">もらいわすれ堂</a> › 申請準備シート</p>
<h1>{esc(it['name'])} 申請準備シート{badge}</h1>
<p class="note">このシートを印刷して、そのまま窓口に持っていけます(スマホ画面のままでもOK)。書くのはご本人ですが、準備はここで全部終わらせましょう。</p>
{warn}
<div class="btns">
  <button class="primary" onclick="if(window.fgTrack)fgTrack('kit_print');window.print()">🖨 このシートを印刷する</button>
  <a href="{esc(it['source_url'])}" rel="noopener" onclick="if(window.fgTrack)fgTrack('kit_official')">公式ページで最新情報を確認</a>
</div>

<h2>この制度について</h2>
<div class="box">
  <p><strong>対象になる可能性のある方</strong><br>{esc(it['target_household'])}</p>
  <p style="margin-top:8px"><strong>金額の目安</strong><br>{esc(it['amount_note'])}</p>
  <p style="margin-top:8px"><strong>窓口</strong><br>{esc(it['how_to_apply'])}</p>
</div>

<h2>やることは3つだけ</h2>
<div class="box">
  <ol class="steps">
    <li>公式ページで最新の内容と申請書の様式を確認する</li>
    <li>下の持ち物をそろえる(全部なくても大丈夫。あるものだけで窓口へ)</li>
    <li>窓口に行く。申請書は窓口にも置いてあり、その場で書けます</li>
  </ol>
</div>

<h2>持ち物チェックリスト(よくある例)</h2>
<p class="note">市町村やご家庭の状況によって変わります。「例」としてそろえて、細かい違いは窓口で確認すれば大丈夫です。チェックとメモはこの端末の中だけに保存され、次に開いたときも残っています。</p>
<div class="box">
  <p class="note"><span class="prog" id="prog"></span></p>
  <ul class="check">
{checks}
  </ul>
</div>

<h2>窓口でのひとこと</h2>
<div class="madoguchi">「<strong>{esc(it['name'])}</strong>について教えてください。対象になるか確認したいです」<br>
<span class="note" style="color:#0F5138">これだけ言えば、あとは職員の方が案内してくれます。対象かどうか自信がなくても大丈夫です。</span></div>

<h2>窓口で聞いたことメモ</h2>
<div class="box">
  <p class="note">担当窓口・電話番号:</p><textarea class="memo" data-m="0" rows="1"></textarea>
  <p class="note" style="margin-top:10px">足りなかった書類・次にやること:</p><textarea class="memo" data-m="1" rows="1"></textarea>
  <p class="note" style="margin-top:10px">いつまでに(期限):</p><textarea class="memo" data-m="2" rows="1"></textarea>
</div>

<div class="disclaimer">このシートは公式情報に基づく「準備のご案内」です。持ち物は一般的な例で、市町村により異なります。受給できるかどうかの最終判断は各窓口で行われます。申請書の作成代行・代筆は行っていません(ご本人が記入します)。専門家のサポートが必要な場合は、提携の専門家(社会保険労務士・行政書士など)をご紹介します。<br>最終更新: {esc(updated)} / もらいわすれ堂(運営: 株式会社フクギイロ)/ 出典: <a href="{esc(it['source_url'])}" rel="noopener">公式ページ</a></div>
<p style="margin-top:16px" class="no-print"><a href="../index.html">準備シート一覧へ</a> ・ <a href="../../shindan/">3分診断</a> ・ <a href="../../index.html">もらいわすれ堂 トップ</a></p>
"""
    body += KIT_JS.replace("__ID__", it["id"])
    title = f"{it['name']} 申請準備シート(印刷用)| もらいわすれ堂"
    desc = f"{it['name']}の申請に行く前の準備シート。持ち物チェックリスト・窓口でのひとこと・メモ欄つき。印刷してそのまま窓口へ。"
    return page(title, desc, body)


def index_page(items, updated):
    lis = "\n".join(
        f'<li style="margin-bottom:8px"><a href="{esc(it["id"])}/">{esc(it["name"])}</a>'
        + (' <span class="status">要確認</span>' if it.get("status") == "要確認" else "")
        + "</li>"
        for it in items
    )
    body = f"""
<h1>申請準備シート一覧</h1>
<p class="note">制度ごとに「印刷して窓口に持っていくだけ」の準備シートを用意しています。どれが自分に合うかわからないときは、まず3分診断からどうぞ。</p>
<a class="no-print" href="../shindan/" style="display:block;max-width:420px;margin:16px auto;padding:14px 24px;background:var(--fg-primary);color:#fff;text-align:center;text-decoration:none;border-radius:999px;font-weight:700">3分でもらい忘れ診断をはじめる</a>
<div class="box"><ul style="list-style:none">{lis}</ul></div>
<div class="disclaimer">最終更新: {esc(updated)}(毎日自動更新)/ もらいわすれ堂(運営: 株式会社フクギイロ)</div>
<p style="margin-top:16px"><a href="../index.html">もらいわすれ堂 トップ</a></p>
"""
    return page("申請準備シート一覧 | もらいわすれ堂", "沖縄の給付金・手当の申請準備シート一覧。持ち物チェックリストつき、印刷してそのまま窓口へ。", body, depth=1)


def main():
    with open(DATA, encoding="utf-8") as f:
        db = json.load(f)
    items = db["items"]
    updated = db.get("updated_at", "")

    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_page(items, updated))
    for it in items:
        d = os.path.join(OUT_DIR, it["id"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(kit_page(it, updated))
    print(f"生成完了: 準備シート{len(items)}ページ+一覧1ページ")


if __name__ == "__main__":
    main()
