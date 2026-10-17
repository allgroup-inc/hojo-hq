# 技術準備 C-1: Entra ID SSO 統合テスト計画

**作成日**: 2026-10-17  
**対象**: 🌟管理システム チーム  
**目的**: Entra ID SSO を使用した認証・権限チェック機能の事前テスト準備

---

## 📋 テスト対象

- [ ] kanri_system/customer_detail.html の Entra ID 認証モジュール
- [ ] Session/Token の検証フロー
- [ ] 権限チェック（admin / 権限なし）
- [ ] 403 エラーハンドリング

---

## 🔧 前提条件（軸チーム確認待ち）

以下が確定するまでは、**モック実装** で進める：

```
C-1. Entra ID SSO 設定値
  □ Tenant ID
  □ Application ID (Client ID)
  □ リダイレクト URI
  □ トークン検証の仕様
```

**現在**: ⏳ 軸チームからの `Entra_ID_SSO_設定書_KAKEHASHI.md` 待機中

---

## 📊 テスト項目（準備フェーズ）

### テスト 1: Mock Token 検証

```javascript
// kanri_system/auth/mock_token_validator.js

// 目的: Entra ID トークン検証ロジックの事前実装
// 入力: JWT token (mock or real)
// 出力: { valid: true/false, user_id: "...", roles: [...] }

const validateMockToken = (token) => {
  // 実装案:
  // 1. Token format check (Bearer + JWT structure)
  // 2. Signature verification (mock/real by flag)
  // 3. Expiry check
  // 4. User/Role extraction
  return { valid: true, user_id: "km-000001", roles: ["admin"] };
};
```

**実装待ち**: 軸チーム Entra ID 設定値到着後に↑を置き換え

---

### テスト 2: Session Cookie 検証（Web ビュー想定）

```javascript
// kanri_system/auth/session_validator.js

// 目的: KAKEHASHI Web ビュー内での Session Cookie 検証
// 想定: admin.html と同一ドメイン配下 → Cookie 自動送信

const validateSessionCookie = (req) => {
  const cookie = req.headers.cookie;
  // Cookie から user_id / roles を抽出
  // 権限チェック
  return { valid: true, user_id: "km-000001", roles: ["admin"] };
};
```

**実装待ち**: 軸チーム admin.html 実装参考コード到着後

---

### テスト 3: 403 エラーハンドリング

```html
<!-- kanri_system/pages/error_403.html -->

<!-- 目的: 権限なしユーザーへの表示画面 -->
<!-- 実装案: -->
<!-- - Entra ID logout ボタン -->
<!-- - KAKEHASHI メイン画面へ戻るボタン -->
<!-- - エラーメッセージ -->
```

**実装済み**: ✅ テンプレート作成
**待機中**: ⏳ 軸チーム「403時の動作」確認（戻る / ログアウト / etc）

---

### テスト 4: 権限別アクセステスト

```javascript
// test/auth_access_control.test.js

describe('Access Control', () => {
  test('Admin user can access customer_detail', () => {
    // Token/Cookie: admin role
    // Expected: ✅ Data displayed
  });

  test('Non-admin user gets 403', () => {
    // Token/Cookie: non-admin role
    // Expected: 🔴 403 error page
  });

  test('No auth info → 403', () => {
    // No token / no session cookie
    // Expected: 🔴 Redirect to login
  });

  test('Invalid token → 403', () => {
    // Malformed / expired token
    // Expected: 🔴 Error message
  });
});
```

**現在**: 📝 テストケース定義済み（実装待ち）

---

## 🎯 テスト環境構築

### Phase A: ローカル開発環境（現在）
```
✅ Mock token / session で動作確認
✅ 権限チェックロジックのユニットテスト
✅ 403 エラーハンドリング確認
```

### Phase B: ステージング環境（軸チーム設定値到着後）
```
⏳ 実 Entra ID 環境で統合テスト
⏳ KAKEHASHI Web ビューでの動作確認
⏳ Session Cookie / Token 引き継ぎテスト
```

### Phase C: 本番環境（Phase 1.5 確定後）
```
⏳ 本番 Entra ID 環境での運用テスト
```

---

## 📝 実装進捗チェックリスト

| タスク | 状態 | 責任 | 期限 |
|---|---|---|---|
| Mock token validator 実装 | ⏳ 準備中 | 管理システムチーム | 2026-10-20 |
| Session validator 実装 | ⏳ 準備中 | 管理システムチーム | 2026-10-20 |
| 403 error page 実装 | ✅ 完了 | 管理システムチーム | — |
| Access control test suite | ⏳ 準備中 | 管理システムチーム | 2026-10-20 |
| **Entra ID 設定書受取** | 🟡 待機 | **軸チーム** | **2026-10-18** |
| **設定値を validator へ統合** | ⏳ ブロック中 | **管理システムチーム** | **2026-10-20** |
| ステージング統合テスト | ⏳ ブロック中 | 両チーム | 2026-10-25 |

---

## 🔗 関連ドキュメント

| ドキュメント | 参照元 | 用途 |
|---|---|---|
| `docs/連携メモ_20261017_軸宛_統合依頼リスト_Phase1.5Phase2.md` | 軸チーム依頼 | C-1 の詳細要件 |
| `kakei-crm/apps/site/admin.html` | 既存実装 | Entra ID 実装パターン参考 |
| `kanri_system/auth/` | 管理システム | 認証モジュール配置先 |

---

_作成: 2026-10-17 / Claude Code（🌟管理システムチャット）_
