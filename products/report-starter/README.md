# 週次経営レポート自動生成テンプレ

売上CSVを置いておくだけで、毎週月曜の朝に **AIの所見つき経営レポート** が
自動で出来上がるテンプレートです。GitHub 1リポジトリで完結、サーバー不要。

```
input/sales.csv(売上データを追記していくだけ)
   │
   ▼  毎週月曜 07:00 JST(GitHub Actions)
[1] 集計   前週・前々週のKPIをPythonで正確に計算(AIに計算させない)
[2] AI所見 Claude APIがハイライト・懸念点・次アクションを執筆
[3] 出力   reports/2026-W31.md のようなレポートを自動コミット
```

**設計思想: 数字は機械が計算し、文章だけAIが書く。** 数値の誤りが起きない
構造にしてあります。

## こんな用途に

- 自分の会社・店舗の週次振り返りの自動化
- 顧問先・クライアントへの定期レポート納品(士業・コンサル・代理店)
- 複数店舗のデータを1つのCSVに集めて横断レポート

## セットアップ(約10分)

1. このテンプレート一式を自分のGitHubリポジトリ(Private推奨)にコピー
2. Settings → Secrets and variables → Actions に `ANTHROPIC_API_KEY` を登録
   (取得方法: https://platform.claude.com/ でキー発行+クレジット購入)
3. Settings → Actions → General → Workflow permissions を
   「Read and write permissions」に変更
4. `input/sales.csv` に自分のデータを入れる(形式は下記)
5. Actionsタブ → `weekly-report` → Run workflow で初回実行

以後、毎週月曜 07:00(JST)に `reports/` へ新しいレポートが追加されます。

## データ形式(input/sales.csv)

```csv
date,category,amount,count
2026-07-21,保険,150000,3
2026-07-21,物販,42000,12
2026-07-22,保険,80000,1
```

| 列 | 内容 |
|---|---|
| date | 売上日(YYYY-MM-DD) |
| category | 商品・部門などの分類(自由) |
| amount | 金額(円・整数) |
| count | 件数(なければ1) |

POSやスプレッドシートからのエクスポートをこの4列に合わせるだけです。
列を増やしたい場合は `scripts/build_report.py` の冒頭コメントを参照。

## まず動きを見たい(APIキーなしでOK)

```
pip install -r requirements.txt
python scripts/build_report.py --offline --asof 2026-07-28
```

`--offline` はAI所見をプレースホルダにして、集計とレポート生成だけを
実行するテストモードです。同梱のサンプルデータ(2026年7月分)でレポートが
1枚できます(`--asof` はサンプルデータの日付に合わせるための指定。
自分のデータで運用するときは不要です)。

## カスタマイズ

- **レポートの文体・観点を変える**: `scripts/build_report.py` の
  `SYSTEM_PROMPT` を編集(例:「飲食店の店長向けに」「金融機関に提出する
  丁寧な文体で」)
- **実行曜日・時刻**: `.github/workflows/weekly-report.yml` の cron(UTC表記)
- **使用モデル**: 既定は高精度モデル。ワークフローの `ANTHROPIC_MODEL` の
  コメントを外すと低コストモデルに切替(所見の質は下がります)
- **月次レポート化**: cron を `0 22 1 * *` 等にし、`--days 30` を付けて実行

## よくある質問

- **Q. 費用は?** レポート1通あたり数円〜十数円。週1なら月100円未満が目安
- **Q. データをGitHubに置くのが不安** Privateリポジトリなら外部非公開です。
  それでも避けたい場合は金額を係数で変換して運用する方法があります(所見の
  質はほぼ変わりません)
- **Q. Actionsが失敗する** Secretsの名前が `ANTHROPIC_API_KEY` か、
  Workflow permissionsが Read and write か、を確認。それでも解決しなければ
  失敗ステップのログを添えてご連絡ください

## ライセンス

購入者本人の商用利用OK(顧問先へのレポート提供もOK)。
テンプレート自体の再配布・再販売は不可。詳細は LICENSE.md。
