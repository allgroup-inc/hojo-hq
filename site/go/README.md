# /go/ 中間リンク(lin.ee直貼り禁止)

各導線 → `/go/<チャネル>/` → Plausibleに計測イベント(+channel)を記録 → 転送先へ自動転送。
直貼りすると ①経路計測 ②転送先の一括変更 ができなくなるため、**lin.ee は必ずここを経由**する。

## チャネル一覧
| パス | 用途 | 転送先 |
|---|---|---|
| /go/site/ | 沖縄企業のミカタ: サイト最下部CTA | https://lin.ee/sh4bTUe |
| /go/shindan/ | 沖縄企業のミカタ: 診断結果CTA | https://lin.ee/sh4bTUe |
| /go/ig/ | 沖縄企業のミカタ: Instagramプロフィール | https://lin.ee/sh4bTUe |
| /go/fb/ | 沖縄企業のミカタ: Facebookページ | https://lin.ee/sh4bTUe |
| /go/card/ | 沖縄企業のミカタ: 紙配布(QRカード・催事・紹介) | https://lin.ee/sh4bTUe |
| /go/insurance-shindan/ | 沖縄企業のミカタ: 保険引き受け目安検索(LINE登録CTA) | https://lin.ee/sh4bTUe |
| /go/fg-top/ | フクギイロ: トップページ | https://lin.ee/7fH7vDQ |
| /go/fg-life/ | フクギイロ: ライフイベント別ページ | https://lin.ee/7fH7vDQ |
| /go/fg-area/ | フクギイロ: 市町村ページ | https://lin.ee/7fH7vDQ |
| /go/fg-kit/ | フクギイロ: 制度キットページ | https://lin.ee/7fH7vDQ |
| /go/fg-shindan/ | フクギイロ: 診断ページ | https://lin.ee/7fH7vDQ |
| /go/fg-jukyu/ | フクギイロ: 受給報告(振り込まれました) | https://lin.ee/7fH7vDQ |

## 転送先を変えるとき
1. `scripts/generate_go_pages.py` の CHANNELS の dest を書き換える
2. `python scripts/generate_go_pages.py` を実行(全ページ再生成)
3. commit & push → デプロイ後、主要チャネルで実際に転送されるか確認

## チャネルを追加するとき
CHANNELS に1行足して再実行するだけ(計測→転送の構造は共通テンプレート)。
Plausible では計測イベントの `channel` プロパティで経路別に集計できる。

**転送先がLINEでないチャネルは `event` と `dest_name` を必ず指定する。**
既定のまま(`line_redirect`)にすると、その導線のクリックがLINE登録として集計され、
KGI(LINE登録1,000社)の現在地を見誤る。例:

```python
"yoyaku": {"dest": "<予約ページURL>", "label": "面談予約(LINE内)",
           "event": "yoyaku_click", "dest_name": "予約ページ"},
```
