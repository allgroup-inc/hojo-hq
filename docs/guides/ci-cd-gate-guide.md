# CI/CD ゲート実行ガイド

Task 2.4: SAST & スタイル規準自動化  
Security Gate: Semgrep SAST ルール + Style Guide 検査

## セットアップ

### 環境構築

```bash
# 1. Python 開発環境構築
cd /home/user/hojo-hq

# 2. 必要なツールをインストール
pip install --upgrade pip setuptools wheel

# 3. 開発依存関係をインストール
pip install -r kakehashi/requirements.txt
# または個別:
pip install semgrep>=1.45 pytest pytest-cov black isort mypy bandit
```

### Semgrep インストール確認

```bash
semgrep --version
# Expected output: semgrep <version> from rules at rules.semgrep.dev
```

## ローカルでのチェック実行

### 1. Semgrep SAST ルール検査

```bash
# 既存ルール確認
semgrep --config=.semgrep.yml kakehashi/ --json > /tmp/semgrep-results.json

# エラーレベルで失敗
semgrep --config=.semgrep.yml kakehashi/ --error

# 特定ルールのみ実行
semgrep --config=.semgrep.yml kakehashi/ --include-rule=no-hardcoded-secrets
```

### 2. スタイルガイド準拠確認

```bash
# スタイル規準チェック実行
python3 scripts/check_style_guide.py kakehashi/

# 詳細出力
python3 scripts/check_style_guide.py kakehashi/ -v
```

### 3. ファイルフォーマット確認

```bash
# Black フォーマット確認
black --check kakehashi/

# 自動修正
black kakehashi/
```

### 4. Import 順序確認

```bash
# isort チェック
isort --check-only kakehashi/

# 自動修正
isort kakehashi/
```

### 5. 型チェック

```bash
# mypy 厳密モード
mypy kakehashi/ --strict

# エラーのみ表示
mypy kakehashi/ --strict --show-error-codes
```

### 6. セキュリティスキャン

```bash
# bandit セキュリティ検査
bandit -r kakehashi/ -c .bandit

# レポート形式で出力
bandit -r kakehashi/ -c .bandit -f json > /tmp/bandit-report.json
```

### 7. テスト実行

```bash
# 全テスト実行
python3 -m pytest kakehashi/kek_wrapper/tests/ -v

# カバレッジ計測
python3 -m pytest kakehashi/kek_wrapper/tests/ \
  --cov=kakehashi.kek_wrapper \
  --cov-report=html \
  --cov-fail-under=85

# カバレッジレポート表示
coverage report --include=kakehashi/* -m
```

### 8. 全チェック一括実行

```bash
# セキュリティゲート全実行
bash scripts/run_security_gate.sh

# または手動で:
set -e

echo "1. Semgrep SAST ルール検査..."
semgrep --config=.semgrep.yml kakehashi/ --error

echo "2. スタイルガイド規準チェック..."
python3 scripts/check_style_guide.py kakehashi/

echo "3. Black フォーマット..."
black --check kakehashi/

echo "4. isort Import 順序..."
isort --check-only kakehashi/

echo "5. mypy 型チェック..."
mypy kakehashi/ --strict

echo "6. bandit セキュリティ..."
bandit -r kakehashi/ -c .bandit

echo "7. pytest テスト + カバレッジ..."
python3 -m pytest kakehashi/kek_wrapper/tests/ \
  --cov=kakehashi.kek_wrapper \
  --cov-fail-under=85 \
  -v

echo "✅ All security checks passed!"
```

## 確認項目チェックリスト

GitHub Actions で実行される順序と同じです。PR 作成前にローカルで全てクリアしてください。

- [ ] **Black フォーマット**: `black --check kakehashi/` (自動修正: `black kakehashi/`)
- [ ] **isort Import 順**: `isort --check-only kakehashi/` (自動修正: `isort kakehashi/`)
- [ ] **mypy 型チェック**: `mypy kakehashi/ --strict`
- [ ] **bandit セキュリティ**: `bandit -r kakehashi/ -c .bandit`
- [ ] **Semgrep SAST**: `semgrep --config=.semgrep.yml kakehashi/ --error`
- [ ] **スタイル規準**: `python3 scripts/check_style_guide.py kakehashi/`
- [ ] **pytest テスト**: `pytest kakehashi/kek_wrapper/tests/ -v`
- [ ] **カバレッジ >= 85%**: `pytest kakehashi/kek_wrapper/tests/ --cov=kakehashi.kek_wrapper --cov-fail-under=85`

## トラブルシューティング

### Semgrep ルール違反

#### no-hardcoded-secrets

**エラー:**
```
Hardcoded secret detected
```

**修正方法:**
```python
# ❌ NG
API_KEY = "sk-1234567890abcdef"

# ✅ OK
import os
API_KEY = os.environ.get("API_KEY")

# または
from kakehashi.kek_wrapper.core.key_vault_connector import KeyVaultConnector
kv = KeyVaultConnector()
API_KEY = kv.get_secret("api-key")
```

#### no-plain-encryption

**エラー:**
```
Direct cryptography module usage forbidden
```

**修正方法:**
```python
# ❌ NG
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
cipher = Cipher(algorithms.AES(key), modes.GCM(nonce))

# ✅ OK
from kakehashi.kek_wrapper.core.crypto_service import CryptoService
crypto = CryptoService()
encrypted = crypto.encrypt(plaintext)
```

#### key-vault-direct-access

**エラー:**
```
Direct Key Vault access forbidden
```

**修正方法:**
```python
# ❌ NG
from azure.keyvault.secrets import SecretClient
client = SecretClient(vault_url="...")

# ✅ OK
from kakehashi.kek_wrapper.core.key_vault_connector import KeyVaultConnector
kv = KeyVaultConnector()
secret = kv.get_secret("secret-name")
```

#### no-unencrypted-audit

**エラー:**
```
Audit log entries must include HMAC signature
```

**修正方法:**
```python
# ❌ NG
audit_log = {
    "event_id": "evt-123",
    "status": "SUCCESS",
}

# ✅ OK
from kakehashi.kek_wrapper.core.audit_log_collector import AuditLogCollector
collector = AuditLogCollector()
event = collector.recordEvent(
    event_type="KEY_ACCESS",
    operation="GET",
    status="SUCCESS",
    # signature は自動で付与されます
)
```

#### hmac-always-constant-time

**エラー:**
```
HMAC signature verification must use hmac.compare_digest()
```

**修正方法:**
```python
import hmac

# ❌ NG
if signature == expected_signature:
    verified = True

# ✅ OK
if hmac.compare_digest(signature, expected_signature):
    verified = True
```

### Black フォーマットエラー

```bash
# エラー確認
black --check kakehashi/

# 自動修正
black kakehashi/

# その後コミット
git add kakehashi/
git commit -m "format: apply black formatter"
```

### mypy 型エラー

```bash
# エラー詳細表示
mypy kakehashi/ --strict --show-error-codes

# 型ヒント追加例
def get_secret(self, name: str) -> bytes:
    """Retrieve secret from Key Vault.
    
    Args:
        name: Secret name
        
    Returns:
        Secret bytes
    """
    ...
```

### pytest カバレッジ不足

```bash
# 未カバーのコード行を表示
pytest kakehashi/kek_wrapper/tests/ \
  --cov=kakehashi.kek_wrapper \
  --cov-report=term-missing

# 最新のテストコードを追加してカバレッジ向上
# 新テスト ファイル: kakehashi/kek_wrapper/tests/test_*.py
```

## GitHub Actions での自動実行

PR 作成時に `.github/workflows/security-gate.yml` が自動実行されます。

**ワークフロー手順:**
1. Black フォーマット確認
2. isort Import 順確認
3. mypy 型チェック
4. bandit セキュリティスキャン
5. Semgrep SAST ルール実行
6. スタイル規準チェック
7. pytest テスト実行
8. カバレッジ計測

**ゲートに引っかかった場合:**
- PR コメントでエラーメッセージ確認
- ローカルで同じコマンド実行して再現
- 修正を加えて再コミット
- `git push` で自動再検査

## 定期メンテナンス

### 毎月初（月初 1 日）

```bash
# 全チェック実行とレポート生成
python3 -m pytest kakehashi/ --cov=kakehashi --cov-report=html
# reports/coverage-html/index.html を確認
```

### Semgrep ルールの更新

```bash
# 最新ルール確認
semgrep --version

# ルールファイル編集
vi .semgrep.yml

# 新ルール追加後は必ずテスト
semgrep --config=.semgrep.yml kakehashi/ --json
```

## 見直し期限

**2026-11-27** (Phase 2 完了時)  
このガイドの内容は Phase E 実装中に最新化されます。

---

## 関連リソース

- **SAST ルール定義:** `.semgrep.yml`
- **スタイル規準:** `scripts/check_style_guide.py`
- **テスト実行:** `kakehashi/kek_wrapper/tests/`
- **仕様書:** `.superpowers/sdd/2026-10-29-Phase-E-implementation-plan/`

**作成:** Task 2.4  
**言語:** Python 3.11+  
**ツール:** Semgrep 1.45+, pytest, mypy, black
