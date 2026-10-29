"""
Monitoring Service for KAKEHASHI kek_wrapper.

Handles metric collection, log event recording, and alert rule evaluation.
Integrates with Azure Application Insights and Log Analytics.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

from kakehashi.kek_wrapper.models.monitoring_models import (
    Metric,
    HealthStatus,
    AlertRule,
    Alert,
    AlertSeverity,
    MetricType,
)

logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Central monitoring service for KAKEHASHI system.

    Manages:
    - Metric collection and aggregation
    - Log event recording
    - Alert rule evaluation
    - Alert history tracking
    """

    def __init__(
        self,
        application_insights_key: str,
        log_analytics_workspace_id: str,
    ):
        """
        Initialize MonitoringService.

        Args:
            application_insights_key: Azure Application Insights instrumentation key
            log_analytics_workspace_id: Azure Log Analytics workspace ID
        """
        self.application_insights_key = application_insights_key
        self.log_analytics_workspace_id = log_analytics_workspace_id

        # Local storage for metrics and rules
        self._metrics: Dict[str, Metric] = {}
        self._alert_rules: Dict[str, AlertRule] = {}
        self._alerts_history: List[Alert] = []

        # Initialize Azure OpenTelemetry (in production)
        # configure_azure_monitor(
        #     connection_string=f"InstrumentationKey={application_insights_key}",
        # )
        # self.meter = metrics.get_meter("kakehashi.kek_wrapper")
        # self.logger = logs.get_logger("kakehashi.audit")

    async def emit_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        tags: Optional[Dict[str, str]] = None,
        unit: str = "count",
    ) -> None:
        """
        Emit a metric to Application Insights.

        Args:
            name: Metric name (e.g., "kek_vault_cache_hit_rate")
            value: Numeric value
            metric_type: Type of metric (COUNTER, GAUGE, HISTOGRAM, RATE)
            tags: Optional tags for filtering/grouping
            unit: Unit of measurement (default: "count")
        """
        metric = Metric(
            name=name,
            type=metric_type,
            value=value,
            unit=unit,
            timestamp=datetime.utcnow(),
            tags=tags or {},
        )

        # Store locally
        self._metrics[name] = metric

        # In production, would send to Application Insights via OpenTelemetry
        logger.debug(f"Emitted metric: {name}={value} ({metric_type.value})")

    async def emit_log_event(
        self,
        level: str,  # "INFO", "WARNING", "ERROR", "CRITICAL"
        event_type: str,  # e.g., "AUTH_FAILURE", "KEY_ROTATION_STARTED"
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit a log event to Log Analytics.

        Args:
            level: Log level (INFO, WARNING, ERROR, CRITICAL)
            event_type: Event type classification
            message: Log message
            context: Additional context data
        """
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "event_type": event_type,
            "message": message,
            "context": context or {},
        }

        # In production, would send to Log Analytics
        logger.log(
            level=self._level_to_int(level),
            msg=f"[{event_type}] {message}",
            extra={"context": context},
        )

    def register_alert_rule(self, rule: AlertRule) -> None:
        """
        Register an alert rule.

        Args:
            rule: AlertRule to register
        """
        self._alert_rules[rule.rule_id] = rule
        logger.info(f"Registered alert rule: {rule.rule_id} ({rule.name})")

    async def evaluate_alert_rules(self) -> List[Alert]:
        """
        Evaluate all registered alert rules.

        Returns:
            List of Alert objects for rules that fired
        """
        fired_alerts: List[Alert] = []

        for rule_id, rule in self._alert_rules.items():
            if not rule.enabled:
                continue

            # Get aggregated metric value for this rule
            aggregated_value = await self._aggregate_metric(
                metric_name=rule.name,
                window_minutes=rule.window_minutes,
            )

            # Check threshold
            if aggregated_value > rule.threshold_value:
                alert = Alert(
                    alert_id=f"alert_{int(datetime.utcnow().timestamp() * 1000)}_{rule_id}",
                    timestamp=datetime.utcnow(),
                    rule_id=rule_id,
                    severity=rule.severity,
                    title=f"{rule.name} exceeded threshold",
                    message=f"{rule.name} = {aggregated_value:.2f} (threshold: {rule.threshold_value})",
                    metric_value=aggregated_value,
                    metric_name=rule.name,
                    context={},
                    status="NEW",
                )

                fired_alerts.append(alert)
                self._alerts_history.append(alert)
                logger.warning(f"Alert fired: {alert.alert_id} for rule {rule_id}")

        return fired_alerts

    async def _aggregate_metric(
        self,
        metric_name: str,
        window_minutes: int,
    ) -> float:
        """
        Aggregate metric over a time window.

        Args:
            metric_name: Name of metric to aggregate
            window_minutes: Time window in minutes

        Returns:
            Aggregated metric value
        """
        # Get metric from local storage
        if metric_name not in self._metrics:
            return 0.0

        metric = self._metrics[metric_name]

        # In production, would query Application Insights with KQL
        # For now, return the latest value
        return metric.value

    async def get_metrics_summary(self) -> Dict[str, float]:
        """
        Get summary of important metrics for dashboard.

        Returns:
            Dictionary of metric name to value
        """
        return {
            "cache_hit_rate": self._get_latest_metric("kek_vault_cache_hit_rate"),
            "audit_log_latency_ms": self._get_latest_metric("audit_log_write_latency_ms"),
            "key_vault_error_rate": self._get_latest_metric("kek_vault_error_rate"),
            "rbac_auth_failure_rate": self._get_latest_metric("rbac_auth_failure_rate"),
            "average_request_latency_ms": self._get_latest_metric("request_latency_p95_ms"),
        }

    def _get_latest_metric(self, metric_name: str) -> float:
        """
        Get the latest value for a metric.

        Args:
            metric_name: Name of metric

        Returns:
            Latest metric value, or 0.0 if not found
        """
        if metric_name in self._metrics:
            return self._metrics[metric_name].value
        return 0.0

    def get_alert_history(self, rule_id: Optional[str] = None, limit: int = 100) -> List[Alert]:
        """
        Get alert history.

        Args:
            rule_id: Optional filter by rule ID
            limit: Maximum number of alerts to return

        Returns:
            List of alerts (most recent first)
        """
        history = self._alerts_history

        if rule_id:
            history = [a for a in history if a.rule_id == rule_id]

        # Return most recent first, limited by limit parameter
        return history[-limit:][::-1]

    @staticmethod
    def _level_to_int(level: str) -> int:
        """Convert log level string to int."""
        level_map = {
            "DEBUG": 10,
            "INFO": 20,
            "WARNING": 30,
            "ERROR": 40,
            "CRITICAL": 50,
        }
        return level_map.get(level.upper(), 20)
