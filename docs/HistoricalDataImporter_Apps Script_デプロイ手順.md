# HistoricalDataImporter.gs - Apps Script デプロイ手順

このドキュメントは、HistoricalDataImporter.gs を Google Apps Script プロジェクトに追加・デプロイするための手順です。

## 環境制限について

このプロジェクトでは Node.js が未インストールのため `clasp push` が使用できません。
そのため **手動でコードをコピー＆ペーストして登録する** 方式を採用しています。

---

## デプロイ手順

### ステップ1: Apps Script エディタを開く

1. **GLOW企業リレーション台帳** スプレッドシートを開く
2. メニュー: **ツール** → **スクリプト エディタ**
   - または、URL: `https://script.google.com/home/projects/1ETmIVwC2A71ta9VlpUTZSPelTeTFIYs0tirjGtbjknyonz2cFXSFMmFk/edit`
3. Google Apps Script のエディタ画面が開きます

### ステップ2: 新しいファイルを作成

1. エディタ左側の「ファイル」セクションで、`+` アイコンをクリック
2. **スクリプト** を選択
3. ファイル名を **`HistoricalDataImporter.gs`** に設定

### ステップ3: コードをコピー＆ペースト

1. このリポジトリから `glow-ma/src/HistoricalDataImporter.gs` のコード全文をコピー
   - [GitHub リンク](https://github.com/allgroup-inc/hojo-hq/blob/claude/glow-ma-sales-system-mbsak8/glow-ma/src/HistoricalDataImporter.gs)
   - または、ローカルファイルから直接コピー

2. Apps Script エディタの新しいファイル内に **全て貼り付け**

3. **Ctrl+S** または **⌘+S** で保存

### ステップ4: メニュー項目を追加 (AdminRunner.gs への追加)

AdminRunner.gs 内の `onOpen()` 関数に、メニュー項目を追加します：

**現在の AdminRunner.gs の onOpen() 関数を確認**:

```javascript
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('GLOW台帳')
    .addItem('G1フェーズA試験を実行', 'PhaseATestRunner.runPhaseATest')
    .addItem('企業データをCSV出力', 'ShareRunner.exportCompaniesAsCSV')
    .addToUi();
}
```

**メニュー項目を追加**:

```javascript
function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('GLOW台帳')
    .addItem('G1フェーズA試験を実行', 'PhaseATestRunner.runPhaseATest')
    .addItem('企業データをCSV出力', 'ShareRunner.exportCompaniesAsCSV')
    .addItem('福田データ：100件インポート', 'importFukudaHistoricalData')  // ← この行を追加
    .addToUi();
}
```

**追加手順**:

1. AdminRunner.gs を開く
2. `onOpen()` 関数を探す
3. `.addItem('福田データ：100件インポート', 'importFukudaHistoricalData')` の行を追加
4. 保存

### ステップ5: 確認テスト

1. スプレッドシートを **再度開く** または **ページをリロード** (F5)
2. メニュー「GLOW台帳」を開く
3. 新しいメニュー項目 **「福田データ：100件インポート」** が表示されていることを確認
4. 表示されていない場合は、Apps Script エディタを一度閉じ、スプレッドシートをリロードしてから再度確認

---

## サンプル試験で動作確認

### テストデータの準備

1. スプレッドシートに新しいタブ `福田_履歴インポート` を作成
2. [fukuda_historical_sample_data.md](fukuda_historical_sample_data.md) の サンプル10行をコピー
3. タブに貼り付け

### インポート実行

1. メニュー「GLOW台帳」→ **「福田データ：100件インポート」** をクリック
2. 画面に「処理中...」というダイアログが表示
3. 完了したら自動的に `福田_インポート結果` タブが作成・表示される

### 結果確認

結果シートに以下が表示されます：

```
インポート結果
ステータス: 成功
取り込み企業数: 10 件
警告: 2 件
エラー: 0 件

詳細:
Row 1: ✅ 企業ID=C000101, 株式会社ABC建設
Row 2: ✅ 企業ID=C000102, 有限会社XYZ整備
...
Row 4: ⚠️ 警告: 会社名フォーマット異常（个人名義_運送）
...
```

### Web管理画面で確認

1. Web管理画面を開く
2. 企業一覧に新しい企業（例：株式会社ABC建設）が表示されているか確認
3. 企業詳細を開き、「対応履歴」セクションに手紙送付日・架電日が記録されているか確認

---

## トラブルシューティング

### エラー: 「importFukudaHistoricalData は定義されていません」

**原因**: HistoricalDataImporter.gs が正しく登録されていない

**対策**:
1. Apps Script エディタで HistoricalDataImporter.gs が存在するか確認
2. ファイル名が正確に **HistoricalDataImporter.gs** であることを確認
3. 両方のファイル（AdminRunner.gs と HistoricalDataImporter.gs）を **保存** していることを確認
4. スプレッドシートをリロード（F5）してから再度試行

### エラー: 「他の処理が台帳を操作中のため...」

**原因**: 別の処理がスプレッドシートをロックしている

**対策**:
- 数秒待ってから再度実行
- 他の自動化ツール（TimerTrigger など）が走っていないか確認

### エラー: 「福田_履歴インポート」タブが見つかりません

**原因**: ステージングシートの名前が違う

**対策**:
1. 新しいタブの名前を正確に **「福田_履歴インポート」** に設定
2. スペースやひらがなの誤りがないか確認
3. 日本語入力が正確か確認

### 警告: 「日付形式が異なります」

**原因**: 日付が `YYYY/MM/DD` 形式以外

**対策**:
- `2026-09-15` → `2026/09/15` に統一
- `令和8年9月15日` → `2026/09/15` に変換

---

## デプロイ完了チェックリスト

- [ ] HistoricalDataImporter.gs ファイルを作成
- [ ] コード全文をコピー＆ペーストして保存
- [ ] AdminRunner.gs に メニュー項目を追加
- [ ] スプレッドシートをリロード
- [ ] GLOW台帳 メニューに「福田データ：100件インポート」が表示される
- [ ] 福田_履歴インポート タブにサンプル10行を貼り付け
- [ ] インポート実行
- [ ] 結果シートに「成功」と表示される
- [ ] Web管理画面で新規企業が表示される
- [ ] 対応履歴に手紙送付日・架電日が記録されている

---

## 本番投入前チェック

実際の福田さんの100件データでインポートする前に：

1. **サンプルテストに成功** → ✅ 確認済み
2. **福田さんのデータ形式が確認済み** → 福田さんから受領した実際のファイルで形式を確認
3. **データ品質チェック実施** → 結果シートのエラー・警告を確認して修正
4. **バックアップ取得** → インポート前に企業マスタシートをコピー（`企業マスタ_backup_YYYYMMDD_HHMMSS`）

本番インポート実行時は **深夜～早朝（日本時間）** を避け、日中の時間帯に実行してください（問題発生時の即座対応のため）。

---

**デプロイに質問がある場合は、いつでもお声がけください！**
