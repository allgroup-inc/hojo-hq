# 実装ハンドブック
> **次チーム（実装・統合テスト）向けの完全ガイド**

**対象者**: エンジニア・QA・インフラ・プロジェクトマネージャー  
**受け取り日**: 2026-09-29  
**実装期間**: 2026-09-29 ～ 2026-10-10  
**最終納品**: 2026-10-10 営業12名による本番利用開始

---

## 🚀 クイックスタート（読む順序）

### 1️⃣ **まず最初に読むドキュメント**（全員）

| ドキュメント | 目的 | 読了時間 |
|---|---|---|
| **このハンドブック** | 全体像・何をするか理解 | 30分 |
| **PHASE2-INTEGRATION-MASTER-PLAN.md** | タスク分解・スケジュール確認 | 1時間 |
| **KAKEHASHI統合アーキテクチャ設計** | システム構成図・他システムとの接点 | 30分 |

### 2️⃣ **役割別に読むドキュメント**

#### エンジニア
1. **API-SPECIFICATION.md** - API仕様書（1.5時間）
2. **kakei-apo の構成** - 既存リポジトリ確認（1時間）
3. **Docker/Terraform設定** - PoC実装の確認（1時間）

#### QA/テスター
1. **統合テストシナリオ** - API-SPECIFICATION.md の「テストシナリオ」セクション（1時間）
2. **DATA-MIGRATION-GUIDE.md** - マイグレーション検証項目（1.5時間）
3. **本番検証チェックリスト** - VERIFY-PRODUCTION.md（1時間）

#### インフラ
1. **Terraform設定** - PoC実装（terraform/ ディレクトリ）（1時間）
2. **DATA-MIGRATION-GUIDE.md** - Phase 3 本番環境準備（1.5時間）
3. **RDSバックアップ・リカバリ** - AWS 手順書（1時間）

#### PM/リーダー
1. **PHASE2-INTEGRATION-MASTER-PLAN.md** - 全体スケジュール・ゲートウェイ（1時間）
2. **リスク管理セクション** - 要因・対策・連絡体制（30分）
3. **ゲートウェイ & 承認ポイント** - 意思決定タイミング（30分）

---

## 📦 ハンドオーバー成果物

### ✅ 既に完成した成果物

```
docs/kakehashi-poc/
├── PHASE1-DEPLOYMENT-PLAN.md           ← PoC本番化ガイド
├── SETUP-AWS.md                        ← AWS環境構築（完了済み）
├── SETUP-ENTRA-ID.md                   ← Entra ID設定（完了済み）
├── SETUP-TERRAFORM.md                  ← Terraform実行（完了済み）
├── VERIFY-PRODUCTION.md                ← 検証チェックリスト
├── PHASE2-INTEGRATION-MASTER-PLAN.md   ← 統合実装ロードマップ【NEW】
├── API-SPECIFICATION.md                ← API完全仕様書【NEW】
└── DATA-MIGRATION-GUIDE.md             ← マイグレーション手順【NEW】

scripts/
├── setup-production.sh                 ← AWS自動化
├── verify-production.sh                ← 検証自動化
└── create-test-users.ps1               ← テストユーザー自動作成

.github/workflows/
└── production-deploy.yml               ← CI/CD パイプライン

kakehashi-apo/                          ← PoC実装コード
├── backend/                            ← Node.js + Express
│   ├── src/
│   │   ├── auth/                       ← OAuth認証
│   │   ├── appointments/               ← アポイントメント管理
│   │   ├── sales-reps/                 ← 営業マン管理
│   │   └── kpi/                        ← KPI集計
│   └── package.json
├── frontend/                           ← React + Material-UI
│   ├── src/
│   │   ├── components/                 ← UI コンポーネント
│   │   ├── pages/                      ← ページ・ビュー
│   │   └── services/                   ← API呼び出し
│   └── package.json
└── docker-compose.yml                  ← ローカル開発環境

terraform/
├── main.tf                             ← VPC・EC2・RDS定義
├── variables.tf                        ← 変数定義
├── terraform.tfvars                    ← 環境固有値
└── scripts/
    └── rds-backup-restore.sh          ← バックアップ・復旧
```

### 🔧 確認すべきコード

```bash
# PoC実装の主要ファイル確認
ls -la kakehashi-apo/backend/src/

# API実装確認
grep -n "app.get\|app.post\|app.patch" kakehashi-apo/backend/src/index.js

# DB接続確認
grep -n "DATABASE_URL\|Prisma\|pg" kakehashi-apo/backend/src/db.js

# 認証実装確認
grep -n "OAuth\|JWT\|Entra" kakehashi-apo/backend/src/auth/index.js
```

---

## 🎯 実装フェーズ（Phase 2）のやることリスト

### Block 1: API・マイグレーション確定（09-29 ～ 09-30）

#### Task 2-1-1: API仕様書最終化
**対象**: エンジニア・PM  
**チェックリスト**:
- [ ] API-SPECIFICATION.md のエンドポイント15個が全て実装可能か確認
- [ ] エラーハンドリングコード（400/401/403/404/409/500）の実装方針確認
- [ ] レート制限の実装方法決定（Redis or in-memory）
- [ ] JWTの署名・検証方法が確定したか
- [ ] Postman コレクション テンプレート作成開始

**成果物**: Postman Collection v2.1 形式（テスト環境用・本番用）

---

#### Task 2-1-2: GASデータ抽出
**対象**: データチーム  
**チェックリスト**:
- [ ] Google Sheets API で `users` シートをJSON出力
- [ ] Google Sheets API で `appointments` シート（過去3年分）をJSON出力
- [ ] 抽出ファイルのサイズ・フォーマット確認
- [ ] 敏感情報（顧客個人情報）が含まれていないか確認
- [ ] S3 or GitHub Secrets に一時保存

**実行コマンド**:
```bash
python3 scripts/migration/extract_gas_data.py \
  --sheet-id $SHEET_ID \
  --output /tmp/gas_export.json
```

---

#### Task 2-1-3: マイグレーションスクリプト作成
**対象**: エンジニア  
**チェックリスト**:
- [ ] `scripts/migration/transform_gas_to_csv.py` を実装（JSON → CSV変換）
- [ ] 営業マンID マッピングテーブルを作成（rep-001 → UUID）
- [ ] CSVクリーニングロジック実装（空白・重複・形式統一）
- [ ] `scripts/migration/validate_migration_data.py` を実装
- [ ] テスト環境で試験実行

**実装テンプレート**:
```python
# scripts/migration/transform_gas_to_csv.py
import json
import csv
from datetime import datetime

def transform_users(json_data):
    """JSON → users.csv に変換"""
    users = []
    for user in json_data['users']:
        users.append({
            'id': user['id'],
            'entra_id': f"user-{user['id']}",  # 後で修正
            'email': user['email'],
            'name': user['name'],
            'role': 'SALES_REP',
            'created_at': datetime.now().isoformat()
        })
    return users

def transform_appointments(json_data):
    """JSON → appointments.csv に変換"""
    appointments = []
    for apt in json_data['appointments']:
        appointments.append({
            'id': f"APO-{apt['date'].replace('-','')}-001",
            'customer_name': apt['customer'],
            'scheduled_datetime': f"{apt['date']}T{apt['time']}:00+09:00",
            'estimated_duration': 60,
            'assigned_sales_rep_id': apt['rep_id'],
            'status': 'COMPLETED' if apt.get('done') else 'CANCELLED' if apt.get('cancelled') else 'SCHEDULED'
        })
    return appointments
```

---

#### Task 2-1-4: テスト環境でマイグレーション検証
**対象**: QA  
**チェックリスト**:
- [ ] テスト用RDS接続確認（`psql -h test-rds...`）
- [ ] マイグレーション実行
- [ ] 行数確認：users = 12、appointments = 1847（±5%）
- [ ] ステータス分布が合理的か（COMPLETED 80-90%）
- [ ] API の GET /appointments で過去データが取得できるか

**検証スクリプト実行**:
```bash
pytest scripts/migration/test_migration.py::test_users_count -v
pytest scripts/migration/test_migration.py::test_appointments_count -v
pytest scripts/migration/test_migration.py::test_status_distribution -v
```

---

### Block 2: 統合テスト実施（10-01 ～ 10-03）

#### Task 2-2-1: kakei-apo への本システムコンポーネント組み込み
**対象**: エンジニア  
**チェックリスト**:
- [ ] kakei-apo リポジトリ (非公開) のセットアップ
- [ ] PoC実装の `kakehashi-apo/backend` → `kakei-apo/src/schedule-management/` へ移設
- [ ] PoC実装の `kakehashi-apo/frontend` → `kakei-apo/apps/schedule-management/` へ移設
- [ ] 既存kakei-apoの認証・DB接続方式に合わせて調整
- [ ] 環境変数を kakei-apo の `.env` に統合
- [ ] Docker イメージ再ビルド・起動テスト

**移設ステップ**:
```bash
# 1. kakei-apo へのパスセットアップ
cd /path/to/kakei-apo
git checkout develop  # 最新ブランチ確認

# 2. PoC実装をコピー
cp -r /path/to/hojo-hq/kakehashi-apo/backend src/schedule-management
cp -r /path/to/hojo-hq/kakehashi-apo/frontend apps/schedule-management

# 3. 依存関係を修正
cd src/schedule-management && npm install

# 4. 認証設定を kakei-apo 既存方式に合わせる
# Entra ID 設定を環境変数から読み込むように修正
```

---

#### Task 2-2-2: ❶入口システム連携テスト
**対象**: QA  
**チェックリスト**:
- [ ] ❶入口システムから `POST /api/v1/appointments` を試行
- [ ] リクエスト形式が API-SPECIFICATION.md に一致するか
- [ ] レスポンス201 CreatedでAPO-XXXが返されるか
- [ ] 営業マンへのラウンドロビン振り分けが動作するか
- [ ] Slack通知が `#営業-スケジュール` に送信されるか

**テストシナリオ**:
```bash
# テスト用のアポイントメントを3件登録
curl -X POST "http://localhost:3000/api/v1/appointments" \
  -H "Authorization: Bearer $TEST_JWT" \
  -d '{
    "customerId": "KM-00001",
    "customerName": "テスト企業A",
    "scheduledDateTime": "2026-10-15T14:00:00+09:00",
    "estimatedDuration": 60,
    "location": "沖縄県那覇市",
    "source": "apogen_system"
  }'

# 返り値確認：201 + APO-20261015-001
# ↓
# Slack に "テスト企業A のアポを営業太郎に割り当てました" と送信されるか確認
```

---

#### Task 2-2-3: ❂訪問管理システム連携テスト
**対象**: QA  
**チェックリスト**:
- [ ] アポイントメントを完了状態（COMPLETED）に更新
- [ ] 本システムから `POST /api/v1/visits/completed` が ❂へ送信されるか
- [ ] ❂システムがその通知を受け取り、その後の処理（申込作成等）に進むか
- [ ] キャンセル通知も同様にテスト

**テストケース**:
```
ケース1: アポ完了
- アポID: APO-20261015-001
- 更新: PATCH /appointments/APO-20261015-001 → status=COMPLETED
- 検証: ❂へのPOST成功、ステータスコード200/202

ケース2: アポキャンセル
- 更新: POST /appointments/APO-20261015-001/cancel
- 検証: ❂へのPOST成功、営業マンのスケジュール時間が開放される
```

---

#### Task 2-2-4: ❸保全CRMとのデータ連携テスト
**対象**: QA  
**チェックリスト**:
- [ ] 本システムのKPIレポート（GET /kpi/daily-summary）が正常に取得できるか
- [ ] ❸側が本システムの KPI データを参照できるか（API連携の疎通確認）
- [ ] データ形式・フィールド名が ❸で期待される形式か

---

#### Task 2-2-5: Slack通知・UI動作の統合テスト
**対象**: QA  
**チェックリスト**:
- [ ] 新規アポ登録時 → Slack に通知が送信されるか
- [ ] UI で「日ビュー」「週ビュー」「月ビュー」が正常に動作するか
- [ ] ドラッグ&ドロップでアポを移動できるか
- [ ] スマートフォン（レスポンシブ）で表示が正しいか
- [ ] リアルタイム更新（複数営業が同じ画面を見ている時）が動作するか

---

### Block 3: 本番環境準備（10-04 ～ 10-07）

#### Task 2-3-1: Terraform本番環境の最終構成確認
**対象**: インフラ  
**チェックリスト**:
- [ ] `terraform plan` で本番リソース（EC2 t3.large、RDS db.t3.medium）が正しく計画されるか
- [ ] セキュリティグループのイングレス・エグレスが適切か
- [ ] VPC・サブネット・ルートテーブルが期待通りか
- [ ] NAT Gateway の設定が正しいか

---

#### Task 2-3-2: RDSバックアップ・リカバリテスト
**対象**: インフラ  
**チェックリスト**:
- [ ] RDSのスナップショット機能が有効化されているか
- [ ] 日次自動バックアップが設定されているか（7日保持）
- [ ] 別のRDSインスタンスへの復旧テストが成功するか
- [ ] 復旧後のデータ確認（行数・整合性）

---

#### Task 2-3-3: Entra ID テストユーザー12名の作成
**対象**: 管理者  
**チェックリスト**:
- [ ] PowerShell スクリプト `create-test-users.ps1` を実行
- [ ] 12名のテストユーザー（rep-001 ～ rep-012）が作成されたか
- [ ] 各ユーザーに仮パスワードを設定、初回ログイン時の変更を強制
- [ ] CSV レポートで認証情報を確認

**実行**:
```powershell
.\scripts\create-test-users.ps1 `
  -TenantId "YOUR_TENANT_ID" `
  -AppId "YOUR_APP_ID" `
  -AppSecret "YOUR_APP_SECRET" `
  -TenantDomain "company.onmicrosoft.com" `
  -UserCount 12
```

---

#### Task 2-3-4: 本番スケジュール・アラートルール事前設定
**対象**: システム管理者  
**チェックリスト**:
- [ ] 営業マンの営業時間（09:00-18:00）を設定
- [ ] 固定休憩時間（12:00-13:00）を設定
- [ ] 移動時間バッファ（30分）を設定
- [ ] Slackアラートルール（新規アポ・キャンセル・リマインダー）を設定
- [ ] テストで通知が正しく送信されるか確認

---

#### Task 2-3-5: 営業マン12名向けトレーニング資料・デモ
**対象**: 運用チーム  
**チェックリスト**:
- [ ] トレーニング資料（PDF）作成：アポ登録・編集・キャンセルの操作方法
- [ ] ビデオデモ作成：3分程度の画面操作ガイド
- [ ] Q&A FAQ 作成
- [ ] トレーニングセッション実施（2026-10-06）

---

### Block 4: 本番検証・リリース（10-08 ～ 10-10）

#### Task 2-4-1: 本番データベースへの最終マイグレーション
**対象**: インフラ  
**チェックリスト**:
- [ ] メンテナンスウィンドウ設定（2026-10-08 03:00-04:00 JST）
- [ ] APIサービス停止
- [ ] 本番RDSへのデータロード実行
- [ ] Entra IDロール同期実行

---

#### Task 2-4-2: 全統合テスト再実行（本番環境）
**対象**: QA  
**チェックリスト**:
- [ ] 本番環境の API に Block 2 のすべてのテストを再実行
- [ ] パフォーマンステスト（レスポンスタイム p99 < 200ms）
- [ ] 負荷テスト（100並行接続、安定稼働確認）

---

#### Task 2-4-3: 営業マン12名による UAT（ユーザー受入テスト）
**対象**: 営業・QA  
**チェックリスト**:
- [ ] 12名全員がシステムにログインできるか
- [ ] 過去のアポイントメント履歴が表示されるか
- [ ] 新規アポ登録・編集・キャンセルが実務で使える状態か
- [ ] Slack通知の内容が営業現場で役に立つか
- [ ] 「本番リリースOK」の判定を得る

---

#### Task 2-4-4: 本番デプロイ実行
**対象**: インフラ  
**チェックリスト**:
- [ ] GitHub Actions ワークフロー（production-deploy.yml）をトリガー
- [ ] 環境: `production`、dry_run: `false` で実行
- [ ] Terraform Apply が完了
- [ ] Docker イメージが本番環境にデプロイ
- [ ] ヘルスチェック通過（HTTP 200）

---

#### Task 2-4-5: 本番運用開始・ホットライン対応準備
**対象**: 運用・サポート  
**チェックリスト**:
- [ ] 運用マニュアル確認（トラブルシューティング）
- [ ] インシデント対応フロー確認
- [ ] ホットライン電話番号・Slack チャネル設定
- [ ] 24時間対応体制の準備（2026-10-10～10-12）

---

## 🧭 意思決定フロー

### ゲートウェイ確認と意思決定

**G1: API仕様確定**（2026-09-29）
```
判定内容: OpenAPI 3.0ドキュメントが完全か・実装可能か
責任者: PM・エンジニアリード
判定基準:
  ✓ 15エンドポイント全て記述完了
  ✓ エラーハンドリング明記
  ✓ テストシナリオ記述完了
判定結果:
  PASS → Task 2-1-3 マイグレーション開始
  FAIL → 修正・再検証（翌日）
```

**G2: データマイグレーション検証**（2026-09-30）
```
判定内容: テスト環境でのマイグレーションが成功したか
責任者: データ責任者・QA
判定基準:
  ✓ users 行数 = 12、appointments 行数 = 1847 (±5%)
  ✓ ステータス分布が合理的（COMPLETED 80-90%）
  ✓ API経由で過去データが取得できる
判定結果:
  PASS → Block 2 統合テスト開始
  FAIL → クリーニング再実施（2026-10-01へ遅延）
```

**G3: 統合テスト完了**（2026-10-03）
```
判定内容: 全統合テストケースが100% パスしたか
責任者: QA・PM
判定基準:
  ✓ API連携 (❶❂): 成功
  ✓ UI動作: 正常
  ✓ Slack通知: 送信確認
  ✓ パフォーマンス: p99 < 200ms
判定結果:
  PASS → Block 3 本番準備へ
  FAIL → バグ修正（2026-10-04-05へ遅延）
```

**G4: UAT合格**（2026-10-09）
```
判定内容: 営業マン12名が「実務で使える」と判定したか
責任者: 営業部長・システム管理者
判定基準:
  ✓ 全員がログイン・操作可能
  ✓ 過去データが正しく表示
  ✓ 新規アポ登録が簡単
  ✓ Slack通知が役に立つ
判定結果:
  PASS → 本番デプロイ実行
  FAIL → 修正・再UAT（2026-10-10へ遅延 → リリース延期）
```

**G5: 本番リリース**（2026-10-10）
```
判定内容: 全ゲート合格・インシデント対応準備完了か
責任者: 小柳さん（最終承認）
判定基準:
  ✓ G1～G4 全て PASS
  ✓ 本番データマイグレーション完了
  ✓ ホットライン対応体制構築
判定結果:
  PASS → 本番リリース実行
  FAIL → 即座に対応（小柳さんが判断）
```

---

## 📞 コミュニケーション・連絡体制

### 毎日 09:00 スタンドアップ（Slack #kakehashi-dev）

参加者: エンジニア・QA・インフラ・PM  
報告項目:
- ✅ 昨日完了したタスク
- 🔄 本日進行中のタスク
- 🚨 ブロッカー・懸念事項
- 📅 次アクション

### 毎週 月曜 15:00 進捗レビュー（Zoom）

参加者: PM・小柳さん・各チーム代表  
確認項目:
- 週次進捗（Block 1/2/3/4 の進捗率）
- リスク顕在化・対応状況
- ゲートウェイ判定予定
- 来週の重点タスク

### 🚨 緊急報告（即座）

条件: G1～G4 のゲートウェイが FAIL となった場合  
報告先: PM → 小柳さん  
内容: 失敗理由・修正方法・スケジュール影響度

---

## 📚 その他の参考資料

### 前フェーズのドキュメント
- `docs/kakehashi-poc/PHASE1-DEPLOYMENT-PLAN.md` - PoC本番化ガイド
- `docs/kakehashi-poc/SETUP-AWS.md` - AWS環境構築
- `docs/kakehashi-poc/SETUP-ENTRA-ID.md` - Entra ID設定
- `docs/kakehashi-poc/VERIFY-PRODUCTION.md` - 本番検証チェックリスト

### PoC実装コード
- `kakehashi-apo/` - 完全実装（Docker・Terraform構成）
- `scripts/` - 自動化スクリプト（bash・PowerShell）
- `.github/workflows/production-deploy.yml` - CI/CD パイプライン

### 事業参考資料
- CLAUDE.md - 本プロジェクト全体の方針・体制・進捗管理
- `docs/designs/kakehashi-integration-architecture.md` - 統合アーキテクチャ図
- `docs/superpowers/plans/2026-09-27-kakehashi-schedule-system-design.md` - 設計計画

---

## ✅ 最終チェックリスト（本番リリース前）

- [ ] Phase 2 のすべてのタスクが COMPLETED
- [ ] すべてのゲートウェイ（G1～G5）が PASS
- [ ] 営業マン12名が「本番利用OK」と署名
- [ ] インシデント対応マニュアル確認済み
- [ ] 監視・アラート設定確認済み
- [ ] バックアップ・リカバリテスト成功
- [ ] 本番リリース日時・手順が最終確定

---

## 🎓 次フェーズへの引き継ぎ

本番リリース成功後（2026-10-10以降）:

1. **本運用マニュアル整備**（10-12 ～ 10-15）
   - トラブルシューティング集約
   - 定期メンテナンス手順

2. **Phase 2 機能追加計画**（10-16以降）
   - 自動スケーリング設定
   - Multi-AZ 対応
   - 高度な分析・レポート機能

3. **他システム統合の拡張**（別セッションで進行）
   - ❷沖縄企業のミカタとの連携強化
   - ❸ゆんたくとの優先度指定
   - ❸保全CRMとの自動データ同期

---

**作成**: Claude (Haiku 4.5)  
**更新**: 2026-09-28  
**バージョン**: 1.0（本番リリース向け確定版）

