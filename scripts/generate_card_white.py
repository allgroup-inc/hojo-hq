import os
import qrcode
from PIL import Image, ImageDraw, ImageFont

BASE = r"C:\Users\takes\hojo-hq"
OUT = os.path.join(BASE, "posts", "card")
QR_URL = "https://allgroup-inc.github.io/hojo-hq/go/card/"
NAVY = (0, 51, 92)
ORANGE = (248, 136, 0)
WHITE = (255, 255, 255)
SUB = (90, 110, 130)

FONTS = [r"C:\Windows\Fonts\meiryob.ttc", r"C:\Windows\Fonts\meiryo.ttc"]
def font(size):
    for p in FONTS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def make_qr(px):
    q = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(QR_URL); q.make(fit=True)
    return q.make_image(fill_color="black", back_color="white").convert("RGB").resize((px, px), Image.NEAREST)

def center(d, text, f, y, width, fill):
    d.text(((width - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)

def logo(target_w):
    lg = Image.open(os.path.join(BASE, "site", "assets", "glow-logo.png")).convert("RGBA")
    h = int(lg.height * target_w / lg.width)
    return lg.resize((target_w, h), Image.LANCZOS)

W, H = 1254, 758
im = Image.new("RGB", (W, H), WHITE)
d = ImageDraw.Draw(im)
d.rectangle([0, 0, W, 10], fill=ORANGE)
d.rectangle([0, H - 10, W, H], fill=NAVY)
center(d, "沖縄企業のミカタ", font(86), 60, W - 420, NAVY)
center(d, "沖縄で使える補助金・助成金、毎日ぜんぶ。", font(40), 180, W - 420, NAVY)
center(d, "運営: 株式会社GLOW", font(32), 250, W - 420, SUB)
d.rounded_rectangle([70, 330, W - 490, 470], radius=18, fill=ORANGE)
center(d, "LINE登録 無料", font(52), 358, W - 420, WHITE)
for i, line in enumerate([
    "✓ 30秒診断で貴社に合う制度がわかる",
    "✓ 締切の約1か月前からLINEでお知らせ",
    "✓ 登録企業の利用料はずっと無料",
]):
    d.text((84, 510 + i * 62), line, font=font(38), fill=NAVY)
qr = make_qr(330)
qx, qy = W - 390, H // 2 - 165
d.rounded_rectangle([qx - 12, qy - 12, qx + 342, qy + 342], radius=14, outline=NAVY, width=3)
im.paste(qr, (qx, qy))
label = "QRでLINE登録"; f_l = font(34); qcx = qx + 165
d.text((qcx - d.textlength(label, font=f_l) / 2, qy + 352), label, font=f_l, fill=NAVY)
lg = logo(180)
im.paste(lg, (int(qcx - lg.width / 2), 26), lg)
im.save(os.path.join(OUT, "card_meishi_white.png"))
print("[ok] card_meishi_white.png")

W, H = 1447, 2039
im = Image.new("RGB", (W, H), WHITE)
d = ImageDraw.Draw(im)
d.rectangle([0, 0, W, 14], fill=ORANGE)
d.rectangle([0, H - 14, W, H], fill=NAVY)
lg = logo(230)
im.paste(lg, (int((W - lg.width) / 2), 50), lg)
center(d, "御社が使える補助金、", font(96), 250, W, NAVY)
center(d, "眠っていませんか?", font(96), 370, W, NAVY)
center(d, "沖縄で使える補助金・助成金を毎日自動チェック", font(46), 530, W, SUB)
d.rounded_rectangle([120, 630, W - 120, 790], radius=24, fill=ORANGE)
center(d, "30秒診断 無料", font(84), 660, W, WHITE)
checks = [
    "✓ 市町村・業種などを選ぶだけ",
    "✓ 貴社に合う制度と金額の目安がわかる",
    "✓ 締切の約1か月前からLINEでお知らせ",
    "✓ 登録企業の利用料はずっと無料",
]
f_c = font(52)
bw = max(d.textlength(s, font=f_c) for s in checks)
x0 = (W - bw) / 2
for i, line in enumerate(checks):
    d.text((x0, 880 + i * 84), line, font=f_c, fill=NAVY)
qr = make_qr(560)
qx, qy = (W - 560) // 2, 1280
d.rounded_rectangle([qx - 16, qy - 16, qx + 576, qy + 576], radius=18, outline=NAVY, width=4)
im.paste(qr, (qx, qy))
center(d, "QRを読み取ってLINE登録", font(52), 1880, W, NAVY)
center(d, "沖縄企業のミカタ|運営: 株式会社GLOW", font(38), 1960, W, SUB)
im.save(os.path.join(OUT, "card_a6_white.png"))
print("[ok] card_a6_white.png")
