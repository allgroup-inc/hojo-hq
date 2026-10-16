#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate test post 3 carousel images (Template 3 + Scope3 省CO2設備投資促進事業, a0WJ200000CDNDnMAP)
6 pages × 1080×1350px, following Template 3 design specs

Color palette:
- Navy: #00335C
- Orange: #F88800
- Light Gray: #F5F5F5
- Text Dark: #333333
- White: #FFFFFF
"""
import os
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.join(os.path.dirname(__file__), "..")
OUT_DIR = os.path.join(BASE, "docs", "ig_posts_test")

# Colors (Template 3)
NAVY = (0, 51, 92)  # #00335C
ORANGE = (248, 136, 0)  # #F88800
LIGHT_GRAY = (245, 245, 245)  # #F5F5F5
TEXT_DARK = (51, 51, 51)  # #333333
WHITE = (255, 255, 255)

# Dimensions
WIDTH = 1080
HEIGHT = 1350

# Font paths
NOTO = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
FALLBACKS = [
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-mincho.ttf",
]

def get_font(size, candidates=None):
    """Load Japanese font or fallback to default."""
    paths = (candidates or [NOTO]) + FALLBACKS
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

def wrap_text(draw, text, font, max_width):
    """Simple line wrapping for Japanese text."""
    lines = []
    current_line = ""
    for char in text:
        test_line = current_line + char
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = char
    if current_line:
        lines.append(current_line)
    return lines

def draw_gradient_box(draw, box, start_color, end_color):
    """Draw a gradient-like box using color interpolation."""
    x1, y1, x2, y2 = box
    for y in range(y1, y2):
        ratio = (y - y1) / (y2 - y1)
        r = int(start_color[0] * (1 - ratio) + end_color[0] * ratio)
        g = int(start_color[1] * (1 - ratio) + end_color[1] * ratio)
        b = int(start_color[2] * (1 - ratio) + end_color[2] * ratio)
        draw.line([(x1, y), (x2, y)], fill=(r, g, b))

def page_1_hook():
    """Page 1: Hook - 事業転換を検討していますか？"""
    img = Image.new('RGB', (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)

    # Navy gradient background
    draw_gradient_box(draw, (0, 0, WIDTH, HEIGHT), NAVY, (0, 31, 63))

    # Main title
    title_font = get_font(56)
    title = "事業転換を検討していますか？"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_w = bbox[2] - bbox[0]
    title_x = (WIDTH - title_w) // 2
    draw.text((title_x, 300), title, font=title_font, fill=WHITE)

    # Subtitle with orange accent
    subtitle_font = get_font(44)
    subtitle = "国が最大15億円サポートします。"
    bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    subtitle_w = bbox[2] - bbox[0]
    subtitle_x = (WIDTH - subtitle_w) // 2
    draw.text((subtitle_x, 620), subtitle, font=subtitle_font, fill=ORANGE)

    # Small text at bottom
    bottom_font = get_font(26)
    bottom_text = "Scope3排出量削減・企業間連携・省CO2設備投資促進事業"
    bbox = draw.textbbox((0, 0), bottom_text, font=bottom_font)
    bottom_w = bbox[2] - bbox[0]
    bottom_x = (WIDTH - bottom_w) // 2
    draw.text((bottom_x, 1150), bottom_text, font=bottom_font, fill=WHITE)

    return img

def page_2_example(before_industry, after_industry, benefit):
    """Pages 2-4: Transformation example."""
    img = Image.new('RGB', (WIDTH, HEIGHT), LIGHT_GRAY)
    draw = ImageDraw.Draw(img)

    title_font = get_font(40)
    heading_font = get_font(32)
    body_font = get_font(24)

    # Title at top
    title = "事業転換のイメージ（試算例）"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_w = bbox[2] - bbox[0]
    title_x = (WIDTH - title_w) // 2
    draw.text((title_x, 40), title, font=title_font, fill=NAVY)

    # Before box
    before_x1, before_y1 = 60, 160
    before_x2, before_y2 = 500, 420
    draw.rectangle([before_x1, before_y1, before_x2, before_y2], outline=NAVY, width=3)
    draw.text((before_x1 + 20, before_y1 + 20), "BEFORE", font=heading_font, fill=NAVY)

    lines = wrap_text(draw, before_industry, body_font, 380)
    y = before_y1 + 80
    for line in lines[:3]:
        draw.text((before_x1 + 20, y), line, font=body_font, fill=TEXT_DARK)
        y += 50

    # Arrow
    arrow_x = (WIDTH - 60) // 2
    draw.line([(arrow_x - 30, 290), (arrow_x + 30, 290)], fill=ORANGE, width=4)
    draw.polygon([(arrow_x + 30, 290), (arrow_x + 20, 275), (arrow_x + 20, 305)], fill=ORANGE)

    # After box
    after_x1, after_y1 = 520, 160
    after_x2, after_y2 = 960, 420
    draw.rectangle([after_x1, after_y1, after_x2, after_y2], outline=ORANGE, width=3)
    draw.text((after_x1 + 20, after_y1 + 20), "AFTER", font=heading_font, fill=ORANGE)

    lines = wrap_text(draw, after_industry, body_font, 380)
    y = after_y1 + 80
    for line in lines[:3]:
        draw.text((after_x1 + 20, y), line, font=body_font, fill=TEXT_DARK)
        y += 50

    # Benefit box
    benefit_x1, benefit_y1 = 60, 480
    benefit_x2, benefit_y2 = 960, 700
    draw.rectangle([benefit_x1, benefit_y1, benefit_x2, benefit_y2], fill=NAVY)
    draw.text((benefit_x1 + 30, benefit_y1 + 30), "効果（試算例）", font=heading_font, fill=ORANGE)

    lines = wrap_text(draw, benefit, body_font, 820)
    y = benefit_y1 + 100
    for line in lines[:3]:
        draw.text((benefit_x1 + 30, y), line, font=body_font, fill=WHITE)
        y += 60

    # Footer text
    footer_font = get_font(20)
    footer = "※この補助金の採択事例ではなく、一般的なイメージ（試算例）です。効果の数字は保証するものではありません。詳細はプロフィールのLINEからご相談ください。"
    lines = wrap_text(draw, footer, footer_font, 900)
    y = 900
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=footer_font)
        line_w = bbox[2] - bbox[0]
        x = (WIDTH - line_w) // 2
        draw.text((x, y), line, font=footer_font, fill=TEXT_DARK)
        y += 40

    return img

def page_5_checklist():
    """Page 5: Preparation checklist."""
    img = Image.new('RGB', (WIDTH, HEIGHT), WHITE)
    draw = ImageDraw.Draw(img)

    # Navy gradient background
    draw_gradient_box(draw, (0, 0, WIDTH, HEIGHT), NAVY, (0, 31, 63))

    # Title
    title_font = get_font(36)
    title = "事業転換の準備チェックリスト"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_w = bbox[2] - bbox[0]
    title_x = (WIDTH - title_w) // 2
    draw.text((title_x, 60), title, font=title_font, fill=ORANGE)

    subtitle_font = get_font(24)
    subtitle = "（6か月の計画例・試算例）"
    bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    subtitle_w = bbox[2] - bbox[0]
    subtitle_x = (WIDTH - subtitle_w) // 2
    draw.text((subtitle_x, 150), subtitle, font=subtitle_font, fill=WHITE)

    # Checklist items
    body_font = get_font(28)
    items = [
        "6ヶ月前：経営課題の整理と転換目標の設定",
        "3ヶ月前：事業計画ドラフト作成・資金試算",
        "1ヶ月前：申請書類の準備・経理資料確認",
        "申請直前：書類チェック・最終提出準備"
    ]

    y = 300
    for item in items:
        draw.rectangle([80, y + 4, 106, y + 30], outline=WHITE, width=3)
        draw.text((130, y), item, font=body_font, fill=WHITE)
        y += 140

    # Footer
    footer_font = get_font(20)
    footer = "※スケジュール・期間は試算例で、一般的な目安です。詳細な進め方はLINE相談でお伝えします。"
    lines = wrap_text(draw, footer, footer_font, 900)
    y = 1050
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=footer_font)
        line_w = bbox[2] - bbox[0]
        x = (WIDTH - line_w) // 2
        draw.text((x, y), line, font=footer_font, fill=WHITE)
        y += 40

    return img

def page_6_cta():
    """Page 6: Call-to-action."""
    img = Image.new('RGB', (WIDTH, HEIGHT), ORANGE)
    draw = ImageDraw.Draw(img)

    # Title
    title_font = get_font(44)
    title = "詳しくはプロフィールの"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_w = bbox[2] - bbox[0]
    title_x = (WIDTH - title_w) // 2
    draw.text((title_x, 200), title, font=title_font, fill=WHITE)

    # LINE text
    line_font = get_font(56)
    line_text = "LINE"
    bbox = draw.textbbox((0, 0), line_text, font=line_font)
    line_w = bbox[2] - bbox[0]
    line_x = (WIDTH - line_w) // 2
    draw.text((line_x, 340), line_text, font=line_font, fill=NAVY)

    # Subtext
    sub_font = get_font(40)
    sub = "から相談できます"
    bbox = draw.textbbox((0, 0), sub, font=sub_font)
    sub_w = bbox[2] - bbox[0]
    sub_x = (WIDTH - sub_w) // 2
    draw.text((sub_x, 490), sub, font=sub_font, fill=WHITE)

    # QR code placeholder (simple rectangle)
    qr_size = 180
    qr_x1 = (WIDTH - qr_size) // 2
    qr_y1 = 700
    qr_x2 = qr_x1 + qr_size
    qr_y2 = qr_y1 + qr_size
    draw.rectangle([qr_x1, qr_y1, qr_x2, qr_y2], fill=WHITE, outline=NAVY, width=3)

    # QR label
    qr_label_font = get_font(20)
    qr_label = "QRコード"
    bbox = draw.textbbox((0, 0), qr_label, font=qr_label_font)
    qr_label_w = bbox[2] - bbox[0]
    qr_label_x = (WIDTH - qr_label_w) // 2
    draw.text((qr_label_x, qr_y2 + 30), qr_label, font=qr_label_font, fill=WHITE)

    # Free consultation text
    footer_font = get_font(28)
    footer = "無料相談受付中"
    bbox = draw.textbbox((0, 0), footer, font=footer_font)
    footer_w = bbox[2] - bbox[0]
    footer_x = (WIDTH - footer_w) // 2
    draw.text((footer_x, 1100), footer, font=footer_font, fill=WHITE)

    return img

def main():
    """Generate all 6 pages."""
    print("[*] Generating test post 3 carousel images...")

    # Page 1: Hook
    print("  P1: Hook")
    img1 = page_1_hook()
    img1.save(os.path.join(OUT_DIR, "ig_test_3_p1.png"))

    # Page 2: Manufacturing → IoT
    print("  P2: Manufacturing → IoT")
    img2 = page_2_example(
        "従来の人手による\n製造プロセス",
        "IoT活用による\n自動化製造",
        "生産性40%向上 / コスト30%削減 / 労働環境改善"
    )
    img2.save(os.path.join(OUT_DIR, "ig_test_3_p2.png"))

    # Page 3: Retail → E-commerce
    print("  P3: Retail → E-commerce")
    img3 = page_2_example(
        "実店舗のみの\n販売体制",
        "ECサイト展開で\n全国販売",
        "顧客層2倍拡大 / 売上50%増加 / 24時間営業"
    )
    img3.save(os.path.join(OUT_DIR, "ig_test_3_p3.png"))

    # Page 4: Food Service → Delivery
    print("  P4: Food Service → Delivery")
    img4 = page_2_example(
        "店舗飲食のみの\n営業体制",
        "宅配・中食事業へ\n展開",
        "営業時間外の収益化 / 店舗負荷軽減 / 収益源多角化"
    )
    img4.save(os.path.join(OUT_DIR, "ig_test_3_p4.png"))

    # Page 5: Checklist
    print("  P5: Checklist")
    img5 = page_5_checklist()
    img5.save(os.path.join(OUT_DIR, "ig_test_3_p5.png"))

    # Page 6: CTA
    print("  P6: CTA")
    img6 = page_6_cta()
    img6.save(os.path.join(OUT_DIR, "ig_test_3_p6.png"))

    print(f"[+] All 6 pages saved to {OUT_DIR}")
    return True

if __name__ == "__main__":
    main()
