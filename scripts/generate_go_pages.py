#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — /go/ 中間リンクページ生成
(.claude/skills/go-link-discipline 準拠: 計測 line_redirect+channel → 約0.4秒 → LINEへ転送)

- lin.ee は直接貼らず、必ず /go/<チャネル>/ を経由する
- 転送先の変更は下の CHANNELS を書き換えて本スクリプトを再実行(一括変更)
- 計測は fukugiiro と同じ Plausible(Cookieなし・イベント名とチャネルのみ送信)

使い方: python scripts/generate_go_pages.py
出力:   site/go/<channel>/index.html + site/go/README.md
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_DIR = os.path.dirname(__file__)
GO_DIR = os.path.join(BASE_DIR, "..", "site", "go")

PLAUSIBLE_DOMAIN = "allgroup-inc.github.io"  # analytics-config.js と同一(小柳さん決裁済み)
REDIRECT_MS = 400

# チャネル定義(転送先を変えるときはここだけ編集して再実行)
CHANNELS = {
    # ── 沖縄企業のミカタ(@345pqedv) ──
    "site":       {"dest": "https://lin.ee/sh4bTUe", "label": "沖縄企業のミカタ: サイト最下部CTA"},
    "shindan":    {"dest": "https://lin.ee/sh4bTUe", "label": "沖縄企業のミカタ: 診断結果CTA"},
    "ig":         {"dest": "https://lin.ee/sh4bTUe", "label": "沖縄企業のミカタ: Instagramプロフィール"},
    "fb":         {"dest": "https://lin.ee/sh4bTUe", "label": "沖縄企業のミカタ: Facebookページ"},
    # ── もらいわすれ堂/フクギイロ(小柳遥さん・2026-07-24開設) ──
    "fg-top":     {"dest": "https://lin.ee/7fH7vDQ", "label": "フクギイロ: トップページ"},
    "fg-area":    {"dest": "https://lin.ee/7fH7vDQ", "label": "フクギイロ: 市町村ページ"},
    "fg-kit":     {"dest": "https://lin.ee/7fH7vDQ", "label": "フクギイロ: 制度キットページ"},
    "fg-shindan": {"dest": "https://lin.ee/7fH7vDQ", "label": "フクギイロ: 診断ページ"},
    "fg-jukyu":   {"dest": "https://lin.ee/7fH7vDQ", "label": "フクギイロ: 受給報告(振り込まれました)"},
}

TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>LINEへ移動中…</title>
<script>
  // 計測(Plausible manual・Cookieなし)。送るのは line_redirect と channel のみ。
  window.plausible = window.plausible || function () {{
    (window.plausible.q = window.plausible.q || []).push(arguments);
  }};
  window.plausible("line_redirect", {{ props: {{ channel: "{channel}" }} }});
  // 計測送信の猶予({ms}ms)後にLINEへ転送。計測が失敗しても必ず転送する。
  setTimeout(function () {{ window.location.replace("{dest}"); }}, {ms});
</script>
<script defer data-domain="{domain}" src="https://plausible.io/js/script.manual.js"></script>
<style>
  body{{font-family:'Noto Sans JP','Hiragino Kaku Gothic ProN','Yu Gothic',Meiryo,sans-serif;
    background:#00335c;color:#F7F5F1;display:flex;flex-direction:column;gap:16px;
    align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center;padding:24px;}}
  a{{color:#F88800;font-weight:700;}}
</style>
</head>
<body>
<p>LINEへ移動しています…</p>
<p>自動で切り替わらない場合は <a href="{dest}">こちらをタップ</a></p>
</body>
</html>
"""

README = """# /go/ 中間リンク(lin.ee直貼り禁止)

各導線 → `/go/<チャネル>/` → Plausibleに `line_redirect`(+channel) を記録 → LINEへ自動転送。
直貼りすると ①経路計測 ②転送先の一括変更 ができなくなるため、**lin.ee は必ずここを経由**する。

## チャネル一覧
{rows}

## 転送先(LINE)を変えるとき
1. `scripts/generate_go_pages.py` の CHANNELS の dest を書き換える
2. `python scripts/generate_go_pages.py` を実行(全ページ再生成)
3. commit & push → デプロイ後、主要チャネルで実際に転送されるか確認

## チャネルを追加するとき
CHANNELS に1行足して再実行するだけ(計測→転送の構造は共通テンプレート)。
Plausible では `line_redirect` イベントの `channel` プロパティで経路別に集計できる。
"""


def main():
    made = []
    for ch, cfg in CHANNELS.items():
        d = os.path.join(GO_DIR, ch)
        os.makedirs(d, exist_ok=True)
        html = TEMPLATE.format(channel=ch, dest=cfg["dest"], ms=REDIRECT_MS, domain=PLAUSIBLE_DOMAIN)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        made.append(ch)
    rows = "\n".join(f"| /go/{ch}/ | {cfg['label']} | {cfg['dest']} |" for ch, cfg in CHANNELS.items())
    rows = "| パス | 用途 | 転送先 |\n|---|---|---|\n" + rows
    with open(os.path.join(GO_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write(README.format(rows=rows))
    print(f"[ok] /go/ {len(made)} チャネルを生成: {', '.join(made)}")


if __name__ == "__main__":
    main()
