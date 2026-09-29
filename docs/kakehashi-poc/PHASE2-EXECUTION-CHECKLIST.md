# Phase 2 実行チェックリスト

> **実行開始日**: 2026-09-29 (本日)  
> **完成日**: 2026-10-10  
> **対象**: 実装チーム全員

---

## ✅ セットアップ完了確認 (09-29 朝)

### GitHub 環境準備
- [ ] GitHub Issues #389-404 が作成済み確認
  - 📌 Issue 一覧: https://github.com/allgroup-inc/hojo-hq/issues?q=milestone%3A%22Phase+2%22
  - Issue 数: 16個全て ✓
  
- [ ] マイルストーン作成 (2分)
  1. GitHub → Issues → Milestones
  2. "Phase 2 (09-29 ~ 10-10)" を作成
  3. 説明: "KAKEHASHI APO Management System Phase 2 Implementation"
  4. 16 issue を このマイルストーンに割り当て
  
- [ ] GitHub Projects 設定 (3分)
  1. GitHub → Projects → New project
  2. テンプレート: "Table"
  3. 名前: "Phase 2 (09-29 ~ 10-10)"
  4. フィルタ: `milestone:"Phase 2 (09-29 ~ 10-10)"`

### Slack チャネル準備
- [ ] #apo-dev チャネル作成 (存在しない場合)
- [ ] メンバー招待: エンジニア全員 + PM + QA
- [ ] チャネル説明: "KAKEHASHI APO Phase 2 実装 09-29~10-10"
- [ ] ピン付け: PHASE2-KICKOFF-GUIDE.md へのリンク

### ドキュメント準備
- [ ] 全員が PHASE2-KICKOFF-GUIDE.md を読了
  - 所要時間: 10分
  - 役割別の読む順序を確認
  
- [ ] PM が PHASE2-INTEGRATION-MASTER-PLAN.md を確認
  - ブロック別スケジュール確認
  - ゲートウェイ判定基準確認
  
- [ ] エンジニアが API-SPECIFICATION.md 確認
  - 15エンドポイント理解
  - 認証フロー (OAuth 2.0 + JWT) 確認

### リソース・権限確認
- [ ] AWS credentials (Terraform 実行用)
  - Access Key ID / Secret Access Key
  - 本番RDS作成権限確認
  
- [ ] Azure Entra ID 権限
  - テストユーザー作成権限確認
  - OAuth app 設定確認
  
- [ ] Google Sheets API key
  - GAS データ抽出用
  - S3 access key/secret

---

## 📅 Block 1 実行 (09-29~09-30)

### 🌅 2026-09-29 09:00 - Block 1 キックオフ
```
【参加】全員
【時間】15分
【場所】Slack #apo-dev でスレッド開始

【アジェンダ】
1. Issue #1-4 の依存関係確認 (3分)
   - #1 (API仕様) と #2 (GASデータ抽出) は並行可能
   - #3 (マイグレーション) は #1,#2 後
   - #4 (検証) は #3 後

2. 担当者割り当て確認 (5分)
   - Issue #1: エンジニア + PM
   - Issue #2: データ/API チーム
   - Issue #3: バックエンド エンジニア
   - Issue #4: QA

3. ブロッカー・質問吸い上げ (7分)
```

### 🔨 2026-09-29 09:15-14:00 - Issue #1, #2 実装
- [ ] **Issue #1 担当**: API-SPECIFICATION.md の15エンドポイント確認
  - [ ] JSON schema の実装可能性を確認
  - [ ] Postman Collection テンプレート生成
  - [ ] エラーハンドリング実装方針決定
  - 期限: 14:00
  
- [ ] **Issue #2 担当**: GAS Sheets からデータ抽出
  - [ ] users シート (12行) → JSON
  - [ ] appointments シート (3年分) → JSON
  - [ ] 敏感情報フィルタリング
  - [ ] S3 に保存
  - 期限: 14:00

### 📊 2026-09-29 14:00 - 進捗レポート
```
【形式】Slack #apo-dev スレッド
【内容】
- Issue #1 成果物: Postman Collection / 実装方針
- Issue #2 成果物: JSON ファイル (sample)
- ブロッカー・懸念事項
```

### 🔧 2026-09-29 14:00-18:00 - Issue #3 実装準備
- [ ] **Issue #3 担当**: マイグレーション実装スクリプト作成
  - [ ] `scripts/migration/transform_gas_to_csv.py` 実装
  - [ ] 営業マン ID マッピングテーブル作成
  - [ ] データクリーニングロジック実装
  - [ ] テスト環境で試験実行
  - 期限: 2026-09-30 11:00

### 🎯 2026-09-29 18:00 - 日次レビュー
```
【参加】全員
【時間】20分
【内容】
1. Issue #1, #2 の成果物確認 (10分)
2. Issue #3 実装状況の質問吸い上げ (5分)
3. 本日のリスク・課題 (5分)
```

### 🌅 2026-09-30 09:00 - Issue #4 キックオフ
- [ ] **Issue #4 担当 (QA)**: テスト環境マイグレーション検証
  - [ ] テスト用RDS 接続確認
  - [ ] Issue #3 で完成した実行スクリプト実行
  - [ ] データ行数確認: users=12, appointments=1,847 (±5%)
  - [ ] ステータス分布が合理的か確認
  - [ ] API で過去データが取得できるか確認
  - 期限: 2026-09-30 18:00

### 🚪 2026-09-30 16:00 - Gateway G1 判定
```
【判定責任】PM / アーキテクト
【判定基準】
✅ Issue #1: API-SPECIFICATION.md 完全網羅 (15 エンドポイント)
✅ Issue #2: users (12行) + appointments (1,847行) JSON 出力
✅ Issue #3: マイグレーション実行スクリプト実装 + テスト実行
✅ Issue #4: テスト環境での検証完了 (行数±5%以内)

【Go/No-Go 判定】
- PASS → Block 2 2026-10-01 開始 ✓
- FAIL → 改善内容リストアップ + 小柳さん相談
```

---

## 📋 毎日の Standup (09-29 以降)

```
⏰ 09:00 JST - Slack #apo-dev
【形式】スレッド投稿 (全員)
【内容】(1行) 今日の目標 / 進捗 / ブロッカー

【例】
エンジニアA: "Issue #3 マイグレーション実装。#2のJSON出力待ち"
エンジニアB: "Issue #2 データ抽出完了。S3にアップロード済み。#3へ引き継ぎ"
QA: "テスト環境RDS接続テスト中。#3の完成待ちで準備"
```

---

## 🔗 依存関係マップ

```
Issue #1 (API仕様)
    ↓
Issue #3 (マイグレーション)  ← Issue #2 (データ抽出) からも依存
    ↓
Issue #4 (テスト環境検証)
    ↓
Gateway G1 判定 (09-30 16:00)
    ↓
Block 2 開始 (10-01)
```

**重要**: Issue #2 と #1 は依存がないため **並行実行可能** (同時開始で問題なし)

---

## ⚠️ よくあるトラブルと対応

| 症状 | 原因 | 対応 |
|---|---|---|
| **GAS Sheets 接続エラー** | API key 未設定 | `.env` ファイルに `GOOGLE_API_KEY=...` 設定 |
| **S3 アップロード失敗** | AWS credentials なし | `aws configure` で credentials 設定 |
| **RDS テスト接続失敗** | VPC セキュリティグループ | Terraform でセキュリティグループを確認・修正 |
| **マイグレーション行数不一致** | データクリーニングロジック | `scripts/migration/validate_migration_data.py` でデバッグ |
| **JSON schema 検証エラー** | スキーマ定義の誤り | API-SPECIFICATION.md と実装を照合 |

---

## 📞 緊急連絡先

| 対象 | 連絡先 | 対応時間 |
|---|---|---|
| API 仕様の質問 | PM (#apo-dev) | 09:00-18:00 |
| GAS/データ抽出エラー | データチーム (#apo-dev) | 09:00-18:00 |
| Terraform/AWS エラー | インフラ (#apo-dev) | 09:00-18:00 |
| 日程・優先度変更 | PM / リーダー | 09:00-18:00 |
| **本番環境障害** (10-10以降) | CTO + PM 二人体制 | 24/7 |

---

## 🎯 成功の定義

### Block 1 成功 (2026-09-30 18:00)
```
✅ 全4 Issue Close
✅ Gateway G1 Pass
✅ マイグレーション検証完了 (行数±5%以内)
✅ 本番RDSへの移行準備完了
```

### Block 2 成功 (2026-10-03 18:00)
```
✅ kakei-apo 統合完了
✅ ❶❂❸連携テスト Pass
✅ UI 統合テスト Pass
```

### Block 3 成功 (2026-10-06 18:00)
```
✅ AWS/Terraform 本番構築完了
✅ Entra ID ユーザー12名登録完了
✅ トレーニング資料完成
```

### Block 4 成功 (2026-10-10 09:00)
```
✅ 本番RDS マイグレーション完了
✅ 全統合テスト・UAT Pass
✅ 営業マン12人・APO担当者 利用開始
✅ 初日障害対応チーム 稼働中
```

---

## 📚 参考ファイル一覧

```
docs/kakehashi-poc/
  ├── README.md                           # プロジェクト概要
  ├── PHASE2-KICKOFF-GUIDE.md             # 実装ガイド
  ├── PHASE2-INTEGRATION-MASTER-PLAN.md  # 詳細スケジュール
  ├── PHASE2-EXECUTION-CHECKLIST.md       # このファイル
  ├── IMPLEMENTATION-HANDBOOK.md          # 実装ハンドブック
  ├── API-SPECIFICATION.md                # REST API仕様書
  ├── DATA-MIGRATION-GUIDE.md             # マイグレーション手順
  ├── GITHUB-ISSUES-CHECKLIST.md          # Issue定義
  └── PHASE2-ISSUES-JSON.json            # Issue定義 (JSON)

scripts/
  ├── create-phase2-issues-api.py         # Issue自動作成ツール
  ├── import-phase2-issues.py             # gh CLI 版
  └── migration/
      ├── transform_gas_to_csv.py         # GAS→CSV変換 (未作成)
      └── validate_migration_data.py      # マイグレーション検証 (未作成)

.github/workflows/
  └── production-deploy.yml               # CI/CD パイプライン
```

---

## 🚀 最後に

**本日 (2026-09-29) の流れ**:
1. ✅ 09:00 - Block 1 キックオフ会議
2. ✅ 09:15 - Issue #1, #2 実装開始
3. ✅ 14:00 - 進捗レポート
4. ✅ 14:00-18:00 - Issue #3 実装
5. ✅ 18:00 - 日次レビュー

**期待値**:
- Issue #1, #2: 2026-09-29 の本日中に完成
- Issue #3, #4: 2026-09-30 に完成
- Gateway G1: 2026-09-30 16:00 に Pass 判定

**頑張りましょう！** 🎉
