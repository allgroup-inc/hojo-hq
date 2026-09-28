# ローカル開発環境セットアップ — 管理システムUI

**対象**: 🌟管理システム開発者  
**期間**: 2026-10-01 実装開始時

---

## 📋 準備物

1. **kakei-crm リポジトリ**（既に配置済み）
   ```bash
   /home/user/kakei-crm/apps/callscreen/prototype/site/kanri_system/
   ```

2. **軸側 API サーバー**（開発環境）
   - 起動ポート: 9000 (推奨)
   - エンドポイント: `/api/customers/dossier`

---

## 🛠️ セットアップ手順

### Step 1: kakei-crm へのファイル移設確認

```bash
cd /home/user/kakei-crm/apps/callscreen/prototype/site/kanri_system/

# ファイル構成確認
ls -la
# 出力:
# ├── README.md
# ├── customer_detail.html
# ├── css/theme.css
# ├── js/api-client.js
# └── js/app.js
```

### Step 2: ローカル HTTP サーバーの起動

```bash
cd /home/user/kakei-crm/apps/callscreen/prototype/site/kanri_system/

# Python 3
python3 -m http.server 8000

# または Node.js http-server
npx http-server . -p 8000
```

**出力例**:
```
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
```

### Step 3: ブラウザで開く

```
http://localhost:8000/customer_detail.html?id=KM-000001
```

---

## 🔧 軸側 API サーバーとの連携

### Step 1: 軸側 API の起動（開発環境）

kakei-crm 側で API サーバーを起動（別ターミナル）:

```bash
cd /home/user/kakei-crm

# API サーバー起動（ポート 9000）
python3 -m core.http_api --port 9000
```

### Step 2: UI 側の API_BASE 設定変更

`js/api-client.js` を以下のように編集:

```javascript
const API_CLIENT = {
    base: 'http://localhost:9000/api',  // ← 変更: /api → http://localhost:9000/api

    async getCustomerDossier(customerId) {
        // ... 以下同じ
    }
};
```

### Step 3: ブラウザで確認

```
http://localhost:8000/customer_detail.html?id=KM-000001
```

**期待される動作**:
- ヘッダーに顧客情報が表示される
- Tab 1 の契約テーブルが表示される
- Tab 3 の受渡・管理テーブルが表示される
- Tab 4 の対応記録テーブルが表示される

---

## 🧪 テストシナリオ

### 成功系: 顧客ID で正常読み込み

**URL**: `http://localhost:8000/customer_detail.html?id=KM-000001`

**確認項目**:
- [ ] ページが読み込まれる（3秒以内）
- [ ] ヘッダーに顧客名、住所が表示される
- [ ] Tab 1 に契約テーブルが表示される（少なくとも1行）
- [ ] Tab 3 に受渡・管理テーブルが表示される
- [ ] Tab 4 に対応記録が表示される

### 失敗系: 顧客ID なし

**URL**: `http://localhost:8000/customer_detail.html`

**期待**: エラーメッセージ「顧客IDが指定されていません。」

### 失敗系: 権限なし（API 403）

**URL**: `http://localhost:8000/customer_detail.html?id=KM-000999`

**期待**: エラーメッセージ「権限がありません。管理メンバーでログインしてください。」

---

## 📝 ブラウザの開発者ツール

### ネットワークタブで確認する項目

1. **API リクエスト**
   - URL: `/api/customers/dossier?id=KM-000001`
   - ステータス: 200 OK
   - レスポンスサイズ: 数KB程度

2. **コンソールエラー**
   - CORS エラー: API サーバーの CORS 設定を確認
   - 404 エラー: ファイルパスを確認

### コンソール JavaScript

```javascript
// API クライアントのテスト
API_CLIENT.getCustomerDossier('KM-000001')
    .then(dossier => console.log(dossier))
    .catch(error => console.error(error));
```

---

## 🔌 CORS 設定（本番環境との相違）

### ローカル開発（異なるポート）
- UI: `http://localhost:8000`
- API: `http://localhost:9000`
- → CORS 有効化が必要

### 本番環境（同一ドメイン）
- URL: `/kanri_system/customer_detail.html`
- API: `/api/customers/dossier`
- → CORS 不要（同一ドメイン）

**軸側での CORS 設定**:
```python
# kakei-crm/core/http_api.py
response.headers['Access-Control-Allow-Origin'] = '*'
response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
```

---

## 🚀 トラブルシューティング

### 症状: ページが真っ白で何も表示されない

**原因**: JavaScript エラー

**対処**:
1. ブラウザのコンソール（F12）を開く
2. エラーメッセージを確認
3. `api-client.js` の URL が正しいか確認

### 症状: テーブルが表示されない

**原因**: API が 404 を返している

**対処**:
1. API サーバーが起動しているか確認
2. `js/api-client.js` の `base` URL が正しいか確認
3. ネットワークタブで API リクエストを確認

### 症状: CORS エラーが出る

**原因**: 軸側 API の CORS 設定がない

**対処**:
1. 軸側で `Access-Control-Allow-Origin: *` を設定
2. または、ローカル開発時は `http://localhost:8000` を許可リストに追加

---

## 📋 確認事項（実装前）

- [ ] kakei-crm 側でファイルが正しく配置されている
- [ ] 軸側 API が `GET /api/customers/dossier` を実装している
- [ ] CORS 設定が有効か、または同一ドメイン設定になっている
- [ ] テスト用の顧客ID が軸側 DB に存在する

---

**作成**: 2026-09-28 Claude Code  
**最終更新**: 2026-09-28
