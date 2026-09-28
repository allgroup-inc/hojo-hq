# デプロイ手順 — 管理システムUI を kanri_system/ に配置

**対象**: 🌟管理システムチャット  
**期限**: 2026-10-15 Phase 1 完成  
**プロトタイプ**: `hojo-hq/prototypes/kanri_system_customer_detail.html`

---

## 📋 配置手順

### Step 1: ファイル構成を kakei-crm へ移設

以下のファイル・フォルダを `kakei-crm/apps/callscreen/prototype/site/kanri_system/` に配置します：

```
kakei-crm/apps/callscreen/prototype/site/kanri_system/
├── README.md              ← 既存（条件・API仕様記載）
├── customer_detail.html   ← 新規作成（プロトタイプをコピー）
├── css/
│   └── theme.css          ← 新規作成（enLife配色・タブスタイル）
├── js/
│   ├── app.js             ← 新規作成（メインアプリケーション）
│   └── api-client.js      ← 新規作成（API呼び出し）
└── assets/
    └── images/            ← 将来用（ロゴ等）
```

### Step 2: プロトタイプからのファイル分割

**hojo-hq/prototypes/kanri_system_customer_detail.html** を以下に分割：

#### `customer_detail.html` (基本テンプレート)
```html
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>顧客カルテ — 家計の見直しやさん</title>
    <link rel="stylesheet" href="./css/theme.css">
</head>
<body>
    <!-- HTML構造のみ →プロトタイプから抽出 -->
    <div id="error-message"></div>
    <div class="header">...</div>
    <div class="container">...</div>

    <script src="./js/app.js"></script>
</body>
</html>
```

#### `css/theme.css` (スタイル)
- `:root` 変数の定義（enLife配色）
- タブナビゲーション
- レイアウト・グリッド
- レスポンシブデザイン

#### `js/app.js` (メインアプリケーション)
- DOM操作（タブ切り替え等）
- レンダリング関数
- URL パラメータ処理
- 初期化処理

#### `js/api-client.js` (API呼び出し)
```javascript
const API_CLIENT = {
  base: '/api',
  async getCustomerDossier(customerId) {
    const url = `${this.base}/customers/dossier?id=${encodeURIComponent(customerId)}`;
    const response = await fetch(url);
    if (!response.ok) throw new Error(`API ${response.status}`);
    return await response.json();
  }
};
```

### Step 3: ローカル開発環境での確認

```bash
cd kakei-crm/apps/callscreen/prototype/site/kanri_system/

# ローカル HTTP サーバーで確認
python3 -m http.server 8000

# ブラウザで開く
# http://localhost:8000/customer_detail.html?id=KM-000001
```

**確認項目**:
- [x] ページ読み込み（HTML構造）
- [x] CSS が適用されている（enLife配色）
- [x] タブ切り替えが動作
- [ ] API呼び出しがクロス失敗（ローカルではプロキシが必要）

### Step 4: 軸側 API との連携確認

**開発環境**で軸側 API を起動している場合：

```bash
# kakei-crm 側で API を起動
cd kakei-crm
python3 -m core.http_api --port 9000

# kanri_system 側で CORS プロキシを設定
# js/api-client.js で以下に変更:
const API_BASE = 'http://localhost:9000/api';
```

**本番環境**（Azure Blob Storage):
- API_BASE = '/api' のまま（同一ドメイン内のルーティング）

### Step 5: デプロイ

```bash
cd kakei-crm

# 本番へのデプロイ（既存手順）
# docs/デプロイ手順_自社ドメイン配信_静的Web.md 参照

az storage blob upload-batch \
  --source apps/callscreen/prototype/site/ \
  --destination containerName \
  --account-name storageAccountName
```

---

## 🧪 テストチェックリスト

### 機能テスト
- [ ] 管理画面が `/kanri_system/customer_detail.html?id=KM-XXXXXX` で開く
- [ ] タブ（契約情報・意向把握・受渡・対応記録）が切り替わる
- [ ] GET /api/customers/dossier が正常に呼び出される
- [ ] 顧客情報がヘッダーに表示される
  - 顧客ID
  - 契約者名
  - 住所
- [ ] 各タブのデータが正しく表示される
  - 契約情報タブ: contracts テーブル
  - 受渡管理タブ: hozen_board テーブル
  - 対応記録タブ: contacts テーブル

### エラーハンドリング
- [ ] 顧客IDなしでアクセス: エラーメッセージ表示
- [ ] API 失敗時: エラーメッセージ表示
- [ ] データなし時: 「記録がありません」表示

### 権限・セキュリティ
- [ ] 管理メンバーのみアクセス（既存 admin.html と同じ認証）
- [ ] API呼び出しに reason ヘッダを含む（軸側規律）
- [ ] 要配慮情報（告知内容）は表示しない

### UI/UX
- [ ] enLife配色が正しく適用（ゴールド#F6C83E、インク#241F14）
- [ ] モバイル対応（タブが2列折り返し等）
- [ ] 読み込み状態を表示（「読み込み中...」）

### パフォーマンス
- [ ] 初回読み込み < 2秒
- [ ] タブ切り替え < 100ms

---

## 🔧 実装時の注意点

### 1. API エラーの処理

管理メンバー以外がアクセスした場合、API は 403 を返します：
```javascript
if (response.status === 403) {
  showError('権限がありません。管理メンバーでログインしてください。');
}
```

### 2. 題外の項目は表示しない

- 会話要約（summary）← 返されない（軸側規律）
- 内部メモ（note）← 返されない
- 要配慮情報（告知内容） ← 告知内容タブは対象外

現在、API は以下の非PII/非要配慮データのみ返します：
- contracts（契約）
- documents（書類）
- contacts（接触記録）←要約・メモなし
- hozen_board（受渡・管理）
- operation_history（操作履歴）

### 3. データが見つからない時の表示

```javascript
if (!dossier.contracts || dossier.contracts.length === 0) {
  container.innerHTML = '<p class="placeholder">契約情報がありません。</p>';
}
```

### 4. admin.html からの遷移

管理メンバー向けの既存 `admin.html` の「カルテ」ボタンから：
```html
<a href="kanri_system/customer_detail.html?id=KM-000000">
  カルテを開く
</a>
```

軸側がリンク追加を管理（条件4）。

---

## 📞 軸側との確認事項

| 項目 | 状態 | 確認内容 |
|---|---|---|
| GET /api/customers/dossier | ✅ 実装済み | レスポンスフォーマット確認 |
| hozen_board 受信・保存 | ✅ 実装済み | 保全CRM からのデータが正確に保存されているか |
| chat_messages | 🔄 検討中 | Phase 2 での実装スケジュール |
| CONTRACT_FIELDS 拡張 | ⏳ 待機中 | 🌟管理システムからの項目定義回答待ち |
| 権限管理・認証 | ✅ 既存 | admin.html と同じメカニズム |

---

## 📝 実装完了後

### 1. 記録ドキュメント作成

実装完了後、以下の記録を軸へ共有：
```markdown
# 記録 2026-10-15 — 🌟管理システム 顧客カルテ画面 Phase 1 実装完了

- [x] customer_detail.html 実装
- [x] 4タブUI 実装
- [x] データ表示（contracts・hozen_board・contacts）
- [x] テスト完了
- [x] 本番デプロイ

**URL**: `/kanri_system/customer_detail.html?id=KM-XXXXXX`
```

### 2. Phase 2 検討

- [ ] chat_messages 実装（WebSocket）
- [ ] 意向把握シート構造化
- [ ] 告知内容タブ（要配慮情報）※守り部審査待ち

---

**以上、UI配置手順です。軸側との確認後、実装を開始してください。**

