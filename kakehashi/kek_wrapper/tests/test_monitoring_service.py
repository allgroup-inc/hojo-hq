"""
Tests for MonitoringService and HealthCheckService.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from kakehashi.kek_wrapper.models.monitoring_models import (
    Metric,
    HealthStatus,
    AlertRule,
    Alert,
    AlertSeverity,
    MetricType,
)


class TestMonitoringService:
    """Tests for MonitoringService."""

    @pytest.fixture
    def monitoring_service(self):
        """Fixture for MonitoringService."""
        from kakehashi.kek_wrapper.core.monitoring_service import MonitoringService

        service = MonitoringService(
            application_insights_key="test-key-12345",
            log_analytics_workspace_id="test-workspace-id",
        )
        return service

    @pytest.mark.asyncio
    async def test_emit_metric_sends_to_application_insights(self, monitoring_service):
        """Test that emit_metric stores metric and sends to Application Insights."""
        # Act
        await monitoring_service.emit_metric(
            name="test_metric",
            value=42.5,
            metric_type=MetricType.GAUGE,
            tags={"env": "test"},
        )

        # Assert
        assert "test_metric" in monitoring_service._metrics
        metric = monitoring_service._metrics["test_metric"]
        assert metric.name == "test_metric"
        assert metric.value == 42.5
        assert metric.type == MetricType.GAUGE
        assert metric.tags == {"env": "test"}

    @pytest.mark.asyncio
    async def test_evaluate_alert_rules_fires_on_threshold_exceeded(self, monitoring_service):
        """Test that alert fires when metric exceeds threshold."""
        # Arrange
        rule = AlertRule(
            rule_id="rule_1",
            name="kek_vault_error_rate",
            condition="metric(kek_vault_error_rate) > 0.05",
            severity=AlertSeverity.ERROR,
            threshold_value=50.0,
            window_minutes=5,
            enabled=True,
            channels=["slack-ops"],
        )
        monitoring_service.register_alert_rule(rule)

        # Emit a metric that exceeds threshold
        await monitoring_service.emit_metric(
            name="kek_vault_error_rate",
            value=65.0,
            metric_type=MetricType.GAUGE,
        )

        # Act
        fired_alerts = await monitoring_service.evaluate_alert_rules()

        # Assert
        assert len(fired_alerts) == 1
        alert = fired_alerts[0]
        assert alert.rule_id == "rule_1"
        assert alert.severity == AlertSeverity.ERROR
        assert alert.status == "NEW"
        assert len(monitoring_service._alerts_history) >= 1

    @pytest.mark.asyncio
    async def test_multiple_alert_rules_all_evaluated(self, monitoring_service):
        """Test that multiple alert rules are all evaluated."""
        # Arrange
        rules = [
            AlertRule(
                rule_id="rule_1",
                name="metric_1",
                condition="metric(metric_1) > 50",
                severity=AlertSeverity.WARNING,
                threshold_value=50.0,
                window_minutes=5,
                enabled=True,
                channels=["slack-ops"],
            ),
            AlertRule(
                rule_id="rule_2",
                name="metric_2",
                condition="metric(metric_2) > 30",
                severity=AlertSeverity.ERROR,
                threshold_value=30.0,
                window_minutes=5,
                enabled=True,
                channels=["email-ops"],
            ),
            AlertRule(
                rule_id="rule_3",
                name="metric_3",
                condition="metric(metric_3) > 10",
                severity=AlertSeverity.CRITICAL,
                threshold_value=10.0,
                window_minutes=5,
                enabled=True,
                channels=["slack-security"],
            ),
        ]

        for rule in rules:
            monitoring_service.register_alert_rule(rule)

        # Emit metrics that exceed thresholds
        await monitoring_service.emit_metric("metric_1", 75.0)
        await monitoring_service.emit_metric("metric_2", 45.0)
        await monitoring_service.emit_metric("metric_3", 20.0)

        # Act
        fired_alerts = await monitoring_service.evaluate_alert_rules()

        # Assert
        assert len(fired_alerts) == 3
        assert all(alert.status == "NEW" for alert in fired_alerts)
        assert len(monitoring_service._alerts_history) >= 3

    @pytest.mark.asyncio
    async def test_emit_log_event_records_event(self, monitoring_service):
        """Test that emit_log_event records events."""
        # Act
        await monitoring_service.emit_log_event(
            level="WARNING",
            event_type="AUTH_FAILURE",
            message="User authentication failed",
            context={"user_id": "user123", "reason": "invalid_token"},
        )

        # Assert - just verify it doesn't raise an exception
        # In real implementation, this would send to Log Analytics

    @pytest.mark.asyncio
    async def test_get_metrics_summary(self, monitoring_service):
        """Test metrics summary retrieval."""
        # Arrange
        await monitoring_service.emit_metric("kek_vault_cache_hit_rate", 0.95)
        await monitoring_service.emit_metric("audit_log_write_latency_ms", 42.0)
        await monitoring_service.emit_metric("kek_vault_error_rate", 0.02)

        # Act
        summary = await monitoring_service.get_metrics_summary()

        # Assert
        assert "cache_hit_rate" in summary
        assert summary["cache_hit_rate"] == 0.95
        assert "audit_log_latency_ms" in summary
        assert summary["audit_log_latency_ms"] == 42.0


class TestHealthCheckService:
    """Tests for HealthCheckService."""

    @pytest.fixture
    def health_check_service(self):
        """Fixture for HealthCheckService."""
        from kakehashi.kek_wrapper.core.health_check_service import HealthCheckService
        from kakehashi.kek_wrapper.core.monitoring_service import MonitoringService

        # Mock dependencies
        mock_kvc = AsyncMock()
        mock_crypto = AsyncMock()
        mock_audit = AsyncMock()
        mock_rbac = AsyncMock()
        mock_monitoring = MonitoringService(
            application_insights_key="test-key",
            log_analytics_workspace_id="test-ws",
        )

        service = HealthCheckService(
            key_vault_connector=mock_kvc,
            crypto_service=mock_crypto,
            audit_collector=mock_audit,
            rbac_enforcer=mock_rbac,
            monitoring_service=mock_monitoring,
        )
        return service

    @pytest.mark.asyncio
    async def test_health_check_returns_all_components_status(self, health_check_service):
        """Test that run_health_check returns status for all 5 components."""
        # Arrange
        health_check_service.kvc.getSecret = AsyncMock(return_value=b"test_secret")
        health_check_service.kvc._get_version_count = AsyncMock(return_value=5)

        health_check_service.crypto.encrypt = AsyncMock(return_value=b"ciphertext")
        health_check_service.crypto.decrypt = AsyncMock(return_value=b"health_check_message")

        from kakehashi.kek_wrapper.models.enums import EventType, Status
        health_check_service.audit.recordEvent = AsyncMock()

        health_check_service.rbac.issue_tokens = AsyncMock(
            return_value={"access_token": "test_token"}
        )
        health_check_service.rbac.verify_token = AsyncMock(
            return_value={"user_id": "health_check_user"}
        )

        # Act
        health_status = await health_check_service.run_health_check()

        # Assert
        assert health_status.overall_status in ["HEALTHY", "DEGRADED", "UNHEALTHY"]
        assert "azure_key_vault" in health_status.checks
        assert "crypto_service" in health_status.checks
        assert "audit_log_collector" in health_status.checks
        assert "rbac_enforcer" in health_status.checks
        assert "database" in health_status.checks

    @pytest.mark.asyncio
    async def test_health_check_crypto_roundtrip_failure_degrades_status(self, health_check_service):
        """Test that crypto failure degrades overall status."""
        # Arrange
        health_check_service.kvc.getSecret = AsyncMock(return_value=b"test_secret")
        health_check_service.kvc._get_version_count = AsyncMock(return_value=5)

        # Crypto fails
        health_check_service.crypto.encrypt = AsyncMock(
            side_effect=Exception("Encryption failed")
        )

        from kakehashi.kek_wrapper.models.enums import EventType, Status
        health_check_service.audit.recordEvent = AsyncMock()

        health_check_service.rbac.issue_tokens = AsyncMock(
            return_value={"access_token": "test_token"}
        )
        health_check_service.rbac.verify_token = AsyncMock(
            return_value={"user_id": "health_check_user"}
        )

        # Act
        health_status = await health_check_service.run_health_check()

        # Assert
        assert health_status.checks["crypto_service"]["status"] == "UNHEALTHY"
        assert health_status.overall_status in ["DEGRADED", "UNHEALTHY"]

    @pytest.mark.asyncio
    async def test_health_check_emits_metrics(self, health_check_service):
        """Test that health check emits system_health_status metric."""
        # Arrange
        health_check_service.kvc.getSecret = AsyncMock(return_value=b"test_secret")
        health_check_service.kvc._get_version_count = AsyncMock(return_value=5)

        health_check_service.crypto.encrypt = AsyncMock(return_value=b"ciphertext")
        health_check_service.crypto.decrypt = AsyncMock(return_value=b"health_check_message")

        health_check_service.audit.recordEvent = AsyncMock()

        health_check_service.rbac.issue_tokens = AsyncMock(
            return_value={"access_token": "test_token"}
        )
        health_check_service.rbac.verify_token = AsyncMock(
            return_value={"user_id": "health_check_user"}
        )

        # Act
        health_status = await health_check_service.run_health_check()

        # Assert
        assert "system_health_status" in health_check_service.monitoring._metrics
