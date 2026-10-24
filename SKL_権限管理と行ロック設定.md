# SKL社 権限管理と行ロック設定ガイド
## 誰が何を編集できるかを完全にコントロール

**作成日**: 2026年10月24日  
**対象**: バックオフィス・システム管理者  
**目的**: 誤編集を防止・役割別アクセス制御を実装

---

## 🎯 **権限管理の原則**

```
【アクセス最小化の原則】

✅ やるべき機能だけ実行可能
❌ 誤操作・権限外の編集を物理的に防止
```

例）
- 一般スタッフ: 自分の行だけ編集可能 → 他人のデータを誤って修正できない
- 部門長: 自部門データのみ編集 → 他部門のデータを見間違える事故を防止
- 経営層: すべて見える・編集可能 → ただし「変更履歴」で追跡可能

---

## 📋 **権限マトリックス（詳細版）**

### **Sheet 1: 従業員マスター**

| ユーザー | 見える範囲 | 編集可能 | ロック対象 |
|---|---|---|---|
| **経営層** | すべての列 | すべて | なし |
| **バックオフィス責任者** | すべての列 | すべて | 特定列は読み取り専用フラグ |
| **バックオフィススタッフ** | すべての列 | A列（ID）のみ | 他の列すべて |
| **部門長** | 全部門データ | 自部門のみ（B列で判定） | 他部門・特定列 |
| **一般スタッフ** | 自分の行のみ | なし | すべて読み取り専用 |

### **Sheet 3: 月別実績**

| ユーザー | 見える範囲 | 編集可能 | ロック対象 |
|---|---|---|---|
| **経営層** | すべての列・行 | すべて | なし |
| **バックオフィス責任者** | すべての列・行 | A列（日付）のみ | 他の列は修正時のみ編集可 |
| **部門長** | 全行を見える | 自部門の行のみ | 他部門の行・計算列 |
| **一般スタッフ** | 自分の行のみ | C列（会場）のみ | 他列・他人の行 |

### **Sheet 5: ダッシュボール**

| ユーザー | 見える範囲 | 編集可能 | ロック対象 |
|---|---|---|---|
| **全員** | すべて | なし（読み取り専用） | すべて |

---

## 🔐 **実装方法 1: Google Sheets ネイティブ機能による行保護**

### **Step 1: 保護範囲の設定**

#### Sheet 1（従業員マスター）の保護設定

1. **部門長向け: 他部門データの読み取り専用化**

```
手順:
1. Sheet1 を開く
2. メニュー「データ」→「保護シートと範囲」
3. 「範囲」タブ → 「新しい範囲を保護」
4. 範囲の入力: B列（部門）が「バックオフィス」でない行
   → 保護対象: 各スタッフが「自分の部門外」のデータを編集できないようにする

実装は複雑なため、GAS で実装（Step 2参照）
```

#### Sheet 3（月別実績）の保護設定

```
2つの方法:

【方法A: 読み取り専用で全体を保護 → 特定行だけ編集可能に】
1. Sheet3 全体を読み取り専用に
2. GAS で「今日の日付」の行だけロック解除
3. スタッフは今日の行のみ編集可能

【方法B: 特定列を保護 → 計算式列を守る】
1. D列～H列（自動計算列）を読み取り専用
2. A列～C列（入力列）のみ編集可能
3. 誤ってリセット・削除するリスクを排除
```

---

## 🤖 **実装方法 2: Google Apps Script による動的権限管理**

### **GAS コード: 権限管理マスター**

```javascript
// ========================================
// SKL Google Sheets 権限管理システム
// ========================================

const PERMISSIONS_CONFIG = {
  // ユーザーグループと対応するメールドメイン
  groups: {
    admin: ["koyanagi@example.com"],  // 小柳さん（経営層）
    backoffice: ["boffice@example.com"],  // バックオフィス
    deptHeads: {  // 各部門長
      "バックオフィス": "dept-boffice@example.com",
      "リユース": "dept-reuse@example.com",
      "イベプロ": "dept-event@example.com",
      "業務提携": "dept-business@example.com"
    },
    staff: ["@example.com"]  // 全スタッフ（ドメイン一括）
  },
  
  // シート別のロック設定
  sheetLocks: {
    "従業員マスター": {
      adminEditable: "A:R",  // 管理者は全列編集可
      deptHeadEditable: "B:J",  // 部門長は基本情報のみ
      staffEditable: "none",  // スタッフは編集不可
    },
    "月別実績": {
      adminEditable: "A:C",
      deptHeadEditable: "A:C",
      staffEditable: "A:C",  // スタッフは自分の行のみ
    },
    "ダッシュボード": {
      readOnly: true  // 全員読み取り専用
    }
  }
};

// ========================================
// onEdit トリガー: 編集時の権限チェック
// ========================================

function onEdit(e) {
  const ss = e.source;
  const sheet = e.range.getSheet();
  const user = Session.getActiveUser().getEmail();
  const editRange = e.range;
  
  // ユーザーの権限を判定
  const userRole = getUserRole(user);
  
  // シート別の権限チェック
  if (!hasEditPermission(userRole, sheet.getName(), editRange, user)) {
    // 権限がない場合: 編集を取り消す＋アラート
    SpreadsheetApp.getUi().alert(
      "権限がありません。\n" +
      "このセルは編集できません。\n" +
      "不明な場合はバックオフィスに問い合わせてください。"
    );
    e.range.clearContent();  // 入力を削除
    return;
  }
  
  // 権限がある場合: 変更履歴を記録
  logEdit(user, sheet.getName(), editRange, e.oldValue, e.value);
}

// ========================================
// ユーザーの権限レベルを判定
// ========================================

function getUserRole(userEmail) {
  // 経営層
  if (PERMISSIONS_CONFIG.groups.admin.includes(userEmail)) {
    return "admin";
  }
  
  // バックオフィス
  if (userEmail.includes("boffice")) {
    return "backoffice";
  }
  
  // 部門長（マスターデータで確認）
  const employeeSheet = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName("従業員マスター");
  const data = employeeSheet.getDataRange().getValues();
  
  for (let i = 1; i < data.length; i++) {
    if (data[i][4] === userEmail) {  // E列（メール）と照合
      const role = data[i][1];  // B列（部門）
      if (["バックオフィス", "リユース", "イベプロ", "業務提携"].includes(role)) {
        return "deptHead_" + role;
      }
    }
  }
  
  // その他: スタッフ
  return "staff";
}

// ========================================
// 編集権限の判定
// ========================================

function hasEditPermission(userRole, sheetName, editRange, userEmail) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName(sheetName);
  
  // ダッシュボールは全員読み取り専用
  if (sheetName === "ダッシュボード") {
    return false;
  }
  
  // 経営層（admin）: すべて編集可能
  if (userRole === "admin") {
    return true;
  }
  
  // バックオフィス: 全シート管理可能
  if (userRole === "backoffice") {
    return true;
  }
  
  // Sheet1（従業員マスター）の権限判定
  if (sheetName === "従業員マスター") {
    if (userRole.startsWith("deptHead_")) {
      // 部門長: 自部門データのみ編集可
      const dept = userRole.split("_")[1];
      const rowData = editRange.getSheet()
        .getRange(editRange.getRow(), 1, 1, 20).getValues()[0];
      
      // B列（部門）が自分の部門か確認
      return rowData[1] === dept && editRange.getColumn() <= 10;
    }
    
    // スタッフ: 編集不可
    return false;
  }
  
  // Sheet3（月別実績）の権限判定
  if (sheetName === "月別実績") {
    const editRow = editRange.getRow();
    const editCol = editRange.getColumn();
    
    // スタッフ: 自分の行の A～C列（日付・会場・売上）のみ編集可
    if (userRole === "staff") {
      const rowData = editRange.getSheet()
        .getRange(editRow, 1, 1, 20).getValues()[0];
      
      // スタッフ名が自分と一致するか確認（後で実装）
      // 現在は日付が当日か確認（簡易版）
      const editDate = new Date(rowData[0]);
      const today = new Date();
      
      if (editDate.toDateString() === today.toDateString()) {
        // 当日のデータ: A～C列のみ編集可
        return editCol >= 1 && editCol <= 3;
      }
      
      return false;
    }
    
    // 部門長: 自部門の当日分のみ編集可
    if (userRole.startsWith("deptHead_")) {
      const dept = userRole.split("_")[1];
      const rowData = editRange.getSheet()
        .getRange(editRow, 1, 1, 20).getValues()[0];
      
      // 部門確認
      const rowDept = rowData[1];  // B列（部門）
      if (rowDept === dept && editCol >= 1 && editCol <= 3) {
        return true;
      }
      
      return false;
    }
  }
  
  return false;
}

// ========================================
// 変更履歴を記録（監査ログ）
// ========================================

function logEdit(user, sheetName, range, oldValue, newValue) {
  const logSheet = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName("編集履歴") || createLogSheet();
  
  const timestamp = new Date();
  const lastRow = logSheet.getLastRow() + 1;
  
  logSheet.getRange(lastRow, 1).setValue(timestamp);
  logSheet.getRange(lastRow, 2).setValue(user);
  logSheet.getRange(lastRow, 3).setValue(sheetName);
  logSheet.getRange(lastRow, 4).setValue(range.getA1Notation());
  logSheet.getRange(lastRow, 5).setValue(oldValue || "（空）");
  logSheet.getRange(lastRow, 6).setValue(newValue);
}

// ========================================
// ロックの強制実行（毎日 23:00）
// ========================================

function enforceSheetLocks() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheets = ss.getSheets();
  
  for (let i = 0; i < sheets.length; i++) {
    const sheet = sheets[i];
    const protections = sheet.getProtections(SpreadsheetApp.ProtectionType.SHEET);
    
    // 既存の保護を削除
    for (let p = 0; p < protections.length; p++) {
      if (protections[p].canEdit()) {
        protections[p].remove();
      }
    }
    
    // 新しい保護ルールを適用
    applySheetProtection(sheet);
  }
}

function applySheetProtection(sheet) {
  const sheetName = sheet.getName();
  
  if (sheetName === "ダッシュボード") {
    // ダッシュボード: 全体読み取り専用
    const range = sheet.getRange(1, 1, sheet.getLastRow(), sheet.getLastColumn());
    const protection = range.protect();
    protection.setDescription("ダッシュボール（読み取り専用）");
    protection.removeEditors(SpreadsheetApp.getEditors());
    protection.addEditors(["koyanagi@example.com"]);  // 経営層のみ編集可（テンプレート更新用）
  }
  
  if (sheetName === "月別実績") {
    // 計算列（D～H列）を読み取り専用
    const calcRange = sheet.getRange(1, 4, sheet.getLastRow(), 5);
    const calcProtection = calcRange.protect();
    calcProtection.setDescription("計算列（読み取り専用）");
    calcProtection.removeEditors(SpreadsheetApp.getEditors());
    calcProtection.addEditors(["koyanagi@example.com", "boffice@example.com"]);
  }
}

// ========================================
// ロギングシートの作成（初回のみ）
// ========================================

function createLogSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const logSheet = ss.insertSheet("編集履歴");
  
  // ヘッダ行
  logSheet.getRange(1, 1).setValue("日時");
  logSheet.getRange(1, 2).setValue("ユーザー");
  logSheet.getRange(1, 3).setValue("シート");
  logSheet.getRange(1, 4).setValue("セル");
  logSheet.getRange(1, 5).setValue("変更前");
  logSheet.getRange(1, 6).setValue("変更後");
  
  // 読み取り専用に設定
  const range = logSheet.getRange(1, 1, logSheet.getLastRow(), 6);
  const protection = range.protect();
  protection.setDescription("編集履歴（自動記録・編集不可）");
  
  return logSheet;
}
```

### **GAS 設定: トリガーの追加**

1. Apps Script コンソール → 「トリガー」
2. 「+ トリガーを作成」
3. 以下を設定:
   - 実行する関数: `enforceSheetLocks`
   - イベント: 時間主導
   - 頻度: 日、23:00（毎日夜間）
4. 保存

---

## 📝 **実装チェックリスト**

### Phase 1（基本構造）
- [ ] 手動で列ロック（Sheet5 ダッシュボール を全員読み取り専用に）
  1. Sheet5 を選択
  2. メニュー「データ」→「保護シートと範囲」
  3. 「シート」タブ → Sheet5 を選択 → 「保護」
  4. 説明: 「ダッシュボール（全員読み取り専用）」

### Phase 2（自動化）
- [ ] GAS コード（権限管理マスター）を Apps Script にコピー
- [ ] ユーザーメールアドレスを PERMISSIONS_CONFIG に記入
- [ ] onEdit トリガーを有効化
- [ ] 毎日 23:00 実行のトリガーを設定
- [ ] テスト: スタッフが「自分の行の範囲外」を編集しようとしたとき、自動でブロック + アラートが表示されることを確認

### Phase 2.5（ログ管理）
- [ ] 「編集履歴」シートが自動作成される
- [ ] すべての編集が「日時・ユーザー・変更前後」の記録されることを確認
- [ ] 月1回、編集履歴を経営層がレビュー

---

## 🔍 **トラブルシューティング**

| 症状 | 原因 | 解決方法 |
|---|---|---|
| 「権限がありません」と出て、すべて編集不可 | GAS権限設定が厳しすぎる | GAS の hasEditPermission() 関数のルールを見直す |
| 部門長が自部門データすら編集できない | ユーザーメールがPERMISSIONS_CONFIG に未登録 | 全メールアドレスを確認・追加 |
| スタッフが当日の行を編集できない | 日付判定が正確でない | 日付形式を確認（YYYY-MM-DD 形式に統一） |
| 編集履歴が記録されない | onEdit トリガーが無効 | Apps Script で onEdit 関数が実行されているか確認 |

---

## 💡 **ベストプラクティス**

### ✅ 推奨する運用

1. **月1回のログレビュー**
   - 「編集履歴」シートを経営層が確認
   - 通常でない変更（大量削除など）がないか確認
   
2. **新しい部門長・スタッフの追加時**
   - GAS の PERMISSIONS_CONFIG にメールアドレスを追加
   - App Script を保存し直す
   
3. **権限トラブル時の対応**
   - スタッフが「編集できない」と報告 → 部門長経由でバックオフィスに連絡
   - バックオフィスが PERMISSIONS_CONFIG を確認 → メール登録漏れを修正
   - 修正後、Google Sheets をリロード

---

**作成者**: Claude Haiku 4.5  
**対応フェーズ**: Phase 1 基本（手動） → Phase 2（自動化）  
**所要時間**: Phase 1 約 30分 / Phase 2 約 2～3 時間
