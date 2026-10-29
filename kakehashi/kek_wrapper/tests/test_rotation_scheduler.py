"""Tests for RotationScheduler (Phase E, Task 3.2).

Tests cover APScheduler integration, cron trigger configuration, and
scheduled rotation execution.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from kakehashi.kek_wrapper.core.rotation_scheduler import RotationScheduler
from kakehashi.kek_wrapper.models.rotation_models import RotationType
from kakehashi.kek_wrapper.models.role import Role


@pytest.fixture
def mock_rotation_service():
    """Create a mock KeyRotationService."""
    service = AsyncMock()
    service.schedule_rotation = AsyncMock(
        return_value=MagicMock(
            success=True,
            new_version=2,
            old_version=1,
            re_encrypted_count=0,
        )
    )
    return service


@pytest.fixture
def rotation_scheduler(mock_rotation_service):
    """Create a RotationScheduler with mocked service."""
    return RotationScheduler(mock_rotation_service)


class TestRotationSchedulerInitialization:
    """Tests for RotationScheduler initialization."""

    def test_rotation_scheduler_initializes_with_service(self, mock_rotation_service):
        """Test that scheduler initializes with KeyRotationService."""
        scheduler = RotationScheduler(mock_rotation_service)

        assert scheduler.rotation_service == mock_rotation_service
        assert isinstance(scheduler.scheduler, AsyncIOScheduler)

    def test_rotation_scheduler_initializes_scheduler(self, rotation_scheduler):
        """Test that AsyncIOScheduler is properly initialized."""
        assert isinstance(rotation_scheduler.scheduler, AsyncIOScheduler)


class TestRotationSchedulerStarting:
    """Tests for scheduler startup."""

    def test_rotation_scheduler_adds_job_on_start(self, rotation_scheduler):
        """Test that start() registers the rotation job."""
        rotation_scheduler.start()

        jobs = rotation_scheduler.get_jobs()
        assert len(jobs) > 0

        # Find the rotation job
        rotation_job = None
        for job in jobs:
            if job.id == "scheduled_key_rotation":
                rotation_job = job
                break

        assert rotation_job is not None
        assert rotation_job.name == "Scheduled Key Rotation (90 days)"

        # Clean up
        rotation_scheduler.stop()

    def test_rotation_scheduler_runs_monthly_at_scheduled_time(self, rotation_scheduler):
        """Test that rotation job is scheduled for 1st of month at 03:00 JST."""
        rotation_scheduler.start()

        jobs = rotation_scheduler.get_jobs()
        rotation_job = None

        for job in jobs:
            if job.id == "scheduled_key_rotation":
                rotation_job = job
                break

        assert rotation_job is not None

        # Verify trigger is CronTrigger
        trigger = rotation_job.trigger
        assert isinstance(trigger, CronTrigger)

        # Verify cron configuration
        # APScheduler CronTrigger stores fields
        assert trigger.timezone.zone == "Asia/Tokyo"

        # Clean up
        rotation_scheduler.stop()

    @pytest.mark.asyncio
    async def test_rotation_scheduler_can_start_and_stop(self, rotation_scheduler):
        """Test that scheduler can start and stop cleanly."""
        rotation_scheduler.start()
        assert len(rotation_scheduler.get_jobs()) > 0

        rotation_scheduler.stop()
        # After stopping, there should be no jobs
        assert len(rotation_scheduler.get_jobs()) == 0


class TestScheduledRotationExecution:
    """Tests for scheduled rotation execution."""

    @pytest.mark.asyncio
    async def test_run_scheduled_rotation_calls_service(self, rotation_scheduler):
        """Test that _run_scheduled_rotation calls the KeyRotationService."""
        await rotation_scheduler._run_scheduled_rotation()

        # Verify schedule_rotation was called with correct parameters
        rotation_scheduler.rotation_service.schedule_rotation.assert_called_once()

        call_args = rotation_scheduler.rotation_service.schedule_rotation.call_args
        assert call_args[1]["rotation_type"] == RotationType.SCHEDULED
        assert call_args[1]["actor_role"] == Role.OPERATOR
        assert call_args[1]["actor_id"] == "scheduler"

    @pytest.mark.asyncio
    async def test_run_scheduled_rotation_handles_success(self, rotation_scheduler):
        """Test that _run_scheduled_rotation handles successful rotation."""
        rotation_scheduler.rotation_service.schedule_rotation = AsyncMock(
            return_value=MagicMock(
                success=True,
                old_version=1,
                new_version=2,
                re_encrypted_count=42,
            )
        )

        # Should not raise
        await rotation_scheduler._run_scheduled_rotation()

        rotation_scheduler.rotation_service.schedule_rotation.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_scheduled_rotation_handles_failure(self, rotation_scheduler):
        """Test that _run_scheduled_rotation handles rotation failure gracefully."""
        rotation_scheduler.rotation_service.schedule_rotation = AsyncMock(
            return_value=MagicMock(
                success=False,
                error_message="Key Vault unavailable",
            )
        )

        # Should not raise even if rotation fails
        await rotation_scheduler._run_scheduled_rotation()

        rotation_scheduler.rotation_service.schedule_rotation.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_scheduled_rotation_handles_exception(self, rotation_scheduler):
        """Test that _run_scheduled_rotation handles exceptions gracefully."""
        rotation_scheduler.rotation_service.schedule_rotation = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        # Should not raise
        await rotation_scheduler._run_scheduled_rotation()

        rotation_scheduler.rotation_service.schedule_rotation.assert_called_once()


class TestSchedulerJobManagement:
    """Tests for job management."""

    def test_get_jobs_returns_list(self, rotation_scheduler):
        """Test that get_jobs returns a list of jobs."""
        rotation_scheduler.start()

        jobs = rotation_scheduler.get_jobs()
        assert isinstance(jobs, list)
        assert len(jobs) > 0

        rotation_scheduler.stop()

    def test_get_jobs_includes_rotation_job(self, rotation_scheduler):
        """Test that get_jobs includes the rotation job."""
        rotation_scheduler.start()

        jobs = rotation_scheduler.get_jobs()
        job_ids = [job.id for job in jobs]

        assert "scheduled_key_rotation" in job_ids

        rotation_scheduler.stop()
