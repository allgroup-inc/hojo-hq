# Entra ID セットアップガイド

**対象**: KAKEHASHI Phase 1 本番環境  
**前提**: Azure Entra ID テナントアクセス権限必須  
**所要時間**: 20 分

---

## ステップ 1: Entra ID テナント確認

### Azure ポータルアクセス
1. https://portal.azure.com にアクセス
2. **Azure Entra ID** → **テナント情報**
3. **テナント ID** をコピー（後で使用）

例: `xxxxx-xxxxx-xxxxx-xxxxx`

---

## ステップ 2: アプリケーション登録

### Azure Entra ID → アプリの登録
1. **Entra ID** → **アプリの登録**
2. **新規登録**
3. **アプリケーション登録設定**:

| 項目 | 値 |
|---|---|
| 名前 | `KAKEHASHI Sales Appointment (Production)` |
| サポートされているアカウント | 「この組織ディレクトリのみのアカウント」 |
| リダイレクト URI | `https://kakehashi.example.com/auth/callback` |
| | （後で本番ドメインに変更） |

4. **登録**

### クライアント ID コピー
```
アプリケーション(クライアント)ID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## ステップ 3: クライアント シークレット生成

### Entra ID アプリ設定 → 証明書とシークレット
1. **新しいクライアント シークレット**
2. **説明**: `KAKEHASHI Terraform Production`
3. **有効期限**: `24 ヶ月`
4. **追加**

### シークレット値をコピー
```
値: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

⚠️ **重要**: この値は一度きりしか表示されません。  
すぐに GitHub Actions Secrets に保管してください。

---

## ステップ 4: API アクセス許可設定

### アプリケーション → API のアクセス許可
1. **アクセス許可を追加**
2. **Microsoft Graph** を検索・選択
3. **委任されたアクセス許可**:

| アクセス許可 | 説明 |
|---|---|
| `User.Read` | サインイン ユーザー プロファイル読み取り |
| `email` | ユーザーのメール アドレス |
| `profile` | ユーザーの基本プロファイル |

4. **アクセス許可を追加**
5. **[テナント名] に管理者の同意を与えます**

✅ **ステータス**: 「許可されている（管理者の同意）」に変更

---

## ステップ 5: リダイレクト URI 設定

### Entra ID アプリ設定 → 認証
1. **リダイレクト URI**:

**開発環境（ローカル）:**
```
http://localhost:3000/auth/callback
```

**本番環境（AWS）:**
```
https://54.xxx.xxx.xxx/auth/callback
（EC2 Elastic IP）

または

https://kakehashi.example.com/auth/callback
（カスタムドメイン）
```

2. **サポートされているアカウント**:
   - 「この組織ディレクトリのみのアカウント」 ✅

3. **暗黙的フローと ハイブリッド フロー**:
   - [ ] アクセス トークン
   - [x] ID トークン

---

## ステップ 6: トークン設定（オプション）

### Entra ID アプリ設定 → トークン設定
1. **グループ クレーム**:
   - 「セキュリティ グループ」を選択
   - トークンに含まれるグループ情報が必要な場合

2. **トークン 有効期限**:
   - Access Token: 1 時間 (既定)
   - Refresh Token: 無期限推奨

---

## ステップ 7: テストユーザー作成

### Entra ID ユーザー管理 → ユーザー一覧
1. **新しいユーザー** × 12 回
2. **ユーザー作成設定**:

| 項目 | 値 |
|---|---|
| ユーザー名 | `rep-001@company.onmicrosoft.com` |
| 表示名 | `営業マン01` |
| パスワード | `TempPassword@123456` |
| パスワードの変更 | オプション（初回ログイン時に変更を強制） |

3. 12 名分のテストユーザーを作成

### テストユーザー一覧例
```
rep-001@company.onmicrosoft.com - 営業マン01
rep-002@company.onmicrosoft.com - 営業マン02
...
rep-012@company.onmicrosoft.com - 営業マン12
```

---

## ステップ 8: ロール割り当て（オプション）

### アプリケーション ロールの定義
Entra ID → アプリの登録 → アプリロール

| ロール | 説明 |
|---|---|
| `admin` | システム管理者（すべてのアクセス） |
| `apo_staff` | APO スタッフ（予定作成・編集） |
| `sales_rep` | 営業代表（自分の予定のみ） |

**注**: ロール割り当ては Terraform または別途スクリプトで実施

---

## ステップ 9: 環境変数テンプレート作成

### `.env.production` ファイル作成

```bash
# Entra ID 認証
ENTRA_CLIENT_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
ENTRA_CLIENT_SECRET="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
ENTRA_TENANT_ID="xxxxx-xxxxx-xxxxx-xxxxx"
ENTRA_CALLBACK_URL="https://kakehashi.example.com/auth/callback"

# Database
DATABASE_URL="postgresql://kakehashi_admin:PASSWORD@db.xxxxx.rds.amazonaws.com:5432/kakehashi_prod"

# Application
NODE_ENV="production"
PORT="3000"
JWT_ALGORITHM="RS256"
JWT_EXPIRY="1h"
JWT_ISSUER="kakehashi-apo-poc"
JWT_AUDIENCE="kakehashi-apo-poc"
```

⚠️ **重要**: このファイルは `.gitignore` に追加し、git にコミットしないこと

---

## ステップ 10: GitHub Actions Secrets 設定

### GitHub リポジトリ → Settings → Secrets

```
新規シークレット:
- Name: ENTRA_CLIENT_ID
  Value: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

- Name: ENTRA_CLIENT_SECRET
  Value: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

- Name: ENTRA_TENANT_ID
  Value: xxxxx-xxxxx-xxxxx-xxxxx

- Name: ENTRA_CALLBACK_URL
  Value: https://kakehashi.example.com/auth/callback
```

---

## ステップ 11: ローカル環境テスト

### ローカル Entra ID ログインテスト

```bash
# 環境変数をロード
export $(cat .env.development | xargs)

# Backend 起動
cd apps/kakehashi-apo-poc/backend
npm run dev

# ブラウザで開く
open http://localhost:3000/auth/login

# Entra ID テストユーザーでログイン
# ユーザー名: rep-001@company.onmicrosoft.com
# パスワード: TempPassword@123456
```

✅ **成功**: ログイン後、カレンダーページにリダイレクト

---

## ステップ 12: セットアップ完了確認チェックリスト

- [ ] Azure Entra ID テナントアクセス確認
- [ ] アプリケーション登録完了（本番テナント）
- [ ] クライアント ID コピー済み
- [ ] クライアント シークレット生成・保管済み
- [ ] API アクセス許可設定完了
- [ ] リダイレクト URI 設定完了（開発 + 本番）
- [ ] テストユーザー 12 名作成済み
- [ ] ロール定義・割り当て完了（オプション）
- [ ] `.env.production` ファイル作成済み
- [ ] GitHub Actions Secrets 設定済み
- [ ] ローカル環境でログインテスト成功

✅ **すべてチェック完了**したら、**Terraform 実行** に進みます。

---

## トラブルシューティング

### エラー: "AADSTS50058: Silent sign-in request failed"
```
原因: ブラウザキャッシュ・Cookie が古い
解決: シークレットウィンドウで再度ログイン
```

### エラー: "AADSTS65001: User or admin has not consented"
```
原因: アプリケーション API アクセス許可が不足
解決: Entra ID → API アクセス許可で管理者の同意を与える
```

### エラー: "redirect_uri_mismatch"
```
原因: リダイレクト URI が設定と一致していない
解決: 登録 URI を確認・修正し、ENTRA_CALLBACK_URL 環境変数を更新
```

### エラー: "AADSTS700016: Application not found"
```
原因: Client ID が間違っている
解決: Azure ポータルでアプリケーション ID を再確認
```

---

## 本番環境での URI 変更

EC2 インスタンスが起動したら：

1. **Elastic IP アドレス確認**:
```bash
aws ec2 describe-addresses --region ap-northeast-1
# PublicIp: 54.xxx.xxx.xxx
```

2. **Entra ID リダイレクト URI 更新**:
   - `https://54.xxx.xxx.xxx/auth/callback`

3. **環境変数更新**:
```bash
ENTRA_CALLBACK_URL="https://54.xxx.xxx.xxx/auth/callback"
```

4. **EC2 アプリケーション環境変数再設定**:
```bash
# EC2 内で実行
docker stop kakehashi-apo-poc-backend
docker rm kakehashi-apo-poc-backend
# docker-compose.yml を環境変数で再起動
docker-compose up -d
```

---

## 次のステップ

✅ Entra ID セットアップ完了  
→ **Terraform 実行** に進む（SETUP-TERRAFORM.md）

---

**ドキュメント版**: 1.0  
**最終更新**: 2026-09-28
