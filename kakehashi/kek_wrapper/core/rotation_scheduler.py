"""Rotation scheduler for automated key rotation (Phase E, Task 3.2).

Manages scheduling of key rotation tasks using APScheduler. Rotations are
scheduled to run monthly on the 1st day at 03:00 JST.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from kakehashi.kek_wrapper.models.rotation_models import RotationType
from kakehashi.kek_wrapper.models.role import Role

if TYPE_CHECKING:
    from kakehashi.kek_wrapper.core.key_rotation_service import KeyRotationService

logger = logging.getLogger(__name__)


class RotationScheduler:
    """Manages scheduled key rotation using APScheduler.

    Attributes:
        rotation_service: KeyRotationService instance.
        scheduler: AsyncIOScheduler instance for job management.
    """

    def __init__(self, key_rotation_service: KeyRotationService):
        """Initialize RotationScheduler.

        Args:
            key_rotation_service: KeyRotationService instance to use for rotations.
        """
        self.rotation_service = key_rotation_service
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        """Start the scheduler and register the rotation job.

        The job runs monthly on the 1st day at 03:00 JST (Asia/Tokyo timezone).
        """
        # Create cron trigger for 1st of month at 03:00 JST
        trigger = CronTrigger(
            day=1, hour=3, minute=0, timezone="Asia/Tokyo"
        )

        self.scheduler.add_job(
            func=self._run_scheduled_rotation,
            trigger=trigger,
            id="scheduled_key_rotation",
            name="Scheduled Key Rotation (90 days)",
        )

        logger.info("Starting rotation scheduler")
        self.scheduler.start()

    async def _run_scheduled_rotation(self) -> None:
        """Execute scheduled key rotation.

        Runs the rotation with OPERATOR role (system scheduled task).
        Failures are logged but do not prevent the scheduler from continuing.
        """
        logger.info("Running scheduled key rotation")

        try:
            result = await self.rotation_service.schedule_rotation(
                rotation_type=RotationType.SCHEDULED,
                actor_role=Role.OPERATOR,
                actor_id="scheduler",
            )

            if result.success:
                logger.info(
                    f"Scheduled rotation completed successfully: "
                    f"old_version={result.old_version}, "
                    f"new_version={result.new_version}, "
                    f"re_encrypted={result.re_encrypted_count}"
                )
            else:
                logger.error(
                    f"Scheduled rotation failed: {result.error_message}"
                )

        except Exception as e:
            logger.error(f"Scheduled rotation job failed: {e}", exc_info=True)

    def stop(self) -> None:
        """Stop the scheduler."""
        logger.info("Stopping rotation scheduler")
        self.scheduler.shutdown()

    def get_jobs(self) -> list:
        """Get list of scheduled jobs.

        Returns:
            List of APScheduler Job objects.
        """
        return self.scheduler.get_jobs()
