# データモデル設計（Task 4）

**テーブル構成:**

```
users (営業マン・スタッフ・管理者)
- id, entra_id, name, email, role (admin/apo_staff/sales_rep), is_active

appointments (アポ)
- id, customer_id, customer_name, scheduled_datetime, actual_datetime
- estimated_duration, assigned_sales_rep_id, location, status
- source (apogen_system/manual), notes, created_by_id, updated_by_id
- created_at, updated_at, cancelled_at

appointment_changes (監査ログ)
- id, appointment_id, change_type (created/updated/cancelled)
- old_values (JSONB), new_values (JSONB), changed_by_id, reason, changed_at

schedules (営業マンの可用性)
- id, user_id, date, start_time, end_time, travel_time_buffer
- break_periods (JSONB), is_available, created_at, updated_at

kpi_metrics (KPI・統計)
- id, date, user_id, appointments_count, completed_count, cancelled_count
- avg_duration, travel_distance, revenue_forecast, created_at, updated_at

notifications (通知ログ)
- id, user_id, type (slack/email/in_app), message, sent_at, is_read
```

**インデックス戦略:**
- appointments(scheduled_datetime), appointments(assigned_sales_rep_id), users(entra_id)
- appointment_changes(changed_at, appointment_id)
- kpi_metrics(date, user_id)
- notifications(user_id, sent_at)

**JSONB活用:**
- old_values/new_values: 柔軟な変更履歴保存（フィールド数可変）
- break_periods: 休憩時間帯の配列 [{startTime: "12:00", endTime: "13:00"}, ...]
