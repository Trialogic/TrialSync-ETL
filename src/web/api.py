"""FastAPI web API for TrialSync ETL.

Provides REST API endpoints for all CLI operations.
"""

from typing import Optional

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.etl import ETLOrchestrator, ExecutionResult, JobExecutor
from src.metrics import get_metrics_collector

app = FastAPI(
    title="TrialSync ETL API",
    description="Web API for TrialSync ETL job management",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
web_dir = Path(__file__).parent.parent.parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")


@app.get("/ui")
async def serve_ui():
    """Serve the web UI."""
    ui_file = web_dir / "index.html"
    if ui_file.exists():
        return FileResponse(ui_file)
    return {"message": "Web UI not found"}


# Request/Response models
class RunJobRequest(BaseModel):
    """Request model for running a job."""

    dry_run: bool = False
    parameters: Optional[dict] = None


class RunJobResponse(BaseModel):
    """Response model for running a job."""

    run_id: int
    status: str
    records_loaded: int
    duration_seconds: float
    error_message: Optional[str] = None


class RunAllJobsResponse(BaseModel):
    """Response model for running all jobs."""

    total_jobs: int
    successful: int
    failed: int
    skipped: int
    results: dict[int, RunJobResponse]


class JobStatusResponse(BaseModel):
    """Response model for job status."""

    job_id: int
    name: str
    is_active: bool
    last_run_at: Optional[str] = None
    last_run_status: Optional[str] = None
    last_run_records: Optional[int] = None


class RunHistoryItem(BaseModel):
    """Model for run history item."""

    run_id: int
    job_id: int
    job_name: str
    run_status: str
    records_loaded: int
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None


class RetryJobRequest(BaseModel):
    """Request model for retrying a job."""

    dry_run: bool = False


class JobListItem(BaseModel):
    """Model for job list item."""

    id: int
    name: str
    source_endpoint: str
    target_table: str
    is_active: bool
    requires_parameters: bool
    last_run_status: Optional[str] = None
    last_run_records: Optional[int] = None
    schedule_cron: Optional[str] = None


class ScheduleRequest(BaseModel):
    """Request model for updating a job schedule."""

    schedule_cron: Optional[str] = None  # None or empty string removes schedule


class ScheduleResponse(BaseModel):
    """Response model for job schedule."""

    job_id: int
    job_name: str
    schedule_cron: Optional[str] = None
    next_run_time: Optional[str] = None
    is_scheduled: bool


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "TrialSync ETL API",
        "version": "1.0.0",
        "docs": "/docs",
        "ui": "/ui",
        "health": "/health",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/jobs/{job_id}/run", response_model=RunJobResponse)
async def run_job(job_id: int, request: RunJobRequest):
    """Execute a single ETL job.

    Args:
        job_id: Job ID to execute.
        request: Run request with optional dry_run and parameters.

    Returns:
        RunJobResponse with execution results.
    """
    try:
        executor = JobExecutor()
        result = executor.execute_job(
            job_id=job_id,
            dry_run=request.dry_run,
            parameters=request.parameters,
        )

        return RunJobResponse(
            run_id=result.run_id,
            status=result.status,
            records_loaded=result.records_loaded,
            duration_seconds=result.duration_seconds,
            error_message=result.error_message,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/jobs/run-all", response_model=RunAllJobsResponse)
async def run_all_jobs(request: RunJobRequest):
    """Execute all active ETL jobs.

    Args:
        request: Run request with optional dry_run.

    Returns:
        RunAllJobsResponse with execution results.
    """
    try:
        orchestrator = ETLOrchestrator()
        results = orchestrator.execute_all_active_jobs(dry_run=request.dry_run)

        # Convert results to response format
        response_results = {}
        successful = 0
        failed = 0
        skipped = 0

        for job_id, result in results.items():
            response_results[job_id] = RunJobResponse(
                run_id=result.run_id,
                status=result.status,
                records_loaded=result.records_loaded,
                duration_seconds=result.duration_seconds,
                error_message=result.error_message,
            )

            if result.status == "success":
                successful += 1
            elif result.status == "failed":
                failed += 1
            elif result.status == "skipped":
                skipped += 1

        return RunAllJobsResponse(
            total_jobs=len(results),
            successful=successful,
            failed=failed,
            skipped=skipped,
            results=response_results,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs", response_model=list[JobListItem])
async def list_jobs():
    """List all ETL jobs.

    Returns:
        List of JobListItem.
    """
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, source_endpoint, target_table, is_active,
                       requires_parameters, last_run_status, last_run_records, schedule_cron
                FROM dw_etl_jobs
                ORDER BY id
                """
            )

            jobs = cursor.fetchall()

            return [
                JobListItem(
                    id=job[0],
                    name=job[1],
                    source_endpoint=job[2],
                    target_table=job[3],
                    is_active=job[4],
                    requires_parameters=job[5],
                    last_run_status=job[6],
                    last_run_records=job[7],
                    schedule_cron=job[8] if len(job) > 8 else None,
                )
                for job in jobs
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: int):
    """Get job status.

    Args:
        job_id: Job ID.

    Returns:
        JobStatusResponse with job status.
    """
    try:
        orchestrator = ETLOrchestrator()
        status = orchestrator.get_job_status(job_id)

        if not status:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return JobStatusResponse(
            job_id=status["job_id"],
            name=status["name"],
            is_active=status["is_active"],
            last_run_at=str(status["last_run_at"]) if status["last_run_at"] else None,
            last_run_status=status["last_run_status"],
            last_run_records=status["last_run_records"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{job_id}/history", response_model=list[RunHistoryItem])
async def get_job_history(
    job_id: int,
    limit: int = 10,
    status: Optional[str] = None,
):
    """Get execution history for a job.

    Args:
        job_id: Job ID.
        limit: Maximum number of runs to return.
        status: Filter by status (running, success, failed).

    Returns:
        List of RunHistoryItem.
    """
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        with pool.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT r.id, r.job_id, j.name, r.run_status, r.records_loaded,
                       r.started_at, r.completed_at, r.duration_ms, r.error_message
                FROM dw_etl_runs r
                JOIN dw_etl_jobs j ON r.job_id = j.id
                WHERE r.job_id = %s
            """
            params = [job_id]

            if status:
                query += " AND r.run_status = %s"
                params.append(status)

            query += " ORDER BY r.started_at DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            runs = cursor.fetchall()

            return [
                RunHistoryItem(
                    run_id=run[0],
                    job_id=run[1],
                    job_name=run[2],
                    run_status=run[3],
                    records_loaded=run[4] or 0,
                    started_at=str(run[5]) if run[5] else None,
                    completed_at=str(run[6]) if run[6] else None,
                    duration_seconds=(run[7] // 1000) if run[7] else None,  # Convert ms to seconds
                    error_message=run[8],
                )
                for run in runs
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/runs", response_model=list[RunHistoryItem])
async def get_all_runs(
    limit: int = 10,
    job_id: Optional[int] = None,
    status: Optional[str] = None,
):
    """Get execution history for all jobs.

    Args:
        limit: Maximum number of runs to return.
        job_id: Filter by job ID.
        status: Filter by status (running, success, failed).

    Returns:
        List of RunHistoryItem.
    """
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        with pool.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT r.id, r.job_id, j.name, r.run_status, r.records_loaded,
                       r.started_at, r.completed_at, r.duration_ms, r.error_message
                FROM dw_etl_runs r
                JOIN dw_etl_jobs j ON r.job_id = j.id
                WHERE 1=1
            """
            params = []

            if job_id:
                query += " AND r.job_id = %s"
                params.append(job_id)

            if status:
                query += " AND r.run_status = %s"
                params.append(status)

            query += " ORDER BY r.started_at DESC LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            runs = cursor.fetchall()

            return [
                RunHistoryItem(
                    run_id=run[0],
                    job_id=run[1],
                    job_name=run[2],
                    run_status=run[3],
                    records_loaded=run[4] or 0,
                    started_at=str(run[5]) if run[5] else None,
                    completed_at=str(run[6]) if run[6] else None,
                    duration_seconds=(run[7] // 1000) if run[7] else None,  # Convert ms to seconds
                    error_message=run[8],
                )
                for run in runs
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/runs/{run_id}/retry", response_model=RunJobResponse)
async def retry_run(run_id: int, request: RetryJobRequest):
    """Retry a failed job run.

    Args:
        run_id: Run ID to retry.
        request: Retry request with optional dry_run.

    Returns:
        RunJobResponse with execution results.
    """
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        # Get run details
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT job_id, run_context
                FROM dw_etl_runs
                WHERE id = %s
                """,
                (run_id,),
            )

            run = cursor.fetchone()
            if not run:
                raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

            job_id, run_context = run
            import json

            parameters_dict = json.loads(run_context) if run_context else None

        # Execute job
        executor = JobExecutor()
        result = executor.execute_job(
            job_id=job_id,
            dry_run=request.dry_run,
            parameters=parameters_dict,
        )

        return RunJobResponse(
            run_id=result.run_id,
            status=result.status,
            records_loaded=result.records_loaded,
            duration_seconds=result.duration_seconds,
            error_message=result.error_message,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{job_id}/schedule", response_model=ScheduleResponse)
async def get_job_schedule(job_id: int):
    """Get job schedule.

    Args:
        job_id: Job ID.

    Returns:
        ScheduleResponse with schedule information.
    """
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, schedule_cron
                FROM dw_etl_jobs
                WHERE id = %s
                """,
                (job_id,),
            )

            job = cursor.fetchone()
            if not job:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

            schedule_cron = job[2]
            next_run_time = None
            is_scheduled = bool(schedule_cron)

            # Calculate next run time if scheduled
            if schedule_cron:
                try:
                    from croniter import croniter
                    from datetime import datetime
                    import pytz

                    cron = croniter(schedule_cron, datetime.now(pytz.UTC))
                    next_run_time = cron.get_next(datetime).isoformat()
                except ImportError:
                    # croniter not installed
                    pass
                except Exception:
                    # Invalid cron expression
                    pass

            return ScheduleResponse(
                job_id=job[0],
                job_name=job[1],
                schedule_cron=schedule_cron,
                next_run_time=next_run_time,
                is_scheduled=is_scheduled,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/jobs/{job_id}/schedule", response_model=ScheduleResponse)
async def update_job_schedule(job_id: int, request: ScheduleRequest):
    """Update job schedule.

    Args:
        job_id: Job ID.
        request: Schedule request with cron expression.

    Returns:
        ScheduleResponse with updated schedule information.
    """
    try:
        # Validate cron expression if provided
        schedule_cron = request.schedule_cron.strip() if request.schedule_cron else None
        if schedule_cron:
            try:
                from croniter import croniter
                from datetime import datetime
                import pytz

                # Validate cron expression
                croniter(schedule_cron, datetime.now(pytz.UTC))
            except ImportError:
                # croniter not installed, skip validation
                pass
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid cron expression: {str(e)}"
                )

        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        with pool.get_connection() as conn:
            cursor = conn.cursor()

            # Check if job exists
            cursor.execute(
                """
                SELECT id, name
                FROM dw_etl_jobs
                WHERE id = %s
                """,
                (job_id,),
            )

            job = cursor.fetchone()
            if not job:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

            # Update schedule
            cursor.execute(
                """
                UPDATE dw_etl_jobs
                SET schedule_cron = %s, updated_at = NOW()
                WHERE id = %s
                """,
                (schedule_cron, job_id),
            )
            conn.commit()

            # Calculate next run time
            next_run_time = None
            if schedule_cron:
                try:
                    from croniter import croniter
                    from datetime import datetime
                    import pytz

                    cron = croniter(schedule_cron, datetime.now(pytz.UTC))
                    next_run_time = cron.get_next(datetime).isoformat()
                except ImportError:
                    # croniter not installed
                    pass
                except Exception:
                    # Invalid cron expression
                    pass

            return ScheduleResponse(
                job_id=job[0],
                job_name=job[1],
                schedule_cron=schedule_cron,
                next_run_time=next_run_time,
                is_scheduled=bool(schedule_cron),
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/jobs/{job_id}/schedule")
async def delete_job_schedule(job_id: int):
    """Remove job schedule.

    Args:
        job_id: Job ID.

    Returns:
        Success message.
    """
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        with pool.get_connection() as conn:
            cursor = conn.cursor()

            # Check if job exists
            cursor.execute(
                """
                SELECT id
                FROM dw_etl_jobs
                WHERE id = %s
                """,
                (job_id,),
            )

            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

            # Remove schedule
            cursor.execute(
                """
                UPDATE dw_etl_jobs
                SET schedule_cron = NULL, updated_at = NOW()
                WHERE id = %s
                """,
                (job_id,),
            )
            conn.commit()

            return {"message": f"Schedule removed for job {job_id}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scheduler/status")
async def get_scheduler_status():
    """Get scheduler service status.

    Returns:
        Status information about the scheduler service.
    """
    try:
        # Check if scheduler process is running
        import subprocess
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        scheduler_running = (
            'scheduler' in result.stdout.lower() or 
            'APScheduler' in result.stdout or 
            'trialsync-etl scheduler' in result.stdout
        )

        # Get scheduled jobs count
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool
        
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) 
                FROM dw_etl_jobs 
                WHERE schedule_cron IS NOT NULL AND is_active = TRUE
                """
            )
            scheduled_count = cursor.fetchone()[0]

        return {
            "scheduler_running": scheduler_running,
            "scheduled_jobs": scheduled_count,
            "message": "Scheduler is running" if scheduler_running else "Scheduler is not running. Start with: trialsync-etl scheduler"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/metrics")
async def get_metrics():
    """Get Prometheus metrics.

    Returns:
        Prometheus metrics in text format.
    """
    try:
        collector = get_metrics_collector()
        metrics_bytes, content_type = collector.get_metrics()
        return Response(content=metrics_bytes, media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
