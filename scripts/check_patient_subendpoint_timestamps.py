#!/usr/bin/env python3
"""Check timestamp fields for patient-scoped sub-endpoints.

This script queries patient sub-endpoints (allergies, conditions, etc.) to identify
what timestamp fields are available for incremental loading.

Requires a valid patient ID to test the parameterized endpoints.
"""

import os
import sys
from typing import Any

import structlog

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.client import ClinicalConductorClient, ODataParams
from src.config import get_settings, reload_settings
from src.db.connection import get_pool

logger = structlog.get_logger(__name__)

# Common timestamp field names to look for
TIMESTAMP_FIELDS = [
    "modifiedDate",
    "modifiedOn",
    "lastUpdatedOn",
    "lastModified",
    "updatedAt",
    "updatedDate",
    "changedDate",
    "createdDate",
    "lastModifiedDate",
    "createDate",
    "updateDate",
]

# Patient sub-endpoints to check (parameterized by patientId)
PATIENT_SUBENDPOINTS = [
    ("/api/v1/patients/{patientId}/allergies/odata", "Patient Allergies", True),
    ("/api/v1/patients/{patientId}/conditions/odata", "Patient Conditions", True),
    ("/api/v1/patients/{patientId}/devices/odata", "Patient Devices", True),
    ("/api/v1/patients/{patientId}/medications/odata", "Patient Medications", True),
    ("/api/v1/patients/{patientId}/procedures/odata", "Patient Procedures", True),
    ("/api/v1/patients/{patientId}/immunizations/odata", "Patient Immunizations", True),
    ("/api/v1/patients/{patientId}/family-history/odata", "Patient Family History", True),
    ("/api/v1/patients/{patientId}/social-history/odata", "Patient Social History", True),
    ("/api/v1/patients/{patientId}/providers/odata", "Patient Providers", True),
    ("/api/v1/patients/{patientId}/touches/campaign/odata", "Patient Campaign Touches", True),
    ("/api/v1/patients/{patientId}/touches/referral/odata", "Patient Referral Touches", True),
]


def get_sample_patient_ids(limit: int = 5) -> list[int]:
    """Get sample patient IDs from the database.

    First tries dim_patients (Silver), then dim_patients_staging (Bronze).
    """
    pool = get_pool()

    with pool.get_connection() as conn:
        cursor = conn.cursor()

        # Try Silver layer first
        try:
            cursor.execute("""
                SELECT DISTINCT patient_id
                FROM dim_patients
                WHERE is_current = TRUE
                ORDER BY patient_id
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
            if rows:
                cursor.close()
                return [row[0] for row in rows]
        except Exception as e:
            logger.warning("Could not query dim_patients", error=str(e))

        # Fall back to Bronze layer
        try:
            cursor.execute("""
                SELECT DISTINCT (data->>'id')::INTEGER as patient_id
                FROM dim_patients_staging
                WHERE data->>'id' IS NOT NULL
                ORDER BY patient_id
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
            if rows:
                cursor.close()
                return [row[0] for row in rows]
        except Exception as e:
            logger.warning("Could not query dim_patients_staging", error=str(e))

        cursor.close()

    return []


def find_timestamp_fields(record: dict[str, Any]) -> list[str]:
    """Find timestamp fields in a record."""
    found_fields = []

    # Check known timestamp field names
    for field in TIMESTAMP_FIELDS:
        if field in record:
            found_fields.append(field)

    # Also check for any field ending with Date, On, or At that looks like a timestamp
    for key in record.keys():
        if key not in found_fields:
            key_lower = key.lower()
            if any(key_lower.endswith(suffix) for suffix in ['date', 'on', 'at']):
                value = record[key]
                if isinstance(value, str) and ('T' in value or 'Z' in value or '-' in value):
                    found_fields.append(key)

    return list(set(found_fields))  # Remove duplicates


def check_endpoint(
    client: ClinicalConductorClient,
    endpoint: str,
    name: str,
    is_odata: bool,
    patient_id: int,
) -> dict[str, Any]:
    """Check an endpoint for timestamp fields."""
    # Substitute patient ID
    actual_endpoint = endpoint.replace("{patientId}", str(patient_id))

    print(f"\n{'='*80}")
    print(f"Checking: {name}")
    print(f"Endpoint: {actual_endpoint}")
    print(f"{'='*80}")

    try:
        if is_odata:
            # Use ODataParams to limit results
            params = ODataParams(top=10)
            # get_odata is a generator that yields Page objects
            # Collect items from the first page only
            records = []
            for page in client.get_odata(actual_endpoint, params=params, page_mode="iterator", dry_run=False):
                records.extend(page.items[:5])  # Get first 5 items
                break  # Only need first page
        else:
            result = client._make_request("GET", actual_endpoint, dry_run=False)
            if isinstance(result, list):
                records = result[:5]
            elif isinstance(result, dict):
                records = [result]
            else:
                print(f"  ⚠️  Unexpected response type: {type(result)}")
                return {
                    "endpoint": endpoint,
                    "name": name,
                    "patient_id": patient_id,
                    "status": "error",
                    "error": f"Unexpected response type: {type(result)}",
                }

        if not records:
            print(f"  ⚠️  No records returned for patient {patient_id}")
            return {
                "endpoint": endpoint,
                "name": name,
                "patient_id": patient_id,
                "status": "no_data",
                "timestamp_fields": [],
                "all_fields": [],
            }

        # Check first record for timestamp fields
        first_record = records[0]
        timestamp_fields = find_timestamp_fields(first_record)
        all_fields = sorted(list(first_record.keys()))

        print(f"  ✅ Found {len(records)} sample record(s)")
        print(f"  📋 Timestamp fields found: {', '.join(timestamp_fields) if timestamp_fields else 'None'}")

        # Show sample values
        if timestamp_fields:
            print(f"\n  Sample timestamp values:")
            for field in timestamp_fields[:5]:
                if field in first_record:
                    value = first_record[field]
                    print(f"    - {field}: {value}")

        # Show all fields for reference
        print(f"\n  All fields ({len(all_fields)} total):")
        for i in range(0, len(all_fields), 5):
            chunk = all_fields[i:i+5]
            print(f"    {', '.join(chunk)}")

        return {
            "endpoint": endpoint,
            "name": name,
            "patient_id": patient_id,
            "status": "success",
            "timestamp_fields": timestamp_fields,
            "all_fields": all_fields,
            "record_count": len(records),
        }

    except Exception as e:
        print(f"  ❌ Error: {e}")
        logger.error("endpoint_check_failed", endpoint=actual_endpoint, error=str(e))
        return {
            "endpoint": endpoint,
            "name": name,
            "patient_id": patient_id,
            "status": "error",
            "error": str(e),
        }


def main():
    """Main function."""
    # Set environment to production to allow API calls
    # This script only reads data, it doesn't write anything
    os.environ["ENVIRONMENT"] = "production"
    os.environ["DRY_RUN"] = "false"

    # Reload settings to pick up environment changes
    settings = reload_settings()

    print("="*80)
    print("Timestamp Field Analysis for Patient Sub-Endpoints")
    print("="*80)
    print("\nThis script checks patient-scoped endpoints (allergies, medications, etc.)")
    print("to identify timestamp fields for incremental loading.\n")

    # Get sample patient IDs
    print("Fetching sample patient IDs from database...")
    patient_ids = get_sample_patient_ids(limit=10)

    if not patient_ids:
        print("❌ Could not find any patient IDs in the database.")
        print("   Please ensure dim_patients or dim_patients_staging has data.")
        sys.exit(1)

    print(f"✅ Found {len(patient_ids)} sample patient IDs: {patient_ids[:5]}...")

    # Initialize API client
    client = ClinicalConductorClient(
        base_url=settings.api.base_url,
        api_key=settings.api.key,
        default_top=10,
        max_pages=1,
    )

    results = []

    # For each endpoint, try multiple patients until we get data
    for endpoint_template, name, is_odata in PATIENT_SUBENDPOINTS:
        result = None

        for patient_id in patient_ids:
            result = check_endpoint(client, endpoint_template, name, is_odata, patient_id)

            # If we got data, stop trying other patients
            if result["status"] == "success" and result.get("record_count", 0) > 0:
                break
            elif result["status"] == "no_data":
                # Try next patient
                continue
            elif result["status"] == "error":
                # Log error but try next patient
                continue

        if result:
            results.append(result)

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")

    endpoints_with_timestamps = []
    endpoints_without_timestamps = []
    endpoints_with_no_data = []
    endpoints_with_errors = []

    for result in results:
        if result["status"] == "error":
            endpoints_with_errors.append(result)
        elif result["status"] == "no_data":
            endpoints_with_no_data.append(result)
        elif result.get("timestamp_fields"):
            endpoints_with_timestamps.append(result)
        else:
            endpoints_without_timestamps.append(result)

    print(f"✅ Endpoints WITH timestamp fields ({len(endpoints_with_timestamps)}):")
    for result in endpoints_with_timestamps:
        fields = ", ".join(result["timestamp_fields"])
        print(f"   - {result['name']}: {fields}")

    print(f"\n⚠️  Endpoints WITHOUT timestamp fields ({len(endpoints_without_timestamps)}):")
    for result in endpoints_without_timestamps:
        print(f"   - {result['name']} (fields: {', '.join(result.get('all_fields', [])[:5])}...)")

    print(f"\n📭 Endpoints with NO DATA ({len(endpoints_with_no_data)}):")
    for result in endpoints_with_no_data:
        print(f"   - {result['name']}")

    if endpoints_with_errors:
        print(f"\n❌ Endpoints with errors ({len(endpoints_with_errors)}):")
        for result in endpoints_with_errors:
            print(f"   - {result['name']}: {result.get('error', 'Unknown error')}")

    # Recommendations
    print(f"\n{'='*80}")
    print("RECOMMENDATIONS FOR INCREMENTAL LOADING")
    print(f"{'='*80}\n")

    # Find the most common timestamp field
    all_fields = []
    for result in endpoints_with_timestamps:
        all_fields.extend(result["timestamp_fields"])

    if all_fields:
        from collections import Counter
        field_counts = Counter(all_fields)
        print("Timestamp field frequency:")
        for field, count in field_counts.most_common():
            print(f"  - {field}: {count} endpoints")

        most_common = field_counts.most_common(1)[0]
        print(f"\nRecommended timestamp_field_name: '{most_common[0]}'")
    else:
        print("⚠️  No timestamp fields found in any patient sub-endpoint.")
        print("   Incremental loading on these endpoints may not be supported.")
        print("   Consider using changed patient tracking from dim_patients instead.")

    # Generate SQL update statements
    print(f"\n{'='*80}")
    print("SQL UPDATE STATEMENTS")
    print(f"{'='*80}\n")

    job_mapping = {
        "Patient Devices": 147,
        "Patient Allergies": 148,
        "Patient Providers": 149,
        "Patient Conditions": 150,
        "Patient Procedures": 151,
        "Patient Medications": 152,
        "Patient Immunizations": 153,
        "Patient Family History": 154,
        "Patient Social History": 155,
        "Patient Campaign Touches": 156,
        "Patient Referral Touches": 157,
    }

    for result in endpoints_with_timestamps:
        job_id = job_mapping.get(result["name"])
        if job_id and result["timestamp_fields"]:
            ts_field = result["timestamp_fields"][0]  # Use first found
            print(f"-- {result['name']} (Job {job_id})")
            print(f"UPDATE dw_etl_jobs")
            print(f"SET incremental_load = TRUE,")
            print(f"    timestamp_field_name = '{ts_field}'")
            print(f"WHERE id = {job_id};\n")

    print("="*80)


if __name__ == "__main__":
    main()
