# KAKEHASHI Monitoring & Alerting Dashboard Guide

## Overview

This guide describes how to set up and use the Azure Application Insights and Log Analytics monitoring dashboard for the KAKEHASHI kek_wrapper system.

The monitoring system tracks metrics and health status across five layers:
1. Azure Key Vault connectivity and performance
2. CryptoService encryption/decryption operations
3. AuditLogCollector write operations
4. RBACEnforcer token operations
5. Database connectivity and queries

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    KAKEHASHI Monitoring                      │
├──────────┬──────────────┬──────────────┬────────────┬────────┤
│ KeyVault │ CryptoSvc    │ AuditLog     │ RBAC       │  DB    │
│ Health   │ Roundtrip    │ Write Latency│ Token Ops  │ Query  │
└──────────┴──────────────┴──────────────┴────────────┴────────┘
                    ↓
        ┌───────────────────────┐
        │ MonitoringService     │
        │ - emit_metric()       │
        │ - emit_log_event()    │
        │ - evaluate_rules()    │
        └───────────┬───────────┘
                    ↓
        ┌───────────────────────┐
        │ Azure Application     │
        │ Insights / Log        │
        │ Analytics             │
        └───────────┬───────────┘
                    ↓
        ┌───────────────────────┐
        │ AlertDispatcher       │
        │ - Slack notifications │
        │ - Email alerts        │
        │ - Escalation rules    │
        └───────────────────────┘
```

## Key Metrics

### 1. Key Vault Metrics
- **Name**: `kek_vault_cache_hit_rate`
  - **Type**: GAUGE
  - **Unit**: percent (0-100)
  - **Description**: Percentage of Key Vault requests served from cache
  
- **Name**: `kek_vault_error_rate`
  - **Type**: GAUGE
  - **Unit**: percent (0-100)
  - **Description**: Percentage of Key Vault requests that fail

- **Name**: `kek_vault_latency_ms`
  - **Type**: HISTOGRAM
  - **Unit**: milliseconds
  - **Description**: Response time for Key Vault operations

### 2. CryptoService Metrics
- **Name**: `crypto_encrypt_latency_ms`
  - **Type**: HISTOGRAM
  - **Unit**: milliseconds
  - **Description**: Time to encrypt a message

- **Name**: `crypto_decrypt_latency_ms`
  - **Type**: HISTOGRAM
  - **Unit**: milliseconds
  - **Description**: Time to decrypt a message

- **Name**: `crypto_key_rotation_duration_ms`
  - **Type**: HISTOGRAM
  - **Unit**: milliseconds
  - **Description**: Time to complete a key rotation

### 3. Audit Log Metrics
- **Name**: `audit_log_write_latency_ms`
  - **Type**: HISTOGRAM
  - **Unit**: milliseconds
  - **Description**: Time to write an audit log entry

- **Name**: `audit_log_buffer_size`
  - **Type**: GAUGE
  - **Unit**: count
  - **Description**: Current number of buffered audit events

### 4. RBAC Metrics
- **Name**: `rbac_auth_failure_rate`
  - **Type**: GAUGE
  - **Unit**: percent
  - **Description**: Percentage of authentication attempts that fail

- **Name**: `rbac_token_issue_latency_ms`
  - **Type**: HISTOGRAM
  - **Unit**: milliseconds
  - **Description**: Time to issue OAuth tokens

### 5. System Health
- **Name**: `system_health_status`
  - **Type**: GAUGE
  - **Unit**: binary (1=healthy, 0=unhealthy)
  - **Description**: Overall system health status

## Alert Rules

### Alert Rule 1: High Key Vault Error Rate
```
Rule ID: kv_error_rate_high
Condition: kek_vault_error_rate > 5%
Severity: ERROR
Window: 5 minutes
Channels: slack-ops, email-ops
```

### Alert Rule 2: Slow CryptoService
```
Rule ID: crypto_latency_high
Condition: crypto_encrypt_latency_ms (p95) > 500ms
Severity: WARNING
Window: 5 minutes
Channels: slack-ops
```

### Alert Rule 3: Audit Log Write Failures
```
Rule ID: audit_write_failures
Condition: audit_log_write_latency_ms (p99) > 1000ms
Severity: ERROR
Window: 5 minutes
Channels: slack-security, email-security
```

### Alert Rule 4: RBAC Auth Failures
```
Rule ID: rbac_auth_failures
Condition: rbac_auth_failure_rate > 10%
Severity: CRITICAL
Window: 5 minutes
Channels: slack-security, email-security, escalation
```

### Alert Rule 5: System Unhealthy
```
Rule ID: system_health_critical
Condition: system_health_status == 0
Severity: CRITICAL
Window: 1 minute
Channels: slack-security, email-security, escalation
```

## Kusto Query Language (KQL) Examples

### Query 1: Key Vault Performance Over Time
```kusto
customMetrics
| where name == "kek_vault_latency_ms"
| extend latency = todouble(value)
| summarize avg_latency=avg(latency), max_latency=max(latency), percentile_95=percentile(latency, 95)
  by bin(timestamp, 1m)
| render timechart
```

### Query 2: Error Rate Trends
```kusto
customMetrics
| where name in ("kek_vault_error_rate", "rbac_auth_failure_rate")
| extend error_rate = todouble(value)
| summarize avg_error_rate=avg(error_rate) by name, bin(timestamp, 5m)
| render columnchart
```

### Query 3: Audit Log Write Performance
```kusto
customMetrics
| where name == "audit_log_write_latency_ms"
| extend latency = todouble(value)
| summarize count=count(), avg=avg(latency), max=max(latency), p99=percentile(latency, 99)
  by bin(timestamp, 1h)
| render barchart
```

### Query 4: Alert History
```kusto
customEvents
| where name == "alert_fired"
| extend severity = tostring(customDimensions.severity), rule_id = tostring(customDimensions.rule_id)
| summarize alert_count=count() by severity, rule_id, bin(timestamp, 1h)
| sort by timestamp desc
```

### Query 5: Health Check Status
```kusto
customMetrics
| where name == "system_health_status"
| extend status = case(value == 1.0, "HEALTHY", value == 0.5, "DEGRADED", "UNHEALTHY")
| summarize last_status=any(status) by tostring(customDimensions.status)
```

## Setting Up Alerts in Azure Portal

### Step 1: Navigate to Application Insights
1. Go to Azure Portal (portal.azure.com)
2. Search for "Application Insights"
3. Select your KAKEHASHI Application Insights resource

### Step 2: Create Alert Rule
1. Click "Alerts" in the left menu
2. Click "Create" → "Alert rule"
3. Select "Custom log search"
4. Enter the metric query (see KQL examples above)
5. Set threshold and window (e.g., > 50.0 in last 5 minutes)
6. Click "Next"

### Step 3: Configure Notification
1. Select "Create new action group"
2. Name: "kakehashi-alerts"
3. Add notification:
   - Type: Email/SMS/Slack/Webhook
   - Slack webhook: Add your Slack webhook URL
   - Email recipient: ops@kakehashi.local
4. Click "Create"

### Step 4: Configure Alert Details
1. Alert rule name: "Key Vault Error Rate High"
2. Description: "Fires when Key Vault error rate exceeds 5% in 5-minute window"
3. Severity: High
4. Click "Create alert rule"

## Dashboard Setup

### Create Custom Dashboard
1. Go to Application Insights
2. Click "Dashboard" in left menu
3. Click "Edit" to customize
4. Add tiles:
   - **Metric 1**: Key Vault Latency (line chart)
   - **Metric 2**: Error Rates (stacked area)
   - **Metric 3**: Health Status (single value)
   - **Metric 4**: Alert Count (bar chart)
5. Save dashboard

## Health Check Execution

The system runs automatic health checks daily at **06:00 UTC** (15:00 JST) via GitHub Actions workflow `.github/workflows/health-check.yml`.

### Manual Health Check
```bash
python -m kakehashi.kek_wrapper.core.health_check_runner
```

### Health Check Output
```json
{
  "timestamp": "2026-10-29T06:00:00Z",
  "overall_status": "HEALTHY",
  "checks": {
    "azure_key_vault": {
      "status": "HEALTHY",
      "latency_ms": 42.5,
      "version_count": 5
    },
    "crypto_service": {
      "status": "HEALTHY",
      "roundtrip_latency_ms": 15.3
    },
    "audit_log_collector": {
      "status": "HEALTHY",
      "write_latency_ms": 8.2
    },
    "rbac_enforcer": {
      "status": "HEALTHY",
      "token_issue_and_verify": "OK"
    },
    "database": {
      "status": "HEALTHY",
      "query_latency_ms": 25.1
    }
  }
}
```

## Troubleshooting

### Issue: Alerts not firing
1. Check alert rule is enabled: `AlertRule.enabled == True`
2. Verify metric data is being sent: Query metric in KQL
3. Check action group configuration: Slack webhook, email recipient
4. Review alert rule threshold: May be too strict

### Issue: High latency alerts
1. Check Key Vault quotas and throttling limits
2. Review CryptoService performance logs
3. Monitor database connection pool
4. Check network latency to Azure services

### Issue: Authentication failures
1. Review RBAC token generation logs
2. Check JWT signing key rotation schedule
3. Verify RBAC policy configuration
4. Review audit log for DENIED events

## Integration with Other Systems

### Slack Integration
- Webhook: `https://hooks.slack.com/services/YOUR/WEBHOOK/URL`
- Channel: `#kakehashi-alerts`
- Format: Rich attachment with color-coded severity

### Email Integration
- Provider: SendGrid API
- Recipients: ops@kakehashi.local, security@kakehashi.local
- Template: HTML email with metric details

### Escalation
- PagerDuty: Integration for CRITICAL alerts
- Phone Call: Via Twilio for system-wide outages

## References

- [Azure Application Insights Documentation](https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview)
- [Kusto Query Language Reference](https://learn.microsoft.com/en-us/azure/kusto/query/)
- [KAKEHASHI Monitoring Service Code](/kakehashi/kek_wrapper/core/monitoring_service.py)
- [Alert Rules Configuration](/kakehashi/kek_wrapper/models/monitoring_models.py)

## Support

For questions or issues with monitoring:
1. Check alert rule logs in Application Insights
2. Review health check results in GitHub Actions
3. Contact: monitoring@kakehashi.local
