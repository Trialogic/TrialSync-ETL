#!/usr/bin/env python3
"""Run all patient sub-endpoint ETL jobs in parallel.

This script executes all 11 patient sub-endpoint jobs concurrently to speed up
the initial import. Each job processes a different endpoint so they can run
simultaneously without conflicts.

Usage:
    # Run all jobs in parallel (default)
    python scripts/run_patient_jobs_parallel.py

    # Dry run (no actual data loading)
    python scripts/run_patient_jobs_parallel.py --dry-run

    # Run specific jobs only
    python scripts/run_patient_jobs_parallel.py --jobs 178,179,180

    # Limit max concurrent jobs (default: all 11)
    python scripts/run_patient_jobs_parallel.py --max-workers 4
"""

import argparse
import sys
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Job definitions - all "Changed" patient sub-endpoint jobs
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


def run_single_job(job_id: int, dry_run: bool = False) -> dict:
    """Execute a single ETL job and return results.

    This function runs in a separate process.
    """
    # Import inside function to avoid multiprocessing issues
    from src.etl.executor import JobExecutor
    import structlog

    # Configure logging for this process
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
    )

    job_name = PATIENT_JOBS.get(job_id, f"Job {job_id}")
    start_time = time.time()

    try:
        executor = JobExecutor()
        result = executor.execute_job(job_id, dry_run=dry_run)

        duration = time.time() - start_time

        return {
            "job_id": job_id,
            "job_name": job_name,
            "status": result.status,
            "records_loaded": result.records_loaded,
            "duration_seconds": duration,
            "error": result.error_message,
        }

    except Exception as e:
        duration = time.time() - start_time
        return {
            "job_id": job_id,
            "job_name": job_name,
            "status": "failed",
            "records_loaded": 0,
            "duration_seconds": duration,
            "error": str(e),
        }


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def main():
    parser = argparse.ArgumentParser(
        description="Run patient sub-endpoint ETL jobs in parallel"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no actual data loading)",
    )
    parser.add_argument(
        "--jobs",
        type=str,
        help="Comma-separated list of job IDs to run (default: all)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=11,
        help="Maximum number of concurrent jobs (default: 11)",
    )

    args = parser.parse_args()

    # Determine which jobs to run
    if args.jobs:
        job_ids = [int(j.strip()) for j in args.jobs.split(",")]
        # Validate job IDs
        invalid = [j for j in job_ids if j not in PATIENT_JOBS]
        if invalid:
            print(f"Error: Invalid job IDs: {invalid}")
            print(f"Valid job IDs: {list(PATIENT_JOBS.keys())}")
            sys.exit(1)
    else:
        job_ids = list(PATIENT_JOBS.keys())

    # Print banner
    print("=" * 70)
    print("PARALLEL PATIENT SUB-ENDPOINT ETL JOBS")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Jobs to run: {len(job_ids)}")
    print(f"Max workers: {args.max_workers}")
    print(f"Dry run: {args.dry_run}")
    print()

    # List jobs
    print("Jobs queued:")
    for job_id in job_ids:
        print(f"  - [{job_id}] {PATIENT_JOBS[job_id]}")
    print()

    # Run jobs in parallel
    start_time = time.time()
    results = []
    completed = 0

    print("=" * 70)
    print("EXECUTION")
    print("=" * 70)

    with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        # Submit all jobs
        future_to_job = {
            executor.submit(run_single_job, job_id, args.dry_run): job_id
            for job_id in job_ids
        }

        # Process results as they complete
        for future in as_completed(future_to_job):
            job_id = future_to_job[future]
            completed += 1

            try:
                result = future.result()
                results.append(result)

                # Print progress
                status_icon = "✓" if result["status"] == "success" else "✗"
                print(
                    f"[{completed}/{len(job_ids)}] {status_icon} "
                    f"{result['job_name']}: "
                    f"{result['records_loaded']:,} records in "
                    f"{format_duration(result['duration_seconds'])}"
                )

                if result["error"]:
                    print(f"         Error: {result['error'][:100]}...")

            except Exception as e:
                print(f"[{completed}/{len(job_ids)}] ✗ Job {job_id}: Exception - {e}")
                results.append({
                    "job_id": job_id,
                    "job_name": PATIENT_JOBS.get(job_id, f"Job {job_id}"),
                    "status": "failed",
                    "records_loaded": 0,
                    "duration_seconds": 0,
                    "error": str(e),
                })

    total_duration = time.time() - start_time

    # Print summary
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)

    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]
    total_records = sum(r["records_loaded"] for r in results)

    print(f"Total duration: {format_duration(total_duration)}")
    print(f"Jobs completed: {len(successful)}/{len(results)}")
    print(f"Total records loaded: {total_records:,}")
    print()

    if successful:
        print("Successful jobs:")
        for r in sorted(successful, key=lambda x: x["records_loaded"], reverse=True):
            print(f"  ✓ {r['job_name']}: {r['records_loaded']:,} records")

    if failed:
        print()
        print("Failed jobs:")
        for r in failed:
            print(f"  ✗ {r['job_name']}: {r['error'][:80]}...")

    print()
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Exit with error code if any jobs failed
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
