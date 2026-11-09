#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沖縄企業のミカタ SNS 画像の4つの型(2026-11-09 第1段階・見本用。どこからも呼ばれない)。

  A        比較・一覧(白)          … 制度を2〜3つ並べ、上限額・締切を比べる
  OKINAWA  沖縄限定(白+オレンジ)   … 県・市町村の制度だけ
  B        豆知識・Q&A(オレンジ)
  C        準備・チェックリスト(紺)

見た目の自動検査: 文字を置くたびに位置を記録し、描き終わったら
  ・安全な範囲(上下左右の余白の内側)からはみ出していないか
  ・文字どうしが重なっていないか
を確かめる。決めた文字の大きさの範囲で収まらないときは描かずに LayoutError を出す
(呼び出し側はその投稿を候補から外す)。
"""
import os

from PIL import Image, ImageDraw, ImageFont

import sns_planner as P

W = H = 1080
MARGIN = 64                                   # 安全な範囲の余白
NAVY = (0, 51, 92)
ORANGE = (248, 136, 0)
WHITE = (255, 255, 255)
CREAM = (255, 248, 236)
INK = (24, 38, 52)
GRAY = (104, 116, 128)
PALE = (214, 228, 240)

BOLD_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
)
REG_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/YuGothR.ttc",
)


class LayoutError(Exception):
    """収まらない・重なる。この投稿は候補から外す。"""


def _font_path(cands):
    for p in cands:
        if os.path.exists(p):
            return p
    raise LayoutError("日本語のフォントが見つからない(fonts-noto-cjk が必要)")


class Canvas:
    def __init__(self, bg):
        self.im = Image.new("RGB", (W, H), bg)
        self.d = ImageDraw.Draw(self.im)
        self.boxes = []          # (x0, y0, x1, y1, 文字)
        self.bold = _font_path(BOLD_CANDIDATES)
        self.reg = _font_path(REG_CANDIDATES)

    def font(self, size, bold=True):
        return ImageFont.truetype(self.bold if bold else self.reg, size, index=0)

    def text(self, xy, s, size, fill, bold=True):
        if not s:
            return xy[1]
        f = self.font(size, bold)
        box = self.d.textbbox(xy, s, font=f)
        self.d.text(xy, s, font=f, fill=fill)
        self.boxes.append((*box, s))
        return box[3]

    def wrap(self, s, size, width, bold=True):
        f = self.font(size, bold)
        lines, cur = [], ""
        for ch in s:
            if self.d.textlength(cur + ch, font=f) > width and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        # 行頭に句読点・閉じかっこが来ないよう前の行へ寄せる
        for i in range(1, len(lines)):
            while lines[i] and lines[i][0] in "、。,.)）」』】・ー" and len(lines[i - 1]) > 1:
                lines[i - 1] += lines[i][0]
                lines[i] = lines[i][1:]
        return [ln for ln in lines if ln]

    def fit(self, s, sizes, width, max_lines, bold=True):
        """大きい順に試して、max_lines 行・幅 width に収まる (大きさ, 行) を返す。"""
        for size in sizes:
            lines = self.wrap(s, size, width, bold)
            f = self.font(size, bold)
            if len(lines) <= max_lines and all(self.d.textlength(ln, font=f) <= width for ln in lines):
                return size, lines
        raise LayoutError(f"文字が収まらない: {s[:30]}")

    def check(self):
        for x0, y0, x1, y1, s in self.boxes:
            if x0 < MARGIN - 1 or y0 < MARGIN - 40 or x1 > W - MARGIN + 1 or y1 > H - 24:
                raise LayoutError(f"はみ出し: {s[:20]}")
        for i, a in enumerate(self.boxes):
            for b in self.boxes[i + 1:]:
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    raise LayoutError(f"文字の重なり: 「{a[4][:12]}」と「{b[4][:12]}」")


def _brand(c, dark):
    c.text((80, 64), "沖縄企業のミカタ", 30, WHITE if dark else NAVY)
    c.d.rectangle((80, 110, 128, 114), fill=ORANGE)


def _footer(c, dark, text, stamp):
    c.d.line((80, H - 128, W - 80, H - 128), fill=(90, 120, 150) if dark else PALE, width=2)
    c.text((80, H - 106), "▶ " + text, 26, WHITE if dark else GRAY, bold=False)
    if stamp:
        c.text((80, H - 62), stamp, 22, WHITE if dark else ORANGE, bold=False)


def _single_card(c, p, today, top):
    """制度が1つだけのとき: 大きく1つを紹介する。"""
    bottom = H - 170
    c.d.rounded_rectangle((80, top, W - 80, bottom), 28, fill=CREAM)
    c.d.rounded_rectangle((80, top, 94, bottom), 7, fill=ORANGE)
    size, lines = c.fit(P.short_name(p["name"]), (46, 42, 38, 34), W - 80 - 130 - 40, 3)
    ty = top + 36
    for ln in lines:
        ty = c.text((130, ty), ln, size, INK) + 8
    iss = P.issuer_text(p)
    if iss:
        size, il = c.fit("実施:" + iss, (26, 23), W - 80 - 130 - 40, 1, bold=False)
        ty = c.text((130, ty + 6), il[0], size, GRAY, bold=False)
    amount_y = bottom - 150
    if ty > amount_y - 8:
        raise LayoutError(f"制度名が長く、金額と重なる: {p['name'][:20]}")
    c.text((130, amount_y), P.amount_text(p), 52, ORANGE)
    c.text((130, amount_y + 80), P.deadline_text(p, today), 32, INK, bold=False)


def _program_cards(c, programs, today, top):
    if len(programs) == 1:
        _single_card(c, programs[0], today, top)
        return
    n = len(programs)
    gap = 20
    avail = H - 160 - top
    card_h = min(200, (avail - gap * (n - 1)) // n)
    y = top
    for p in programs:
        c.d.rounded_rectangle((80, y, W - 80, y + card_h), 24, fill=CREAM)
        c.d.rounded_rectangle((80, y, 92, y + card_h), 6, fill=ORANGE)
        size, lines = c.fit(P.short_name(p["name"]), (36, 32, 28, 26), W - 80 - 124 - 32, 2)
        ty = y + 20
        for ln in lines:
            ty = c.text((124, ty), ln, size, INK) + 6
        meta_y = y + card_h - 56
        if ty > meta_y - 4:
            raise LayoutError(f"制度名が長く、金額・締切と重なる: {p['name'][:20]}")
        c.text((124, meta_y), P.amount_text(p), 30, ORANGE)
        dl = P.deadline_text(p, today)
        f = c.font(26, False)
        c.text((W - 80 - 28 - int(c.d.textlength(dl, font=f)), meta_y + 4), dl, 26, INK, bold=False)
        y += card_h + gap


def render_a(programs, today, stamp=""):
    c = Canvas(WHITE)
    _brand(c, False)
    c.text((80, 150), "小さな会社でも使いやすい", 38, GRAY)
    c.text((80, 202), "補助金、いま募集中", 62, NAVY)
    _program_cards(c, programs, today, 320)
    _footer(c, False, "くわしい条件は原文で。リンクはプロフィールから", stamp)
    c.check()
    return c.im


def render_okinawa(programs, today, stamp=""):
    c = Canvas(WHITE)
    c.d.rectangle((0, 0, W, 300), fill=ORANGE)
    _brand(c, True)
    c.text((80, 150), "沖縄県・市町村の制度", 38, WHITE)
    c.text((80, 200), "沖縄限定、いま募集中", 62, WHITE)
    _program_cards(c, programs, today, 340)
    _footer(c, False, "くわしい条件は原文で。リンクはプロフィールから", stamp)
    c.check()
    return c.im


def render_b(entry, stamp=""):
    c = Canvas(ORANGE)
    _brand(c, True)
    c.text((80, 150), entry.get("kicker", ""), 34, WHITE)
    y = 200
    for ln in entry["title"]:
        size, lines = c.fit(ln, (68, 60, 54), W - 160, 1)
        y = c.text((80, y), lines[0], size, WHITE) + 12
    top = max(y + 30, 400)
    for i, col in enumerate(entry["columns"][:2]):
        x0 = 80 + i * 470
        c.d.rounded_rectangle((x0, top, x0 + 450, H - 170), 28, fill=WHITE)
        c.text((x0 + 36, top + 30), col["head"], 46, NAVY)
        c.d.rectangle((x0 + 36, top + 96, x0 + 96, top + 102), fill=ORANGE)
        ly = top + 130
        for ln in col["lines"]:
            if ln:
                size, fl = c.fit(ln, (30, 27, 24), 380, 1)
                c.text((x0 + 36, ly), fl[0], size, INK)
            ly += 62
        if col.get("note"):
            size, fl = c.fit(col["note"], (26, 23), 380, 1, bold=False)
            c.text((x0 + 36, ly + 6), fl[0], size, GRAY, bold=False)
    _footer(c, True, entry.get("footer", "保存しておくと、あとで見返せます"), stamp)
    c.check()
    return c.im


def render_c(entry, stamp=""):
    c = Canvas(NAVY)
    _brand(c, True)
    c.text((80, 160), entry["title_top"], 54, WHITE)
    size, lines = c.fit(entry["title_main"], (86, 76, 66), W - 160, 1)
    c.text((80, 228), lines[0], size, ORANGE)
    c.text((80, 340), entry["title_bottom"], 54, WHITE)
    y = 470
    for head, sub in entry["checks"][:3]:
        c.d.rounded_rectangle((80, y + 6, 136, y + 62), 12, outline=ORANGE, width=5)
        c.d.line((92, y + 34, 106, y + 50, 126, y + 18), fill=ORANGE, width=7)
        size, hl = c.fit(head, (42, 38, 34), W - 168 - 80, 1)
        c.text((168, y), hl[0], size, WHITE)
        size, sl = c.fit(sub, (28, 25), W - 168 - 80, 1, bold=False)
        c.text((168, y + 60), sl[0], size, PALE, bold=False)
        y += 140
    _footer(c, True, entry.get("footer", "締切の約1か月前から、LINEでお知らせします"), stamp)
    c.check()
    return c.im


def render(post, today, stamp=""):
    kind = post["type"]
    if kind == P.TYPE_A:
        return render_a(post["programs"], today, stamp)
    if kind == P.TYPE_OKINAWA:
        return render_okinawa(post["programs"], today, stamp)
    if kind == P.TYPE_B:
        return render_b(post["text"], stamp)
    if kind == P.TYPE_C:
        return render_c(post["text"], stamp)
    raise LayoutError(f"知らない型: {kind}")
