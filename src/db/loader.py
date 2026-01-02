"""DataLoader for bulk insert/upsert to staging tables.

Handles batch loading of JSONB records with upsert semantics,
lineage tracking, and transactional integrity.
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

import psycopg2
import psycopg2.extras
from psycopg2.extensions import connection as PgConnection
from psycopg2.sql import Identifier, SQL

from src.config import get_settings, preflight_check
from src.db.connection import get_pool


@dataclass
class LoadResult:
    """Result of a data load operation."""

    rows_inserted: int = 0
    rows_updated: int = 0
    batches_total: int = 0
    batches_succeeded: int = 0
    batches_failed: int = 0
    duration_ms: float = 0.0
    errors: list[dict[str, Any]] = None

    def __post_init__(self):
        """Initialize errors list if None."""
        if self.errors is None:
            self.errors = []


class DataLoader:
    """Bulk loader for staging tables.

    Handles batch insert/upsert of JSONB records with:
    - Source ID-based deduplication
    - Lineage tracking (etl_job_id, etl_run_id)
    - Per-batch transactions
    - Retry logic for transient errors
    """

    def __init__(
        self,
        batch_size: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        """Initialize DataLoader.

        Args:
            batch_size: Records per batch. If None, uses settings.
            max_retries: Maximum retries for transient errors. If None, uses settings.
        """
        settings = get_settings()
        self.batch_size = batch_size or settings.etl.batch_size
        self.max_retries = max_retries or settings.etl.max_retries
        self.pool = get_pool()

    def load_to_staging(
        self,
        table_name: str,
        records: list[dict[str, Any]],
        etl_job_id: int,
        etl_run_id: int,
        source_id_key: str = "id",
        instance_id: Optional[int] = None,
        dry_run: Optional[bool] = None,
    ) -> LoadResult:
        """Load records into a staging table with upsert semantics.

        Args:
            table_name: Target staging table name (e.g., 'dim_studies_staging').
            records: List of records, each with 'data' (JSONB) and source_id.
            etl_job_id: ETL job ID for lineage.
            etl_run_id: ETL run ID for lineage.
            source_id_key: Key in data to extract patient/record ID (default: 'id').
            instance_id: Instance ID to use as source_id (from source_instance_id in job config).
                         If provided, this will be used as source_id instead of extracting from data.
            dry_run: Optional override for dry_run setting. If None, uses global setting.

        Returns:
            LoadResult with statistics.

        Raises:
            ValueError: If table_name is invalid or records are malformed.
            PreflightError: If preflight checks fail.
        """
        # Preflight check
        preflight_check(allow_db_write=True, dry_run=dry_run)

        if not records:
            return LoadResult()

        start_time = time.time()

        # Validate and prepare records
        prepared_records = self._prepare_records(
            records=records,
            etl_job_id=etl_job_id,
            etl_run_id=etl_run_id,
            source_id_key=source_id_key,
            instance_id=instance_id,
        )

        # Deduplicate by source_id (last occurrence wins)
        deduplicated = self._deduplicate_records(prepared_records)

        # Split into batches
        batches = [
            deduplicated[i : i + self.batch_size]
            for i in range(0, len(deduplicated), self.batch_size)
        ]

        result = LoadResult(batches_total=len(batches))
        loaded_at = datetime.utcnow()

        # Process each batch
        for batch_idx, batch in enumerate(batches):
            try:
                batch_result = self._load_batch(
                    table_name=table_name,
                    batch=batch,
                    etl_job_id=etl_job_id,
                    etl_run_id=etl_run_id,
                    loaded_at=loaded_at,
                )
                result.rows_inserted += batch_result["inserted"]
                result.rows_updated += batch_result["updated"]
                result.batches_succeeded += 1
            except Exception as e:
                result.batches_failed += 1
                result.errors.append(
                    {
                        "batch_index": batch_idx,
                        "error_code": type(e).__name__,
                        "message": str(e),
                    }
                )

        result.duration_ms = (time.time() - start_time) * 1000

        return result

    def _prepare_records(
        self,
        records: list[dict[str, Any]],
        etl_job_id: int,
        etl_run_id: int,
        source_id_key: str,
        instance_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Prepare and validate records for loading.

        Args:
            records: Raw records from API.
            etl_job_id: ETL job ID.
            etl_run_id: ETL run ID.
            source_id_key: Key to extract patient/record ID from data (for validation).
            instance_id: Instance ID to use as source_id. If provided, uses this instead of extracting from data.

        Returns:
            Prepared records with source_id set (either from instance_id or extracted from data).

        Raises:
            ValueError: If records are invalid.
        """
        prepared = []

        for idx, record in enumerate(records):
            # Validate record structure
            if not isinstance(record, dict):
                raise ValueError(f"Record {idx} is not a dictionary")

            # Extract data (should be JSONB-compatible)
            data = record.get("data")
            if data is None:
                raise ValueError(f"Record {idx} missing 'data' field")

            # Determine source_id: use instance_id if provided, otherwise extract from data
            if instance_id is not None:
                # Use instance_id as source_id (for multi-tenant support)
                source_id = str(instance_id)
            else:
                # Extract source_id from data (legacy behavior)
                if isinstance(data, dict):
                    source_id = str(data.get(source_id_key, ""))
                else:
                    # If data is already a string/JSON, try to parse it
                    if isinstance(data, str):
                        try:
                            parsed = json.loads(data)
                            source_id = str(parsed.get(source_id_key, ""))
                        except json.JSONDecodeError:
                            raise ValueError(f"Record {idx} has invalid JSON in 'data' field")
                    else:
                        raise ValueError(f"Record {idx} 'data' must be dict or JSON string")

                if not source_id:
                    raise ValueError(
                        f"Record {idx} missing source_id (key: {source_id_key})"
                    )

            # Ensure data is JSON-serializable
            if isinstance(data, dict):
                data_json = json.dumps(data)
            else:
                data_json = json.dumps(data) if not isinstance(data, str) else data

            prepared.append(
                {
                    "source_id": source_id,
                    "data": data_json,
                    "etl_job_id": etl_job_id,
                    "etl_run_id": etl_run_id,
                }
            )

        return prepared

    def _deduplicate_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Deduplicate records by (source_id, patient_id) (last occurrence wins).

        When source_id is instance_id, multiple patients share the same source_id,
        so we deduplicate by (source_id, patient_id) combination.

        Args:
            records: List of prepared records.

        Returns:
            Deduplicated records.
        """
        seen = {}
        for record in records:
            source_id = record["source_id"]
            # Extract patient_id from data for deduplication
            data = json.loads(record["data"]) if isinstance(record["data"], str) else record["data"]
            patient_id = str(data.get("id", ""))
            # Use composite key for deduplication
            dedup_key = f"{source_id}:{patient_id}"
            seen[dedup_key] = record

        return list(seen.values())

    def _load_batch(
        self,
        table_name: str,
        batch: list[dict[str, Any]],
        etl_job_id: int,
        etl_run_id: int,
        loaded_at: datetime,
    ) -> dict[str, int]:
        """Load a single batch with upsert semantics.

        Args:
            table_name: Target table name.
            batch: Batch of records to load.
            etl_job_id: ETL job ID.
            etl_run_id: ETL run ID.
            loaded_at: Timestamp for loaded_at column.

        Returns:
            Dictionary with 'inserted' and 'updated' counts.

        Raises:
            psycopg2.Error: On database errors.
        """
        # Build upsert query with RETURNING to track inserts vs updates
        query = SQL(
            """
            WITH upserted AS (
                INSERT INTO {table} (source_id, data, etl_job_id, etl_run_id, loaded_at, created_at, updated_at)
                VALUES %s
                ON CONFLICT (source_id) DO UPDATE SET
                    data = EXCLUDED.data,
                    etl_job_id = EXCLUDED.etl_job_id,
                    etl_run_id = EXCLUDED.etl_run_id,
                    loaded_at = EXCLUDED.loaded_at,
                    updated_at = EXCLUDED.loaded_at
                RETURNING xmax
            )
            SELECT
                COUNT(*) FILTER (WHERE xmax = 0) as inserted,
                COUNT(*) FILTER (WHERE xmax > 0) as updated
            FROM upserted
        """
        ).format(table=Identifier(table_name))

        # Prepare values for execute_values
        values = []
        for record in batch:
            # Parse JSONB data - ensure it's a dict
            if isinstance(record["data"], str):
                try:
                    data_dict = json.loads(record["data"])
                except json.JSONDecodeError:
                    data_dict = record["data"]
            else:
                data_dict = record["data"]

            values.append(
                (
                    record["source_id"],
                    json.dumps(data_dict),  # psycopg2.extras.Json will handle JSONB
                    etl_job_id,
                    etl_run_id,
                    loaded_at,
                    loaded_at,  # created_at
                    loaded_at,  # updated_at
                )
            )

        # Execute with retry logic
        for attempt in range(self.max_retries + 1):
            try:
                with self.pool.get_connection() as conn:
                    cursor = conn.cursor()

                    # Use execute_values with Json wrapper for JSONB
                    # Note: We need to use a different approach since execute_values
                    # doesn't work well with RETURNING
                    # Instead, we'll use a CTE approach with individual inserts
                    # or use execute_batch

                    # Convert values to use Json wrapper for JSONB
                    # Extract source_instance_id from the first record's etl_job_id context
                    # (We'll need to pass instance_id through the batch)
                    jsonb_values = []
                    for val in values:
                        # val structure: (source_id, data_json, etl_job_id, etl_run_id, loaded_at, created_at, updated_at)
                        # source_id is now the instance_id (as string)
                        # We need source_instance_id as integer for the composite constraint
                        instance_id_int = int(val[0]) if val[0] else None
                        jsonb_values.append(
                            (
                                val[0],  # source_id (instance_id as string)
                                instance_id_int,  # source_instance_id (instance_id as integer)
                                psycopg2.extras.Json(json.loads(val[1])),  # data as JSONB
                                val[2],  # etl_job_id
                                val[3],  # etl_run_id
                                val[4],  # loaded_at
                                val[5],  # created_at
                                val[6],  # updated_at
                            )
                        )

                    # Use execute_batch for better performance
                    # ON CONFLICT uses composite unique constraint: (source_instance_id, data->>'id')
                    insert_query = SQL(
                        """
                        INSERT INTO {table} (source_id, source_instance_id, data, etl_job_id, etl_run_id, loaded_at, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (source_instance_id, (data->>'id')) DO UPDATE SET
                            data = EXCLUDED.data,
                            etl_job_id = EXCLUDED.etl_job_id,
                            etl_run_id = EXCLUDED.etl_run_id,
                            loaded_at = EXCLUDED.loaded_at,
                            updated_at = EXCLUDED.loaded_at,
                            source_id = EXCLUDED.source_id
                    """
                    ).format(table=Identifier(table_name))

                    psycopg2.extras.execute_batch(
                        cursor,
                        insert_query,
                        jsonb_values,
                        page_size=len(jsonb_values),
                    )

                    # Count inserted vs updated by checking if created_at == updated_at
                    # (inserts will have them equal, updates will have updated_at > created_at)
                    cursor.execute(
                        SQL(
                            """
                            SELECT
                                COUNT(*) FILTER (WHERE created_at = updated_at) as inserted,
                                COUNT(*) FILTER (WHERE created_at < updated_at) as updated
                            FROM {table}
                            WHERE etl_run_id = %s
                                AND source_id = ANY(%s)
                        """
                        ).format(table=Identifier(table_name)),
                        (
                            etl_run_id,
                            [r["source_id"] for r in batch],
                        ),
                    )
                    result = cursor.fetchone()
                    inserted_count = result[0] if result else 0
                    updated_count = result[1] if result else 0

                    conn.commit()
                    return {"inserted": inserted_count, "updated": updated_count}

            except (
                psycopg2.OperationalError,
                psycopg2.InterfaceError,
            ) as e:
                # Transient errors - retry
                if attempt < self.max_retries:
                    time.sleep(2**attempt)  # Exponential backoff
                    continue
                raise

            except psycopg2.Error:
                # Non-transient errors - don't retry
                raise

        # Should never reach here, but just in case
        raise RuntimeError("Failed to load batch after retries")

