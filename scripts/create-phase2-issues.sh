#!/bin/bash
# Phase 2 GitHub Issues 自動生成スクリプト
# 使用法: bash scripts/create-phase2-issues.sh

set -e

REPO="allgroup-inc/hojo-hq"
MILESTONE="Phase 2 (09-29 ~ 10-10)"

# Issue データベース
declare -A ISSUES=(
  # Block 1: API・マイグレーション確定
  ["1"]="Block 1|2-1-1: API仕様書最終化|API仕様書 (docs/kakehashi-poc/API-SPECIFICATION.md) の15個のエンドポイント・スキーマが実装可能か確認し、最終化。\n\n**チェックリスト**:\n- [ ] 全15エンドポイント実装可能性の確認\n- [ ] エラーハンドリング実装方針決定\n- [ ] レート制限実装方法決定\n- [ ] JWT署名・検証方法確定\n- [ ] Postman Collection テンプレート作成\n\n**期限**: 2026-09-29|phase-2,block-1,api,critical|"
  ["2"]="Block 1|2-1-2: GASデータ抽出|既存GASシートから営業マンデータ (12行) と過去アポ記録 (1,847件) をJSON形式で抽出。\n\n**チェックリスト**:\n- [ ] Google Sheets API で users シート抽出\n- [ ] appointments シート (3年分) をJSON出力\n- [ ] 敏感情報フィルタリング確認\n- [ ] S3に一時保存\n\n**期限**: 2026-09-29|phase-2,block-1,data,migration|"
  ["3"]="Block 1|2-1-3: マイグレーションスクリプト作成|GAS JSONデータをPostgreSQL RDSへ移行するスクリプト実装。営業マンIDマッピング・データクリーニング・バリデーション機能を含む。\n\n**チェックリスト**:\n- [ ] scripts/migration/transform_gas_to_csv.py 実装\n- [ ] 営業マンID マッピングテーブル作成\n- [ ] CSVクリーニングロジック実装\n- [ ] scripts/migration/validate_migration_data.py 実装\n- [ ] テスト環境で試験実行\n\n**期限**: 2026-09-30\n**ブロッカー**: Issue #1 (API仕様確定)|phase-2,block-1,data,migration|Issue #1"
  ["4"]="Block 1|2-1-4: テスト環境でマイグレーション検証|テスト用RDSでマイグレーション実行し、データ品質・正確性・行数を検証。\n\n**チェックリスト**:\n- [ ] テスト用RDS接続確認\n- [ ] マイグレーション実行\n- [ ] 行数確認: users=12、appointments=1,847 (±5%)\n- [ ] ステータス分布が合理的か確認\n- [ ] API経由で過去データが取得できるか確認\n\n**期限**: 2026-09-30\n**ブロッカー**: Issue #3 (マイグレーションスクリプト)|phase-2,block-1,data,qa|Issue #3"

  # Block 2: 統合テスト実施
  ["5"]="Block 2|2-2-1: kakei-apo への本システム組み込み|PoC実装をkakei-apo リポジトリへ移設・統合。既存認証・環境に合わせる。\n\n**チェックリスト**:\n- [ ] kakei-apo リポジトリセットアップ\n- [ ] PoC実装を移設\n- [ ] 既存認証方式に調整\n- [ ] 環境変数統合\n- [ ] Dockerイメージ再ビルド・起動テスト\n\n**期限**: 2026-10-01\n**ブロッカー**: Issue #4 (マイグレーション検証)|phase-2,block-2,integration|Issue #4"
  ["6"]="Block 2|2-2-2: ❶入口システム連携テスト|営業受付システム (❶入口) と本APO管理システムの連携テスト。新規アポ登録・振り分け・通知の統合動作確認。\n\n**チェックリスト**:\n- [ ] POST /api/v1/appointments で新規登録\n- [ ] レスポンス201 Created + APO-ID返却確認\n- [ ] ラウンドロビン振り分け動作確認\n- [ ] Slack通知送信確認\n- [ ] エラーケースのハンドリング確認\n\n**期限**: 2026-10-02\n**ブロッカー**: Issue #5 (kakei-apo組み込み)|phase-2,block-2,integration,qa|Issue #5"
  ["7"]="Block 2|2-2-3: ❂訪問管理・❸保全CRM連携テスト|営業訪問管理システム (❂) と保全CRM (❸) の双方向連携テスト。訪問完了・結果入力の統合動作確認。\n\n**チェックリスト**:\n- [ ] POST /api/visits/completed で訪問完了通知受信\n- [ ] KPI自動集計トリガー確認\n- [ ] 保全CRM への結果同期確認\n- [ ] 失敗時のロールバック手順確認\n\n**期限**: 2026-10-02\n**ブロッカー**: Issue #5 (kakei-apo組み込み)|phase-2,block-2,integration,qa|Issue #5"
  ["8"]="Block 2|2-2-4: UI統合テスト|フロントエンド (React + Material-UI) の確認。カレンダー表示・ドラッグ操作・アポ詳細確認・Slack連携の実装確認。\n\n**チェックリスト**:\n- [ ] 月表示・週表示・日表示レンダリング確認\n- [ ] ドラッグ&ドロップ操作確認\n- [ ] アポ詳細モーダル表示確認\n- [ ] 営業マン検索・フィルタリング動作確認\n- [ ] レスポンシブデザイン (モバイル/タブレット) 確認\n\n**期限**: 2026-10-03\n**ブロッカー**: Issue #5 (kakei-apo組み込み)|phase-2,block-2,ui,qa|Issue #5"
  ["9"]="Block 2|2-2-5: Gateway G1検証 (Block 1の成果物品質)|Block 1の4つのタスクが完了し、以下の基準を満たしているか判定:\n\n**判定基準** (Pass必須):\n- [ ] API-SPECIFICATION.md が全15エンドポイントを網羅\n- [ ] マイグレーション検証でデータ行数 users=12/appointments≈1,847\n- [ ] テスト環境でAPI経由データ取得が成功\n- [ ] ブロッカーIssue (1,2,3,4) すべてCloseされている\n\n**判定責任**: PM/アーキテクト\n**期限**: 2026-09-30 23:59\n**ブロッカー**: Issue #1,#2,#3,#4 (すべてCloseされていることが前提)|phase-2,gateway,qa,critical|Issue #1,#2,#3,#4"

  # Block 3: 本番環境準備
  ["10"]="Block 3|2-3-1: 本番環境インフラ準備|AWS/Terraform による本番RDS・EC2・セキュリティグループの構築。シークレット管理 (GitHub Secrets) の設定。\n\n**チェックリスト**:\n- [ ] Terraform apply で本番RDS (PostgreSQL 15) 構築\n- [ ] EC2 t3.large インスタンス起動\n- [ ] セキュリティグループ設定 (3306ポート許可等)\n- [ ] CloudWatch ログ設定\n- [ ] GitHub Secrets に DEPLOY_KEY・RDS_PASSWORD登録\n\n**期限**: 2026-10-04\n**ブロッカー**: Issue #9 (Gateway G1)|phase-2,block-3,infra,critical|Issue #9"
  ["11"]="Block 3|2-3-2: Entra IDテストユーザー・本番ユーザー作成|Azure Entra ID に営業マン12人 + Admin + テストユーザーを登録。OAuthトークン発行テスト実施。\n\n**チェックリスト**:\n- [ ] Entra ID に12営業マン登録 (email: user-001@〜user-012@\n- [ ] Admin アカウント作成\n- [ ] テストユーザー (3名) 作成\n- [ ] JWT トークン発行テスト\n- [ ] トークン署名・検証テスト (RS256)\n\n**期限**: 2026-10-05\n**ブロッカー**: Issue #10 (本番インフラ)|phase-2,block-3,infra|Issue #10"
  ["12"]="Block 3|2-3-3: トレーニング・運用マニュアル準備|営業マン12人向けトレーニング資料 (動画/PDF)・運用マニュアル・FAQ作成。\n\n**チェックリスト**:\n- [ ] トレーニング動画 (基本操作 / カレンダー / ドラッグ操作)\n- [ ] PDF クイックスタートガイド作成\n- [ ] FAQ (よくある質問と回答)\n- [ ] Slack ウェルカムメッセージ・ピン付け情報作成\n- [ ] 日本語UI文面の最終校正\n\n**期限**: 2026-10-06\n**ブロッカー**: Issue #9 (Gateway G1)|phase-2,block-3,ops|Issue #9"

  # Block 4: 本番デプロイ・運用開始
  ["13"]="Block 4|2-4-1: 本番RDSデータマイグレーション|テスト環境で検証済みのマイグレーション実行スクリプトを本番RDSで実行。ロールバック手順の確認。\n\n**チェックリスト**:\n- [ ] バックアップ作成確認\n- [ ] マイグレーション実行 (users 12行 + appointments 1,847行)\n- [ ] データ行数・整合性確認\n- [ ] API経由データ取得テスト\n- [ ] ロールバック手順テスト\n\n**期限**: 2026-10-08 AM\n**ブロッカー**: Issue #10,#11 (インフラ・ユーザー準備)|phase-2,block-4,data,migration,critical|Issue #10,#11"
  ["14"]="Block 4|2-4-2: 全統合テスト・本番UAT|本番環境でEnd-to-End統合テスト実施。営業マン・APO担当・システム管理者による本番環境確認。\n\n**チェックリスト**:\n- [ ] 本番RDSでAPI全15エンドポイント動作確認\n- [ ] 本番Entra IDトークン発行・検証確認\n- [ ] UI操作 (カレンダー・ドラッグ・登録) 確認\n- [ ] ❶❂❸連携の本番データで統合テスト\n- [ ] パフォーマンステスト (同時接続10人)\n- [ ] UAT参加者のサインオフ取得\n\n**期限**: 2026-10-09\n**ブロッカー**: Issue #13 (本番RDSマイグレ)|phase-2,block-4,qa,critical|Issue #13"
  ["15"]="Block 4|2-4-3: Gateway G5最終判定 (本番リリース可否)|本番環境のテスト・UATが完了し、本番リリースが安全か最終判定。不合格時は改善リストアップ。\n\n**判定基準** (Pass必須):\n- [ ] 統合テスト合格 (全15エンドポイント ✓)\n- [ ] UAT参加者 (営業マン/APO/管理者) サインオフ取得\n- [ ] パフォーマンス基準達成 (同時接続10人で平均応答時間 <2s)\n- [ ] セキュリティチェック完了 (OWASP Top 10)\n- [ ] ロールバック手順テスト成功\n\n**判定責任**: CTO/プロダクトリーダー\n**期限**: 2026-10-09 16:00\n**ブロッカー**: Issue #14 (統合テスト・UAT)|phase-2,gateway,qa,critical|Issue #14"
  ["16"]="Block 4|2-4-4: 本番デプロイ・運用開始|GitHub Actions による本番デプロイ実行。営業マン12人・APO担当者の利用開始。障害対応体制の起動。\n\n**チェックリスト**:\n- [ ] CI/CDパイプライン実行 (test → docker build → terraform apply → verify)\n- [ ] Blue-Green デプロイメント実施 (ダウンタイム0)\n- [ ] 営業マンへの利用開始通知\n- [ ] Slack #apo-support チャネル開設・運用チーム追加\n- [ ] 障害対応ホットライン (連絡先) 案内\n- [ ] 初日サポート体制起動 (09:00-18:00)\n\n**期限**: 2026-10-10 09:00\n**ブロッカー**: Issue #15 (G5最終判定Pass)|phase-2,block-4,infra,deployment,critical|Issue #15"
)

echo "🚀 Phase 2 GitHub Issues 自動生成開始"
echo "対象リポジトリ: $REPO"
echo "マイルストーン: $MILESTONE"
echo ""

# Issue作成関数
create_issue() {
  local num=$1
  local data=$2

  IFS='|' read -r block title description labels blockers <<< "$data"

  # ブロッカー処理
  local body="$description"
  if [ -n "$blockers" ]; then
    body="$body\n\n**ブロッカー**: $blockers"
  fi

  echo "📌 Issue #$num: $title"

  # gh CLI で Issue 作成
  gh issue create \
    --repo "$REPO" \
    --title "[$block] $title" \
    --body "$(echo -e "$body")" \
    --label "$labels" \
    --milestone "$MILESTONE" \
    --assignee "@me" \
    2>/dev/null || echo "⚠️  Issue #$num 作成スキップ (既存または権限エラー)"

  echo ""
}

# Issue作成実行
for issue_num in {1..16}; do
  if [ -n "${ISSUES[$issue_num]}" ]; then
    create_issue "$issue_num" "${ISSUES[$issue_num]}"
  fi
done

echo "✅ GitHub Issues 生成完了"
echo ""
echo "📊 進捗確認: gh issue list --repo $REPO --milestone '$MILESTONE'"
