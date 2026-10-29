# Phase E 仕様: High-Performance KAKEHASHI with Enterprise-Grade Security
**Azure Key Vault 統合・スケール・監査ログ外部送信・マルチチャット統一設計**

---

## Executive Summary

**目標**: LocalKekProvider(テスト用) から Azure Key Vault(本番) への移行を軸に、Salesforce / BlueBean相当のエンタープライズセキュリティレベルで、5つの並行開発チャットが統一された実装スタイル・CI/CDゲート・監査機構を共有する KAKEHASHI システムを構築する。

**期限**: 2026-12-17  
**体制**: 5チャット並行開発 + 三名体制議事化 + 小柳さん決裁  
**デリバリー**: 
- ④ コア・ラッパーライブラリ（Key Vault接続・エラーハンドリング・中央監査ログ）
- ⑤ 実装スタイルガイド（5チャット共通）
- ⑥ CI/CDゲート仕様（セキュリティチェック + 監査ログ形式検証）
- ⑦ マルチチャット統合ドキュメント
- ⑧ セキュリティコンプライアンス・モニタリング・インシデント対応手順

---

## 1. セキュリティ要件（Enterprise-Grade Level）

### 1.1 準拠基準
- **SOC 2 Type II パス**: アクセス制御・監査ログ・暗号化の3層
- **ISO 27001**: 情報セキュリティ管理体系
- **参考実装**: Salesforce Shield / Azure Enterprise Security / BlueBean Encryption Layer

### 1.2 暗号化戦略
```
┌─────────────────────────────────────┐
│ クライアント (各チャット)            │
│   ↓ TLS 1.2+ (in transit)          │
├─────────────────────────────────────┤
│ コア・ラッパーライブラリ             │
│   ↓ Azure Key Vault (KMS)          │
├─────────────────────────────────────┤
│ データベース / Storage               │
│   ↓ AES-256-GCM (at rest)          │
└─────────────────────────────────────┘
```

**実装**:
- **In Transit**: TLS 1.2以上必須、証明書ピンニング（本番）
- **At Rest**: Application-level 暗号化（Key Vaultキーを使用）
  - PII（顧客氏名・連絡先・契約番情報）は DB保存時に暗号化
  - 暗号化キー: Key Vault から動的フェッチ
  - IV (Initialization Vector): 値ごとにランダム生成
- **Key Vault**: Azure Managed Identity 経由でアクセス（シークレット公開禁止）

### 1.3 アクセス制御（RBAC）
```
┌────────────────────────────────────┐
│ Role          │ Permissions        │
├────────────────────────────────────┤
│ admin         │ Full access        │
│               │ Key rotation       │
│               │ User mgmt          │
│               │ Audit log export   │
├────────────────────────────────────┤
│ operator      │ Read/write data    │
│               │ View own logs      │
│               │ Execute workflows  │
├────────────────────────────────────┤
│ auditor       │ Read-only          │
│               │ Audit log access   │
│               │ No data write      │
├────────────────────────────────────┤
│ guest         │ Limited read       │
│               │ No sensitive data  │
└────────────────────────────────────┘
```

**実装方法**:
- Azure AD / Managed Identity でロール割り当て
- 各 API エンドポイントで `@RequireRole("admin")` デコレータ
- ログイン時に JWT トークン + ロール情報を発行
- トークン有効期限: 1時間（短期） + Refresh Token（24時間）

### 1.4 監査ログ（Immutable / Append-Only）

**ログフロー**:
```
各チャット → コア・ラッパー → 監査ログ中央集約 → Azure Blob Storage (append-only)
                            ↓
                     監査ログ DB (read-only)
                            ↓
                     外部SIEM / 監査ツールへ送信
```

**記録内容** (JSON schema):
```json
{
  "timestamp": "2026-10-29T15:30:45.123Z",
  "event_id": "evt_a1b2c3d4",
  "event_type": "KEY_ACCESS|SECRET_DECRYPT|KEY_ROTATE|USER_LOGIN|DATA_EXPORT|COMPLIANCE_CHECK",
  "actor": {
    "user_id": "user_abc123",
    "role": "operator",
    "chat_id": "chat_001"
  },
  "resource": {
    "type": "KEY_VAULT|DATABASE|AUDIT_LOG",
    "resource_id": "kv_prod_001",
    "operation": "GET|PUT|DELETE|DECRYPT"
  },
  "result": {
    "status": "SUCCESS|FAILURE|DENIED",
    "error_code": null,
    "duration_ms": 45
  },
  "context": {
    "ip_address": "192.0.2.1",
    "user_agent": "KAKEHASHI/1.0",
    "chat_session": "session_xyz789"
  },
  "signature": "HMAC-SHA256(log_entry + secret_key)"
}
```

**改ざん防止**:
- 各ログエントリに HMAC-SHA256署名を付与（シークレットキーは Key Vault保管）
- ログを Append-only Blob Storage に保存（削除・編集不可）
- ログ検証ツール: 定期的に署名チェック + 連続性検証

### 1.5 キーローテーション

**戦略**:
```
初回デプロイ (KV_v1)
        ↓
90日経過
        ↓
KV_v2 生成 → 新キーで暗号化開始（並行2キー）
        ↓
既存データ レキー（バッチ処理）
        ↓
KV_v1 廃止（ログで記録）
        ↓
90日経過
        ↓
KV_v3 へ...（以降同じ）
```

**実装**:
- Key Vault で自動ローテーション有効（90日ごと）
- 各暗号化レコードに `key_version` フィールドを記録
- 復号時: キーバージョンを参照して正しいキーを使用
- 緊急ローテーション: 侵害・疑いがあれば即座に `KV_emergency` へ切り替え（24時間以内）

---

## 2. アーキテクチャ設計（案3: ハイブリッド）

### 2.1 コンポーネント構成

```
┌────────────────────────────────────────────────────────────┐
│ 5チャット並行開発                                          │
│  Chat 1 (glow-ma)                                        │
│  Chat 2 (市場調査)                                        │
│  Chat 3 (ゆんたく)                                        │
│  Chat 4 (沖縄企業のミカタ)                                 │
│  Chat 5 (過去アーカイブ)                                   │
└────────────────────────────────────────────────────────────┘
               ↓ 依存（統一）
┌────────────────────────────────────────────────────────────┐
│ Core Wrapper Library (@kakehashi/kek-wrapper)             │
│ ├─ KeyVaultConnector                                      │
│ │  ├─ authenticate()        [Managed Identity]            │
│ │  ├─ getSecret()           [キャッシュ + TTL]           │
│ │  ├─ rotateKey()           [定期 / 緊急]                │
│ │  └─ logAccess()           [中央監査ログ]                │
│ ├─ CryptoService                                         │
│ │  ├─ encrypt(data, key)    [AES-256-GCM]               │
│ │  ├─ decrypt(ciphertext)   [複号化]                     │
│ │  └─ validateSignature()   [HMAC-SHA256]               │
│ ├─ AuditLogCollector                                     │
│ │  ├─ recordEvent()         [イベント記録]                │
│ │  ├─ validateLog()         [署名・連続性]                │
│ │  └─ exportToSIEM()        [外部送信]                    │
│ └─ ErrorHandler                                          │
│    ├─ logSecurityEvent()    [セキュリティインシデント]      │
│    └─ alertOnFailure()      [自動通知]                    │
└────────────────────────────────────────────────────────────┘
               ↓ 依存
┌────────────────────────────────────────────────────────────┐
│ Azure Services                                             │
│ ├─ Key Vault (credential + encryption keys)              │
│ ├─ Managed Identity (auth)                               │
│ ├─ Blob Storage (append-only audit logs)                │
│ ├─ Monitor / Alert Rules (security events)              │
│ └─ Application Insights (performance + traces)           │
└────────────────────────────────────────────────────────────┘
```

### 2.2 デプロイメント戦略

**フェーズ**:
1. **Week 1-2**: Core Wrapper + Unit Tests + Local テスト
2. **Week 3-4**: CI/CD ゲート実装 + Staging デプロイ
3. **Week 5-6**: 5チャット統合開始（並行）+ Integration テスト
4. **Week 7-8**: セキュリティ監査（外部）+ ペネトレーション テスト
5. **Week 9-10**: 本番デプロイ（段階的ロールアウト 10%→50%→100%）
6. **Week 11-12**: 監視・インシデント対応・ドキュメント完成 + 決裁

**リスク軽減**:
- Blue-Green デプロイ（即座にロールバック可）
- Canary デプロイ（10% ユーザーで検証）
- 各フェーズで小柳さん決裁を経て次へ

---

## 3. 実装スタイルガイド（5チャット共通）

### 3.1 コーディング規約

**言語**: Python 3.11+（既存：kakei-crm）

```python
# ✅ 正例
from kakehashi.kek_wrapper import KeyVaultConnector, CryptoService

class UserService:
    def __init__(self):
        self.kv = KeyVaultConnector()
        self.crypto = CryptoService()
        self.audit = AuditLogCollector()
    
    async def fetch_user(self, user_id: str) -> dict:
        """
        ユーザー情報を取得・復号化
        Raises: SecurityError（キー取得失敗時）
        """
        try:
            encrypted_record = await db.get(user_id)
            key = await self.kv.getSecret(f"user_key_{user_id}")
            plaintext = self.crypto.decrypt(encrypted_record, key)
            
            # 監査ログ記録
            await self.audit.recordEvent(
                event_type="DATA_READ",
                resource_id=user_id,
                status="SUCCESS"
            )
            return plaintext
        except Exception as e:
            await self.audit.recordEvent(
                event_type="DATA_READ",
                resource_id=user_id,
                status="FAILURE",
                error_code=str(e)
            )
            raise SecurityError(f"Failed to read user: {e}") from e

# ❌ 反例
# - Key Vault を直接呼ばない（Wrapper を使う）
# - 監査ログなしにセンシティブデータをアクセスしない
# - 例外をサイレント処理しない
```

### 3.2 エラーハンドリング

```python
class SecurityError(Exception):
    """セキュリティ関連エラー（暗号化失敗・キー取得失敗など）"""
    pass

class AuditError(Exception):
    """監査ログ記録失敗"""
    pass

# 必須: すべてのセキュリティ例外は自動的に監査ログされる
try:
    data = decrypt(...)
except SecurityError as e:
    # → 自動で audit_log に "DECRYPT_FAILURE" が記録される
    # → アラート送信（breach 疑い）
    raise
```

### 3.3 データクラス定義

```python
from dataclasses import dataclass
from enum import Enum

class EventType(Enum):
    KEY_ACCESS = "KEY_ACCESS"
    SECRET_DECRYPT = "SECRET_DECRYPT"
    KEY_ROTATE = "KEY_ROTATE"
    USER_LOGIN = "USER_LOGIN"
    DATA_EXPORT = "DATA_EXPORT"
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"

@dataclass
class AuditLogEntry:
    timestamp: str  # ISO 8601
    event_id: str   # UUID
    event_type: EventType
    actor_user_id: str
    actor_role: str
    resource_type: str
    resource_id: str
    operation: str
    status: str  # SUCCESS | FAILURE | DENIED
    error_code: Optional[str]
    duration_ms: int
    ip_address: str
    signature: str  # HMAC-SHA256
```

---

## 4. CI/CDゲート仕様

### 4.1 自動検査項目

**ステージ 1: コミット前**（ローカルフック）
```bash
# .husky/pre-commit
- Black / isort （コードフォーマット）
- mypy （型チェック）
- bandit （セキュリティ脆弱性スキャン）
  └─ KeyVault 直呼び出し・シークレットハードコードを検出 → FAIL
```

**ステージ 2: PR作成時**（GitHub Actions）
```yaml
name: Security Gate
on: pull_request

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      # 検査 1: 監査ログ形式の検証
      - name: Validate Audit Log Schema
        run: |
          python scripts/validate_audit_schema.py
          # → JSON schema に違反したら FAIL
      
      # 検査 2: Key Vault 直呼び出し検出
      - name: Detect Direct KV Access
        run: |
          grep -r "KeyVault\(" --include="*.py" src/
          if [ $? -eq 0 ]; then
            echo "ERROR: Direct KeyVault() call detected. Use Wrapper."
            exit 1
          fi
      
      # 検査 3: ハードコードシークレット検出
      - name: Secrets Detection
        uses: truffleHog3 / (or equivalent)
        with:
          path: ./
          fail: true
      
      # 検査 4: SAST (Static Analysis Security Testing)
      - name: SAST
        run: |
          semgrep --config=.semgrep.yml --json -o semgrep.json
          # → High/Critical 発見時 FAIL
      
      # 検査 5: 実装スタイル準拠チェック
      - name: Style Compliance
        run: |
          python scripts/check_style_guide.py
          # → 監査ログ記録忘れ、エラーハンドリング不足 など
```

**ステージ 3: マージ前**（自動テスト + 統合テスト）
```yaml
jobs:
  integration-test:
    runs-on: ubuntu-latest
    services:
      - azure-key-vault-mock  # ローカルモック
    steps:
      - name: Unit Tests
        run: pytest tests/ -v --cov
        # → Coverage >= 85% 必須
      
      - name: Integration Tests
        run: pytest tests/integration/ -v
        # → Key Vault 接続・監査ログ記録・E2E暗号化 など
      
      - name: Security Tests
        run: pytest tests/security/ -v
        # → キーローテーション・再署名・レキー など
      
      - name: Audit Log Validation
        run: python scripts/validate_audit_logs.py
        # → ログが Append-only で記録されたか、署名は正しいか
```

**ステージ 4: 本番マージ後**（Monitoring）
```yaml
jobs:
  post-deploy-monitor:
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Monitor Key Vault Access
        run: |
          az monitor metrics query \
            --resource-group $RESOURCE_GROUP \
            --resource-name $KV_NAME \
            --metric "SuccessfulRequests"
      
      - name: Check Audit Logs for Anomalies
        run: python scripts/detect_anomalies.py
        # → 異常アクセスパターンを検知 → Slack通知
```

---

## 5. マルチチャット統合ドキュメント

### 5.1 各チャット責務

| チャット | コンポーネント | 責務 | 完成期限 |
|---|---|---|---|
| Chat 1 (glow-ma) | Core Wrapper | KeyVaultConnector, CryptoService | 2026-11-15 |
| Chat 2 (市場調査) | Audit Collector | 監査ログ中央集約・SIEM送信 | 2026-11-22 |
| Chat 3 (ゆんたく) | RBAC Layer | ロール・パーミッション管理 | 2026-11-22 |
| Chat 4 (沖縄企業のミカタ) | Key Rotation | キーローテーション・緊急対応 | 2026-11-29 |
| Chat 5 (アーカイブ) | Monitoring | インシデント検知・アラート | 2026-11-29 |

### 5.2 進捗同期

**週次リズム** (毎週月曜)
```
9:00 - 30分: 全チャット進捗報告（Slack #kakehashi-phase-e）
  各チャット: ✅完成した機能 / 🚧 今週の作業 / ⚠️ ブロッカー
10:00 - 30分: 統合テスト（Staging）
  → 各チャットの出力を結合、E2E動作確認
```

**議事化ルール**
- 設計変更・スケジュール延期: 三名体制議事（スイシン/ウタガイ/ベッカイ）
- 確定事項: 小柳さん決裁の前に議事を通す

---

## 6. セキュリティコンプライアンス・監視・インシデント対応

### 6.1 定期監査

**外部セキュリティ監査**（Week 7-8）
- ペネトレーション テスト（ホワイトボックス）
  - Key Vault 接続の安全性
  - 監査ログ改ざん可能性
  - RBAC バイパス可能性
- コードレビュー（OWASP Top 10）
- インフラ監査（TLS, 暗号化アルゴリズム）

**内部自動監査** (毎週)
```python
# scripts/weekly_compliance_check.py
- 監査ログ署名検証（全件）
- キーローテーション履歴確認
- 異常アクセスパターン検知（ML）
- RBAC ポリシーの整合性確認
```

### 6.2 インシデント対応計画

**タイムライン**（SLA）
```
T+0分    : セキュリティイベント自動検知 → Slack/PagerDuty通知
T+5分    : オンコール対応者が確認
T+15分   : 初期判定（真正なセキュリティ事象か）
T+30分   : 緊急対応決定（KEY_EMERGENCY ローテーション等）
T+60分   : インシデント報告書起案
T+24時間 : 事後分析・改善案提出
```

**対応フロー**
```
セキュリティイベント
├─ 暗号化失敗
│  └─ Key Vault へのアクセス確認 → リトライ / ロールバック
├─ 監査ログ署名不一致
│  └─ → 即座に Key Vault 認証キーローテーション
├─ 異常ログインパターン
│  └─ → RBAC 一時停止 + IP ホワイトリスト追加
├─ キー盗難（疑い）
│  └─ → KEY_EMERGENCY へ即座に切り替え（24時間以内）
│       → レキー開始（既存データ + 新キー）
└─ その他
   └─ → 小柳さんへエスカレーション
```

### 6.3 SIEMへの外部送信

**送信先**: Azure Sentinel / Datadog / Splunk（選択可能）

**送信スケジュール**:
- リアルタイム: セキュリティイベント（高優先度）
- 1時間ごと: 監査ログダイジェスト
- 日1回: コンプライアンスレポート（SOC 2 / ISO 27001対応）

**フォーマット**:
```json
{
  "source": "kakehashi-phase-e",
  "timestamp": "2026-10-29T15:30:45Z",
  "severity": "HIGH|MEDIUM|LOW",
  "message": "...",
  "audit_log": { /* 上記 1.4 参照 */ }
}
```

---

## 7. 実装スケジュール（詳細）

| 週 | Chat 1 | Chat 2 | Chat 3 | Chat 4 | Chat 5 | マイルストーン |
|---|---|---|---|---|---|---|
| W1-2 (11/3-14) | Core Wrapper 設計・実装 | - | - | - | - | Wrapper α版 完成 |
| W3-4 (11/17-28) | Unit/Integration テスト | CI ゲート実装 | - | - | - | CI PASS |
| W5-6 (12/1-12) | Wrapper リリース | Chat 統合開始 | 統合テスト | - | - | Staging ✅ |
| W7-8 (12/15-26) | 本番リリース準備 | - | - | 外部監査 | - | **決裁前夜** |
| W9-10 (12/29-1/9) | - | - | - | 本番デプロイ | 監視開始 | 本番稼働 |
| W11-12 (1/12-23) | - | - | - | - | ドキュメント完成 | **完了** |

**期限: 2026-12-17**

---

## 8. Salesforce / BlueBean 相当性の説明資料

### 営業・監査向け説明テンプレート

**セキュリティレベル対比表**
```
機能                    | Salesforce Shield | KAKEHASHI Phase E | BlueBean
─────────────────────────────────────────────────────────────────
暗号化（At Rest）      | ✅ AES-256       | ✅ AES-256-GCM   | ✅
暗号化（In Transit）   | ✅ TLS 1.2+      | ✅ TLS 1.2+      | ✅
キーローテーション     | ✅ 90日自動      | ✅ 90日自動      | ✅
RBAC                    | ✅ 8+ ロール     | ✅ 4+ ロール     | ✅
監査ログ（Append-only） | ✅              | ✅ HMAC署名      | ✅
ペネトレーション テスト | ✅ 年1回        | ✅ W7-8          | ✅ 年2回
SOC 2 Type II           | ✅              | ✅ パス予定      | ✅
ISO 27001               | ✅              | ✅ パス予定      | ✅
────────────────────────────────────────────────────────────────
コスト（年間）          | $$$（高）       | $$（中）         | $$$（高）
```

**差別化ポイント**
- **カスタマイズ性**: KAKEHASHI は 5チャット並行開発対応（Salesforce/BlueBean は単体）
- **コスト**: Azure での実装のため 30-40% 低コスト化可能
- **地域性**: 沖縄特化ビジネスに最適化（GLOW・もらいわすれ堂統合）
- **速度**: 開発期限 2026-12-17（ベンダー導入より 6ヶ月短期）

---

## 次ステップ

1. ✅ **この仕様書の確認・承認** → 小柳さん決裁
2. **実装計画策定** → writing-plans スキルへ
3. **5チャット別セッションへ連携メモ配信** → docs/連携メモ_YYYYMMDD_Phase-E.md
4. **Week 1 開発開始** → Chat 1 (glow-ma) で Core Wrapper 実装

---

*設計書完成日: 2026-10-29*  
*著: Claude Haiku 4.5*  
*決裁待ち: 小柳さん*
