# SKL社 Google Sheets 実装ガイド
**実装日**: 2026年10月24日  
**対象**: 将来スケーラブル版（34名→100名対応）

---

## 📋 **Phase 1: 基本構造構築（Week 1-2 / 約8-10時間）**

### Step 1: Google Sheets の新規作成
1. Google Drive で **新しいスプレッドシート**を作成
2. 名称: `SKL社_統合管理システム_2026`
3. シートを以下の7つにリネーム:
   - Sheet1 → `従業員マスター`
   - Sheet2 → `催事会場マスター`
   - Sheet3 → `月別実績`
   - Sheet4 → `部門KPI`
   - Sheet5 → `ダッシュボード`
   - Sheet6 → `設定・ルール`
   - Sheet7 → `API連携層`

### Step 2: 従業員マスター（Sheet 1）の構築
**カラム構成（A列～R列）:**

```
A: 従業員ID        (例: A001, A002...)  ← 【重要】自動採番スクリプト使用
B: 部門           (バックオフィス / リユース / イベプロ / 業務提携)
C: チーム         (将来用: 部門内チーム分類)
D: 氏名           (テキスト)
E: ふりがな       (テキスト)
F: 雇用形態       (正社員 / 契約社員 / パート・アルバイト / 業務委託)
G: 性別           (男性 / 女性 / その他)
H: 主スキル       (営業 / イベント企画 / 接客 / 事務 / 管理 / その他)
I: 副スキル       (将来用)
J: 勤務可能エリア (複数選択: エリアA / エリアB / エリアC...)
K: 時給（予定）   (数値 / 将来: 給与体系導入時)
L: 基本給（予定） (数値 / 将来: 社員昇格時)
M: インセンティブ率 (% / 将来: 歩合体系導入時)
N: 契約開始日     (日付)
O: ステータス     (稼働 / 休止 / 退職)
P: 連絡先        (将来用)
Q: 評価スコア    (自動計算式)
R: 備考          (テキスト)
```

**実装方法:**
1. A列にヘッダを入力 → A1セルに「従業員ID」
2. A2以下に `A001, A002, A003...` を入力（または自動採番スクリプト使用）
3. 既存の `SKL従業員データ.csv` から氏名・部門・雇用形態などを転記
4. B～J列に該当データを入力

### Step 3: 催事会場マスター（Sheet 2）の構築
**カラム構成（A列～Q列）:**

```
A: 会場ID         (例: V001, V002...)  ← 【重要】自動採番
B: 部門           (保険 / キャリア / リユース)
C: 会場グループ   (大分類)
D: 会場名         (テキスト)
E: 開催場所       (住所)
F: 天候対応       (屋内 / 屋外 / どちらでも)
G: 緯度（予定）   (数値 / 地図表示時)
H: 経度（予定）   (数値 / 地図表示時)
I: 施設規模       (小 / 中 / 大)
J: 安全性評価     (1～5の数値)
K: 過去6ヶ月催事数 (自動計算: COUNTIF)
L: 累計売上       (自動計算: SUMIF)
M: 平均売上       (自動計算: L/K)
N: 単価トレンド   (自動計算 / 将来: 予測式)
O: 最後の催事日   (日付)
P: ステータス     (稼働 / 試験 / 停止)
Q: 備考          (テキスト)
```

**実装方法:**
1. 既存の `SKL催事会場データ.csv` から転記（108会場）
2. A列に `V001～V108` を自動採番
3. K～M列には後述の計算式を実装

### Step 4: 月別実績（Sheet 3）の構築
**カラム構成:**

```
行: 月（2026年1月～）
列:
  A: 月 (例: 2026/01)
  B: 従業員数（稼働）
  C: 総催事数
  D: 総売上
  E: 部門別売上（バックオフィス）
  F: 部門別売上（リユース）
  G: 部門別売上（イベプロ）
  H: 部門別売上（業務提携）
  I: 月別KPI達成率（%）
  J: 注記（天候影響など）
```

**初期データ:**
- 2024年1月～現在までの過去データを入力（月別トレンド分析用）
- データソース: 既存の営業記録・実績レポート

### Step 5: 部門KPI（Sheet 4）の構築
**行構成:**

```
行1: ヘッダ
行2-5: 部門別（バックオフィス / リユース / イベプロ / 業務提携）
行6: 全社合計
```

**カラム構成:**

```
A: 部門
B: 現在の人数（社員＋契約）
C: 直近月の催事数
D: 直近月の売上
E: 前月比（%）
F: 今期累計売上
G: 昨年同期比（%）
H: 平均個人売上（売上/人数）
I: 目標値（月間KPI）
J: 達成率（D/I * 100）
K: ステータス（🟢達成 / 🟡進行中 / 🔴未達）
```

**計算式例:**
- B列: `=COUNTIF(従業員マスター!B:B, A2)`
- J列: `=IF(I2=0, 0, D2/I2*100)`

### Step 6: ダッシュボード（Sheet 5）の構築
**セクション構成:**

#### 6a. 月別サマリー（A1:D10）
```
B1: 【当月サマリー】
B2: 当月（2026年10月）
B3: 稼働人数: =COUNTIF(従業員マスター!O:O,"稼働")
B4: 総催事数: =COUNTIF(月別実績!C:C, ">"&0)
B5: 総売上: =SUM(月別実績!D:D)
B6: 前月比: =(B5 - 前月売上) / 前月売上 * 100
```

#### 6b. 部門別パフォーマンス（A12:E25）
- 横棒グラフ: 部門別催事数・売上ランキング（CHART関数）
- 参照先: Sheet4（部門KPI）

#### 6c. 会場ランキング Top 20（A27:C50）
```
カラム: 会場名 / 過去6ヶ月催事数 / 累計売上
ソート: 売上金額降順
実装: Sheet2のL列データを並べ替え表示
```

#### 6d. トレンド分析（A52:H70）
- 折れ線グラフ: 過去12ヶ月の売上推移
- 参照先: Sheet3（月別実績）

#### 6e. 個人KPI進捗（A72:F100）
```
行: 従業員（稼働者のみ）
列: 氏名 / 部門 / 直近月売上 / 目標値 / 達成率 / ステータス
計算式: 達成率 = 売上 / 目標 * 100
色分け: 緑(100%以上) / 黄(70-99%) / 赤(70%未満)
```

#### 6f. アラート・注記（A102:B120）
```
緊急度: 【高】
内容: 〇〇会場で3ヶ月催事なし
内容: △△部門の個人売上が目標-30%
内容: □□さんが1ヶ月間記録なし
```

### Step 7: 設定・ルール（Sheet 6）の構築

| 設定項目 | 現在値 | 説明 |
|---|---|---|
| **基準日** | 2026/10/24 | 計算基準となる日付 |
| **会計年度** | 1月～12月 | KPI計測期間 |
| **部門定義** | 4部門 | 将来: 部門数拡張時の更新先 |
| **スキル定義** | 10種類 | 従業員スキルの選択肢 |
| **エリア定義** | 3エリア | 勤務可能エリアの選択肢 |
| **月間KPI目標** | 150万円 | 全社月間売上目標 |
| **部門別KPI** | 設定表 | 下表を参照 |
| **緊急アラート閾値** | 3ヶ月 | 催事記録なし → アラート発動 |

**部門別KPI設定表:**

| 部門 | 月間売上目標 | 催事数目標 | 個人売上目標 |
|---|---|---|---|
| バックオフィス | 20万 | 4 | 5万 |
| リユース | 30万 | 6 | 5万 |
| イベプロ | 60万 | 12 | 5万 |
| 業務提携 | 40万 | 8 | 5万 |

### Step 8: API連携層（Sheet 7）の構築（準備段階）

```
A: 連携システム
B: エンドポイント（将来）
C: 必須パラメータ
D: 実装予定日
E: 説明

例:
給与管理システム / /api/payroll/import / 従業員ID、売上 / 2027年1月 / 月間売上から給与計算
勤務スケジューリング / /api/schedule/suggest / 従業員スキル、エリア / 2027年3月 / 最適人員配置提案
```

---

## 🎨 **カラー・フォーマット設定**

### ブランドカラー適用
- **海軍紺（主色）**: #0D3B66
- **オレンジ（副色）**: #EF8844
- **成功（緑）**: #2ECC40
- **警告（赤）**: #FF4136
- **中立（グレー）**: #B0BEC5

### 実装場所
1. **ダッシュボード(Sheet5)**
   - ヘッダ背景: 海軍紺 × 白文字
   - サマリーボックス背景: オレンジ（薄い）
   - グラフの色: 海軍紺・オレンジ・緑・赤を組み合わせ

2. **KPI達成状況**
   - 100%以上: 🟢 #2ECC40
   - 70～99%: 🟡 #FFD700
   - 70%未満: 🔴 #FF4136

3. **データ行の背景**
   - ヘッダ行: 濃紺（#0D3B66）
   - 奇数行: 白
   - 偶数行: 薄いグレー（#F5F5F5）

### 条件付き書式設定
**Sheet 4 (部門KPI) の J列（達成率）:**
```
ルール1: 値 >= 100 → 背景色 #2ECC40（緑）
ルール2: 70 <= 値 < 100 → 背景色 #FFD700（黄）
ルール3: 値 < 70 → 背景色 #FF4136（赤）
```

**Sheet 5 (ダッシュボード) の K列（ステータス）:**
```
ルール1: "達成" → 背景色 #2ECC40 + 白文字
ルール2: "進行中" → 背景色 #FFD700 + 黒文字
ルール3: "未達" → 背景色 #FF4136 + 白文字
```

---

## 🤖 **Google Apps Script (GAS) - 初期実装テンプレート**

### GAS設定手順
1. Google Sheets メニュー: **拡張機能** → **Apps Script**
2. `Code.gs` を以下のテンプレートに置き換え
3. プロジェクト名: `SKL_GoogleSheets_Automation`

### Code.gs テンプレート

```javascript
// ===== 自動実行トリガー =====
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('SKL管理')
    .addItem('◀ 従業員IDを自動採番', 'autoNumberEmployeeIDs')
    .addItem('◀ 会場IDを自動採番', 'autoNumberVenueIDs')
    .addItem('◀ KPI計算を実行', 'calculateKPIs')
    .addItem('◀ ダッシュボードを更新', 'refreshDashboard')
    .addItem('◀ 月間レポート生成', 'generateMonthlyReport')
    .addSeparator()
    .addItem('⚙ 権限管理の設定', 'setupPermissions')
    .addToUi();
}

// ===== 従業員ID自動採番 =====
function autoNumberEmployeeIDs() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('従業員マスター');
  const lastRow = sheet.getLastRow();
  const range = sheet.getRange('A2:A' + lastRow);
  const values = range.getValues();
  
  for (let i = 0; i < values.length; i++) {
    if (!values[i][0]) {
      values[i][0] = 'A' + String(i + 1).padStart(3, '0');
    }
  }
  range.setValues(values);
  SpreadsheetApp.getUi().alert('従業員IDを採番しました: A001～A' + lastRow);
}

// ===== 会場ID自動採番 =====
function autoNumberVenueIDs() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('催事会場マスター');
  const lastRow = sheet.getLastRow();
  const range = sheet.getRange('A2:A' + lastRow);
  const values = range.getValues();
  
  for (let i = 0; i < values.length; i++) {
    if (!values[i][0]) {
      values[i][0] = 'V' + String(i + 1).padStart(3, '0');
    }
  }
  range.setValues(values);
  SpreadsheetApp.getUi().alert('会場IDを採番しました: V001～V' + lastRow);
}

// ===== KPI自動計算 =====
function calculateKPIs() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const deptKPI = ss.getSheetByName('部門KPI');
  const employeeSheet = ss.getSheetByName('従業員マスター');
  
  // 部門リスト
  const departments = ['バックオフィス', 'リユース', 'イベプロ', '業務提携'];
  
  for (let i = 0; i < departments.length; i++) {
    const row = i + 2;
    const dept = departments[i];
    
    // B列: 現在の人数（稼働中）
    deptKPI.getRange('B' + row).setFormula(
      '=COUNTIFS(従業員マスター!B:B,"' + dept + '",従業員マスター!O:O,"稼働")'
    );
  }
  
  SpreadsheetApp.getUi().alert('KPI計算式を設定しました');
}

// ===== ダッシュボード更新 =====
function refreshDashboard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const dashboard = ss.getSheetByName('ダッシュボード');
  
  // B3: 稼働人数
  dashboard.getRange('B3').setFormula(
    '=COUNTIF(従業員マスター!O:O,"稼働")'
  );
  
  // B4: 総催事数（Sheet3から）
  dashboard.getRange('B4').setFormula(
    '=COUNTA(月別実績!A:A)-1'
  );
  
  // B5: 総売上（Sheet3から）
  dashboard.getRange('B5').setFormula(
    '=SUM(月別実績!D:D)'
  );
  
  SpreadsheetApp.getUi().alert('ダッシュボードを更新しました');
}

// ===== 月間レポート生成 =====
function generateMonthlyReport() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const today = new Date();
  const month = Utilities.formatDate(today, Session.getScriptTimeZone(), 'yyyy/MM');
  
  const email = Session.getActiveUser().getEmail();
  const subject = `SKL社 月間レポート ${month}`;
  const message = `
    月間レポートが生成されました。
    生成日時: ${Utilities.formatDate(today, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss')}
    
    ダッシュボード（Sheet5）をご確認ください。
  `;
  
  GmailApp.sendEmail(email, subject, message);
  SpreadsheetApp.getUi().alert('月間レポートをメール送信しました');
}

// ===== 権限管理（将来実装） =====
function setupPermissions() {
  // 【Phase 2以降実装】
  // 6つのユーザーグループ別アクセス制御
  // - 経営層: 全Sheet編集可
  // - バックオフィス責任者: Sheet1-4編集可
  // - 各部門長: 自部門データのみ編集可
  // - 一般スタッフ: 自行のみ表示・入力可
  
  SpreadsheetApp.getUi().alert('権限管理設定（Phase 2以降の機能）');
}

// ===== 毎日自動実行トリガー（将来実装） =====
function setupDailyTrigger() {
  // 毎日09:00に dailyAlert() を実行
  // 【Phase 2以降実装】
}

function dailyAlert() {
  // 催事記録なし3ヶ月の会場をアラート
  // 部門KPI未達者をアラート
  // 【Phase 2以降実装】
}
```

### GAS をスプレッドシートに設定
1. **Apps Scriptコンソール**で上記コードを貼り付け
2. `Ctrl + S` で保存
3. Google Sheets に戻る → メニュー「SKL管理」が表示

---

## 📅 **Phase 2～4 の展開予定（参考）**

### Phase 2: 自動化・トリガー（Week 3-4 / 6-8時間）
- ✅ 毎日のアラート自動配信（3ヶ月催事なし会場 → アラート）
- ✅ 月末自動レポート生成・メール送信
- ✅ 部門別KPI自動計算の詳細化

### Phase 3: 通知・連携（Month 2 / 10-12時間）
- ✅ LINE通知連携（重要アラートをスタッフに LINE配信）
- ✅ Slack連携（経営層へ日報配信）
- ✅ メール自動配信（個人売上報告書）

### Phase 4: 外部システム統合（Month 3+ / 20時間以上）
- ✅ 給与管理システムへのAPI連携
- ✅ 勤務スケジューリングシステムとの連携
- ✅ Instagram/LINE広告の成果データ自動取込
- ✅ 予実分析レポートの自動化

---

## ⚠️ **実装チェックリスト**

### 初期構築（必須）
- [ ] Sheet 1～7 を作成・リネーム
- [ ] 従業員マスター（Sheet1）に34名分のデータを入力
- [ ] 催事会場マスター（Sheet2）に108会場分のデータを入力
- [ ] ダッシュボール（Sheet5）の 6セクションを構築
- [ ] カラー・条件付き書式を設定
- [ ] GAS テンプレートをApps Scriptに貼り付け

### 動作確認
- [ ] GAS メニュー「SKL管理」が表示される
- [ ] 「◀ 従業員IDを自動採番」で A001～A034 が採番される
- [ ] 「◀ 会場IDを自動採番」で V001～V108 が採番される
- [ ] 「◀ KPI計算を実行」で 部門KPI が自動計算される
- [ ] ダッシュボードに稼働人数・総催事数・総売上が表示される

---

## 📞 **トラブルシューティング**

| 問題 | 原因 | 解決方法 |
|---|---|---|
| GAS メニューが表示されない | Apps Script が未保存 | `Ctrl+S` で保存 → Google Sheets をリロード |
| 自動採番が重複する | 既存データと混在 | 既存データを A001～A034 にリセット |
| 計算式でエラー | シート名が違う | Sheet タブのシート名を確認・修正 |
| 条件付き書式が反映されない | セル範囲の指定漏れ | 各 Sheet で指定範囲を再確認 |

---

**次のステップ**: Phase 1 構築完了後、Phase 2（自動化）へ進みます。
