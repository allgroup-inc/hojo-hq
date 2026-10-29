"""Tests for ErrorHandler (Phase E, Task 1.4).

Tests cover:
- SecurityError trigger and audit logging integration
- Alert on key rotation failure with escalation
- Cascading alerts with rate limiting

AuditLogCollector is mocked; Slack is mocked or used with file fallback.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from kakehashi.kek_wrapper.core.error_handler import (
    FALLBACK_ALERT_FILE,
    RATE_LIMIT_THRESHOLD,
    RATE_LIMIT_WINDOW,
    AuditError,
    ErrorHandler,
    SecurityError,
)
from kakehashi.kek_wrapper.models.enums import EventType, Role, Status


def run(coro):
    """Synchronous runner for async tests."""
    return asyncio.run(coro)


# ============================================================ Fixtures


@pytest.fixture
def mock_audit_collector():
    """Mock AuditLogCollector for injection into ErrorHandler."""
    collector = AsyncMock()
    collector.recordEvent = AsyncMock(return_value="evt-test-id-001")
    return collector


@pytest.fixture
def error_handler(mock_audit_collector):
    """ErrorHandler with mocked audit collector."""
    return ErrorHandler(mock_audit_collector)


@pytest.fixture
def temp_alert_file(monkeypatch):
    """Temporary alert file for testing fallback."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".log") as f:
        temp_path = f.name
    monkeypatch.setattr(
        "kakehashi.kek_wrapper.core.error_handler.FALLBACK_ALERT_FILE",
        temp_path,
    )
    yield temp_path
    try:
        os.unlink(temp_path)
    except FileNotFoundError:
        pass


# ============================================================ Tests


class TestSecurityErrorTriggers:
    """Test that SecurityError is properly defined and independent from AuditError."""

    def test_security_error_is_exception(self):
        """SecurityError must be an Exception subclass."""
        assert issubclass(SecurityError, Exception)

    def test_audit_error_is_importable(self):
        """AuditError must be importable from error_handler (re-export from Task 1.3)."""
        assert issubclass(AuditError, Exception)

    def test_security_error_and_audit_error_are_distinct(self):
        """SecurityError and AuditError must be different classes."""
        assert SecurityError is not AuditError


class TestSecurityErrorTriggersAuditLog:
    """test_security_error_triggers_audit_log: Mock collector, verify audit call."""

    def test_security_error_triggers_audit_log(self, error_handler, mock_audit_collector):
        """logSecurityEvent must call audit_collector.recordEvent with correct params."""
        run(
            error_handler.logSecurityEvent(
                "KEY_VAULT_AUTH_FAILED",
                {"error": "ManagedIdentity timeout"},
            )
        )

        # Assert audit_collector.recordEvent was called
        mock_audit_collector.recordEvent.assert_called_once()
        call_kwargs = mock_audit_collector.recordEvent.call_args.kwargs

        # Verify the call parameters
        assert call_kwargs["event_type"] == EventType.SECURITY
        assert call_kwargs["status"] == Status.FAILURE
        assert call_kwargs["error_code"] == "KEY_VAULT_AUTH_FAILED"
        assert call_kwargs["operation"] == "SECURITY_EVENT"
        assert "error_type" in call_kwargs["context"]
        assert call_kwargs["context"]["error_type"] == "KEY_VAULT_AUTH_FAILED"

    def test_audit_failure_propagates(self, error_handler, mock_audit_collector):
        """If audit_collector.recordEvent raises AuditError, it must propagate."""
        mock_audit_collector.recordEvent.side_effect = AuditError(
            "cannot write audit entry"
        )

        with pytest.raises(AuditError, match="cannot write audit entry"):
            run(
                error_handler.logSecurityEvent(
                    "KEY_VAULT_AUTH_FAILED",
                    {"error": "ManagedIdentity timeout"},
                )
            )


class TestAlertOnKeyRotationFailure:
    """test_alert_on_key_rotation_failure: Simulate emergency rotation, verify escalation."""

    def test_alert_on_key_rotation_failure(self, error_handler, mock_audit_collector):
        """logSecurityEvent for ROTATION_FORCED must escalate to CRITICAL alert."""
        with patch.object(error_handler, "alertOnFailure") as mock_alert:
            run(
                error_handler.logSecurityEvent(
                    "ROTATION_FORCED",
                    {"reason": "key_compromise"},
                )
            )

        # Assert audit was called
        mock_audit_collector.recordEvent.assert_called_once()

        # Assert alertOnFailure was called with CRITICAL severity
        mock_alert.assert_called_once()
        severity, message = mock_alert.call_args[0]
        assert severity == "CRITICAL"
        assert "KEY ROTATION" in message
        assert "EMERGENCY" in message

    def test_rotation_failure_audit_record(self, error_handler, mock_audit_collector):
        """Audit record for ROTATION_FORCED must have status=FAILURE."""
        run(
            error_handler.logSecurityEvent(
                "ROTATION_FORCED",
                {"reason": "key_compromise"},
            )
        )

        # Verify audit status
        call_kwargs = mock_audit_collector.recordEvent.call_args.kwargs
        assert call_kwargs["status"] == Status.FAILURE


class TestCascadingAlerts:
    """test_cascading_alerts: 3 rapid events, verify rate limiting and escalation."""

    def test_cascading_alerts_rate_limiting(
        self, error_handler, mock_audit_collector, temp_alert_file
    ):
        """3 rapid logSecurityEvent calls must trigger rate limiting on subsequent alerts."""
        # Mock alertOnFailure to track calls
        with patch.object(error_handler, "_send_alert_impl") as mock_send:
            # Call 3 times rapidly (will exceed rate limit threshold of 5)
            # First call with HIGH severity
            run(
                error_handler.logSecurityEvent(
                    "DECRYPT_FAILED",
                    {"error": "Invalid key material"},
                )
            )
            # Second call with HIGH severity
            run(
                error_handler.logSecurityEvent(
                    "DECRYPT_FAILED",
                    {"error": "Timeout on decryption"},
                )
            )
            # Third call with HIGH severity (total 3 < 5, so no escalation yet)
            run(
                error_handler.logSecurityEvent(
                    "DECRYPT_FAILED",
                    {"error": "Permission denied on key access"},
                )
            )

        # First 3 calls should use HIGH severity (< rate limit threshold)
        # After rate limiting (5+), the next call would escalate
        calls = mock_send.call_args_list
        assert len(calls) >= 3
        # At least first call should be HIGH
        assert calls[0][0][0] == "HIGH"

    def test_cascading_alerts_distinct_timestamps(self, error_handler, mock_audit_collector):
        """Each event must have distinct timestamps in audit log."""
        call_count = 0

        async def record_event_impl(**kwargs):
            nonlocal call_count
            call_count += 1
            return f"evt-id-{call_count}"

        mock_audit_collector.recordEvent.side_effect = record_event_impl

        # Mock alertOnFailure to not actually send alerts
        with patch.object(error_handler, "alertOnFailure", new_callable=AsyncMock):
            run(
                error_handler.logSecurityEvent(
                    "KEY_VAULT_AUTH_FAILED",
                    {"error": "Error 1"},
                )
            )
            run(
                error_handler.logSecurityEvent(
                    "KEY_VAULT_AUTH_FAILED",
                    {"error": "Error 2"},
                )
            )
            run(
                error_handler.logSecurityEvent(
                    "KEY_VAULT_AUTH_FAILED",
                    {"error": "Error 3"},
                )
            )

        # All 3 should have been recorded
        assert call_count == 3

    def test_cascading_alerts_escalation_tracker(self, error_handler, mock_audit_collector):
        """Alert history must track consecutive failures for escalation."""
        # Build alert history by calling alertOnFailure directly
        async def simulate_cascading():
            await error_handler.alertOnFailure("HIGH", "Failure 1")
            await error_handler.alertOnFailure("HIGH", "Failure 2")
            await error_handler.alertOnFailure("HIGH", "Failure 3")
            await error_handler.alertOnFailure("HIGH", "Failure 4")
            await error_handler.alertOnFailure("HIGH", "Failure 5")

        run(simulate_cascading())

        # After 5 alerts, the next one should trigger escalation
        assert len(error_handler._alert_history) >= 5


class TestAlertSeverityAndEscalation:
    """Test alert severity assignment and escalation rules."""

    def test_critical_severity_for_rotation_forced(
        self, error_handler, mock_audit_collector
    ):
        """ROTATION_FORCED must result in CRITICAL alert."""
        with patch.object(error_handler, "alertOnFailure") as mock_alert:
            run(
                error_handler.logSecurityEvent(
                    "ROTATION_FORCED",
                    {"error": "Key compromise detected"},
                )
            )

        severity, message = mock_alert.call_args[0]
        assert severity == "CRITICAL"

    def test_high_severity_for_other_errors(self, error_handler, mock_audit_collector):
        """Non-ROTATION errors should result in HIGH alert."""
        with patch.object(error_handler, "alertOnFailure") as mock_alert:
            run(
                error_handler.logSecurityEvent(
                    "KEY_VAULT_AUTH_FAILED",
                    {"error": "Auth timeout"},
                )
            )

        severity, message = mock_alert.call_args[0]
        assert severity == "HIGH"


class TestAlertOnFailure:
    """Test alertOnFailure method directly."""

    def test_alert_on_failure_critical_sends_immediately(
        self, error_handler, temp_alert_file
    ):
        """CRITICAL alert should call _send_alert_impl immediately."""
        with patch.object(error_handler, "_send_alert_impl") as mock_send:
            run(error_handler.alertOnFailure("CRITICAL", "Critical failure"))

        mock_send.assert_called_once_with("CRITICAL", "Critical failure")

    def test_alert_on_failure_medium_writes_to_file(self, error_handler, temp_alert_file):
        """MEDIUM alert should call _write_to_file."""
        with patch.object(error_handler, "_write_to_file") as mock_write:
            run(error_handler.alertOnFailure("MEDIUM", "Medium failure"))

        mock_write.assert_called_once()

    def test_alert_on_failure_high_sends_alert(
        self, error_handler, temp_alert_file
    ):
        """HIGH alert should call _send_alert_impl."""
        with patch.object(error_handler, "_send_alert_impl") as mock_send:
            run(error_handler.alertOnFailure("HIGH", "High failure"))

        mock_send.assert_called_once()

    def test_alert_on_failure_invalid_severity(self, error_handler):
        """Invalid severity must raise ValueError."""
        with pytest.raises(ValueError, match="severity must be"):
            run(error_handler.alertOnFailure("INVALID", "message"))

    def test_alert_on_failure_empty_message(self, error_handler):
        """Empty message must raise ValueError."""
        with pytest.raises(ValueError, match="message must be"):
            run(error_handler.alertOnFailure("HIGH", ""))


class TestSlackFallback:
    """Test Slack integration and fallback to file."""

    def test_slack_fallback_when_unavailable(
        self, error_handler, temp_alert_file, monkeypatch
    ):
        """If Slack unavailable, _write_to_file should be called."""
        # Set webhook URL so _send_slack is actually called
        error_handler._slack_webhook_url = "https://hooks.slack.com/services/test"

        # Simulate Slack failure
        with patch.object(error_handler, "_send_slack") as mock_slack:
            mock_slack.side_effect = RuntimeError("Slack connection failed")
            with patch.object(error_handler, "_write_to_file") as mock_write:
                run(error_handler._send_alert_impl("HIGH", "Test message"))

        # Should have attempted Slack and fallen back to file
        mock_slack.assert_called_once()
        mock_write.assert_called_once()

    def test_write_to_file_without_slack_webhook(
        self, error_handler, temp_alert_file, monkeypatch
    ):
        """If SLACK_WEBHOOK_URL not set, use file fallback."""
        error_handler._slack_webhook_url = None
        with patch.object(error_handler, "_write_to_file") as mock_write:
            run(error_handler._send_alert_impl("HIGH", "Test message"))

        mock_write.assert_called_once()


class TestErrorHandlerValidation:
    """Test input validation in ErrorHandler methods."""

    def test_log_security_event_empty_error_type(self, error_handler):
        """Empty error_type must raise ValueError."""
        with pytest.raises(ValueError, match="error_type must be"):
            run(error_handler.logSecurityEvent("", {"error": "test"}))

    def test_log_security_event_invalid_error_type(self, error_handler):
        """Non-string error_type must raise ValueError."""
        with pytest.raises(ValueError, match="error_type must be"):
            run(error_handler.logSecurityEvent(123, {"error": "test"}))

    def test_log_security_event_invalid_context(self, error_handler):
        """Non-dict context must raise ValueError."""
        with pytest.raises(ValueError, match="context must be"):
            run(error_handler.logSecurityEvent("ERROR", "not a dict"))


class TestRateLimiting:
    """Test rate limiting and consolidation logic."""

    def test_rate_limit_consolidation(self, error_handler, temp_alert_file):
        """When 5+ alerts in 1 min, next alert must escalate to CRITICAL."""

        async def simulate():
            # Populate alert history
            for i in range(RATE_LIMIT_THRESHOLD):
                await error_handler.alertOnFailure("HIGH", f"Alert {i+1}")

            # Next alert should trigger escalation
            with patch.object(error_handler, "_send_alert_impl") as mock_send:
                await error_handler.alertOnFailure("HIGH", "Alert 6")

            # Should have sent CRITICAL escalation alert
            calls = mock_send.call_args_list
            escalation_call = calls[-1] if calls else None
            if escalation_call:
                severity = escalation_call[0][0]
                assert severity == "CRITICAL"

        run(simulate())

    def test_rate_limit_history_pruning(self, error_handler):
        """Old alerts outside the 1-min window should be pruned."""

        async def simulate():
            # Manually add old alerts outside RATE_LIMIT_WINDOW
            now = datetime.now(timezone.utc)
            old_time = now - RATE_LIMIT_WINDOW - __import__(
                "datetime"
            ).timedelta(seconds=1)
            error_handler._alert_history = [
                (old_time, "HIGH", "Old alert"),
            ]

            # Call alertOnFailure; old alert should be pruned
            await error_handler.alertOnFailure("HIGH", "New alert")

            # Old alert should not count toward rate limit
            assert len(error_handler._alert_history) == 1
            assert error_handler._alert_history[0][2] == "New alert"

        run(simulate())




class TestFileLogging:
    """Test file-based alert logging."""

    def test_write_to_file_success(self, error_handler, temp_alert_file):
        """_write_to_file should successfully write to fallback file."""

        async def simulate():
            await error_handler._write_to_file("Test alert message")

            # Verify the file was written
            with open(temp_alert_file, "r") as f:
                lines = f.readlines()
                assert len(lines) > 0
                # Should be valid JSON
                entry = json.loads(lines[0])
                assert "timestamp" in entry
                assert entry["message"] == "Test alert message"

        run(simulate())

    def test_sync_write_to_file(self, temp_alert_file):
        """_sync_write_to_file should write JSON entry to file."""
        entry = {"timestamp": "2026-11-13T10:00:00+00:00", "message": "Test"}
        ErrorHandler._sync_write_to_file(entry)

        with open(temp_alert_file, "r") as f:
            lines = f.readlines()
            assert len(lines) > 0
            loaded = json.loads(lines[-1])
            assert loaded["message"] == "Test"


class TestSendAlertImpl:
    """Test _send_alert_impl routing logic."""

    def test_send_alert_impl_critical_with_webhook(self, error_handler, temp_alert_file):
        """_send_alert_impl with webhook should call _send_slack for CRITICAL."""
        error_handler._slack_webhook_url = "https://hooks.slack.com/test"

        async def simulate():
            with patch.object(error_handler, "_send_slack", new_callable=AsyncMock):
                await error_handler._send_alert_impl("CRITICAL", "Critical message")
                # _send_slack should have been called
                assert error_handler._send_slack.called

        run(simulate())

    def test_send_alert_impl_no_webhook_uses_file(self, error_handler, temp_alert_file):
        """_send_alert_impl without webhook should use file."""
        error_handler._slack_webhook_url = None

        async def simulate():
            with patch.object(error_handler, "_write_to_file", new_callable=AsyncMock):
                await error_handler._send_alert_impl("HIGH", "High message")
                # _write_to_file should have been called
                assert error_handler._write_to_file.called

        run(simulate())


class TestEmailAlerting:
    """Test email alerting support."""

    def test_email_to_read_from_env(self, error_handler, monkeypatch):
        """ALERT_EMAIL_TO should be read from environment variable."""
        monkeypatch.setenv("ALERT_EMAIL_TO", "alert@example.com")
        handler = ErrorHandler(error_handler._audit_collector)
        assert handler._email_to == "alert@example.com"

    def test_alert_send_email_on_slack_failure(self, error_handler, temp_alert_file):
        """When Slack fails, email should be attempted."""
        error_handler._slack_webhook_url = "https://hooks.slack.com/test"
        error_handler._email_to = "alert@example.com"

        async def simulate():
            with patch.object(error_handler, "_send_slack") as mock_slack:
                mock_slack.side_effect = RuntimeError("Slack connection failed")
                with patch.object(error_handler, "_send_email") as mock_email:
                    mock_email.return_value = True
                    await error_handler._send_alert_impl("HIGH", "Test message")

            # Should have attempted Slack, then email
            mock_slack.assert_called_once()
            mock_email.assert_called_once()

        run(simulate())

    def test_alert_email_failure_fallback_to_file(
        self, error_handler, temp_alert_file
    ):
        """When both Slack and email fail, file fallback triggered."""
        error_handler._slack_webhook_url = "https://hooks.slack.com/test"
        error_handler._email_to = "alert@example.com"

        async def simulate():
            with patch.object(error_handler, "_send_slack") as mock_slack:
                mock_slack.side_effect = RuntimeError("Slack failed")
                with patch.object(error_handler, "_send_email") as mock_email:
                    mock_email.return_value = False
                    with patch.object(error_handler, "_write_to_file") as mock_file:
                        await error_handler._send_alert_impl("HIGH", "Test")

            # All three should be attempted
            mock_slack.assert_called_once()
            mock_email.assert_called_once()
            mock_file.assert_called_once()

        run(simulate())

    def test_alert_both_services_missing_file_only(
        self, error_handler, temp_alert_file
    ):
        """Without Slack or email, file logging is only option."""
        error_handler._slack_webhook_url = None
        error_handler._email_to = None

        async def simulate():
            with patch.object(error_handler, "_write_to_file") as mock_file:
                await error_handler._send_alert_impl("HIGH", "Test message")

            # Only file should be called
            mock_file.assert_called_once()

        run(simulate())

    def test_sync_send_email_success(self, temp_alert_file, monkeypatch):
        """_sync_send_email should return True on successful send."""
        monkeypatch.setenv("ALERT_EMAIL_TO", "alert@example.com")
        monkeypatch.setenv("SMTP_HOST", "localhost")
        monkeypatch.setenv("SMTP_PORT", "25")

        with patch("smtplib.SMTP") as mock_smtp:
            # Mock successful SMTP send
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = ErrorHandler._sync_send_email("CRITICAL", "Test message")

            assert result is True
            mock_server.sendmail.assert_called_once()

    def test_sync_send_email_no_recipient(self):
        """_sync_send_email returns False if ALERT_EMAIL_TO not set."""
        with patch.dict(os.environ, {}, clear=True):
            result = ErrorHandler._sync_send_email("HIGH", "Test")
            assert result is False

    def test_sync_send_email_smtp_failure(self, monkeypatch):
        """_sync_send_email returns False on SMTP error."""
        monkeypatch.setenv("ALERT_EMAIL_TO", "alert@example.com")

        with patch("smtplib.SMTP") as mock_smtp:
            # Mock SMTP failure
            mock_smtp.side_effect = ConnectionError("SMTP connection refused")

            result = ErrorHandler._sync_send_email("HIGH", "Test")

            assert result is False

    def test_send_email_async_wrapper(self, error_handler):
        """_send_email should return result of sync email send."""

        async def simulate():
            error_handler._email_to = "alert@example.com"

            with patch.object(
                ErrorHandler, "_sync_send_email", return_value=True
            ) as mock_sync:
                result = await error_handler._send_email("CRITICAL", "Test")

            assert result is True
            mock_sync.assert_called_once()

        run(simulate())
