#!/usr/bin/env python3
"""Check and recommend timeout settings for ETL jobs.

Analyzes recent job runs to recommend appropriate timeout settings.
"""

import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import get_settings
from src.db import ConnectionPool

def analyze_job_timeouts():
    """Analyze job execution times and recommend timeouts."""
    settings = get_settings()
    pool = ConnectionPool(database_url=settings.database.url)
    pool.initialize()
    
    print("=" * 80)
    print("ETL JOB TIMEOUT ANALYSIS")
    print("=" * 80)
    print()
    
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        
        # Get recent successful job runs with their durations
        cursor.execute('''
            SELECT 
                j.id as job_id,
                j.name as job_name,
                COUNT(*) as run_count,
                AVG(r.duration_ms) as avg_duration_ms,
                MAX(r.duration_ms) as max_duration_ms,
                AVG(r.records_loaded) as avg_records,
                MAX(r.records_loaded) as max_records
            FROM dw_etl_runs r
            JOIN dw_etl_jobs j ON r.job_id = j.id
            WHERE r.run_status = 'success'
              AND r.completed_at > NOW() - INTERVAL '30 days'
              AND r.duration_ms IS NOT NULL
              AND r.duration_ms > 0
            GROUP BY j.id, j.name
            HAVING COUNT(*) > 0
            ORDER BY AVG(r.duration_ms) DESC
            LIMIT 20
        ''')
        
        jobs = cursor.fetchall()
        
        if not jobs:
            print("No recent successful runs found.")
            return
        
        print(f"Found {len(jobs)} jobs with recent successful runs:\n")
        print(f"{'Job ID':<8} {'Job Name':<30} {'Avg Duration':<15} {'Max Duration':<15} {'Avg Records':<12} {'Recommended Timeout':<20}")
        print("-" * 110)
        
        current_timeout = settings.etl.default_timeout_seconds * 1000  # Convert to ms
        
        for row in jobs:
            job_id, job_name, run_count, avg_ms, max_ms, avg_records, max_records = row
            
            avg_sec = (avg_ms or 0) / 1000
            max_sec = (max_ms or 0) / 1000
            avg_rec = int(avg_records or 0)
            max_rec = int(max_records or 0)
            
            # Recommend timeout: 2x max duration, minimum 300s, rounded up to nearest 5 minutes
            recommended_sec = max(300, int((max_sec * 2) / 300) * 300)
            if recommended_sec > 3600:
                recommended_sec = int((recommended_sec / 3600) + 0.5) * 3600  # Round to nearest hour
            
            # Format durations
            avg_str = f"{avg_sec:.1f}s" if avg_sec < 60 else f"{avg_sec/60:.1f}m"
            max_str = f"{max_sec:.1f}s" if max_sec < 60 else f"{max_sec/60:.1f}m"
            rec_str = f"{recommended_sec/60:.0f}m" if recommended_sec < 3600 else f"{recommended_sec/3600:.0f}h"
            
            # Check if current timeout is sufficient
            status = "✅" if max_sec < current_timeout / 1000 else "⚠️"
            
            print(f"{job_id:<8} {job_name[:28]:<30} {avg_str:<15} {max_str:<15} {avg_rec:>10,} {rec_str:<20} {status}")
        
        print()
        print(f"Current default timeout: {settings.etl.default_timeout_seconds}s ({settings.etl.default_timeout_seconds/60:.1f} minutes)")
        print()
        
        # Check for jobs that might need higher timeout
        cursor.execute('''
            SELECT 
                j.id,
                j.name,
                COUNT(*) as timeout_count
            FROM dw_etl_runs r
            JOIN dw_etl_jobs j ON r.job_id = j.id
            WHERE r.run_status IN ('failed', 'running')
              AND r.error_message LIKE '%timeout%'
              AND r.started_at > NOW() - INTERVAL '7 days'
            GROUP BY j.id, j.name
            ORDER BY timeout_count DESC
        ''')
        
        timeout_jobs = cursor.fetchall()
        
        if timeout_jobs:
            print("⚠️  Jobs with recent timeout issues:")
            for job_id, job_name, count in timeout_jobs:
                print(f"   Job {job_id} ({job_name}): {count} timeout(s)")
            print()
            print("   Consider increasing timeout for these jobs.")
        else:
            print("✅ No recent timeout issues detected.")
        
        print()
        print("=" * 80)
    
    pool.close()


if __name__ == "__main__":
    analyze_job_timeouts()

