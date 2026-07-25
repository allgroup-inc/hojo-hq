# /go/ 中間リンク(lin.ee直貼り禁止)

各導線 → `/go/<チャネル>/` → Plausibleに `line_redirect`(+channel) を記録 → LINEへ自動転送。
直貼りすると ①経路計測 ②転送先の一括変更 ができなくなるため、**lin.ee は必ずここを経由**する。

## チャネル一覧
| パス | 用途 | 転送先 |
|---|---|---|
| /go/site/ | 沖縄企業のミカタ: サイト最下部CTA | https://lin.ee/sh4bTUe |
| /go/shindan/ | 沖縄企業のミカタ: 診断結果CTA | https://lin.ee/sh4bTUe |
| /go/ig/ | 沖縄企業のミカタ: Instagramプロフィール | https://lin.ee/sh4bTUe |
| /go/fg-top/ | フクギイロ: トップページ | https://lin.ee/7fH7vDQ |
| /go/fg-area/ | フクギイロ: 市町村ページ | https://lin.ee/7fH7vDQ |
| /go/fg-kit/ | フクギイロ: 制度キットページ | https://lin.ee/7fH7vDQ |
| /go/fg-shindan/ | フクギイロ: 診断ページ | https://lin.ee/7fH7vDQ |

## 転送先(LINE)を変えるとき
1. `scripts/generate_go_pages.py` の CHANNELS の dest を書き換える
2. `python scripts/generate_go_pages.py` を実行(全ページ再生成)
3. commit & push → デプロイ後、主要チャネルで実際に転送されるか確認

## チャネルを追加するとき
CHANNELS に1行足して再実行するだけ(計測→転送の構造は共通テンプレート)。
Plausible では `line_redirect` イベントの `channel` プロパティで経路別に集計できる。
