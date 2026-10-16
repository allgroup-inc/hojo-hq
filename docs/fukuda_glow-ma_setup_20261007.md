# 福田さん glow-ma ユーザー登録手順

**決裁日**: 2026-10-07 (小柳さん決裁)  
**実行予定**: 2026-10-08～10  
**実行者**: 小柳さん

---

## 📋 登録情報

| 項目 | 内容 |
|---|---|
| **メールアドレス** | glowfukuda@gmail.com |
| **名前** | 福田 貴志 |
| **部門** | LINE部 & SNS部 (兼務) |
| **直属上司** | 小柳さん |

---

## 🔐 権限設定

以下の4つの権限を付与：

1. **line_alert_responder** - LINE返信メッセージ作成・確認
2. **line_segment_manager** - LINE配信設定（セグメント・タイミング変更）
3. **data_entry** - 企業マスタデータ登録・修正
4. **analytics_viewer** - ダッシュボード・分析レポート閲覧

❌ **付与しない権限**: Instagram投稿スケジュール・コンテンツ承認（ツナグさん・ヒロメさんが承認）

---

## 🛠️ 実装方法（Google Sheets + Google Apps Script）

### 方法A: スプレッドシート ユーザー管理シート に直接登録

**対象**: `glow-ma/` 配下の管理スプレッドシート内「ユーザー管理」シート

以下の情報を新しい行に追加：

```
| メール | 名前 | 部門 | 権限 | 直属上司 | 有効期限 |
|---|---|---|---|---|---|
| glowfukuda@gmail.com | 福田 貴志 | LINE部&SNS部 | line_alert_responder,line_segment_manager,data_entry,analytics_viewer | koyanagi | 2026-12-31 |
```

### 方法B: Google Apps Script で自動登録

以下のコマンド相当の GAS 関数を実行：

```javascript
// 福田さんのユーザーを登録する GAS 関数
function registerFukudaUser() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('ユーザー管理');
  const newRow = sheet.getLastRow() + 1;
  
  sheet.getRange(newRow, 1).setValue('glowfukuda@gmail.com');
  sheet.getRange(newRow, 2).setValue('福田 貴志');
  sheet.getRange(newRow, 3).setValue('LINE部&SNS部');
  sheet.getRange(newRow, 4).setValue('line_alert_responder,line_segment_manager,data_entry,analytics_viewer');
  sheet.getRange(newRow, 5).setValue('koyanagi');
  sheet.getRange(newRow, 6).setValue('2026-12-31');
  
  Logger.log('✅ 福田さんのユーザー登録完了');
}
```

---

## ✅ 登録完了確認

以下の点を確認：

- [ ] glow-ma Web管理画面にログイン可能か
- [ ] 企業マスタデータが表示されるか
- [ ] LINE配信設定メニューにアクセス可能か
- [ ] ダッシュボード・分析ページが表示されるか

---

## 📅 関連スケジュール

| 日付 | タスク |
|---|---|
| 2026-10-07 | 提案書作成・決裁 |
| 2026-10-08～10 | LINE・Instagram権限追加（本メモ含む） |
| 2026-10-10～11 | glow-ma ユーザー登録・権限設定（**このドキュメント**） |
| 2026-10-11 | 訪問ログ収集スプレッドシート設定 |
| 2026-10-14 | 福田さんオンボーディング・操作研修 |
| 2026-10-15 | 新体制運用開始 |

---

## 🔒 セキュリティ・ガバナンス

- **アクセス制御**: glowfukuda@gmail.com の権限スコープを上記に限定
- **監査**: 福田さんのアクション（配信設定変更・データ入力）は月次で監査
- **企業データ**: 登録データはランダムサンプリング検証
- **異常検知**: 異常時は小柳さんへ即通知

---

**実行確認**: 登録完了後、以下を記録  
- 実行日時:  
- 実行者:  
- 確認事項:
