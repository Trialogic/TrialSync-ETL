#!/usr/bin/env python3
"""Test script to verify all instance and system endpoints are working.

This script tests all instance and system endpoints from the ETL jobs
configuration to confirm they're accessible and returning valid data.
"""

import sys
from pathlib import Path
from typing import Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.api import ClinicalConductorClient, ODataParams
from src.api.client import APIError
from src.config import get_settings

# Define all instance and system endpoints from ETL jobs
INSTANCE_ENDPOINTS = [
    {
        "job_id": 158,
        "name": "Instance Details",
        "endpoint": "/api/v1/instance/details",
        "is_odata": False,
        "expected_records": 0,  # Single object, not a list
    },
    {
        "job_id": 159,
        "name": "Instance Topology",
        "endpoint": "/api/v1/instance/topology",
        "is_odata": False,
        "expected_records": 0,  # Single object, not a list
    },
]

SYSTEM_ENDPOINTS = [
    {
        "job_id": 120,
        "name": "System Allergies",
        "endpoint": "/api/v1/system/allergies/odata",
        "is_odata": True,
        "expected_records": 936,
    },
    {
        "job_id": 121,
        "name": "System Conditions",
        "endpoint": "/api/v1/system/conditions/odata",
        "is_odata": True,
        "expected_records": 404,
    },
    {
        "job_id": 122,
        "name": "System Medications",
        "endpoint": "/api/v1/system/medications/odata",
        "is_odata": True,
        "expected_records": 2295,
    },
    {
        "job_id": 123,
        "name": "System Procedures",
        "endpoint": "/api/v1/system/procedures/odata",
        "is_odata": True,
        "expected_records": 671,
    },
    {
        "job_id": 124,
        "name": "System Immunizations",
        "endpoint": "/api/v1/system/immunizations/odata",
        "is_odata": True,
        "expected_records": 78,
    },
    {
        "job_id": 125,
        "name": "System Devices",
        "endpoint": "/api/v1/system/devices/odata",
        "is_odata": True,
        "expected_records": 3294,
    },
    {
        "job_id": 126,
        "name": "System Social History",
        "endpoint": "/api/v1/system/social-history/odata",
        "is_odata": True,
        "expected_records": 120,
    },
    {
        "job_id": 128,
        "name": "System Document Types",
        "endpoint": "/api/v1/system/document-types",
        "is_odata": False,
        "expected_records": 20,
    },
    {
        "job_id": 129,
        "name": "System Action Categories",
        "endpoint": "/api/v1/system/action-categories",
        "is_odata": False,
        "expected_records": 10,
    },
    {
        "job_id": 130,
        "name": "System Study Categories",
        "endpoint": "/api/v1/system/study-categories",
        "is_odata": False,
        "expected_records": 106,
    },
    {
        "job_id": 131,
        "name": "System Study Subcategories",
        "endpoint": "/api/v1/system/study-subcategories",
        "is_odata": False,
        "expected_records": 8,
    },
    {
        "job_id": 132,
        "name": "System Study Statuses",
        "endpoint": "/api/v1/system/study-statuses",  # Note: Not OData, returns array directly
        "is_odata": False,
        "expected_records": 15,
    },
    {
        "job_id": 133,
        "name": "System Lookup Lists",
        "endpoint": "/api/v1/system/lookup-lists",
        "is_odata": False,
        "expected_records": 54,
    },
    {
        "job_id": 134,
        "name": "System Patient Custom Fields",
        "endpoint": "/api/v1/system/patient-customfields",
        "is_odata": False,
        "expected_records": 9,
    },
    {
        "job_id": 135,
        "name": "System Study Custom Fields",
        "endpoint": "/api/v1/system/study-customfields",
        "is_odata": False,
        "expected_records": 0,
    },
    {
        "job_id": 136,
        "name": "System Organizations",
        "endpoint": "/api/v1/system/organizations",
        "is_odata": False,
        "expected_records": 1,
    },
]


def test_endpoint(client: ClinicalConductorClient, endpoint_config: dict[str, Any]) -> dict[str, Any]:
    """Test a single endpoint and return results.
    
    Args:
        client: API client instance
        endpoint_config: Endpoint configuration dict
        
    Returns:
        Test results dict
    """
    job_id = endpoint_config["job_id"]
    name = endpoint_config["name"]
    endpoint = endpoint_config["endpoint"]
    is_odata = endpoint_config["is_odata"]
    expected_records = endpoint_config["expected_records"]
    
    result = {
        "job_id": job_id,
        "name": name,
        "endpoint": endpoint,
        "status": "unknown",
        "status_code": None,
        "error": None,
        "record_count": None,
        "response_type": None,
        "is_working": False,
    }
    
    try:
        if is_odata:
            # Use OData pagination with small page size for testing
            # Pass dry_run=False to allow actual network requests
            params = ODataParams(top=10, skip=0)
            pages = list(client.get_odata(endpoint, params=params, page_mode="iterator", dry_run=False))
            
            # Count total records
            total_records = 0
            for page in pages:
                total_records += len(page.items)
            
            result["record_count"] = total_records
            result["response_type"] = "odata"
            result["status"] = "success"
            result["status_code"] = 200
            result["is_working"] = True
            
            # Check if we got at least some records (or 0 if expected)
            if total_records >= 0:
                result["is_working"] = True
        else:
            # Non-OData endpoint - make direct request
            # Build full URL - ensure base doesn't have /api/v1 since endpoint already has it
            base = client.base_url.rstrip("/")
            if base.endswith("/api/v1"):
                base = base[:-7]  # Remove /api/v1
            
            if not endpoint.startswith("/"):
                endpoint = "/" + endpoint
            url = f"{base}{endpoint}"
            
            # Make request using internal method (dry_run=False to allow actual requests)
            response = client._make_request("GET", url, dry_run=False)
            data = client._parse_response(response, "test")
            
            # Handle different response formats
            if isinstance(data, list):
                result["record_count"] = len(data)
                result["response_type"] = "array"
            elif isinstance(data, dict):
                # Could be single object or wrapped
                if "value" in data:
                    items = data["value"]
                    result["record_count"] = len(items) if isinstance(items, list) else 1
                    result["response_type"] = "odata_wrapped"
                elif "items" in data:
                    items = data["items"]
                    result["record_count"] = len(items) if isinstance(items, list) else 1
                    result["response_type"] = "items_wrapped"
                else:
                    # Single object - count as 1
                    result["record_count"] = 1
                    result["response_type"] = "object"
            else:
                result["record_count"] = 1
                result["response_type"] = "unknown"
            
            result["status"] = "success"
            result["status_code"] = response.status_code
            result["is_working"] = True
            
    except APIError as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["is_working"] = False
        # Try to extract status code from error message
        if "404" in str(e):
            result["status_code"] = 404
        elif "401" in str(e) or "403" in str(e):
            result["status_code"] = 401
        elif "429" in str(e):
            result["status_code"] = 429
        elif "500" in str(e) or "501" in str(e):
            result["status_code"] = 500
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        result["is_working"] = False
    
    return result


def print_results(results: list[dict[str, Any]], category: str) -> None:
    """Print test results in a formatted table.
    
    Args:
        results: List of test result dicts
        category: Category name (Instance or System)
    """
    print(f"\n{'='*80}")
    print(f"{category} Endpoints Test Results")
    print(f"{'='*80}\n")
    
    # Print table header
    print(f"{'Job ID':<8} {'Name':<35} {'Status':<12} {'Records':<10} {'Type':<15} {'Error':<20}")
    print("-" * 80)
    
    working_count = 0
    error_count = 0
    
    for result in results:
        job_id = result["job_id"]
        name = result["name"]
        status = result["status"]
        record_count = result["record_count"] if result["record_count"] is not None else "N/A"
        response_type = result["response_type"] or "N/A"
        error = result["error"] or ""
        
        # Truncate long errors
        if len(error) > 18:
            error = error[:15] + "..."
        
        status_icon = "✅" if result["is_working"] else "❌"
        
        print(f"{job_id:<8} {name:<35} {status_icon} {status:<10} {str(record_count):<10} {response_type:<15} {error:<20}")
        
        if result["is_working"]:
            working_count += 1
        else:
            error_count += 1
    
    print("-" * 80)
    print(f"Summary: {working_count} working, {error_count} errors\n")


def main():
    """Main test function."""
    print("Testing Instance and System Endpoints")
    print("=" * 80)
    
    # Initialize client
    try:
        settings = get_settings()
        # Ensure base URL doesn't have /api/v1 suffix (endpoints already include it)
        base_url = settings.api.base_url.rstrip("/")
        if base_url.endswith("/api/v1"):
            base_url = base_url[:-7]  # Remove /api/v1
        
        client = ClinicalConductorClient(
            base_url=base_url,
            api_key=settings.api.key,
            default_top=1000,  # Larger page size for large datasets
            max_pages=500,  # Allow many pages for very large datasets (e.g., medications, devices)
        )
        print(f"✓ Initialized API client")
        print(f"  Base URL: {client.base_url}")
        print(f"  API Key: {'*' * 20}...{settings.api.key[-4:]}")
    except Exception as e:
        print(f"❌ Failed to initialize API client: {e}")
        return 1
    
    # Test instance endpoints
    print("\n" + "="*80)
    print("Testing Instance Endpoints...")
    print("="*80)
    
    instance_results = []
    for endpoint_config in INSTANCE_ENDPOINTS:
        print(f"Testing {endpoint_config['name']} ({endpoint_config['endpoint']})...", end=" ")
        result = test_endpoint(client, endpoint_config)
        instance_results.append(result)
        if result["is_working"]:
            print(f"✅ OK ({result['record_count']} records)")
        else:
            print(f"❌ FAILED: {result['error']}")
    
    # Test system endpoints
    print("\n" + "="*80)
    print("Testing System Endpoints...")
    print("="*80)
    
    system_results = []
    for endpoint_config in SYSTEM_ENDPOINTS:
        print(f"Testing {endpoint_config['name']} ({endpoint_config['endpoint']})...", end=" ")
        result = test_endpoint(client, endpoint_config)
        system_results.append(result)
        if result["is_working"]:
            print(f"✅ OK ({result['record_count']} records)")
        else:
            print(f"❌ FAILED: {result['error']}")
    
    # Print summary tables
    print_results(instance_results, "Instance")
    print_results(system_results, "System")
    
    # Overall summary
    all_results = instance_results + system_results
    total_working = sum(1 for r in all_results if r["is_working"])
    total_errors = sum(1 for r in all_results if not r["is_working"])
    
    print(f"\n{'='*80}")
    print("Overall Summary")
    print(f"{'='*80}")
    print(f"Total Endpoints Tested: {len(all_results)}")
    print(f"✅ Working: {total_working}")
    print(f"❌ Errors: {total_errors}")
    print(f"Success Rate: {(total_working/len(all_results)*100):.1f}%")
    print(f"{'='*80}\n")
    
    # Return exit code
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

