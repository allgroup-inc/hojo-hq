# 技術準備 C-4: Phase 1.5 統合テスト要件

**作成日**: 2026-10-17  
**対象**: 🌟管理システム チーム  
**目的**: Phase 1.5 統合テスト(①②③完了後の本実装テスト)の実施要件・成功定義の確認

---

## 📋 テスト対象

Phase 1.5 完全統合後の検証項目：

```
1. KAKEHASHI ↔ kanri_system UI の認証引き継ぎ
2. Entra ID SSO → kanri_system アクセス制御
3. call-log API データ送信 → 受取・保存・監査ログ確認
4. S1→S6 データフロー全体(入力〜集約〜DB保存〜UI表示)
```

---

## 🔧 前提条件（軸チーム確認待ち）

以下が確定するまでは、**テスト計画は保留**。本セクションの確認で初めて実施計画を立てられます：

```
C-4. Phase 1.5 統合テスト要件
  □ テスト環境（開発 / ステージング / 本番）
  □ テストデータ（ダミー / 実データ）
  □ テスト実行タイミングの制約（営業時間など）
  □ テスト成功の判定基準（何をもって「完了」とするか）
```

**現在**: ⏳ 軸チームからの統合テスト要件確認待機中

---

## 📊 テスト項目（計画フェーズ）

### テスト 1: KAKEHASHI → kanri_system 認証シーム

```javascript
// test/integration/kakehashi_auth_handoff.test.js

/**
 * KAKEHASHI Web ビューから kanri_system への認証情報引き継ぎテスト
 * ①②③ の回答により、実装方式が決まる（Web Cookie / postMessage / URL引き継ぎ など）
 * ここはテンプレート：実装方式確定後に具体化
 */

describe('KAKEHASHI ↔ kanri_system Auth Handoff', () => {
  
  test('User can access kanri_system after KAKEHASHI login', async () => {
    // 手順:
    // 1. KAKEHASHI でユーザーがログイン(Entra ID)
    // 2. admin.html → kanri_system へナビゲート
    // 3. kanri_system が user_id / roles を取得できることを確認
    // 期待結果: ✅ 権限に応じた画面表示
  });

  test('Unauthorized user gets 403 with clear error message', async () => {
    // 手順:
    // 1. 権限なしユーザーでアクセス
    // 期待結果: 🔴 403 ページ表示 + logout ボタン + KAKEHASHI へ戻るボタン
  });

  test('Session cookie / token expires correctly', async () => {
    // 手順:
    // 1. 認証情報を取得
    // 2. 有効期限を確認（例：1時間 / 8時間）
    // 3. 期限切れ後のアクセス時に再認証が求められること
    // 期待結果: セッション有効期限が仕様通り機能
  });
});
```

**実装待ち**: ①②③ 回答により、実装方式が確定したら具体化

---

### テスト 2: Entra ID SSO ↔ call-log API

```javascript
// test/integration/entra_id_call_log_flow.test.js

/**
 * Entra ID でのログイン → call-log API への ID・権限情報送信テスト
 */

describe('Entra ID ↔ call-log API Data Flow', () => {
  
  test('User ID from Entra ID token is sent to call-log API', async () => {
    // 手順:
    // 1. Entra ID でユーザーがログイン
    // 2. kanri_system 内でアクション実行（顧客カルテ表示など）
    // 3. call-log API が正確なユーザーID・タイムスタンプ・アクション種別を受け取ることを確認
    // 期待結果: call-log DB に正確に記録される
  });

  test('API call fails gracefully when auth token is invalid', async () => {
    // 手順:
    // 1. 不正なトークンでアクション実行
    // 2. API エラーが処理される（リトライ / キューイング など）
    // 期待結果: ユーザー画面には影響なし。ログに記録。
  });

  test('Offline call-log queue flushes when connection restored', async () => {
    // 手順:
    // 1. ネットワーク遮断の状態でアクション実行
    // 2. ローカル queue に保存される
    // 3. ネットワーク復旧時に自動flush
    // 期待結果: 遅延なく call-log API へ送信される
  });
});
```

**実装待ち**: C-2（call-log API仕様）受取後に具体化

---

### テスト 3: S1→S6 データフロー通貫テスト

```python
# test/integration/s1_s6_flow_e2e.py

"""
S1 日報 → S2-S5 中間システム → S6 DB → UI 表示 の全フロー
"""

import pytest

class TestS1S6EndToEndFlow:
    
    @pytest.fixture
    def s1_sample_batch(self):
        """S1 からの実データまたはダミーバッチ"""
        return {
            'batch_id': 'batch_20261017_001',
            'timestamp': '2026-10-17T15:00:00Z',
            'entries': [
                {
                    '日付': '2026-10-17',
                    '営業ID': 'empl_001',
                    '客先': '顧客A',
                    '訪問/通話時間': 120,
                    '案件': '新規提案',
                    '進捗': '打ち合わせ完了',
                    '次回予定': '2026-10-20'
                },
                # ... 追加エントリ
            ]
        }
    
    def test_s1_data_is_normalized_correctly(self, s1_sample_batch):
        # S1 入力形式 → S6 内部形式への変換が正確なことを確認
        adapter = S1InputAdapter(None)
        for entry in s1_sample_batch['entries']:
            normalized = adapter.normalize(entry)
            assert normalized['employee_id'] is not None
            assert normalized['customer_name'] is not None
            assert isinstance(normalized['call_duration'], int)
    
    def test_aggregation_and_enrichment_work(self, s1_sample_batch):
        # S2-S5 での集約・顧客マスタエンリッチメント
        adapter = S1InputAdapter(None)
        normalized = [adapter.normalize(e) for e in s1_sample_batch['entries']]
        aggregator = DataAggregator()
        aggregated = aggregator.aggregate_call_logs(normalized)
        enriched = aggregator.enrich_customer_data(aggregated)
        # 期待結果: 顧客マスタが参照され、既存/新規フラグが立つ
        for customer_name, data in enriched.items():
            assert 'customer_id' in data or 'is_new' in data
    
    def test_data_saved_to_s6_db(self, s1_sample_batch):
        # S6 DB への保存と query
        # 手順: データを save_call_log_batch() で保存 → query で取得
        # 期待結果:
        #   - 全件保存される
        #   - 日付・顧客・営業IDで query 可能
        #   - created_at / updated_at が自動設定される
        pass
    
    def test_ui_display_shows_saved_data(self):
        # kanri_system UI（顧客カルテ）に保存データが表示される
        # 手順:
        #   1. S1→S6 データ保存完了
        #   2. kanri_system UI で該当顧客を開く
        #   3. 最新の call_log / 集約データが表示される
        # 期待結果: UI に S6 DB のデータが即座に反映
        pass
    
    def test_idempotent_handling_duplicate_batch(self):
        # 同じ batch_id で2回送信された場合の処理
        # 手順: 同じ S1 バッチを2回処理
        # 期待結果: 重複レコードが作られず、audit_log に「重複」と記録される
        pass
    
    def test_partial_failure_and_audit_log(self):
        # 5件中3件成功・2件失敗のケース
        # 期待結果:
        #   - 成功分は DB に保存
        #   - 失敗分は audit_log に失敗理由を記録
        #   - UI に「⚠️ 2件処理に失敗」など通知表示
        pass
```

**実装待ち**: C-3（S1→S6フロー全体図・仕様）受取後に具体化

---

### テスト 4: エラーハンドリング・監査ログ検証

```python
# test/integration/error_handling_and_audit.test.js

describe('Error Handling & Audit Log', () => {
  
  test('Network error on API call is retried and logged', () => {
    // Timeout / 503 エラーが適切に retry される
    // audit_log に「retry_attempt: 1/2/3」が記録される
  });

  test('Data validation error is clearly reported', () => {
    // 必須フィールド欠損 / 形式エラーが検出され、
    // ユーザーへ「⚠️ 顧客名が入力されていません」など具体的なメッセージ表示
  });

  test('Audit log contains full traceability', () => {
    // audit_log が以下を記録:
    //   - batch_id / 処理日時
    //   - 入力レコード数 / 成功数 / 失敗数
    //   - 失敗レコードの ID と失敗理由
    // → 後で「あの顧客のデータが入っていない」と質問が来たときに、
    //   audit_log から原因を追跡可能
  });
});
```

---

## 🎯 テスト環境構築（軸チーム確認必須）

### Phase A: ローカル開発環境（現在）
```
✅ C-1/C-2/C-3 の Mock 実装で単体テスト実施可能
✅ 統合テストはまだ「テンプレート段階」（実装方式待ち）
```

### Phase B: ステージング環境（①②③確定後 + C-1/C-2/C-3受取後）
```
⏳ Entra ID SSO を軸チームのステージング AD に接続
⏳ call-log API を軸チームのステージング endpoint に接続
⏳ S1 のダミーデータセットで全フロー試験
⏳ エラーハンドリング・リトライ・監査ログ確認
```

### Phase C: 本番環境（テスト完全合格後）
```
⏳ 実 Entra ID 環境での統合テスト
⏳ 実 S1 データ（または実フォーマット・期間限定テスト）での検証
⏳ 本番デプロイ可否の判定
```

---

## 🎯 テスト成功の定義（軸チーム判定）

以下の確認をお願いします：

```
□ テスト実施環境:
  □ 開発環境のみで十分か
  □ ステージング環境でのテストが必須か
  □ 本番環境での実施テストが必須か

□ テストデータ:
  □ ダミーデータ(製造側で作成可能な仮データ)で大丈夫か
  □ 実データ(実際の S1 日報など)での検証が必須か
  □ 本番運用前の期間限定で実データテストすべきか

□ テスト実行のタイミング・制約:
  □ 営業時間内でOKか / 営業時間外のみか
  □ 特定の営業日に限定すべきか（例：月曜のみ など）
  □ テスト実施期間は？（1週間 / 2週間 など）

□ 「統合完了」の定義:
  以下のいずれをもって「合格」とするか？
  
  □ 全テストケースが PASS（テンプレート C-1/C-2/C-3 のテストが全て green）
  □ ユーザー受け入れテスト(UAT)で軸チームが承認
  □ 本番環境での 1 週間の安定稼働確認
  □ 監査ログレビュー（エラー / 重複 / 欠損が 0 件）
  □ その他: ___________
```

---

## 📝 実装進捗チェックリスト

| タスク | 状態 | 責任 | 期限 |
|---|---|---|---|
| テスト環境の構成決定 | ⏳ 待機 | 軸チーム | 2026-10-20 |
| テストデータセットの準備 | ⏳ 待機 | 軸チーム | 2026-10-22 |
| テスト実行スケジュール確定 | ⏳ 待機 | 軸チーム | 2026-10-20 |
| テスト成功判定基準の確定 | ⏳ 待機 | 軸チーム | 2026-10-20 |
| 統合テスト実施（ステージング） | ⏳ ブロック中 | 両チーム | 2026-10-27 |
| 本番環境での最終テスト | ⏳ ブロック中 | 両チーム | 2026-11-03 |

---

## 🔗 関連ドキュメント

| ドキュメント | 参照元 | 用途 |
|---|---|---|
| `docs/技術準備_C1_EntraID_SSO統合テスト計画.md` | 本テストのサブモジュール | SSO 認証テストの詳細 |
| `docs/技術準備_C2_CallLog_API統合テスト計画.md` | 本テストのサブモジュール | call-log API テストの詳細 |
| `docs/技術準備_C3_S1S6フロー全体通貫テスト計画.md` | 本テストのサブモジュール | データフロー通貫テストの詳細 |
| `docs/連携メモ_20261017_軸宛_統合依頼リスト_Phase1.5Phase2.md` | 軸チーム依頼 | C-4 の確認項目リスト |

---

_作成: 2026-10-17 / Claude Code（🌟管理システムチャット）_
