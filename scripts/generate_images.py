#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq デザイン部(エガクさん) — 投稿画像ジェネレータ
posts/launch/*.md の「## 画像に載せる文言(タイトル/サブ/数字)」を読み取り、
ブランド配色の 1080x1080 画像を posts/images/ に生成する(Instagram正方形)。

- 依存: Pillow（CIでは fonts-noto-cjk を apt install）
- フォント: Noto CJK(Linux) / Yu Gothic・Meiryo(Windows) を自動探索
- 出力は決定論的(タイムスタンプ非埋め込み)なので、内容が変わらない限り差分は出ない
"""
import glob
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(__file__)
POSTS_DIR = os.path.join(BASE_DIR, "..", "posts", "launch")
OUT_DIR = os.path.join(BASE_DIR, "..", "posts", "images")
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "subsidies.json")

# ブランド表記(全画像共通)。「何の会社か一目で分かる」ための日本語名を必ず載せる。
BRAND_JA = "沖縄企業のミカタ"
# プロフィール遷移CTA(全画像共通)。Meta一次情報上、プロフィール遷移は配信量の予測ターゲット
# (docs/SNS投稿設計_調査結果.md ❶)。フィード上は1枚ずつ流れるため、各画像を自己完結させる。
def _load_count():
    try:
        import json
        with open(DATA_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("count") or len(d.get("items", []))
    except Exception:
        return None

W = H = 1080
PAD = 96

# ブランド配色(公開サイト index.html に準拠)
BG_TOP = (2, 28, 48)       # #021c30
BG_BOTTOM = (0, 51, 92)    # #00335c
GOLD = (248, 136, 0)       # #F88800
WHITE = (247, 245, 241)    # #F7F5F1
MUTED = (176, 196, 214)    # 白の淡色

SITE = "沖縄企業のミカタ ｜ allgroup-inc.github.io/hojo-hq"

# フォント候補(太字 / 標準)。先頭から存在するものを使用。
BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
]
REG_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/YuGothR.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
]


def find_font(cands):
    for p in cands:
        if os.path.exists(p):
            return p
    return None


BOLD_PATH = find_font(BOLD_CANDIDATES)
REG_PATH = find_font(REG_CANDIDATES) or BOLD_PATH
if not BOLD_PATH:
    print("[error] 日本語フォントが見つかりません。CIでは fonts-noto-cjk を install してください。", file=sys.stderr)
    sys.exit(2)


def font(bold: bool, size: int):
    return ImageFont.truetype(BOLD_PATH if bold else REG_PATH, size)


def text_w(draw, s, f):
    return draw.textlength(s, font=f)


def fit_font(draw, s, bold, max_w, start, min_size=28):
    """max_w に収まる最大サイズのフォントを返す。"""
    size = start
    while size > min_size:
        f = font(bold, size)
        if text_w(draw, s, f) <= max_w:
            return f
        size -= 4
    return font(bold, min_size)


# 禁則処理: 行頭にきてはいけない文字(句読点・閉じ括弧・長音・小書き仮名)
NO_LINE_START = "、。，．・：；？！」』）］｝〕〉》ーゝゞぁぃぅぇぉっゃゅょゎ"
# 禁則処理: 行末にきてはいけない文字(開き括弧)
NO_LINE_END = "「『（［｛〔〈《"


def wrap(draw, s, f, max_w):
    """CJK対応の文字単位ワードラップ(基本的な禁則処理つき)。

    句読点や閉じ括弧が行頭に落ちると読みづらいため、
    その場合は直前の1文字ごと次の行へ送る。
    """
    lines, cur = [], ""
    for ch in s:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if text_w(draw, cur + ch, f) <= max_w:
            cur += ch
            continue
        # ここで折り返す必要がある。禁則にかかる場合は直前の文字ごと送る
        if len(cur) > 1 and (ch in NO_LINE_START or cur[-1] in NO_LINE_END):
            lines.append(cur[:-1])
            cur = cur[-1] + ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def gradient_bg():
    img = Image.new("RGB", (W, H), BG_TOP)
    top, bot = BG_TOP, BG_BOTTOM
    for y in range(H):
        t = y / (H - 1)
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        img.paste((r, g, b), (0, y, W, y + 1))
    return img


def parse_post(path):
    text = open(path, encoding="utf-8").read()
    def grab(label):
        m = re.search(rf"- {label}:\s*(.+)", text)
        return m.group(1).strip() if m else ""
    return {
        "title": grab("タイトル"),
        "sub": grab("サブ"),
        "number": grab("数字"),
        "badge": grab("バッジ"),
    }


def render(post, out_path):
    img = gradient_bg()
    d = ImageDraw.Draw(img)
    max_w = W - PAD * 2

    # 上部: 日本語サービス名(大)＋ローマ字(小)＋金のライン
    # 「何の会社か一目で分かる」ため、全画像に日本語名を大きく載せる(②への対応)
    bn = font(True, 44)
    d.text((PAD, PAD), BRAND_JA, font=bn, fill=WHITE)
    eb = font(True, 24)
    d.text((PAD, PAD + 58), "OKINAWA KIGYO NO MIKATA｜補助金・助成金 情報", font=eb, fill=GOLD)
    d.line([(PAD, PAD + 96), (PAD + 220, PAD + 96)], fill=GOLD, width=4)

    # バッジ(予告カード等): 右上に金枠のピル
    if post.get("badge"):
        bf = font(True, 28)
        tw = text_w(d, post["badge"], bf)
        bw, bh = int(tw + 56), 56
        bx, by = W - PAD - bw, PAD - 6
        d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh // 2,
                            outline=GOLD, width=3)
        d.text((bx + 28, by + (bh - bf.size) // 2 - 2), post["badge"], font=bf, fill=GOLD)

    # 中央ブロックを縦積みで配置(下部CTA帯と重ならない範囲に収める)
    y = 300

    # 数字(大・金)
    if post["number"]:
        nf = fit_font(d, post["number"], True, max_w, start=150, min_size=52)
        d.text((PAD, y), post["number"], font=nf, fill=GOLD)
        y += nf.size + 40

    # タイトル(白・太)
    if post["title"]:
        tf = font(True, 66)
        for ln in wrap(d, post["title"], tf, max_w):
            d.text((PAD, y), ln, font=tf, fill=WHITE)
            y += int(tf.size * 1.28)
        y += 16

    # サブ(淡色)。1行に収まるよう自動縮小し、末尾の「…」だけが次行に落ちるのを防ぐ
    if post["sub"]:
        sf = fit_font(d, post["sub"], False, max_w, start=40, min_size=30)
        for ln in wrap(d, post["sub"], sf, max_w):
            d.text((PAD, y), ln, font=sf, fill=MUTED)
            y += int(sf.size * 1.3)

    # 下部CTA帯: 余白を埋め、全画像でプロフィール遷移を促す(②の余白解消＋❶のプロフィール遷移)
    cnt = _load_count()
    cta_head = "プロフィールのリンクから"
    cta_main = (f"掲載{cnt}件を、登録なしで今すぐチェック" if cnt
                else "掲載中の制度を、登録なしで今すぐチェック")
    band_h = 208
    band_top = H - PAD - band_h
    d.rounded_rectangle([PAD, band_top, W - PAD, band_top + band_h],
                        radius=24, fill=GOLD)
    cx = PAD + 44
    cy = band_top + 34
    hf = font(True, 30)
    d.text((cx, cy), "▶  " + cta_head, font=hf, fill=(2, 28, 48))
    cy += 46
    mf = fit_font(d, cta_main, True, max_w - 88, start=42, min_size=30)
    d.text((cx, cy), cta_main, font=mf, fill=(2, 28, 48))
    cy += mf.size + 18
    uf = font(False, 26)
    d.text((cx, cy), "@okinawa_mikata ｜ allgroup-inc.github.io/hojo-hq", font=uf, fill=(2, 28, 48))

    img.save(out_path, "PNG", optimize=True)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    md_files = sorted(glob.glob(os.path.join(POSTS_DIR, "*.md")))
    if not md_files:
        print(f"[warn] 投稿mdが見つかりません: {POSTS_DIR}", file=sys.stderr)
        return
    made = []
    for md in md_files:
        post = parse_post(md)
        if not (post["title"] or post["number"]):
            continue
        base = os.path.splitext(os.path.basename(md))[0]
        out = os.path.join(OUT_DIR, base + ".png")
        render(post, out)
        made.append(os.path.basename(out))
    print(f"[ok] {len(made)} 枚を posts/images/ に生成しました（font: {os.path.basename(BOLD_PATH)}）")
    for m in made:
        print("  -", m)


if __name__ == "__main__":
    main()
