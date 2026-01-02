"""FastAPI web API for TrialSync ETL.

Provides REST API endpoints for all CLI operations.
"""

import time
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
    last_run_at: Optional[str] = None
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
                       requires_parameters, last_run_status, last_run_records, last_run_at, schedule_cron
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
                    last_run_at=str(job[8]) if job[8] else None,
                    schedule_cron=job[9] if len(job) > 9 else None,
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
    """Retry a failed or timed-out job run.

    If the run has a checkpoint, it will resume from where it left off.
    Otherwise, it will start a new run.

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
                SELECT job_id, run_status, run_context
                FROM dw_etl_runs
                WHERE id = %s
                """,
                (run_id,),
            )

            run = cursor.fetchone()
            if not run:
                raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

            job_id, run_status, run_context = run
            import json

            # Check if there's a checkpoint
            has_checkpoint = False
            parameters_dict = None
            if run_context:
                try:
                    context_dict = json.loads(run_context)
                    if "checkpoint" in context_dict:
                        has_checkpoint = True
                    # Extract parameters (not checkpoint)
                    if "checkpoint" not in context_dict:
                        parameters_dict = context_dict
                except (json.JSONDecodeError, TypeError):
                    # If not valid JSON, treat as parameters
                    parameters_dict = json.loads(run_context) if run_context else None

        # Execute job with resume if checkpoint exists
        executor = JobExecutor()
        result = executor.execute_job(
            job_id=job_id,
            dry_run=request.dry_run,
            parameters=parameters_dict,
            resume_from_checkpoint=has_checkpoint,
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


# ============================================================================
# Transformation Procedures API
# ============================================================================

class TransformationProcedure(BaseModel):
    """Model for transformation procedure."""

    name: str
    description: Optional[str] = None
    last_run_at: Optional[str] = None
    last_run_status: Optional[str] = None
    schedule_cron: Optional[str] = None
    is_scheduled: bool = False
    next_run_time: Optional[str] = None


class ExecuteTransformationRequest(BaseModel):
    """Request model for executing a transformation procedure."""

    procedure_name: str


class ExecuteTransformationResponse(BaseModel):
    """Response model for executing a transformation procedure."""

    run_id: int
    procedure_name: str
    status: str
    rows_affected: Optional[int] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    execution_log: Optional[str] = None


class TransformationRunHistory(BaseModel):
    """Model for transformation run history."""

    id: int
    procedure_name: str
    run_status: str
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    rows_affected: Optional[int] = None
    error_message: Optional[str] = None


class TransformationScheduleRequest(BaseModel):
    """Request model for updating transformation schedule."""

    schedule_cron: Optional[str] = None
    is_active: bool = True


@app.get("/transformations", response_model=list[TransformationProcedure])
async def list_transformations():
    """List all transformation procedures.

    Returns:
        List of TransformationProcedure.
    """
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        # Get all stored procedures that match transformation pattern
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # First check if transformation tables exist
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'dw_transformation_schedules'
                )
            """)
            tables_exist = cursor.fetchone()[0]
            
            # Query procedures - simplified query
            cursor.execute(
                """
                SELECT 
                    r.routine_name,
                    (SELECT obj_description(oid, 'pg_proc') 
                     FROM pg_proc 
                     WHERE proname = r.routine_name 
                     AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                     LIMIT 1) as description
                FROM information_schema.routines r
                WHERE r.routine_schema = 'public'
                  AND r.routine_type = 'PROCEDURE'
                  AND (
                      r.routine_name LIKE 'load_dw_dim%'
                      OR r.routine_name LIKE 'load_dw_fact%'
                      OR r.routine_name LIKE 'load_all_new%'
                  )
                ORDER BY r.routine_name
                """
            )
            procedures = cursor.fetchall()

            # Get schedule and last run info
            result = []
            for proc_name, description in procedures:
                schedule_cron = None
                is_scheduled = False
                last_run_at = None
                last_run_status = None
                next_run_time = None
                
                # Get schedule (only if table exists)
                if tables_exist:
                    try:
                        cursor.execute(
                            """
                            SELECT schedule_cron, is_active, last_run_at, last_run_status, next_run_time
                            FROM dw_transformation_schedules
                            WHERE procedure_name = %s
                            """,
                            (proc_name,),
                        )
                        schedule_row = cursor.fetchone()

                        if schedule_row:
                            schedule_cron = schedule_row[0]
                            is_scheduled = bool(schedule_row[1]) and bool(schedule_cron)
                            last_run_at = str(schedule_row[2]) if schedule_row[2] else None
                            last_run_status = schedule_row[3]
                            next_run_time = str(schedule_row[4]) if schedule_row[4] else None
                    except Exception as e:
                        # Table might not exist or have wrong schema, continue without schedule info
                        # Log error but don't fail the entire request
                        import structlog
                        logger = structlog.get_logger(__name__)
                        logger.warning("error_loading_schedule", procedure=proc_name, error=str(e))

                # If no schedule record exists, check last run from history (only if table exists)
                if not last_run_at and tables_exist:
                    try:
                        cursor.execute(
                            """
                            SELECT started_at, run_status
                            FROM dw_transformation_runs
                            WHERE procedure_name = %s
                            ORDER BY started_at DESC
                            LIMIT 1
                            """,
                            (proc_name,),
                        )
                        last_run = cursor.fetchone()
                        if last_run:
                            last_run_at = str(last_run[0])
                            last_run_status = last_run[1]
                    except Exception:
                        # Table might not exist, continue without history
                        pass

                result.append(
                    TransformationProcedure(
                        name=proc_name,
                        description=description,
                        last_run_at=last_run_at,
                        last_run_status=last_run_status,
                        schedule_cron=schedule_cron,
                        is_scheduled=is_scheduled,
                        next_run_time=next_run_time,
                    )
                )

            return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Error loading transformations: {str(e)}\n\nDetails: {error_details}"
        )


@app.post("/transformations/{procedure_name}/execute", response_model=ExecuteTransformationResponse)
async def execute_transformation(procedure_name: str):
    """Execute a transformation procedure manually.

    Args:
        procedure_name: Name of the procedure to execute.

    Returns:
        ExecuteTransformationResponse with execution results.
    """
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        # Validate procedure exists
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT routine_name
                FROM information_schema.routines
                WHERE routine_schema = 'public'
                  AND routine_type = 'PROCEDURE'
                  AND routine_name = %s
                """,
                (procedure_name,),
            )
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=404, detail=f"Transformation procedure '{procedure_name}' not found"
                )

            # Create run record
            cursor.execute(
                """
                INSERT INTO dw_transformation_runs (procedure_name, run_status, started_at)
                VALUES (%s, 'running', NOW())
                RETURNING id
                """,
                (procedure_name,),
            )
            run_id = cursor.fetchone()[0]
            conn.commit()

        # Execute procedure and capture output
        import io
        import sys
        from contextlib import redirect_stdout

        execution_log = io.StringIO()
        rows_affected = None
        error_message = None
        status = "success"
        duration_seconds = None
        start_time = time.time()

        try:
            with pool.get_connection() as conn:
                # Set client_min_messages to capture NOTICE messages
                cursor = conn.cursor()
                cursor.execute("SET client_min_messages TO NOTICE")

                # Capture procedure output
                # Note: PostgreSQL RAISE NOTICE messages go to stderr, not stdout
                # We'll need to use a different approach - log to a table or use plpgsql_check
                cursor.execute(f"CALL {procedure_name}()")
                conn.commit()

                # Try to get affected rows if available
                # Note: Procedures don't return row counts directly, we'd need to query the target tables
                # For now, we'll leave it as None

                duration_seconds = time.time() - start_time
                status = "success"

        except Exception as e:
            duration_seconds = time.time() - start_time
            status = "failed"
            error_message = str(e)
            execution_log.write(f"Error: {error_message}")

        # Update run record
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE dw_transformation_runs
                SET run_status = %s,
                    completed_at = NOW(),
                    duration_seconds = %s,
                    rows_affected = %s,
                    error_message = %s,
                    execution_log = %s
                WHERE id = %s
                """,
                (
                    status,
                    duration_seconds,
                    rows_affected,
                    error_message,
                    execution_log.getvalue() or None,
                    run_id,
                ),
            )

            # Update schedule last_run info
            cursor.execute(
                """
                UPDATE dw_transformation_schedules
                SET last_run_at = NOW(),
                    last_run_status = %s,
                    updated_at = NOW()
                WHERE procedure_name = %s
                """,
                (status, procedure_name),
            )
            conn.commit()

        return ExecuteTransformationResponse(
            run_id=run_id,
            procedure_name=procedure_name,
            status=status,
            rows_affected=rows_affected,
            duration_seconds=duration_seconds,
            error_message=error_message,
            execution_log=execution_log.getvalue() or None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transformations/{procedure_name}/schedule", response_model=TransformationProcedure)
async def get_transformation_schedule(procedure_name: str):
    """Get schedule for a transformation procedure.

    Args:
        procedure_name: Name of the procedure.

    Returns:
        TransformationProcedure with schedule information.
    """
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        with pool.get_connection() as conn:
            cursor = conn.cursor()

            # Get or create schedule record
            cursor.execute(
                """
                SELECT schedule_cron, is_active, last_run_at, last_run_status, next_run_time
                FROM dw_transformation_schedules
                WHERE procedure_name = %s
                """,
                (procedure_name,),
            )
            schedule_row = cursor.fetchone()

            if schedule_row:
                schedule_cron, is_active, last_run_at, last_run_status, next_run_time = schedule_row
                is_scheduled = bool(is_active) and bool(schedule_cron)
            else:
                # Create default record
                cursor.execute(
                    """
                    INSERT INTO dw_transformation_schedules (procedure_name, is_active)
                    VALUES (%s, FALSE)
                    RETURNING schedule_cron, is_active, last_run_at, last_run_status, next_run_time
                    """,
                    (procedure_name,),
                )
                conn.commit()
                schedule_row = cursor.fetchone()
                schedule_cron, is_active, last_run_at, last_run_status, next_run_time = schedule_row
                is_scheduled = False

            # Get description
            cursor.execute(
                """
                SELECT obj_description(p.oid, 'pg_proc')
                FROM pg_proc p
                WHERE p.proname = %s
                LIMIT 1
                """,
                (procedure_name,),
            )
            desc_row = cursor.fetchone()
            description = desc_row[0] if desc_row and desc_row[0] else None

            return TransformationProcedure(
                name=procedure_name,
                description=description,
                last_run_at=str(last_run_at) if last_run_at else None,
                last_run_status=last_run_status,
                schedule_cron=schedule_cron,
                is_scheduled=is_scheduled,
                next_run_time=str(next_run_time) if next_run_time else None,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/transformations/{procedure_name}/schedule", response_model=TransformationProcedure)
async def update_transformation_schedule(
    procedure_name: str, request: TransformationScheduleRequest
):
    """Update schedule for a transformation procedure.

    Args:
        procedure_name: Name of the procedure.
        request: Schedule request with cron expression.

    Returns:
        TransformationProcedure with updated schedule information.
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
                cron = croniter(schedule_cron, datetime.now(pytz.UTC))
                next_run_time = cron.get_next(datetime)
            except ImportError:
                # croniter not installed, skip validation
                next_run_time = None
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid cron expression: {str(e)}"
                )
        else:
            next_run_time = None

        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        with pool.get_connection() as conn:
            cursor = conn.cursor()

            # Check if procedure exists
            cursor.execute(
                """
                SELECT routine_name
                FROM information_schema.routines
                WHERE routine_schema = 'public'
                  AND routine_type = 'PROCEDURE'
                  AND routine_name = %s
                """,
                (procedure_name,),
            )
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=404, detail=f"Transformation procedure '{procedure_name}' not found"
                )

            # Upsert schedule
            cursor.execute(
                """
                INSERT INTO dw_transformation_schedules (procedure_name, schedule_cron, is_active, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (procedure_name) 
                DO UPDATE SET 
                    schedule_cron = EXCLUDED.schedule_cron,
                    is_active = EXCLUDED.is_active,
                    next_run_time = %s,
                    updated_at = NOW()
                RETURNING schedule_cron, is_active, last_run_at, last_run_status, next_run_time
                """,
                (procedure_name, schedule_cron, request.is_active, next_run_time),
            )
            schedule_row = cursor.fetchone()
            conn.commit()

            schedule_cron, is_active, last_run_at, last_run_status, next_run_time = schedule_row
            is_scheduled = bool(is_active) and bool(schedule_cron)

            # Get description
            cursor.execute(
                """
                SELECT obj_description(p.oid, 'pg_proc')
                FROM pg_proc p
                WHERE p.proname = %s
                LIMIT 1
                """,
                (procedure_name,),
            )
            desc_row = cursor.fetchone()
            description = desc_row[0] if desc_row and desc_row[0] else None

            return TransformationProcedure(
                name=procedure_name,
                description=description,
                last_run_at=str(last_run_at) if last_run_at else None,
                last_run_status=last_run_status,
                schedule_cron=schedule_cron,
                is_scheduled=is_scheduled,
                next_run_time=str(next_run_time) if next_run_time else None,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/transformations/{procedure_name}/schedule")
async def delete_transformation_schedule(procedure_name: str):
    """Remove schedule for a transformation procedure.

    Args:
        procedure_name: Name of the procedure.

    Returns:
        Success message.
    """
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE dw_transformation_schedules
                SET schedule_cron = NULL, is_active = FALSE, updated_at = NOW()
                WHERE procedure_name = %s
                """,
                (procedure_name,),
            )
            conn.commit()

            return {"message": f"Schedule removed for transformation procedure '{procedure_name}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transformations/{procedure_name}/history", response_model=list[TransformationRunHistory])
async def get_transformation_history(procedure_name: str, limit: int = 20):
    """Get execution history for a transformation procedure.

    Args:
        procedure_name: Name of the procedure.
        limit: Maximum number of runs to return.

    Returns:
        List of TransformationRunHistory.
    """
    try:
        orchestrator = ETLOrchestrator()
        pool = orchestrator.pool

        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, procedure_name, run_status, started_at, completed_at,
                       duration_seconds, rows_affected, error_message
                FROM dw_transformation_runs
                WHERE procedure_name = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (procedure_name, limit),
            )
            runs = cursor.fetchall()

            return [
                TransformationRunHistory(
                    id=run[0],
                    procedure_name=run[1],
                    run_status=run[2],
                    started_at=str(run[3]),
                    completed_at=str(run[4]) if run[4] else None,
                    duration_seconds=float(run[5]) if run[5] else None,
                    rows_affected=run[6],
                    error_message=run[7],
                )
                for run in runs
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
