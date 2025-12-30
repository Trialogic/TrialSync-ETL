from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class ETLJob:
    id: int
    name: str
    source_endpoint: str
    target_table: str
    is_active: bool
    requires_parameters: bool
    parameter_source_table: Optional[str] = None
    parameter_source_column: Optional[str] = None


@dataclass
class ETLRunResult:
    job_id: int
    run_id: int
    status: str  # 'success' | 'failed'
    records_loaded: int
    duration_seconds: float
    error_message: Optional[str] = None


class ETLOrchestrator:
    """
    Minimal orchestrator for Week 1: execute a single non-parameterized job.
    Expects db to provide helper methods, api to provide get_odata, and loader to load_to_staging.
    """
    def __init__(self, db, api, loader, logger=None):
        self.db = db
        self.api = api
        self.loader = loader
        self.log = logger

    def execute_job(self, job_id: int) -> ETLRunResult:
        job = self._load_job_config(job_id)
        run_id = self._create_run_record(job_id)
        start = datetime.utcnow()
        try:
            if job.requires_parameters:
                raise NotImplementedError("Parameterized jobs handled in Week 2")
            records = self.api.get_odata(job.source_endpoint)
            self.loader.load_to_staging(job.target_table, records, job_id, run_id)
            self._update_run_record(run_id, 'success', len(records), None, start)
            return ETLRunResult(job_id, run_id, 'success', len(records), self._elapsed(start))
        except Exception as e:
            self._update_run_record(run_id, 'failed', 0, str(e), start)
            if self.log:
                self.log.error("job_failed", job_id=job_id, run_id=run_id, error=str(e))
            raise

    # --- DB helpers (delegates to db layer) ---
    def _load_job_config(self, job_id: int) -> ETLJob:
        row = self.db.get_job_config(job_id)
        return ETLJob(**row)

    def _create_run_record(self, job_id: int) -> int:
        return self.db.create_run(job_id)

    def _update_run_record(self, run_id: int, status: str, records: int, error: Optional[str], start: datetime) -> None:
        duration = self._elapsed(start)
        self.db.update_run(run_id, status=status, records_loaded=records, error_message=error, duration_seconds=duration)

    @staticmethod
    def _elapsed(start: datetime) -> float:
        return (datetime.utcnow() - start).total_seconds()
