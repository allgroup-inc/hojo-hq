# PoC Task 8 - 統合テスト・E2E テスト実行ガイド

## 概要

本ドキュメントでは、PoC Task 8 で実装した統合テストとE2Eテストの実行方法を説明します。

- **統合テスト**: バックエンド API の End-to-End テスト (30本)
- **E2E テスト**: Playwright を使用したフロントエンド+バックエンド統合テスト (16本)

## テスト実行方法

### 1. バックエンド統合テスト

#### セットアップ

```bash
cd apps/kakehashi-apo-poc/backend
npm install
```

#### テスト実行

```bash
# 統合テストのみ実行
npm run test:integration

# すべてのテストを実行
npm test

# テスト watch モード（コード変更を監視）
npm run test:watch

# カバレッジレポート生成
npm run test:coverage
```

#### テスト内容

統合テストはバックエンド API の全体的なフロー検証を実施：

| テストスイート | テスト数 | 説明 |
|---|---|---|
| User Authentication Flow | 6 | JWT トークン生成・検証・無効化 |
| Free-time Slot Retrieval | 7 | 空き時間スロット取得・バリデーション |
| RBAC - Role-based Access Control | 6 | ロールベースアクセス制御の検証 |
| End-to-End User Journey | 2 | 完全なユーザーフロー検証 |
| Error Handling | 4 | エラーハンドリング・異常系テスト |
| Health and Status Checks | 2 | ヘルスチェック・タイムスタンプ検証 |
| Appointment Management | 2 | アポイントメント作成・権限確認 |
| Data Consistency Checks | 2 | データ一貫性・複数呼び出し確認 |

#### テスト結果例

```
Test Suites: 1 passed, 1 total
Tests:       30 passed, 30 total
Snapshots:   0 total
Time:        2.778 s
```

### 2. E2E テスト (Playwright)

#### セットアップ

```bash
cd apps/kakehashi-apo-poc
npm install
# または
npm install --legacy-peer-deps  # 依存関係の競合がある場合
```

#### テスト実行

```bash
# E2E テスト実行（開発サーバー自動起動）
npm run test:e2e

# UI モードで実行（インタラクティブ）
npm run test:e2e:ui

# 特定のテストファイルのみ実行
npx playwright test frontend/tests/e2e/calendar-flow.e2e.ts

# 特定のブラウザのみ実行
npx playwright test --project=chromium

# デバッグモード
npx playwright test --debug
```

#### テスト対象ブラウザ

playwright.config.ts で以下のブラウザをテスト対象に設定：

- Desktop Chrome
- Desktop Firefox
- Desktop Safari
- Mobile Chrome (Pixel 5)
- Mobile Safari (iPhone 12)

#### テスト内容

E2E テストはフロントエンド UI とバックエンド API の統合を検証：

| テストスイート | テスト数 | 説明 |
|---|---|---|
| Calendar Rendering | 3 | カレンダー表示・グリッド描画 |
| Appointment Display | 2 | アポイントメント・スロット表示 |
| Navigation | 2 | 月次ナビゲーション・タイムスロット |
| Business Hours Validation | 2 | 営業時間・休憩時間検証 |
| Responsiveness | 2 | モバイル・タブレットビューポート |
| Interaction & State | 3 | キーボードナビゲーション・リロード保持 |
| Error Handling & Resilience | 2 | API 失敗時・コンソールエラー処理 |

#### テスト結果例

```
✓ 16 passed (45.2s)
```

### 3. 開発環境でのテスト実行

#### 統合テスト + E2E テストの連続実行

```bash
# ターミナル 1: バックエンドの開発サーバー起動
cd apps/kakehashi-apo-poc/backend
npm run dev

# ターミナル 2: フロントエンドの開発サーバー起動
cd apps/kakehashi-apo-poc/frontend
npm start

# ターミナル 3: 統合テスト実行
cd apps/kakehashi-apo-poc/backend
npm run test:integration

# ターミナル 4: E2E テスト実行
cd apps/kakehashi-apo-poc
npm run test:e2e
```

## テスト設定の詳細

### バックエンド統合テスト設定

**ファイル**: `backend/jest.config.js`

```javascript
{
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>'],
  testMatch: ['**/?(*.)+(spec|test).ts?(x)'],
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json', 'node']
}
```

**テスト対象ファイル**: `backend/tests/integration.test.ts`

### E2E テスト設定

**ファイル**: `playwright.config.ts`

```typescript
{
  testDir: './frontend/tests/e2e',
  timeout: 30000,
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry'
  },
  webServer: {
    command: 'npm run start',
    url: 'http://localhost:3000',
    reuseExistingServer: true
  }
}
```

**テスト対象ファイル**: `frontend/tests/e2e/calendar-flow.e2e.ts`

## トラブルシューティング

### バックエンド統合テストが失敗する場合

1. **依存関係の再インストール**
   ```bash
   cd apps/kakehashi-apo-poc/backend
   rm -rf node_modules package-lock.json
   npm install
   ```

2. **キーペアの確認**
   ```bash
   # private-key.pem と public-key.pem が存在することを確認
   ls -la apps/kakehashi-apo-poc/backend/*.pem
   ```

3. **ポート競合の確認**
   ```bash
   # テスト実行中に他のサーバーがポート 3000-3100 を使用していないか確認
   lsof -i :3000
   ```

### E2E テストが失敗する場合

1. **開発サーバーの確認**
   ```bash
   # localhost:3000 が正しく起動しているか確認
   curl http://localhost:3000
   ```

2. **Playwright ブラウザのインストール**
   ```bash
   cd apps/kakehashi-apo-poc
   npx playwright install
   ```

3. **テストレポート確認**
   ```bash
   # HTML レポートを生成して確認
   npx playwright show-report
   ```

## CI/CD での実行

GitHub Actions など CI/CD パイプラインでテストを実行する場合：

```yaml
- name: Run integration tests
  run: npm run test:integration
  working-directory: apps/kakehashi-apo-poc/backend

- name: Run E2E tests
  run: npm run test:e2e
  working-directory: apps/kakehashi-apo-poc
```

## テスト カバレッジ

### 統合テストのカバレッジ

- **OAuth/JWT 認証**: 100% カバー
  - トークン生成・検証・有効期限
  - Bearer トークン抽出
  - エラーハンドリング

- **RBAC (Role-based Access Control)**: 100% カバー
  - ADMIN ロール・SALES_REP ロール
  - 所有者確認・全体確認
  - アクセス拒否時の処理

- **Free-time Slot API**: 100% カバー
  - スロット取得・フォーマット検証
  - 営業時間・休憩時間
  - バリデーションエラー

### E2E テストのカバレッジ

- **UI 要素**: カレンダー・スロット・アポイントメント描画
- **ユーザーインタラクション**: ナビゲーション・キーボード操作
- **レスポンシビリティ**: デスクトップ・モバイル・タブレット
- **エラー処理**: API 失敗・コンソールエラー

## 次のステップ

- **Task 9**: Docker・Terraform デプロイ検証
- **Task 10**: ドキュメント・リリースノート作成

---

**最終更新**: 2026-10-08
**バージョン**: PoC v0.1.0
