# KachiTalk 認証キー設定ガイド

完全自動化を実現するための認証キー管理方法です。

## 認証キーの取得方法

### ステップ 1: Developer Tools を開く

ブラウザで **F12** キーを押す（または右クリック → 検証）

### ステップ 2: Network タブを確認

1. Developer Tools の **Network** タブをクリック
2. KachiTalk admin にアクセス: https://kachitalk-line-enlife.azurewebsites.net/admin
3. ページを再読込（F5）

### ステップ 3: API リクエストを探す

以下のようなリクエストを探します：
- `/api/export`
- `/export`
- 「CSV」キーワードが含まれるリクエスト

### ステップ 4: 認証ヘッダーをコピー

見つけたリクエストをクリック → **Headers** タブ → 以下をコピー：

```
Authorization: Bearer <TOKEN>
```

または

```
Authorization: <TYPE> <TOKEN>
Cookie: session=<SESSION_ID>
X-API-Key: <KEY>
```

**「Bearer 」の部分を含める必要があります。**

## 認証キーの設定方法

### 方法 1: 環境変数（推奨・安全）

**シェル環境に一時設定：**
```bash
export KACHITALK_AUTH_TOKEN="Bearer eyJhbGciOiJIUzI1NiIs..."
```

**設定確認：**
```bash
echo $KACHITALK_AUTH_TOKEN
```

### 方法 2: スケジュール実行時（自動化）

#### 2-1. GitHub Secrets に登録（最も安全）

このリポジトリが公開なため、認証キーはコミットできません。
代わりに GitHub Secrets に登録して、GitHub Actions で使用します。

**設定手順（リポジトリ管理者）:**

1. GitHub リポジトリページを開く
2. **Settings** → **Secrets and variables** → **Actions**
3. **New repository secret** をクリック
4. 名前: `KACHITALK_AUTH_TOKEN`
5. 値: コピーした認証キー
6. **Add secret** をクリック

**GitHub Actions での使用:**
```yaml
- name: KachiTalk 自動分析
  env:
    KACHITALK_AUTH_TOKEN: ${{ secrets.KACHITALK_AUTH_TOKEN }}
  run: bash /home/user/hojo-hq/scripts/auto_kachitalk_analysis.sh
```

#### 2-2. 環境ファイル（ローカル開発）

非公開リポジトリの場合、`.env` ファイルで管理：

**ファイル: `/home/user/hojo-hq/.env`**
```
KACHITALK_AUTH_TOKEN=Bearer eyJhbGciOiJIUzI1NiIs...
KACHITALK_API_URL=https://kachitalk-line-enlife.azurewebsites.net/api
```

**使用方法:**
```bash
# スクリプト実行前に読み込み
source /home/user/hojo-hq/.env
bash /home/user/hojo-hq/scripts/auto_kachitalk_analysis.sh
```

**注意: `.env` は公開リポジトリにコミットしてはいけません。**

### 方法 3: スケジュール実行に組み込み

#### Cloud Scheduler / Cron の場合

スケジュール登録時に環境変数を設定：

```bash
# システム cron (Linux)
0 9 * * 1 export KACHITALK_AUTH_TOKEN="Bearer ..." && bash /home/user/hojo-hq/scripts/auto_kachitalk_analysis.sh
```

#### クラウド環境（例: GCP Cloud Scheduler）

```
Environment variables を設定:
KACHITALK_AUTH_TOKEN = Bearer eyJhbGciOiJIUzI1NiIs...
```

## セキュリティのベストプラクティス

### ✅ すること

- ✅ トークンをシェルヒストリーから削除: `history -c` (トークン含む行を削除後)
- ✅ 環境変数で管理: `export KACHITALK_AUTH_TOKEN="..."`
- ✅ GitHub Secrets に登録して自動化
- ✅ トークンにスコープ制限がある場合、最小権限を使用
- ✅ トークンの有効期限を確認・更新

### ❌ してはいけないこと

- ❌ トークンをコード・ドキュメント・Slack に貼り付ける
- ❌ トークンをコミット・GitHub にプッシュする
- ❌ 共有リポジトリの `.env` にコミットする
- ❌ トークンを平文でログに出力する
- ❌ HTTPS ではないサイトに送信する

## 認証キーの更新方法

KachiTalk admin のセキュリティ更新でトークンが変わった場合：

1. 上記の「ステップ 1～4」で新しいトークンを取得
2. 環境変数を更新:
   ```bash
   export KACHITALK_AUTH_TOKEN="Bearer <新しいトークン>"
   ```
3. GitHub Secrets の場合は、管理画面から更新

## トラブルシューティング

### Q1: `❌ 認証失敗: トークンが無効または期限切れです`

**原因:** トークンの有効期限が切れているか、形式が間違っている

**対応:**
1. Developer Tools で新しいトークンを取得
2. `echo $KACHITALK_AUTH_TOKEN` で設定を確認
3. トークンに `Bearer ` プレフィックスが含まれているか確認

### Q2: `❌ 権限なし: このトークンはエクスポート権限を持っていません`

**原因:** 使用しているトークンにエクスポート権限がない

**対応:**
1. 別の API リクエスト（エクスポート権限があるもの）からトークンを取得
2. KachiTalk admin で、アカウント権限を確認

### Q3: 環境変数の設定を確認したい

```bash
# 設定確認
echo "Auth Token: $KACHITALK_AUTH_TOKEN"

# 空の場合、設定されていない
if [ -z "$KACHITALK_AUTH_TOKEN" ]; then
  echo "未設定"
fi
```

## 次のステップ

認証キーを設定したら、自動分析パイプラインを実行：

```bash
# 手動実行
bash /home/user/hojo-hq/scripts/auto_kachitalk_analysis.sh

# スケジュール実行（毎週月曜 9:00 JST）
# → 既にトリガーが設定されている場合は不要
```

## 参考ドキュメント

- [KachiTalk 完全分析セットアップガイド](./kachitalk_complete_analysis_setup.md)
- [自動分析システム完成報告](./KachiTalk_自動分析システム_完成報告.md)
