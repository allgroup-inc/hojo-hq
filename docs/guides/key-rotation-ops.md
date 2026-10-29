# Key Vault 鍵ローテーション運用ガイド

## 概要
Azure Key Vault での自動・手動鍵ローテーション手順。90 日定期ローテーション + 緊急ローテーション対応。

## 自動スケジュール ローテーション

### 設定

Azure Key Vault のローテーション ポリシーを設定:

```bash
# 現在の設定確認
az keyvault key rotation-policy show \
  --vault-name hojo-kv \
  --key-name encryption-key

# 90 日定期ローテーション設定
az keyvault key rotation-policy update \
  --vault-name hojo-kv \
  --key-name encryption-key \
  --expires-in 90d \
  --rotation-interval 3m  # 3 months
```

### 自動実行フロー

1. **スケジュール:** 毎月 1 日 03:00 JST (Azure Automation or Cloud Scheduler)
2. **トリガー:** `KeyVaultConnector.rotateKey(force_emergency=False)`
3. **生成:** 新バージョンを生成(`/versions` エンドポイント)
4. **キャッシュ:** 旧バージョン cached 削除(generation カウンタ更新)
5. **監査:** AuditLogCollector に記録
6. **通知:** Slack #security に「ローテーション完了」通知

### スケジュール済みジョブ設定

GitHub Actions workflow (gated by Phase 3):

```yaml
name: Key Rotation
on:
  schedule:
    - cron: "0 3 1 * *"  # 毎月 1 日 03:00 JST
jobs:
  rotate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Rotate Key Vault Keys
        run: |
          python3 scripts/rotate_keys.py --schedule
```

## 緊急ローテーション

### トリガー条件

以下の場合は即座に緊急ローテーション:

1. **キー漏洩疑い:** 開発マシンの破損、GitHub leak 検知等
2. **セキュリティアラート:** AWS/Azure の異常アクセス通知
3. **監査指摘:** 外部監査による鍵アクセス異常検知
4. **構成エラー:** キーマテリアル誤出力・ログ記録等

### 手動実行手順

```bash
# 緊急ローテーション実行 (旧キャッシュすべて削除)
python3 scripts/rotate_keys.py --emergency \
  --vault-name hojo-kv \
  --key-name encryption-key

# 実行内容:
# 1. 新バージョン生成
# 2. generation カウンタ +1 (stale key invalidate)
# 3. キャッシュすべて削除
# 4. 既存データの再暗号化(段階的)
# 5. 監査ログ: KEY_ROTATE / SUCCESS / "emergency"
```

### 実行後確認

```bash
# 新バージョンが "latest" になったか確認
az keyvault key show \
  --vault-name hojo-kv \
  --name encryption-key

# 出力に "versions": [..., "new-version"] が含まれることを確認

# 監査ログ確認
az storage blob download \
  --account-name hojoauditlog \
  --container-name audit-log \
  --name audit-KEY_ROTATE-YYYYMMDD.json \
  --file local.json
  
# JSON 内に event_type: "KEY_ROTATE" で最新日時の記録を確認
```

## キー バージョン管理

### バージョン ライフサイクル

| ステータス | TTL | 説明 |
|---|---|---|
| **latest** | 90日 | 新規データ暗号化に使用。90 日後に自動ローテーション |
| **active** | 無制限 | 既存暗号化データの復号に使用 |
| **old** | 6 ヶ月 | 復号専用。暗号化禁止。6 ヶ月後に削除 |
| **disabled** | 無制限 | 緊急ローテーション時の旧バージョン。キャッシュ削除のみ |

### 既存データの再暗号化

新キーで既存データを再暗号化する手順(段階的):

```python
# Phase 3.2 で実装
async def reencrypt_all_data(old_key_version: str, new_key_version: str):
    """
    Batch reencryption: old key → new key
    無中断実行(読み取り時に段階的再暗号化も可能)
    """
    crypto = CryptoService(kek_provider=connector)
    batch_size = 100
    
    async for encrypted_batch in fetch_encrypted_data_batch(batch_size):
        for encrypted_data in encrypted_batch:
            if encrypted_data.key_version == old_key_version:
                # 復号(旧キー)
                plaintext = await crypto.decrypt(encrypted_data, old_key)
                
                # 再暗号化(新キー)
                new_encrypted = await crypto.encrypt(plaintext, new_key)
                
                # 保存
                await save_encrypted_data(id, new_encrypted)
                
                # 監査
                await audit_collector.recordEvent(
                    event_type=EventType.CRYPTO,
                    operation=Operation.ROTATE,
                    status=Status.SUCCESS,
                    context={"old_version": old_key_version, "new_version": new_key_version}
                )
```

## Slack 通知テンプレート

### ローテーション成功

```
🔄 Key Rotation Completed

Vault: hojo-kv
Key: encryption-key
Old Version: v123
New Version: v124
Time: 2026-11-01 03:15 JST

Audit Log: ✅ 1 record logged
Cache Invalidation: ✅ 567 entries cleared
Status: 🟢 OK
```

### 緊急ローテーション

```
🚨 EMERGENCY Key Rotation

Vault: hojo-kv
Key: encryption-key
Reason: [Key Exposure / Security Alert / Audit Finding]
Executed: 2026-10-29 14:33 JST
Operator: takeshi.koyanagi9@gmail.com

Actions:
- ✅ New version generated: v125
- ✅ Generation counter bumped (invalidates all cached keys)
- ✅ Old version disabled
- ✅ Audit log created

Re-encryption Status: Pending (Phase 3.3 monitor)
Review: Required
```

## トラブルシューティング

### Q: 新キーで暗号化がされていない
→ generation カウンタを確認。キャッシュされた旧キーが使用されている可能性あり。`rotateKey(force_emergency=True)` を実行。

### Q: 古いデータが復号できない
→ 古いキー バージョンがまだ存在するか確認。削除していないか、バージョン ID が間違っていないか。

### Q: ローテーション失敗時の復旧
→ 監査ログから失敗理由を確認。Azure Key Vault API のレート制限の場合は数分後に再試行。

## 見直し期限
**2026-12-01**(Phase 3.2 ローテーションサービス実装完了時に見直し)
