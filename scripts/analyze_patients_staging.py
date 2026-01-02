#!/usr/bin/env python3
"""Analyze patients_staging table to see what fields are present and missing."""

import os
import sys
import json
from collections import Counter

os.environ["ENVIRONMENT"] = "development"
os.environ["DRY_RUN"] = "false"

import psycopg2
import psycopg2.extras

from src.config import get_settings
from src.db import ConnectionPool


def get_all_keys_from_jsonb(data):
    """Recursively extract all keys from JSONB."""
    keys = set()
    
    if isinstance(data, dict):
        for key, value in data.items():
            keys.add(key)
            if isinstance(value, (dict, list)):
                keys.update(get_all_keys_from_jsonb(value))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                keys.update(get_all_keys_from_jsonb(item))
    
    return keys


def analyze_patients_staging(pool: ConnectionPool):
    """Analyze patients staging table."""
    print("="*80)
    print("PATIENTS STAGING ANALYSIS")
    print("="*80)
    
    with pool.get_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get table structure
        print("\n1. Table Structure:")
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'dim_patients_staging'
            ORDER BY ordinal_position
        """)
        
        columns = cursor.fetchall()
        print(f"   Columns: {len(columns)}")
        for col in columns:
            print(f"     - {col['column_name']}: {col['data_type']}")
        
        # Get record count
        cursor.execute("SELECT COUNT(*) as cnt FROM dim_patients_staging")
        total_records = cursor.fetchone()['cnt']
        print(f"\n2. Total Records: {total_records:,}")
        
        # Sample records to analyze fields
        print("\n3. Analyzing JSONB Fields:")
        cursor.execute("""
            SELECT data
            FROM dim_patients_staging
            ORDER BY loaded_at DESC
            LIMIT 100
        """)
        
        samples = cursor.fetchall()
        print(f"   Analyzing {len(samples)} sample records...")
        
        # Collect all keys
        all_keys = Counter()
        top_level_keys = Counter()
        nested_keys = Counter()
        
        for sample in samples:
            data = sample.get('data') or sample
            if isinstance(data, dict):
                # Top-level keys
                for key in data.keys():
                    top_level_keys[key] += 1
                    all_keys[key] += 1
                
                # Nested keys
                for key, value in data.items():
                    if isinstance(value, dict):
                        for nested_key in value.keys():
                            nested_keys[f"{key}.{nested_key}"] += 1
                            all_keys[f"{key}.{nested_key}"] += 1
                    elif isinstance(value, list) and value and isinstance(value[0], dict):
                        for nested_key in value[0].keys():
                            nested_keys[f"{key}[].{nested_key}"] += 1
                            all_keys[f"{key}[].{nested_key}"] += 1
        
        print(f"\n   Top-Level Fields Found ({len(top_level_keys)}):")
        for key, count in top_level_keys.most_common():
            pct = (count / len(samples)) * 100
            print(f"     - {key}: {count}/{len(samples)} ({pct:.1f}%)")
        
        print(f"\n   Important Nested Fields:")
        important_nested = [k for k, v in nested_keys.most_common(20) if v >= len(samples) * 0.5]
        for key in important_nested:
            count = nested_keys[key]
            pct = (count / len(samples)) * 100
            print(f"     - {key}: {count}/{len(samples)} ({pct:.1f}%)")
        
        # Check for common searchable fields
        print("\n4. Searchable Fields Analysis:")
        searchable_fields = {
            'id': "data->>'id'",
            'status': "data->>'status'",
            'firstName': "data->>'firstName'",
            'lastName': "data->>'lastName'",
            'displayName': "data->>'displayName'",
            'email': "data->'primaryEmail'->>'email'",
            'phone': "data->'phone1'->>'number'",
            'dateOfBirth': "data->>'dateOfBirth'",
            'uid': "data->>'uid'",
        }
        
        for field_name, json_path in searchable_fields.items():
            cursor.execute(f"""
                SELECT COUNT(*) as cnt
                FROM dim_patients_staging
                WHERE {json_path} IS NOT NULL
            """)
            count = cursor.fetchone()['cnt']
            pct = (count / total_records) * 100 if total_records > 0 else 0
            print(f"   {field_name:20} ({json_path:30}): {count:>8,} ({pct:>5.1f}%)")
        
        # Check patient ID in JSONB
        print("\n5. Patient ID Analysis:")
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN data->>'id' IS NOT NULL THEN 1 END) as has_id,
                COUNT(CASE WHEN data->>'id' IS NULL THEN 1 END) as missing_id
            FROM dim_patients_staging
        """)
        id_stats = cursor.fetchone()
        print(f"   Total records: {id_stats['total']:,}")
        print(f"   Has id in JSONB: {id_stats['has_id']:,}")
        print(f"   Missing id in JSONB: {id_stats['missing_id']:,}")
        
        # Sample record structure
        print("\n6. Sample Record Structure:")
        if samples:
            sample = samples[0]['data']
            print(f"   Sample record keys: {list(sample.keys())[:20]}...")
            print(f"   Full structure (first record):")
            print(json.dumps(sample, indent=2, default=str)[:1000] + "...")
        
        return {
            'total_records': total_records,
            'top_level_keys': dict(top_level_keys),
            'nested_keys': dict(nested_keys),
            'searchable_fields': searchable_fields
        }


def check_silver_layer(pool: ConnectionPool):
    """Check if silver layer patients table exists."""
    print("\n" + "="*80)
    print("SILVER LAYER CHECK")
    print("="*80)
    
    with pool.get_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check if dim_patients exists
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('dim_patients', 'dim_patient')
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        
        if tables:
            print("\n✅ Silver layer patient table(s) found:")
            for table in tables:
                print(f"   - {table['table_name']}")
                
                # Get structure
                cursor.execute(f"""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = '{table['table_name']}'
                    ORDER BY ordinal_position
                """)
                columns = cursor.fetchall()
                print(f"     Columns ({len(columns)}):")
                for col in columns[:15]:
                    print(f"       - {col['column_name']}: {col['data_type']}")
                if len(columns) > 15:
                    print(f"       ... and {len(columns) - 15} more")
                
                # Get record count
                cursor.execute(f"SELECT COUNT(*) as cnt FROM {table['table_name']}")
                count = cursor.fetchone()['cnt']
                print(f"     Records: {count:,}")
        else:
            print("\n⚠️  No silver layer patient table found")
            print("   Recommendation: Create dim_patients table in silver layer")


def main():
    """Main function."""
    settings = get_settings()
    pool = ConnectionPool(database_url=settings.database.url)
    pool.initialize()
    
    try:
        analysis = analyze_patients_staging(pool)
        check_silver_layer(pool)
        
        print("\n" + "="*80)
        print("RECOMMENDATIONS")
        print("="*80)
        print("\n1. Staging Layer Options:")
        print("   a) Add computed columns for common searches:")
        print("      - patient_id (INTEGER) from data->>'id'")
        print("      - status (VARCHAR) from data->>'status'")
        print("      - display_name (VARCHAR) from data->>'displayName'")
        print("      - email (VARCHAR) from data->'primaryEmail'->>'email'")
        print("   b) Add indexes on these columns for performance")
        print("   c) Keep JSONB for full data preservation")
        
        print("\n2. Silver Layer Options:")
        print("   a) Create dim_patients table with Type 2 SCD")
        print("   b) Extract all important fields into columns")
        print("   c) Add proper indexes and constraints")
        print("   d) This is the recommended approach for production")
        
        print("\n3. Rebuild Strategy:")
        print("   a) Truncate dim_patients_staging")
        print("   b) Re-run Patients ETL job (Job ID 3)")
        print("   c) Verify all fields are captured")
        print("   d) Then transform to silver layer")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        pool.close()


if __name__ == "__main__":
    sys.exit(main())

