# GitHub Actions × Slack 連携セットアップガイド

診断ページの多層的信頼性システムで、GitHub Actions ワークフロー失敗時に Slack へ即時通知を送るための設定手順です。

## 前提条件

- Slack Workspace の管理権限（小柳さん）
- GitHub repository の Admin 権限

## Step 1: Slack Incoming Webhook を作成

### 1-1. Slack App を作成（初回のみ）

https://api.slack.com/apps から「Create New App」をクリック

```
App name: hojo-hq-notifications
Workspace: もらいわすれ堂 の Workspace を選択
```

### 1-2. Incoming Webhooks を有効化

左メニュー → **Incoming Webhooks** → On に切り替え

### 1-3. Webhook URL を生成

「Add New Webhook to Workspace」をクリック
→ 通知先チャネルを選択: `#tech-alerts` または `#hojo-qa`（新規作成も可）
→ **Webhook URL** をコピー（このURLはSecret値になります）

```
形式: https://hooks.slack.com/services/{WORKSPACE_ID}/{CHANNEL_ID}/{SECRET_TOKEN}
```

## Step 2: GitHub Actions Secret に登録

### 2-1. GitHub repository settings を開く

```
https://github.com/allgroup-inc/hojo-hq/settings/secrets/actions
```

### 2-2. 「New repository secret」をクリック

| 項目 | 値 |
|---|---|
| **Name** | `SLACK_WEBHOOK_URL` |
| **Secret** | Step 1-3 でコピーした Webhook URL |

「Add secret」をクリック

## Step 3: ワークフロー実行確認

### 3-1. GitHub Actions を手動実行

```
https://github.com/allgroup-inc/hojo-hq/actions/workflows/daily-sync-branches.yml
```

「Run workflow」 → ブランチ: `claude/okinawa-disposable-income-plan-axxs6v` を選択 → 「Run workflow」

### 3-2. ワークフロー失敗をシミュレート

テスト用に意図的に生成ファイルを削除してワークフロー失敗を引き起こす：

```bash
# テスト環境で実行（本番環境ではない）
rm site/fukugiiro/shindan/index.html
# ワークフロー実行
# Slack へ通知が届くことを確認
# git restore で復帰
```

### 3-3. 成功を確認

✅ Slack チャネルに以下のメッセージが届いていることを確認：

```
🚨 Daily Sync Workflow Failed

Branch: claude/okinawa-disposable-income-plan-axxs6v
Repository: allgroup-inc/hojo-hq
Action: View Details（リンク）
```

## Step 4: チーム割り当て（SNS部・LINE部）

### 4-1. 日次確認担当者を決定

`docs/診断ページ日次確認チェックリスト.md` の「実施者」欄に以下の情報を入力：

| 実施時刻 | 担当部門 | 担当者 |
|---|---|---|
| 9:00 JST（朝） | SNS部 または LINE部 | 【氏名】 |
| 14:00 JST（午後） | SNS部 または LINE部 | 【氏名】 |

### 4-2. カレンダー共有

Google Calendar / Slack リマインダー / Notion で、毎平日 9:00 / 14:00 の確認タスクをシェア

## トラブルシューティング

### Slack 通知が来ない場合

1. **Webhook URL は正しいか？**
   ```bash
   # テスト送信
   curl -X POST 'YOUR_WEBHOOK_URL' \
     -H 'Content-Type: application/json' \
     -d '{"text":"テストメッセージ"}'
   ```

2. **Secret は正しく設定されているか？**
   - GitHub Settings → Secrets and variables → Actions で確認
   - 値の最初と最後が `https://hooks.slack.com/...` か確認

3. **チャネルは Public か？**
   - Private チャネルの場合、Slack App をチャネルに招待する必要あり

### ワークフローが実行されない場合

1. **cron schedule が正しいか？**
   ```yaml
   - cron: '0 6 * * *'  # 毎日 6:00 UTC
   - cron: '0 12 * * *' # 毎日 12:00 UTC
   ```

2. **ブランチは claude/* か okinawa-disposable-income-plan-axxs6v か？**
   ```bash
   git branch --show-current
   ```

## 参考リンク

- [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions)
- 実装ドキュメント: `docs/診断ページ日次確認チェックリスト.md`
