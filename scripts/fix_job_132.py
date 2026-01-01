#!/usr/bin/env python3
"""Fix Job 132: System Study Statuses endpoint path.

Updates the ETL job configuration to use the correct endpoint path:
- Old: /api/v1/system/study-statuses/odata (404 error)
- New: /api/v1/system/study-statuses (working, returns array)
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import get_settings
from src.db import get_pool
import structlog

logger = structlog.get_logger(__name__)


def fix_job_132():
    """Update Job 132 endpoint configuration."""
    settings = get_settings()
    pool = get_pool()
    
    logger.info("fixing_job_132", job_id=132)
    
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        
        # First, check current configuration
        cursor.execute(
            """
            SELECT id, name, source_endpoint, requires_parameters, 
                   parameter_source_table, parameter_source_column
            FROM dw_etl_jobs
            WHERE id = 132
            """
        )
        current = cursor.fetchone()
        
        if not current:
            logger.error("job_not_found", job_id=132)
            print("❌ Error: Job 132 not found in database")
            return False
        
        job_id, name, current_endpoint, requires_params, param_table, param_column = current
        
        print(f"Current configuration for Job {job_id} ({name}):")
        print(f"  Endpoint: {current_endpoint}")
        print(f"  Requires Parameters: {requires_params}")
        print(f"  Parameter Source: {param_table}")
        print()
        
        # Update the configuration
        new_endpoint = "/api/v1/system/study-statuses"
        
        cursor.execute(
            """
            UPDATE dw_etl_jobs 
            SET 
                source_endpoint = %s,
                requires_parameters = false,
                parameter_source_table = NULL,
                parameter_source_column = NULL,
                updated_at = NOW()
            WHERE id = 132
            RETURNING id, name, source_endpoint, requires_parameters
            """,
            (new_endpoint,)
        )
        
        updated = cursor.fetchone()
        conn.commit()
        
        if updated:
            print("✅ Successfully updated Job 132 configuration:")
            print(f"  Job ID: {updated[0]}")
            print(f"  Name: {updated[1]}")
            print(f"  New Endpoint: {updated[2]}")
            print(f"  Requires Parameters: {updated[3]}")
            print()
            print("Verification:")
            print(f"  Old endpoint: {current_endpoint}")
            print(f"  New endpoint: {updated[2]}")
            print()
            
            if updated[2] == new_endpoint:
                print("✅ Configuration update verified successfully!")
                logger.info(
                    "job_132_fixed",
                    job_id=132,
                    old_endpoint=current_endpoint,
                    new_endpoint=new_endpoint
                )
                return True
            else:
                print("❌ Warning: Endpoint doesn't match expected value")
                return False
        else:
            print("❌ Error: Update did not affect any rows")
            logger.error("job_132_update_failed", job_id=132)
            return False


def main():
    """Main function."""
    print("=" * 80)
    print("Fix Job 132: System Study Statuses Endpoint")
    print("=" * 80)
    print()
    print("This script will update Job 132 to use the correct endpoint path:")
    print("  Old: /api/v1/system/study-statuses/odata (404 error)")
    print("  New: /api/v1/system/study-statuses (working)")
    print()
    
    try:
        success = fix_job_132()
        if success:
            print()
            print("=" * 80)
            print("✅ Job 132 configuration fixed successfully!")
            print("=" * 80)
            print()
            print("Next steps:")
            print("  1. Verify the update in the database")
            print("  2. Test the job: trialsync-etl run --job-id 132")
            print("  3. Check staging table: SELECT COUNT(*) FROM dim_system_study_statuses_staging;")
            return 0
        else:
            print()
            print("=" * 80)
            print("❌ Failed to update Job 132 configuration")
            print("=" * 80)
            return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception("fix_job_132_error", error=str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())

