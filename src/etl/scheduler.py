from __future__ import annotations
from typing import Any, Dict, Iterable, Optional
import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = structlog.get_logger(__name__)

class JobScheduler:
    """
    Thin wrapper around APScheduler to schedule ETL jobs via cron expressions.

    Usage:
        scheduler = JobScheduler(orchestrator)
        scheduler.start()
        scheduler.schedule_job(1, "0 2 * * *")
    """

    def __init__(
        self,
        orchestrator: Any,
        timezone: str = "UTC",
        job_defaults: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._scheduler = BackgroundScheduler(timezone=timezone, job_defaults=job_defaults or {})

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("scheduler.started")

    def shutdown(self, wait: bool = True) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=wait)
            logger.info("scheduler.stopped")

    def schedule_job(self, job_id: int, cron_expression: str) -> None:
        trigger = CronTrigger.from_crontab(cron_expression)
        self._scheduler.add_job(
            self._run_job,
            trigger,
            id=f"etl-job-{job_id}",
            replace_existing=True,
            args=[job_id],
            coalesce=True,
            max_instances=1,
        )
        logger.info("scheduler.job_scheduled", job_id=job_id, cron=cron_expression)

    def unschedule_job(self, job_id: int) -> None:
        job = self._scheduler.get_job(f"etl-job-{job_id}")
        if job:
            job.remove()
            logger.info("scheduler.job_unscheduled", job_id=job_id)

    def _run_job(self, job_id: int) -> None:
        try:
            logger.info("scheduler.job_start", job_id=job_id)
            self._orchestrator.execute_job(job_id)
            logger.info("scheduler.job_end", job_id=job_id)
        except Exception as e:  # noqa: BLE001
            logger.exception("scheduler.job_error", job_id=job_id, error=str(e))

    # --- Loading schedules ---
    def refresh_from_rows(self, rows: Iterable[Dict[str, Any]]) -> int:
        """Idempotently refresh schedules from rows with keys: job_id, cron_expression, enabled."""
        count = 0
        for r in rows:
            if not r.get("enabled", True):
                self.unschedule_job(int(r["job_id"]))
                continue
            self.schedule_job(int(r["job_id"]), str(r["cron_expression"]))
            count += 1
        logger.info("scheduler.refreshed", scheduled=count)
        return count
