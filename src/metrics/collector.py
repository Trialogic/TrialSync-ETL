"""Prometheus metrics collector for ETL operations."""

import time
from typing import Optional

from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST

# Job execution metrics
jobs_total = Counter(
    "trialsync_jobs_total",
    "Total number of ETL jobs executed",
    ["job_id", "status"],
)

job_failures_total = Counter(
    "trialsync_job_failures_total",
    "Total number of job failures",
    ["job_id", "error_category"],
)

job_duration_seconds = Histogram(
    "trialsync_job_duration_seconds",
    "Job execution duration in seconds",
    ["job_id", "status"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),
)

records_loaded_total = Counter(
    "trialsync_records_loaded_total",
    "Total number of records loaded",
    ["job_id", "table"],
)

# API request metrics
api_requests_total = Counter(
    "trialsync_api_requests_total",
    "Total number of API requests",
    ["route", "method", "status_code"],
)

api_request_duration_seconds = Histogram(
    "trialsync_api_request_duration_seconds",
    "API request duration in seconds",
    ["route", "method"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10, 30),
)

# Database pool metrics
db_pool_in_use = Gauge(
    "trialsync_db_pool_in_use",
    "Number of database connections in use",
    ["component"],
)

db_pool_size = Gauge(
    "trialsync_db_pool_size",
    "Total size of database connection pool",
    ["component"],
)

db_pool_waiters = Gauge(
    "trialsync_db_pool_waiters",
    "Number of waiters for database connections",
    ["component"],
)

# Running jobs gauge
running_jobs = Gauge(
    "trialsync_running_jobs",
    "Number of currently running jobs",
)

# Service info
service_info = Info(
    "trialsync_build_info",
    "Build information",
)

# Uptime tracking
start_time = time.time()
uptime_seconds = Gauge(
    "trialsync_uptime_seconds",
    "Service uptime in seconds",
)


class MetricsCollector:
    """Collects and exposes Prometheus metrics for ETL operations."""

    def __init__(self):
        """Initialize metrics collector."""
        # Set service info
        try:
            import subprocess
            git_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
            ).decode().strip()[:7]
        except Exception:
            git_sha = "unknown"

        service_info.info({
            "service": "trialsync-etl",
            "version": "1.0.0",
            "git_sha": git_sha,
        })

        # Update uptime periodically (will be updated on /metrics requests)
        self._update_uptime()

    def _update_uptime(self):
        """Update uptime gauge."""
        uptime_seconds.set(time.time() - start_time)

    def record_job_execution(
        self,
        job_id: int,
        status: str,
        duration_seconds: float,
        records_loaded: int = 0,
        table: Optional[str] = None,
        error_category: Optional[str] = None,
    ):
        """Record a job execution.

        Args:
            job_id: Job ID
            status: Job status (success, failed, skipped)
            duration_seconds: Execution duration
            records_loaded: Number of records loaded
            table: Target table name
            error_category: Error category if failed (API, DB, Data, System)
        """
        jobs_total.labels(job_id=str(job_id), status=status).inc()
        job_duration_seconds.labels(job_id=str(job_id), status=status).observe(duration_seconds)

        if records_loaded > 0 and table:
            records_loaded_total.labels(job_id=str(job_id), table=table).inc(records_loaded)

        if status == "failed" and error_category:
            job_failures_total.labels(job_id=str(job_id), error_category=error_category).inc()

    def record_api_request(
        self,
        route: str,
        method: str,
        status_code: int,
        duration_seconds: float,
    ):
        """Record an API request.

        Args:
            route: API route
            method: HTTP method
            status_code: HTTP status code
            duration_seconds: Request duration
        """
        api_requests_total.labels(route=route, method=method, status_code=str(status_code)).inc()
        api_request_duration_seconds.labels(route=route, method=method).observe(duration_seconds)

    def update_running_jobs(self, count: int):
        """Update the number of running jobs.

        Args:
            count: Number of currently running jobs
        """
        running_jobs.set(count)

    def update_db_pool_metrics(
        self,
        component: str,
        in_use: int,
        pool_size: int,
        waiters: int = 0,
    ):
        """Update database pool metrics.

        Args:
            component: Component name (e.g., 'etl', 'api')
            in_use: Number of connections in use
            pool_size: Total pool size
            waiters: Number of waiters
        """
        db_pool_in_use.labels(component=component).set(in_use)
        db_pool_size.labels(component=component).set(pool_size)
        db_pool_waiters.labels(component=component).set(waiters)

    def get_metrics(self) -> tuple[bytes, str]:
        """Get Prometheus metrics in text format.

        Returns:
            Tuple of (metrics_bytes, content_type)
        """
        self._update_uptime()
        return generate_latest(), CONTENT_TYPE_LATEST

