#!/usr/bin/env python3
"""Retry failed patient parameters from ETL jobs.

This script reads the failed parameters from job checkpoints and retries them
with a slower rate to avoid rate limiting.

Usage:
    # Retry all failed patients from all jobs
    python scripts/retry_failed_patients.py

    # Retry specific jobs only
    python scripts/retry_failed_patients.py --jobs 178,179

    # Dry run (show what would be retried)
    python scripts/retry_failed_patients.py --dry-run

    # Set delay between requests (default: 2 seconds)
    python scripts/retry_failed_patients.py --delay 3
"""

import argparse
import json
import sys
import os
import time
from datetime import datetime
from typing import Any, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import structlog

from src.api import ClinicalConductorClient
from src.db import DataLoader, get_pool
from src.etl.executor import JobExecutor

logger = structlog.get_logger(__name__)

# Patient sub-endpoint jobs
PATIENT_JOBS = {
    178: "Patient Allergies",
    179: "Patient Conditions",
    180: "Patient Devices",
    181: "Patient Medications",
    182: "Patient Procedures",
    183: "Patient Immunizations",
    184: "Patient Providers",
    185: "Patient Family History",
    186: "Patient Social History",
    187: "Patient Campaign Touches",
    188: "Patient Referral Touches",
}


def get_failed_parameters(job_id: int) -> list[dict]:
    """Get failed parameters from the most recent run's checkpoint.

    Args:
        job_id: Job ID to get failures for.

    Returns:
        List of failed parameter dicts with 'parameters', 'endpoint', 'error'.
    """
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT run_context
            FROM dw_etl_runs
            WHERE job_id = %s
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        if not row or not row[0]:
            return []

        ctx = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        checkpoint = ctx.get("checkpoint", {})
        return checkpoint.get("failed_parameters", [])


def get_all_historical_failures(job_id: int) -> list[dict]:
    """Get all unique failed parameters from all runs of a job.

    This collects failures from all historical runs, not just the most recent.

    Args:
        job_id: Job ID to get failures for.

    Returns:
        List of unique failed parameter dicts.
    """
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT run_context
            FROM dw_etl_runs
            WHERE job_id = %s
              AND run_context IS NOT NULL
              AND run_context::text LIKE '%%failed_parameters%%'
            ORDER BY started_at DESC
            """,
            (job_id,),
        )

        all_failures = {}
        for row in cursor.fetchall():
            ctx = row[0] if isinstance(row[0], dict) else json.loads(row[0])
            checkpoint = ctx.get("checkpoint", {})
            for failure in checkpoint.get("failed_parameters", []):
                params = failure.get("parameters", {})
                patient_id = params.get("patientId")
                if patient_id and patient_id not in all_failures:
                    all_failures[patient_id] = failure

        return list(all_failures.values())


def retry_patient(
    job_config: dict,
    patient_id: int,
    api_client: ClinicalConductorClient,
    data_loader: DataLoader,
    dry_run: bool = False,
) -> dict:
    """Retry a single patient for a job.

    Args:
        job_config: Job configuration dict.
        patient_id: Patient ID to retry.
        api_client: API client instance.
        data_loader: Data loader instance.
        dry_run: If True, don't write to database.

    Returns:
        Result dict with status, records, error.
    """
    endpoint = job_config["source_endpoint"].replace("{patientId}", str(patient_id))

    try:
        # Fetch data from API
        records = []
        for page in api_client.get_odata(endpoint, page_mode="iterator", dry_run=dry_run):
            if page.items:
                for item in page.items:
                    if isinstance(item, dict):
                        item["_parentId"] = str(patient_id)
                        records.append({"data": item})

        if not records:
            return {
                "status": "success",
                "records": 0,
                "error": None,
            }

        # Load to staging
        if not dry_run:
            result = data_loader.load_to_staging(
                table_name=job_config["target_table"],
                records=records,
                etl_job_id=job_config["id"],
                etl_run_id=None,  # No run ID for retries
                instance_id=job_config.get("source_instance_id"),
                dry_run=dry_run,
            )
            loaded = result.rows_inserted + result.rows_updated
        else:
            loaded = len(records)

        return {
            "status": "success",
            "records": loaded,
            "error": None,
        }

    except Exception as e:
        return {
            "status": "failed",
            "records": 0,
            "error": str(e),
        }


def get_job_config(job_id: int) -> Optional[dict]:
    """Get job configuration from database."""
    pool = get_pool()
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, source_endpoint, target_table, source_instance_id
            FROM dw_etl_jobs
            WHERE id = %s AND is_active = TRUE
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row[0],
            "name": row[1],
            "source_endpoint": row[2],
            "target_table": row[3],
            "source_instance_id": row[4],
        }


def main():
    parser = argparse.ArgumentParser(
        description="Retry failed patient parameters from ETL jobs"
    )
    parser.add_argument(
        "--jobs",
        type=str,
        help="Comma-separated list of job IDs to retry (default: all with failures)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be retried without making changes",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay in seconds between requests (default: 2.0)",
    )
    parser.add_argument(
        "--all-historical",
        action="store_true",
        help="Include failures from all historical runs, not just the most recent",
    )

    args = parser.parse_args()

    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
    )

    # Determine which jobs to process
    if args.jobs:
        job_ids = [int(j.strip()) for j in args.jobs.split(",")]
    else:
        job_ids = list(PATIENT_JOBS.keys())

    print("=" * 70)
    print("RETRY FAILED PATIENTS")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Jobs to check: {job_ids}")
    print(f"Delay between requests: {args.delay}s")
    print(f"Dry run: {args.dry_run}")
    print(f"Include historical failures: {args.all_historical}")
    print()

    # Initialize clients
    api_client = ClinicalConductorClient()
    data_loader = DataLoader()

    total_retried = 0
    total_success = 0
    total_failed = 0
    total_records = 0

    for job_id in job_ids:
        job_name = PATIENT_JOBS.get(job_id, f"Job {job_id}")
        job_config = get_job_config(job_id)

        if not job_config:
            print(f"Skipping Job {job_id}: not found or inactive")
            continue

        # Get failed parameters
        if args.all_historical:
            failures = get_all_historical_failures(job_id)
        else:
            failures = get_failed_parameters(job_id)

        if not failures:
            print(f"Job {job_id} ({job_name}): No failures to retry")
            continue

        print(f"\n{'=' * 70}")
        print(f"Job {job_id}: {job_name}")
        print(f"Failures to retry: {len(failures)}")
        print("=" * 70)

        job_success = 0
        job_failed = 0
        job_records = 0
        still_failing = []

        for i, failure in enumerate(failures):
            params = failure.get("parameters", {})
            patient_id = params.get("patientId")

            if not patient_id:
                continue

            total_retried += 1

            if args.dry_run:
                print(f"  [{i+1}/{len(failures)}] Would retry patient {patient_id}")
                job_success += 1
                continue

            # Retry with delay
            result = retry_patient(
                job_config=job_config,
                patient_id=patient_id,
                api_client=api_client,
                data_loader=data_loader,
                dry_run=args.dry_run,
            )

            if result["status"] == "success":
                job_success += 1
                job_records += result["records"]
                print(f"  [{i+1}/{len(failures)}] Patient {patient_id}: OK ({result['records']} records)")
            else:
                job_failed += 1
                still_failing.append({
                    "patient_id": patient_id,
                    "error": result["error"],
                })
                print(f"  [{i+1}/{len(failures)}] Patient {patient_id}: FAILED - {result['error'][:50]}...")

            # Delay between requests
            if i < len(failures) - 1:
                time.sleep(args.delay)

        total_success += job_success
        total_failed += job_failed
        total_records += job_records

        print(f"\nJob {job_id} summary: {job_success} success, {job_failed} failed, {job_records} records")

        if still_failing:
            print(f"Still failing patients: {[f['patient_id'] for f in still_failing[:10]]}...")

    # Print summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total patients retried: {total_retried}")
    print(f"Successful: {total_success}")
    print(f"Failed: {total_failed}")
    print(f"Records loaded: {total_records}")
    print("=" * 70)


if __name__ == "__main__":
    main()
