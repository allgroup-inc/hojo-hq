# エンライフ営業成績 ← → カチトーク連携ガイド

Google Sheetの営業成績データをカチトークと連携し、営業管理ダッシュボードから一元管理できるようにします。

## 概要

```
Excel（営業成績確定）
    ↓
Google Sheet「営業成績（月別）」
    ↓
extract_sales_performance.py（CSV形式で抽出）
    ↓
sync_to_kachitalk.py（カチトークへ送信）
    ↓
カチトーク状況確認ダッシュボード
```

## 前提条件

- Google Sheetの「営業成績（月別）」シートにデータが入力済み
- カチトークAPI認証トークン（カチトーク管理者から取得）
- Python 3.8以上 + `requests` ライブラリ

## セットアップ手順

### 1. 環境変数設定

カチトークのAPI認証情報を環境変数として設定します：

```bash
# Linux / Mac の場合
export KACHITALK_ENDPOINT="https://kachitalk-line-enlife.azurewebsites.net"
export KACHITALK_API_TOKEN="<カチトークから取得したトークン>"

# Windows (PowerShell) の場合
$env:KACHITALK_ENDPOINT="https://kachitalk-line-enlife.azurewebsites.net"
$env:KACHITALK_API_TOKEN="<カチトークから取得したトークン>"
```

### 2. Pythonライブラリのインストール

```bash
pip install requests
```

### 3. CSVエクスポートと同期（毎月の実行手順）

#### 手順A: Excelからデータを抽出

```bash
python3 /home/user/hojo-hq/enlife/scripts/extract_sales_performance.py
```

出力: `/tmp/sales_performance_for_sheets.csv`

#### 手順B: Google Sheetに貼り付け

1. CSVをテキストエディタで開く
2. すべての行をコピー（Ctrl+A）
3. Google Sheetの「営業成績（月別）」シートを開く
4. セル A1 をクリック
5. 貼り付け（Ctrl+V）
6. Apps Scriptエディタで `updatePerformanceAnalysis()` を実行

#### 手順C: カチトークへ同期

```bash
python3 /home/user/hojo-hq/enlife/scripts/sync_to_kachitalk.py \
  --csv /tmp/sales_performance_for_sheets.csv \
  --endpoint "$KACHITALK_ENDPOINT" \
  --token "$KACHITALK_API_TOKEN"
```

成功メッセージが表示されたら、カチトークの状況確認URLでデータが表示されるようになります。

---

## カチトークでの確認方法

### 営業成績ダッシュボード

カチトークの「状況確認」セクションで、以下の情報が表示されます：

- **月別営業成績**: 5月〜9月の営業メンバー別KPI実績
- **KPI分析**: 平均値・ランキング・トップパフォーマー
- **営業メンバー別詳細**: 個別営業マンの実績推移

### URL

```
https://kachitalk-line-enlife.azurewebsites.net/admin?key=<アクセスキー>
```

※ `<アクセスキー>` はカチトーク管理者から取得

---

## 自動化オプション

### GitHub Actions での自動同期（上級）

`.github/workflows/enlife-kachitalk-sync.yml` を作成して、毎月初にGoogle Sheetからカチトークへ自動同期します。

```yaml
name: エンライフ営業成績 → カチトーク同期

on:
  schedule:
    - cron: '0 8 1 * *'  # 毎月1日朝8時 JST

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Python セットアップ
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: 依存関係インストール
        run: pip install requests
      
      - name: CSV抽出
        run: |
          python3 enlife/scripts/extract_sales_performance.py
      
      - name: カチトークへ同期
        run: |
          python3 enlife/scripts/sync_to_kachitalk.py \
            --csv /tmp/sales_performance_for_sheets.csv \
            --endpoint "${{ secrets.KACHITALK_ENDPOINT }}" \
            --token "${{ secrets.KACHITALK_API_TOKEN }}"
        env:
          KACHITALK_ENDPOINT: ${{ secrets.KACHITALK_ENDPOINT }}
          KACHITALK_API_TOKEN: ${{ secrets.KACHITALK_API_TOKEN }}
```

### Google Apps Script での自動実行

Google Sheetで `updatePerformanceAnalysis()` 実行後、自動的にカチトークへ送信する処理を追加：

```javascript
// Google Sheetの Apps Script
function onSalesDataUpdated() {
  // updatePerformanceAnalysis() 実行後に呼ばれる
  syncToKachiTalk();
}

function syncToKachiTalk() {
  const data = getSalesPerformanceSummary();
  const endpoint = PropertiesService.getScriptProperties().getProperty('KACHITALK_ENDPOINT');
  const token = PropertiesService.getScriptProperties().getProperty('KACHITALK_TOKEN');
  
  const options = {
    method: 'post',
    headers: {
      'Authorization': 'Bearer ' + token,
      'Content-Type': 'application/json'
    },
    payload: JSON.stringify(data),
    muteHttpExceptions: true
  };
  
  const response = UrlFetchApp.fetch(endpoint + '/api/sales-performance', options);
  Logger.log('KachiTalk sync response: ' + response.getResponseCode());
}
```

---

## トラブルシューティング

### 「カチトーク接続失敗」エラー

**原因**: APIエンドポイントまたはトークンが正しくない

**対策**:
1. `KACHITALK_ENDPOINT` と `KACHITALK_API_TOKEN` が正しく設定されているか確認
2. トークンが有効期限切れでないか確認
3. カチトーク管理者に接続テストを依頼

```bash
# テスト実行
python3 -c "
from enlife.scripts.sync_to_kachitalk import KachiTalkSyncer
syncer = KachiTalkSyncer('$KACHITALK_ENDPOINT', '$KACHITALK_API_TOKEN')
print('接続テスト:', 'OK' if syncer.test_connection() else 'NG')
"
```

### 「ファイルが見つかりません」エラー

**原因**: CSVファイルが生成されていない

**対策**:
1. `extract_sales_performance.py` が正常に終了したか確認
2. Excelファイルのパスが正しいか確認
3. `/tmp/sales_performance_for_sheets.csv` が存在するか確認

```bash
# CSVファイルを確認
ls -la /tmp/sales_performance_for_sheets.csv
head /tmp/sales_performance_for_sheets.csv
```

### カチトークに一部データしか送信されていない

**原因**: 営業マン名または月が正確でない可能性

**対策**:
1. Google Sheetの営業マン名を確認（スペース・文字種を正確に）
2. 月の表記が「5月」「6月」など正確か確認
3. 手動で同期スクリプトを実行し、エラーメッセージを確認

```bash
python3 /home/user/hojo-hq/enlife/scripts/sync_to_kachitalk.py \
  --csv /tmp/sales_performance_for_sheets.csv \
  --endpoint "$KACHITALK_ENDPOINT" \
  --token "$KACHITALK_API_TOKEN"
```

---

## 関連ドキュメント

- **営業成績管理システム概要**: `enlife/README.md`
- **セットアップマニュアル**: `docs/enlife_営業成績管理システム_セットアップ完全マニュアル.md`
- **実装ガイド**: `docs/enlife_営業成績管理システム_実装ガイド.md`
- **カチトーク管理者向け**: `kakei-crm/deploy/デプロイ手順_カチトークへ_v0.1.md`

---

## サポート

問題が発生した場合:

1. 上記の「トラブルシューティング」セクションを確認
2. `/tmp/sales_performance_for_sheets.csv` の内容を確認
3. カチトーク管理者にAPI接続を確認してもらう
4. GitHub Issue で報告

**最終更新**: 2026-10-18
