#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq SNS部(ヒロメさん) — 週1カルーセル生成(carousel-writerスキル準拠)
「いま沖縄で募集中の補助金 Top5」を7枚構成(表紙+制度5+保存CTA)で生成する。
金曜の自動投稿(post_social.py)がこの素材を使う。

carousel-writerの原則:
- 表紙がすべて(フック+スワイプの約束)。1枚1アイデア。文字は最小限。
- 締めは保存CTA(カルーセルは保存・滞在時間で伸びる)。
制約(CLAUDE.md): 締切3層ルール=SNSは残り30日以上のみ / 金額・締切は原文値 /
誇大表現なし / 出典URLはキャプションに全件記載。

出力:
  posts/carousel/slide_01.png 〜 slide_07.png (1080x1350)
  posts/carousel/caption.md (キャプション+ハッシュタグ+出典)
決定論的出力(タイムスタンプ非埋込)。
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

import shipping_gate

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(BASE, "data", "subsidies.json")
OUT_DIR = os.path.join(BASE, "posts", "carousel")

# 出荷ゲート(運用規程1-3)の通過日。**キャプション文面を書き換えたら必ず更新する。**
# 2026-08-17: accuracy-check(締切・金額・出典URLはdata由来)/ deadline-alert(30日以上先のみ掲載)/
#             humanizer(定型句なし)で確認。
GATE_CHECKED = "2026-08-17"
SITE_URL = "https://allgroup-inc.github.io/hojo-hq/?utm_source=instagram&utm_medium=social&utm_campaign=carousel"

W, H = 1080, 1350  # IG推奨4:5(画面占有が最大)
PAD = 96
BG_TOP = (2, 28, 48)
BG_BOTTOM = (0, 51, 92)
GOLD = (248, 136, 0)
WHITE = (247, 245, 241)
MUTED = (176, 196, 214)
BRAND = "沖縄企業のミカタ"

BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
]
REG_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/YuGothR.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
]


def _find(cands):
    for p in cands:
        if os.path.exists(p):
            return p
    return None


BOLD = _find(BOLD_CANDIDATES)
REG = _find(REG_CANDIDATES) or BOLD
if not BOLD:
    print("[error] 日本語フォントなし(CIは fonts-noto-cjk を install)", file=sys.stderr)
    sys.exit(2)


def font(bold, size):
    return ImageFont.truetype(BOLD if bold else REG, size)


NO_LINE_START = "、。，．・：；？！」』）］｝〕〉》ーゝゞぁぃぅぇぉっゃゅょゎ"


def wrap(draw, s, f, max_w):
    lines, cur = [], ""
    for ch in s:
        if draw.textlength(cur + ch, font=f) <= max_w:
            cur += ch
        else:
            if ch in NO_LINE_START and cur:
                lines.append(cur[:-1])
                cur = cur[-1] + ch
            else:
                lines.append(cur)
                cur = ch
    if cur:
        lines.append(cur)
    return lines


def canvas():
    im = Image.new("RGB", (W, H))
    for y in range(H):
        t = y / H
        im.paste(tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)),
                 (0, y, W, y + 1))
    return im


def footer(d, page, total):
    d.text((PAD, H - 88), BRAND, font=font(True, 34), fill=MUTED)
    s = f"{page}/{total}"
    f = font(False, 34)
    d.text((W - PAD - d.textlength(s, font=f), H - 88), s, font=f, fill=MUTED)


def amount_short(v):
    if not v:
        return "上限額 要確認"
    if v >= 100_000_000:
        oku = f"{v / 100_000_000:.1f}".rstrip("0").rstrip(".")
        return f"上限 {oku}億円"
    if v >= 10000:
        return f"上限 {v // 10000:,}万円"
    return f"上限 {v:,}円"


def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def save(im, n):
    im.save(os.path.join(OUT_DIR, f"slide_{n:02d}.png"), "PNG")


def cover(total_slides):
    im = canvas()
    d = ImageDraw.Draw(im)
    d.rectangle((PAD, 210, PAD + 10, 470), fill=GOLD)
    d.text((PAD + 44, 216), "いま沖縄で", font=font(True, 92), fill=WHITE)
    d.text((PAD + 44, 330), "募集中の補助金", font=font(True, 92), fill=WHITE)
    d.text((PAD + 44, 452), "Top5", font=font(True, 150), fill=GOLD)
    y = 700
    for line in ("締切まで30日以上。", "いまから準備が間に合うものだけ", "選びました。"):
        d.text((PAD, y), line, font=font(False, 52), fill=MUTED)
        y += 74
    d.text((PAD, 1010), "スワイプで5件 →", font=font(True, 56), fill=GOLD)
    footer(d, 1, total_slides)
    save(im, 1)


def seido_slide(n, total, rank, it, today):
    im = canvas()
    d = ImageDraw.Draw(im)
    # 番号バッジ
    d.ellipse((PAD, 170, PAD + 130, 300), fill=GOLD)
    f = font(True, 76)
    s = str(rank)
    d.text((PAD + 65 - d.textlength(s, font=f) / 2, 196), s, font=f, fill=(2, 28, 48))
    # 制度名(最大3行)
    name = " ".join((it.get("name") or "").split())
    f_name = font(True, 60)
    lines = wrap(d, name, f_name, W - PAD * 2)[:3]
    if len(wrap(d, name, f_name, W - PAD * 2)) > 3:
        lines[-1] = lines[-1][:-1] + "…"
    y = 370
    for ln in lines:
        d.text((PAD, y), ln, font=f_name, fill=WHITE)
        y += 84
    # 区切り
    y += 30
    d.rectangle((PAD, y, W - PAD, y + 4), fill=(255, 255, 255, 40))
    y += 56
    dl = it.get("deadline") or "要確認"
    dd = parse_date(dl)
    days = f"(残り{(dd - today).days}日)" if dd else ""
    f_val = font(False, 44)
    max_val_w = W - PAD - (PAD + 150)
    for label, val in (("締切", f"{dl} {days}"),
                       ("金額", amount_short(it.get("max_amount"))),
                       ("実施", it.get("issuer") or "要確認")):
        while val and d.textlength(val, font=f_val) > max_val_w:
            val = val[:-2] + "…" if not val.endswith("…") else val[:-2] + "…"
        d.text((PAD, y), label, font=font(True, 44), fill=GOLD)
        d.text((PAD + 150, y), val, font=f_val, fill=WHITE)
        y += 84
    d.text((PAD, 1080), "※要件・締切は原文でご確認ください", font=font(False, 36), fill=MUTED)
    footer(d, n, total)
    save(im, n)


def cta_slide(n, total):
    im = canvas()
    d = ImageDraw.Draw(im)
    d.text((PAD, 240), "5件とも、", font=font(True, 76), fill=WHITE)
    d.text((PAD, 340), "締切まで1か月以上。", font=font(True, 76), fill=WHITE)
    d.text((PAD, 470), "いまから準備が間に合います。", font=font(False, 52), fill=MUTED)
    d.rectangle((PAD, 640, W - PAD, 850), outline=GOLD, width=4)
    d.text((PAD + 44, 676), "保存しておくと、", font=font(True, 54), fill=WHITE)
    d.text((PAD + 44, 750), "締切前に見返せます。", font=font(True, 54), fill=WHITE)
    y = 930
    for line in ("うちの会社で使えるかは、30秒診断で。",
                 "締切アラート(無料)はLINEで届きます。",
                 "→ プロフィールのリンクから"):
        d.text((PAD, y), line, font=font(False, 46), fill=MUTED)
        y += 66
    footer(d, n, total)
    save(im, n)


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    today = datetime.now(JST).date()
    pool = []
    for it in data.get("items", []):
        d = parse_date(it.get("deadline"))
        if not d or it.get("status") != "募集中":
            continue
        if (d - today).days >= 30:  # 締切3層ルール: SNSは30日以上のみ
            pool.append(it)
    pool.sort(key=lambda x: x["deadline"])
    # 上限額が出ている制度を優先しつつ、締切が近い順にTop5
    with_amt = [it for it in pool if it.get("max_amount")]
    top5 = (with_amt + [it for it in pool if not it.get("max_amount")])[:5]
    if len(top5) < 5:
        print(f"[skip] 30日以上先の募集中制度が{len(top5)}件のみ — カルーセルは生成しません")
        # 素材が古いまま金曜を迎えないよう、既存素材を撤去
        if os.path.isdir(OUT_DIR):
            for fn in os.listdir(OUT_DIR):
                os.remove(os.path.join(OUT_DIR, fn))
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    total = 7
    cover(total)
    for i, it in enumerate(top5, start=1):
        seido_slide(i + 1, total, i, it, today)
    cta_slide(7, total)

    # キャプション(hook-writer: 1行目=具体+時限。出典は全件)
    lines = [
        "締切まで30日以上ある補助金だけ、5件選びました。今から準備が間に合います🌺",
        "",
    ]
    for i, it in enumerate(top5, start=1):
        dd = parse_date(it["deadline"])
        days = f"・残り{(dd - today).days}日" if dd else ""
        lines.append(f"{i}. {it['name']}")
        lines.append(f"　締切 {it['deadline']}{days} / {amount_short(it.get('max_amount'))}")
    lines += [
        "",
        "🔖 保存しておくと、締切前に見返せます。",
        f"うちの会社で使えるかは30秒診断で👇\n{SITE_URL}",
        "※要件・締切・金額は必ず原文の公募要領でご確認ください。",
        "",
        "#沖縄補助金 #沖縄助成金 #沖縄経営者 #中小企業支援 #沖縄企業のミカタ",
        "",
        "## 出典",
    ]
    lines += [f"- {it['name']}: {it['source_url']}" for it in top5]
    with open(os.path.join(OUT_DIR, "caption.md"), "w", encoding="utf-8") as f:
        f.write("## キャプション\n" + "\n".join(lines[:-len(top5) - 1]) + "\n\n"
                + "\n".join(lines[-len(top5) - 1:]) + "\n\n"
                + shipping_gate.render_stamp(
                    "scripts/generate_carousel.py(SNS部・ヒロメさん)", GATE_CHECKED))
    print(f"[ok] カルーセル7枚+キャプションを posts/carousel/ に生成(基準日 {today})")
    for it in top5:
        print("  -", it["name"][:40], it["deadline"])


if __name__ == "__main__":
    main()
