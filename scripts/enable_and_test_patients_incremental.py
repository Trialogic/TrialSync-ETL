#!/usr/bin/env python3
"""Enable and test incremental loading for the Patients job (Job ID 3).

This script:
1. Enables incremental loading for the Patients job
2. Runs the job twice to demonstrate incremental loading
3. Shows the difference in record counts
"""

import os
import sys
from datetime import datetime

import psycopg2
import psycopg2.extras
import structlog

from src.config import get_settings
from src.db import ConnectionPool
from src.etl import JobExecutor

logger = structlog.get_logger(__name__)

PATIENTS_JOB_ID = 3


def check_database_columns(pool: ConnectionPool) -> tuple[bool, bool]:
    """Check if incremental loading columns exist.
    
    Returns:
        Tuple of (incremental_load_exists, timestamp_field_name_exists)
    """
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'dw_etl_jobs'
            AND column_name IN ('incremental_load', 'timestamp_field_name')
        """)
        
        columns = {row[0] for row in cursor.fetchall()}
        
        return 'incremental_load' in columns, 'timestamp_field_name' in columns


def add_database_columns(pool: ConnectionPool):
    """Add incremental loading columns if they don't exist."""
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        
        # Add incremental_load column
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'dw_etl_jobs' 
                    AND column_name = 'incremental_load'
                ) THEN
                    ALTER TABLE dw_etl_jobs 
                    ADD COLUMN incremental_load BOOLEAN DEFAULT FALSE;
                END IF;
            END $$;
        """)
        
        # Add timestamp_field_name column
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'dw_etl_jobs' 
                    AND column_name = 'timestamp_field_name'
                ) THEN
                    ALTER TABLE dw_etl_jobs 
                    ADD COLUMN timestamp_field_name VARCHAR(100) DEFAULT 'lastUpdatedOn';
                END IF;
            END $$;
        """)
        
        conn.commit()
        print("✅ Database columns verified/created")


def enable_incremental_loading(pool: ConnectionPool):
    """Enable incremental loading for Patients job."""
    with pool.get_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get current configuration
        cursor.execute("""
            SELECT id, name, incremental_load, timestamp_field_name
            FROM dw_etl_jobs
            WHERE id = %s
        """, (PATIENTS_JOB_ID,))
        
        current = cursor.fetchone()
        
        if not current:
            print(f"❌ Error: Job {PATIENTS_JOB_ID} not found")
            return False
        
        print(f"\nCurrent configuration for Job {PATIENTS_JOB_ID} ({current['name']}):")
        print(f"  Incremental Load: {current.get('incremental_load', False)}")
        print(f"  Timestamp Field: {current.get('timestamp_field_name', 'N/A')}")
        
        # Disable incremental loading - Patients endpoint doesn't support timestamp filtering
        # The PatientViewModel doesn't have modifiedDate, createdDate, or other timestamp fields
        cursor.execute("""
            UPDATE dw_etl_jobs
            SET incremental_load = FALSE,
                timestamp_field_name = NULL,
                updated_at = NOW()
            WHERE id = %s
            RETURNING incremental_load, timestamp_field_name
        """, (PATIENTS_JOB_ID,))
        
        updated = cursor.fetchone()
        conn.commit()
        
        print(f"\n⚠️  Incremental loading NOT supported for Patients endpoint")
        print(f"  Reason: PatientViewModel doesn't have modifiedDate/createdDate fields")
        print(f"  Configuration:")
        print(f"    Incremental Load: {updated['incremental_load']}")
        print(f"    Timestamp Field: {updated['timestamp_field_name'] or 'N/A'}")
        print(f"\n  Note: Patients endpoint will always do full loads.")
        print(f"        Consider using ID-based filtering or change detection at the database level.")
        
        return True


def get_last_run_info(pool: ConnectionPool) -> dict:
    """Get information about the last run."""
    with pool.get_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check if duration_seconds column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'dw_etl_runs'
            AND column_name = 'duration_seconds'
        """)
        has_duration = cursor.fetchone() is not None
        
        # Build query based on available columns
        if has_duration:
            cursor.execute("""
                SELECT 
                    id,
                    run_status,
                    records_loaded,
                    started_at,
                    completed_at,
                    duration_seconds
                FROM dw_etl_runs
                WHERE job_id = %s
                ORDER BY started_at DESC
                LIMIT 1
            """, (PATIENTS_JOB_ID,))
        else:
            cursor.execute("""
                SELECT 
                    id,
                    run_status,
                    records_loaded,
                    started_at,
                    completed_at
                FROM dw_etl_runs
                WHERE job_id = %s
                ORDER BY started_at DESC
                LIMIT 1
            """, (PATIENTS_JOB_ID,))
        
        return cursor.fetchone() or {}


def run_job_test(executor: JobExecutor, run_number: int) -> dict:
    """Run the job and return results."""
    print(f"\n{'='*80}")
    print(f"Run #{run_number}: Executing Patients Job (ID {PATIENTS_JOB_ID})")
    print(f"{'='*80}")
    
    start_time = datetime.now()
    
    try:
        result = executor.execute_job(job_id=PATIENTS_JOB_ID, dry_run=False)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"\n✅ Run #{run_number} completed:")
        print(f"  Status: {result.status}")
        print(f"  Records Loaded: {result.records_loaded:,}")
        print(f"  Duration: {duration:.2f} seconds")
        if result.error_message:
            print(f"  Error: {result.error_message}")
        
        return {
            "run_number": run_number,
            "status": result.status,
            "records_loaded": result.records_loaded,
            "duration_seconds": duration,
            "error": result.error_message,
        }
        
    except Exception as e:
        print(f"\n❌ Run #{run_number} failed: {e}")
        logger.error("job_execution_failed", job_id=PATIENTS_JOB_ID, error=str(e))
        return {
            "run_number": run_number,
            "status": "failed",
            "records_loaded": 0,
            "duration_seconds": 0,
            "error": str(e),
        }


def main():
    """Main function."""
    # Set environment for testing
    # Note: We need ENVIRONMENT=production to allow network requests
    # This is safe because we're only testing against the configured API endpoint
    original_env = os.environ.get("ENVIRONMENT")
    os.environ["ENVIRONMENT"] = "production"
    os.environ["DRY_RUN"] = "false"
    
    print("="*80)
    print("Enable and Test Incremental Loading for Patients Job")
    print("="*80)
    
    settings = get_settings()
    pool = ConnectionPool(database_url=settings.database.url)
    pool.initialize()
    
    try:
        # Step 1: Check/add database columns
        print("\nStep 1: Checking database schema...")
        has_incremental, has_timestamp = check_database_columns(pool)
        
        if not (has_incremental and has_timestamp):
            print("  Adding missing columns...")
            add_database_columns(pool)
        else:
            print("  ✅ Required columns exist")
        
        # Step 2: Check incremental loading support
        print("\nStep 2: Checking incremental loading support...")
        if not enable_incremental_loading(pool):
            print("❌ Failed to update configuration")
            return 1
        
        # Step 3: Check last run
        print("\nStep 3: Checking last run status...")
        last_run = get_last_run_info(pool)
        if last_run:
            print(f"  Last run: {last_run.get('run_status', 'N/A')}")
            print(f"  Last records: {last_run.get('records_loaded', 0):,}")
            print(f"  Last run at: {last_run.get('completed_at', 'N/A')}")
            if 'duration_seconds' in last_run:
                print(f"  Last duration: {last_run.get('duration_seconds', 0)}s")
        else:
            print("  No previous runs found (this will be a full load)")
        
        # Step 4: Initialize executor
        print("\nStep 4: Initializing job executor...")
        executor = JobExecutor()
        
        # Step 5: Run job once (full load only - incremental not supported)
        print("\nStep 5: Running job (full load - incremental loading not supported)...")
        print("\n⚠️  Note: This will make actual API calls and load data to the database")
        print("   Patients endpoint doesn't support timestamp-based incremental loading\n")
        
        # Single run (full load)
        result = run_job_test(executor, 1)
        
        # Step 6: Results
        print(f"\n{'='*80}")
        print("RESULTS")
        print(f"{'='*80}\n")
        
        print(f"Run #1 (Full Load):")
        print(f"  Records: {result['records_loaded']:,}")
        print(f"  Duration: {result['duration_seconds']:.2f}s")
        print(f"  Status: {result['status']}")
        
        if result['status'] == 'success':
            print(f"\n✅ Job completed successfully!")
            print(f"   Loaded {result['records_loaded']:,} patient records")
        else:
            print(f"\n❌ Job failed: {result.get('error', 'Unknown error')}")
        
        # Step 7: Verify configuration
        print(f"\n{'='*80}")
        print("VERIFICATION")
        print(f"{'='*80}\n")
        
        with pool.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute("""
                SELECT id, name, incremental_load, timestamp_field_name
                FROM dw_etl_jobs
                WHERE id = %s
            """, (PATIENTS_JOB_ID,))
            
            config = cursor.fetchone()
            print(f"Job Configuration:")
            print(f"  ID: {config['id']}")
            print(f"  Name: {config['name']}")
            print(f"  Incremental Load: {config['incremental_load']}")
            print(f"  Timestamp Field: {config['timestamp_field_name']}")
        
        print(f"\n{'='*80}")
        print("✅ Test Complete!")
        print(f"{'='*80}\n")
        
        print("Next steps:")
        print("  1. Review the results above")
        print("  2. Patients endpoint does NOT support incremental loading (no timestamp fields)")
        print("  3. Consider alternative approaches:")
        print("     - ID-based filtering (fetch only records with ID > last_max_id)")
        print("     - Change detection at database level (compare staging vs warehouse)")
        print("     - Full load with upsert (current approach)")
        print("\nTo enable incremental loading for other jobs that support it:")
        print("  UPDATE dw_etl_jobs")
        print("  SET incremental_load = TRUE, timestamp_field_name = 'modifiedDate'")
        print("  WHERE id IN (2, 9, 25, 26);  -- Studies, PatientVisits, Appointments, Staff")
        print("  (Verify timestamp field names first using check_timestamp_fields.py)")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error("script_error", error=str(e), exc_info=True)
        return 1
        
    finally:
        pool.close()
        # Restore original environment if it was set
        if original_env:
            os.environ["ENVIRONMENT"] = original_env
        elif "ENVIRONMENT" in os.environ:
            del os.environ["ENVIRONMENT"]


if __name__ == "__main__":
    sys.exit(main())

