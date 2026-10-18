# エンライフ営業成績管理システム - アーキテクチャ概要

## システム全体像

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          エンライフ営業成績管理                            │
└─────────────────────────────────────────────────────────────────────────┘

①【入力】
   Excelファイル（営業成績確定）
   ↓
   
②【集約】
   Google Sheet「営業成績（月別）」
   - 営業マン8名 × 月5月〜9月 = 40レコード
   - KPI指標14個を全員分集約
   ↓
   
③【分析・可視化】
   Google Apps Script（SalesPerformanceManager.gs）
   ├─ ensureSalesPerformanceTabs()    初期化（1回のみ）
   ├─ updatePerformanceAnalysis()     分析実行（毎月）
   └─ getSalesPerformanceSummary()    ログ出力（確認用）
   ↓
   Google Sheet「KPI分析」シート
   - 月別平均値
   - 総平均値
   - トップパフォーマー（月別・総合）
   ↓
   
④【同期】
   Python スクリプト群
   ├─ extract_sales_performance.py    CSV形式に変換
   ├─ sync_to_kachitalk.py            カチトークAPI送信
   └─ sync_all.sh                     ワンコマンド実行
   ↓
   
⑤【営業管理ダッシュボード】
   カチトーク（kakei-crm）
   - 営業成績メトリクス表示
   - スタッフ別実績確認
   - 月別推移グラフ
   ↓
   
⑥【確認・共有】
   カチトーク状況確認URL
   https://kachitalk-line-enlife.azurewebsites.net/admin?key=...
```

---

## コンポーネント詳細

### ①【入力】Excelファイル

**所在**: ユーザーの手元 / OneDrive 等

**形式**:
- File1: 5月〜7月のデータ（複数シート）
- File2: 7月・8月・9月のデータ（1シート）

**変更频度**: 月1回（月初に営業成績確定後）

---

### ②【集約】Google Sheet

**所在**: Google Drive（共有スプレッドシート）

**シート構成**:

#### A. 「営業成績（月別）」シート（入力用）
| 営業マン | 月 | ANP実績 | 契約件数 | 契約世帯 | ... | 供給アポ実績 |
|---------|---|--------|--------|--------|-----|----------|
| 前原　芳乃 | 5月 | 1234000 | 5 | 8 | ... | 12 |
| 前原　芳乃 | 6月 | 1567000 | 6 | 9 | ... | 15 |
| ... | ... | ... | ... | ... | ... | ... |

**形式**: 営業マン × 月 = 1行

**数値形式**: コンマなし・式なし（純粋な数値のみ）

#### B. 「KPI分析」シート（自動生成）
| KPI指標 | 5月平均 | 6月平均 | 7月平均 | 8月平均 | 9月平均 | 総平均 | トップ(5月) | ... | 総トップ |
|--------|--------|--------|--------|--------|--------|--------|----------|-----|--------|
| ANP実績 | 987654 | 1123456 | 945678 | 1234567 | 1098765 | 1077904 | 前原　芳乃 | ... | 幸良　妃奈代 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

**自動計算**:
- 月別平均: AVERAGE(月内の全営業マンの値)
- 総平均: AVERAGE(全月・全営業マンの値)
- トップ: MAX(該当月・該当KPIの値)を持つ営業マン名

---

### ③【分析・可視化】Google Apps Script

**所在**: `enlife/src/SalesPerformanceManager.gs`

**言語**: Google Apps Script（JavaScript方言）

**関数一覧**:

```javascript
// 初期化関数（初回セットアップ時のみ、1回実行）
ensureSalesPerformanceTabs()
  → 「営業成績（月別）」「KPI分析」の2シートを作成
  → ヘッダー行を自動設定
  → ログ: ✓ 営業成績管理タブの初期化完了

// メイン分析関数（毎月初に実行）
updatePerformanceAnalysis()
  → 「営業成績（月別）」からデータを読み込み
  → 月別・指標別の平均値を計算
  → トップパフォーマーを判定
  → 「KPI分析」シートに結果を書き込み
  → ログ: ✓ KPI分析の更新完了: 14 指標を集計

// デバッグ用
getSalesPerformanceSummary()
  → 営業成績サマリーをログ出力
  → 全営業マンの月別合計を表示
```

**内部データ構造**:
```javascript
{
  営業マン1: {
    5月: {
      ANP実績: 1234000,
      契約件数: 5,
      ...
    },
    6月: { ... }
  },
  営業マン2: { ... }
}
```

---

### ④【同期】Python スクリプト群

**所在**: `enlife/scripts/`

#### A. extract_sales_performance.py
**役割**: Excelファイル → CSV（Google Sheet形式）

**入力**:
- File1: `/root/.claude/uploads/.../7faea010-...xlsx`
- File2: `/root/.claude/uploads/.../e7617513-...xlsx`

**処理フロー**:
1. File1から5月〜7月を抽出（行11-24、列5から）
2. File2から7月・8月・9月を抽出（動的に行を検出）
3. CSV形式に統一（営業マン, 月, KPI1, KPI2, ...）
4. `/tmp/sales_performance_for_sheets.csv` に出力

**出力形式**:
```csv
営業マン,月,ANP実績,契約件数,...,供給アポ実績
前原　芳乃,5月,1234000,5,...,12
前原　芳乃,6月,1567000,6,...,15
...
```

**実行**:
```bash
python3 enlife/scripts/extract_sales_performance.py
```

#### B. sync_to_kachitalk.py
**役割**: CSV → カチトークAPI送信

**入力**: CSV形式の営業成績データ

**処理フロー**:
1. CSVを読み込む
2. カチトークAPI接続確認
3. 営業マン × 月 × KPIを1件ずつ送信
4. 成功/失敗を集計

**認証方式**: Bearer Token（HTTP Authorization ヘッダー）

**エンドポイント**:
```
POST https://kachitalk-line-enlife.azurewebsites.net/api/sales-performance
```

**実行**:
```bash
python3 enlife/scripts/sync_to_kachitalk.py \
  --csv /tmp/sales_performance_for_sheets.csv \
  --endpoint "$KACHITALK_ENDPOINT" \
  --token "$KACHITALK_API_TOKEN"
```

#### C. google_sheets_sync.py
**役割**: Google Sheets API統合版（将来用、上級者向け）

**特徴**:
- Service Accountで直接Google Sheetsから読み込み
- 手動CSVエクスポートが不要
- 自動スケジュール実行に対応

**前提条件**:
- Google Cloud ProjectでService Accountを作成
- Sheets・Drive APIを有効化

#### D. sync_all.sh
**役割**: ワンコマンド実行・ガイド

**機能**:
1. extract_sales_performance.py を実行
2. Google Sheet貼り付けを確認（対話型）
3. sync_to_kachitalk.py を実行
4. 成功/失敗を報告

**実行**:
```bash
bash enlife/scripts/sync_all.sh
```

---

### ⑤【営業管理ダッシュボード】カチトーク（kakei-crm）

**所在**: 非公開リポジトリ `allgroup-inc/kakei-crm`

**用途**: エンライフ全体の顧客・営業管理システム

**営業成績との連携点**:
- 営業メトリクス API（実装予定）
- KPI分析・ランキング表示
- 月別推移グラフ

**データフロー**:
```
kakei-crm API ← Python スクリプト（sync_to_kachitalk.py）
     ↓
カチトークダッシュボード
```

---

### ⑥【確認・共有】カチトーク状況確認URL

**URL**: `https://kachitalk-line-enlife.azurewebsites.net/admin?key=...`

**表示内容**:
- 営業メンバー別実績（月別）
- KPI指標別ランキング
- 月別推移グラフ
- 総合スコアボード

---

## 毎月のワークフロー

```
【月初（営業成績確定直後）】

Day 1:
  1. Excelファイルを確定
  2. Python で extract_sales_performance.py を実行
     → /tmp/sales_performance_for_sheets.csv を生成
  3. CSV をコピー
  4. Google Sheet「営業成績（月別）」に貼り付け（A1セルから）

Day 1-2:
  5. Apps Script エディタで ensureSalesPerformanceTabs() を実行（初回のみ）
  6. Apps Script エディタで updatePerformanceAnalysis() を実行
     → 「KPI分析」シートが自動計算される

Day 2:
  7. Python で sync_to_kachitalk.py を実行
     → カチトークへデータが送信される
  8. カチトークダッシュボードで確認

【毎月の確認】
  - Google Sheet「KPI分析」で詳細を確認
  - カチトークダッシュボードで全体を確認
  - 営業会議でランキング・改善点を共有
```

---

## トラブルシューティングフロー

```
【症状】カチトークにデータが表示されない

├─ Step 1: CSVファイルの確認
│  └─ /tmp/sales_performance_for_sheets.csv が存在するか
│     ├─ 無い場合 → extract_sales_performance.py を再実行
│     └─ ある場合 → Step 2 へ
│
├─ Step 2: CSVの内容確認
│  └─ head /tmp/sales_performance_for_sheets.csv
│     ├─ 営業マン名が正確か（スペース・文字種を確認）
│     ├─ 月が「5月」「6月」等正確か
│     └─ KPI値が数値か
│
├─ Step 3: Google Sheet の確認
│  └─ 「営業成績（月別）」シート
│     ├─ A1セルにヘッダーがあるか
│     ├─ データが40行あるか（8名 × 5月）
│     └─ 数式やエラーが無いか
│
├─ Step 4: Apps Script の確認
│  └─ updatePerformanceAnalysis() が実行されたか
│     ├─ ログで「✓ KPI分析の更新完了」を確認
│     └─ 「KPI分析」シートが計算されているか
│
└─ Step 5: カチトーク API の確認
   └─ sync_to_kachitalk.py をテスト実行
      ├─ 接続確認メッセージを確認
      ├─ 送信成功メッセージを確認
      └─ 失敗メッセージがあれば管理者に確認
```

---

## 拡張ポイント（将来実装）

### 短期（1-2ヶ月）
- [ ] Google Sheets API統合（手動CSVエクスポート不要）
- [ ] GitHub Actions での自動同期（毎月1日朝自動実行）
- [ ] カチトーク API エンドポイント実装（軸・カチトーク側の実装が必要）

### 中期（3-6ヶ月）
- [ ] リアルタイム同期（日次更新）
- [ ] メール・LINE通知（新しいランキング発表時）
- [ ] グラフ・チャート化（推移の可視化）
- [ ] 成長率・前月比の自動計算

### 長期（6-12ヶ月）
- [ ] 他社システムとの統合（CRM・ERP）
- [ ] 予測・目標設定機能
- [ ] AI による成績分析・改善提案

---

## 技術スタック

| レイヤー | 技術 | 役割 |
|---------|------|------|
| **データ入力** | Excel | 営業成績の原始データ |
| **データ集約** | Google Sheets | 統一フォーマット・基盤 |
| **分析・計算** | Google Apps Script | 月別平均・ランキング・トップ判定 |
| **データ変換** | Python 3.8+ | Excel→CSV→JSON 変換 |
| **API通信** | requests (Python) | HTTP Bearer Token認証 |
| **ダッシュボード** | kakei-crm / カチトーク | 営業管理・可視化 |
| **CI/CD** | GitHub Actions | 自動同期（将来） |

---

## セキュリティ考慮事項

1. **認証**: Bearer Token方式（HTTPS必須）
2. **権限**: API トークンは環境変数で管理（リポジトリに直貼り禁止）
3. **データ**: 個人情報は含まない（営業成績KPIのみ）
4. **アクセス制御**: Google Sheet は適切な共有設定（編集者限定）
5. **ログ**: 同期実行ログはスクリプトが記録、個人情報は非表示

---

## ドキュメント体系

| ドキュメント | 対象者 | 内容 |
|-----------|-------|------|
| **README.md** | 全員 | システム概要・クイックスタート |
| **README_KACHITALK_INTEGRATION.md** | 運用者 | カチトーク連携・毎月の手順 |
| **ARCHITECTURE.md** | 開発者・管理者 | このファイル。技術詳細 |
| **実装ガイド** | 開発者 | GAS関数リファレンス |
| **セットアップマニュアル** | 初期設定者 | 初回セットアップ（15分） |

---

**最終更新**: 2026-10-18  
**作成者**: Claude Haiku 4.5
