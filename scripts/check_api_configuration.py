#!/usr/bin/env python3
"""Check API configuration in database to ensure all jobs point to dev, not production."""

import os
import sys

os.environ["ENVIRONMENT"] = "development"
os.environ["DRY_RUN"] = "false"

import psycopg2
import psycopg2.extras

from src.config import get_settings
from src.db import ConnectionPool

PRODUCTION_HOSTS = [
    "tektonresearch.clinicalconductor.com",
    "tektonresearch.clinicalconductor.com/ccsweb",
]

DEV_HOST = "usimportccs09-ccs.advarracloud.com"

def check_api_credentials(pool: ConnectionPool):
    """Check API credentials table."""
    print("="*80)
    print("API CREDENTIALS CONFIGURATION")
    print("="*80)
    
    with pool.get_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # First check what columns exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'dw_api_credentials'
            ORDER BY ordinal_position
        """)
        columns = [row['column_name'] for row in cursor.fetchall()]
        
        # Build query based on available columns
        if 'instance_name' in columns:
            select_cols = "id, instance_name, base_url, api_key, is_active"
        else:
            select_cols = "id, base_url, api_key, is_active"
        
        cursor.execute(f"""
            SELECT {select_cols}
            FROM dw_api_credentials
            ORDER BY id
        """)
        
        credentials = cursor.fetchall()
        
        if not credentials:
            print("\n⚠️  No API credentials found in database")
            return []
        
        issues = []
        
        for cred in credentials:
            base_url_lower = cred['base_url'].lower()
            is_production = any(host in base_url_lower for host in PRODUCTION_HOSTS)
            is_dev = DEV_HOST in base_url_lower
            
            status = "✅ DEV" if is_dev else ("❌ PRODUCTION" if is_production else "⚠️  UNKNOWN")
            
            name = cred.get('instance_name', f"Credential {cred['id']}")
            print(f"\nCredential ID {cred['id']}: {name}")
            print(f"  Status: {status}")
            print(f"  Base URL: {cred['base_url']}")
            print(f"  Active: {cred['is_active']}")
            
            if is_production:
                issues.append({
                    'type': 'credential',
                    'id': cred['id'],
                    'name': name,
                    'base_url': cred['base_url'],
                    'action': 'Update to dev URL'
                })
        
        return issues


def check_etl_jobs(pool: ConnectionPool):
    """Check ETL jobs and their source_instance_id."""
    print("\n" + "="*80)
    print("ETL JOBS CONFIGURATION")
    print("="*80)
    
    with pool.get_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check if instance_name exists in credentials table
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'dw_api_credentials' AND column_name = 'instance_name'
        """)
        has_instance_name = cursor.fetchone() is not None
        
        if has_instance_name:
            cursor.execute("""
                SELECT 
                    j.id,
                    j.name,
                    j.source_endpoint,
                    j.source_instance_id,
                    c.instance_name,
                    c.base_url,
                    c.is_active as cred_active
                FROM dw_etl_jobs j
                LEFT JOIN dw_api_credentials c ON j.source_instance_id = c.id
                WHERE j.is_active = TRUE
                ORDER BY j.id
            """)
        else:
            cursor.execute("""
                SELECT 
                    j.id,
                    j.name,
                    j.source_endpoint,
                    j.source_instance_id,
                    NULL as instance_name,
                    c.base_url,
                    c.is_active as cred_active
                FROM dw_etl_jobs j
                LEFT JOIN dw_api_credentials c ON j.source_instance_id = c.id
                WHERE j.is_active = TRUE
                ORDER BY j.id
            """)
        
        jobs = cursor.fetchall()
        
        if not jobs:
            print("\n⚠️  No active ETL jobs found")
            return []
        
        issues = []
        jobs_with_prod = []
        
        print(f"\nTotal active jobs: {len(jobs)}")
        print(f"\nJobs using database credentials (source_instance_id != NULL):")
        
        for job in jobs:
            if job['source_instance_id'] is not None:
                base_url_lower = (job['base_url'] or '').lower()
                is_production = any(host in base_url_lower for host in PRODUCTION_HOSTS)
                
                status = "❌ PRODUCTION" if is_production else "✅ DEV" if DEV_HOST in base_url_lower else "⚠️  UNKNOWN"
                
                instance_name = job.get('instance_name') or f"Credential {job['source_instance_id']}"
                print(f"\n  Job {job['id']}: {job['name']}")
                print(f"    Instance ID: {job['source_instance_id']} ({instance_name})")
                print(f"    Base URL: {job['base_url']}")
                print(f"    Status: {status}")
                
                if is_production:
                    jobs_with_prod.append(job)
                    issues.append({
                        'type': 'job',
                        'job_id': job['id'],
                        'job_name': job['name'],
                        'instance_id': job['source_instance_id'],
                        'base_url': job['base_url'],
                        'action': 'Update credential or set source_instance_id to NULL'
                    })
        
        jobs_without_instance = [j for j in jobs if j['source_instance_id'] is None]
        print(f"\nJobs using .env credentials (source_instance_id = NULL): {len(jobs_without_instance)}")
        if jobs_without_instance:
            print(f"  These jobs will use CC_API_BASE_URL from .env file")
            job_ids = [f"Job {j['id']}" for j in jobs_without_instance[:5]]
            print(f"  First 5: {', '.join(job_ids)}")
        
        return issues


def main():
    """Main function."""
    print("="*80)
    print("API CONFIGURATION AUDIT")
    print("="*80)
    print("\nChecking for production API URLs in database configuration...")
    print(f"Production hosts to flag: {', '.join(PRODUCTION_HOSTS)}")
    print(f"Dev host expected: {DEV_HOST}")
    
    settings = get_settings()
    pool = ConnectionPool(database_url=settings.database.url)
    pool.initialize()
    
    try:
        # Check API credentials
        credential_issues = check_api_credentials(pool)
        
        # Check ETL jobs
        job_issues = check_etl_jobs(pool)
        
        # Summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        
        all_issues = credential_issues + job_issues
        
        if not all_issues:
            print("\n✅ No production URLs found! All configurations point to dev.")
        else:
            print(f"\n❌ Found {len(all_issues)} configuration(s) pointing to PRODUCTION:")
            
            for issue in all_issues:
                print(f"\n  {issue['type'].upper()}: {issue.get('name') or issue.get('job_name')}")
                print(f"    Current URL: {issue['base_url']}")
                print(f"    Action: {issue['action']}")
        
        print("\n" + "="*80)
        print("RECOMMENDATIONS")
        print("="*80)
        
        if credential_issues:
            print("\n1. Update API credentials in dw_api_credentials table:")
            for issue in credential_issues:
                print(f"   UPDATE dw_api_credentials")
                print(f"   SET base_url = 'https://{DEV_HOST}/CCSWEB'")
                print(f"   WHERE id = {issue['id']};")
        
        if job_issues:
            print("\n2. For jobs using production credentials, either:")
            print("   a) Update the credential they reference (see above), OR")
            print("   b) Set source_instance_id = NULL to use .env credentials:")
            for issue in job_issues:
                print(f"      UPDATE dw_etl_jobs")
                print(f"      SET source_instance_id = NULL")
                print(f"      WHERE id = {issue['job_id']};")
        
        print("\n3. Verify .env file has dev URL:")
        print(f"   CC_API_BASE_URL=https://{DEV_HOST}/CCSWEB")
        
        return 0 if not all_issues else 1
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        pool.close()


if __name__ == "__main__":
    sys.exit(main())

