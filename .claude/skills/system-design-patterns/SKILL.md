---
name: system-design-patterns
description: "GLOW・enLife・hojo-hq の既存システム（glow-ma 営業管理・KAKEHASHI CTI・ミカタ制度DB・もらいわすれ堂受給管理）から実装パターン・設計原則・反復教訓を抽出。新規機能設計時に『スクラッチからの設計は時間がもったいない』という運用者の違和感を解消し、既存の API 連携・プロセスフロー・データモデル・権限モデルを参照・複用できる設計辞書。新規システムは必ずこれを通す。"
---

# システム設計パターン辞書（hojo-hq 専用版）

実装が先行して「スクラッチから設計し直す」ことを避けるために、
GLOW・enLife グループで検証済みの実装パターンと、失敗から学んだ教訓を一冊の辞書にまとめたもの。
新しいシステムを企画したら、まずここを読む。既存パターンが当てはまれば、半分の時間で実装できる。

---

## 原則 1: 顧客マスタは一度だけ作る（分散すると死ぬ）

### 現状: glow-ma の教訓

❌ **Before（2026 年 6 月まで）:**
```
GLOW 本社が管理する顧客DB
  ├─ Sheet 1: 「紹介企業（嶺井さんの紹介）」
  ├─ Sheet 2: 「ミカタ LINE 登録者」
  ├─ Sheet 3: 「家計の見直しやさん顧客」
  └─ Sheet 4: 「前職での個別管理ファイル」（未統合）

結果: 同じ企業が 3-4 回出現する重複・企業 ID が 統一されない・接触履歴が分散

例: 
  「GLOW/2026-0015」（ミカタから登録）
  「kakei/1450」（家計から登録）
  「review/3827」（嶺井さんのメモ）
  → 全部「〇〇建設」だが、誰も気づかない
  → 営業は「初対面」で何度も訪問、顧客は不信感
```

✅ **After（2026 年 8 月から、glow-ma 統合）:**
```
単一の顧客マスタ（Google Sheets + Apps Script）
  ├─ 企業 ID: 自動採番（glow-20260815-0001 形式）
  ├─ 企業基本情報: 商号・業種・所在地・代表者名・従業員数
  ├─ 流入ルート: 「①紹介 / ②ミカタ / ③家計 / ④その他」（複数可）
  ├─ 接触履歴: すべての営業マン/LINE/note が同じレコードに記録
  ├─ 営業ステータス: 「初期接触 / 提案中 / 成約 / 失注」
  └─ 複数ステークホルダーの権限設定:
      • 嶺井さん: 「紹介企業」フルアクセス
      • ミカタチーム: 「ミカタ登録企業」の LINE 登録日・メール配信状態のみ参照
      • 家計チーム: 「家計顧客」フルアクセス（GLOW との接触履歴は見えない）

結果:
  • 同一企業の 2 重登録が 0 に
  • ミカタから「意外と営業実績がある企業」が発見できるようになった
  • 営業マンの移動・人事異動時に顧客引き継ぎが簡潔に
```

### 設計原則

```
① 企業マスタは「入力口」が単一
  複数チーム / 複数キャンペーン からの登録は、全て同じマスタへ
  ただし「流入ルート」フィールドで来源を記録

② ID は自動採番・変更不可
  手動入力 = 重複・表ゆれの温床
  フォーマット: [ブランド短縮形]_[企業種別]_[採番番号]
  例: glow_company_000215 / kakei_household_001834

③ 権限は「データに対する操作範囲」で切る
  • ミカタ営業: 「ミカタ登録日」「LINE 登録状態」のみ参照・更新可能
  • GLOW 営業: 「接触履歴」「提案内容」のみ参照・更新可能
  • 統括（小柳さん）: 全データ参照・監査
  → 全体を見える一方で、各チームはスコープ内だけ操作

④ 「個社別の個別管理ファイル」は御法度
  スプレッドシートの「個別シート」= 単一マスタからの派生物
  マスタを更新したら、派生物は自動更新される設計にする
  手動コピペ = 同期漏れの温床

⑤ リレーション(紐付け)は「ID 参照」で
  「営業案件」マスタも「LINE 配信履歴」も、企業マスタへの ID 参照のみ
  企業情報を変更しても、配信履歴は歴史として残る
```

### 実装時の注意

```
言語: Google Sheets + Apps Script（Google Workspace に統合済み）
ライセンス料: GLOW / enLife / フクギイロ で既に契約（追加コスト 0）

例: KAKEHASHI に顧客マスタを追加する場合
  1. glow-ma の企業マスタを共有権限で KAKEHASHI テーム へ開放
  2. KAKEHASHI 用の派生シート（「KAKEHASHI_通話ログ」）を作成
  3. Apps Script で「企業 ID → 企業名」の自動ルックアップ
  4. 新しい通話ログが入るたび、企業マスタの「最終接触日」を自動更新
  5. 何も手動コピペしない
```

---

## 原則 2: 権限モデルは「3 段階」で十分

### KAKEHASHI での実装例

```
背景: enLife の営業マンが 12 人、マネージャー 2 人、本社 1 人
     各営業マンの顧客データは「見てはいけない」ことが多い
     (他営業の顧客フォロー防止、個人情報、営業秘密)

❌ NG: 「各営業マン個別にアクセス許可」
  → 12 人分の個別設定、誰が誰に許可したか追跡不可、感情的対立

✅ OK: 階層型権限（3 段階）

  L1 権限: 営業マン本人
    └─ 自分の顧客・自分の通話ログ のみ参照・編集
    └─ 実装: 「ログイン ID = 営業 ID」で自動フィルタリング
    └─ UI: 「あなたの顧客」ビューのみ見える（他のシート名は灰色）
    
  L2 権限: マネージャー
    └─ 担当チーム全体の顧客・通話ログ 参照のみ（編集不可）
    └─ + 部下の営業成績・失注理由・平均通話時間 の分析ダッシュボード
    └─ 実装: 「部下 ID リスト」でフィルタリング
    └─ UI: 「あなたのチーム」「個人別成績」「顧客プール」
    
  L3 権限: 統括（小柳さん）
    └─ 全データ参照・監査
    └─ + システム設定・スタッフ追加・権限変更
    └─ 実装: 権限チェック なし（Admin フラグ）
    └─ UI: すべてのシート・機能が見える
```

### 実装の盲点（よくやる失敗）

```
❌ 「共有フォルダ」で権限管理
  会社: Google Drive で「営業チーム」フォルダを共有
  現実: 営業 A が自分の顧客ファイルをフォルダにコピペ
       → フォルダ内で「A さん顧客.xlsx」が増殖
       → 誰が最新版かわからない
       → 権限も「フォルダ共有」のみで個別制御不可

✅ 「スプレッドシート」で権限管理（Apps Script で補強）
  単一マスタ内で「行のアクセス制限」を設定
  例:
    | 企業 ID | 企業名 | 営業担当 | 通話ログ | 失注理由 |
    | glow-001 | AA 建設 | 営業 A | ✓ 見える | ✓ 見える（本人のみ）|
    | glow-002 | BB 工業 | 営業 B | ✗ 見えない | ✗ 見えない（他営業） |
  
  実装:
    function onOpen() {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      const sheet = ss.getSheetByName("CustomerLog");
      
      // ログイン中のユーザーを取得
      const user = Session.getActiveUser().getEmail();
      
      // 範囲を保護し、このユーザー以外に制限
      const protection = sheet.protect();
      protection.removeEditors([...]);
      protection.addEditor(user);
    }

❌ 「削除」を許可
  営業 A が誤ってログを削除
  → 復旧に 2 日、その間にマネージャーが進捗を見落とし失注

✅ 「削除禁止」+ 「行の非表示」で統制
  GAS で「削除機能」を実装しない
  代わり: データ → 「ステータス」が「削除」に変わるだけ
  復旧: 管理者が「削除」ステータスを「有効」に戻す（歴史が残る）
```

---

## 原則 3: プロセスフローは「Zapier / Power Automate」で自動化（手作業を減らす）

### ミカタ の実装例: 「LINE 登録 → 制度提案」フロー

```
❌ Before（運用者の人力）:
  1. LINE で「プロフィール入力」フォーム送信
  2. 営業が回答を Google Sheet に手動入力
  3. 営業が制度適合フィルタ実行（CSV ダウンロード）
  4. メール/LINE で提案送付
  5. 配信ログを Google Sheet に手動入力
  
  時間: 1 社あたり 3-5 分 × 月 50 社 = 2.5-4 時間/月

✅ After（Zapier 自動化）:
  1. LINE 登録者が「プロフィール入力」フォーム送信
  2. Zapier トリガー: Form 完了 → JSON で glow-ma へ送信
  3. Apps Script: 業種・売上・地域 から制度を自動抽出
  4. Zapier アクション: 提案メール自動送信 + SMS 通知
  5. 配信ログ自動記録
  
  時間: 1 社あたり 5 秒（自動）× 月 50 社 = 4 分/月
  削減: 2.5 時間/月 → 運用者が他の施策に時間を使える

実装図:
  LINE 登録者
    ↓
  [プロフィール入力フォーム（LINE）]
    ↓ Zapier トリガー
  [glow-ma 企業マスタ]
    ↓ Apps Script
  [制度マッチング API]
    ↓ Zapier アクション
  [メール送信 + SMS 通知 + ログ記録]
    ↓
  [完了イベント記録（GA）]
```

### 実装の落とし穴

```
❌ 「Zapier で全て済ませる」
  15 ステップ以上の Zapier flow は、保守が難しくなる
  複雑な条件分岐は Zapier では判定しきれない

✅ 「Zapier は『トリガー→データ入力→通知』の 3 役に限定」
  複雑な処理は Apps Script で実装
  
  例:
    Zapier: LINE 登録 → glow-ma に送信（トリガー + 入力）
    Apps Script: 業種から制度 3 つを選抜する（複雑な処理）
    Zapier: メール送信 + ログ記録（通知 + 記録）

❌ 「Zapier で履歴を取っていない」
  配信ログが Zapier のタスク履歴に残るだけ
  → 検査・監査の時に「本当に送ったのか」が不明

✅ 「すべてのトランザクションを Sheet に記録」
  Zapier で「Google Sheet に追記」を最後のステップにする
  
  Sheet:
    | 企業 ID | 送信日時 | 送信内容 | 送信先 | 成功/失敗 | Zapier タスク ID |
    | glow-001 | 2026-10-01 09:45 | 制度提案 A,B,C | LINE | 成功 | task-6284 |
```

---

## 原則 4: API 連携は「認証情報」を安全に管理（誤公開・流出防止）

### glow-ma での教訓

```
背景: glow-ma は GitHub の公開リポジトリ（法務・営業情報は非公開へ分離）
     Web App には複数ベンダーの API キーが必要:
       • Claude API
       • Gemini API
       • Google Sheets API
       • Zoom Phone API

❌ Before（危険な状態）:
  Apps Script で:
    const CLAUDE_KEY = "sk-proj-abc123...";  ← コード内にハードコード
    const ZOOM_KEY = "eyJ0eXAi...";
  
  結果:
    • GitHub で公開コード → 誰でも API キーを見つけられる
    • Key rotation の度にコード変更 & デプロイ（運用負荷）

✅ After（安全な実装）:
  方法 1: Apps Script のプロジェクト設定に環境変数を保存
    Apps Script エディタ → 「プロジェクト設定」
    → 「スクリプト プロパティ」に登録:
      CLAUDE_API_KEY: sk-proj-abc123...
      ZOOM_API_KEY: eyJ0eXAi...
    
    コード内:
      const CLAUDE_KEY = PropertiesService.getScriptProperties()
        .getProperty('CLAUDE_API_KEY');
    
    利点: 
      • コードに平文なし（GitHub に載せても安全）
      • Key rotation は設定から、デプロイ不要
      • 監査ログに誰が変更したか記録

  方法 2: Google Secret Manager（大規模な場合）
    Google Cloud Platform の Secret Manager を使用
    Apps Script から API で取得
    
    利点:
      • キーの有効期限を自動管理
      • アクセス監査ログが完全に残る
      • キーの暗号化・スナップショット機能
    
    コスト: 月 $0.06 / secret（ほぼ無料）

  実装:
    function getAPIKey(keyName) {
      const projectId = "my-project-id";
      const response = UrlFetchApp.fetch(
        `https://secretmanager.googleapis.com/v1/projects/${projectId}/secrets/${keyName}/versions/latest:access`,
        {
          method: 'get',
          headers: {
            'Authorization': `Bearer ${ScriptApp.getOAuthToken()}`
          }
        }
      );
      return JSON.parse(response).payload.data;
    }
```

### 実装チェックリスト（GitHub push 前）

```
□ コード内にハードコード された API キー・パスワード がないか
  bash: grep -r "sk-proj-\|Bearer \|password=" . --include="*.gs" --include="*.py"
  
□ .env ファイルは .gitignore に入っているか
  
□ 本番環境の Key が開発環境のテストコードに混じっていないか
  
□ API キーの rotation スケジュール は決まっているか（例: 3 ヶ月ごと）
  
□ 誤公開時の対応ルール が決まっているか
  └─ 発見したら即座に Key を無効化、新規キーを再発行
```

---

## 原則 5: データモデル設計（正規化と実運用のバランス）

### KAKEHASHI 通話ログの例

```
❌ Over-normalized（理論的には正しいが、運用が重い）:
  Table 企業
    | 企業ID | 企業名 | 業種 | 従業員数 |
  
  Table 営業
    | 営業ID | 営業名 | 所属 | 成績 |
  
  Table 通話
    | 通話ID | 企業ID | 営業ID | 通話日時 | 通話時間 | 成約有無 |
  
  Table 通話内容
    | 通話ID | 議論トピック | 顧客の懸念 | 営業の提案 |
  
  問題: 
    • 営業ダッシュボード作成に「3 つのテーブル JOIN」が必要
    • 1 つのレコード追加に複数テーブルへの INSERT が必要
    • Apps Script で実装する際に複雑度が爆上がり

✅ Balanced（実運用重視）:
  Sheet 1: 企業マスタ
    | 企業ID | 企業名 | 業種 | 従業員数 | 最終接触営業ID | 最終接触日 |
  
  Sheet 2: 営業マスタ
    | 営業ID | 営業名 | 所属 | 月間成績 |
  
  Sheet 3: 通話ログ（全データを 1 行に）
    | 通話ID | 企業ID | 営業ID | 通話日時 | 通話時間 | 顧客の懸念 | 営業の提案 | 成約有無 | 成約金額 | フォローアップ予定日 |
  
  利点:
    • ダッシュボードは「通話ログ Sheet」だけ読めば完成
    • 新規通話追加は「1 行追記」で完了
    • Apps Script のクエリが単純（QUERY / FILTER 関数のみ）
    • マネージャーが Excel で分析するのも簡単
  
  注意:
    • データの「一部修正」に注意（例: 企業名が変わった）
    → 通話ログの企業名は「変えない」（歴史として残す）
    → 企業マスタだけ更新、通話ログはそのまま
```

---

## 実装パターン: 標準 Apps Script テンプレート

### Web App の標準構成

```javascript
// ---- 0. 権限チェック ----
function doGet(e) {
  const user = Session.getActiveUser().getEmail();
  
  // L3 管理者チェック
  if (!isAdmin(user)) {
    return HtmlService.createHtmlOutput("アクセス権がありません");
  }
  
  return HtmlService.createTemplateFromFile('index')
    .evaluate()
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWSAME);
}

// ---- 1. マスタデータ取得（権限フィルタ付き） ----
function getCustomers(userEmail) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName("CustomerLog");
  
  const data = sheet.getDataRange().getValues();
  
  // ユーザー権限に応じてフィルタ
  if (isAdmin(userEmail)) {
    return data; // 全データ
  } else if (isManager(userEmail)) {
    return data.filter(row => isTeamMember(row[2], userEmail)); // チーム内
  } else {
    return data.filter(row => row[2] === userEmail); // 本人のみ
  }
}

// ---- 2. トランザクション記録 ----
function logTransaction(action, details) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet()
    .getSheetByName("AuditLog");
  
  sheet.appendRow([
    new Date(),  // タイムスタンプ
    Session.getActiveUser().getEmail(),  // 実行者
    action,  // 操作（新規作成 / 更新 / 削除）
    JSON.stringify(details),  // 詳細（変更前後）
    JSON.stringify({
      ipAddress: /* IP は取得不可（Google Apps Script の制限） */,
      userAgent: "Apps Script"
    })
  ]);
}

// ---- 3. エラーハンドリング ----
function executeWithErrorHandling(callback) {
  try {
    return callback();
  } catch (e) {
    logTransaction("ERROR", {
      message: e.message,
      stack: e.stack
    });
    throw new Error("操作に失敗しました。管理者に連絡してください");
  }
}

// ---- 4. API 呼び出し（認証情報は環境変数から） ----
function callClaudeAPI(prompt) {
  const apiKey = PropertiesService.getScriptProperties()
    .getProperty('CLAUDE_API_KEY');
  
  const payload = {
    model: "claude-opus-4-turbo-2025-04-09",
    max_tokens: 1024,
    messages: [{ role: "user", content: prompt }]
  };
  
  const options = {
    method: 'post',
    contentType: 'application/json',
    headers: { 'Authorization': `Bearer ${apiKey}` },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  const response = UrlFetchApp.fetch(
    "https://api.anthropic.com/v1/messages",
    options
  );
  
  if (response.getResponseCode() !== 200) {
    logTransaction("API_ERROR", {
      statusCode: response.getResponseCode(),
      response: response.getContentText()
    });
    throw new Error("API 呼び出しに失敗しました");
  }
  
  return JSON.parse(response.getContentText());
}
```

---

## 実装パターン: 新規システム導入チェックリスト

```
新しいシステム（API / 自動化 / DB）を設計する前に、
必ず以下を確認してから「スクラッチ設計」するか「既存パターン流用」するか決める：

□ 顧客マスタ
  ├─ 既存の「企業マスタ」で足りるのか、新規マスタが必要か
  └─ 既存を流用する場合、新しい「フィールド」は何を足すか

□ 権限モデル
  ├─ L1/L2/L3 の 3 段階で収まるか
  └─ 特殊な操作制限（「営業 A と営業 B だけ見える」など）が必要か

□ プロセスフロー
  ├─ Zapier / Power Automate で自動化できる部分はないか
  └─ 手作業が必ず必要な部分は、どこか

□ API 連携
  ├─ 既存の連携（Claude / Gemini / Zoom など）で足りるのか
  └─ 新規 API が必要な場合、認証情報管理はどうするか

□ データモデル
  ├─ 正規化度と運用負荷のバランスが取れているか
  └─ 履歴管理（誰が何を変えたか）は必要か

□ 監査・ログ
  ├─ すべてのトランザクション（作成 / 更新 / 削除）をログに残すか
  └─ ログの保持期限は決まっているか（コスト面も考慮）

□ 外部公開・個人情報
  ├─ このデータは個人情報を含むか（mamori.md 要確認）
  └─ 含む場合、マスク・匿名化・アクセス制限はどうするか
```

---

## 関連スキル

- `user-research-hojo` — ユーザーの権限要件・プロセスフローを決める
- `transcription-analysis-hojo` — 自動化の実装例（Zapier / Apps Script）
- `shiryo-sakusei` — 実装例の出典確認
