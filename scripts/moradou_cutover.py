#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
moradou.jp の開通を実測し、開通していたら旧URL側の正規URLを新ドメインへ向ける。

議事_20260828 のウタガイ②「canonicalの切替はDNS開通・表示確認の**後**でなければ、
死んだドメインを正規URLとして検索エンジンに教えてしまう」を、人の判断ではなく
機械の実測で担保する。判定が1つでも欠けたら切り替えない。

判定(すべて満たしたときだけ「開通」):
  1. https://moradou.jp/ が 200 で返る(証明書も正規のもの)
  2. その中身に「もらいわすれ堂」がある
  3. その中身の canonical が https://moradou.jp/ を指している
     ← ドメイン業者の仮ページ(パーキング)を「開通」と誤認しないための決め手。
       仮ページはこちらのcanonicalを持てない
  4. https://moradou.jp/yamanashi/ が 200 で返る(山梨版まで配信されている)
  5. https://moradou.jp/sitemap.xml に moradou.jp のURLが入っている

「取れなかった(通信失敗)」と「中身が違う」は分けて記録する。通信失敗は
掲載が誤っている証拠にはならない(CLAUDE.md 再発防止メモ)。

使い方:
  python scripts/moradou_cutover.py --check       # 開通したか見るだけ(0=開通 / 2=まだ)
  python scripts/moradou_cutover.py --apply       # 開通していたら正規URLを切り替える
  python scripts/moradou_cutover.py --self-test   # 判定ロジックの自己テスト
"""
import argparse
import os
import re
import sys
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DOMAIN = "moradou.jp"
NEW_BASE = f"https://{DOMAIN}"
YAMANASHI_BASE = f"{NEW_BASE}/yamanashi"
TIMEOUT = 20
UA = "moradou-cutover/1.0 (+https://github.com/allgroup-inc/hojo-hq)"

# 開通と認めるための条件。(名前, パス, 中身に必ず含まれるもの)
CHECKS = [
    ("トップが開く", "/", ["もらいわすれ堂", f'rel="canonical" href="{NEW_BASE}/"']),
    ("山梨版が開く", "/yamanashi/", ["もらいわすれ堂"]),
    ("sitemapが新ドメイン", "/sitemap.xml", [f"<loc>{NEW_BASE}/"]),
]

NOT_LIVE = 2  # 「まだ開通していない」— 異常(1)とは区別する


def fetch(url):
    """(本文, エラー理由) を返す。取れたら理由はNone。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            if r.status != 200:
                return None, f"HTTP {r.status}"
            return r.read().decode("utf-8", errors="replace"), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, f"つながらない({e.reason})"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def judge(results):
    """results: [(名前, 本文 or None, エラー理由 or None, 必須文字列)] → (開通か, 行ごとの説明)"""
    lines, live = [], True
    for name, body, err, needles in results:
        if body is None:
            live = False
            lines.append(f"  ✗ {name}: 取得できない({err})")
            continue
        missing = [n for n in needles if n not in body]
        if missing:
            live = False
            lines.append(f"  ✗ {name}: 取得できたが中身が違う(見つからない: {missing})")
        else:
            lines.append(f"  ✓ {name}")
    return live, lines


def probe():
    results = []
    for name, path, needles in CHECKS:
        body, err = fetch(NEW_BASE + path)
        results.append((name, body, err, needles))
    return judge(results)


# ── 正規URLの切替 ───────────────────────────────────────────
# ページの canonical は2系統ある。
#   ① ジェネレーターが出すもの(area/kit/life/山梨の大半) → MOVED_TO で自動追従
#   ② 手書きのページ(沖縄の index/shindan/privacy/houkoku/teisei と山梨のトップ)
#      → 生成されないので、ここで直接書き換える
# ②を忘れると「ほとんどのページは新ドメインを指しているのに、入口のトップだけ
# 旧URLを指している」という、いちばん効くページだけ抜けた状態になる。
# そのため**両系統やったあとで、旧URLを指すcanonicalが1つも無いことを確かめる**。
SITE_TREES = [
    ("site/fukugiiro", "https://allgroup-inc.github.io/hojo-hq/fukugiiro", NEW_BASE),
    ("site/yamanashi", "https://allgroup-inc.github.io/hojo-hq/yamanashi", YAMANASHI_BASE),
]
_CANON = re.compile(r'(rel="canonical"\s+href=")([^"]*)(")')


def rewrite_canonical_html(text, old_base, new_base):
    """canonical属性の中だけを書き換える。ナビのリンク等には触らない
    (旧URL側のページは実際にそこに在り続けるので、リンクは旧URLのままが正しい)。"""
    def sub(m):
        url = m.group(2)
        if url.startswith(old_base):
            url = new_base + url[len(old_base):]
        return m.group(1) + url + m.group(3)
    return _CANON.sub(sub, text)


def rewrite_canonicals():
    """全HTMLのcanonicalを新ドメインへ。生成物も含めて当てる(冪等)。"""
    n = 0
    for rel_tree, old_base, new_base in SITE_TREES:
        tree = os.path.join(BASE, rel_tree)
        for root, dirs, files in os.walk(tree):
            for name in files:
                if not name.endswith(".html"):
                    continue
                fp = os.path.join(root, name)
                with open(fp, encoding="utf-8") as f:
                    body = f.read()
                out = rewrite_canonical_html(body, old_base, new_base)
                if out != body:
                    with open(fp, "w", encoding="utf-8") as f:
                        f.write(out)
                    n += 1
    return n


def stale_canonicals():
    """旧URLを指したままの canonical を持つページを返す(切替後に0であるべき)。"""
    bad = []
    for rel_tree, old_base, _new in SITE_TREES:
        tree = os.path.join(BASE, rel_tree)
        for root, dirs, files in os.walk(tree):
            for name in files:
                if not name.endswith(".html"):
                    continue
                fp = os.path.join(root, name)
                with open(fp, encoding="utf-8") as f:
                    body = f.read()
                for m in _CANON.finditer(body):
                    if m.group(2).startswith(old_base):
                        bad.append(os.path.relpath(fp, BASE))
                        break
    return sorted(bad)


TARGETS = [
    ("scripts/fg_seo.py", NEW_BASE),
    ("scripts/fg_yamanashi.py", YAMANASHI_BASE),
]
_MOVED_LINE = re.compile(r"^MOVED_TO = .*$", re.M)


def set_moved_to(text, value):
    """MOVED_TO の行を書き換える。行が無ければ例外(静かに何もしないのを防ぐ)。"""
    if not _MOVED_LINE.search(text):
        raise ValueError("MOVED_TO の行が見つかりません")
    new = "MOVED_TO = None" if value is None else f'MOVED_TO = "{value}"'
    return _MOVED_LINE.sub(new, text, count=1)


def current_moved_to(text):
    m = _MOVED_LINE.search(text)
    if not m:
        return "(行なし)"
    return m.group(0)


def apply_cutover():
    changed = []
    for rel, value in TARGETS:
        p = os.path.join(BASE, rel)
        with open(p, encoding="utf-8") as f:
            text = f.read()
        before = current_moved_to(text)
        after_text = set_moved_to(text, value)
        if after_text == text:
            print(f"[skip] {rel} は既に {before}")
            continue
        with open(p, "w", encoding="utf-8") as f:
            f.write(after_text)
        changed.append(rel)
        print(f"[変更] {rel}: {before} → MOVED_TO = \"{value}\"")
    return changed


def main_check(verbose=True):
    live, lines = probe()
    if verbose:
        print(f"[moradou_cutover] {NEW_BASE} の開通確認")
        print("\n".join(lines))
    if live:
        print("→ 開通しています")
        return 0
    print("→ まだ開通していません(切替はしません)")
    return NOT_LIVE


def main_apply():
    rc = main_check()
    if rc != 0:
        return rc
    changed = apply_cutover()
    n = rewrite_canonicals()
    print(f"[変更] 手書き・生成済みページの canonical: {n}ファイル")
    stale = stale_canonicals()
    if stale:
        print(f"::error::旧URLを指したままの canonical が {len(stale)} ページ残っています", file=sys.stderr)
        for f in stale[:20]:
            print(f"  NG {f}", file=sys.stderr)
        return 1
    if not changed and n == 0:
        print("→ 既に切替済みです。変更はありません")
        return 0
    print(f"→ 設定{len(changed)}ファイル + ページ{n}ファイルを変更しました。"
          "このあとページを再生成してください")
    return 0


# ── 自己テスト ────────────────────────────────────────────────
def self_test():
    ok = ng = 0

    def check(label, cond):
        nonlocal ok, ng
        if cond:
            ok += 1
        else:
            ng += 1
            print(f"  NG {label}")

    good_top = f'<html><link rel="canonical" href="{NEW_BASE}/">もらいわすれ堂</html>'
    good_ymn = "<html>もらいわすれ堂 山梨版</html>"
    good_map = f"<urlset><url><loc>{NEW_BASE}/kit/</loc></url></urlset>"

    def res(top=good_top, ymn=good_ymn, smap=good_map, errs=(None, None, None)):
        bodies = [top, ymn, smap]
        return [(n, bodies[i], errs[i], needles)
                for i, (n, _p, needles) in enumerate(CHECKS)]

    live, _ = judge(res())
    check("全部そろえば開通と判定する", live)

    live, lines = judge(res(top=None, errs=("つながらない(NXDOMAIN)", None, None)))
    check("トップが引けなければ開通としない", not live)
    check("通信失敗は『取得できない』と書く", "取得できない" in lines[0])

    # ドメイン業者の仮ページ: 200で返るがこちらのcanonicalは持てない
    parking = "<html><title>このドメインは取得されています</title></html>"
    live, lines = judge(res(top=parking))
    check("仮ページ(パーキング)を開通と誤認しない", not live)
    check("通信失敗ではなく『中身が違う』と書く", "中身が違う" in lines[0])

    # もらいわすれ堂の文字はあるが canonical が旧URLのまま = 配信前
    half = '<html><link rel="canonical" href="https://allgroup-inc.github.io/hojo-hq/fukugiiro/">もらいわすれ堂</html>'
    live, _ = judge(res(top=half))
    check("canonicalが旧URLのままなら開通としない", not live)

    live, _ = judge(res(ymn=None, errs=(None, "HTTP 404", None)))
    check("山梨版が無ければ開通としない", not live)

    live, _ = judge(res(smap="<urlset></urlset>"))
    check("sitemapが空なら開通としない", not live)

    live, _ = judge(res(smap="<loc>https://allgroup-inc.github.io/hojo-hq/fukugiiro/</loc>"))
    check("sitemapが旧URLのままなら開通としない", not live)

    check("『まだ』と『異常』の終了コードが違う", NOT_LIVE not in (0, 1))

    src = 'X = 1\nMOVED_TO = None\nY = 2\n'
    check("MOVED_TOを設定できる",
          set_moved_to(src, NEW_BASE) == f'X = 1\nMOVED_TO = "{NEW_BASE}"\nY = 2\n')
    check("Noneへ戻せる(切り戻し)",
          set_moved_to(set_moved_to(src, NEW_BASE), None) == src)
    check("他の行は触らない", "X = 1" in set_moved_to(src, NEW_BASE))
    try:
        set_moved_to("X = 1\n", NEW_BASE)
        check("MOVED_TOの行が無ければ例外", False)
    except ValueError:
        check("MOVED_TOの行が無ければ例外", True)

    # 実ファイルに MOVED_TO の行が本当にあるか(書き換え先が消えていないか)
    for rel, _v in TARGETS:
        p = os.path.join(BASE, rel)
        with open(p, encoding="utf-8") as f:
            check(f"{rel} に MOVED_TO の行がある", bool(_MOVED_LINE.search(f.read())))

    # canonical の書き換え
    old_b = "https://allgroup-inc.github.io/hojo-hq/fukugiiro"
    page = (f'<link rel="canonical" href="{old_b}/kit/abc/">'
            f'<a href="{old_b}/kit/abc/">リンク</a>')
    out = rewrite_canonical_html(page, old_b, NEW_BASE)
    check("canonicalは新ドメインへ",
          f'rel="canonical" href="{NEW_BASE}/kit/abc/"' in out)
    check("ナビのリンクは旧URLのまま(ページは実際そこに在る)",
          f'<a href="{old_b}/kit/abc/">' in out)
    check("2度かけても変わらない(冪等)",
          rewrite_canonical_html(out, old_b, NEW_BASE) == out)
    check("別ドメインのcanonicalには触らない",
          rewrite_canonical_html('<link rel="canonical" href="https://example.com/">',
                                 old_b, NEW_BASE)
          == '<link rel="canonical" href="https://example.com/">')
    check("トップ(末尾スラッシュのみ)も変換",
          f'href="{NEW_BASE}/"' in rewrite_canonical_html(
              f'<link rel="canonical" href="{old_b}/">', old_b, NEW_BASE))

    # 実ツリーに canonical を持つページが実在するか(対象ゼロで素通りしないこと)
    found = 0
    for rel_tree, _o, _n in SITE_TREES:
        for root, _d, files in os.walk(os.path.join(BASE, rel_tree)):
            for name in files:
                if name.endswith(".html"):
                    with open(os.path.join(root, name), encoding="utf-8") as f:
                        if _CANON.search(f.read()):
                            found += 1
    check(f"canonicalを持つページが実在する(見つかった数 {found})", found > 100)
    check("切替前は旧URLを指している(=まだ切替えていない)", len(stale_canonicals()) == found)

    print(f"自己テスト: OK {ok} / NG {ng}")
    return 1 if ng else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="開通したか見るだけ")
    ap.add_argument("--apply", action="store_true", help="開通していたら切り替える")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.apply:
        return main_apply()
    if a.check:
        return main_check()
    ap.error("--check / --apply / --self-test のいずれかを指定してください")


if __name__ == "__main__":
    sys.exit(main() or 0)
