#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq SNS部(ヒロメさん) — 週1カルーセル生成(carousel-writerスキル準拠)
「いま沖縄で募集中の補助金 Top5」を8枚構成(表紙+制度5+申請前チェック+保存・送るCTA)で生成する。
金曜の自動投稿(post_social.py)がこの素材を使う。

carousel-writerの原則:
- 表紙がすべて(フック+スワイプの約束)。1枚1アイデア。文字は最小限。
- 締めは保存CTA(カルーセルは保存・滞在時間で伸びる)。
制約(CLAUDE.md): 締切3層ルール=SNSは残り30日以上のみ / 金額・締切は原文値 /
誇大表現なし / 出典URLはキャプションに全件記載。

出力:
  posts/carousel/slide_01.png 〜 slide_08.png (1080x1350)
  posts/carousel/caption.md (キャプション+ハッシュタグ+出典)
決定論的出力(タイムスタンプ非埋込)。
"""
import json
import re
import os
import sys
from datetime import datetime, timezone, timedelta

from PIL import Image, ImageDraw, ImageFont

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import shipping_gate
from generate_ig_hub import hub_guide
from region_filter import other_region

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(BASE, "data", "subsidies.json")
OUT_DIR = os.path.join(BASE, "posts", "carousel")

# 出荷ゲート(運用規程1-3)の通過日。**キャプション文面を書き換えたら必ず更新する。**
# 2026-08-17: accuracy-check(締切・金額・出典URLはdata由来)/ deadline-alert(30日以上先のみ掲載)/
#             humanizer(定型句なし)で確認。
GATE_CHECKED = "2026-10-16"
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


def cover_hook(top5, today):
    """表紙と1行目のフック。週番号で3型を回す(決定論的=プレビューと実投稿がずれない)。
    曖昧なフックは伸びない・数字や対象を具体的に、という調査結果に沿い、
    すべて実データの数字だけで作る(docs/SNS_バズ投稿調査_20261016.md)。"""
    amounts = [it.get("max_amount") or 0 for it in top5]
    days = [(parse_date(it["deadline"]) - today).days for it in top5]
    kind = ["amount", "time", "before"][today.isocalendar()[1] % 3]
    # 上限額の「合計」は1社が受け取れる額ではなく誇大に読めるため使わない。最大の1件だけを示す
    if kind == "amount" and max(amounts) >= 10_000_000:
        top = amount_short(max(amounts)).replace("上限 ", "")
        return {"big": ["この5件のうち", "上限の最大は"], "num": top,
                "sub": ["対象地域に沖縄も入る、", "いま募集中の補助金です。"],
                "caption": f"いま募集中の補助金5件。いちばん大きいものは上限{top}です。どれも対象地域に沖縄が入ります🌺"}
    if kind == "before":
        return {"big": ["見積もりを取る前に、", "見ておきたい"], "num": "補助金5件",
                "sub": ["締切まで1か月以上あるものだけ。", "発注の前に、まず確認を。"],
                "caption": "見積もりを取る前に、見ておきたい補助金を5件まとめました。どれも締切まで1か月以上あります🌺"}
    return {"big": ["締切まで、", "まだ"], "num": f"{min(days)}日以上",
            "sub": ["いまから準備が間に合う、", "対象地域に沖縄も入る5件です。"],
            "caption": f"締切まで、まだ{min(days)}日以上。今から準備が間に合う補助金だけ、5件選びました🌺"}


def cover(total_slides, hook):
    im = canvas()
    d = ImageDraw.Draw(im)
    d.rectangle((PAD, 210, PAD + 10, 470), fill=GOLD)
    d.text((PAD + 44, 216), hook["big"][0], font=font(True, 84), fill=WHITE)
    d.text((PAD + 44, 326), hook["big"][1], font=font(True, 84), fill=WHITE)
    f_num = font(True, 150)
    num = hook["num"]
    while d.textlength(num, font=f_num) > W - PAD * 2 - 44 and f_num.size > 90:
        f_num = font(True, f_num.size - 10)
    d.text((PAD + 44, 448), num, font=f_num, fill=GOLD)
    y = 700
    for line in hook["sub"]:
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


CHECKLIST = [
    ("GビズIDプライムはある?", "国の電子申請(jGrants)で使います。発行に日数がかかることも。"),
    ("発注・契約は、まだ?", "多くの補助金は、交付決定より前の発注が対象外です。"),
    ("公募要領の「対象者」を読んだ?", "業種・従業員数・地域の条件があります。"),
]


def checklist_slide(n, total):
    """保存されやすい「チェックリスト型」の1枚。内容は制度に依らない一般的な確認事項のみ。"""
    im = canvas()
    d = ImageDraw.Draw(im)
    d.text((PAD, 180), "申請の前に", font=font(True, 64), fill=MUTED)
    d.text((PAD, 260), "3つだけ確認", font=font(True, 96), fill=WHITE)
    y = 450
    f_t, f_s = font(True, 54), font(False, 40)
    for title, sub in CHECKLIST:
        d.rounded_rectangle((PAD, y + 6, PAD + 56, y + 62), radius=10, outline=GOLD, width=5)
        d.line((PAD + 12, y + 34, PAD + 26, y + 50, PAD + 48, y + 16), fill=GOLD, width=7)
        d.text((PAD + 84, y), title, font=f_t, fill=WHITE)
        yy = y + 80
        for ln in wrap(d, sub, f_s, W - PAD * 2 - 84):
            d.text((PAD + 84, yy), ln, font=f_s, fill=MUTED)
            yy += 56
        y = yy + 46
    footer(d, n, total)
    save(im, n)


def cta_slide(n, total):
    im = canvas()
    d = ImageDraw.Draw(im)
    d.text((PAD, 200), "あとで見返すなら", font=font(True, 70), fill=WHITE)
    d.text((PAD, 296), "保存しておくと便利です", font=font(True, 70), fill=GOLD)
    d.rectangle((PAD, 470, W - PAD, 700), outline=GOLD, width=4)
    d.text((PAD + 44, 506), "経理担当・顧問の先生に", font=font(True, 54), fill=WHITE)
    d.text((PAD + 44, 586), "送っておくと話が早いです", font=font(True, 54), fill=WHITE)
    y = 800
    for line in ("各制度の公募ページへは、",
                 "プロフィールのリンクからタップで。",
                 "締切のお知らせ(無料)もLINEで届きます。"):
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
        if other_region(it):  # 他地域の自治体制度は表紙「沖縄」と食い違うため除く
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
    total = 8
    hook = cover_hook(top5, today)
    cover(total, hook)
    for i, it in enumerate(top5, start=1):
        seido_slide(i + 1, total, i, it, today)
    checklist_slide(7, total)
    cta_slide(8, total)
    for fn in os.listdir(OUT_DIR):  # 枚数が減った場合の古いスライドを残さない
        m = re.match(r"slide_(\d+)\.png$", fn)
        if m and int(m.group(1)) > total:
            os.remove(os.path.join(OUT_DIR, fn))

    # キャプション(hook-writer: 1行目=具体+時限。出典は全件)
    lines = [
        hook["caption"],
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
        "経理担当や顧問の先生に送っておくと、相談が早く進みます。",
        "7枚目に、申請前に確認したい3つをまとめました。",
        hub_guide(0),
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
    print(f"[ok] カルーセル8枚+キャプションを posts/carousel/ に生成(基準日 {today})")
    for it in top5:
        print("  -", it["name"][:40], it["deadline"])


if __name__ == "__main__":
    main()
