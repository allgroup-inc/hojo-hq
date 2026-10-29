# KAKEHASHI 実装スタイルガイド

## 概要
Phase E セキュリティ実装の統一スタイル。すべてのチャットがこの規準に従う。

## §3.1 Key Vault アクセスの一元化

**必須:** すべての Key Vault アクセスは KeyVaultConnector 経由のみ。

❌ 禁止:
```python
from azure.keyvault.secrets import SecretClient
client = SecretClient(vault_url, credential)
secret = client.get_secret("my-secret")
```

✅ 推奨:
```python
from kakehashi.kek_wrapper.core import KeyVaultConnector

connector = KeyVaultConnector(vault_url, credential)
secret = await connector.getSecret("my-secret")
await connector.logAccess("GET_SECRET", "SUCCESS", "my-secret", "GET")
```

**理由:** Key Vault アクセスは必ず監査ログ記録(logAccess)と共に行い、ネットワークエラー時の再試行、5 分キャッシュなどの一貫した処理を確保する。

## §3.2 データ暗号化の統一

**必須:** 平文データの保存・送信禁止。すべて AES-256-GCM 暗号化。

❌ 禁止:
```python
secret_data = "customer_id:12345"  # 平文
with open("data.txt", "w") as f:
    f.write(secret_data)
```

✅ 推奨:
```python
from kakehashi.kek_wrapper.core import CryptoService, KeyVaultConnector

crypto = CryptoService(kek_provider=connector)
key = await connector.getSecret("encryption-key")
encrypted = await crypto.encrypt(b"customer_id:12345", key)
# EncryptedData: ciphertext, iv, key_version, timestamp

with open("data.json", "w") as f:
    json.dump(encrypted.to_dict(), f)
```

**理由:** IV はメッセージごとにランダム生成。決定的暗号化は不使用。

## §3.3 監査ログの必須記録

**必須:** 所有権変更・セキュリティ決定・外部送信は必ず監査ログ記録。

監査対象操作:
- `KEY_VAULT`: getSecret, rotate, invalidate (Task 1.1 logAccess)
- `CRYPTO`: encrypt, decrypt, validateSignature (Task 1.2 audit)
- `AUDIT`: recordEvent, exportToSIEM (Task 1.3 self-log)
- `SECURITY`: SecurityError 発生、DENIED 決定、通知送信 (Task 1.4 alert)
- `RBAC`: 権限変更、新規ユーザー追加 (Task 3.1)

❌ 禁止:
```python
async def rotate_keys():
    await connector.rotateKey(force_emergency=True)
    # 監査ログなし
```

✅ 推奨:
```python
async def rotate_keys():
    await connector.rotateKey(force_emergency=True)
    await audit_collector.recordEvent(
        event_type=EventType.KEY_ROTATE,
        actor_role=Role.SYSTEM,
        resource_id="encryption-key",
        operation=Operation.ROTATE,
        status=Status.SUCCESS,
    )
```

**理由:** 外部監査・コンプライアンス証跡・インシデント調査に必須。

## §3.4 エラーハンドリング・アラート

**必須:** SecurityError/AuditError は捕捉・アラート・回復。

❌ 禁止:
```python
try:
    key = await connector.getSecret("my-secret")
except Exception:
    pass  # silent fail
```

✅ 推奨:
```python
from kakehashi.kek_wrapper.models import SecurityError, AuditError

try:
    key = await connector.getSecret("my-secret")
except AuditError as e:
    await error_handler.logSecurityEvent("AUDIT_FAILURE", context={
        "resource": "my-secret",
        "error": str(e),
    })
    await error_handler.alertOnFailure("CRITICAL", f"Audit log write failed: {e}")
    raise  # propagate
except Exception as e:
    logger.error(f"Key retrieval failed: {e}", exc_info=True)
    raise
```

**理由:** SecurityError は放置厳禁。通知・ログ・復旧のフローを確立。

## 命名規約

- **関数:** snake_case (Python standard)
- **クラス:** PascalCase
- **定数:** UPPER_SNAKE_CASE
- **Key Vault 秘密名:** lowercase-with-dashes (アンダースコア不可)
  - ✅ OK: `encryption-key`, `db-password`
  - ❌ NG: `encryption_key`, `db_password`

## 型ヒント

**必須:** すべての関数に type hints。mypy --strict 適合。

❌ 禁止:
```python
def get_secret(name):
    return await connector.getSecret(name)
```

✅ 推奨:
```python
async def get_secret(name: str) -> bytes:
    """Get secret from Key Vault and cache for 5 minutes."""
    return await connector.getSecret(name)
```

## ドキュメンテーション

**必須:** セキュリティ関連関数に docstring & security note。

```python
async def encrypt(plaintext: bytes, key: bytes) -> EncryptedData:
    """
    Encrypt plaintext using AES-256-GCM.
    
    Args:
        plaintext: Data to encrypt (bytes)
        key: Encryption key (bytes, 32 bytes for AES-256)
    
    Returns:
        EncryptedData with ciphertext, IV (random 16 bytes), key version
    
    Security Notes:
        - IV is randomly generated per message (no deterministic encryption)
        - GCM tag validates ciphertext integrity
        - On decryption, invalid tag raises ValueError immediately
        - Key must be kept in memory only; never log or persist plaintext
    """
```

## テストカバレッジ

**必須:** >= 85% coverage on all source files (Tasks 1.1-1.4, 3.1-3.3).

```bash
pytest kakehashi/kek_wrapper/tests/ \
  --cov=kakehashi.kek_wrapper \
  --cov-fail-under=85 \
  --cov-report=term-missing
```

## 見直し期限
**2026-11-28**(Phase 2 完了)
