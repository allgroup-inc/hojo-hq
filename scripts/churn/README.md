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

## 顧客カルテ(お客様管理)
別システムから「申込み台帳」と「接触履歴」をCSVで書き出し、顧客IDで束ねてカルテを出す。
- 接触履歴の列名は `docs/churn/interaction_column_map.example.json` を `private/interaction_map.json` にコピーして合わせる。
- カルテ出力: `python -m scripts.churn.cli karte --csv private/apps.csv --column-map private/column_map.json --interactions private/inter.csv --interaction-map private/interaction_map.json --model private/risk_model.json --customer-id C1 --out private/karte_C1.html --as-of 2026-07-26`
- カルテは顧客個人情報を含むため `private/` に出力し、コミットしない。

## 運用コンソール(一括生成)
全顧客のカルテ＋顧客インデックス＋リスク一覧＋要フォローを1コマンドで `private/console/` に出す。
`python -m scripts.churn.cli console --csv private/apps.csv --column-map private/column_map.json --interactions private/inter.csv --interaction-map private/interaction_map.json --model private/risk_model.json --out-dir private/console --as-of 2026-07-26`
生成物は顧客個人情報を含むため `private/` 限定・コミットしない。
`index.html`・`list.html`(＝`list.csv`)・各顧客の`karte_*.html`・`followups.html`はすべて同じ`--out-dir`直下に書かれ、
リスク一覧や顧客インデックスの行から各カルテへ相対リンクで飛べる(サブディレクトリに分かれているとリンク切れ404になるため)。
`private/console/index.html`(または`list.html`)を開いて回遊する。

## 誤コミット自動検知(churn-pii-guard)
公開リポジトリへの個人情報の誤コミットを機械的に止める。
- ローカルで有効化(各自1回): `git config core.hooksPath .githooks`
  以後、`private/` 配下・CSV/Excel・`karte_*.html`・`risk_model*.json` をステージしてコミットしようとすると中断する。
- 意図的に通す場合のみ: `CHURN_PII_GUARD_ALLOW="<パス>" git commit ...`
- CI(PR)でも `.github/workflows/pii-guard.yml` が同じ検査を実行するので、フック未設定でもPRで検知される。
