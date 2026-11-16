# glow-ma/wld02 — 世界の架け橋 相談企業KPIの集計(移設済み)

2026-11-07、小柳さんの承認(使いやすさの改善⑦)を受けて、計算の関数を `glow-ma/src/` へ移しました。

- `glow-ma/src/wld02Kpi.js`: 週次KPIの計算(テストは `tests/glow_ma_wld02Kpi.test.mjs`)
- `glow-ma/src/nameMatch.js`: 名寄せの候補と法人番号の確かめ方(テストは `tests/glow_ma_wld02NameMatch.test.mjs`)
- `glow-ma/src/Wld02Runner.gs`: 台帳への組み込み。4つの記録タブの用意と、毎週月曜の集計を行う
  - 毎週の集計は、日次メンテナンスの中で月曜に行う
  - 法人番号の点検は、件数だけを稼働状況タブに書く

名寄せの候補(12組)は、これまでどおり人の確認を待ちます。自動で企業IDを統合することはしません。
決裁記録と設計書は、非公開リポジトリ(glow-docs-private)にあります。
