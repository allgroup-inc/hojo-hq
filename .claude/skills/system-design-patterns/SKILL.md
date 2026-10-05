---
name: system-design-patterns
description: "GLOW・enLife・hojo-hq の既存システム（glow-ma 営業管理・KAKEHASHI CTI・ミカタ制度DB・もらいわすれ堂受給管理）から実装パターン・設計原則・反復教訓を抽出。新規機能設計時に『スクラッチからの設計は時間がもったいない』という運用者の違和感を解消し、既存の API 連携・プロセスフロー・データモデル・権限モデルを参照・複用できる設計辞書。新規システムは必ずこれを通す。"
---

# システム設計パターン辞書（hojo-hq 専用版）

実装が先行って「スクラッチから設計し直す」ことを避けるために、
GLOW・enLife グループで検証済みの実装パターンと、失敗から学んだ教訓を一冊の辞書にまとめたもの。
新しいシステムを企画したら、まずここを読む。既存パターンが当てはまれば、半分の時間で実装できる。

---

## 設計プロセス（3段階フェーズ）

新規システム企画時は必ず以下の順序で設計を進める。各フェーズの終了後に次へ進む。

### Phase 1: アーキテクチャ設計

**目的**: システム全体の構成要素と責務を定義

**1-1 データフロー図を描く**
- 入力（API / ユーザー入力 / 外部システム）
- 処理（Apps Script / Python / 外部サービス）
- 出力（Google Sheets / 通知 / 監査ログ）
- 各要素の責務と境界を明記

**1-2 既存パターン（原則 1～5）から流用可能な部分を特定**
- 顧客マスタ: 既存の企業マスタで足りるか、新規作成が必要か
- 権限モデル: L1/L2/L3 の 3 段階で収まるか
- プロセス: Zapier / Power Automate で自動化できる部分はないか
- データモデル: 正規化度と運用負荷のバランスは取れているか

**1-3 関連ドキュメントを参照**
- `user-research-hojo` — ユーザー権限要件・プロセスフロー決定
- `mamori.md` — 個人情報・法務確認

**合格条件**
- [ ] システム全体を図解（コンポーネント・データフロー含む）
- [ ] 既存パターンの流用判定が明記
- [ ] 新規開発必要部分が特定

---

### Phase 2: コンポーネント設計

**目的**: 各機能単位の設計詳細を決定

**2-1 入力インタフェースを設計**
- 手動入力フォーム か自動取得か
- 入力検証ルール
- エラーハンドリング方法
- 冪等性が必要か（重複実行対応）

**2-2 処理ロジックを実装**
- 言語・フレームワーク選定（Apps Script / Python / Node.js など）
- 複雑な条件分岐は Apps Script ではなく専用言語で実装
- API 呼び出しの認証・エラー処理（原則 4 参照）

**2-3 出力インタフェースを設計**
- Google Sheets への書き込み方法
- ログ・監査記録の形式
- 配信通知の仕様（メール / SMS / LINE）

**合格条件**
- [ ] 各コンポーネントの入出力が定義
- [ ] API キー・認証情報の管理方法が決定
- [ ] トランザクション記録の仕様が明記

---

### Phase 3: データフロー検証

**目的**: 設計が完全かつ実装可能か確認

**3-1 データモデルの妥当性を検証**
- 正規化度（原則 5 参照）が運用に耐えるか
- 履歴管理が必要な項目は何か
- 削除が発生する場合、物理削除ではなく論理削除か

**3-2 権限フローを完全化**
- 全ユーザーロール（L1/L2/L3 + 特例）をリストアップ
- 各ロールが見える・編集できるデータを明記
- 削除は禁止か、論理削除か

**3-3 エラー・例外ケースを洗い出し**
- API が 403 / 404 / 500 を返した場合
- ネットワーク遮断時の再試行ロジック
- 不完全なデータが投入された場合

**3-4 本番前テスト計画を立案**
- `## 本番前テスト` セクションで定義したチェックリストを実行

**合格条件**
- [ ] データモデル・権限フローの図解が完成
- [ ] 例外ケースが全て定義
- [ ] テスト手順とチェックリストが明記

---

## 原則一覧（参照順）

- **原則 1**: 顧客マスタは一度だけ作る（分散すると死ぬ）
- **原則 2**: 権限モデルは「3 段階」で十分
- **原則 3**: プロセスフローは「Zapier / Power Automate」で自動化（手作業を減らす）
- **原則 4**: API 連携は「認証情報」を安全に管理（誤公開・流出防止）
- **原則 5**: データモデル設計（正規化と実運用のバランス）

各原則の詳細は以下を参照。新規システム設計時は必ず全て確認する。

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

## 実装例: マイクロサービスアーキテクチャ（TypeScript）

### 概要

複数の独立したサービスに分割し、API を介して連携。
GLOW 営業管理・ミカタ・家計の見直しやさんをスケーラブルに統合する構成。

### 構成要素

```
┌─────────────────┐
│  LINE ユーザー   │
└────────┬────────┘
         │ プロフィール入力
         ↓
┌─────────────────────────────┐
│ API Gateway                 │
│ (認証・リクエスト振り分け)    │
└────────┬────────┬────────────┘
         │        │
         ↓        ↓
┌──────────────┐  ┌──────────────┐
│ Customer     │  │ Matching     │
│ Service      │  │ Service      │
│ (企業マスタ)  │  │ (制度選抜)    │
└──────┬───────┘  └──────┬───────┘
       │                │
       └────────┬───────┘
                ↓
         ┌──────────────┐
         │ Notification │
         │ Service      │
         │ (配信管理)    │
         └──────────────┘
```

### サンプル実装（50 行）

```typescript
// customer-service.ts — 企業マスタ管理
interface Customer {
  id: string;
  name: string;
  industry: string;
  revenue: number;
  createdAt: Date;
}

class CustomerService {
  async getOrCreateCustomer(data: {
    name: string;
    industry: string;
  }): Promise<Customer> {
    // 企業マスタから検索（重複排除）
    const existing = await this.findByName(data.name);
    if (existing) return existing;

    // なければ新規作成
    const id = `glow-${Date.now()}`;
    const customer = { id, ...data, createdAt: new Date() };
    await this.saveToSheet(customer);
    return customer;
  }

  private async findByName(name: string): Promise<Customer | null> {
    // Google Sheets から検索
    const sheet = await this.getSheet("CustomerMaster");
    return sheet.values.find(row => row.name === name) || null;
  }

  private async saveToSheet(customer: Customer): Promise<void> {
    // トランザクション記録も同時に行う
    const sheet = await this.getSheet("CustomerMaster");
    await sheet.append([
      customer.id, customer.name, customer.industry, 
      customer.revenue, customer.createdAt.toISOString()
    ]);
  }
}

// matching-service.ts — 制度マッチング
class MatchingService {
  async findApplicablePrograms(customer: Customer): Promise<Program[]> {
    // 企業マスタの業種・売上から制度を抽出
    const programDb = await this.getProgramDatabase();
    return programDb.filter(p => 
      p.targetIndustries.includes(customer.industry) &&
      p.minRevenue <= customer.revenue
    );
  }
}

// notification-service.ts — 配信管理
class NotificationService {
  async notifyPrograms(customerId: string, programs: Program[]): Promise<void> {
    const customer = await new CustomerService().getById(customerId);
    
    // Zapier との連携（メール送信トリガー）
    await this.callZapier({
      event: "program_notification",
      customerId,
      programs: programs.map(p => ({ id: p.id, name: p.name }))
    });

    // 配信ログを記録（履歴残存）
    await this.logDelivery({
      customerId,
      programCount: programs.length,
      timestamp: new Date(),
      status: "pending"
    });
  }
}
```

### TypeScript を選ぶ理由

- 型安全: 顧客 ID や金額の取り違いを compile-time に検出
- テスト容易: 各サービスを独立して単体テスト可能
- スケーラビリティ: Apps Script では難しい複雑な条件分岐を実装
- ローカル開発: Node.js で開発・テストしてから Google Cloud Run にデプロイ可能

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

## 検証失敗時（設計レビュー NG パターン）

### 検出ルール

以下のいずれかに該当する設計は、Phase 3 で「要再検討」となり、Issue 自動起票。

#### NG-1: 依存グラフが不完全

```
❌ 問題: 
  Customer Service は「Notification Service を呼ぶ」と書いてあるが、
  Notification Service が何の API を呼ぶかが未定義
  → 実装時に想定外の外部 API 呼び出しが発生

✅ 検証方法:
  各サービスの「入力 → 処理 → 出力」を図化
  出力先のサービスが入力として受け付けるか確認
  例: Customer Service の出力（Customer JSON）が
      Matching Service の入力スキーマと一致するか
```

#### NG-2: スケール非対応設計

```
❌ 問題:
  「月 50 社のデータ処理」を想定したが、
  実装では全行をメモリに読み込む設計
  → 月 5,000 社になったとき、メモリ不足で落ちる

✅ 検証方法:
  想定データ量（現在・1 年後・5 年後）を明記
  大量データ時の処理方法を事前に設計
  例: Google Sheets ではなく BigQuery を検討
  または: バッチ処理化（時間帯を分散）
```

#### NG-3: 権限モデルの穴

```
❌ 問題:
  「営業 L1 は自分の顧客のみ見える」と書いてあるが、
  「監査ログは全営業が見える」と矛盾している
  → 営業 A が営業 B の顧客に対して無断で提案を見て、営業機密漏洩

✅ 検証方法:
  全ユーザーロールに対して、
  「見える / 編集できる / 削除できる」を
  データベースの「各テーブル × 各フィールド」単位で明記
  矛盾があれば一覧表で検出
```

#### NG-4: トランザクション記録の欠落

```
❌ 問題:
  「配信ログは保存する」と書いてあるが、
  「API 呼び出しの失敗はどこに記録するのか」が未定義
  → API 503 エラーで失敗したが、ログが無いため原因究明に 1 日要費

✅ 検証方法:
  すべてのアクション（成功 / 失敗 / 再試行）を
  同じログテーブルに記録するか確認
  失敗時の alert 仕様も記載
```

### Issue 自動起票仕様

設計レビューで NG が検出された場合、以下情報を含む Issue を自動起票。

```
Title: [Design Review NG] <原則番号> — <NG理由>
例: [Design Review NG] NG-1 — 依存グラフ未定義（CustomerService → NotificationService）

Body:
## 設計フェーズ
Phase 2 (コンポーネント設計) / Phase 3 (データフロー検証)

## NG パターン
NG-1: 依存グラフが不完全

## 詳細
Customer Service の出力が Notification Service の入力スキーマと一致しない
- Customer Service 出力: { id, name, industry, revenue, createdAt }
- Notification Service 入力: { customerId, programs[] }
→ 中間変換ロジックが未定義

## 対応
以下のいずれかで対応:
1. 変換ロジックを明記（Services 間のアダプター）
2. API Gateway で正規化
3. サービス設計そのものを見直し

## 期限
Phase 3 の合格条件確認までに解決（推奨: 同日）

Labels: design-review, ng-pattern, <原則名>
```

---

## 本番前テスト（設計から実装への移行）

### テスト前の準備

```
□ 依存グラフ図（Phase 2）が完成しているか
□ データモデル・権限フローの図解（Phase 3）が完成しているか
□ Issue や NG パターンが全て解決しているか
□ チームのサインオフが取れているか
```

### サンプルプロジェクト構造（ローカルテスト用）

```
test-project/
├── .env                           # API キー（.gitignore 必須）
├── package.json
├── src/
│   ├── services/
│   │   ├── customer.service.ts
│   │   ├── matching.service.ts
│   │   └── notification.service.ts
│   ├── models/
│   │   └── types.ts               # Customer, Program の型定義
│   └── index.ts                   # 統合テスト エントリーポイント
└── test/
    ├── customer.test.ts
    ├── matching.test.ts
    └── integration.test.ts
```

### テストチェックリスト

#### アーキテクチャ図作成
```
□ コンポーネント図を PNG で出力
  └─ 各サービスの責務が明確か
  └─ データ流向が一方向か（循環依存がないか）
  
□ データモデル図（Entity-Relationship Diagram）
  └─ 各テーブル / Sheet のフィールドが一覧化
  └─ 正規化度（1NF / 2NF / 3NF）が適切か
```

#### コンポーネント分離確認
```
□ 各サービスが独立してテスト可能か
  └─ CustomerService.getOrCreateCustomer() を mock なしで実行
  └─ MatchingService.findApplicablePrograms() に異なる customer を渡す
  
□ インタフェース（入出力）が型安全か
  └─ TypeScript コンパイルエラーが 0 か
  
□ 外部依存（API キー、Google Sheets）が環境変数化されているか
  └─ .env ファイルから読み込めるか
```

#### データフロー検証
```
□ Happy Path テスト（正常系）
  手順:
  1. ユーザー入力: { name: "ABC建設", industry: "建築", revenue: 5000万 }
  2. Customer Service が企業マスタに保存
  3. Matching Service が該当制度を抽出（3件以上）
  4. Notification Service がログに記録
  
  検証:
  - Google Sheets に企業 ID が自動採番されているか
  - 制度検索が正しい結果を返すか
  - 配信ログにタイムスタンプが記録されているか

□ Edge Case テスト（異常系）
  手順:
  1. 同じ企業名を 2 回送信
  2. API 403 エラーをシミュレート
  3. データベースが空の状態で検索
  
  検証:
  - 企業 ID の重複がないか
  - 403 エラーがログに記録されるか
  - 空結果が graceful に処理されるか

□ 権限フロー検証
  手順:
  1. L1 ユーザーで自分の顧客データを取得
  2. L1 ユーザーで他人の顧客データを取得（should fail）
  3. L3 管理者で全データを取得
  
  検証:
  - 権限なしアクセスが 403 を返すか
  - L3 のみ監査ログを見られるか
  - 誰が何をいつ変更したかが記録されているか
```

### CI/CD パイプラインでの自動検証

```yaml
# .github/workflows/design-validation.yml
name: Design Validation

on: [pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      # TypeScript コンパイル
      - run: npx tsc --noEmit
      
      # 単体テスト（各 Service）
      - run: npm test -- --testPathPattern="service"
      
      # 統合テスト（フロー全体）
      - run: npm test -- --testPathPattern="integration"
      
      # 型安全チェック
      - run: npx type-coverage --min 95
      
      # アーキテクチャ図の自動検証（Mermaid）
      - run: npx mermaid --version
```

### テスト完了条件

```
✅ すべてのチェックリスト項目が完了
✅ Happy Path テストが成功
✅ Edge Case テストが成功（失敗ケースも期待通り）
✅ 権限フロー検証が成功
✅ CI/CD パイプラインが green
✅ code coverage が 80% 以上
✅ チームレビュー・承認が取れた
```

テスト完了後、本番環境への依頼（小柳さん決裁）へ進む。

---

## 関連スキル

- `user-research-hojo` — ユーザーの権限要件・プロセスフローを決める
- `transcription-analysis-hojo` — 自動化の実装例（Zapier / Apps Script）
- `shiryo-sakusei` — 実装例の出典確認
