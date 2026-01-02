#!/usr/bin/env python3
"""Reload patients_staging with chunking and resumability support."""

import os
import sys
import time
from datetime import datetime

# Set environment to production to allow API calls, but we'll verify dev API
os.environ["ENVIRONMENT"] = "production"
os.environ["DRY_RUN"] = "false"

import psycopg2
import psycopg2.extras
import structlog

from src.config import get_settings
from src.db import ConnectionPool
from src.etl import JobExecutor
from src.api.client import ClinicalConductorClient, ODataParams

logger = structlog.get_logger(__name__)

PATIENTS_JOB_ID = 3
DEFAULT_CHUNK_SIZE = 1000  # API limit is 1000 for $top, so we use 1000 per chunk


def ensure_source_id_column(pool: ConnectionPool):
    """Ensure source_id column exists in staging table."""
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'dim_patients_staging'
            AND column_name = 'source_id'
        """)
        
        if cursor.fetchone():
            print("✅ source_id column exists")
            return True
        
        print("Adding source_id column...")
        
        # Add column
        cursor.execute("""
            ALTER TABLE dim_patients_staging 
            ADD COLUMN source_id VARCHAR(255)
        """)
        
        # Populate from existing data
        cursor.execute("""
            UPDATE dim_patients_staging
            SET source_id = data->>'id'
            WHERE source_id IS NULL AND data->>'id' IS NOT NULL
        """)
        
        # Create unique index
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_dim_patients_staging_source_id 
            ON dim_patients_staging(source_id) 
            WHERE source_id IS NOT NULL
        """)
        
        conn.commit()
        print("✅ Added source_id column and unique index")
        return True


def load_patients_chunked(pool: ConnectionPool, start_from_id: int = 0, chunk_size: int = DEFAULT_CHUNK_SIZE):
    """Load patients in chunks with resumability."""
    settings = get_settings()
    
    # Verify dev API
    if 'usimportccs09' not in settings.api.base_url.lower():
        print(f"\n❌ ERROR: Not pointing to dev API!")
        return False
    
    print(f"\n✅ Using DEV API: {settings.api.base_url}")
    
    # Update database credential to use .env key
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE dw_api_credentials
            SET api_key = %s,
                base_url = %s,
                updated_at = NOW()
            WHERE id = 1
        """, (settings.api.key, settings.api.base_url.replace('/api/v1', '')))
        conn.commit()
        print("✅ Database credential updated with .env API key")
    
    # Initialize API client (will use database credentials in production mode)
    client = ClinicalConductorClient()
    
    # Get total count first
    print("\nFetching total patient count...")
    try:
        first_page = next(client.get_odata(
            "/api/v1/patients/odata",
            params=ODataParams(top=1),
            page_mode="iterator",
            dry_run=False
        ))
        total_count = first_page.count if first_page.count else 0
        print(f"Total patients in API: {total_count:,}")
    except Exception as e:
        print(f"⚠️  Could not get count: {e}")
        total_count = 0
    
    # Truncate if starting from 0
    if start_from_id == 0:
        print("\n⚠️  Starting fresh - truncating staging table...")
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("TRUNCATE TABLE dim_patients_staging")
            conn.commit()
        print("✅ Table truncated")
    else:
        print(f"\n📌 Resuming from patient ID: {start_from_id}")
        print("   (Skipping records already loaded)")
    
    # Load in chunks
    print(f"\n{'='*80}")
    print("LOADING PATIENTS IN CHUNKS")
    print(f"{'='*80}")
    print(f"Chunk size: {chunk_size:,} records")
    print(f"Starting from ID: {start_from_id}")
    
    executor = JobExecutor()
    all_loaded = 0
    chunk_num = 0
    last_id = start_from_id
    
    # Use $filter to get records in chunks by ID
    # This allows resumability
    try:
        while True:
            chunk_num += 1
            print(f"\n--- Chunk {chunk_num} ---")
            
            # Build filter to get next chunk
            # Get records where id > last_id, ordered by id, limit chunk_size
            filter_expr = f"id gt {last_id}"
            
            params = ODataParams(
                filter=filter_expr,
                orderby="id asc",
                top=chunk_size
            )
            
            print(f"Fetching patients where id > {last_id} (up to {chunk_size:,} records)...")
            
            # Fetch chunk
            chunk_items = []
            try:
                for page in client.get_odata(
                    "/api/v1/patients/odata",
                    params=params,
                    page_mode="iterator",
                    dry_run=False
                ):
                    if isinstance(page.items, list):
                        chunk_items.extend(page.items)
                    
                    # If we got fewer than top, we're done
                    if len(page.items) < chunk_size:
                        break
                
                if not chunk_items:
                    print("✅ No more records to load")
                    break
                
                print(f"Fetched {len(chunk_items):,} records")
                
                # Load this chunk using executor's data loader
                records = [{"data": item} for item in chunk_items if isinstance(item, dict)]
                
                if records:
                    # Create a run ID for this chunk
                    with pool.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO dw_etl_runs (job_id, run_status, parameters)
                            VALUES (%s, 'running', NULL)
                            RETURNING id
                        """, (PATIENTS_JOB_ID,))
                        run_id = cursor.fetchone()[0]
                        conn.commit()
                    
                    result = executor.data_loader.load_to_staging(
                        table_name="dim_patients_staging",
                        records=records,
                        etl_job_id=PATIENTS_JOB_ID,
                        etl_run_id=run_id,
                        dry_run=False,
                    )
                    
                    # Update run status
                    with pool.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE dw_etl_runs
                            SET run_status = 'success',
                                records_loaded = %s,
                                completed_at = NOW()
                            WHERE id = %s
                        """, (result.rows_inserted + result.rows_updated, run_id))
                        conn.commit()
                    
                    loaded = result.rows_inserted + result.rows_updated
                    all_loaded += loaded
                    
                    print(f"Loaded: {loaded:,} records (inserted: {result.rows_inserted:,}, updated: {result.rows_updated:,})")
                    print(f"Total loaded so far: {all_loaded:,}")
                    
                    # Update last_id for next chunk
                    if chunk_items:
                        valid_ids = [int(item.get("id", 0)) for item in chunk_items if isinstance(item, dict) and item.get("id")]
                        if valid_ids:
                            last_id = max(valid_ids)
                            print(f"Last ID processed: {last_id}")
                
                # Small delay between chunks
                time.sleep(0.5)
                
            except Exception as e:
                print(f"\n❌ Error in chunk {chunk_num}: {e}")
                print(f"   Last successful ID: {last_id}")
                print(f"   You can resume by running with --resume-from {last_id}")
                raise
            
            # Check if we got fewer records than requested (end of data)
            if len(chunk_items) < chunk_size:
                print("\n✅ Reached end of data")
                break
        
        print(f"\n{'='*80}")
        print("LOAD COMPLETE")
        print(f"{'='*80}")
        print(f"Total records loaded: {all_loaded:,}")
        
        # Verify
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM dim_patients_staging")
            count = cursor.fetchone()[0]
            print(f"Records in staging: {count:,}")
            
            # Field coverage
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN data->>'id' IS NOT NULL THEN 1 END) as has_id,
                    COUNT(CASE WHEN data->>'status' IS NOT NULL THEN 1 END) as has_status,
                    COUNT(CASE WHEN data->>'displayName' IS NOT NULL THEN 1 END) as has_display_name
                FROM dim_patients_staging
            """)
            stats = cursor.fetchone()
            if stats[0] > 0:
                print(f"\nField Coverage:")
                print(f"  ID: {stats[1]:,}/{stats[0]:,} ({stats[1]/stats[0]*100:.1f}%)")
                print(f"  Status: {stats[2]:,}/{stats[0]:,} ({stats[2]/stats[0]*100:.1f}%)")
                print(f"  Display Name: {stats[3]:,}/{stats[0]:,} ({stats[3]/stats[0]*100:.1f}%)")
        
        return True
        
    except KeyboardInterrupt:
        print(f"\n\n⚠️  Interrupted by user")
        print(f"Last successful ID: {last_id}")
        print(f"To resume: python scripts/reload_patients_with_chunking.py --resume-from {last_id}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error("chunked_load_error", error=str(e), last_id=last_id, exc_info=True)
        print(f"\nLast successful ID: {last_id}")
        print(f"To resume: python scripts/reload_patients_with_chunking.py --resume-from {last_id}")
        return False


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Reload patients_staging with chunking')
    parser.add_argument('--resume-from', type=int, default=0,
                       help='Resume from this patient ID (for resumability)')
    parser.add_argument('--chunk-size', type=int, default=DEFAULT_CHUNK_SIZE,
                       help=f'Chunk size (default: {DEFAULT_CHUNK_SIZE})')
    args = parser.parse_args()
    
    chunk_size = args.chunk_size
    
    print("="*80)
    print("RELOAD PATIENTS STAGING (WITH CHUNKING)")
    print("="*80)
    print(f"\nThis will:")
    if args.resume_from == 0:
        print("  1. Truncate dim_patients_staging")
        print("  2. Fetch ALL patient records from CC dev API in chunks")
        print("  3. Load them into staging")
    else:
        print(f"  1. Resume loading from patient ID {args.resume_from}")
        print("  2. Skip records already loaded")
        print("  3. Continue loading remaining records")
    print(f"\nChunk size: {chunk_size:,} records")
    print("This may take several minutes...")
    
    if args.resume_from == 0:
        response = input("\nProceed? (yes/no): ")
        if response.lower() != 'yes':
            print("Cancelled.")
            return 0
    
    settings = get_settings()
    pool = ConnectionPool(database_url=settings.database.url)
    pool.initialize()
    
    try:
        # Ensure source_id column exists
        ensure_source_id_column(pool)
        
        # Determine starting point
        if args.resume_from > 0:
            start_id = args.resume_from
        else:
            start_id = 0
        
        # Load patients
        success = load_patients_chunked(pool, start_from_id=start_id, chunk_size=chunk_size)
        
        if success:
            print("\n✅ Reload Complete!")
            print("\nNext steps:")
            print("  1. Analyze: python scripts/analyze_patients_staging.py")
            print("  2. Load to silver: CALL load_dw_dim_patient();")
        
        return 0 if success else 1
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        pool.close()


if __name__ == "__main__":
    sys.exit(main())
