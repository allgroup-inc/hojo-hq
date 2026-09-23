#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂 独自ドメイン(moradou.jp)配信ツリーの組み立て
議事: docs/議事_20260828_独自ドメインmoradou.md(2026-08-28 小柳さん決裁)

site/ のうち「もらいわすれ堂のもの」だけを取り出し、URL基底を独自ドメインへ
書き換えた配信用ツリーを作る。allgroup-inc/moradou(配信専用リポジトリ)へ
そのまま push できる形にする。

  site/fukugiiro/   → /            (沖縄版=トップ)
  site/yamanashi/   → /yamanashi/  (山梨版。2026-09-20 一本化で site/ 直下へ移動)
  site/go/fg-*      → /go/fg-*     (もらいわすれ堂のLINE導線のみ)
  site/go/ymn-*     → /go/ymn-*

ブランド分離(CLAUDE.md): 「沖縄企業のミカタ」(株式会社GLOW)のページ・
/go/ チャネル・トップは**持ち込まない**。持ち込まれていないことを最後に検査する。

なぜ生成側ではなく配信時に書き換えるか:
  公開ページ内のURLは3種類の基底しか使っていない(下の REWRITES)。配信時の
  前置き換え1箇所で canonical・OGP・パンくず・JSON-LD・sitemap・LINE導線が
  すべて追従する。40本のジェネレーターを触らないので、旧URL側(github.io)の
  挙動は一切変わらない = 可逆。

使い方:
  python scripts/deploy_moradou.py --out /tmp/moradou     # 配信ツリーを作る
  python scripts/deploy_moradou.py --out /tmp/moradou --domain example.jp
  python scripts/deploy_moradou.py --self-test            # 検査そのものの自己テスト
"""
import argparse
import os
import re
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SITE = os.path.join(BASE, "site")

# 旧URL基底(公開ページはこの3つしか使っていない。increase したら verify が落ちる)
OLD_ROOT = "https://allgroup-inc.github.io/hojo-hq"
OLD_FUKUGIIRO = f"{OLD_ROOT}/fukugiiro"
OLD_YAMANASHI = f"{OLD_ROOT}/yamanashi"
OLD_GO = f"{OLD_ROOT}/go"
# ホスト名だけの記述(例: analytics-config.js の data-domain)。接頭辞3種を当てた後に残った分を拾う
OLD_HOST = "allgroup-inc.github.io"

# 書き換え対象の拡張子(画像・フォントは触らない)
TEXT_EXT = {".html", ".htm", ".xml", ".txt", ".json", ".js", ".css", ".svg", ".webmanifest", ".md"}

# もらいわすれ堂の /go/ チャネル接頭辞。ミカタ(site/shindan/ig/fb/card/insurance-*)は除く
GO_PREFIXES = ("fg-", "ymn-")

# 配信ツリーに現れてはいけない表記(ブランド混同の検知)
FORBIDDEN_IN_OUTPUT = ["沖縄企業のミカタ", OLD_ROOT, OLD_HOST]


def rewrites(domain):
    """旧URL基底 → 新URL基底。長い順に適用する(前方一致の食い合いを防ぐ)。"""
    new_root = f"https://{domain}"
    pairs = [
        (OLD_FUKUGIIRO, new_root),
        (OLD_YAMANASHI, f"{new_root}/yamanashi"),
        (OLD_GO, f"{new_root}/go"),
        (OLD_HOST, domain),
    ]
    return sorted(pairs, key=lambda p: -len(p[0]))


def rewrite_text(text, domain):
    for old, new in rewrites(domain):
        text = text.replace(old, new)
    return text


# 既知のURL基底(第1階層)。ここに無いパスが公開ページに現れたら、書き換え規則が
# 追いついていないということなので配信を止める。
# ← ホスト名だけの規則(OLD_HOST)が先に当たると /hojo-hq/ が残った壊れたURLになり、
#   しかも "allgroup-inc" が消えるので verify() では捕まえられない。ここで止める。
KNOWN_SEGMENTS = {"fukugiiro", "yamanashi", "go", ""}
_HOJO_URL = re.compile(r"https://allgroup-inc\.github\.io/hojo-hq/([A-Za-z0-9._-]*)")


def unknown_bases(text):
    """text の中の、書き換え規則が用意されていないURL基底を返す。"""
    return sorted({seg for seg in _HOJO_URL.findall(text) if seg not in KNOWN_SEGMENTS})


def is_text(path):
    return os.path.splitext(path)[1].lower() in TEXT_EXT


def copy_tree(src, dst, domain, stats):
    """src を dst へ複製し、テキストファイルはURL基底を書き換える。"""
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != ".git"]
        rel = os.path.relpath(root, src)
        out_dir = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(out_dir, exist_ok=True)
        for name in files:
            s = os.path.join(root, name)
            d = os.path.join(out_dir, name)
            if is_text(s):
                with open(s, encoding="utf-8") as f:
                    body = f.read()
                unknown = unknown_bases(body)
                if unknown:
                    stats["unknown"].append((os.path.relpath(s, BASE), unknown))
                with open(d, "w", encoding="utf-8") as f:
                    f.write(rewrite_text(body, domain))
                stats["rewritten"] += 1
            else:
                shutil.copy2(s, d)
                stats["copied"] += 1


def filter_sitemap(xml, domain):
    """sitemap から もらいわすれ堂 以外(ミカタの themes/ とトップ)を落とし、URLを書き換える。"""
    keep = []
    for block in re.findall(r"<url>.*?</url>", xml, re.S):
        loc = re.search(r"<loc>(.*?)</loc>", block, re.S)
        if not loc:
            continue
        u = loc.group(1).strip()
        if u.startswith(OLD_FUKUGIIRO + "/") or u.startswith(OLD_YAMANASHI + "/"):
            keep.append(rewrite_text(block, domain))
    head = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
    return head + "\n".join(keep) + "\n</urlset>\n"


README = """# moradou（配信専用）

もらいわすれ堂（株式会社フクギイロ）の公開サイト {domain} の配信先です。

**このリポジトリを直接編集しないでください。** 中身は
[allgroup-inc/hojo-hq](https://github.com/allgroup-inc/hojo-hq) の `site/` から
`scripts/deploy_moradou.py` が自動生成し、`moradou-deploy` ワークフローが
main への push ごとに丸ごと入れ替えます。手で直した分は次の配信で消えます。

- 本文・データの修正 → hojo-hq 側
- 公開設定（Pages / Custom domain）→ このリポジトリの Settings
- 経緯 → hojo-hq の `docs/議事_20260828_独自ドメインmoradou.md`
"""

ROBOTS = """User-agent: *
Allow: /
Disallow: /go/

Sitemap: https://{domain}/sitemap.xml
"""

NOT_FOUND = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>ページが見つかりませんでした｜もらいわすれ堂</title>
<style>
body{{margin:0;font-family:"Noto Sans JP","Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,sans-serif;
  background:#FFFBF4;color:#3B322B;font-size:17px;line-height:1.9;
  display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px;box-sizing:border-box}}
.card{{max-width:560px;width:100%;background:#fff;border:1px solid #EAE0D2;border-radius:20px;
  padding:34px 28px;text-align:center}}
h1{{font-size:1.3rem;margin:0 0 10px;line-height:1.6;text-wrap:balance;word-break:auto-phrase}}
p{{margin:0 0 8px;color:#6d5c4d;font-size:.95rem}}
.links{{margin-top:22px;display:grid;gap:10px}}
.links a{{display:block;padding:14px 18px;min-height:44px;box-sizing:border-box;
  border:2px solid #C8BBA8;border-radius:12px;color:#3B322B;text-decoration:none;font-weight:700}}
.links a.main{{background:#B9502F;border-color:#B9502F;color:#fff}}
</style>
</head>
<body>
<div class="card">
<h1>ページが見つかりませんでした</h1>
<p>アドレスが変わったか、入力に誤りがあるかもしれません。</p>
<div class="links">
<a class="main" href="https://{domain}/">もらいわすれ堂 トップ</a>
<a href="https://{domain}/shindan/">3分診断でさがす</a>
<a href="https://{domain}/yamanashi/">山梨版</a>
</div>
</div>
</body>
</html>
"""


def verify(out_dir):
    """配信ツリーに旧URL・他ブランドが残っていないか検査する。
    ここで落とすことで「書き換え漏れが成功として通る」事故を防ぐ。"""
    bad = []
    for root, dirs, files in os.walk(out_dir):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            p = os.path.join(root, name)
            if not is_text(p):
                continue
            with open(p, encoding="utf-8", errors="replace") as f:
                body = f.read()
            for ng in FORBIDDEN_IN_OUTPUT:
                if ng in body:
                    # 1ファイル1件だけ報告する(旧URLはホスト名規則にも当たるため二重計上になる)
                    bad.append((os.path.relpath(p, out_dir), ng))
                    break
    return bad


def build(out_dir, domain):
    for need in ("fukugiiro", "yamanashi", "go", "sitemap.xml"):
        if not os.path.exists(os.path.join(SITE, need)):
            print(f"::error::site/{need} が無い。先にサイトを生成してください", file=sys.stderr)
            return 1

    # .git と CNAME 以外を一旦片付ける(配信先リポジトリの上で動かす前提)
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        if name in (".git",):
            continue
        p = os.path.join(out_dir, name)
        shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)

    stats = {"rewritten": 0, "copied": 0, "unknown": []}
    copy_tree(os.path.join(SITE, "fukugiiro"), out_dir, domain, stats)
    copy_tree(os.path.join(SITE, "yamanashi"), os.path.join(out_dir, "yamanashi"), domain, stats)

    go_src = os.path.join(SITE, "go")
    channels = sorted(c for c in os.listdir(go_src)
                      if c.startswith(GO_PREFIXES) and os.path.isdir(os.path.join(go_src, c)))
    for ch in channels:
        copy_tree(os.path.join(go_src, ch), os.path.join(out_dir, "go", ch), domain, stats)

    with open(os.path.join(SITE, "sitemap.xml"), encoding="utf-8") as f:
        sm = filter_sitemap(f.read(), domain)
    with open(os.path.join(out_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(sm)
    with open(os.path.join(out_dir, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(ROBOTS.format(domain=domain))
    with open(os.path.join(out_dir, "404.html"), "w", encoding="utf-8") as f:
        f.write(NOT_FOUND.format(domain=domain))
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(README.format(domain=domain))
    with open(os.path.join(out_dir, "CNAME"), "w", encoding="utf-8") as f:
        f.write(domain + "\n")
    open(os.path.join(out_dir, ".nojekyll"), "w").close()

    if stats["unknown"]:
        print(f"::error::書き換え規則の無いURL基底が {len(stats['unknown'])} ファイルにあります。"
              f"deploy_moradou.py の rewrites() に追加してください", file=sys.stderr)
        for path, segs in stats["unknown"][:20]:
            print(f"  NG {path}: /hojo-hq/{{{', '.join(segs)}}}/", file=sys.stderr)
        return 1

    bad = verify(out_dir)
    n_urls = sm.count("<loc>")
    print(f"[deploy_moradou] domain={domain} 書換{stats['rewritten']}ファイル / "
          f"複製{stats['copied']}ファイル / go {len(channels)}チャネル / sitemap {n_urls}件")
    if bad:
        print(f"::error::配信ツリーに残ってはいけない文字列が {len(bad)} 件あります", file=sys.stderr)
        for path, ng in bad[:20]:
            print(f"  NG {path}: {ng}", file=sys.stderr)
        return 1
    print("[deploy_moradou] 検査OK(旧URL残存なし・他ブランド混入なし)")
    return 0


# ── 自己テスト ────────────────────────────────────────────────
def self_test():
    ok, ng = 0, 0

    def check(label, cond):
        nonlocal ok, ng
        if cond:
            ok += 1
        else:
            ng += 1
            print(f"  NG {label}")

    d = "moradou.jp"
    check("fukugiiro基底がルートになる",
          rewrite_text(f"{OLD_FUKUGIIRO}/shindan/", d) == "https://moradou.jp/shindan/")
    check("末尾スラッシュなしも変換",
          rewrite_text(OLD_FUKUGIIRO, d) == "https://moradou.jp")
    check("山梨基底は /yamanashi/ 配下",
          rewrite_text(f"{OLD_YAMANASHI}/kit/", d) == "https://moradou.jp/yamanashi/kit/")
    check("go基底は /go/ 配下",
          rewrite_text(f"{OLD_GO}/fg-kit/", d) == "https://moradou.jp/go/fg-kit/")
    check("3基底が混在しても全部変換",
          rewrite_text(f"{OLD_FUKUGIIRO}/ {OLD_YAMANASHI}/ {OLD_GO}/", d)
          == "https://moradou.jp/ https://moradou.jp/yamanashi/ https://moradou.jp/go/")
    check("無関係なURLは触らない",
          rewrite_text("https://www.instagram.com/moradou.okinawa/", d)
          == "https://www.instagram.com/moradou.okinawa/")
    check("ドメインを変えれば追従する",
          rewrite_text(f"{OLD_FUKUGIIRO}/", "example.jp") == "https://example.jp/")
    check("長い基底が先に適用される(前方一致の食い合いなし)",
          [p[0] for p in rewrites(d)][0] == OLD_FUKUGIIRO)
    check("ホスト名だけの規則は最後に適用される",
          [p[0] for p in rewrites(d)][-1] == OLD_HOST)
    check("ホスト名だけの記述も新ドメインになる",
          rewrite_text('data-domain="allgroup-inc.github.io"', d) == 'data-domain="moradou.jp"')
    check("ホスト名規則がパス付きURLを壊さない",
          rewrite_text(f"{OLD_GO}/fg-kit/", d) == "https://moradou.jp/go/fg-kit/")

    check("未知の基底: 既知の3種は検知しない",
          unknown_bases(f"{OLD_FUKUGIIRO}/ {OLD_YAMANASHI}/ {OLD_GO}/ {OLD_ROOT}/") == [])
    check("未知の基底: 新しい第1階層を検知する",
          unknown_bases(f"{OLD_ROOT}/themes/abc/") == ["themes"])
    check("未知の基底: 複数を並べて返す",
          unknown_bases(f"{OLD_ROOT}/staff/ {OLD_ROOT}/nobishiro/") == ["nobishiro", "staff"])
    check("未知の基底: 無関係なURLは拾わない",
          unknown_bases("https://example.com/hojo-hq/themes/") == [])

    check("テキスト判定: html", is_text("a/b.html"))
    check("テキスト判定: 大文字拡張子", is_text("a/B.HTML"))
    check("テキスト判定: 画像は対象外", not is_text("a/b.jpg"))
    check("テキスト判定: webpは対象外", not is_text("a/b.webp"))

    sample = (
        '<?xml version="1.0"?><urlset>'
        f"<url><loc>{OLD_FUKUGIIRO}/</loc></url>"
        f"<url><loc>{OLD_YAMANASHI}/kit/</loc></url>"
        f"<url><loc>{OLD_ROOT}/themes/abc/</loc></url>"
        f"<url><loc>{OLD_ROOT}/</loc></url>"
        "</urlset>")
    sm = filter_sitemap(sample, d)
    check("sitemap: もらいわすれ堂の2件だけ残る", sm.count("<loc>") == 2)
    check("sitemap: ミカタのthemesを落とす", "themes" not in sm)
    check("sitemap: URLが書き換わる", "https://moradou.jp/yamanashi/kit/" in sm)
    check("sitemap: 旧URLが残らない", OLD_ROOT not in sm)

    check("404はもらいわすれ堂の導線のみ",
          "https://moradou.jp/shindan/" in NOT_FOUND.format(domain=d)
          and "ミカタ" not in NOT_FOUND.format(domain=d))
    check("robotsのSitemapが新ドメイン",
          "Sitemap: https://moradou.jp/sitemap.xml" in ROBOTS.format(domain=d))
    check("robotsは /go/ を除外", "Disallow: /go/" in ROBOTS.format(domain=d))
    check("READMEに直接編集しない旨がある", "直接編集しないでください" in README.format(domain=d))
    check("READMEは .md なので書換対象(旧URLが混ざらない)",
          is_text("README.md") and OLD_ROOT not in README.format(domain=d))

    check("goチャネルの採用接頭辞にミカタが入らない",
          not any("site".startswith(p) or "insurance-shindan".startswith(p) for p in GO_PREFIXES))
    check("goチャネルの採用接頭辞にもらいわすれ堂が入る",
          all(any(c.startswith(p) for p in GO_PREFIXES) for c in ("fg-kit", "ymn-top")))

    # verify() が実際に検知することを、壊して確かめる
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        with open(os.path.join(t, "clean.html"), "w", encoding="utf-8") as f:
            f.write("<p>https://moradou.jp/</p>")
        check("verify: きれいなら0件", verify(t) == [])
        with open(os.path.join(t, "dirty.html"), "w", encoding="utf-8") as f:
            f.write(f"<a href='{OLD_FUKUGIIRO}/'>旧URL</a>")
        check("verify: 旧URL残存を検知", len(verify(t)) == 1)
        with open(os.path.join(t, "brand.html"), "w", encoding="utf-8") as f:
            f.write("<p>沖縄企業のミカタ</p>")
        check("verify: 他ブランド混入を検知", len(verify(t)) == 2)
        with open(os.path.join(t, "host.js"), "w", encoding="utf-8") as f:
            f.write(f'data-domain="{OLD_HOST}"')
        check("verify: ホスト名だけの残存も検知", len(verify(t)) == 3)
        with open(os.path.join(t, "x.jpg"), "w", encoding="utf-8") as f:
            f.write(OLD_FUKUGIIRO)
        check("verify: 画像は検査しない", len(verify(t)) == 3)

    print(f"自己テスト: OK {ok} / NG {ng}")
    return 1 if ng else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="配信ツリーの出力先")
    ap.add_argument("--domain", default="moradou.jp")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.out:
        ap.error("--out か --self-test を指定してください")
    return build(os.path.abspath(a.out), a.domain)


if __name__ == "__main__":
    sys.exit(main() or 0)
