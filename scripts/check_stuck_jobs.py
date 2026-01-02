#!/usr/bin/env python3
"""Check for stuck jobs in 'running' status."""

import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.db import get_pool

def check_stuck_jobs():
    """Check for jobs stuck in 'running' status."""
    pool = get_pool()
    
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        
        # Find runs that have been running for more than 1 hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        cursor.execute("""
            SELECT r.id, r.job_id, j.name, r.run_status, r.started_at, 
                   NOW() - r.started_at as duration
            FROM dw_etl_runs r
            JOIN dw_etl_jobs j ON r.job_id = j.id
            WHERE r.run_status = 'running'
            AND r.started_at < %s
            ORDER BY r.started_at DESC
        """, (one_hour_ago,))
        
        stuck_runs = cursor.fetchall()
        
        if stuck_runs:
            print(f"Found {len(stuck_runs)} stuck job(s) in 'running' status:\n")
            for run in stuck_runs:
                run_id, job_id, job_name, status, started_at, duration = run
                print(f"  Run ID: {run_id}")
                print(f"  Job ID: {job_id} - {job_name}")
                print(f"  Status: {status}")
                print(f"  Started: {started_at}")
                print(f"  Duration: {duration}")
                print()
        else:
            print("No stuck jobs found.")
        
        # Also check current running jobs
        cursor.execute("""
            SELECT r.id, r.job_id, j.name, r.run_status, r.started_at, 
                   NOW() - r.started_at as duration
            FROM dw_etl_runs r
            JOIN dw_etl_jobs j ON r.job_id = j.id
            WHERE r.run_status = 'running'
            ORDER BY r.started_at DESC
        """)
        
        all_running = cursor.fetchall()
        
        if all_running:
            print(f"\nAll jobs currently in 'running' status ({len(all_running)}):\n")
            for run in all_running:
                run_id, job_id, job_name, status, started_at, duration = run
                print(f"  Run ID: {run_id} | Job: {job_id} ({job_name}) | Started: {started_at} | Duration: {duration}")

if __name__ == "__main__":
    check_stuck_jobs()

