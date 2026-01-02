#!/usr/bin/env python3
"""Analyze jobs that are repeatedly failing."""

import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.db import get_pool

def analyze_failing_jobs(days=7, min_failures=3):
    """Analyze jobs that are repeatedly failing.
    
    Args:
        days: Number of days to look back (default: 7)
        min_failures: Minimum number of failures to report (default: 3)
    """
    pool = get_pool()
    
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get all runs in the time period
        cursor.execute("""
            SELECT r.id, r.job_id, j.name, r.run_status, r.started_at, 
                   r.completed_at, r.error_message, r.records_loaded
            FROM dw_etl_runs r
            JOIN dw_etl_jobs j ON r.job_id = j.id
            WHERE r.started_at >= %s
            ORDER BY r.job_id, r.started_at DESC
        """, (cutoff_date,))
        
        runs = cursor.fetchall()
        
        # Group by job
        job_stats = defaultdict(lambda: {
            'name': '',
            'total_runs': 0,
            'success': 0,
            'failed': 0,
            'running': 0,
            'recent_failures': [],
            'last_success': None,
            'last_failure': None,
            'failure_rate': 0.0
        })
        
        for run in runs:
            run_id, job_id, job_name, status, started_at, completed_at, error_message, records_loaded = run
            
            stats = job_stats[job_id]
            stats['name'] = job_name
            stats['total_runs'] += 1
            
            if status == 'success':
                stats['success'] += 1
                if not stats['last_success'] or started_at > stats['last_success']:
                    stats['last_success'] = started_at
            elif status == 'failed':
                stats['failed'] += 1
                if not stats['last_failure'] or started_at > stats['last_failure']:
                    stats['last_failure'] = started_at
                
                # Track recent failures (last 5)
                stats['recent_failures'].append({
                    'run_id': run_id,
                    'started_at': started_at,
                    'error': error_message[:200] if error_message else 'No error message',
                    'records_loaded': records_loaded
                })
            elif status == 'running':
                stats['running'] += 1
        
        # Calculate failure rates
        for job_id, stats in job_stats.items():
            if stats['total_runs'] > 0:
                stats['failure_rate'] = (stats['failed'] / stats['total_runs']) * 100
            # Keep only last 5 failures
            stats['recent_failures'] = sorted(
                stats['recent_failures'],
                key=lambda x: x['started_at'],
                reverse=True
            )[:5]
        
        # Filter to jobs with minimum failures
        failing_jobs = {
            job_id: stats
            for job_id, stats in job_stats.items()
            if stats['failed'] >= min_failures
        }
        
        # Sort by failure count (descending)
        sorted_jobs = sorted(
            failing_jobs.items(),
            key=lambda x: (x[1]['failed'], x[1]['failure_rate']),
            reverse=True
        )
        
        if not sorted_jobs:
            print(f"No jobs found with {min_failures} or more failures in the last {days} days.")
            return
        
        print(f"Jobs with {min_failures}+ failures in the last {days} days:\n")
        print("=" * 100)
        
        for job_id, stats in sorted_jobs:
            print(f"\nJob ID: {job_id} - {stats['name']}")
            print(f"  Total Runs: {stats['total_runs']}")
            print(f"  Success: {stats['success']} | Failed: {stats['failed']} | Running: {stats['running']}")
            print(f"  Failure Rate: {stats['failure_rate']:.1f}%")
            
            if stats['last_success']:
                print(f"  Last Success: {stats['last_success']}")
            else:
                print(f"  Last Success: Never")
            
            if stats['last_failure']:
                print(f"  Last Failure: {stats['last_failure']}")
            
            if stats['recent_failures']:
                print(f"\n  Recent Failures ({len(stats['recent_failures'])}):")
                for failure in stats['recent_failures']:
                    print(f"    Run {failure['run_id']}: {failure['started_at']}")
                    print(f"      Error: {failure['error']}")
                    if failure['records_loaded']:
                        print(f"      Records: {failure['records_loaded']}")
            
            print("-" * 100)
        
        # Summary
        print(f"\nSummary:")
        print(f"  Total jobs analyzed: {len(job_stats)}")
        print(f"  Jobs with {min_failures}+ failures: {len(sorted_jobs)}")
        print(f"  Total failures across all jobs: {sum(s['failed'] for s in job_stats.values())}")
        print(f"  Total successes across all jobs: {sum(s['success'] for s in job_stats.values())}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze repeatedly failing ETL jobs")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)"
    )
    parser.add_argument(
        "--min-failures",
        type=int,
        default=3,
        help="Minimum number of failures to report (default: 3)"
    )
    
    args = parser.parse_args()
    
    analyze_failing_jobs(days=args.days, min_failures=args.min_failures)

