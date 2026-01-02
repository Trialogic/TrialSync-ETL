"""Job Executor for ETL jobs.

Executes individual ETL jobs, handling both parameterized and non-parameterized jobs,
coordinating API calls and data loading.
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime
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
    ) -> None:
        """Update ETL run record.

        Args:
            run_id: Run ID.
            status: Run status ('success', 'failed', 'running').
            records_loaded: Number of records loaded.
            error_message: Error message if failed.
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

            cursor.execute(
                """
                UPDATE dw_etl_runs
                SET run_status = %s,
                    records_loaded = %s,
                    error_message = %s,
                    completed_at = NOW(),
                    duration_ms = %s
                WHERE id = %s
                """,
                (status, records_loaded, error_message, duration_ms, run_id),
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
            )

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
    ) -> ExecutionResult:
        """Execute an ETL job.

        Args:
            job_id: Job ID to execute.
            dry_run: If True, don't write to database.
            parameters: Optional parameters (for testing parameterized jobs).

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

        logger.info(
            "job_execution_started",
            job_id=job_id,
            job_name=job_config.name,
            requires_parameters=job_config.requires_parameters,
            dry_run=dry_run,
        )

        # Create run record
        run_id = self.create_run(job_id, parameters)

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

                # Execute for each parameter set
                for param_set in param_list:
                    endpoint = self.substitute_parameters(
                        job_config.source_endpoint, param_set
                    )

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
                    )

                    total_records += records

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

        Returns:
            Number of records loaded.
        """
        # Fetch data from API
        logger.info(
            "fetching_api_data",
            endpoint=endpoint,
            etl_job_id=etl_job_id,
            etl_run_id=etl_run_id,
            incremental_load=incremental_load,
        )

        # Use provided client or default
        client = api_client or self.api_client

        # Build OData params with incremental filter if enabled
        odata_params = None
        if incremental_load:
            last_run_time = self._get_last_successful_run_timestamp(
                etl_job_id, parameters
            )
            if last_run_time:
                # Format as OData DateTimeOffset: YYYY-MM-DDTHH:mm:ss.fffZ
                filter_date = last_run_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                filter_expr = f"{timestamp_field_name} gt {filter_date}"
                from src.api.client import ODataParams

                odata_params = ODataParams(filter=filter_expr)
                logger.info(
                    "incremental_filter_applied",
                    endpoint=endpoint,
                    filter_date=filter_date,
                    timestamp_field=timestamp_field_name,
                )

        all_items = []
        try:
            for page in client.get_odata(
                endpoint, params=odata_params, page_mode="iterator", dry_run=dry_run
            ):
                # Validate page.items is a list
                if not isinstance(page.items, list):
                    logger.warning(
                        "invalid_page_items",
                        endpoint=endpoint,
                        items_type=type(page.items).__name__,
                    )
                    continue
                all_items.extend(page.items)
        except Exception as e:
            logger.error(
                "error_fetching_data",
                endpoint=endpoint,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

        logger.info(
            "api_data_fetched",
            endpoint=endpoint,
            items_count=len(all_items),
            etl_job_id=etl_job_id,
            etl_run_id=etl_run_id,
        )

        if dry_run:
            logger.info(
                "dry_run_skipping_load",
                endpoint=endpoint,
                items_count=len(all_items),
                target_table=target_table,
            )
            return len(all_items)

        # Prepare records for loading - validate items are dicts
        records = []
        for item in all_items:
            if not isinstance(item, dict):
                logger.warning(
                    "invalid_item_type",
                    endpoint=endpoint,
                    item_type=type(item).__name__,
                    item_repr=str(item)[:100],
                )
                continue
            records.append({"data": item})

        # Load to staging
        # Pass source_instance_id as instance_id to use as source_id
        result = self.data_loader.load_to_staging(
            table_name=target_table,
            records=records,
            etl_job_id=etl_job_id,
            etl_run_id=etl_run_id,
            instance_id=job_config.source_instance_id,
            dry_run=dry_run,
        )

        logger.info(
            "data_loaded",
            endpoint=endpoint,
            target_table=target_table,
            rows_inserted=result.rows_inserted,
            rows_updated=result.rows_updated,
            batches_total=result.batches_total,
            etl_job_id=etl_job_id,
            etl_run_id=etl_run_id,
        )

        return result.rows_inserted + result.rows_updated

