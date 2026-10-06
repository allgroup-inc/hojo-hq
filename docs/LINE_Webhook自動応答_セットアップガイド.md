# LINE Webhook 自動応答メッセージ — セットアップガイド

## 概要

LINE公式アカウントの「会社情報登録」時の自動応答メッセージをWebhook経由で自動化します。これにより:
- メッセージ内容のバージョン管理が可能
- 変更を即座に反映できる
- 受け取った情報を自動で確認メッセージに含める

## セットアップ手順

### ステップ1: Google Apps Script（GAS）へコードをデプロイ

1. **Google Apps Script プロジェクトを開く**
   - `glow-ma` のGAS プロジェクト（または新規作成）
   - エディタ内で新しいファイルを作成: `line_webhook_handler.gs`

2. **コードをコピー**
   - `scripts/line_webhook_handler.gs` の全内容をコピー
   - GAS エディタに貼り付け

3. **認証情報を設定**
   - **プロジェクト設定** → **スクリプトプロパティ**
   - 以下を追加:
     - `LINE_CHANNEL_ACCESS_TOKEN`: LINE Channel Access Token
     - `LINE_CHANNEL_SECRET`: LINE Channel Secret

   ※ 取得方法:
   - [LINE Developers Console](https://developers.line.biz/)
   - 該当チャネル → 「設定」タブ → 「Channel credentials」

4. **Webhookをデプロイ**
   - **「新しいデプロイ」** をクリック
   - **種類**: 「ウェブアプリ」を選択
   - **実行者**: 「ウェブアプリケーションにアクセスしているユーザー」を選択
   - **アクセスできるユーザー**: 「すべてのユーザー」を選択
   - **デプロイ** をクリック
   - Webhook URL をコピー（フォーマット: `https://script.google.com/...`）

### ステップ2: LINE Channel の Webhook URL を設定

1. **[LINE Developers Console](https://developers.line.biz/) にアクセス**
   - 該当チャネルを選択

2. **Messaging API → Webhook 設定**
   - **Webhook URL**: ステップ1でコピーしたURLを貼り付け
   - **Webhook の使用**: 「オン」に切り替え
   - **検証** をクリック（"Connected" と表示されればOK）

3. **自動応答メッセージを無効化**（重要）
   - LINE Official Account Manager で、従来の「【会社情報登録】」自動応答を**オフ**にする
   - （Webhook と自動応答メッセージが両方有効だと二重応答になるため）

### ステップ3: 動作確認

1. **テスト送信**
   - 管理者用 LINE アカウントから以下を送信:
   ```
   【会社情報登録】
   企業名: テスト株式会社
   代表者: 山田太郎
   所在地: 沖縄県那覇市
   電話: 098-123-4567
   ```

2. **応答を確認**
   - 改善されたメッセージが返信される
   - 企業名・代表者・所在地・電話が確認メッセージに表示される

3. **ログを確認**
   - GAS プロジェクト内のスプレッドシート「LINE_Webhook_Log」に記録される
   - 各送受信イベントをトラッキング可能

## メッセージテンプレートの更新

改善されたメッセージの内容を変更する場合:

1. `scripts/line_webhook_handler.gs` の `COMPANY_REGISTRATION_REPLY` を編集
2. GAS エディタに反映
3. **自動で反映される**（デプロイ不要）

## トラブルシューティング

| 症状 | 原因 | 対策 |
|---|---|---|
| Webhook検証に失敗 | URLが間違っている / デプロイが失敗している | URL をコピーし直し、Webhook設定を再度実行 |
| メッセージが返信されない | 自動応答メッセージと両方有効 / チャネル認証情報が未設定 | 自動応答をオフにする / スクリプトプロパティを確認 |
| メッセージが二重に返信される | 自動応答メッセージと Webhook が両方有効 | LINE Official Account Manager の自動応答を**必ずオフ**にする |
| 登録情報が「(確認中)」と表示される | フォーマットが異なる | 送信形式を確認（改行区切り、「企業名:」など） |

## セキュリティ注意事項

- **LINE_CHANNEL_SECRET**: リポジトリにコミットしない（GAS スクリプトプロパティのみに保存）
- **Webhook URL**: 署名検証により不正なリクエストから保護
- **ユーザーID**: ログシートに LINE User ID が記録される（アクセス制限を設定）

## 関連ファイル

- `scripts/line_webhook_handler.gs` — Webhook ハンドラー実装
- `docs/LINE運用設計.md` — LINE 運用全体設計
- `docs/LINE_Webhook自動応答_セットアップガイド.md` — このファイル

## 参考リンク

- [LINE Messaging API ドキュメント](https://developers.line.biz/en/docs/messaging-api/)
- [LINE Developers Console](https://developers.line.biz/)
- [Google Apps Script ドキュメント](https://developers.google.com/apps-script)
