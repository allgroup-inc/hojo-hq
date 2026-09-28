# Phase 2 実装 Kickoff ガイド

> **作成日**: 2026-09-28  
> **対象**: Phase 2実装チーム (エンジニア・QA・PM)  
> **目標**: 2026-10-10 本番デプロイ

---

## 📋 このガイドの位置づけ

このドキュメントは **Phase 0完成 → Phase 2実装開始** までの引き継ぎガイドです。以下の流れで Phase 2を進めます：

```
Kickoff (09-28)
    ↓
GitHub Issues 作成 (09-28 夜間)
    ↓
Block 1 実行 (09-29~09-30)
    ↓
Gateway G1 判定 (09-30)
    ↓
Block 2 実行 (10-01~10-03)
    ↓
Block 3 実行 (10-04~10-06)
    ↓
Block 4 実行 (10-08~10-10)
    ↓
本番デプロイ (10-10 09:00)
```

---

## 🎯 今日やること (2026-09-28)

### Step 1: このドキュメント全体を読む
**所要時間**: 15分

- 全チーム: 対象範囲・依存関係・リスク一覧を確認

### Step 2: GitHub Issues を作成
**所要時間**: 10分

以下の2つの方法から選択：

#### **方法A: スクリプトで自動作成** (推奨)
```bash
cd /home/user/hojo-hq

# Python インポートツール実行
python3 scripts/import-phase2-issues.py

# (gh CLI がインストール済みの場合)
```

**前提条件**:
- `gh` CLI がインストール・認証済み
- GitHub Personal Access Token (repo 権限) が設定済み

#### **方法B: 手動作成**
1. 以下のファイルを開く: `docs/kakehashi-poc/PHASE2-ISSUES-JSON.json`
2. 各 issue を GitHub Web UI (`https://github.com/allgroup-inc/hojo-hq/issues/new`) で手動作成
3. ラベル・マイルストーン・ブロッカー関連付けを設定

### Step 3: GitHub Projects を設定
**所要時間**: 5分

1. GitHub リポジトリ → Projects タブ
2. 新規 Project: **Phase 2 (09-29 ~ 10-10)**
3. テンプレート: **Table (Table form)**
4. フィルタ設定: `milestone:"Phase 2 (09-29 ~ 10-10)"`

### Step 4: Channel / Slack 通知設定
**所要時間**: 5分

**Slack**:
- #apo-dev チャネルを作成 (存在しない場合)
- GitHub integration 設定: `allgroup-inc/hojo-hq` を接続
- `issues:updated` イベント有効化

**日次 standup** (09-29 以降):
- 時刻: 09:00 JST
- 場所: #apo-dev
- 議題: 前日の進捗・本日のブロッカー・サポート必要項目

---

## 📚 準備資料一覧

全チーム向けの 6つのドキュメント (すべて docs/kakehashi-poc/ に配置):

| ドキュメント | 用途 | 対象 |
|---|---|---|
| **README.md** | プロジェクト全体概要・成果物一覧 | 全員 |
| **PHASE2-INTEGRATION-MASTER-PLAN.md** | 4ブロック・ゲートウェイの詳細スケジュール | PM・リーダー |
| **IMPLEMENTATION-HANDBOOK.md** | 実装タスク・ゲートウェイ・通信規約 | エンジニア・QA |
| **API-SPECIFICATION.md** | REST API 15エンドポイント完全仕様 | バックエンド・フロントエンド |
| **DATA-MIGRATION-GUIDE.md** | GAS → RDS マイグレーション手順 | データ・バックエンド |
| **GITHUB-ISSUES-CHECKLIST.md** | 16 Issue の定義と依存関係 | PM・プロダクト |

**読む順序**:
1. 全員: README.md (5分)
2. 全員: このドキュメント (10分)
3. 役割別:
   - PM: PHASE2-INTEGRATION-MASTER-PLAN.md → GITHUB-ISSUES-CHECKLIST.md
   - バックエンド: API-SPECIFICATION.md → DATA-MIGRATION-GUIDE.md → IMPLEMENTATION-HANDBOOK.md
   - フロントエンド: API-SPECIFICATION.md → IMPLEMENTATION-HANDBOOK.md
   - QA: IMPLEMENTATION-HANDBOOK.md → DATA-MIGRATION-GUIDE.md

---

## 🚀 Block 1 のセットアップ (09-29 朝)

### 9:00 - Block 1 キックオフ
```
【参加】エンジニア・データ・PM・QA
【アジェンダ】
- Issue #1〜#4 の依存関係確認
- ブロッカー・優先順位の明確化
- 各自の担当 Issue 確認
- 質問・懸念事項の吸い上げ
【所要時間】15分
```

### 9:15 - 各自タスク開始

**Issue #1: API仕様書最終化** (エンジニア・PM)
- ファイル: `docs/kakehashi-poc/API-SPECIFICATION.md`
- 内容確認: 15エンドポイント・スキーマ・認証
- 成果物: Postman Collection テンプレート生成
- 期限: 2026-09-29 14:00

**Issue #2: GASデータ抽出** (データチーム)
- 対象: Google Sheets の users / appointments シート
- 出力: JSON形式
- 格納: S3一時フォルダ
- 期限: 2026-09-29 14:00

**Issue #3: マイグレーションスクリプト作成** (バックエンド)
- ファイル:
  - `scripts/migration/transform_gas_to_csv.py` (新規作成)
  - `scripts/migration/validate_migration_data.py` (新規作成)
- 前提: Issue #1, #2 完了
- 期限: 2026-09-30 11:00

**Issue #4: テスト環境でマイグレーション検証** (QA)
- 対象: テスト用RDS接続・データ品質確認
- 行数検証: users=12, appointments=1,847 (±5%)
- 前提: Issue #3 完了
- 期限: 2026-09-30 18:00

### 14:00 - Block 1 進捗確認
```
【形式】Slack #apo-dev でスレッド報告
【内容】Issue #1, #2 の成果物・進捗状況
【対象】PM・リーダー
```

### 18:00 - Block 1 日次レビュー
```
【参加】エンジニア・データ・QA・PM
【アジェンダ】
- Issue #1, #2 の成果物確認
- Issue #3 の実装方針確認
- Issue #4 の準備状況
- ブロッカー・リスク共有
【所要時間】20分
```

---

## 🚪 Gateway G1 判定 (09-30 16:00)

### 判定基準 (すべて PASS 必須)
```
✅ Issue #1: API-SPECIFICATION.md が15エンドポイント完全網羅
✅ Issue #2: users (12行) + appointments (1,847行) をJSON出力
✅ Issue #3: マイグレーション実行スクリプト実装完了
✅ Issue #4: テスト環境でデータ検証完了 (行数±5%以内)
✅ Issue #1,#2,#3,#4 すべてCloseされている
```

### 判定責任者
- **PM/プロダクトリーダー**: Gate open/close の判定
- **アーキテクト**: 技術的妥当性の確認

### 不合格時の対応
1. 改善リストアップ (短時間修正可能か / 設計見直し必要か)
2. 優先度付け (Critical / High / Medium)
3. Block 2 開始タイミング判定
4. 小柳さんへ相談 (設計根本的変更の場合)

---

## 🔄 Block 2 実行 (10-01~10-03)

### Issue #5: kakei-apo 統合
**対象**: PoC実装を kakei-apo リポジトリへ移設  
**依存**: Issue #4 (Gateway G1 Pass)  
**期限**: 2026-10-01 18:00

### Issue #6-8: 統合テスト
**対象**: ❶入口・❂訪問管理・❸保全CRM との連携確認  
**依存**: Issue #5 完了  
**期限**: 2026-10-02~10-03

### Issue #9: Gateway G1 検証
**判定責任**: PM・アーキテクト  
**期限**: 2026-09-30 23:59 (Block 1→2 の Go/No-Go)

---

## 🏗️ Block 3 実行 (10-04~10-06)

### Issue #10-12: 本番環境準備
- **#10**: AWS/Terraform インフラ構築
- **#11**: Entra ID ユーザー・トークン設定
- **#12**: トレーニング・運用マニュアル

### 実行チェックポイント
```
2026-10-04 AM: Terraform apply 実行完了
2026-10-05 AM: Entra ID ユーザー12名登録完了
2026-10-06 PM: トレーニング資料完成
```

---

## 🎯 Block 4 実行 (10-08~10-10)

### Issue #13-16: 本番デプロイ
- **#13**: 本番RDS マイグレーション (10-08 AM)
- **#14**: 統合テスト・UAT (10-09)
- **#15**: Gateway G5 最終判定 (10-09 16:00)
- **#16**: 本番デプロイ・運用開始 (10-10 09:00)

### 本番デプロイ手順
```bash
# 2026-10-10 08:30 開始
git fetch origin main
git checkout -B production origin/main
git merge --no-ff claude/sales-appointment-management-app-5fuo4y

# CI/CD パイプライン自動実行
# - test ✓
# - docker build ✓
# - terraform apply ✓
# - verify ✓
# - notify slack

# 08:50 デプロイ完了通知
# 09:00 営業マン・APO担当者 利用開始
```

---

## ⚠️ リスク・対応策

| リスク | 発生確率 | 影響度 | 対応策 |
|---|---|---|---|
| **RDS接続エラー** | Medium | High | Terraform 구성 사전검증 / VPC 보안그룹 점검 |
| **Entra ID トークン発行失敗** | Low | High | テストユーザーで事前検証 / Azure Portal 相談 |
| **マイグレーション時間超過** | Medium | Medium | 本番RDSでリハーサル実施 (10-07) |
| **UI動作確認の遅延** | Low | Medium | フロントエンド並行開発 (Block 2中) |
| **ロールバック手順未検証** | Low | Critical | ① テスト環境で検証 ② 本番前リハーサル |

---

## 📞 エスカレーション基準

### 「相談してから動く」対象
- **API仕様の変更** (15エンドポイント中3個以上)
- **RDS スキーマ変更** (既存テーブル削除・構造大幅変更)
- **Entra ID 連携方式の見直し**
- **本番デプロイ日時の変更** (10-10 09:00)

### **相談先**
1. **PM/リーダー**: 日程・優先度・リソース相談
2. **小柳さん**: ① 予算変更 ② 機能削減/追加 ③ ステークホルダー調整

### **緊急時連絡**
```
【平日業務時間】Slack #apo-dev
【夜間・休日】PM/エンジニアリーダー 直通
【本番環境障害】CTO + PM 二人体制で対応
```

---

## ✅ Phase 2 最終チェックリスト

### Kickoff 当日 (09-28)
- [ ] このドキュメント全員が読了
- [ ] 16 Issue が GitHub に作成済み
- [ ] GitHub Projects 設定完了
- [ ] Slack #apo-dev 通知設定完了
- [ ] 各自の担当 Issue 確認済み
- [ ] 質問・懸念事項の全共有

### Block 1 開始前 (09-29 08:30)
- [ ] 本番環境準備シークレット (AWS/Azure) 配置済み
- [ ] GAS Sheets アクセス権限確認済み
- [ ] テスト環境RDS 接続テスト完了
- [ ] Git ブランチ `phase2-implementation` 作成済み

### Block 1 完了時 (09-30 18:00)
- [ ] Issue #1-4 すべてClose
- [ ] Gateway G1 Pass or No-Go 明確化
- [ ] 本番レディネス判定ドキュメント作成

### Block 4 完了時 (10-10 10:00)
- [ ] 営業マン12人が APO システム利用開始
- [ ] 初日障害対応チーム待機中
- [ ] 本番運用マニュアル デプロイ完了
- [ ] 1週間分の予定データが正常に同期中

---

## 📌 参考リンク

- **PoC 実装**: `apps/kakehashi-apo/` (Phase 0 完成品)
- **既存GAS**: Google Sheets / Apps Script
- **本番環境設定**: `terraform/` + `scripts/setup-production.sh`
- **CI/CD パイプライン**: `.github/workflows/production-deploy.yml`

---

## 🎓 役割別 読んでおくべき資料

### **エンジニア (バックエンド)**
1. API-SPECIFICATION.md (全仕様)
2. DATA-MIGRATION-GUIDE.md (Phase 1 詳細)
3. IMPLEMENTATION-HANDBOOK.md (実装チェックリスト)
4. `terraform/main.tf` (本番インフラ)

### **エンジニア (フロントエンド)**
1. API-SPECIFICATION.md (インタフェース仕様)
2. IMPLEMENTATION-HANDBOOK.md (UI実装チェック)
3. `apps/kakehashi-apo/frontend/` (既存コンポーネント)

### **QA / テスター**
1. IMPLEMENTATION-HANDBOOK.md (テストシナリオ)
2. DATA-MIGRATION-GUIDE.md (マイグレーション検証)
3. API-SPECIFICATION.md (API テストケース)

### **PM / プロダクトリーダー**
1. PHASE2-INTEGRATION-MASTER-PLAN.md (全体タイムライン)
2. GITHUB-ISSUES-CHECKLIST.md (16 Issue 管理)
3. IMPLEMENTATION-HANDBOOK.md (ゲートウェイ判定基準)

### **プロジェクトマネージャー / リーダー**
1. このドキュメント (Kickoff ガイド)
2. PHASE2-INTEGRATION-MASTER-PLAN.md (スケジュール・リスク)
3. IMPLEMENTATION-HANDBOOK.md (日次スタンダップ内容)

---

## 🏁 まとめ

**Phase 2 の3つのゴール**:
1. ✅ **09-30**: API仕様・データマイグレーション確定 (Block 1)
2. ✅ **10-07**: kakei-apo 統合完了 (Block 1~3)
3. ✅ **10-10**: 本番デプロイ・営業マン利用開始 (Block 4)

**最後に**:
- 何か不明な点 → このガイドを読み直し (9割解決)
- それでも不明 → PM/リーダーに Slack で相談
- 技術的な懸念 → アーキテクト・CTO に Issue コメントで相談

**では、09-29 09:00 の Block 1 キックオフでお会いしましょう！** 🚀

---

**作成**: Claude Haiku 4.5  
**日時**: 2026-09-28  
**版**: Phase 2 Kickoff v1.0
