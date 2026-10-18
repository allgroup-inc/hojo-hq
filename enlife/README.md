# エンライフ営業成績管理システム

エンライフメンバーの月別営業成績・KPI実績を Google Sheets で管理・分析するシステムです。

## 📁 ディレクトリ構成

```
enlife/
├── src/
│   └── SalesPerformanceManager.gs    # Google Apps Script（分析・集計機能）
├── scripts/
│   └── extract_sales_performance.py  # Python データ抽出スクリプト
└── README.md                          # このファイル
```

## 🚀 クイックスタート

### 初回セットアップ（15分）
1. **Google Sheets にコードを追加**
   - `src/SalesPerformanceManager.gs` を Google Apps Script にコピー
   - `ensureSalesPerformanceTabs()` を実行
   - 「営業成績（月別）」「KPI分析」シートが自動作成されます

2. **データを入力**
   - `scripts/extract_sales_performance.py` を実行してExcelからデータを抽出
   - CSV形式で Google Sheet に貼り付け

3. **分析を実行**
   - `updatePerformanceAnalysis()` を実行
   - 平均値・ランキングが自動計算されます

### 毎月の運用（5分）
1. Excelから最新データを抽出
2. Google Sheet に追加
3. `updatePerformanceAnalysis()` を実行

## 📊 機能

### 営業成績（月別）シート
- 営業メンバー × 月 × KPI14指標のデータベース
- 5月〜9月、8名 = 40レコード

### KPI分析シート
- 月別の KPI 平均値（自動計算）
- 総平均値（全月・全メンバー）
- 月別・総合トップパフォーマー（自動判定）

### KPI 指標（14個）
1. ANP実績
2. 契約件数
3. 契約世帯
4. 世帯取り
5. 世帯単価
6. 世帯率
7. 落ち率
8. 新規訪問
9. 再アポ訪問
10. その他訪問
11. 合計訪問
12. 自己アポ作成
13. 自己アポ訪問実績
14. 供給アポ実績

## 📖 ドキュメント

- **セットアップマニュアル** → `docs/enlife_営業成績管理システム_セットアップ完全マニュアル.md`
  - 初心者向けの分かりやすい手順書（約15分で完了）
  - トラブルシューティング・FAQ付き

- **実装ガイド** → `docs/enlife_営業成績管理システム_実装ガイド.md`
  - 技術仕様書・関数リファレンス
  - システム開発者向け

## 🛠 主要関数

| 関数 | 説明 |
|---|---|
| `ensureSalesPerformanceTabs()` | 管理シートを初期化（初回1回のみ） |
| `updatePerformanceAnalysis()` | 分析を実行・更新（毎月） |
| `getSalesPerformanceSummary()` | サマリーをログ出力（確認用） |

## 💾 データ抽出スクリプト

```bash
python3 enlife/scripts/extract_sales_performance.py
```

**入力**: Excel ファイル（File1・File2）  
**出力**: `/tmp/sales_performance_for_sheets.csv`

Excelファイルから月別営業成績データを抽出し、Google Sheets 用の CSV 形式に変換します。

## 📋 営業メンバー

- 前原　芳乃
- 奈須　章
- 下地　健太
- 幸良　妃奈代
- 徳元　孝樹
- 喜納　礼奈
- 名嘉山　望
- 狩俣　亜希乃

## 🔗 関連リンク

- **カチトーク（営業管理システム）**: https://kachitalk-line-enlife.azurewebsites.net/admin
- **Google Sheets**: エンライフの営業管理スプレッドシート

## 🔗 カチトークとの連携

Google Sheetの営業成績データを、カチトーク（エンライフ営業管理システム）と自動連携できます。

### 連携の流れ
1. Google Sheetの「営業成績（月別）」シートにデータを入力
2. Apps Scriptで分析を実行
3. Python スクリプトでカチトークへ自動送信
4. カチトークのダッシュボードで営業成績を確認

### セットアップ
詳細は以下のドキュメントを参照:
- **連携ガイド**: `README_KACHITALK_INTEGRATION.md`

### 毎月の実行（簡単版）
```bash
# 一括処理スクリプト
bash scripts/sync_all.sh
```

### 毎月の実行（ステップバイステップ）
```bash
# Step 1: Excelからデータを抽出
python3 scripts/extract_sales_performance.py

# Step 2: Google Sheetに手動で貼り付け（A1セルから）

# Step 3: カチトークへ同期
python3 scripts/sync_to_kachitalk.py \
  --csv /tmp/sales_performance_for_sheets.csv \
  --endpoint "$KACHITALK_ENDPOINT" \
  --token "$KACHITALK_API_TOKEN"
```

## 📝 ライセンス

エンライフ内部用システム

---

**最終更新**: 2026-10-18
