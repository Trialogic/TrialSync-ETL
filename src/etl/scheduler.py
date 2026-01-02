"""ETL Job Scheduler.

Uses APScheduler to execute ETL jobs based on their cron schedules stored in the database.
"""

import time
from datetime import datetime
from typing import Optional

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from croniter import croniter
import pytz

from src.config import get_settings
from src.etl import JobExecutor
from src.db import get_pool

logger = structlog.get_logger(__name__)


class ETLScheduler:
    """Scheduler for ETL jobs using APScheduler."""

    def __init__(self, job_executor: Optional[JobExecutor] = None):
        """Initialize scheduler.

        Args:
            job_executor: JobExecutor instance. If None, creates one.
        """
        self.job_executor = job_executor or JobExecutor()
        self.scheduler = BackgroundScheduler(timezone=pytz.UTC)
        self.pool = get_pool()
        self.settings = get_settings()

    def load_scheduled_jobs(self) -> None:
        """Load all scheduled jobs from database and add them to scheduler."""
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, schedule_cron
                FROM dw_etl_jobs
                WHERE schedule_cron IS NOT NULL
                  AND is_active = TRUE
            """
            )

            jobs = cursor.fetchall()

            logger.info(
                "loading_scheduled_jobs",
                count=len(jobs),
            )

            for job_id, name, schedule_cron in jobs:
                try:
                    # Parse cron expression to validate
                    croniter(schedule_cron, datetime.now(pytz.UTC))

                    # Handle both 5-field and 6-field cron expressions
                    # APScheduler expects 5 fields (minute hour day month weekday)
                    # Some cron expressions have 6 fields (second minute hour day month weekday)
                    cron_parts = schedule_cron.strip().split()
                    if len(cron_parts) == 6:
                        # Remove seconds field (first field)
                        cron_5field = " ".join(cron_parts[1:])
                    elif len(cron_parts) == 5:
                        cron_5field = schedule_cron
                    else:
                        raise ValueError(f"Invalid cron format: {schedule_cron} (expected 5 or 6 fields)")

                    # Add job to scheduler
                    self.scheduler.add_job(
                        func=self._execute_job,
                        trigger=CronTrigger.from_crontab(cron_5field, timezone=pytz.UTC),
                        args=[job_id],
                        id=f"etl_job_{job_id}",
                        name=f"ETL: {name}",
                        replace_existing=True,
                        max_instances=1,  # Prevent overlapping runs
                    )

                    logger.info(
                        "job_scheduled",
                        job_id=job_id,
                        job_name=name,
                        schedule=schedule_cron,
                    )
                except Exception as e:
                    logger.error(
                        "failed_to_schedule_job",
                        job_id=job_id,
                        job_name=name,
                        schedule=schedule_cron,
                        error=str(e),
                    )

    def _execute_job(self, job_id: int) -> None:
        """Execute a scheduled ETL job.

        Args:
            job_id: Job ID to execute.
        """
        logger.info(
            "scheduled_job_starting",
            job_id=job_id,
        )

        try:
            result = self.job_executor.execute_job(
                job_id=job_id,
                dry_run=self.settings.dry_run,
            )

            logger.info(
                "scheduled_job_completed",
                job_id=job_id,
                run_id=result.run_id,
                status=result.status,
                records_loaded=result.records_loaded,
            )
        except Exception as e:
            logger.error(
                "scheduled_job_failed",
                job_id=job_id,
                error=str(e),
            )

    def start(self) -> None:
        """Start the scheduler."""
        self.load_scheduled_jobs()
        self.scheduler.start()
        logger.info(
            "scheduler_started",
            job_count=len(self.scheduler.get_jobs()),
        )

    def stop(self) -> None:
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("scheduler_stopped")

    def reload_jobs(self) -> None:
        """Reload scheduled jobs from database."""
        # Remove all existing jobs
        for job in self.scheduler.get_jobs():
            self.scheduler.remove_job(job.id)

        # Reload from database
        self.load_scheduled_jobs()

        logger.info(
            "scheduler_reloaded",
            job_count=len(self.scheduler.get_jobs()),
        )

    def get_scheduled_jobs(self) -> list[dict]:
        """Get list of currently scheduled jobs.

        Returns:
            List of job information dictionaries.
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            next_run = None
            if hasattr(job, 'next_run_time') and job.next_run_time:
                next_run = job.next_run_time.isoformat()
            jobs.append(
                {
                    "job_id": int(job.id.replace("etl_job_", "")),
                    "name": job.name,
                    "next_run_time": next_run,
                }
            )
        return jobs

