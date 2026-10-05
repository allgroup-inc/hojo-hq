# Block 2 統合テストスイート

> **⚠️ 2026-10-05 注記: このスイートが叩くのは `apps/kakehashi-apo-poc` の PoC API(`/api/v1/...`)であり、軸(kakei-crm)の実窓口(`/api/appointments/{reserve,pending,receive,review,cancel}` 等)ではない。**
> 軸との統合の証拠(Gateway G1)には使わない。軸の窓口仕様 v1 に沿った書き直しは kakei-crm 側で行う
> (kakei-crm `docs/回答_20261005_❶Block2チャット→軸_pre-flight準備状況と残懸念.md`)。
> 結果 JSON の配管(`results_writer.py`、`run-block2-tests.sh`)はそのまま流用する。

> **対象**: Phase 2 Block 2 統合テスト自動化(PoC 向け)  
> **Issue**: #5-8 (kakei-apo統合, 業務軸連携, UI統合)  
> **目標**: 本番環境に向けたエンドツーエンド統合テスト  

---

## 📋 テスト構成

### 1️⃣ 業務軸統合テスト (`business-axis-integration-tests.py`)

**対象**: Issue #6, #7, #8  
**テストシナリオ**: ❶入口システム → KAKEHASHI → ❂訪問管理 / ❸保全CRM

#### テスト項目（全10項目）

| # | テスト | 説明 | Issue |
|---|--------|------|-------|
| 1 | 新規アポ登録 | POST /api/v1/appointments で新規アポを登録 | #6 |
| 2 | ラウンドロビン振り分け | GET /api/v1/sales-reps/round-robin で営業マン自動割当 | #6 |
| 3 | Slack通知送信 | POST /api/v1/notifications/slack-webhook で通知 | #6 |
| 4 | 訪問完了通知 | POST /api/visits/completed で訪問完了を受信 | #7 |
| 5 | 訪問キャンセル通知 | POST /api/visits/cancelled でキャンセル処理 | #7 |
| 6 | KPI自動集計 | GET /api/v1/kpi/daily-summary で日次KPI取得 | #7 |
| 7 | 月間レポート | GET /api/v1/kpi/monthly-performance で月間レポート生成 | #7 |
| 8 | 営業マン空き時間 | GET /api/v1/sales-reps/{id}/free-slots で空き枠取得 | #8 |
| 9 | アポ日程変更 | PATCH /api/v1/appointments/{id} で日程変更 | #8 |
| 10 | アポキャンセル | POST /api/v1/appointments/{id}/cancel でキャンセル | #8 |

**実行方法**:
```bash
python3 scripts/integration-tests/business-axis-integration-tests.py \
  --base-url http://localhost:3000
```

**期待される出力**:
```
✅ 成功 (10件):
   ✅ ❶→KAKEHASHI: アポ登録成功 (201 Created)
   ✅ ❶→KAKEHASHI: ラウンドロビン振り分け成功 (営業マン: rep-001)
   ...
🎯 総合スコア: 100% (10/10)
🎉 全テスト合格! Block 2 統合準備完了
```

---

### 2️⃣ APIチェーンテスト (`api-chain-tests.py`)

**対象**: Issue #6, #7  
**テストシナリオ**: 実際の営業フロー（6ステップチェーン）

#### チェーン構成

```
Chain 1: 新規アポ登録 (POST /api/v1/appointments)
   ↓
Chain 2: ラウンドロビン振り分け (GET /api/v1/sales-reps/round-robin)
   ↓
Chain 3: Slack通知送信 (POST /api/v1/notifications/slack-webhook)
   ↓
Chain 4: 訪問完了通知 (POST /api/visits/completed)
   ↓
Chain 5: KPI取得 (GET /api/v1/kpi/daily-summary)
   ↓
Chain 6: 月間レポート生成 (GET /api/v1/kpi/monthly-performance)
```

**実行方法**:
```bash
python3 scripts/integration-tests/api-chain-tests.py \
  --base-url http://localhost:3000 \
  --repeat 1  # 複数回実行
```

**期待される出力**:
```
📊 APIチェーンテスト結果
ステップ アクション               ステータス  応答時間    備考
------- -------------------- --------- ---------- ----
1       新規アポ登録           ✅        123ms     APO-ID: APO-20261015-0001
2       ラウンドロビン振り分け ✅         45ms     営業太郎 (rep-001)
...
🎯 結果: 6/6 成功 (100%)
🎉 全ステップ合格! API連携が正常に動作しています
```

---

### 3️⃣ UIスモークテスト (`ui-integration-tests.ts`)

**対象**: Issue #8  
**フレームワーク**: Playwright (TypeScript)  
**テスト項目**: 12項目 (カレンダー表示、ドラッグ操作、モーダル、フィルタリング等)

#### テスト項目一覧

| # | テスト | 説明 | 検査内容 |
|---|--------|------|---------|
| 1 | 月表示 | 月表示カレンダーのレンダリング | 7×6グリッド + アポ表示 |
| 2 | 週表示 | 週表示カレンダーのレンダリング | 7列 × 9-18時スロット |
| 3 | 日表示 | 日表示カレンダーのレンダリング | 09:00-18:00時間軸 |
| 4 | ドラッグ操作 | ドラッグ&ドロップでアポ時間変更 | 移動 + 確定ダイアログ |
| 5 | 詳細モーダル | アポイントメント詳細表示 | 5フィールド + 編集ボタン |
| 6 | 営業マン検索 | 営業マン検索フィルタ | 検索→フィルタリング |
| 7 | ステータスフィルタ | ステータス別フィルタリング | SCHEDULED/COMPLETED/CANCELLED |
| 8 | モバイル対応 | モバイルビューポート (375x667) | ハンバーガーメニュー + タッチ対応 |
| 9 | タブレット対応 | タブレットビューポート (768x1024) | サイドバー表示 |
| 10 | 新規登録フォーム | 新規アポ登録フォーム | フィールド入力→送信→成功メッセージ |
| 11 | フォーム検証 | フォーム検証エラー | 必須フィールド未入力時エラー表示 |
| 12 | パフォーマンス計測 | ページロード時間計測 | LCP < 3秒 |

**実行方法**:
```bash
# 初回セットアップ
npm install -D @playwright/test

# テスト実行
npx playwright test scripts/integration-tests/ui-integration-tests.ts

# ブラウザ表示付きで実行
npx playwright test --headed
```

**期待される出力**:
```
📅 月表示カレンダーのレンダリング確認
   ✅ 月表示: 35日 + 47件アポ表示

🎯 12/12 テスト成功
✅ すべてのUI要素が正常に動作しています
```

---

### 4️⃣ パフォーマンスベースライン (`performance-baseline.py`)

**対象**: Issue #8, #14  
**計測項目**: レスポンス時間 (p50, p95, p99)、スループット、エラー率

#### 計測シナリオ

| 負荷シナリオ | 並行ユーザー | リクエスト/ユーザー | 用途 |
|-------------|-------------|------------------|------|
| ベースライン | 1 | 10 | 基準値設定 |
| 軽負荷 | 5 | 10 | 通常運用想定 |
| 中負荷 | 10 | 10 | ピーク時想定 |
| 高負荷 | 20 | 5 | ストレステスト |

#### 性能基準

| 指標 | 基準値 | 説明 |
|------|-------|------|
| P95応答時間 | ≤ 1000ms | 95%のリクエストが1秒以内 |
| P99応答時間 | ≤ 2000ms | 99%のリクエストが2秒以内 |
| エラー率 | ≤ 1% | エラー件数は1%以下 |
| スループット | ≥ 10 RPS | 最低10リクエスト/秒 |

**実行方法**:
```bash
# ベースライン計測
python3 scripts/integration-tests/performance-baseline.py \
  --base-url http://localhost:3000

# ストレステスト付き
python3 scripts/integration-tests/performance-baseline.py \
  --base-url http://localhost:3000 \
  --stress-test \
  --duration 60
```

**期待される出力**:
```
⚡ ベースライン: 1ユーザー x 10リクエスト
🧪 アポ一覧取得 (GET /api/v1/appointments)
  ✓ 成功: 10/10
  ⏱️  平均応答時間: 145ms
  ⏱️  P95: 203ms
  ⏱️  P99: 312ms
  ⏱️  スループット: 45.3 RPS

✅ すべてのパフォーマンス基準を満たしています
```

---

## 🚀 統合テスト実行

### 全テスト実行スクリプト

```bash
# 全テストを順序実行
./scripts/integration-tests/run-block2-tests.sh

# ベース URL 指定
BASE_URL=http://production-api.example.com ./scripts/integration-tests/run-block2-tests.sh
```

### 個別テスト実行

```bash
# 業務軸統合テストのみ
python3 scripts/integration-tests/business-axis-integration-tests.py

# APIチェーンテストのみ
python3 scripts/integration-tests/api-chain-tests.py --repeat 3

# UIテストのみ
npx playwright test scripts/integration-tests/ui-integration-tests.ts

# パフォーマンスベースラインのみ
python3 scripts/integration-tests/performance-baseline.py --stress-test
```

---

## 📊 テスト結果の解釈

### ✅ 全テスト合格の場合

```
🎉 Block 2 統合テスト合格! Gateway G1 クリア準備完了

次のステップ:
  1. ✅ Issue #5-8 を Close
  2. ✅ Gateway G1 判定を実施 (2026-10-03 16:00)
  3. ✅ Block 3 本番環境準備を開始
```

### ❌ テスト失敗の場合

1. **API接続エラー**
   ```
   ❌ 業務軸統合テスト: 失敗 (Status 0)
   → API サーバーが起動しているか確認
   ```

2. **パフォーマンス基準未達**
   ```
   ⚠️ /api/v1/appointments の P95 応答時間が 1523ms
   → データベースインデックスの確認
   → キャッシュレイヤー導入検討
   ```

3. **エラー率が高い**
   ```
   ❌ エラー率が 5.2% (基準値: 1%)
   → サーバーログで詳細なエラーを確認
   → リソース不足の可能性
   ```

---

## 🔧 トラブルシューティング

### Q: `requests.exceptions.ConnectionError: HTTPConnection(host='localhost', port=3000)`

**A**: APIサーバーが起動していません  
```bash
# サーバー起動確認
ps aux | grep node
curl -s http://localhost:3000/health
```

### Q: `JWT トークンが無効です`

**A**: テストトークンを更新してください  
```python
# scripts/integration-tests/business-axis-integration-tests.py
self.jwt_token = "新しいトークン"
```

### Q: `Playwright がインストールされていません`

**A**: UIテストのセットアップ  
```bash
cd /home/user/hojo-hq
npm install -D @playwright/test
npx playwright install
```

### Q: `エラー率が基準値を超えている`

**A**: リソース不足またはDBクエリが遅い  
```bash
# DB 接続確認
psql -h localhost -U postgres -d kakehashi_test -c "SELECT 1"

# スロークエリログ確認
tail -100 /var/log/postgresql/postgresql.log
```

---

## 📈 CI/CD 統合

### GitHub Actions パイプライン

```yaml
# .github/workflows/block2-integration-tests.yml
name: Block 2 Integration Tests

on: [push, pull_request]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: password
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: ./scripts/integration-tests/run-block2-tests.sh
        env:
          BASE_URL: http://localhost:3000
```

---

## 📝 テスト追加ガイド

新しいテストを追加する場合:

1. **テスト関数を作成**
   ```python
   def test_new_feature(self):
       """新機能のテスト"""
       print("\n🧪 [Test N] 新機能テスト")
       # テスト実装...
   ```

2. **run_all_tests() に追加**
   ```python
   def run_all_tests(self):
       self.test_new_feature()  # ← 追加
   ```

3. **実行スクリプトに登録**
   ```bash
   run_test "新機能テスト" "business-axis-integration-tests.py"
   ```

4. **README に記載**
   - テスト項目表にN+1番目の行を追加
   - 期待値を明記

---

## 🎯 Gateway G1 判定基準

Block 2 テストが **全て合格** することが G1 Pass の前提条件：

- ✅ 業務軸統合テスト: 10/10 成功
- ✅ APIチェーンテスト: 6/6 ステップ成功
- ✅ UI統合テスト: 12/12 成功
- ✅ パフォーマンスベースライン: すべての基準を満たす

**判定時刻**: 2026-10-03 16:00 JST  
**判定責任**: PM / プロダクトリーダー
