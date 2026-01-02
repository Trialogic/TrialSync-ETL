#!/usr/bin/env python3
"""Test checkpoint and resume functionality.

This script tests the checkpoint/resume feature by:
1. Running a job with a short timeout to trigger checkpoint
2. Verifying checkpoint was saved
3. Resuming from checkpoint
4. Verifying job completes successfully
"""

import os
import sys
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import get_settings
from src.db import ConnectionPool
from src.etl.executor import JobExecutor, CheckpointData, JobTimeoutError

def test_checkpoint_resume():
    """Test checkpoint and resume functionality."""
    settings = get_settings()
    pool = ConnectionPool(database_url=settings.database.url)
    pool.initialize()
    
    executor = JobExecutor()
    
    print("=" * 80)
    print("CHECKPOINT AND RESUME TEST")
    print("=" * 80)
    print()
    
    # Use a small job for testing (Sites has ~40 records)
    test_job_id = 1  # Sites job
    timeout_seconds = 10  # Very short timeout to trigger checkpoint quickly
    
    print(f"📋 Test Configuration:")
    print(f"   Job ID: {test_job_id} (Sites)")
    print(f"   Timeout: {timeout_seconds} seconds")
    print(f"   Expected: Job will timeout and save checkpoint")
    print()
    
    try:
        # Step 1: Run job with short timeout
        print("Step 1: Running job with short timeout...")
        print(f"   Started at: {datetime.now()}")
        
        result = executor.execute_job(
            job_id=test_job_id,
            dry_run=False,
            timeout_seconds=timeout_seconds,
        )
        
        print(f"   Status: {result.status}")
        print(f"   Records loaded: {result.records_loaded}")
        print(f"   Duration: {result.duration_seconds:.2f} seconds")
        if result.error_message:
            print(f"   Error: {result.error_message[:200]}...")
        print()
        
        run_id = result.run_id
        
        # Step 2: Check if checkpoint was saved
        print("Step 2: Checking for checkpoint...")
        checkpoint = executor.get_checkpoint(run_id)
        
        if checkpoint:
            print(f"   ✅ Checkpoint found!")
            print(f"      Skip: {checkpoint.skip}")
            print(f"      Page index: {checkpoint.page_index}")
            print(f"      Total records: {checkpoint.total_records}")
            print(f"      Last checkpoint: {checkpoint.last_checkpoint_time}")
            print()
            
            # Step 3: Resume from checkpoint
            print("Step 3: Resuming from checkpoint...")
            print(f"   Started at: {datetime.now()}")
            
            resume_result = executor.execute_job(
                job_id=test_job_id,
                dry_run=False,
                resume_from_checkpoint=True,
                timeout_seconds=300,  # Longer timeout for resume
            )
            
            print(f"   Status: {resume_result.status}")
            print(f"   Records loaded: {resume_result.records_loaded}")
            print(f"   Duration: {resume_result.duration_seconds:.2f} seconds")
            if resume_result.error_message:
                print(f"   Error: {resume_result.error_message[:200]}...")
            print()
            
            # Step 4: Verify final state
            print("Step 4: Verifying final state...")
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT run_status, records_loaded, error_message
                    FROM dw_etl_runs
                    WHERE id = %s
                    """,
                    (resume_result.run_id,),
                )
                final_state = cursor.fetchone()
                
                if final_state:
                    status, records, error = final_state
                    print(f"   Final status: {status}")
                    print(f"   Final records: {records}")
                    if error:
                        print(f"   Error: {error[:200]}...")
                    
                    if status == "success":
                        print()
                        print("   ✅ SUCCESS: Job completed after resume!")
                    else:
                        print()
                        print("   ⚠️  Job did not complete successfully")
            
        else:
            print("   ⚠️  No checkpoint found")
            print("   This could mean:")
            print("      - Job completed before timeout")
            print("      - Job failed before checkpoint could be saved")
            print("      - Checkpoint wasn't saved for another reason")
            print()
            
            # Check run status
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT run_status, records_loaded, error_message
                    FROM dw_etl_runs
                    WHERE id = %s
                    """,
                    (run_id,),
                )
                run_state = cursor.fetchone()
                if run_state:
                    status, records, error = run_state
                    print(f"   Run status: {status}")
                    print(f"   Records loaded: {records}")
                    if error:
                        print(f"   Error: {error[:200]}...")
        
        print()
        print("=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        
    except JobTimeoutError as e:
        print(f"   ⚠️  Timeout occurred (expected): {str(e)[:200]}...")
        print()
        print("   This is expected behavior. The checkpoint should be saved.")
        print("   Try running the test again to verify resume works.")
    except Exception as e:
        print(f"   ❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        pool.close()


if __name__ == "__main__":
    test_checkpoint_resume()

