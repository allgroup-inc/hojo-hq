# Block 2 統合テスト自動化完了レポート

> **実行日**: 2026-09-29  
> **対象**: Issue #5-8 (kakei-apo統合, 業務軸連携テスト)  
> **ステータス**: ✅ 自動化スクリプト構築完了  

---

## 📊 実装サマリー

### ✅ 完成内容

| # | コンポーネント | ファイル | テスト数 | 対応Issue |
|---|----------------|---------|---------|-----------|
| 1 | 業務軸統合テスト | `business-axis-integration-tests.py` | 10 | #6, #7, #8 |
| 2 | APIチェーンテスト | `api-chain-tests.py` | 6ステップ | #6, #7 |
| 3 | UIスモークテスト | `ui-integration-tests.ts` | 12 | #8 |
| 4 | パフォーマンステスト | `performance-baseline.py` | 4シナリオ | #8, #14 |
| 5 | 実行フレームワーク | `run-block2-tests.sh` | - | 統合実行 |

**合計テスト項目**: 32+ テストケース  
**実装行数**: 2,000+ 行のテストコード  

---

## 🎯 テスト仕様

### 1. 業務軸統合テスト (Issue #6, #7, #8)

```
❶入口システム → KAKEHASHI APO管理 → ❂訪問管理 / ❸保全CRM
```

#### テスト項目

| # | API | メソッド | テスト内容 | 成功条件 |
|---|-----|---------|-----------|---------|
| 1 | `/api/v1/appointments` | POST | 新規アポ登録 | 201 Created + APO-ID返却 |
| 2 | `/api/v1/sales-reps/round-robin` | GET | ラウンドロビン振り分け | 200 + 営業マンID |
| 3 | `/api/v1/notifications/slack-webhook` | POST | Slack通知送信 | 200 + message_id |
| 4 | `/api/visits/completed` | POST | 訪問完了通知 | 200 + processing_id |
| 5 | `/api/visits/cancelled` | POST | 訪問キャンセル通知 | 200 |
| 6 | `/api/v1/kpi/daily-summary` | GET | 日次KPI集計 | 200 + 件数データ |
| 7 | `/api/v1/kpi/monthly-performance` | GET | 月間パフォーマンスレポート | 200 + sales_reps配列 |
| 8 | `/api/v1/sales-reps/{id}/free-slots` | GET | 営業マン空き枠取得 | 200 + slots配列 |
| 9 | `/api/v1/appointments/{id}` | PATCH | アポ日程変更 | 200 |
| 10 | `/api/v1/appointments/{id}/cancel` | POST | アポキャンセル | 200 |

**実行コマンド**:
```bash
python3 scripts/integration-tests/business-axis-integration-tests.py
```

**期待される結果**: 10/10 成功 (100%)

---

### 2. APIチェーンテスト (Issue #6, #7)

実際の営業フローを再現した 6ステップのシーケンシャルテスト

```
Step 1: 新規アポ登録 (POST /api/v1/appointments)
   ↓ [取得] APO-ID
Step 2: ラウンドロビン振り分け (GET /api/v1/sales-reps/round-robin)
   ↓ [取得] 営業マンID
Step 3: Slack通知送信 (POST /api/v1/notifications/slack-webhook)
   ↓ [確認] 通知送信成功
Step 4: 訪問完了通知 (POST /api/visits/completed)
   ↓ [確認] KPI更新トリガー
Step 5: KPI集計取得 (GET /api/v1/kpi/daily-summary)
   ↓ [取得] 今日の実績
Step 6: 月間レポート生成 (GET /api/v1/kpi/monthly-performance)
   ↓ [確認] レポート出力
```

**計測項目**: 各ステップの応答時間 + 連携の正常性

**実行コマンド**:
```bash
python3 scripts/integration-tests/api-chain-tests.py --repeat 1
```

**期待される結果**: 6/6 ステップ成功 (100%)

---

### 3. UI統合テスト (Issue #8)

Playwright を使用したブラウザ自動化テスト

#### テスト対象（12項目）

| # | テスト | 検査項目 | デバイス |
|---|--------|---------|---------|
| 1-3 | カレンダー表示 (月/週/日) | レンダリング正常性 | Desktop |
| 4 | ドラッグ&ドロップ操作 | アポ時間変更 | Desktop |
| 5 | 詳細モーダル | アポ情報表示 | Desktop |
| 6 | 営業マン検索 | フィルタリング | Desktop |
| 7 | ステータスフィルタ | SCHEDULED/COMPLETED/CANCELLED | Desktop |
| 8 | モバイル対応 | 375x667ビューポート | Mobile (iPhone SE) |
| 9 | タブレット対応 | 768x1024ビューポート | Tablet (iPad) |
| 10 | 新規登録フォーム | フォーム入力→送信 | Desktop |
| 11 | フォーム検証 | バリデーションエラー | Desktop |
| 12 | パフォーマンス | ページロード時間計測 | Desktop |

**実行コマンド**:
```bash
npx playwright test scripts/integration-tests/ui-integration-tests.ts
```

**期待される結果**: 12/12 テスト成功 (100%)

---

### 4. パフォーマンスベースライン (Issue #8, #14)

複数の負荷シナリオでのレスポンス時間・スループット計測

#### 負荷シナリオ

| シナリオ | 並行ユーザー | リクエスト/ユーザー | 用途 |
|---------|-------------|-----------------|------|
| ベースライン | 1 | 10 | 基準値設定 |
| 軽負荷 | 5 | 10 | 通常運用想定 |
| 中負荷 | 10 | 10 | ピーク時想定 |
| 高負荷 | 20 | 5 | ストレステスト |

#### 計測対象エンドポイント

- GET `/api/v1/appointments` (アポ一覧)
- GET `/api/v1/sales-reps` (営業マン一覧)
- GET `/api/v1/kpi/daily-summary` (日次KPI)
- GET `/api/v1/kpi/monthly-performance` (月間パフォーマンス)

#### 性能基準

| 指標 | 基準値 | 検査方法 |
|------|-------|---------|
| P95応答時間 | ≤ 1000ms | 95%のリクエストが1秒以内 |
| P99応答時間 | ≤ 2000ms | 99%のリクエストが2秒以内 |
| エラー率 | ≤ 1% | エラー件数は全体の1%以下 |
| スループット | ≥ 10 RPS | 最低10リクエスト/秒 |

**実行コマンド**:
```bash
# ベースライン計測
python3 scripts/integration-tests/performance-baseline.py

# ストレステスト付き（60秒間）
python3 scripts/integration-tests/performance-baseline.py --stress-test --duration 60
```

**期待される結果**: すべての基準を満たす

---

## 🚀 実行方法

### 全テスト一括実行

```bash
# 統合実行スクリプト
./scripts/integration-tests/run-block2-tests.sh

# ベース URL 指定
BASE_URL=http://localhost:3000 ./scripts/integration-tests/run-block2-tests.sh
```

### 個別テスト実行

```bash
# 業務軸統合テスト
python3 scripts/integration-tests/business-axis-integration-tests.py

# APIチェーンテスト
python3 scripts/integration-tests/api-chain-tests.py

# UIテスト
npx playwright test scripts/integration-tests/ui-integration-tests.ts

# パフォーマンステスト
python3 scripts/integration-tests/performance-baseline.py
```

---

## 📈 テスト結果の解釈

### ✅ 全テスト合格の場合

```
🎉 Block 2 統合テスト合格! Gateway G1 クリア準備完了

次のステップ:
  1. ✅ Issue #5-8 を Close
  2. ✅ Gateway G1 判定を実施 (2026-10-03 16:00)
     - API仕様確定 (Issue #1)
     - マイグレーション検証完了 (Issue #4)
     - 統合テスト合格 (本テスト)
  3. ✅ Block 3 本番環境準備を開始
```

### ⚠️ テスト失敗の場合

| エラー | 原因 | 対応 |
|--------|------|------|
| API接続エラー | サーバー未起動 | `curl http://localhost:3000/health` で確認 |
| 応答時間超過 | DB遅延 | PostgreSQL インデックス確認・キャッシュレイヤー検討 |
| エラー率が高い | リソース不足 | サーバーログ確認・リソース増強 |

---

## 🛠️ トラブルシューティング

### Q: `ConnectionError: HTTPConnection refused`

**A**: APIサーバーが起動していません
```bash
ps aux | grep node
curl -s http://localhost:3000/health
```

### Q: `JWT トークン無効`

**A**: テストトークンを更新
```python
self.jwt_token = "新しいトークン"
```

### Q: `Playwright not found`

**A**: UI テストセットアップ
```bash
npm install -D @playwright/test
npx playwright install
```

---

## 📋 GitHub Actions CI/CD 統合

```yaml
# .github/workflows/block2-integration-tests.yml
name: Block 2 Integration Tests

on: [push, pull_request]

jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: password
    steps:
      - uses: actions/checkout@v3
      - run: ./scripts/integration-tests/run-block2-tests.sh
        env:
          BASE_URL: http://localhost:3000
```

---

## 🎯 Gateway G1 判定基準

Block 2 テスト合格 = 以下のすべてを満たす：

- ✅ **業務軸統合テスト**: 10/10 成功
- ✅ **APIチェーンテスト**: 6/6 成功  
- ✅ **UIテスト**: 12/12 成功
- ✅ **パフォーマンス**: P95 ≤1000ms, エラー率 ≤1%

**判定時刻**: 2026-10-03 16:00 JST  
**判定責任者**: PM / プロダクトリーダー

---

## 📂 ファイル一覧

```
scripts/integration-tests/
├── README.md                                    # テスト実行ガイド
├── business-axis-integration-tests.py          # 業務軸統合テスト (10テスト)
├── api-chain-tests.py                          # APIチェーンテスト (6ステップ)
├── ui-integration-tests.ts                     # UI統合テスト (Playwright, 12テスト)
├── performance-baseline.py                     # パフォーマンス計測 (4シナリオ)
├── run-block2-tests.sh                         # 統合実行スクリプト
├── conftest.py                                 # Pytest 設定
├── pytest.ini                                  # Pytest 初期化
└── __init__.py                                 # パッケージ初期化
```

---

## 📊 実装状況

### Block 1 (2026-09-29 完了)
- ✅ API仕様書最終化 (Issue #1)
- ✅ GASデータ抽出 (Issue #2)
- ✅ マイグレーションスクリプト (Issue #3)
- ✅ テスト環境マイグレーション検証 (Issue #4)

### Block 2 (2026-10-01-03 実行予定)
- 🚀 kakei-apo 統合 (Issue #5)
- 🚀 業務軸連携テスト (本実装, Issue #6-8)
- 🚀 Gateway G1 判定 (2026-10-03 16:00)

### Block 3 (2026-10-04-07)
- ⏳ 本番環境インフラ構築 (Issue #10-12)

### Block 4 (2026-10-08-10)
- ⏳ 本番デプロイ・運用開始 (Issue #13-16)

---

## ✨ 次のステップ

1. **2026-10-01**: Block 2 テスト実行開始
2. **2026-10-01-03**: 統合テスト実施 (本実装で自動化)
3. **2026-10-03 16:00**: Gateway G1 Pass/Fail 判定
4. **2026-10-04**: Block 3 本番環境準備開始（G1 Pass時）

---

**最終更新**: 2026-09-29  
**実装者**: Claude Automation Team  
**ステータス**: ✅ 自動化完了・テスト実行待機中
