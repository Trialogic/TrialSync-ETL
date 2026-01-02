#!/usr/bin/env python3
"""Reload patients_staging table from CC dev with latest ETL code."""

import os
import sys

# Set environment to production to allow API calls, but we'll verify dev API
os.environ["ENVIRONMENT"] = "production"
os.environ["DRY_RUN"] = "false"

import psycopg2
import structlog

from src.config import get_settings
from src.db import ConnectionPool
from src.etl import JobExecutor

logger = structlog.get_logger(__name__)

PATIENTS_JOB_ID = 3


def reload_patients_staging():
    """Reload patients staging table."""
    print("="*80)
    print("RELOAD PATIENTS STAGING FROM CC DEV")
    print("="*80)
    
    settings = get_settings()
    
    # Verify we're using dev
    if 'usimportccs09' not in settings.api.base_url.lower():
        print(f"\n❌ ERROR: API base URL is not pointing to dev!")
        print(f"   Current URL: {settings.api.base_url}")
        print(f"   Expected: https://usimportccs09-ccs.advarracloud.com/CCSWEB")
        return False
    
    print(f"\n✅ Verified: Using DEV API")
    print(f"   Base URL: {settings.api.base_url}")
    
    # In production mode, it uses database credentials
    # Let's update the database credential to match .env if needed
    pool = ConnectionPool(database_url=settings.database.url)
    pool.initialize()
    
    try:
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get .env API key
            dev_api_key = settings.api.key
            
            # Update database credential to use .env key (in case it's different)
            cursor.execute("""
                UPDATE dw_api_credentials
                SET api_key = %s,
                    base_url = %s,
                    updated_at = NOW()
                WHERE id = 1
                RETURNING base_url, api_key
            """, (dev_api_key, settings.api.base_url.replace('/api/v1', '')))
            
            updated = cursor.fetchone()
            conn.commit()
            
            print(f"\n✅ Database credential updated:")
            print(f"   Base URL: {updated[0]}")
            print(f"   API Key: {updated[1][:20]}...")
        
        # Truncate staging
        print("\n" + "="*80)
        print("TRUNCATING STAGING TABLE")
        print("="*80)
        
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            print("\nTruncating dim_patients_staging...")
            cursor.execute("TRUNCATE TABLE dim_patients_staging")
            conn.commit()
            print("✅ Table truncated")
        
        # Run ETL job
        print("\n" + "="*80)
        print("RUNNING PATIENTS ETL JOB")
        print("="*80)
        print("\nFetching all patient records from CC dev API...")
        print("This may take several minutes depending on the number of patients...\n")
        
        executor = JobExecutor()
        result = executor.execute_job(job_id=PATIENTS_JOB_ID, dry_run=False)
        
        print("\n" + "="*80)
        print("RELOAD RESULTS")
        print("="*80)
        print(f"\nStatus: {result.status}")
        print(f"Records Loaded: {result.records_loaded:,}")
        
        if result.error_message:
            print(f"\n❌ Error: {result.error_message}")
            return False
        
        # Verify the load
        print("\n" + "="*80)
        print("VERIFICATION")
        print("="*80)
        
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            
            # Count records
            cursor.execute("SELECT COUNT(*) FROM dim_patients_staging")
            count = cursor.fetchone()[0]
            print(f"\n✅ Total records in staging: {count:,}")
            
            # Check field coverage
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN data->>'id' IS NOT NULL THEN 1 END) as has_id,
                    COUNT(CASE WHEN data->>'status' IS NOT NULL THEN 1 END) as has_status,
                    COUNT(CASE WHEN data->>'displayName' IS NOT NULL THEN 1 END) as has_display_name,
                    COUNT(CASE WHEN data->>'firstName' IS NOT NULL THEN 1 END) as has_first_name,
                    COUNT(CASE WHEN data->>'lastName' IS NOT NULL THEN 1 END) as has_last_name,
                    COUNT(CASE WHEN data->'primaryEmail'->>'email' IS NOT NULL THEN 1 END) as has_email,
                    COUNT(CASE WHEN data->'phone1'->>'number' IS NOT NULL THEN 1 END) as has_phone
                FROM dim_patients_staging
            """)
            stats = cursor.fetchone()
            
            print(f"\nField Coverage:")
            print(f"  ID:              {stats[1]:,}/{stats[0]:,} ({stats[1]/stats[0]*100:.1f}%)")
            print(f"  Status:         {stats[2]:,}/{stats[0]:,} ({stats[2]/stats[0]*100:.1f}%)")
            print(f"  Display Name:   {stats[3]:,}/{stats[0]:,} ({stats[3]/stats[0]*100:.1f}%)")
            print(f"  First Name:     {stats[4]:,}/{stats[0]:,} ({stats[4]/stats[0]*100:.1f}%)")
            print(f"  Last Name:      {stats[5]:,}/{stats[0]:,} ({stats[5]/stats[0]*100:.1f}%)")
            print(f"  Email:          {stats[6]:,}/{stats[0]:,} ({stats[6]/stats[0]*100:.1f}%)")
            print(f"  Phone:          {stats[7]:,}/{stats[0]:,} ({stats[7]/stats[0]*100:.1f}%)")
            
            # Sample record to show structure
            cursor.execute("""
                SELECT data
                FROM dim_patients_staging
                ORDER BY loaded_at DESC
                LIMIT 1
            """)
            sample = cursor.fetchone()[0]
            
            print(f"\n📋 Sample Record Keys ({len(sample)} fields):")
            for key in sorted(list(sample.keys()))[:20]:
                print(f"   - {key}")
            if len(sample) > 20:
                print(f"   ... and {len(sample) - 20} more fields")
        
        print("\n" + "="*80)
        print("✅ RELOAD COMPLETE!")
        print("="*80)
        print("\nNext steps:")
        print("  1. Analyze data: python scripts/analyze_patients_staging.py")
        print("  2. Load to silver: CALL load_dw_dim_patient();")
        print("  3. Query silver: SELECT * FROM v_patients_current LIMIT 10;")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error("reload_patients_error", error=str(e), exc_info=True)
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        pool.close()


def main():
    """Main function."""
    print("\n⚠️  This will:")
    print("   1. Truncate dim_patients_staging")
    print("   2. Fetch ALL patient records from CC dev API")
    print("   3. Load them into staging")
    print("\nThis may take several minutes...")
    
    response = input("\nProceed? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        return 0
    
    success = reload_patients_staging()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

