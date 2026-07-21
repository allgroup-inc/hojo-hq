# hojo-hq

沖縄特化 助成金・補助金 自動収集/開示サイトのAI組織リポジトリ。
ALLGROUPグループの経営者リード獲得装置(出口: 士業送客・GLOW・法人保険)。

## 構成
```
hojo-hq/
├── CLAUDE.md              # 憲法(事業定義・KPI・絶対ルール)
├── .claude/agents/
│   ├── shushu.md          # 収集部(攻め)
│   ├── kensho.md          # 検証部
│   └── mamori.md          # 守り部(法務)
└── docs/
    └── 収集対象リスト.md
```

## 立ち上げ手順
1. allgroup-inc org に本リポジトリを作成しpush
2. 守り部でjGrants API規約+第1弾ソースを審査
3. 収集スクリプト(Python)+GitHub Actions cron設定
4. 静的サイト(GitHub Pages)+LINE公式アカウント接続
5. 沖縄県分のみでMVP公開 → データ鮮度を1ヶ月検証

## 決裁待ち事項(小柳さん)
- [ ] サイト名(仮: 沖縄補助金ナビ)
- [ ] LINE公式アカウント: 新規 or 家計の見直しやさんと共用
- [ ] 士業紹介先の確保(嶺井さん経由)
