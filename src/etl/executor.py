"""Job Executor for ETL jobs.

Executes individual ETL jobs, handling both parameterized and non-parameterized jobs,
coordinating API calls and data loading. Supports checkpoint/resume and timeout handling.
"""

import json
import signal
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

import psycopg2
import psycopg2.extras
import structlog
from psycopg2.extensions import connection as PgConnection
from psycopg2.sql import Identifier, SQL

from src.api import ClinicalConductorClient, ODataParams
from src.config import get_settings
from src.db import DataLoader, get_pool
from src.metrics import get_metrics_collector

logger = structlog.get_logger(__name__)


class JobTimeoutError(Exception):
    """Raised when a job exceeds its timeout."""

    pass


class CheckpointData:
    """Checkpoint data for resuming a job.

    Supports both pagination checkpoints (for single API calls) and
    parameter checkpoints (for parameterized jobs like patient sub-endpoints).
    """

    def __init__(
        self,
        skip: int = 0,
        page_index: int = 0,
        total_records: int = 0,
        last_checkpoint_time: Optional[datetime] = None,
        # Parameterized job checkpoint fields
        parameter_index: int = 0,
        failed_parameters: Optional[list[dict]] = None,
    ):
        self.skip = skip
        self.page_index = page_index
        self.total_records = total_records
        self.last_checkpoint_time = last_checkpoint_time or datetime.utcnow()
        # For parameterized jobs: track which parameter we're at
        self.parameter_index = parameter_index
        # Track failed parameters for retry/reporting
        self.failed_parameters = failed_parameters or []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "skip": self.skip,
            "page_index": self.page_index,
            "total_records": self.total_records,
            "last_checkpoint_time": self.last_checkpoint_time.isoformat()
            if self.last_checkpoint_time
            else None,
            "parameter_index": self.parameter_index,
            "failed_parameters": self.failed_parameters,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckpointData":
        """Create from dictionary."""
        last_checkpoint = None
        if data.get("last_checkpoint_time"):
            try:
                last_checkpoint = datetime.fromisoformat(data["last_checkpoint_time"])
            except (ValueError, TypeError):
                pass
        return cls(
            skip=data.get("skip", 0),
            page_index=data.get("page_index", 0),
            total_records=data.get("total_records", 0),
            last_checkpoint_time=last_checkpoint,
            parameter_index=data.get("parameter_index", 0),
            failed_parameters=data.get("failed_parameters", []),
        )


@dataclass
class JobConfig:
    """ETL job configuration."""

    id: int
    name: str
    source_endpoint: str
    target_table: str
    is_active: bool
    requires_parameters: bool
    parameter_source_table: Optional[str] = None
    parameter_source_column: Optional[str] = None
    source_instance_id: Optional[int] = None
    description: Optional[str] = None
    incremental_load: bool = False
    timestamp_field_name: str = "lastUpdatedOn"
    depends_on: Optional[list[int]] = None


@dataclass
class ExecutionResult:
    """Result of job execution."""

    run_id: int
    status: str  # 'success', 'failed', 'running'
    records_loaded: int = 0
    error_message: Optional[str] = None
    duration_seconds: float = 0.0
    parameters: Optional[dict[str, Any]] = None


class JobExecutor:
    """Executes ETL jobs.

    Coordinates API calls and data loading for both parameterized
    and non-parameterized jobs.
    """

    def __init__(
        self,
        api_client: Optional[ClinicalConductorClient] = None,
        data_loader: Optional[DataLoader] = None,
    ):
        """Initialize job executor.

        Args:
            api_client: Clinical Conductor API client. If None, creates one.
            data_loader: DataLoader instance. If None, creates one.
        """
        self.api_client = api_client or ClinicalConductorClient()
        self.data_loader = data_loader or DataLoader()
        self.pool = get_pool()

    def get_job_config(self, job_id: int) -> JobConfig:
        """Load job configuration from database.

        Args:
            job_id: Job ID.

        Returns:
            JobConfig object.

        Raises:
            ValueError: If job not found or inactive.
        """
        with self.pool.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute(
                """
                SELECT id, name, source_endpoint, target_table, is_active,
                       requires_parameters, parameter_source_table,
                       parameter_source_column, source_instance_id,
                       COALESCE(incremental_load, FALSE) as incremental_load,
                       COALESCE(timestamp_field_name, 'lastUpdatedOn') as timestamp_field_name,
                       COALESCE(depends_on, ARRAY[]::INTEGER[]) as depends_on
                FROM dw_etl_jobs
                WHERE id = %s
                """,
                (job_id,),
            )

            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Job {job_id} not found")

            if not row["is_active"]:
                raise ValueError(f"Job {job_id} is not active")

            # Extract values safely - RealDictCursor returns dict-like objects
            incremental_load = row.get("incremental_load")
            if incremental_load is None:
                incremental_load = False
            elif not isinstance(incremental_load, bool):
                incremental_load = bool(incremental_load)
            
            timestamp_field_name = row.get("timestamp_field_name")
            if not timestamp_field_name or not isinstance(timestamp_field_name, str):
                timestamp_field_name = "lastUpdatedOn"
            
            depends_on = row.get("depends_on")
            if depends_on is None:
                depends_on = []
            elif not isinstance(depends_on, list):
                depends_on = list(depends_on) if depends_on else []
            
            return JobConfig(
                id=row["id"],
                name=row["name"],
                source_endpoint=row["source_endpoint"],
                target_table=row["target_table"],
                is_active=row["is_active"],
                requires_parameters=row["requires_parameters"],
                parameter_source_table=row["parameter_source_table"],
                parameter_source_column=row["parameter_source_column"],
                source_instance_id=row["source_instance_id"],
                description=None,  # Column doesn't exist in database
                incremental_load=incremental_load,
                timestamp_field_name=timestamp_field_name,
                depends_on=depends_on,
            )

    def create_run(
        self, job_id: int, parameters: Optional[dict[str, Any]] = None
    ) -> int:
        """Create a new ETL run record.

        Args:
            job_id: Job ID.
            parameters: Parameters for parameterized jobs.

        Returns:
            Run ID.
        """
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO dw_etl_runs (job_id, run_status, run_context)
                VALUES (%s, 'running', %s)
                RETURNING id
                """,
                (job_id, json.dumps(parameters) if parameters else None),
            )

            run_id = cursor.fetchone()[0]
            conn.commit()

            logger.info(
                "etl_run_created",
                job_id=job_id,
                run_id=run_id,
                parameters=parameters,
            )

            return run_id

    def update_run(
        self,
        run_id: int,
        status: str,
        records_loaded: int = 0,
        error_message: Optional[str] = None,
        checkpoint: Optional[CheckpointData] = None,
    ) -> None:
        """Update ETL run record.

        Args:
            run_id: Run ID.
            status: Run status ('success', 'failed', 'running').
            records_loaded: Number of records loaded.
            error_message: Error message if failed.
            checkpoint: Optional checkpoint data to save.
        """
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()

            # Get started_at to calculate duration
            cursor.execute(
                """
                SELECT started_at FROM dw_etl_runs WHERE id = %s
                """,
                (run_id,),
            )
            started_at = cursor.fetchone()[0]

            duration_seconds = (
                (datetime.utcnow() - started_at).total_seconds()
                if started_at
                else 0
            )
            duration_ms = int(duration_seconds * 1000)  # Convert to milliseconds

            # Build run_context with checkpoint if provided
            run_context = None
            if checkpoint:
                context_dict = checkpoint.to_dict()
                # Also preserve any existing parameters
                cursor.execute(
                    """
                    SELECT run_context FROM dw_etl_runs WHERE id = %s
                    """,
                    (run_id,),
                )
                existing_context = cursor.fetchone()[0]
                if existing_context:
                    try:
                        # Handle both dict (JSONB auto-deserialized) and string
                        existing_dict = existing_context if isinstance(existing_context, dict) else json.loads(existing_context)
                        # Merge checkpoint into existing context
                        existing_dict["checkpoint"] = context_dict
                        run_context = json.dumps(existing_dict)
                    except (json.JSONDecodeError, TypeError):
                        # If existing context isn't valid JSON, create new
                        run_context = json.dumps({"checkpoint": context_dict})
                else:
                    run_context = json.dumps({"checkpoint": context_dict})

            # Update with duration_ms (database column name)
            if run_context:
                cursor.execute(
                    """
                    UPDATE dw_etl_runs
                    SET run_status = %s,
                        records_loaded = %s,
                        error_message = %s,
                        completed_at = CASE WHEN %s != 'running' THEN NOW() ELSE NULL END,
                        duration_ms = %s,
                        run_context = %s
                    WHERE id = %s
                    """,
                    (
                        status,
                        records_loaded,
                        error_message,
                        status,
                        duration_ms,
                        run_context,
                        run_id,
                    ),
                )
            else:
                cursor.execute(
                    """
                    UPDATE dw_etl_runs
                    SET run_status = %s,
                        records_loaded = %s,
                        error_message = %s,
                        completed_at = CASE WHEN %s != 'running' THEN NOW() ELSE NULL END,
                        duration_ms = %s
                    WHERE id = %s
                    """,
                    (status, records_loaded, error_message, status, duration_ms, run_id),
                )

            # Update job's last_run_* fields
            cursor.execute(
                """
                UPDATE dw_etl_jobs
                SET last_run_at = NOW(),
                    last_run_status = %s,
                    last_run_records = %s,
                    updated_at = NOW()
                WHERE id = (SELECT job_id FROM dw_etl_runs WHERE id = %s)
                """,
                (status, records_loaded, run_id),
            )

            conn.commit()

            logger.info(
                "etl_run_updated",
                run_id=run_id,
                status=status,
                records_loaded=records_loaded,
                duration_seconds=duration_seconds,
                checkpoint=checkpoint.to_dict() if checkpoint else None,
            )

    def get_checkpoint(self, run_id: int) -> Optional[CheckpointData]:
        """Get checkpoint data from a run.

        Args:
            run_id: Run ID.

        Returns:
            CheckpointData if found, None otherwise.
        """
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT run_context FROM dw_etl_runs WHERE id = %s
                """,
                (run_id,),
            )
            row = cursor.fetchone()
            if not row or not row[0]:
                return None

            try:
                # Handle both dict (JSONB auto-deserialized) and string
                context = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                checkpoint_data = context.get("checkpoint")
                if checkpoint_data:
                    return CheckpointData.from_dict(checkpoint_data)
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

            return None

    def get_parameter_values(
        self,
        source_table: str,
        source_column: str,
        job_id: int,
    ) -> list[Any]:
        """Get parameter values from source table.

        Args:
            source_table: Source table name.
            source_column: Column path (JSONB path, e.g., 'data->id').
            job_id: Job ID for logging.

        Returns:
            List of parameter values.
        """
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()

            # Extract values from JSONB column
            # Handle both direct column access and JSONB path access
            if "->" in source_column or "->>" in source_column:
                # JSONB path access
                query = SQL(
                    """
                    SELECT DISTINCT {column}
                    FROM {table}
                    WHERE {column} IS NOT NULL
                    ORDER BY {column}
                    """
                ).format(
                    table=Identifier(source_table),
                    column=SQL(source_column),
                )
            else:
                # Direct column access
                query = SQL(
                    """
                    SELECT DISTINCT {column}
                    FROM {table}
                    WHERE {column} IS NOT NULL
                    ORDER BY {column}
                    """
                ).format(
                    table=Identifier(source_table),
                    column=Identifier(source_column),
                )

            cursor.execute(query)
            values = [row[0] for row in cursor.fetchall()]

            logger.info(
                "parameter_values_fetched",
                job_id=job_id,
                source_table=source_table,
                source_column=source_column,
                count=len(values),
            )

            return values

    def substitute_parameters(
        self, endpoint: str, parameters: dict[str, Any]
    ) -> str:
        """Substitute parameters in endpoint URL.

        Args:
            endpoint: Endpoint template (e.g., '/api/v1/studies/{studyId}/subjects/odata').
            parameters: Parameter values (e.g., {'studyId': 123}).

        Returns:
            Substituted endpoint.
        """
        result = endpoint
        for key, value in parameters.items():
            placeholder = f"{{{key}}}"
            result = result.replace(placeholder, str(value))
        return result

    def execute_job(
        self,
        job_id: int,
        dry_run: bool = False,
        parameters: Optional[dict[str, Any]] = None,
        resume_from_checkpoint: bool = False,
        timeout_seconds: Optional[int] = None,
    ) -> ExecutionResult:
        """Execute an ETL job.

        Args:
            job_id: Job ID to execute.
            dry_run: If True, don't write to database.
            parameters: Optional parameters (for testing parameterized jobs).
            resume_from_checkpoint: If True, resume from saved checkpoint if available.
            timeout_seconds: Maximum execution time in seconds.

        Returns:
            ExecutionResult with execution details.

        Raises:
            ValueError: If job not found or invalid.
        """
        start_time = time.time()

        # Load job configuration
        job_config = self.get_job_config(job_id)

        # Get API client for this job (use credentials from database if source_instance_id is set)
        api_client = self._get_api_client(job_config.source_instance_id)

        # Check for existing run to resume from
        run_id: Optional[int] = None
        if resume_from_checkpoint:
            # Find the most recent running or failed run with a checkpoint
            with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, run_status, run_context
                    FROM dw_etl_runs
                    WHERE job_id = %s
                      AND run_status IN ('running', 'failed')
                      AND run_context IS NOT NULL
                      AND run_context::text LIKE '%%checkpoint%%'
                    ORDER BY started_at DESC
                    LIMIT 1
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
                if row:
                    run_id, status, context = row
                    logger.info(
                        "resuming_existing_run",
                        job_id=job_id,
                        run_id=run_id,
                        previous_status=status,
                    )
                else:
                    logger.info(
                        "no_checkpoint_found",
                        job_id=job_id,
                        message="No checkpoint found, starting new run",
                    )

        # Create new run if not resuming
        if run_id is None:
            run_id = self.create_run(job_id, parameters)

        logger.info(
            "job_execution_started",
            job_id=job_id,
            job_name=job_config.name,
            run_id=run_id,
            requires_parameters=job_config.requires_parameters,
            dry_run=dry_run,
            resume_from_checkpoint=resume_from_checkpoint,
            timeout_seconds=timeout_seconds,
        )

        try:
            total_records = 0

            if job_config.requires_parameters:
                # Parameterized job
                if parameters:
                    # Use provided parameters (for testing)
                    param_list = [parameters]
                else:
                    # Fetch parameters from source table
                    if not job_config.parameter_source_table:
                        raise ValueError(
                            f"Job {job_id} requires parameters but "
                            "parameter_source_table is not set"
                        )
                    if not job_config.parameter_source_column:
                        raise ValueError(
                            f"Job {job_id} requires parameters but "
                            "parameter_source_column is not set"
                        )

                    param_values = self.get_parameter_values(
                        source_table=job_config.parameter_source_table,
                        source_column=job_config.parameter_source_column,
                        job_id=job_id,
                    )

                    # Convert to parameter dicts
                    # Assume single parameter (e.g., studyId)
                    # Extract parameter name from endpoint (e.g., {studyId})
                    import re

                    param_match = re.search(r"\{(\w+)\}", job_config.source_endpoint)
                    if not param_match:
                        raise ValueError(
                            f"Job {job_id} endpoint doesn't contain parameter placeholder"
                        )

                    param_name = param_match.group(1)
                    param_list = [{param_name: val} for val in param_values]

                # Execute for each parameter set with error handling and checkpointing
                # Track failures to allow partial success
                failed_params = []
                successful_params = 0
                start_index = 0

                # Load checkpoint for parameterized job resume
                if resume_from_checkpoint:
                    checkpoint = self.get_checkpoint(run_id)
                    if checkpoint and checkpoint.parameter_index > 0:
                        start_index = checkpoint.parameter_index
                        total_records = checkpoint.total_records
                        failed_params = checkpoint.failed_parameters or []
                        successful_params = start_index - len(failed_params)
                        logger.info(
                            "resuming_parameterized_job",
                            job_id=job_id,
                            run_id=run_id,
                            start_index=start_index,
                            total_params=len(param_list),
                            previous_records=total_records,
                            previous_failures=len(failed_params),
                        )

                # Checkpoint settings
                checkpoint_interval_params = 100  # Save every N parameters
                checkpoint_interval_seconds = 60  # Or every N seconds
                last_checkpoint_time = time.time()

                for param_index, param_set in enumerate(param_list):
                    # Skip already processed parameters when resuming
                    if param_index < start_index:
                        continue

                    endpoint = self.substitute_parameters(
                        job_config.source_endpoint, param_set
                    )

                    try:
                        records = self._fetch_and_load(
                            endpoint=endpoint,
                            target_table=job_config.target_table,
                            etl_job_id=job_id,
                            etl_run_id=run_id,
                            dry_run=dry_run,
                            api_client=api_client,
                            incremental_load=job_config.incremental_load,
                            timestamp_field_name=job_config.timestamp_field_name,
                            parameters=param_set,
                            instance_id=job_config.source_instance_id,
                            resume_from_checkpoint=False,  # Don't nest checkpoint resume
                            timeout_seconds=timeout_seconds,
                        )

                        total_records += records
                        successful_params += 1

                    except JobTimeoutError:
                        # Save checkpoint before re-raising timeout
                        checkpoint = CheckpointData(
                            parameter_index=param_index,
                            total_records=total_records,
                            failed_parameters=failed_params[-100:],  # Keep last 100 failures
                        )
                        self.update_run(
                            run_id,
                            "running",
                            records_loaded=total_records,
                            checkpoint=checkpoint,
                        )
                        raise

                    except Exception as param_error:
                        # Log individual parameter failure but continue with others
                        failed_params.append({
                            "parameters": param_set,
                            "endpoint": endpoint,
                            "error": str(param_error),
                        })
                        logger.warning(
                            "parameter_execution_failed",
                            job_id=job_id,
                            run_id=run_id,
                            parameters=param_set,
                            endpoint=endpoint,
                            error=str(param_error),
                            failed_count=len(failed_params),
                            total_params=len(param_list),
                            progress_pct=round((param_index + 1) / len(param_list) * 100, 1),
                        )
                        # Continue to next parameter
                        continue

                    # Save checkpoint periodically
                    current_time = time.time()
                    params_since_checkpoint = (param_index + 1 - start_index)
                    time_since_checkpoint = current_time - last_checkpoint_time

                    if (params_since_checkpoint > 0 and
                        params_since_checkpoint % checkpoint_interval_params == 0) or \
                       time_since_checkpoint >= checkpoint_interval_seconds:
                        checkpoint = CheckpointData(
                            parameter_index=param_index + 1,
                            total_records=total_records,
                            failed_parameters=failed_params[-100:],  # Keep last 100 failures
                        )
                        self.update_run(
                            run_id,
                            "running",
                            records_loaded=total_records,
                            checkpoint=checkpoint,
                        )
                        last_checkpoint_time = current_time
                        logger.info(
                            "parameterized_job_checkpoint",
                            job_id=job_id,
                            run_id=run_id,
                            parameter_index=param_index + 1,
                            total_params=len(param_list),
                            progress_pct=round((param_index + 1) / len(param_list) * 100, 2),
                            total_records=total_records,
                            failed_count=len(failed_params),
                        )

                # Log summary of parameter failures
                if failed_params:
                    failure_rate = len(failed_params) / len(param_list) * 100
                    logger.warning(
                        "parameterized_job_partial_failures",
                        job_id=job_id,
                        run_id=run_id,
                        total_params=len(param_list),
                        successful_params=successful_params,
                        failed_params=len(failed_params),
                        failure_rate_pct=round(failure_rate, 2),
                        failed_details=failed_params[:10],  # Log first 10 failures
                    )

                    # If ALL parameters failed, raise an error
                    if successful_params == 0:
                        raise RuntimeError(
                            f"All {len(param_list)} parameter executions failed. "
                            f"First error: {failed_params[0]['error']}"
                        )

            else:
                # Non-parameterized job
                records = self._fetch_and_load(
                    endpoint=job_config.source_endpoint,
                    target_table=job_config.target_table,
                    etl_job_id=job_id,
                    etl_run_id=run_id,
                    dry_run=dry_run,
                    api_client=api_client,
                    incremental_load=job_config.incremental_load,
                    timestamp_field_name=job_config.timestamp_field_name,
                    parameters=None,
                    instance_id=job_config.source_instance_id,
                    resume_from_checkpoint=resume_from_checkpoint,
                    timeout_seconds=timeout_seconds,
                )

                total_records = records

            # Update run as success
            self.update_run(
                run_id=run_id,
                status="success",
                records_loaded=total_records,
            )

            duration = time.time() - start_time

            # Record metrics
            metrics_collector = get_metrics_collector()
            metrics_collector.record_job_execution(
                job_id=job_id,
                status="success",
                duration_seconds=duration,
                records_loaded=total_records,
                table=job_config.target_table,
            )

            logger.info(
                "job_execution_completed",
                job_id=job_id,
                run_id=run_id,
                status="success",
                records_loaded=total_records,
                duration_seconds=duration,
            )

            return ExecutionResult(
                run_id=run_id,
                status="success",
                records_loaded=total_records,
                duration_seconds=duration,
            )

        except JobTimeoutError as e:
            # Timeout errors: keep run as 'running' with checkpoint saved
            error_message = str(e)
            # Get current records_loaded from checkpoint
            checkpoint = self.get_checkpoint(run_id)
            records_loaded = checkpoint.total_records if checkpoint else 0
            
            self.update_run(
                run_id=run_id,
                status="running",  # Keep as running so it can be resumed
                records_loaded=records_loaded,
                error_message=error_message,
            )

            duration = time.time() - start_time

            logger.warning(
                "job_execution_timeout",
                job_id=job_id,
                run_id=run_id,
                error=error_message,
                duration_seconds=duration,
                records_loaded=records_loaded,
                message="Job timed out but checkpoint saved. Retry to resume.",
            )

            return ExecutionResult(
                run_id=run_id,
                status="running",  # Return as running, not failed
                records_loaded=records_loaded,
                error_message=error_message,
                duration_seconds=duration,
            )

        except Exception as e:
            # Update run as failed
            error_message = str(e)
            self.update_run(
                run_id=run_id,
                status="failed",
                records_loaded=0,
                error_message=error_message,
            )

            duration = time.time() - start_time

            # Determine error category
            error_category = "System"
            error_type = type(e).__name__
            if "API" in error_type or "api" in error_message.lower():
                error_category = "API"
            elif "psycopg2" in error_type or "database" in error_message.lower() or "db" in error_message.lower():
                error_category = "DB"
            elif "ValueError" in error_type or "data" in error_message.lower():
                error_category = "Data"

            # Record metrics
            metrics_collector = get_metrics_collector()
            metrics_collector.record_job_execution(
                job_id=job_id,
                status="failed",
                duration_seconds=duration,
                records_loaded=0,
                table=job_config.target_table,
                error_category=error_category,
            )

            logger.error(
                "job_execution_failed",
                job_id=job_id,
                run_id=run_id,
                error=error_message,
                duration_seconds=duration,
                error_category=error_category,
            )

            return ExecutionResult(
                run_id=run_id,
                status="failed",
                records_loaded=0,
                error_message=error_message,
                duration_seconds=duration,
            )

    def _get_api_client(self, source_instance_id: Optional[int] = None) -> ClinicalConductorClient:
        """Get API client for a job.

        In development/test environments, always uses .env credentials.
        In production, uses database credentials if source_instance_id is set.

        Args:
            source_instance_id: Optional credential ID from dw_api_credentials table.

        Returns:
            ClinicalConductorClient instance.
        """
        settings = get_settings()

        # In development/test, always use .env credentials (ignore database credentials)
        if settings.is_development or settings.is_test:
            if source_instance_id is not None:
                logger.info(
                    "using_env_credentials_in_dev",
                    source_instance_id=source_instance_id,
                    environment=settings.environment,
                    message="Using .env credentials in development/test (ignoring database credentials)",
                )
            return self.api_client

        # In production, use database credentials if source_instance_id is set
        if source_instance_id is None:
            # Use default client (from .env) as fallback
            return self.api_client

        # Get credentials from database
        with self.pool.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(
                """
                SELECT base_url, api_key
                FROM dw_api_credentials
                WHERE id = %s AND is_active = TRUE
                """,
                (source_instance_id,),
            )

            row = cursor.fetchone()
            if not row:
                logger.warning(
                    "credential_not_found",
                    source_instance_id=source_instance_id,
                    message="Using default credentials from .env",
                )
                return self.api_client

            # Create client with database credentials
            logger.info(
                "using_database_credentials",
                source_instance_id=source_instance_id,
                base_url=row["base_url"],
            )
            return ClinicalConductorClient(
                base_url=row["base_url"],
                api_key=row["api_key"],
            )

    def _get_last_successful_run_timestamp(
        self, job_id: int, parameters: Optional[dict[str, Any]] = None
    ) -> Optional[datetime]:
        """Get timestamp of last successful run for incremental loading.

        Args:
            job_id: Job ID.
            parameters: Optional parameters for parameterized jobs.

        Returns:
            Timestamp of last successful run, or None if no previous run.
        """
        with self.pool.get_connection() as conn:
            cursor = conn.cursor()

            if parameters:
                # For parameterized jobs, find last successful run with matching parameters
                cursor.execute(
                    """
                    SELECT completed_at
                    FROM dw_etl_runs
                    WHERE job_id = %s
                      AND run_status = 'success'
                      AND run_context = %s
                    ORDER BY completed_at DESC
                    LIMIT 1
                    """,
                    (job_id, json.dumps(parameters)),
                )
            else:
                # For non-parameterized jobs, find last successful run
                cursor.execute(
                    """
                    SELECT completed_at
                    FROM dw_etl_runs
                    WHERE job_id = %s
                      AND run_status = 'success'
                    ORDER BY completed_at DESC
                    LIMIT 1
                    """,
                    (job_id,),
                )

            row = cursor.fetchone()
            if row and row[0]:
                return row[0]

            return None

    def _fetch_and_load(
        self,
        endpoint: str,
        target_table: str,
        etl_job_id: int,
        etl_run_id: int,
        dry_run: bool = False,
        api_client: Optional[ClinicalConductorClient] = None,
        incremental_load: bool = False,
        timestamp_field_name: str = "lastUpdatedOn",
        parameters: Optional[dict[str, Any]] = None,
        instance_id: Optional[int] = None,
        resume_from_checkpoint: bool = False,
        timeout_seconds: Optional[int] = None,
    ) -> int:
        """Fetch data from API and load to staging.

        Args:
            endpoint: API endpoint to call.
            target_table: Target staging table.
            etl_job_id: ETL job ID.
            etl_run_id: ETL run ID.
            dry_run: If True, skip database writes.
            api_client: Optional API client to use.
            incremental_load: If True, only fetch records modified since last run.
            timestamp_field_name: Name of timestamp field to filter on.
            parameters: Optional parameters for parameterized jobs.
            resume_from_checkpoint: If True, resume from saved checkpoint.
            timeout_seconds: Maximum execution time in seconds.

        Returns:
            Number of records loaded.

        Raises:
            JobTimeoutError: If job exceeds timeout.
        """
        # Set timeout
        settings = get_settings()
        timeout = timeout_seconds or settings.etl.default_timeout_seconds
        start_time = time.time()

        # Load checkpoint if resuming
        checkpoint: Optional[CheckpointData] = None
        initial_skip = 0
        if resume_from_checkpoint:
            checkpoint = self.get_checkpoint(etl_run_id)
            if checkpoint:
                initial_skip = checkpoint.skip
                logger.info(
                    "resuming_from_checkpoint",
                    endpoint=endpoint,
                    etl_run_id=etl_run_id,
                    skip=initial_skip,
                    page_index=checkpoint.page_index,
                    total_records=checkpoint.total_records,
                )

        # Fetch data from API
        logger.info(
            "fetching_api_data",
            endpoint=endpoint,
            etl_job_id=etl_job_id,
            etl_run_id=etl_run_id,
            incremental_load=incremental_load,
            resume_from_skip=initial_skip,
            timeout_seconds=timeout,
        )

        # Use provided client or default
        client = api_client or self.api_client

        # Build OData params with incremental filter if enabled
        from src.api.client import ODataParams

        odata_params = ODataParams()
        if initial_skip > 0:
            odata_params.skip = initial_skip

        if incremental_load:
            last_run_time = self._get_last_successful_run_timestamp(
                etl_job_id, parameters
            )
            if last_run_time:
                # Format as OData DateTimeOffset: YYYY-MM-DDTHH:mm:ss.fffZ
                filter_date = last_run_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                filter_expr = f"{timestamp_field_name} gt {filter_date}"
                if odata_params.filter:
                    odata_params.filter = f"({odata_params.filter}) and ({filter_expr})"
                else:
                    odata_params.filter = filter_expr
                logger.info(
                    "incremental_filter_applied",
                    endpoint=endpoint,
                    filter_date=filter_date,
                    timestamp_field=timestamp_field_name,
                )

        # Get batch size from DataLoader (already configured)
        batch_size = self.data_loader.batch_size

        # Accumulate records in batches and load incrementally
        current_batch = []
        total_loaded = checkpoint.total_records if checkpoint else 0
        total_inserted = 0
        total_updated = 0
        page_count = checkpoint.page_index if checkpoint else 0
        skip = initial_skip
        last_checkpoint_time = time.time()
        checkpoint_interval = 60  # Save checkpoint every 60 seconds

        try:
            for page in client.get_odata(
                endpoint, params=odata_params, page_mode="iterator", dry_run=dry_run
            ):
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    # Save checkpoint before raising timeout
                    checkpoint = CheckpointData(
                        skip=skip,
                        page_index=page_count,
                        total_records=total_loaded,
                    )
                    self.update_run(
                        etl_run_id,
                        "running",
                        records_loaded=total_loaded,
                        checkpoint=checkpoint,
                    )
                    raise JobTimeoutError(
                        f"Job exceeded timeout of {timeout} seconds (elapsed: {elapsed:.1f}s). "
                        f"Progress saved: {total_loaded} records loaded, skip={skip}. "
                        f"Resume by retrying the run."
                    )

                page_count += 1
                # Validate page.items is a list
                if not isinstance(page.items, list):
                    logger.warning(
                        "invalid_page_items",
                        endpoint=endpoint,
                        items_type=type(page.items).__name__,
                    )
                    continue

                # Add items to current batch
                for item in page.items:
                    if not isinstance(item, dict):
                        logger.warning(
                            "invalid_item_type",
                            endpoint=endpoint,
                            item_type=type(item).__name__,
                            item_repr=str(item)[:100],
                        )
                        continue
                    # Inject parent parameters into item data for parameterized jobs
                    # This enables triggers to extract patient_id, studyId, etc.
                    if parameters:
                        item["_parentId"] = str(list(parameters.values())[0])
                    current_batch.append({"data": item})

                    # When batch is full, load it to database
                    if len(current_batch) >= batch_size:
                        if not dry_run:
                            batch_result = self.data_loader.load_to_staging(
                                table_name=target_table,
                                records=current_batch,
                                etl_job_id=etl_job_id,
                                etl_run_id=etl_run_id,
                                instance_id=instance_id,
                                dry_run=dry_run,
                            )
                            total_inserted += batch_result.rows_inserted
                            total_updated += batch_result.rows_updated
                            total_loaded += batch_result.rows_inserted + batch_result.rows_updated

                            logger.info(
                                "batch_loaded",
                                endpoint=endpoint,
                                target_table=target_table,
                                batch_size=len(current_batch),
                                rows_inserted=batch_result.rows_inserted,
                                rows_updated=batch_result.rows_updated,
                                total_loaded=total_loaded,
                                page_count=page_count,
                                etl_job_id=etl_job_id,
                                etl_run_id=etl_run_id,
                            )
                        else:
                            total_loaded += len(current_batch)

                        # Clear batch for next iteration
                        current_batch = []

                # Update skip for next iteration (estimate based on page size)
                if page.items:
                    skip += len(page.items)
                elif page.next_link:
                    # Parse next_link to get skip value if available
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(page.next_link)
                    query_params = parse_qs(parsed.query)
                    skip_str = query_params.get("$skip", [None])[0]
                    if skip_str:
                        try:
                            skip = int(skip_str)
                        except ValueError:
                            skip += len(page.items) if page.items else odata_params.top or 100
                    else:
                        skip += len(page.items) if page.items else odata_params.top or 100
                else:
                    skip += len(page.items) if page.items else odata_params.top or 100

                # Save checkpoint periodically (every checkpoint_interval seconds)
                current_time = time.time()
                if current_time - last_checkpoint_time >= checkpoint_interval:
                    checkpoint = CheckpointData(
                        skip=skip,
                        page_index=page_count,
                        total_records=total_loaded,
                    )
                    self.update_run(
                        etl_run_id,
                        "running",
                        records_loaded=total_loaded,
                        checkpoint=checkpoint,
                    )
                    last_checkpoint_time = current_time
                    logger.debug(
                        "checkpoint_saved",
                        endpoint=endpoint,
                        etl_run_id=etl_run_id,
                        skip=skip,
                        page_count=page_count,
                        total_loaded=total_loaded,
                    )

        except JobTimeoutError:
            # Re-raise timeout errors (checkpoint already saved)
            raise
        except Exception as e:
            logger.error(
                "error_fetching_data",
                endpoint=endpoint,
                error=str(e),
                error_type=type(e).__name__,
                total_loaded=total_loaded,
            )
            # Try to load any remaining records in current_batch before raising
            if current_batch and not dry_run:
                try:
                    batch_result = self.data_loader.load_to_staging(
                        table_name=target_table,
                        records=current_batch,
                        etl_job_id=etl_job_id,
                        etl_run_id=etl_run_id,
                        instance_id=instance_id,
                        dry_run=dry_run,
                    )
                    total_inserted += batch_result.rows_inserted
                    total_updated += batch_result.rows_updated
                    total_loaded += batch_result.rows_inserted + batch_result.rows_updated
                    logger.info(
                        "final_batch_loaded_on_error",
                        endpoint=endpoint,
                        batch_size=len(current_batch),
                        total_loaded=total_loaded,
                    )
                except Exception as load_error:
                    logger.error(
                        "error_loading_final_batch",
                        endpoint=endpoint,
                        error=str(load_error),
                        batch_size=len(current_batch),
                    )
            raise

        # Load any remaining records in the final batch
        if current_batch:
            if not dry_run:
                batch_result = self.data_loader.load_to_staging(
                    table_name=target_table,
                    records=current_batch,
                    etl_job_id=etl_job_id,
                    etl_run_id=etl_run_id,
                    instance_id=instance_id,
                    dry_run=dry_run,
                )
                total_inserted += batch_result.rows_inserted
                total_updated += batch_result.rows_updated
                total_loaded += batch_result.rows_inserted + batch_result.rows_updated

                logger.info(
                    "final_batch_loaded",
                    endpoint=endpoint,
                    target_table=target_table,
                    batch_size=len(current_batch),
                    rows_inserted=batch_result.rows_inserted,
                    rows_updated=batch_result.rows_updated,
                    total_loaded=total_loaded,
                    etl_job_id=etl_job_id,
                    etl_run_id=etl_run_id,
                )
            else:
                total_loaded += len(current_batch)

        # Clear checkpoint on successful completion
        self.update_run(
            etl_run_id,
            "running",
            records_loaded=total_loaded,
            checkpoint=None,  # Clear checkpoint on success
        )

        logger.info(
            "api_data_fetched_and_loaded",
            endpoint=endpoint,
            total_items=total_loaded,
            total_inserted=total_inserted,
            total_updated=total_updated,
            pages_processed=page_count,
            etl_job_id=etl_job_id,
            etl_run_id=etl_run_id,
        )

        if dry_run:
            logger.info(
                "dry_run_complete",
                endpoint=endpoint,
                items_count=total_loaded,
                target_table=target_table,
            )

        return total_loaded

