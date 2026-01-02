#!/usr/bin/env python3
"""Fix production API URL to dev URL in database."""

import os
import sys

os.environ["ENVIRONMENT"] = "development"
os.environ["DRY_RUN"] = "false"

import psycopg2
import psycopg2.extras
import structlog

from src.config import get_settings
from src.db import ConnectionPool

logger = structlog.get_logger(__name__)

PRODUCTION_URL = "https://tektonresearch.clinicalconductor.com/CCSWEB"
DEV_URL = "https://usimportccs09-ccs.advarracloud.com/CCSWEB"


def fix_production_url(pool: ConnectionPool):
    """Update production URL to dev URL."""
    with pool.get_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check current state
        cursor.execute("""
            SELECT id, base_url, is_active
            FROM dw_api_credentials
            WHERE id = 1
        """)
        
        current = cursor.fetchone()
        
        if not current:
            print("❌ Credential ID 1 not found")
            return False
        
        print(f"\nCurrent configuration:")
        print(f"  ID: {current['id']}")
        print(f"  Base URL: {current['base_url']}")
        print(f"  Active: {current['is_active']}")
        
        if DEV_URL in current['base_url']:
            print("\n✅ Already pointing to dev! No update needed.")
            return True
        
        if PRODUCTION_URL not in current['base_url']:
            print(f"\n⚠️  URL is neither production nor dev: {current['base_url']}")
            response = input("Update to dev anyway? (yes/no): ")
            if response.lower() != 'yes':
                return False
        
        # Update to dev
        print(f"\nUpdating credential ID 1:")
        print(f"  From: {current['base_url']}")
        print(f"  To:   {DEV_URL}")
        
        cursor.execute("""
            UPDATE dw_api_credentials
            SET 
                base_url = %s,
                updated_at = NOW()
            WHERE id = 1
        """, (DEV_URL,))
        
        conn.commit()
        
        # Verify
        cursor.execute("""
            SELECT id, base_url, updated_at
            FROM dw_api_credentials
            WHERE id = 1
        """)
        
        updated = cursor.fetchone()
        
        if DEV_URL in updated['base_url']:
            print("\n✅ Successfully updated to dev URL!")
            print(f"   Updated at: {updated['updated_at']}")
            
            # Count affected jobs
            cursor.execute("""
                SELECT COUNT(*) as job_count
                FROM dw_etl_jobs
                WHERE source_instance_id = 1 AND is_active = TRUE
            """)
            job_count = cursor.fetchone()['job_count']
            print(f"   Affected jobs: {job_count}")
            
            logger.info(
                "production_url_fixed",
                credential_id=1,
                old_url=current['base_url'],
                new_url=DEV_URL,
                affected_jobs=job_count
            )
            return True
        else:
            print("\n❌ Update failed - URL not changed")
            return False


def main():
    """Main function."""
    print("="*80)
    print("Fix Production API URL to Dev URL")
    print("="*80)
    print("\nThis script will update credential ID 1 to point to dev environment.")
    print(f"Production: {PRODUCTION_URL}")
    print(f"Dev:        {DEV_URL}")
    
    response = input("\nProceed with update? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        return 0
    
    settings = get_settings()
    pool = ConnectionPool(database_url=settings.database.url)
    pool.initialize()
    
    try:
        if fix_production_url(pool):
            print("\n" + "="*80)
            print("✅ Fix Complete!")
            print("="*80)
            print("\nAll ETL jobs using credential ID 1 will now connect to dev.")
            print("\nNext steps:")
            print("  1. Verify the update: python scripts/check_api_configuration.py")
            print("  2. Test a job: trialsync-etl run --job-id 3 --dry-run")
            return 0
        else:
            print("\n❌ Fix failed")
            return 1
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error("fix_production_url_error", error=str(e), exc_info=True)
        return 1
        
    finally:
        pool.close()


if __name__ == "__main__":
    sys.exit(main())

