# GitHub Issues 管理チェックリスト
> **Phase 2 実装タスク・ゲートウェイ判定を Issues で追跡**

**作成日**: 2026-09-28  
**用途**: GitHub Projects で進捗管理・可視化  
**マイルストーン**: Phase 2 (09-29 ～ 10-10)

---

## 📋 自動登録推奨 Issues 一覧（16件）

### Block 1: API・マイグレーション確定（4件）

#### Issue 1: [Block 1] 2-1-1: API仕様書最終化
- **対象**: エンジニア・PM
- **期限**: 2026-09-29
- **ラベル**: phase-2, block-1, api, critical
- **チェックリスト**:
  - [ ] API-SPECIFICATION.md のエンドポイント15個が全て実装可能か確認
  - [ ] エラーハンドリングコード実装方針確認
  - [ ] レート制限実装方法決定
  - [ ] JWTの署名・検証方法確定
  - [ ] Postman Collection テンプレート作成
- **ブロッカー**: —
- **前提**: —

---

#### Issue 2: [Block 1] 2-1-2: GASデータ抽出
- **対象**: データチーム
- **期限**: 2026-09-29
- **ラベル**: phase-2, block-1, data, migration
- **チェックリスト**:
  - [ ] Google Sheets API で users シートをJSON出力
  - [ ] appointments シート（過去3年分）をJSON出力
  - [ ] 敏感情報が含まれていないか確認
  - [ ] S3に一時保存
- **ブロッカー**: —
- **前提**: —

---

#### Issue 3: [Block 1] 2-1-3: マイグレーションスクリプト作成
- **対象**: エンジニア
- **期限**: 2026-09-30
- **ラベル**: phase-2, block-1, data, migration
- **チェックリスト**:
  - [ ] scripts/migration/transform_gas_to_csv.py を実装
  - [ ] 営業マンID マッピングテーブル作成
  - [ ] CSVクリーニングロジック実装
  - [ ] scripts/migration/validate_migration_data.py を実装
  - [ ] テスト環境で試験実行
- **ブロッカー**: Issue 1 (API仕様確定)
- **前提**: Issue 2 (GASデータ抽出)

---

#### Issue 4: [Block 1] 2-1-4: テスト環境でマイグレーション検証
- **対象**: QA
- **期限**: 2026-09-30
- **ラベル**: phase-2, block-1, data, qa
- **チェックリスト**:
  - [ ] テスト用RDS接続確認
  - [ ] マイグレーション実行
  - [ ] 行数確認：users = 12、appointments = 1847 (±5%)
  - [ ] ステータス分布が合理的か確認
  - [ ] API で過去データが取得できるか確認
- **ブロッカー**: Issue 3 (マイグレーションスクリプト)
- **前提**: —

---

### Block 2: 統合テスト実施（5件）

#### Issue 5: [Block 2] 2-2-1: kakei-apo への本システム組み込み
- **対象**: エンジニア
- **期限**: 2026-10-01
- **ラベル**: phase-2, block-2, integration
- **チェックリスト**:
  - [ ] kakei-apo リポジトリセットアップ
  - [ ] PoC実装を kakei-apo へ移設
  - [ ] 既存認証方式に合わせて調整
  - [ ] 環境変数を kakei-apo 配下に統合
  - [ ] Docker イメージ再ビルド・起動テスト
- **ブロッカー**: Issue 4 (マイグレーション検証完了)
- **前提**: —

---

#### Issue 6: [Block 2] 2-2-2: ❶入口システム連携テスト
- **対象**: QA
- **期限**: 2026-10-02
- **ラベル**: phase-2, block-2, integration, qa
- **テストシナリオ**:
  - [ ] POST /api/v1/appointments で新規アポ登録
  - [ ] レスポンス201 Created + APO-XXXが返される
  - [ ] 営業マンへのラウンドロビン振り分け動作確認
  - [ ] Slack通知が送信される
- **ブロッカー**: Issue 5 (kakei-apo組み込み)
- **前提**: —

---

#### Issue 7: [Block 2] 2-2-3: ❂訪問管理システム連携テスト
- **対象**: QA
- **期限**: 2026-10-02
- **ラベル**: phase-2, block-2, integration, qa
- **テストシナリオ**:
  - [ ] アポ完了時 POST /api/v1/visits/completed が ❂へ送信
  - [ ] キャンセル時 POST /api/v1/visits/cancelled が ❂へ送信
  - [ ] ❂システムが通知を受け取り処理進行
- **ブロッカー**: Issue 5 (kakei-apo組み込み)
- **前提**: —

---

#### Issue 8: [Block 2] 2-2-4: ❸保全CRM連携テスト
- **対象**: QA
- **期限**: 2026-10-03
- **ラベル**: phase-2, block-2, integration, qa
- **テストシナリオ**:
  - [ ] KPIレポート GET /kpi/daily-summary が正常取得
  - [ ] ❸側が本システムのKPI データを参照可能
  - [ ] データ形式・フィールド名が ❸で期待される形式か確認
- **ブロッカー**: Issue 5 (kakei-apo組み込み)
- **前提**: —

---

#### Issue 9: [Block 2] 2-2-5: Slack通知・UI動作統合テスト
- **対象**: QA
- **期限**: 2026-10-03
- **ラベル**: phase-2, block-2, qa, ui
- **テストシナリオ**:
  - [ ] 新規アポ登録時 Slack通知送信確認
  - [ ] UI 日ビュー・週ビュー・月ビュー動作確認
  - [ ] ドラッグ&ドロップでアポ移動可能
  - [ ] スマートフォン（レスポンシブ）表示確認
  - [ ] リアルタイム更新（複数営業同時アクセス）確認
- **ブロッカー**: Issue 5 (kakei-apo組み込み)
- **前提**: —

---

### ゲートウェイ: 判定タイムポイント（5件）

#### Issue 10: [ゲートウェイ] G1: API仕様確定
- **判定日**: 2026-09-29
- **責任者**: PM・エンジニアリード
- **ラベル**: phase-2, gateway, critical
- **判定基準**:
  - [ ] 15エンドポイント全て記述完了
  - [ ] エラーハンドリング明記
  - [ ] テストシナリオ記述完了
- **判定結果**:
  - PASS → Task 2-1-3 マイグレーション開始
  - FAIL → 修正・再検証（翌日）
- **前提**: Issue 1 (API仕様書最終化)

---

#### Issue 11: [ゲートウェイ] G2: データマイグレーション検証
- **判定日**: 2026-09-30
- **責任者**: データ責任者・QA
- **ラベル**: phase-2, gateway, critical
- **判定基準**:
  - [ ] users 行数 = 12、appointments 行数 = 1847 (±5%)
  - [ ] ステータス分布が合理的（COMPLETED 80-90%）
  - [ ] API経由で過去データが取得できる
- **判定結果**:
  - PASS → Block 2 統合テスト開始
  - FAIL → クリーニング再実施
- **前提**: Issue 4 (テスト環境検証)

---

#### Issue 12: [ゲートウェイ] G3: 統合テスト完了
- **判定日**: 2026-10-03
- **責任者**: QA・PM
- **ラベル**: phase-2, gateway, critical
- **判定基準**:
  - [ ] API連携 (❶❂): 成功
  - [ ] UI動作: 正常
  - [ ] Slack通知: 送信確認
  - [ ] パフォーマンス: p99 < 200ms
- **判定結果**:
  - PASS → Block 3 本番準備へ
  - FAIL → バグ修正
- **前提**: Issue 6, 7, 8, 9 (全Block 2テスト)

---

#### Issue 13: [ゲートウェイ] G4: UAT合格
- **判定日**: 2026-10-09
- **責任者**: 営業部長・システム管理者
- **ラベル**: phase-2, gateway, critical
- **判定基準**:
  - [ ] 全員がログイン・操作可能
  - [ ] 過去データが正しく表示
  - [ ] 新規アポ登録が簡単
  - [ ] Slack通知が役に立つ
- **判定結果**:
  - PASS → 本番デプロイ実行
  - FAIL → 修正・再UAT（10-10へ遅延）
- **前提**: Block 3 本番準備・トレーニング

---

#### Issue 14: [ゲートウェイ] G5: 本番リリース承認
- **判定日**: 2026-10-10
- **責任者**: 小柳さん（最終承認）
- **ラベル**: phase-2, gateway, critical
- **判定基準**:
  - [ ] G1～G4 全て PASS
  - [ ] 本番データマイグレーション完了
  - [ ] ホットライン対応体制構築
- **判定結果**:
  - PASS → 本番リリース実行
  - FAIL → 即座に対応
- **前提**: Issue 13 (G4 UAT合格)

---

### Block 3・4: 本番準備・リリース（2件）

#### Issue 15: [Block 3] 本番環境準備・テストユーザー・トレーニング
- **対象**: インフラ・管理者・運用チーム
- **期限**: 2026-10-07
- **ラベル**: phase-2, block-3, infra
- **チェックリスト**:
  - [ ] Terraform本番環境構成確認（Task 2-3-1）
  - [ ] RDS バックアップ・リカバリテスト（Task 2-3-2）
  - [ ] Entra ID テストユーザー12名作成（Task 2-3-3）
  - [ ] 本番スケジュール・アラートルール設定（Task 2-3-4）
  - [ ] 営業マン12名向けトレーニング資料・デモ作成（Task 2-3-5）
- **ブロッカー**: Issue 12 (G3 統合テスト完了)
- **前提**: —

---

#### Issue 16: [Block 4] 本番データマイグレーション・UAT・デプロイ
- **対象**: インフラ・QA・営業・運用チーム
- **期限**: 2026-10-10
- **ラベル**: phase-2, block-4, critical
- **チェックリスト**:
  - [ ] 本番RDSへの最終マイグレーション（2026-10-08）（Task 2-4-1）
  - [ ] 本番環境で全統合テスト再実行（Task 2-4-2）
  - [ ] 営業マン12名によるUAT実施（2026-10-09）（Task 2-4-3）
  - [ ] 本番デプロイ実行（GitHub Actions）（Task 2-4-4）
  - [ ] 本番運用開始・ホットライン対応（Task 2-4-5）
- **ブロッカー**: Issue 13 (G4 UAT合格), Issue 15 (本番環境準備)
- **前提**: —

---

## 📊 Issues 依存グラフ

```
2026-09-29
  Issue 1 (API確定)
  Issue 2 (GAS抽出)
    ↓
  Issue 10 (G1判定) ← Issue 1 前提
    ↓
  Issue 3 (マイグレ実装) ← Issue 10 PASS
  Issue 4 (マイグレ検証) ← Issue 3 完了
    ↓
  Issue 11 (G2判定) ← Issue 4 前提

2026-10-01
  Issue 5 (kakei-apo組み込み) ← Issue 11 PASS
    ↓
  Issue 6 (❶連携テスト) ← Issue 5 前提
  Issue 7 (❂連携テスト) ← Issue 5 前提
  Issue 8 (❸連携テスト) ← Issue 5 前提
  Issue 9 (UI統合テスト) ← Issue 5 前提
    ↓
  Issue 12 (G3判定) ← Issue 6,7,8,9 前提

2026-10-04
  Issue 15 (本番準備) ← Issue 12 PASS
    ↓
  Issue 16 (本番マイグレ・デプロイ) ← Issue 15 完了

2026-10-09
  Issue 13 (G4判定) ← Issue 16 UAT前提
    ↓
  Issue 14 (G5承認) ← Issue 13 PASS
    ↓
  🚀 本番リリース (2026-10-10)
```

---

## 🔗 GitHub Projects 設定推奨

### ボード構成

```
To Do (未開始)
  - Issue 1, 2, 3, ...

In Progress (進行中)
  - 現在実行中のIssue

Review (レビュー中)
  - テスト中・判定待ちのIssue

Done (完了)
  - 完了したIssue
```

### ラベル設定

- `phase-2`: Phase 2 統合実装
- `block-1`, `block-2`, `block-3`, `block-4`: ブロック分類
- `gateway`: ゲートウェイ判定
- `critical`: 最優先タスク
- `api`, `data`, `migration`, `integration`, `qa`, `infra`, `ui`: 領域分類

### マイルストーン

- `Phase 2 (09-29 ~ 10-10)`: 全Issue共通

---

## 📝 Issue 作成手順（GitHub CLI or Web UI）

### GitHub CLI を使用する場合

```bash
# Issue作成の例（1件）
gh issue create \
  --title "[Block 1] 2-1-1: API仕様書最終化" \
  --body "対象: エンジニア・PM\n期限: 2026-09-29\n\n## チェックリスト\n- [ ] API仕様..." \
  --label "phase-2,block-1,api,critical" \
  --milestone "Phase 2 (09-29 ~ 10-10)" \
  --repo allgroup-inc/hojo-hq
```

### GitHub Web UI を使用する場合

1. https://github.com/allgroup-inc/hojo-hq/issues → New Issue
2. 上記のIssue情報を入力
3. Labels: phase-2, block-X, ...を選択
4. Milestone: "Phase 2 (09-29 ~ 10-10)" を選択
5. Create Issue

---

## 📞 Issues コメント・コミュニケーション

### Issue での報告フォーマット

進捗報告時:
```
## 本日の進捗
- [x] XXX完了
- [ ] YYY実施中
- [ ] ZZZ明日開始予定

## ブロッカー
なし / あり（詳細：...）

## 次のステップ
...
```

---

## ✅ 日別 Issue 進捗追跡

| 日付 | Focus Issues | ゲートウェイ | 期待結果 |
|---|---|---|---|
| 09-29 | 1, 2, 10 | G1判定 | API確定 |
| 09-30 | 3, 4, 11 | G2判定 | マイグレ確定 |
| 10-01~03 | 5, 6, 7, 8, 9, 12 | G3判定 | 統合テスト完了 |
| 10-04~07 | 15 | — | 本番準備 |
| 10-08~09 | 16 | G4判定 | UAT合格 |
| 10-10 | 14 | G5判定 | 本番リリース |

---

**このドキュメントを参考に、GitHub Issues を作成・管理してください。**  
**進捗は毎日 09:00 スタンドアップで報告。ゲートウェイ判定で承認前進。**

