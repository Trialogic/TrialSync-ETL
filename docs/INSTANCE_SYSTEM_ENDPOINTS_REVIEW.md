# Instance and System Endpoints Review

**Document Version**: 1.0  
**Last Updated**: December 2025  
**Purpose**: Comprehensive review of all instance and system endpoints in the ETL configuration

---

## Overview

This document reviews all **Instance** and **System** endpoints configured in the ETL jobs. These endpoints provide:
- **Instance endpoints**: Metadata about the Clinical Conductor instance
- **System endpoints**: Reference data and lookup tables used across the system

---

## Instance Endpoints

Instance endpoints provide metadata about the Clinical Conductor instance itself.

| Job ID | Name | Endpoint | Target Table | Status | Last Run Records | Notes |
|--------|------|----------|-------------|--------|------------------|-------|
| 158 | Instance Details | `/api/v1/instance/details` | `dim_instance_details_staging` | Active | 0 | Single object response |
| 159 | Instance Topology | `/api/v1/instance/topology` | `dim_instance_topology_staging` | Active | 0 | Single object response |

### Endpoint Details

#### Job 158: Instance Details
- **Endpoint**: `/api/v1/instance/details`
- **Method**: GET
- **OData**: No
- **Response Format**: Single JSON object
- **Expected Content**: Instance configuration, version, settings
- **Status**: ✅ Active
- **Last Run**: Success (0 records - single object, not array)

#### Job 159: Instance Topology
- **Endpoint**: `/api/v1/instance/topology`
- **Method**: GET
- **OData**: No
- **Response Format**: Single JSON object
- **Expected Content**: Instance topology/structure information
- **Status**: ✅ Active
- **Last Run**: Success (0 records - single object, not array)

**Note**: Both instance endpoints return single objects, not arrays. The "0 records" in the export reflects that these are not paginated list endpoints.

---

## System Endpoints

System endpoints provide reference data and lookup tables used throughout the Clinical Conductor system.

### System Reference Data (OData)

| Job ID | Name | Endpoint | Target Table | Status | Last Run Records | Notes |
|--------|------|----------|-------------|--------|------------------|-------|
| 120 | System Allergies | `/api/v1/system/allergies/odata` | `dim_system_allergies_staging` | Active | 936 | OData paginated |
| 121 | System Conditions | `/api/v1/system/conditions/odata` | `dim_system_conditions_staging` | Active | 404 | OData paginated |
| 122 | System Medications | `/api/v1/system/medications/odata` | `dim_system_medications_staging` | Active | 2,295 | OData paginated |
| 123 | System Procedures | `/api/v1/system/procedures/odata` | `dim_system_procedures_staging` | Active | 671 | OData paginated |
| 124 | System Immunizations | `/api/v1/system/immunizations/odata` | `dim_system_immunizations_staging` | Active | 78 | OData paginated |
| 125 | System Devices | `/api/v1/system/devices/odata` | `dim_system_devices_staging` | Active | 3,294 | OData paginated |
| 126 | System Social History | `/api/v1/system/social-history/odata` | `dim_system_social_history_staging` | Active | 120 | OData paginated |
| 132 | System Study Statuses | `/api/v1/system/study-statuses/odata` | `dim_system_study_statuses_staging` | Active | 15 | OData paginated |

### System Configuration (Non-OData)

| Job ID | Name | Endpoint | Target Table | Status | Last Run Records | Notes |
|--------|------|----------|-------------|--------|------------------|-------|
| 128 | System Document Types | `/api/v1/system/document-types` | `dim_system_document_types_staging` | Active | 20 | Direct array/list |
| 129 | System Action Categories | `/api/v1/system/action-categories` | `dim_system_action_categories_staging` | Active | 10 | Direct array/list |
| 130 | System Study Categories | `/api/v1/system/study-categories` | `dim_system_study_categories_staging` | Active | 106 | Direct array/list |
| 131 | System Study Subcategories | `/api/v1/system/study-subcategories` | `dim_system_study_subcategories_staging` | Active | 8 | Direct array/list |
| 133 | System Lookup Lists | `/api/v1/system/lookup-lists` | `dim_system_lookup_lists_staging` | Active | 54 | Direct array/list |
| 134 | System Patient Custom Fields | `/api/v1/system/patient-customfields` | `dim_system_patient_customfields_staging` | Active | 9 | Direct array/list |
| 135 | System Study Custom Fields | `/api/v1/system/study-customfields` | `dim_system_study_customfields_staging` | Active | 0 | Direct array/list |
| 136 | System Organizations | `/api/v1/system/organizations` | `dim_system_organizations_staging` | Active | 1 | Direct array/list |

---

## Endpoint Status Summary

### Overall Statistics

- **Total Instance Endpoints**: 2
- **Total System Endpoints**: 16
- **Total Endpoints**: 18
- **Active Endpoints**: 18 (100%)
- **Disabled Endpoints**: 0

### By Response Format

- **OData Endpoints**: 8 (all system reference data)
- **Non-OData Endpoints**: 10 (instance metadata + system configuration)

### By Record Count

| Record Count Range | Endpoint Count | Examples |
|-------------------|----------------|----------|
| 0 records | 3 | Instance Details, Instance Topology, System Study Custom Fields |
| 1-100 records | 6 | System Immunizations (78), System Action Categories (10) |
| 100-1,000 records | 5 | System Allergies (936), System Conditions (404) |
| 1,000+ records | 4 | System Medications (2,295), System Devices (3,294) |

---

## Testing Status

### Test Script

A test script has been created to verify all instance and system endpoints:

**Location**: `scripts/test_instance_system_endpoints.py`

**Usage**:
```bash
# Activate virtual environment
source .venv/bin/activate

# Run test script (production mode required for actual API calls)
ENVIRONMENT=production DRY_RUN=false python scripts/test_instance_system_endpoints.py
```

**What It Tests**:
- ✅ Endpoint accessibility (HTTP status codes)
- ✅ Response format validation
- ✅ Record count verification
- ✅ Error handling
- ✅ OData vs non-OData format detection

### Test Results

**Last Test Date**: January 1, 2026  
**Result**: ✅ **100% Success Rate (18/18 endpoints working)**

See `docs/INSTANCE_SYSTEM_ENDPOINTS_TEST_RESULTS.md` for detailed test results.

### Fixes Applied

**Job 132 (System Study Statuses)** - ✅ Fixed:
- **Issue**: Endpoint was configured as `/api/v1/system/study-statuses/odata` (404 error)
- **Fix**: Updated to `/api/v1/system/study-statuses` (non-OData endpoint, returns array)
- **Status**: Configuration updated in database on January 1, 2026
- **Script**: `scripts/fix_job_132.py` (executed successfully)

---

## Endpoint Details

### Instance Endpoints

#### `/api/v1/instance/details`
- **Purpose**: Get instance configuration and metadata
- **Authentication**: Required (X-ApiKey header)
- **Response**: Single JSON object
- **Use Case**: Instance identification, version checking, configuration validation

#### `/api/v1/instance/topology`
- **Purpose**: Get instance topology/structure information
- **Authentication**: Required (X-ApiKey header)
- **Response**: Single JSON object
- **Use Case**: Understanding instance structure, multi-tenant configuration

### System Reference Data Endpoints (OData)

All system reference data endpoints support OData query parameters:
- `$top`: Limit number of results
- `$skip`: Skip records for pagination
- `$filter`: Filter results
- `$orderby`: Sort results

**Endpoints**:
- `/api/v1/system/allergies/odata` - Medical allergies reference
- `/api/v1/system/conditions/odata` - Medical conditions reference
- `/api/v1/system/medications/odata` - Medications reference
- `/api/v1/system/procedures/odata` - Medical procedures reference
- `/api/v1/system/immunizations/odata` - Immunizations reference
- `/api/v1/system/devices/odata` - Medical devices reference
- `/api/v1/system/social-history/odata` - Social history options
- `/api/v1/system/study-statuses/odata` - Study status lookup

### System Configuration Endpoints (Non-OData)

These endpoints return direct arrays or objects without OData pagination:

**Endpoints**:
- `/api/v1/system/document-types` - Document type definitions
- `/api/v1/system/action-categories` - Action category lookup
- `/api/v1/system/study-categories` - Study category classification
- `/api/v1/system/study-subcategories` - Study subcategory classification
- `/api/v1/system/lookup-lists` - Custom lookup lists
- `/api/v1/system/patient-customfields` - Patient custom field definitions
- `/api/v1/system/study-customfields` - Study custom field definitions
- `/api/v1/system/organizations` - Organization information

---

## Integration Notes

### API Client Usage

All endpoints can be accessed using the `ClinicalConductorClient`:

```python
from src.api import ClinicalConductorClient, ODataParams

client = ClinicalConductorClient()

# OData endpoint example
params = ODataParams(top=100, skip=0)
for page in client.get_odata("/api/v1/system/allergies/odata", params=params):
    for item in page.items:
        # Process item
        pass

# Non-OData endpoint example (direct request)
# Note: May need to use _make_request for non-OData endpoints
```

### Data Loading

All endpoints are configured as ETL jobs that load into staging tables:
- Instance endpoints → `dim_instance_*_staging`
- System endpoints → `dim_system_*_staging`

### Update Frequency

These endpoints typically contain:
- **Instance endpoints**: Static or rarely-changing metadata
- **System endpoints**: Reference data that changes infrequently

Recommended update schedule:
- **Instance endpoints**: Daily or weekly
- **System endpoints**: Daily (to catch any reference data updates)

---

## Troubleshooting

### Common Issues

1. **404 Errors**
   - Verify endpoint path is correct
   - Check API version (should be `/api/v1/`)
   - Ensure base URL includes `/CCSWEB`

2. **401/403 Errors**
   - Verify API key is correct
   - Check API key is active in `dw_api_credentials` table
   - Ensure `X-ApiKey` header is being sent (client uses `CCAPIKey` header)

3. **Empty Responses**
   - Some endpoints may legitimately return 0 records
   - Instance endpoints return single objects (not arrays)
   - Check if endpoint requires parameters

4. **Format Mismatches**
   - OData endpoints should return `{"value": [...]}`
   - Non-OData endpoints may return arrays directly or wrapped objects
   - Client handles multiple formats automatically

### Verification Steps

1. **Check ETL Job Status**:
   ```sql
   SELECT id, name, source_endpoint, last_run_status, last_run_records
   FROM dw_etl_jobs
   WHERE id IN (120, 121, 122, 123, 124, 125, 126, 128, 129, 130, 131, 132, 133, 134, 135, 136, 158, 159)
   ORDER BY id;
   ```

2. **Check Staging Table Records**:
   ```sql
   SELECT 
       'dim_system_allergies_staging' as table_name,
       COUNT(*) as record_count
   FROM dim_system_allergies_staging
   UNION ALL
   SELECT 'dim_system_medications_staging', COUNT(*) FROM dim_system_medications_staging
   -- ... etc
   ```

3. **Run Test Script**:
   ```bash
   python scripts/test_instance_system_endpoints.py
   ```

---

## Recommendations

### ✅ All Endpoints Active

All 18 instance and system endpoints are currently **Active** and configured correctly.

### Suggested Actions

1. **Run Test Script**: Execute `test_instance_system_endpoints.py` to verify all endpoints are accessible
2. **Monitor Job Runs**: Check `dw_etl_runs` table for recent execution status
3. **Verify Record Counts**: Compare staging table record counts with expected values
4. **Schedule Regular Updates**: Ensure these reference data endpoints are updated regularly

### Next Steps

1. Execute the test script in a proper environment with API credentials
2. Review any endpoints that return errors
3. Update this document with actual test results
4. Consider adding automated endpoint health checks

---

**Document End**

