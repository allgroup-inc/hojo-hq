#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
一次ソース(公式ページ)を取得して、探している語の前後をそのまま抜き出す。

なぜ要るか(2026-09-24):
  投稿済みの内容を公式ページと突き合わせたいのに、開発環境からは egress 制限で
  官公庁・自治体のページを開けない。検索結果の要約で代用すると、それは原文ではない。
  GitHub Actions は外に出られるので、**原文を取りに行く場所**をここに用意する。

原則:
  - ページの文言を**そのまま**出す。要約も解釈もしない(判断は人がする)
  - 「取得できなかった」と「語が見つからなかった」は必ず分ける
    (通信失敗は、掲載が誤っている証拠にならない)
  - 文字コードは宣言を優先して推定する(cp932 は EUC-JP を例外なく読めてしまう)

使い方:
  python scripts/quote_source.py --url URL [--url URL2] --word 現況届 --word 11月分
  python scripts/quote_source.py --self-test
"""
import argparse
import re
import sys
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TIMEOUT = 25
UA = "moradou-source-quote/1.0 (+https://github.com/allgroup-inc/hojo-hq)"
CONTEXT = 90  # 前後に出す文字数

_META_CHARSET = re.compile(rb'charset["\s=:]+([A-Za-z0-9_\-]+)', re.I)


def sniff_charset(raw, header_charset=None):
    if header_charset:
        return header_charset
    m = _META_CHARSET.search(raw[:4096])
    return m.group(1).decode("ascii", "ignore") if m else None


def _jp_score(text):
    head = text[:4000]
    jp = sum(1 for c in head if 0x3040 <= ord(c) <= 0x30FF or 0x4E00 <= ord(c) <= 0x9FFF)
    bad = sum(1 for c in head if c == "�" or 0xE000 <= ord(c) <= 0xF8FF)
    return jp - bad * 5


def decode_html(raw, header_charset=None):
    declared = sniff_charset(raw, header_charset)
    cands = ([declared] if declared else []) + ["utf-8", "euc_jp", "shift_jis", "cp932"]
    best, best_score = None, None
    for enc in cands:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        score = _jp_score(text)
        if best_score is None or score > best_score:
            best, best_score = text, score
        if enc == declared and score > 0:
            break
    return best if best is not None else raw.decode("utf-8", errors="replace")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            cs = None
            try:
                cs = r.headers.get_content_charset()
            except Exception:
                pass
            return decode_html(raw, cs), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, f"つながらない({e.reason})"
    except Exception as e:
        return None, f"{type(e).__name__}"


def to_text(html):
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&#39;", "'")):
        html = html.replace(a, b)
    return re.sub(r"[ \t　]+", " ", html)


def quotes(text, word, context=CONTEXT, limit=3):
    out = []
    for m in re.finditer(re.escape(word), text):
        s = max(0, m.start() - context)
        e = min(len(text), m.end() + context)
        out.append(re.sub(r"\s*\n\s*", " ", text[s:e]).strip())
        if len(out) >= limit:
            break
    return out


def run(urls, words, fetcher=fetch):
    lines, missing, unreachable = [], [], []
    for url in urls:
        html, err = fetcher(url)
        lines.append(f"\n── {url}")
        if html is None:
            lines.append(f"   [取得できず] {err} ※ここから内容の正誤は判断できません")
            unreachable.append(url)
            continue
        text = to_text(html)
        lines.append(f"   [取得OK] 本文 {len(text)}文字")
        for w in words:
            qs = quotes(text, w)
            if not qs:
                lines.append(f"   ・「{w}」… 見つかりません")
                missing.append((url, w))
                continue
            for q in qs:
                lines.append(f"   ・「{w}」… …{q}…")
    return "\n".join(lines), missing, unreachable


def self_test():
    ok = bad = 0

    def check(label, cond):
        nonlocal ok, bad
        if cond:
            ok += 1
        else:
            bad += 1
            print(f"  NG {label}")

    html = ("<html><head><meta charset='utf-8'></head><body>"
            "<script>現況届 ダミー</script>"
            "<p>毎年8月中に、8月1日時点の養育状況を確認するため現況届が必要です。</p>"
            "<p>届出がない場合は11月分以降の手当を受けられません。</p></body></html>")
    text = to_text(html)
    check("タグを落とす", "<p>" not in text)
    check("scriptの中は本文に含めない", "ダミー" not in text)

    q = quotes(text, "現況届")
    check("語の前後を抜き出す", q and "8月1日時点" in q[0])
    check("見つからない語は空", quotes(text, "10月30日") == [])

    out, missing, unreach = run(["https://x/a"], ["現況届", "10月30日"],
                                fetcher=lambda u: (html, None))
    check("取得OKと書く", "[取得OK]" in out)
    check("見つからない語を数える", missing == [("https://x/a", "10月30日")])
    check("取得できたURLは未到達に入れない", unreach == [])

    out, missing, unreach = run(["https://x/b"], ["現況届"],
                                fetcher=lambda u: (None, "HTTP 403"))
    check("取得失敗を分けて書く", "[取得できず]" in out and "403" in out)
    check("取得失敗は『見つからない』に混ぜない", missing == [])
    check("取得失敗を数える", unreach == ["https://x/b"])
    check("取得失敗から正誤を判断しないと明記", "判断できません" in out)

    euc = "現況届は8月です".encode("euc_jp")
    check("EUC-JPを文字化けさせない",
          "現況届" in decode_html(b"<meta charset='euc-jp'>" + euc))
    check("宣言が無くても日本語を優先して選ぶ", "現況届" in decode_html(euc))
    check("UTF-8はそのまま読む", "現況届" in decode_html("現況届".encode("utf-8")))

    check("HTML実体参照を戻す", "&" in to_text("<p>A&amp;B</p>"))

    print(f"自己テスト: OK {ok} / NG {bad}")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--word", action="append", default=[])
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not (a.url and a.word):
        ap.error("--url と --word を指定してください")
    out, missing, unreach = run(a.url, a.word)
    print(out)
    print(f"\n見つからなかった語 {len(missing)}件 / 取得できなかったURL {len(unreach)}件")
    print("※取得できなかったものは、内容が誤っている証拠にはなりません")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
