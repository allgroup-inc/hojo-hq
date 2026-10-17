# 技術準備 C-2: call-log API 統合テスト計画

**作成日**: 2026-10-17  
**対象**: 🌟管理システム チーム  
**目的**: call-log API データ送信機能の事前テスト・統合準備

---

## 📋 テスト対象

- [ ] 顧客カルテ（customer_detail.html）での操作ログ送信
- [ ] call-log API への正確なデータ送信
- [ ] エラーハンドリング・リトライロジック
- [ ] ログ形式の検証・監査

---

## 🔧 前提条件（軸チーム確認待ち）

以下が確定するまでは、**Mock API** で進める：

```
C-2. call-log API 仕様
  □ エンドポイント
  □ HTTP メソッド (POST / PUT)
  □ 必須フィールド（user_id / timestamp / action など）
  □ 認証方式（Bearer Token / Key など）
  □ 送信タイミング（リアルタイム / バッチ）
  □ エラーハンドリング（失敗時の再試行）
```

**現在**: ⏳ 軸チームからの `call_log_API仕様.md` 待機中

---

## 📊 テスト項目（準備フェーズ）

### テスト 1: ローカル Mock API の構築

```python
# scripts/mock_call_log_api.py

"""
Mock call-log API server for local testing
Endpoint: http://localhost:8888/api/call-log/send
"""

from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/call-log/send', methods=['POST'])
def receive_call_log():
    # Mock implementation
    payload = request.json
    
    # Validation
    required_fields = ['user_id', 'timestamp', 'action', 'customer_id']
    if not all(k in payload for k in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Mock save to local log
    print(f"[MOCK] Received: {payload}")
    return jsonify({'status': 'ok', 'id': 'log_12345'}), 200

if __name__ == '__main__':
    app.run(port=8888)
```

**実装済み**: ⏳ Flask mock server テンプレート作成予定
**テスト**: curl / Postman での動作確認

---

### テスト 2: kanri_system からのデータ送信ロジック

```javascript
// kanri_system/lib/call_log_sender.js

/**
 * Send call log to API
 * @param {object} event - User action (view, edit, delete, etc)
 * @returns {promise} API response
 */
export const sendCallLog = async (event) => {
  const payload = {
    user_id: getCurrentUserId(),
    timestamp: new Date().toISOString(),
    action: event.type, // 'view' / 'edit' / 'delete' / etc
    customer_id: event.customerId,
    details: event.details || null,
  };

  try {
    const response = await fetch('/api/call-log/send', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Call log send failed:', error);
    // リトライロジック / オフラインキャッシング
    await cacheCallLogOffline(payload);
  }
};
```

**実装状態**: ⏳ テンプレート作成予定

---

### テスト 3: イベント種別の定義

```javascript
// kanri_system/lib/call_log_events.js

export const CALL_LOG_EVENTS = {
  CUSTOMER_VIEW: 'customer_view', // 顧客カルテを開く
  CUSTOMER_EDIT: 'customer_edit', // 顧客情報を編集
  CONTRACT_VIEW: 'contract_view', // 契約情報を表示
  CONTRACT_EDIT: 'contract_edit', // 契約情報を編集
  EXPORT_PDF: 'export_pdf',       // PDF エクスポート
  PRINT: 'print',                 // 印刷
  CALL_LOG_VIEW: 'call_log_view', // ログを表示
};

// Usage in components
export const trackEvent = (eventType, customerId, details = {}) => {
  sendCallLog({
    type: eventType,
    customerId,
    details,
  });
};
```

**実装済み**: ✅ イベント定義テンプレート

---

### テスト 4: オフラインキャッシング・リトライ

```javascript
// kanri_system/lib/call_log_queue.js

/**
 * Queue logs when API is unavailable
 * Retry when connection restored
 */

class CallLogQueue {
  constructor() {
    this.queue = [];
    this.loadFromStorage();
  }

  async enqueue(logPayload) {
    this.queue.push({
      payload: logPayload,
      timestamp: new Date(),
      retryCount: 0,
    });
    this.saveToStorage();
  }

  async flushQueue() {
    for (let item of this.queue) {
      try {
        const response = await sendCallLog(item.payload);
        // Remove from queue on success
        this.queue = this.queue.filter(q => q !== item);
      } catch (error) {
        item.retryCount++;
        if (item.retryCount > 3) {
          // Max retries exceeded
          console.error('Call log dropped:', item);
          this.queue = this.queue.filter(q => q !== item);
        }
      }
    }
    this.saveToStorage();
  }

  saveToStorage() {
    localStorage.setItem('call_log_queue', JSON.stringify(this.queue));
  }

  loadFromStorage() {
    const stored = localStorage.getItem('call_log_queue');
    if (stored) this.queue = JSON.parse(stored);
  }
}

export const logQueue = new CallLogQueue();
```

**実装状態**: ⏳ テンプレート作成予定

---

### テスト 5: データ形式・検証テスト

```javascript
// test/call_log_format.test.js

describe('Call Log Format', () => {
  test('Required fields present', () => {
    const log = {
      user_id: 'km-000001',
      timestamp: '2026-10-17T10:30:00Z',
      action: 'customer_view',
      customer_id: 'cust-001',
    };
    expect(validateCallLog(log)).toBe(true);
  });

  test('Timestamp is ISO 8601', () => {
    const log = createCallLog('customer_view');
    expect(/^\d{4}-\d{2}-\d{2}T/.test(log.timestamp)).toBe(true);
  });

  test('Action is in allowed list', () => {
    const log = createCallLog('invalid_action');
    expect(validateCallLog(log)).toBe(false);
  });

  test('Handles API error gracefully', async () => {
    // Mock API returns 500
    const result = await sendCallLog(mockLog);
    expect(logQueue.queue.length).toBe(1); // Added to queue
  });
});
```

**実装済み**: ✅ テストケース定義

---

## 🎯 実装進捗チェックリスト

| タスク | 状態 | 責任 | 期限 |
|---|---|---|---|
| Mock API サーバー構築 | ⏳ 準備中 | 管理システムチーム | 2026-10-20 |
| call_log_sender.js 実装 | ⏳ 準備中 | 管理システムチーム | 2026-10-20 |
| イベント定義 | ✅ 完了 | 管理システムチーム | — |
| オフラインキャッシング | ⏳ 準備中 | 管理システムチーム | 2026-10-20 |
| データ形式テスト | ⏳ 準備中 | 管理システムチーム | 2026-10-20 |
| **call-log API 仕様書受取** | 🟡 待機 | **軸チーム** | **2026-10-18** |
| **実 API との統合テスト** | ⏳ ブロック中 | **管理システムチーム** | **2026-10-22** |

---

## 📊 期待されるログ出力例

```json
{
  "user_id": "km-000001",
  "timestamp": "2026-10-17T10:30:45.123Z",
  "action": "customer_view",
  "customer_id": "cust-000001",
  "details": {
    "source": "customer_search",
    "session_id": "sess_abc123"
  }
}
```

---

## 🔗 関連ドキュメント

| ドキュメント | 参照元 | 用途 |
|---|---|---|
| `docs/連携メモ_20261017_軸宛_統合依頼リスト_Phase1.5Phase2.md` | 軸チーム依頼 | C-2 の詳細要件 |
| `kanri_system/lib/` | 管理システム | 実装配置先 |
| `test/` | 管理システム | テストファイル配置先 |

---

_作成: 2026-10-17 / Claude Code（🌟管理システムチャット）_
