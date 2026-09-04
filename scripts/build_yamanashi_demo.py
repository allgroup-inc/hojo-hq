#!/usr/bin/env python3
# もらいわすれ堂 山梨版の「デモ版」(Claude Artifact用・単一ファイル)を組み立てる。
#
# 目的: 本番公開前に、小柳さんがスマホから実物と同じ動きで確認できるようにする。
# 運用ルール(2026-09-03 小柳さん指示「常に最新の情報で管理される様に」):
#   site/fukugiiro/yamanashi/ 配下・data/fukugiiro/yamanashi_seido.json・
#   共有アセット(film.css / fg-base.css / icon.svg)を変更したら、
#   このスクリプトを実行し、下記のデモURLへ再公開して同じURLを最新に保つ。
#   デモURL(Claudeのアーティファクト。非公開・URL固定):
#     トップ:  https://claude.ai/code/artifact/ef7ee2fb-2d40-43ef-98be-0a6a3a23ace0
#     3分診断: https://claude.ai/code/artifact/84a7d9ab-d2b4-4821-bfc1-c8293f84ac60
#   再公開は Claude Code のセッションから Artifact ツールに url= を渡して行う。
#
# デモの性質:
#   - 計測(GA4)は無効化済み。デモの閲覧は本番の数字に混ざらない
#   - LINEボタンだけ本物(@630pbjqq)。その他の内部リンクは案内トーストを出す
#   - 本番公開(mainマージ)後は本番URLが正となり、このデモは廃止してよい
import base64, re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
YMN = ROOT / "site/fukugiiro/yamanashi"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "demo_out"

TOP_URL = "https://claude.ai/code/artifact/ef7ee2fb-2d40-43ef-98be-0a6a3a23ace0"
SHINDAN_URL = "https://claude.ai/code/artifact/84a7d9ab-d2b4-4821-bfc1-c8293f84ac60"

def data_uri(path, mime):
    return "data:%s;base64,%s" % (mime, base64.b64encode(path.read_bytes()).decode())

ICON = data_uri(ROOT / "site/fukugiiro/assets/icon.svg", "image/svg+xml")
FILM_CSS = (ROOT / "site/fukugiiro/assets/film.css").read_text()
FG_BASE_CSS = (ROOT / "site/fukugiiro/assets/fg-base.css").read_text()
YMN_FILM_JS = (YMN / "assets/ymn-film.js").read_text()
LOGIC_JS = (YMN / "shindan/logic.js").read_text()
DB = (ROOT / "data/fukugiiro/yamanashi_seido.json").read_text()

BAND = ('<div style="background:#B9502F;color:#fff;text-align:center;font-size:13px;'
        'padding:7px 10px;font-weight:700;letter-spacing:.08em">デモ版(確認用)— 本番のURLではありません</div>\n')

DEMO_JS = """
<script>
(function(){
  var t=document.createElement('div');
  t.style.cssText='position:fixed;left:50%;bottom:110px;transform:translateX(-50%);background:#333;color:#fff;padding:10px 16px;border-radius:8px;font-size:13px;z-index:999;display:none;max-width:86vw;text-align:center';
  document.body.appendChild(t);
  var timer=null;
  function toast(msg){ t.textContent=msg; t.style.display='block'; clearTimeout(timer); timer=setTimeout(function(){t.style.display='none';},2600); }
  document.addEventListener('click',function(e){
    var a=e.target&&e.target.closest?e.target.closest('a'):null; if(!a) return;
    var h=a.getAttribute('href')||'';
    if(h.indexOf('http')===0||h.indexOf('#')===0||h.indexOf('data:')===0||h.indexOf('mailto:')===0) return;
    e.preventDefault();
    toast('デモ版のため、このページは本番公開後に見られます');
  }, true);
})();
</script>
"""

def strip_doc(html):
    html = re.sub(r'<!DOCTYPE[^>]*>\s*', '', html, flags=re.I)
    html = re.sub(r'</?html[^>]*>\s*', '', html)
    html = re.sub(r'</?head>\s*', '', html)
    html = re.sub(r'</?body[^>]*>\s*', '', html)
    html = re.sub(r'<meta charset[^>]*>\s*', '', html, flags=re.I)
    html = re.sub(r'<meta name="viewport"[^>]*>\s*', '', html)
    html = re.sub(r'<meta name="description"[^>]*>\s*', '', html)
    html = re.sub(r'<meta property="og:[^>]*>\s*', '', html)
    html = re.sub(r'<link rel="canonical"[^>]*>\s*', '', html)
    html = re.sub(r'<link rel="icon"[^>]*>\s*', '', html)
    html = re.sub(r'<link rel="preconnect"[^>]*>\s*', '', html)
    html = re.sub(r'<script type="application/ld\+json">.*?</script>\s*', '', html, flags=re.S)
    return html

def must_replace(html, old, new, label):
    assert old in html, "見つからない: %s(サイト側の構造が変わった。デモビルダーの追従が必要)" % label
    return html.replace(old, new)

def build_top():
    html = strip_doc((YMN / "index.html").read_text())
    html = re.sub(r'<title>[^<]*</title>', '<title>もらいわすれ堂 山梨版(デモ)</title>', html)
    html = must_replace(html, '<link rel="stylesheet" href="../assets/film.css">',
                        '<style>\n%s\n</style>' % FILM_CSS, "film.cssリンク")
    for name in ["yakei.jpg", "fuji.jpg", "budo.jpg", "momo.jpg"]:
        html = must_replace(html, 'assets/film/%s' % name,
                            data_uri(YMN / "assets/film" / name, "image/jpeg"), name)
    html = html.replace('src="../assets/icon.svg"', 'src="%s"' % ICON)
    html = html.replace('<script src="../analytics-config.js"></script>', '')
    html = must_replace(html, '<script src="../assets/fg-analytics.js"></script>',
                        '<script>window.fgTrack=function(){};</script>', "計測スクリプト")
    html = must_replace(html, '<script src="assets/ymn-film.js" defer></script>', '', "フィルムJS")
    html = must_replace(html, 'fetch("../../data/fukugiiro/yamanashi_seido.json").then(function(r){return r.json()})',
                        'Promise.resolve(window.FG_DB)', "制度データfetch")
    html = '<script>window.FG_DB=%s;</script>\n' % DB + html
    html = html.replace('href="shindan/?resume=1"', 'href="%s"' % SHINDAN_URL)
    html = html.replace('href="shindan/"', 'href="%s"' % SHINDAN_URL)
    html = html.replace('href="../../go/ymn-top/"',
                        'href="https://line.me/R/ti/p/%40630pbjqq" target="_blank" rel="noopener"')
    html = BAND + html + '\n<script>\n' + YMN_FILM_JS + '\n</script>\n' + DEMO_JS
    (OUT / "demo_yamanashi_top.html").write_text(html)
    print("top:", len(html), "bytes")

def build_shindan():
    html = strip_doc((YMN / "shindan/index.html").read_text())
    html = re.sub(r'<title>[^<]*</title>', '<title>3分診断 山梨版(デモ)</title>', html)
    html = must_replace(html, '<link rel="stylesheet" href="../../assets/fg-base.css">',
                        '<style>\n%s\n</style>' % FG_BASE_CSS, "fg-base.cssリンク")
    html = html.replace('src="../../assets/icon.svg"', 'src="%s"' % ICON)
    html = html.replace('<script src="../../analytics-config.js"></script>', '')
    html = must_replace(html, '<script src="../../assets/fg-analytics.js"></script>',
                        '<script>window.fgTrack=function(){};</script>', "計測スクリプト")
    html = must_replace(html, '<script src="logic.js"></script>',
                        '<script>\n%s\n</script>' % LOGIC_JS, "logic.js")
    html = must_replace(html, 'fetch("../../../data/fukugiiro/yamanashi_seido.json").then(function(r){return r.json()})',
                        'Promise.resolve(window.FG_DB)', "制度データfetch")
    html = '<script>window.FG_DB=%s;</script>\n' % DB + html
    html = html.replace('https://allgroup-inc.github.io/hojo-hq/go/ymn-shindan/',
                        'https://line.me/R/ti/p/%40630pbjqq')
    html = html.replace('href="../"', 'href="%s"' % TOP_URL)
    html = html.replace('href="./"', 'href="%s"' % TOP_URL)
    html = BAND + html + DEMO_JS
    (OUT / "demo_yamanashi_shindan.html").write_text(html)
    print("shindan:", len(html), "bytes")

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    build_top()
    build_shindan()
    print("出力先:", OUT)
