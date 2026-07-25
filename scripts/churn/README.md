# 早期解約リスク保全（churn）

申込〜解約の実績（CSV）から「6ヶ月以内解約リスク%」を出し、高リスク先へ先回り保全をあてる。

## 大原則
- **顧客個人データは `private/`（gitignore）でのみ扱う。絶対にコミットしない。**
- 入力は統一エクセルの1シートをCSVエクスポートしたもの。列名は `column_map.json` で対応づける。

## 手順
1. `docs/churn/column_map.example.json` を `private/column_map.json` にコピーし、実エクセルの列名に合わせる。
2. 学習: `python -m scripts.churn.cli fit --csv private/data.csv --column-map private/column_map.json --model private/risk_model.json --as-of 2026-07-25`
3. 妥当性確認（品質ゲート）: `python -m scripts.churn.cli backtest --csv private/data.csv --column-map private/column_map.json --split 2026-01-01 --as-of 2026-07-25` → AUCが0.5付近なら本番に出さない。
4. 採点・一覧出力: `python -m scripts.churn.cli score --csv private/data.csv --column-map private/column_map.json --model private/risk_model.json --out private/list --as-of 2026-07-25`

## テスト
`python -m unittest discover -s tests/churn -v`
