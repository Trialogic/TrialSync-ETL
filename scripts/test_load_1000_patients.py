#!/usr/bin/env python3
"""Test load 1000 patients and verify completeness."""

import os
import sys
import time

# Set environment to production to allow API calls
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
TARGET_COUNT = 1000  # Load exactly 1000 patients for testing


def ensure_source_id_column(pool: ConnectionPool):
    """Ensure source_id column exists in staging table."""
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'dim_patients_staging'
            AND column_name = 'source_id'
        """)
        
        if cursor.fetchone():
            return True
        
        print("Adding source_id column...")
        cursor.execute("""
            ALTER TABLE dim_patients_staging 
            ADD COLUMN source_id VARCHAR(255)
        """)
        cursor.execute("""
            UPDATE dim_patients_staging
            SET source_id = data->>'id'
            WHERE source_id IS NULL AND data->>'id' IS NOT NULL
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_dim_patients_staging_source_id 
            ON dim_patients_staging(source_id) 
            WHERE source_id IS NOT NULL
        """)
        conn.commit()
        return True


def load_test_patients(pool: ConnectionPool):
    """Load exactly 1000 patients for testing."""
    settings = get_settings()
    
    # Verify dev API
    if 'usimportccs09' not in settings.api.base_url.lower():
        print(f"\n❌ ERROR: Not pointing to dev API!")
        return False
    
    print(f"\n✅ Using DEV API: {settings.api.base_url}")
    
    # Update database credential
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
    
    # Truncate staging
    print("\n⚠️  Truncating staging table...")
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE dim_patients_staging")
        conn.commit()
    print("✅ Table truncated")
    
    # Initialize API client
    client = ClinicalConductorClient()
    executor = JobExecutor()
    
    print(f"\n{'='*80}")
    print(f"LOADING {TARGET_COUNT} PATIENTS FOR TESTING")
    print(f"{'='*80}")
    
    all_items = []
    last_id = 0
    chunk_size = 1000  # API limit
    
    # Fetch in chunks until we have 1000
    while len(all_items) < TARGET_COUNT:
        filter_expr = f"id gt {last_id}"
        params = ODataParams(
            filter=filter_expr,
            orderby="id asc",
            top=chunk_size
        )
        
        print(f"\nFetching patients where id > {last_id} (need {TARGET_COUNT - len(all_items)} more)...")
        
        chunk_items = []
        for page in client.get_odata(
            "/api/v1/patients/odata",
            params=params,
            page_mode="iterator",
            dry_run=False
        ):
            if isinstance(page.items, list):
                chunk_items.extend(page.items)
        
        if not chunk_items:
            print("✅ No more records available")
            break
        
        # Only take what we need
        needed = TARGET_COUNT - len(all_items)
        all_items.extend(chunk_items[:needed])
        
        if chunk_items:
            last_id = max(int(item.get("id", 0)) for item in chunk_items if isinstance(item, dict) and item.get("id"))
        
        print(f"Fetched {len(chunk_items):,} records, total so far: {len(all_items):,}")
        
        if len(all_items) >= TARGET_COUNT:
            break
    
    print(f"\n✅ Fetched {len(all_items):,} patient records from API")
    
    # Load to staging
    print("\nLoading to staging table...")
    records = [{"data": item} for item in all_items if isinstance(item, dict)]
    
    if records:
        # Create a run ID
        with pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dw_etl_runs (job_id, run_status)
                VALUES (%s, 'running')
                RETURNING id
            """, (PATIENTS_JOB_ID,))
            run_id = cursor.fetchone()[0]
            conn.commit()
        
        # Get instance_id from job config (source_instance_id = 1 for dev)
        result = executor.data_loader.load_to_staging(
            table_name="dim_patients_staging",
            records=records,
            etl_job_id=PATIENTS_JOB_ID,
            etl_run_id=run_id,
            instance_id=1,  # source_instance_id from job config
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
        
        print(f"✅ Loaded: {result.rows_inserted + result.rows_updated:,} records")
        print(f"   Inserted: {result.rows_inserted:,}")
        print(f"   Updated: {result.rows_updated:,}")
    
    return True


def verify_completeness(pool: ConnectionPool):
    """Verify data completeness."""
    print(f"\n{'='*80}")
    print("DATA COMPLETENESS VERIFICATION")
    print(f"{'='*80}")
    
    with pool.get_connection() as conn:
        cursor = conn.cursor()
        
        # Total count
        cursor.execute("SELECT COUNT(*) FROM dim_patients_staging")
        total = cursor.fetchone()[0]
        print(f"\nTotal Records: {total:,}")
        
        if total == 0:
            print("❌ No records found!")
            return False
        
        # Field coverage
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN source_id IS NOT NULL THEN 1 END) as has_source_id,
                COUNT(CASE WHEN data->>'id' IS NOT NULL THEN 1 END) as has_id,
                COUNT(CASE WHEN data->>'status' IS NOT NULL THEN 1 END) as has_status,
                COUNT(CASE WHEN data->>'displayName' IS NOT NULL THEN 1 END) as has_display_name,
                COUNT(CASE WHEN data->>'firstName' IS NOT NULL THEN 1 END) as has_first_name,
                COUNT(CASE WHEN data->>'lastName' IS NOT NULL THEN 1 END) as has_last_name,
                COUNT(CASE WHEN data->>'dateOfBirth' IS NOT NULL THEN 1 END) as has_dob,
                COUNT(CASE WHEN data->'primaryEmail'->>'email' IS NOT NULL THEN 1 END) as has_email,
                COUNT(CASE WHEN data->'phone1'->>'number' IS NOT NULL THEN 1 END) as has_phone,
                COUNT(CASE WHEN data->>'address1' IS NOT NULL THEN 1 END) as has_address,
                COUNT(CASE WHEN data->'primarySite'->>'id' IS NOT NULL THEN 1 END) as has_site
            FROM dim_patients_staging
        """)
        stats = cursor.fetchone()
        
        print("\nField Coverage:")
        print("-" * 80)
        fields = [
            ("source_id", stats[1]),
            ("data->id", stats[2]),
            ("data->status", stats[3]),
            ("data->displayName", stats[4]),
            ("data->firstName", stats[5]),
            ("data->lastName", stats[6]),
            ("data->dateOfBirth", stats[7]),
            ("data->email", stats[8]),
            ("data->phone", stats[9]),
            ("data->address1", stats[10]),
            ("data->primarySite->id", stats[11]),
        ]
        
        for field_name, count in fields:
            pct = (count / total * 100) if total > 0 else 0
            status = "✅" if pct >= 95 else "⚠️" if pct >= 50 else "❌"
            print(f"{status} {field_name:<30} {count:>6,}/{total:>6,} ({pct:>5.1f}%)")
        
        # Sample record structure
        cursor.execute("""
            SELECT data
            FROM dim_patients_staging
            WHERE data IS NOT NULL
            LIMIT 1
        """)
        sample = cursor.fetchone()
        
        if sample:
            data = sample[0]
            if isinstance(data, dict):
                keys = sorted(list(data.keys()))
                print(f"\n📋 Sample Record Structure:")
                print(f"   Total fields: {len(keys)}")
                print(f"   Top 30 fields: {', '.join(keys[:30])}")
                if len(keys) > 30:
                    print(f"   ... and {len(keys) - 30} more fields")
        
        # Check for data consistency
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN source_id = data->>'id' THEN 1 END) as source_id_matches
            FROM dim_patients_staging
            WHERE source_id IS NOT NULL
        """)
        consistency = cursor.fetchone()
        if consistency[0] > 0:
            match_pct = (consistency[1] / consistency[0] * 100) if consistency[0] > 0 else 0
            print(f"\n🔍 Data Consistency:")
            print(f"   source_id matches data->id: {consistency[1]:,}/{consistency[0]:,} ({match_pct:.1f}%)")
        
        # Sample records
        cursor.execute("""
            SELECT 
                id,
                source_id,
                data->>'id' as patient_id,
                data->>'displayName' as display_name,
                data->>'status' as status,
                data->>'firstName' as first_name,
                data->>'lastName' as last_name,
                data->'primaryEmail'->>'email' as email,
                loaded_at
            FROM dim_patients_staging
            ORDER BY loaded_at DESC
            LIMIT 5
        """)
        print(f"\n📄 Sample Records (most recently loaded):")
        print("-" * 80)
        for row in cursor.fetchall():
            print(f"  ID: {row[0]}, Source ID: {row[1]}, Patient ID: {row[2]}")
            print(f"    Name: {row[3]} ({row[4]})")
            print(f"    First/Last: {row[5]} {row[6]}")
            print(f"    Email: {row[7] or 'N/A'}")
            print(f"    Loaded: {row[8]}")
            print()
    
    return True


def main():
    """Main function."""
    print("="*80)
    print("TEST LOAD: 1000 PATIENTS")
    print("="*80)
    print("\nThis will:")
    print("  1. Truncate dim_patients_staging")
    print(f"  2. Fetch exactly {TARGET_COUNT} patient records from CC dev API")
    print("  3. Load them into staging")
    print("  4. Verify data completeness")
    
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
        
        # Load test patients
        success = load_test_patients(pool)
        
        if success:
            # Verify completeness
            verify_completeness(pool)
            
            print("\n" + "="*80)
            print("✅ TEST COMPLETE!")
            print("="*80)
        
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

