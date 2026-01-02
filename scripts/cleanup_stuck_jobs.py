#!/usr/bin/env python3
"""Clean up jobs stuck in 'running' status."""

import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.db import get_pool

def cleanup_stuck_jobs(max_age_minutes=60, dry_run=True):
    """Mark stuck jobs as failed.
    
    Args:
        max_age_minutes: Jobs running longer than this will be marked as stuck
        dry_run: If True, only show what would be changed without making changes
    """
    pool = get_pool()
    
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        
        # Find runs that have been running for more than max_age_minutes
        cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        
        cursor.execute("""
            SELECT r.id, r.job_id, j.name, r.run_status, r.started_at, 
                   NOW() - r.started_at as duration
            FROM dw_etl_runs r
            JOIN dw_etl_jobs j ON r.job_id = j.id
            WHERE r.run_status = 'running'
            AND r.started_at < %s
            ORDER BY r.started_at DESC
        """, (cutoff_time,))
        
        stuck_runs = cursor.fetchall()
        
        if not stuck_runs:
            print("No stuck jobs found.")
            return
        
        print(f"Found {len(stuck_runs)} stuck job(s):\n")
        for run in stuck_runs:
            run_id, job_id, job_name, status, started_at, duration = run
            print(f"  Run ID: {run_id} | Job: {job_id} ({job_name})")
            print(f"    Started: {started_at}")
            print(f"    Duration: {duration}")
            print()
        
        if dry_run:
            print("DRY RUN: Would mark these jobs as 'failed' with error 'Job appears to be stuck'")
            print("Run with --execute to actually update the database")
        else:
            # Calculate duration in milliseconds
            for run in stuck_runs:
                run_id, job_id, job_name, status, started_at, duration = run
                duration_seconds = duration.total_seconds()
                duration_ms = int(duration_seconds * 1000)
                
                error_message = f"Job appears to be stuck (running for {duration})"
                
                # Update the run
                cursor.execute("""
                    UPDATE dw_etl_runs
                    SET run_status = 'failed',
                        error_message = %s,
                        completed_at = NOW(),
                        duration_ms = %s
                    WHERE id = %s
                """, (error_message, duration_ms, run_id))
                
                # Update the job's last_run_* fields
                cursor.execute("""
                    UPDATE dw_etl_jobs
                    SET last_run_at = NOW(),
                        last_run_status = 'failed',
                        last_run_records = 0,
                        updated_at = NOW()
                    WHERE id = %s
                """, (job_id,))
            
            conn.commit()
            print(f"\n✓ Updated {len(stuck_runs)} stuck job(s) to 'failed' status")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up stuck ETL jobs")
    parser.add_argument(
        "--max-age",
        type=int,
        default=60,
        help="Maximum age in minutes for a job to be considered stuck (default: 60)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually update the database (default is dry-run)"
    )
    
    args = parser.parse_args()
    
    cleanup_stuck_jobs(
        max_age_minutes=args.max_age,
        dry_run=not args.execute
    )

