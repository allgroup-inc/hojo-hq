# 情報自動収集→AI整形→静的サイト公開 パイプラインテンプレ

RSS・Webサイトから情報を毎日自動収集し、Claude APIで構造化データに整形して、
静的HTMLサイトとして自動公開するパイプラインの完成テンプレートです。

サーバー不要・**GitHub 1リポジトリで完結**します(GitHub Actions + GitHub Pages)。

```
GitHub Actions cron(1日2回)
   │
   ▼
[1] collect.py    情報源(RSS/HTML)を巡回して生データを保存
   │
   ▼
[2] structure.py  Claude APIで構造化(タイトル・日付・金額・要約などをJSON化)
   │
   ▼
[3] validate.py   品質ゲート(必須項目チェック・不明値は「要確認」表示)
   │
   ▼
[4] build_site.py 静的HTMLを生成 → GitHub Pagesで公開
```

## こんな用途に

- 補助金・助成金・入札情報などの公的情報まとめサイト
- 業界ニュースの自動キュレーションサイト
- 競合他社・求人・イベント情報のウォッチサイト
- 社内向けの情報収集ダッシュボード

## 必要なもの

| もの | 費用目安 |
|---|---|
| GitHubアカウント(無料枠でOK) | 0円 |
| Anthropic APIキー | 月数百円〜(収集量による) |

## セットアップ(約15分)

1. このテンプレート一式を自分の新しいGitHubリポジトリにコピー
2. リポジトリの Settings → Secrets → Actions に `ANTHROPIC_API_KEY` を登録
3. `config/sources.yml` に収集したい情報源を書く
4. `config/schema.json` を自分の用途に合わせて編集(そのままでも動きます)
5. Settings → Pages で「Deploy from a branch」→ `main` / `/site` を選択
6. Actionsタブから `pipeline` ワークフローを手動実行(Run workflow)

以後は1日2回、自動で収集→整形→公開が回ります。

詳細は `docs/SETUP.md`、カスタマイズ方法は `docs/CUSTOMIZE.md`、
よくある質問は `docs/FAQ.md` を参照してください。

## ディレクトリ構成

```
├── config/
│   ├── sources.yml        # 収集する情報源の定義
│   └── schema.json        # 抽出する項目の定義(JSON Schema)
├── scripts/
│   ├── collect.py         # [1] 収集
│   ├── structure.py       # [2] Claude APIで構造化
│   ├── validate.py        # [3] 品質ゲート
│   └── build_site.py      # [4] サイト生成
├── site/                  # 生成された公開サイト(自動更新)
├── data/                  # 収集・整形データ(自動更新)
├── .github/workflows/
│   └── pipeline.yml       # 自動実行の設定(cron)
└── docs/                  # セットアップ・カスタマイズガイド
```

## 注意事項(必ずお読みください)

- クロール対象サイトの **robots.txt と利用規約を必ず確認** してください。
  本テンプレートは既定で RSS と、明示的に許可されたページのみを対象とする設計です。
- 公開する情報の正確性は運用者の責任で担保してください。本テンプレートの
  品質ゲートは「不明な値を断定しない(要確認表示にする)」仕組みを備えていますが、
  最終確認を代替するものではありません。
- ライセンスは `LICENSE.md` を参照(購入者本人の商用利用可・再配布不可)。
