#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLOW LINE公式アカウント(@042wvrgo)のリッチメニューを、画像の作成から設定まで自動で行う。

  python scripts/glow_line_setup.py --render   # 画像だけ作る(posts/images/glow-line-richmenu.png)
  python scripts/glow_line_setup.py --apply    # 画像を作り、LINEに登録して全員の既定メニューにする

--apply には環境変数 GLOW_LINE_CHANNEL_ACCESS_TOKEN(GitHub Secrets)が必要。
ボタン(左から):
  世界へ挑戦  … 世界の架け橋のLP(GLOW_LP_URL があればそちら)
  補助金を探す … 沖縄企業のミカタ
  経営の相談   … ゆんたく経営相談室
同じ名前(GLOW-)の古いメニューは登録後に消すので、何度流しても1つだけ残る。
"""
import argparse
import json
import os
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFont

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE_DIR, "..", "posts", "images", "glow-line-richmenu.png")

W, H = 2500, 843
NAVY = (0, 51, 92)
RED = (185, 80, 47)
CREAM = (255, 251, 244)
INK = (31, 42, 46)

MIKATA_URL = "https://allgroup-inc.github.io/hojo-hq/"
YUNTAKU_URL = "https://allgroup-inc.github.io/yuntaku-lp/"
# 世界の架け橋LP(2026-10-05 公開・小柳さん決裁。allgroup-inc/glow-world・独自ドメイン glow-okinawa.jp)。Variables GLOW_LP_URL があればそちらを優先
LP_URL = "https://glow-okinawa.jp/"
MENU_PREFIX = "GLOW-"

BUTTONS = [
    {"title": "世界へ挑戦", "sub": "世界の架け橋(海外販路)", "bg": RED, "fg": CREAM},
    {"title": "補助金を探す", "sub": "沖縄企業のミカタ(無料)", "bg": NAVY, "fg": CREAM},
    {"title": "経営の相談", "sub": "ゆんたく経営相談室", "bg": CREAM, "fg": NAVY},
]

BOLD = next((p for p in [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/YuGothB.ttc", "C:/Windows/Fonts/meiryob.ttc",
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf"] if os.path.exists(p)), None)
REG = next((p for p in [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/YuGothR.ttc", "C:/Windows/Fonts/meiryo.ttc"] if os.path.exists(p)), BOLD)


def render():
    if not BOLD:
        sys.exit("[error] 日本語フォントなし")
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    col = W // 3
    f_title = ImageFont.truetype(BOLD, 120)
    f_sub = ImageFont.truetype(REG, 54)
    f_brand = ImageFont.truetype(BOLD, 40)
    for i, b in enumerate(BUTTONS):
        x0 = i * col
        x1 = W if i == 2 else (i + 1) * col
        d.rectangle([x0, 0, x1, H], fill=b["bg"])
        cx = (x0 + x1) // 2
        d.text((cx, H // 2 - 40), b["title"], font=f_title, fill=b["fg"], anchor="mm")
        d.text((cx, H // 2 + 90), b["sub"], font=f_sub, fill=b["fg"], anchor="mm")
        d.text((cx, H - 70), "タップ", font=f_sub, fill=b["fg"], anchor="mm")
    d.text((40, 30), "GLOW", font=f_brand, fill=CREAM)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, optimize=True)
    print(f"[ok] {os.path.relpath(OUT)} ({os.path.getsize(OUT) // 1024}KB)")
    return OUT


def menu_body(lp_url):
    col = W // 3
    left = ({"type": "uri", "label": "世界へ挑戦", "uri": lp_url} if lp_url else
            {"type": "message", "label": "世界へ挑戦", "text": "世界へ挑戦について知りたい"})
    actions = [
        left,
        {"type": "uri", "label": "補助金を探す", "uri": MIKATA_URL},
        {"type": "uri", "label": "経営の相談", "uri": YUNTAKU_URL},
    ]
    areas = []
    for i, a in enumerate(actions):
        w = W - 2 * col if i == 2 else col
        areas.append({"bounds": {"x": i * col, "y": 0, "width": w, "height": H}, "action": a})
    return {
        "size": {"width": W, "height": H},
        "selected": True,
        "name": MENU_PREFIX + ("lp" if lp_url else "talk"),
        "chatBarText": "メニュー",
        "areas": areas,
    }


def call(method, url, token, body=None, ctype="application/json"):
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"[error] {method} {url} → HTTP {e.code}: {e.read().decode('utf-8', 'replace')}")


def apply(path):
    token = os.environ.get("GLOW_LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not token:
        sys.exit("[error] GLOW_LINE_CHANNEL_ACCESS_TOKEN が未設定")
    lp_url = os.environ.get("GLOW_LP_URL", "").strip() or LP_URL
    api = "https://api.line.me/v2/bot"
    bot = call("GET", f"{api}/info", token)
    print(f"[ok] 接続先: {bot.get('displayName')} ({bot.get('basicId')})")
    if bot.get("basicId") != "@042wvrgo":
        sys.exit("[error] GLOW以外のアカウントのトークンです。設定を止めました")
    body = menu_body(lp_url)
    call("POST", f"{api}/richmenu/validate", token, body)
    new_id = call("POST", f"{api}/richmenu", token, body)["richMenuId"]
    with open(path, "rb") as f:
        call("POST", f"https://api-data.line.me/v2/bot/richmenu/{new_id}/content", token, f.read(), "image/png")
    call("POST", f"{api}/user/all/richmenu/{new_id}", token)
    print(f"[ok] 既定メニューに設定: {new_id}(左ボタン: {'LP' if lp_url else 'トークへ送信'})")
    for m in call("GET", f"{api}/richmenu/list", token).get("richmenus", []):
        if m["richMenuId"] != new_id and m.get("name", "").startswith(MENU_PREFIX):
            call("DELETE", f"{api}/richmenu/{m['richMenuId']}", token)
            print(f"[ok] 古いメニューを削除: {m['richMenuId']}")


def self_test():
    b = menu_body("")
    assert b["areas"][0]["action"]["type"] == "message"
    assert sum(a["bounds"]["width"] for a in b["areas"]) == W
    assert menu_body("https://example.com/")["areas"][0]["action"]["uri"] == "https://example.com/"
    print("[ok] 自己テスト")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    self_test()
    p = render()
    if a.apply:
        apply(p)
