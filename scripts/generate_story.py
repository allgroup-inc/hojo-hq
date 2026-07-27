#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq デザイン部(エガクさん) — 縦型ストーリーズ画像(1080x1920)
毎日のInstagramストーリーズ用画像を自動生成する。update.yml で毎日自動実行。

締切3層ルール(.claude/skills/hojo-deadline-alert):
SNS告知は「締切30日以上先」の制度のみ。準備が間に合わない直前の制度は載せない。
→ data/subsidies.json から残り30日以上の募集中制度を締切が近い順に掲載。

出力: posts/images/story_alert.png
運用: ストーリーズに画像を上げ、リンクスタンプでサイト(UTM付き)へ誘導
      (docs/SNS投稿カレンダー.md「ストーリーズ運用」)。
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

from PIL import Image, ImageDraw, ImageFont

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "subsidies.json")
SNS_MIN_DAYS = 30  # SNS告知は30日以上先のみ(3層ルール)
OUT_PATH = os.path.join(BASE_DIR, "..", "posts", "images", "story_alert.png")

W, H = 1080, 1920
PAD = 96
MAX_ITEMS = 3

BG_TOP = (2, 28, 48)
BG_BOTTOM = (0, 51, 92)
GOLD = (248, 136, 0)
WHITE = (247, 245, 241)
MUTED = (176, 196, 214)
NAVY = (2, 28, 48)

FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
]
FONT_CANDIDATES_REG = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/YuGothR.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
]


def find_font(cands):
    for p in cands:
        if os.path.exists(p):
            return p
    return None


BOLD = find_font(FONT_CANDIDATES_BOLD)
REG = find_font(FONT_CANDIDATES_REG) or BOLD
if not BOLD:
    print("[error] 日本語フォントなし(CIは fonts-noto-cjk)", file=sys.stderr)
    sys.exit(2)


def font(bold, size):
    return ImageFont.truetype(BOLD if bold else REG, size)


def wrap(d, s, f, max_w, max_lines=2):
    lines, cur = [], ""
    for ch in s:
        if d.textlength(cur + ch, font=f) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
            if len(lines) == max_lines:
                lines[-1] = lines[-1][:-1] + "…"
                return lines
    if cur:
        lines.append(cur)
    return lines[:max_lines]


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    today = datetime.now(timezone(timedelta(hours=9))).date()
    pool = []
    for it in data.get("items", []):
        try:
            d = datetime.strptime(it.get("deadline", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        days = (d - today).days
        if days >= SNS_MIN_DAYS and it.get("status") == "募集中":
            pool.append({**it, "days_left": days})
    pool.sort(key=lambda x: x["days_left"])
    items = pool[:MAX_ITEMS]
    total = len(pool)

    img = Image.new("RGB", (W, H), BG_TOP)
    for y in range(H):
        t = y / (H - 1)
        img.paste((
            int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t),
            int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t),
            int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t),
        ), (0, y, W, y + 1))
    d = ImageDraw.Draw(img)
    max_w = W - PAD * 2

    # ヘッダー(ブランド)
    d.text((PAD, 180), "沖縄企業のミカタ", font=font(True, 56), fill=WHITE)
    d.text((PAD, 260), "OKINAWA KIGYO NO MIKATA｜補助金・助成金 情報", font=font(True, 26), fill=GOLD)
    d.line([(PAD, 320), (PAD + 260, 320)], fill=GOLD, width=5)

    # 見出し(30日以上=準備が間に合う制度だけを載せる)
    d.text((PAD, 420), "いま準備すれば間に合う", font=font(True, 68), fill=WHITE)
    d.text((PAD, 520), "補助金", font=font(True, 120), fill=GOLD)

    y = 740
    if items:
        for it in items:
            days = it.get("days_left", 0)
            when = f"締切 {it.get('deadline','')}(残り{days}日)"
            # カード
            card_h = 250
            d.rounded_rectangle([PAD, y, W - PAD, y + card_h], radius=22,
                                fill=(255, 255, 255, 255))
            cy = y + 34
            badge = font(True, 32)
            d.text((PAD + 40, cy), when, font=badge, fill=(0, 80, 136))
            cy += 56
            tf = font(True, 38)
            for ln in wrap(d, it.get("name", ""), tf, max_w - 80, max_lines=2):
                d.text((PAD + 40, cy), ln, font=tf, fill=NAVY)
                cy += 52
            y += card_h + 36
        if total > MAX_ITEMS:
            d.text((PAD, y + 4), f"ほか {total - MAX_ITEMS} 件も掲載中",
                   font=font(False, 34), fill=MUTED)
            y += 60
    else:
        d.text((PAD, y), "本日は掲載対象の制度がありません。",
               font=font(True, 42), fill=WHITE)
        d.text((PAD, y + 70), "次の公募に備えるなら、gBizID取得から。",
               font=font(False, 34), fill=MUTED)

    # 下部CTA
    band_h = 190
    bt = H - 260 - band_h
    bt = max(bt, y + 40)
    d.text((PAD, bt - 48), "※要件・締切は必ず原文でご確認ください", font=font(False, 24), fill=MUTED)
    d.rounded_rectangle([PAD, bt, W - PAD, bt + band_h], radius=24, fill=GOLD)
    d.text((PAD + 44, bt + 38), "▼ リンクから一覧をチェック", font=font(True, 44), fill=NAVY)
    d.text((PAD + 44, bt + 108), "登録なしで今すぐ見られます(無料)", font=font(False, 30), fill=NAVY)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    img.save(OUT_PATH, "PNG", optimize=True)
    print(f"[ok] story_alert.png を生成({len(items)}件掲載 / 30日以上先の対象{total}件)")


if __name__ == "__main__":
    main()
