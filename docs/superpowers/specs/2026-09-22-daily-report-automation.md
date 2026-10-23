# 日次レポート自動配信システム設計書

**Goal**: GLOW営業管理システムの日次パフォーマンスレポートを、毎朝10時にメール配信・スプレッドシート記載する自動化

**対象**: 小柳さん(takeshi.koyanagi9@gmail.com)宛

---

## 1. データソースと集計ロジック

### 1.1 手紙発送数

**データ源**: 企業マスタ「最終手紙送付日」列

```javascript
// 前日の手紙送付企業を集計
const yesterday = new Date();
yesterday.setDate(yesterday.getDate() - 1);

const lettersSentYesterday = masterRecords.filter(r => 
  r["最終手紙送付日"] === yesterday.toLocaleDateString("ja-JP")
).length;

// 週間(過去7日), 月間(1日〜今日)も同様に集計
```

**レポート出力**:
```
■ 手紙発送
  昨日: 15通
  週間合計: 85通 (前週: 92通, -7通)
  月間合計: 312通 (前月同期: 280通, +32通)
```

---

### 1.2 QRスキャン数

**データ源**: LINE公式アカウント「友だち追加」ログ + GA4イベント

```javascript
// LINE登録ユーザー数(前日) - LINE登録ユーザー数(前々日)
const lineUserCountYesterday = getLineUserCount(yesterday);
const lineUserCountDay Before = getLineUserCount(dayBefore);
const newQRScansYesterday = lineUserCountYesterday - lineUserCountDayBefore;

// 累計QRスキャン数
const totalQRScans = lineUserCountYesterday;

// スキャン率 = 累計QRスキャン / 手紙発送総数
const lettersSentTotal = getTotalLettersSent();
const qrScanRate = (totalQRScans / lettersSentTotal * 100).toFixed(1);
```

**レポート出力**:
```
■ QRスキャン
  昨日: 3件
  週間合計: 18件 (前週: 15件, +3件)
  月間合計: 62件 (前月同期: 51件, +11件)
  累計スキャン率: 1.6% (62/3,875通)
```

---

### 1.3 架電数

**データ源**: BlueBean CTI ログ + 企業マスタ「活動記録」タブ

```javascript
// 昨日の架電を集計(BB API または 活動記録テーブル)
const callsYesterday = interactionRecords.filter(r =>
  r["対応日時"].toLocaleDateString() === yesterday.toLocaleDateString() &&
  r["種別"] === "電話"
).length;

// ランク別内訳
const callsByRank = {
  A: callsYesterday.filter(r => r["企業ランク"] === "A").length,
  B: callsYesterday.filter(r => r["企業ランク"] === "B").length,
  C: callsYesterday.filter(r => r["企業ランク"] === "C").length,
  D: callsYesterday.filter(r => r["企業ランク"] === "D").length,
};
```

**レポート出力**:
```
■ 架電数
  昨日: 8件 (A:5, B:2, C:1, D:0)
  週間合計: 48件 (前週: 42件, +6件)
  月間合計: 178件 (前月同期: 155件, +23件)
  平均通話時間: 4.2分 (昨日)
```

---

### 1.4 訪問・面談数

**データ源**: 企業マスタ「活動記録」タブ

```javascript
// 昨日の訪問を集計
const visitsYesterday = interactionRecords.filter(r =>
  r["対応日時"].toLocaleDateString() === yesterday.toLocaleDateString() &&
  ["訪問", "面談"].includes(r["種別"])
).length;

// 訪問内訳
const visitsByType = {
  "訪問": interactionRecords.filter(r => r["種別"] === "訪問").length,
  "面談": interactionRecords.filter(r => r["種別"] === "面談").length,
};

// 成約数
const contractsYesterday = interactionRecords.filter(r =>
  r["対応日時"].toLocaleDateString() === yesterday.toLocaleDateString() &&
  r["成約"] === true
).length;
```

**レポート出力**:
```
■ 訪問・面談
  昨日: 2件訪問 + 1件面談 = 3件対応 (成約: 0件)
  週間合計: 12件対応 (成約: 1件, 前週: 0件, +1件)
  月間合計: 38件対応 (成約: 2件, 前月同期: 2件)
  成約率: 5.3% (2/38)
```

---

### 1.5 企業スコア・ランク分布

**データ源**: 企業マスタ全体

```javascript
// 現在のランク分布
const rankDistribution = {
  A: masterRecords.filter(r => r["ランク"] === "A").length,
  B: masterRecords.filter(r => r["ランク"] === "B").length,
  C: masterRecords.filter(r => r["ランク"] === "C").length,
  D: masterRecords.filter(r => r["ランク"] === "D").length,
};

// スコア分布(セグメント)
const scoreSegments = {
  "90点以上": masterRecords.filter(r => r["総合スコア"] >= 90).length,
  "70-89点": masterRecords.filter(r => r["総合スコア"] >= 70 && r["総合スコア"] < 90).length,
  "40-69点": masterRecords.filter(r => r["総合スコア"] >= 40 && r["総合スコア"] < 70).length,
  "15-39点": masterRecords.filter(r => r["総合スコア"] >= 15 && r["総合スコア"] < 40).length,
  "15点未満": masterRecords.filter(r => r["総合スコア"] < 15).length,
};

// 昨日のランク昇格・降格数
const rankUpYesterday = interactionRecords.filter(r =>
  r["対応日時"].toLocaleDateString() === yesterday.toLocaleDateString() &&
  r["ランク変更"] === "昇格"
).length;
```

**レポート出力**:
```
■ 企業ランク分布
  A: 24社 (前日: 23社, +1社)
  B: 18社 (前日: 18社)
  C: 15社 (前日: 16社, -1社)
  D: 8社 (前日: 8社)
  ━━━━━
  合計: 65社 (新規登録: 0社)

■ スコアセグメント
  90点以上: 12社 (前週: 10社, +2社)
  70-89点: 18社 (前週: 16社, +2社)
  40-69点: 22社 (前週: 25社, -3社)
  15-39点: 10社 (前週: 10社)
  15点未満: 3社 (前週: 4社, -1社)
```

---

### 1.6 流入ルート別成約数

**データ源**: 企業マスタ「流入ルート」 × 成約企業

```javascript
// 流入ルート別の成約実績
const contractsByRoute = {};
["①紹介", "②手紙DM", "③ミカタ経由", "④開拓架電"].forEach(route => {
  contractsByRoute[route] = masterRecords.filter(r =>
    r["流入ルート"].includes(route) && r["成約"] === true
  ).length;
});

// 流入ルート別の成約率
const routeConversionRate = {};
["①紹介", "②手紙DM", "③ミカタ経由", "④開拓架電"].forEach(route => {
  const total = masterRecords.filter(r => r["流入ルート"].includes(route)).length;
  const contracts = contractsByRoute[route];
  routeConversionRate[route] = (contracts / total * 100).toFixed(1);
});
```

**レポート出力**:
```
■ 流入ルート別成約状況
  ①紹介: 2成約 (7社, 成約率: 28.6%)
  ②手紙DM: 0成約 (28社, 成約率: 0%)
  ③ミカタ経由: 0成約 (12社, 成約率: 0%)
  ④開拓架電: 0成約 (18社, 成約率: 0%)
  ━━━━━━
  合計: 2成約 (65社, 全体成約率: 3.1%)
```

---

## 2. レポート構成

```
【GLOW日次レポート】2026-09-30
配信時刻: 2026-10-01 10:00 JST

━━━━━━━━━━━━━━━━━━━━━━━━━━
■ 手紙発送
  昨日: 15通
  週間合計: 85通 (前週: 92通, -7通)
  月間合計: 312通 (前月同期: 280通, +32通)

■ QRスキャン
  昨日: 3件
  週間合計: 18件 (前週: 15件, +3件)
  月間合計: 62件 (前月同期: 51件, +11件)
  累計スキャン率: 1.6% (62/3,875通)

■ 架電数
  昨日: 8件 (A:5, B:2, C:1, D:0)
  週間合計: 48件 (前週: 42件, +6件)
  月間合計: 178件 (前月同期: 155件, +23件)

■ 訪問・面談
  昨日: 3件対応 (訪問:2, 面談:1, 成約:0)
  週間合計: 12件対応 (成約:1, 前週: 0件, +1件)
  月間合計: 38件対応 (成約:2)
  成約率: 5.3%

■ 企業ランク分布
  A: 24社 (前日: 23社, +1社)
  B: 18社 / C: 15社 / D: 8社
  合計: 65社

■ スコアセグメント
  90点以上: 12社 (+2社) | 70-89点: 18社 (+2社)
  40-69点: 22社 (-3社) | 15-39点: 10社 | 15点未満: 3社 (-1社)

■ 流入ルート別成約
  ①紹介: 2成約 (成約率: 28.6%)
  ②手紙DM: 0成約 (成約率: 0%)
  ③ミカタ経由: 0成約 (成約率: 0%)
  ④開拓架電: 0成約 (成約率: 0%)
━━━━━━━━━━━━━━━━━━━━━━━━━━

注: 架電実績は BlueBean 自動連携による
週間比較 = 過去7日 vs その前7日
月間比較 = 当月1日〜今日 vs 前月同期
```

---

## 3. 技術実装

### 3.1 Google Apps Script トリガー

```javascript
// グローバルトリガーの登録(手動1回のみ実行)
function createDailyReportTrigger() {
  // 毎日10:00 JST に実行
  ScriptApp.newTrigger('sendDailyReport')
    .timeBased()
    .atHour(10)
    .nearMinute(0)
    .everyDays(1)
    .create();
}

// メイン処理
function sendDailyReport() {
  try {
    const reportData = compileDailyReport();
    const emailBody = formatReportEmail(reportData);
    
    GmailApp.sendEmail(
      'takeshi.koyanagi9@gmail.com',
      `【GLOW日次レポート】${reportData.reportDate}`,
      emailBody,
      { htmlBody: emailBody }
    );
    
    // スプレッドシート「日次レポート」タブにも記載
    writeReportToSheet(reportData);
    
    Logger.log('✓ 日次レポート配信完了: ' + reportData.reportDate);
  } catch (e) {
    Logger.log('✗ エラー: ' + e.toString());
    GmailApp.sendEmail(
      'takeshi.koyanagi9@gmail.com',
      '【GLOW日次レポート】エラーが発生しました',
      e.toString()
    );
  }
}
```

### 3.2 データ集計関数

```javascript
function compileDailyReport() {
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const masterSheet = ss.getSheetByName(GlowSchema.COMPANY_MASTER_SHEET_NAME);
  const interactionSheet = ss.getSheetByName("活動記録");
  
  const masterRecords = readMasterRecords(masterSheet);
  const interactions = readInteractionRecords(interactionSheet);
  
  return {
    reportDate: yesterday.toLocaleDateString("ja-JP"),
    letters: {
      yesterday: countLettersByDate(masterRecords, yesterday),
      weekly: countLettersByDateRange(masterRecords, getWeekStartDate(yesterday), yesterday),
      monthly: countLettersByMonth(masterRecords, yesterday.getFullYear(), yesterday.getMonth() + 1),
    },
    qrScans: {
      // LINE連携で取得
      yesterday: getLineNewUsersYesterday(),
      weekly: getLineNewUsersWeekly(),
      monthly: getLineNewUsersMonthly(),
    },
    calls: {
      yesterday: countCallsByDate(interactions, yesterday),
      // ... 週間・月間も同様
    },
    // ... その他のデータ
  };
}
```

### 3.3 メール送信フォーマット

```javascript
function formatReportEmail(reportData) {
  const html = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; }
    .header { background-color: #00335C; color: white; padding: 20px; }
    .section { margin: 20px 0; padding: 15px; border-left: 4px solid #F88800; }
    .metric { display: inline-block; width: 48%; margin: 5px 1%; }
    .number { font-size: 24px; font-weight: bold; color: #00335C; }
    .label { color: #999; font-size: 12px; }
    .compare { color: #F88800; font-weight: bold; }
  </style>
</head>
<body>
  <div class="header">
    <h1>【GLOW日次レポート】${reportData.reportDate}</h1>
    <p>配信時刻: ${new Date().toLocaleString("ja-JP")}</p>
  </div>
  
  <div class="section">
    <h2>■ 手紙発送</h2>
    <div class="metric">
      <div class="label">昨日</div>
      <div class="number">${reportData.letters.yesterday}</div>
      <div class="label">通</div>
    </div>
    <div class="metric">
      <div class="label">週間合計</div>
      <div class="number">${reportData.letters.weekly}</div>
      <div class="label">通 <span class="compare">(前週: ${reportData.letters.weeklyPrev})</span></div>
    </div>
  </div>
  
  <!-- 以下、同様に各セクション -->
  
  <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
  <p style="color: #999; font-size: 12px;">
    このレポートは自動生成されました。
    <br>架電実績は BlueBean CTI システムから自動取得しています。
  </p>
</body>
</html>
  `;
  return html;
}
```

---

## 4. 実装スケジュール

| Task | 期間 | 依存 |
|---|---|---|
| T1: 設計書完成 | 2026-09-22 | - |
| T2: 集計ロジック実装 | 2026-09-23 〜 25 | T1 |
| T3: メール送信 + フォーマット | 2026-09-26 | T2 |
| T4: スプレッドシート記載処理 | 2026-09-27 | T2 |
| T5: トリガー設定 + テスト配信 | 2026-09-28 | T3, T4 |
| T6: 本番運用開始 | 2026-09-29 10:00 | T5 |

---

## 5. テスト・検証計画

### 5.1 ユニットテスト
- 日付計算(yesterday, weekly, monthly)
- 集計ロジック(各メトリクス)
- 前週比・前月比の正確性

### 5.2 統合テスト
- メール送信動作確認
- スプレッドシート記載確認
- トリガーの自動実行確認

### 5.3 本番前テスト
- 2026-09-28朝に手動実行 → メール受信確認
- 複数回実行での重複チェック
- 日付境界(月末・月初)の確認

---

## 6. 注意事項

- **LINE API連携**: 新規ユーザーカウントの取得方法を確認
- **BlueBean ログ**: CTI システムが完全に稼働してからデータ集計開始
- **スプレッドシート容量**: 日次データが積み重なるため、定期的なアーカイブを検討
- **タイムゾーン**: JST(UTC+9) で統一

