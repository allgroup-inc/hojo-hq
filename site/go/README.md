# /go/ 中間リンク(lin.ee直貼り禁止)

各導線 → `/go/<チャネル>/` → GA4に計測イベント(+channel)を記録 → 転送先へ自動転送。
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
| /go/fg-jukyu/ | フクギイロ: 受給報告(受け取れました) | https://lin.ee/7fH7vDQ |
| /go/fg-ig/ | もらいわすれ堂: Instagramプロフィール → 3分診断 | https://allgroup-inc.github.io/hojo-hq/fukugiiro/shindan/?utm_source=instagram&utm_medium=social&utm_campaign=profile |
| /go/fg-ig-line/ | もらいわすれ堂: Instagramプロフィール → LINE | https://lin.ee/7fH7vDQ |
| /go/ymn-top/ | フクギイロ山梨: トップページ | https://line.me/R/ti/p/%40630pbjqq |
| /go/ymn-shindan/ | フクギイロ山梨: 診断ページ | https://line.me/R/ti/p/%40630pbjqq |
| /go/ymn-area/ | フクギイロ山梨: 市町村ページ | https://line.me/R/ti/p/%40630pbjqq |
| /go/ymn-kit/ | フクギイロ山梨: 準備シートページ | https://line.me/R/ti/p/%40630pbjqq |
| /go/ymn-life/ | フクギイロ山梨: ライフイベント別ページ | https://line.me/R/ti/p/%40630pbjqq |
| /go/ymn-jukyu/ | フクギイロ山梨: 受給報告(受け取れました) | https://line.me/R/ti/p/%40630pbjqq |

## 転送先を変えるとき
1. `scripts/generate_go_pages.py` の CHANNELS の dest を書き換える
2. `python scripts/generate_go_pages.py` を実行(全ページ再生成)
3. commit & push → デプロイ後、主要チャネルで実際に転送されるか確認

## チャネルを追加するとき
CHANNELS に1行足して再実行するだけ(計測→転送の構造は共通テンプレート)。
GA4 では計測イベントの `channel` パラメータで経路別に集計できる。

## プロフィールの1枠目を /go/ に通すかどうか(事業で型が違う)

| 事業 | プロフィール1枠目 | 理由 |
|---|---|---|
| 沖縄企業のミカタ | サイトへ **utm付きの直リンク** | `docs/決裁キュー.md` の既定 |
| もらいわすれ堂 | **`/go/fg-ig/` 経由** | ❸の計測がゼロで、utm だけだと着地前の離脱を取りこぼすため |

型が分かれているのは事故ではなく決定。**ミカタに合わせて直リンクへ戻さないこと。**
経緯と採用条件: `docs/議事_20260921_IGプロフィール導線をgo経由にする.md`

**転送先がLINEでないチャネルは `event` と `dest_name` を必ず指定する。**
既定のまま(`line_redirect`)にすると、その導線のクリックがLINE登録として集計され、
KGI(LINE登録1,000社)の現在地を見誤る。例:

```python
"yoyaku": {"dest": "<予約ページURL>", "label": "面談予約(LINE内)",
           "event": "yoyaku_click", "dest_name": "予約ページ"},
```
