#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — /go/ 中間リンクページ生成
(.claude/skills/go-link-discipline 準拠: 計測イベント+channel → 約0.4秒 → 転送先へ)

- lin.ee は直接貼らず、必ず /go/<チャネル>/ を経由する
- 転送先の変更は下の CHANNELS を書き換えて本スクリプトを再実行(一括変更)
- 計測は fukugiiro と同じ GA4(2026-08-24 小柳さん決裁でPlausibleから切替。
  議事: docs/議事_20260824_計測GA4切替.md)。イベント名とチャネルのみ送信。
  GA4_MEASUREMENT_ID が空の間は計測タグを出さない(転送のみ・外部送信ゼロ)

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

# GA4測定ID(analytics-config.js と同一の値にする)。空の間は計測なしで転送のみ。
GA4_MEASUREMENT_ID = "G-TQMX3MPFSR"
REDIRECT_MS = 400

# チャネル定義(転送先を変えるときはここだけ編集して再実行)
# 既定は「LINEへ転送」。転送先がLINEでないチャネルは event と dest_name を必ず上書きする
# (go-link-discipline: line_redirect のまま流用するとLINE登録数が水増しされ、KGIを見誤る)。
DEFAULT_EVENT = "line_redirect"
DEFAULT_DEST_NAME = "LINE"

CHANNELS = {
    # ── 沖縄企業のミカタ(@345pqedv) ──
    "site":       {"dest": "https://lin.ee/sh4bTUe", "label": "沖縄企業のミカタ: サイト最下部CTA"},
    "shindan":    {"dest": "https://lin.ee/sh4bTUe", "label": "沖縄企業のミカタ: 診断結果CTA"},
    "ig":         {"dest": "https://lin.ee/sh4bTUe", "label": "沖縄企業のミカタ: Instagramプロフィール"},
    "fb":         {"dest": "https://lin.ee/sh4bTUe", "label": "沖縄企業のミカタ: Facebookページ"},
    "card":       {"dest": "https://lin.ee/sh4bTUe", "label": "沖縄企業のミカタ: 紙配布(QRカード・催事・紹介)"},
    "insurance-shindan": {"dest": "https://lin.ee/sh4bTUe", "label": "沖縄企業のミカタ: 保険引き受け目安検索(LINE登録CTA)"},
    # ── もらいわすれ堂/フクギイロ(小柳遥さん・2026-07-24開設) ──
    "fg-top":     {"dest": "https://lin.ee/7fH7vDQ", "label": "フクギイロ: トップページ"},
    "fg-life":    {"dest": "https://lin.ee/7fH7vDQ", "label": "フクギイロ: ライフイベント別ページ"},
    "fg-area":    {"dest": "https://lin.ee/7fH7vDQ", "label": "フクギイロ: 市町村ページ"},
    "fg-kit":     {"dest": "https://lin.ee/7fH7vDQ", "label": "フクギイロ: 制度キットページ"},
    "fg-shindan": {"dest": "https://lin.ee/7fH7vDQ", "label": "フクギイロ: 診断ページ"},
    "fg-jukyu":   {"dest": "https://lin.ee/7fH7vDQ", "label": "フクギイロ: 受給報告(受け取れました)"},
}

TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>{dest_name}へ移動中…</title>
{analytics}
<style>
  body{{font-family:'Noto Sans JP','Hiragino Kaku Gothic ProN','Yu Gothic',Meiryo,sans-serif;
    background:#00335c;color:#F7F5F1;display:flex;flex-direction:column;gap:16px;
    align-items:center;justify-content:center;min-height:100vh;margin:0;text-align:center;padding:24px;}}
  a{{color:#F88800;font-weight:700;}}
</style>
</head>
<body>
<p>{dest_name}へ移動しています…</p>
<p>自動で切り替わらない場合は <a href="{dest}">こちらをタップ</a></p>
</body>
</html>
"""

# GA4計測つき: beacon送信+event_callbackで「送信でき次第すぐ転送」。
# gtag.jsが{ms}ms内に読み込めなくても必ず転送する(計測より転送優先)。
# 自動巡回(navigator.webdriver=true)は計測せず即転送(2026-09-04: 実訪問との混同防止)。
ANALYTICS_GA4 = """<script async src="https://www.googletagmanager.com/gtag/js?id={mid}"></script>
<script>
  var fgDone = false;
  function fgGo() {{ if (fgDone) return; fgDone = true; window.location.replace("{dest}"); }}
  if (navigator.webdriver) {{
    setTimeout(fgGo, 50);
  }} else {{
    window.dataLayer = window.dataLayer || [];
    function gtag() {{ dataLayer.push(arguments); }}
    gtag("js", new Date());
    gtag("config", "{mid}", {{ transport_type: "beacon" }});
    // 送るのはイベント名と channel のみ(個人識別子なし)
    gtag("event", "{event}", {{ channel: "{channel}", transport_type: "beacon",
      event_callback: fgGo, event_timeout: {ms} }});
    setTimeout(fgGo, {ms});
  }}
</script>"""

# 計測なし(GA4_MEASUREMENT_ID未設定の間): 外部送信ゼロで即転送
ANALYTICS_NONE = """<script>
  setTimeout(function () {{ window.location.replace("{dest}"); }}, 50);
</script>"""

README = """# /go/ 中間リンク(lin.ee直貼り禁止)

各導線 → `/go/<チャネル>/` → GA4に計測イベント(+channel)を記録 → 転送先へ自動転送。
直貼りすると ①経路計測 ②転送先の一括変更 ができなくなるため、**lin.ee は必ずここを経由**する。

## チャネル一覧
{rows}

## 転送先を変えるとき
1. `scripts/generate_go_pages.py` の CHANNELS の dest を書き換える
2. `python scripts/generate_go_pages.py` を実行(全ページ再生成)
3. commit & push → デプロイ後、主要チャネルで実際に転送されるか確認

## チャネルを追加するとき
CHANNELS に1行足して再実行するだけ(計測→転送の構造は共通テンプレート)。
GA4 では計測イベントの `channel` パラメータで経路別に集計できる。

**転送先がLINEでないチャネルは `event` と `dest_name` を必ず指定する。**
既定のまま(`line_redirect`)にすると、その導線のクリックがLINE登録として集計され、
KGI(LINE登録1,000社)の現在地を見誤る。例:

```python
"yoyaku": {{"dest": "<予約ページURL>", "label": "面談予約(LINE内)",
           "event": "yoyaku_click", "dest_name": "予約ページ"}},
```
"""


def main():
    made = []
    for ch, cfg in CHANNELS.items():
        d = os.path.join(GO_DIR, ch)
        os.makedirs(d, exist_ok=True)
        if GA4_MEASUREMENT_ID:
            analytics = ANALYTICS_GA4.format(
                mid=GA4_MEASUREMENT_ID, dest=cfg["dest"], ms=REDIRECT_MS,
                channel=ch, event=cfg.get("event", DEFAULT_EVENT))
        else:
            analytics = ANALYTICS_NONE.format(dest=cfg["dest"])
        html = TEMPLATE.format(
            channel=ch, dest=cfg["dest"], analytics=analytics,
            dest_name=cfg.get("dest_name", DEFAULT_DEST_NAME),
        )
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
