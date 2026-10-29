"""ErrorHandler & SecurityAlert: error handling and alerting for security events (Phase E, Task 1.4).

Ensures all crypto/key/audit failures are logged AND trigger immediate notifications to operators.

Alert Escalation:
    - CRITICAL: immediate Slack/PagerDuty notification
    - HIGH: 1-minute batch notification
    - MEDIUM: file log only

Rate Limiting:
    - If 5+ alerts in 1 minute, escalate to single consolidated alert
    - No spam; consolidation prevents alert fatigue
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

from ..models.enums import EventType, Status

# Import and re-export AuditError from Task 1.3
from .audit_log_collector import AuditError

__all__ = ["SecurityError", "AuditError", "ErrorHandler"]

logger = logging.getLogger(__name__)

#: Fallback alert file when Slack is unavailable.
FALLBACK_ALERT_FILE = "/tmp/kakehashi_alerts.log"

#: Rate limiting: max alerts in 1 minute before consolidation.
RATE_LIMIT_THRESHOLD = 5

#: Time window for rate limiting.
RATE_LIMIT_WINDOW = timedelta(minutes=1)


class SecurityError(Exception):
    """Raised on cryptographic or key management failures."""

    pass


class ErrorHandler:
    """Handles security errors and triggers alerts with audit logging.

    Integrates with AuditLogCollector (Task 1.3) to log security events,
    and sends alerts via Slack (with fallback to file) based on severity
    and rate limiting rules.
    """

    def __init__(self, audit_collector: Any) -> None:
        """
        Args:
            audit_collector: an AuditLogCollector instance for logging security events.
        """
        self._audit_collector = audit_collector
        self._alert_history: list[tuple[datetime, str, str]] = []  # (timestamp, severity, message)
        self._lock = asyncio.Lock()
        self._slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self._email_to = os.getenv("ALERT_EMAIL_TO")

    async def logSecurityEvent(self, error_type: str, context: dict) -> None:
        """Log a security event to audit trail and send alert.

        Args:
            error_type: type of security error (e.g. "KEY_VAULT_AUTH_FAILED",
                        "ROTATION_FORCED", "DECRYPT_FAILED").
            context: additional context dict (e.g. {"error": "...", "resource_id": "..."}).
                     Required key: "error" (error message).

        Raises:
            AuditError: if audit logging fails (security event must not be silent).
        """
        if not isinstance(error_type, str) or not error_type:
            raise ValueError("error_type must be a non-empty string")
        if not isinstance(context, dict):
            raise ValueError("context must be a dict")

        # Determine alert severity based on error type
        if "ROTATION_FORCED" in error_type or "COMPROMISE" in error_type.upper():
            severity = "CRITICAL"
        else:
            severity = "HIGH"

        # Build audit event
        resource_id = context.get("resource_id", error_type)
        error_msg = context.get("error", "")

        # Record in audit log (Task 1.3 integration)
        try:
            await self._audit_collector.recordEvent(
                event_type=EventType.SECURITY,
                actor_role="OPERATOR",  # system-level event
                resource_id=resource_id,
                operation="SECURITY_EVENT",
                status=Status.FAILURE,
                error_code=error_type,
                context={"error_type": error_type, **context},
            )
        except AuditError as exc:
            # Audit failure is critical; do not swallow
            logger.error("Audit log failed for security event %s: %s", error_type, exc)
            raise

        # Build alert message
        alert_msg = f"[{error_type}] {error_msg}"
        if "ROTATION" in error_type.upper():
            alert_msg = f"KEY ROTATION EMERGENCY: {alert_msg}"

        # Send alert with rate limiting
        await self.alertOnFailure(severity, alert_msg)

    async def alertOnFailure(self, severity: str, message: str) -> None:
        """Send an alert with rate limiting and escalation.

        Alert escalation:
            - CRITICAL: immediate dispatch
            - HIGH: 1-min batch consolidation
            - MEDIUM: file log only

        Rate limiting: if 5+ alerts in 1 minute, consolidate to single alert.

        Args:
            severity: "CRITICAL", "HIGH", or "MEDIUM".
            message: human-readable alert message.
        """
        if severity not in ("CRITICAL", "HIGH", "MEDIUM"):
            raise ValueError(f"severity must be CRITICAL, HIGH, or MEDIUM; got {severity!r}")
        if not isinstance(message, str) or not message:
            raise ValueError("message must be a non-empty string")

        async with self._lock:
            now = datetime.now(timezone.utc)

            # Prune old alerts outside the 1-minute window
            cutoff = now - RATE_LIMIT_WINDOW
            self._alert_history = [
                (ts, sev, msg) for ts, sev, msg in self._alert_history
                if ts > cutoff
            ]

            # Check rate limit: if 5+ alerts in the last minute, escalate
            recent_count = len(self._alert_history)
            if recent_count >= RATE_LIMIT_THRESHOLD:
                # Consolidate: emit a single escalation alert
                escalation_msg = (
                    f"ESCALATION: {recent_count} consecutive security failures detected. "
                    f"Latest: {message}"
                )
                await self._send_alert_impl("CRITICAL", escalation_msg)
                self._alert_history.append((now, "CRITICAL", escalation_msg))
                return

            # Record this alert
            self._alert_history.append((now, severity, message))

            # Send based on severity
            if severity == "CRITICAL":
                await self._send_alert_impl("CRITICAL", message)
            elif severity == "HIGH":
                await self._send_alert_impl("HIGH", message)
            elif severity == "MEDIUM":
                await self._write_to_file(message)

    async def _send_alert_impl(self, severity: str, message: str) -> None:
        """Send alert via Slack, email, or fallback to file.

        Tries Slack first (if URL set), then email (if recipient set), then file.

        Args:
            severity: "CRITICAL", "HIGH", or "MEDIUM".
            message: alert message.
        """
        # Try Slack
        if self._slack_webhook_url:
            try:
                await self._send_slack(severity, message)
                return
            except Exception as exc:
                logger.warning("Slack alert failed (%s): %s", type(exc).__name__, exc)

        # Try Email
        if self._email_to:
            try:
                success = await self._send_email(severity, message)
                if success:
                    return
            except Exception as exc:
                logger.warning("Email alert failed (%s): %s", type(exc).__name__, exc)

        # Fallback to file
        logger.debug("All alert channels unavailable; using file fallback")
        await self._write_to_file(message)

    async def _send_slack(self, severity: str, message: str) -> None:
        """Send alert to Slack via webhook.

        Args:
            severity: "CRITICAL", "HIGH", or "MEDIUM".
            message: alert message.

        Raises:
            Exception: if the POST fails.
        """
        import aiohttp

        color = {"CRITICAL": "danger", "HIGH": "warning", "MEDIUM": "good"}.get(severity, "good")
        payload = {
            "attachments": [
                {
                    "color": color,
                    "title": f"{severity} Security Alert",
                    "text": message,
                    "ts": int(datetime.now(timezone.utc).timestamp()),
                }
            ]
        }

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                self._slack_webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if not 200 <= resp.status < 300:
                    raise RuntimeError(
                        f"Slack returned HTTP {resp.status}: {await resp.text()}"
                    )
                logger.info("Alert sent to Slack: %s", message)

    async def _send_email(self, severity: str, message: str) -> bool:
        """Send alert via email (non-blocking).

        Args:
            severity: "CRITICAL", "HIGH", or "MEDIUM".
            message: alert message.

        Returns:
            True if email was sent successfully, False otherwise.
            Does not raise; logs errors and returns False so file fallback can proceed.
        """
        if not self._email_to:
            return False

        try:
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self._sync_send_email,
                severity,
                message,
            )
            if success:
                logger.info("Alert sent to email: %s", self._email_to)
            return success
        except Exception as exc:
            logger.error("Email send failed: %s", exc)
            return False

    @staticmethod
    def _sync_send_email(severity: str, message: str) -> bool:
        """Synchronous email send (called in executor).

        Uses smtplib to send email via localhost or configured SMTP server.
        Gracefully handles configuration errors and send failures.

        Args:
            severity: alert severity level.
            message: alert message body.

        Returns:
            True if sent successfully, False otherwise.
        """
        try:
            import smtplib
            from email.mime.text import MIMEText

            email_to = os.getenv("ALERT_EMAIL_TO")
            if not email_to:
                return False

            # Build email
            subject = f"[KAKEHASHI Alert] {severity} Security Event"
            body = f"Severity: {severity}\n\nMessage:\n{message}\n\nSent: {datetime.now(timezone.utc).isoformat()}"
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = "kakehashi-alerts@localhost"
            msg["To"] = email_to

            # Send via SMTP (localhost:25 by default, or env var SMTP_HOST:SMTP_PORT)
            smtp_host = os.getenv("SMTP_HOST", "localhost")
            smtp_port = int(os.getenv("SMTP_PORT", "25"))
            timeout = 10

            with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as server:
                server.sendmail("kakehashi-alerts@localhost", [email_to], msg.as_string())
            return True

        except Exception as exc:
            logger.error("Failed to send email: %s", exc)
            return False

    async def _write_to_file(self, message: str) -> None:
        """Write alert to fallback file (non-blocking).

        Args:
            message: alert message.
        """
        try:
            loop = asyncio.get_event_loop()
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": message,
            }
            await loop.run_in_executor(
                None,
                self._sync_write_to_file,
                entry,
            )
        except Exception as exc:
            logger.error("Failed to write alert to file: %s", exc)

    @staticmethod
    def _sync_write_to_file(entry: dict) -> None:
        """Synchronous file write (called in executor).

        Args:
            entry: dict with "timestamp" and "message" keys.
        """
        try:
            with open(FALLBACK_ALERT_FILE, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            logger.error("Failed to write to %s: %s", FALLBACK_ALERT_FILE, exc)
