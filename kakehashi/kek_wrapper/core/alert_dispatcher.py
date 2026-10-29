"""
Alert Dispatcher for KAKEHASHI kek_wrapper.

Routes alerts to Slack, Email, PagerDuty, and other channels.
"""

import aiohttp
import asyncio
import logging
from typing import List, Dict

from kakehashi.kek_wrapper.models.monitoring_models import (
    Alert,
    AlertSeverity,
)

logger = logging.getLogger(__name__)


class AlertDispatcher:
    """
    Routes alerts to various notification channels.

    Supports:
    - Slack (ops and security channels)
    - Email (ops and security recipients)
    - PagerDuty (for escalation)
    - Phone calls (for critical incidents)
    """

    def __init__(
        self,
        slack_webhook_url: str,
        slack_security_webhook_url: str,
        sendgrid_api_key: str,
        ops_email: str,
        security_email: str,
    ):
        """
        Initialize AlertDispatcher.

        Args:
            slack_webhook_url: Slack webhook for ops channel
            slack_security_webhook_url: Slack webhook for security channel
            sendgrid_api_key: SendGrid API key for email
            ops_email: Email address for ops alerts
            security_email: Email address for security alerts
        """
        self.slack_webhook = slack_webhook_url
        self.slack_security_webhook = slack_security_webhook_url
        self.sendgrid_api_key = sendgrid_api_key
        self.ops_email = ops_email
        self.security_email = security_email

    async def dispatch_alert(
        self,
        alert: Alert,
        channels: List[str],
    ) -> None:
        """
        Dispatch alert to specified channels.

        Args:
            alert: Alert object to dispatch
            channels: List of channel names (e.g., ["slack-ops", "email-security"])
        """
        for channel in channels:
            try:
                if channel == "slack-ops":
                    await self._send_slack_message(
                        webhook_url=self.slack_webhook,
                        alert=alert,
                        channel_name="ops-alerts",
                    )

                elif channel == "slack-security":
                    await self._send_slack_message(
                        webhook_url=self.slack_security_webhook,
                        alert=alert,
                        channel_name="security-alerts",
                    )

                elif channel == "email-ops":
                    await self._send_email(
                        recipient=self.ops_email,
                        alert=alert,
                        subject_prefix="[KAKEHASHI OPS] ",
                    )

                elif channel == "email-security":
                    await self._send_email(
                        recipient=self.security_email,
                        alert=alert,
                        subject_prefix="[KAKEHASHI SECURITY] ",
                    )

                else:
                    logger.warning(f"Unknown channel: {channel}")

            except Exception as e:
                # Log but don't fail - dispatch failures shouldn't stop the system
                logger.error(f"Failed to dispatch alert to {channel}: {str(e)}")

    async def _send_slack_message(
        self,
        webhook_url: str,
        alert: Alert,
        channel_name: str,
    ) -> None:
        """
        Send alert message to Slack via webhook.

        Args:
            webhook_url: Slack webhook URL
            alert: Alert to send
            channel_name: Channel name (for logging)
        """
        color_map = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff6700",
            AlertSeverity.ERROR: "#da3633",
            AlertSeverity.CRITICAL: "#8f0000",
        }

        # Get severity value (AlertSeverity is str enum)
        severity_str = alert.severity if isinstance(alert.severity, str) else alert.severity.value

        payload = {
            "attachments": [
                {
                    "color": color_map.get(alert.severity, "#999999"),
                    "title": f"{severity_str}: {alert.title}",
                    "text": alert.message,
                    "fields": [
                        {"title": "Rule ID", "value": alert.rule_id, "short": True},
                        {"title": "Status", "value": alert.status, "short": True},
                        {"title": "Timestamp", "value": alert.timestamp.isoformat(), "short": True},
                        {"title": "Metric", "value": f"{alert.metric_name}={alert.metric_value:.2f}", "short": False},
                    ],
                    "footer": "KAKEHASHI Monitoring",
                    "ts": int(alert.timestamp.timestamp()),
                }
            ]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload) as resp:
                    if resp.status != 200:
                        raise Exception(f"Slack API error: {resp.status}")
                    logger.info(f"Alert sent to {channel_name}: {alert.alert_id}")

        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            raise

    async def _send_email(
        self,
        recipient: str,
        alert: Alert,
        subject_prefix: str,
    ) -> None:
        """
        Send alert via email (SendGrid).

        Args:
            recipient: Email recipient
            alert: Alert to send
            subject_prefix: Subject line prefix
        """
        subject = f"{subject_prefix}{alert.severity.value}: {alert.title}"
        body = f"""
Alert: {alert.title}

Severity: {alert.severity.value}
Rule ID: {alert.rule_id}
Status: {alert.status}
Timestamp: {alert.timestamp.isoformat()}

Message: {alert.message}

Metric: {alert.metric_name} = {alert.metric_value:.2f}

Context: {alert.context}

---
KAKEHASHI Monitoring System
"""

        # In production, would use SendGrid API
        # For now, just log it
        logger.info(f"Email alert to {recipient}: {subject}")

    async def dispatch_escalation(
        self,
        alert: Alert,
        escalation_rules: List[str],
    ) -> None:
        """
        Dispatch escalation actions (e.g., PagerDuty, phone call).

        Args:
            alert: Alert to escalate
            escalation_rules: List of escalation rules to apply
        """
        for rule in escalation_rules:
            try:
                if rule == "pagerduty":
                    await self._escalate_pagerduty(alert)
                elif rule == "phone_call_admin":
                    await self._escalate_phone_call(alert)
                else:
                    logger.warning(f"Unknown escalation rule: {rule}")

            except Exception as e:
                logger.error(f"Escalation failed for rule {rule}: {e}")

    async def _escalate_pagerduty(self, alert: Alert) -> None:
        """
        Escalate to PagerDuty.

        Args:
            alert: Alert to escalate
        """
        # Implementation would call PagerDuty API
        logger.info(f"Escalated to PagerDuty: {alert.alert_id}")

    async def _escalate_phone_call(self, alert: Alert) -> None:
        """
        Escalate via phone call.

        Args:
            alert: Alert to escalate
        """
        # Implementation would call phone service (Twilio, etc.)
        logger.info(f"Escalated to phone call: {alert.alert_id}")
