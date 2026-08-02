# カスタマイズガイド(補助金特化版)

## 1. 収集テーマを変える(最重要・1行)

`config/sources.yml` の `keyword` を変えるだけで、サイトのテーマが変わります。

| 作りたいサイト | keyword例 |
|---|---|
| 地域特化 | 沖縄 / 北海道 / 福岡市 |
| 分野特化 | IT導入 / 省エネ / 創業 / 事業承継 / 販路開拓 |
| 業種特化 | 農業 / 観光 / 建設 / 飲食 |

複数テーマを1サイトに載せる場合は、`sources:` にブロックを複数並べます
(idはユニークに)。

## 2. 表示項目を変える

`config/schema.json` の `properties` を編集します。**date(締切)・amount
(上限額)・rate(補助率)の「不明なら要確認」ルールは絶対に消さないでください**
(誤情報の公開防止の要です)。

項目を追加したら `scripts/build_site.py` の CARD テンプレートにも表示を
追加します。

## 3. サイトの見た目・名前を変える

`scripts/build_site.py` 冒頭の `SITE_TITLE` / `SITE_DESCRIPTION`、
`<style>` 内の `--accent`(基調色)を編集します。

## 4. LINE登録などのCTAを設置する

`build_site.py` の PAGE テンプレートの `<main>` 直前などに、LINE公式
アカウントへのリンクバナーを追加するのが定番です:

```html
<div style="text-align:center; margin:16px 0;">
  <a href="https://lin.ee/xxxx" style="display:inline-block; background:#06C755;
     color:#fff; padding:12px 32px; border-radius:8px; text-decoration:none;
     font-weight:bold;">締切リマインドをLINEで受け取る</a>
</div>
```

※締切直前の告知は準備が間に合わないため、利用者への案内は
「締切の約1か月前から」を推奨します(サイトのフッターにも明記済み)。

## 5. 自治体サイトを情報源に足す

RSSがあればRSSを最優先で(規約面で最も安全)。HTMLページを追加する場合は
**必ず robots.txt と利用規約を確認**してください(不許可のページは自動で
スキップされます)。

## 6. モデル・実行頻度・件数上限

pipeline-starterと同じです:
- モデル: ワークフローの `ANTHROPIC_MODEL` コメントを外して低コスト化
- 頻度: `.github/workflows/pipeline.yml` の cron(UTC表記)
- 件数上限: `config/sources.yml` の `max_items_per_run`
