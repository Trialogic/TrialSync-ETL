#!/usr/bin/env python3
"""Check which API endpoints have timestamp fields for incremental loading.

This script queries a sample of records from each endpoint to identify
what timestamp fields are available (modifiedDate, lastUpdatedOn, etc.)
"""

import os
import sys
from typing import Any, Optional

import structlog

from src.api.client import ClinicalConductorClient
from src.config import get_settings

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
]

# Key endpoints to check (focusing on patient-related and high-volume)
ENDPOINTS_TO_CHECK = [
    # Patient-related (high priority)
    ("/api/v1/patients/odata", "Patients", True),
    ("/api/v1/patient-visits/odata", "PatientVisits", True),
    ("/api/v1/appointments/odata", "Appointments", True),
    
    # Study-related
    ("/api/v1/studies/odata", "Studies", True),
    ("/api/v1/sites", "Sites", False),  # Non-OData
    
    # Other high-volume
    ("/api/v1/subject-statuses/odata", "SubjectStatuses", True),
    ("/api/v1/staff/odata", "Staff", True),
    ("/api/v1/elements/odata", "Elements", True),
]


def find_timestamp_fields(record: dict[str, Any]) -> list[str]:
    """Find timestamp fields in a record.
    
    Args:
        record: API response record
        
    Returns:
        List of timestamp field names found
    """
    found_fields = []
    
    for field in TIMESTAMP_FIELDS:
        if field in record:
            found_fields.append(field)
    
    # Also check for any field ending with Date, On, or At
    for key in record.keys():
        if key not in TIMESTAMP_FIELDS:
            if any(key.lower().endswith(suffix) for suffix in ['date', 'on', 'at']):
                if isinstance(record[key], str) and ('T' in record[key] or 'Z' in record[key]):
                    found_fields.append(key)
    
    return found_fields


def check_endpoint(
    client: ClinicalConductorClient,
    endpoint: str,
    name: str,
    is_odata: bool,
) -> dict[str, Any]:
    """Check an endpoint for timestamp fields.
    
    Args:
        client: API client
        endpoint: Endpoint path
        name: Display name
        is_odata: Whether endpoint is OData
        
    Returns:
        Dictionary with findings
    """
    print(f"\n{'='*80}")
    print(f"Checking: {name} ({endpoint})")
    print(f"{'='*80}")
    
    try:
        if is_odata:
            # Get first page of results
            result = client.get_odata(endpoint, top=10, dry_run=False)
            
            if isinstance(result, list):
                records = result[:5]  # Check first 5 records
            else:
                print(f"  ⚠️  Unexpected response type: {type(result)}")
                return {
                    "endpoint": endpoint,
                    "name": name,
                    "is_odata": is_odata,
                    "status": "error",
                    "error": f"Unexpected response type: {type(result)}",
                }
        else:
            # Non-OData endpoint
            result = client._make_request("GET", endpoint, dry_run=False)
            if isinstance(result, list):
                records = result[:5]
            elif isinstance(result, dict):
                records = [result]
            else:
                print(f"  ⚠️  Unexpected response type: {type(result)}")
                return {
                    "endpoint": endpoint,
                    "name": name,
                    "is_odata": is_odata,
                    "status": "error",
                    "error": f"Unexpected response type: {type(result)}",
                }
        
        if not records:
            print(f"  ⚠️  No records returned")
            return {
                "endpoint": endpoint,
                "name": name,
                "is_odata": is_odata,
                "status": "no_data",
                "timestamp_fields": [],
            }
        
        # Check first record for timestamp fields
        first_record = records[0]
        timestamp_fields = find_timestamp_fields(first_record)
        
        print(f"  ✅ Found {len(records)} sample record(s)")
        print(f"  📋 Timestamp fields found: {', '.join(timestamp_fields) if timestamp_fields else 'None'}")
        
        # Show sample values
        if timestamp_fields:
            print(f"\n  Sample timestamp values:")
            for field in timestamp_fields[:3]:  # Show first 3
                if field in first_record:
                    value = first_record[field]
                    print(f"    - {field}: {value}")
        
        # Show all top-level fields for reference
        print(f"\n  All top-level fields ({len(first_record)} total):")
        field_list = sorted(list(first_record.keys()))[:20]  # Show first 20
        print(f"    {', '.join(field_list)}")
        if len(first_record) > 20:
            print(f"    ... and {len(first_record) - 20} more")
        
        return {
            "endpoint": endpoint,
            "name": name,
            "is_odata": is_odata,
            "status": "success",
            "timestamp_fields": timestamp_fields,
            "sample_record_keys": list(first_record.keys())[:30],
        }
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        logger.error("endpoint_check_failed", endpoint=endpoint, error=str(e))
        return {
            "endpoint": endpoint,
            "name": name,
            "is_odata": is_odata,
            "status": "error",
            "error": str(e),
        }


def main():
    """Main function."""
    # Set environment
    os.environ["ENVIRONMENT"] = "development"
    os.environ["DRY_RUN"] = "false"
    
    settings = get_settings()
    client = ClinicalConductorClient(
        base_url=settings.api.base_url,
        api_key=settings.api.api_key,
        default_top=10,  # Small sample
        max_pages=1,  # Just first page
    )
    
    print("="*80)
    print("Timestamp Field Analysis for Clinical Conductor API Endpoints")
    print("="*80)
    print("\nThis script checks which endpoints have timestamp fields")
    print("that can be used for incremental loading.\n")
    
    results = []
    
    for endpoint, name, is_odata in ENDPOINTS_TO_CHECK:
        result = check_endpoint(client, endpoint, name, is_odata)
        results.append(result)
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")
    
    endpoints_with_timestamps = []
    endpoints_without_timestamps = []
    endpoints_with_errors = []
    
    for result in results:
        if result["status"] == "error":
            endpoints_with_errors.append(result)
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
        print(f"   - {result['name']}")
    
    if endpoints_with_errors:
        print(f"\n❌ Endpoints with errors ({len(endpoints_with_errors)}):")
        for result in endpoints_with_errors:
            print(f"   - {result['name']}: {result.get('error', 'Unknown error')}")
    
    print(f"\n{'='*80}")
    print("RECOMMENDATIONS")
    print(f"{'='*80}\n")
    
    # Find the most common timestamp field
    all_fields = []
    for result in endpoints_with_timestamps:
        all_fields.extend(result["timestamp_fields"])
    
    if all_fields:
        from collections import Counter
        field_counts = Counter(all_fields)
        most_common = field_counts.most_common(1)[0]
        print(f"Most common timestamp field: '{most_common[0]}' (found in {most_common[1]} endpoints)")
        print(f"\nRecommended default: timestamp_field_name = '{most_common[0]}'")
    
    print("\nTo enable incremental loading for a job:")
    print("  UPDATE dw_etl_jobs")
    print(f"  SET incremental_load = TRUE,")
    print(f"      timestamp_field_name = '{most_common[0] if all_fields else 'modifiedDate'}'")
    print("  WHERE id = <job_id>;")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()

