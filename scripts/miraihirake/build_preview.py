#!/usr/bin/env python3
"""みらいひらけ堂の試写用1ファイルHTMLを組む。

GitHub Pages では公開判定まで miraihirake を配信から外しているため(update.yml)、
CSS・JS・写真・ロゴをすべて埋め込んだ1ファイルを作り、Actions の成果物や
Claude のアーティファクトとしてそのまま開けるようにする。

使い方: python scripts/miraihirake/build_preview.py [--out dist/miraihirake/preview.html]
"""
import argparse
import base64
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SITE = ROOT / "site" / "miraihirake"
MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp"}

# IntersectionObserver が使えない閲覧環境(サンドボックス等)では全シーンを即 .in にして
# 「アニメーションが動かない」状態を避ける。本番の film.js には影響しない。
FALLBACK_JS = """
try { new IntersectionObserver(function(){}); } catch (e) {
  document.querySelectorAll(".mfilm .scene").forEach(function(s){ s.classList.add("in"); });
}
"""


def data_uri(rel: str) -> str:
    path = SITE / rel
    mime = MIME.get(path.suffix.lower())
    if not mime:
        raise SystemExit(f"未対応の拡張子: {rel}")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def build() -> str:
    html = (SITE / "index.html").read_text(encoding="utf-8")
    css = (SITE / "assets" / "film.css").read_text(encoding="utf-8")
    js = (SITE / "assets" / "film.js").read_text(encoding="utf-8")

    html, n_css = re.subn(r'<link rel="stylesheet" href="assets/film\.css">', lambda _: f"<style>\n{css}\n</style>", html)
    html, n_js = re.subn(r'<script src="assets/film\.js" defer></script>', "", html)
    if n_css != 1 or n_js != 1:
        raise SystemExit(f"index.html の film.css/film.js 参照が想定と違う(css={n_css}, js={n_js})")

    for rel in sorted(set(re.findall(r'src="(assets/[^"]+)"', html))):
        html = html.replace(f'src="{rel}"', f'src="{data_uri(rel)}"')

    html = html.replace("</body>", f"<script>\n{js}\n{FALLBACK_JS}\n</script>\n</body>")
    leftover = re.findall(r'(?:src|href)="assets/[^"]+"', html)
    if leftover:
        raise SystemExit(f"埋め込み漏れ: {leftover}")
    return html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist" / "miraihirake" / "preview.html"))
    args = ap.parse_args()
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    html = build()
    out.write_text(html, encoding="utf-8")
    print(f"ok {out} ({len(html) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
