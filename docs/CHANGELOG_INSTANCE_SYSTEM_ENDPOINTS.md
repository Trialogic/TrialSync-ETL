# Instance and System Endpoints - Change Log

## January 1, 2026

### Endpoint Testing and Fixes

#### ✅ All Endpoints Verified Working (100% Success Rate)

**Test Results**: All 18 instance and system endpoints tested and confirmed working.

- **Instance Endpoints**: 2/2 working
- **System Endpoints**: 16/16 working
- **Total**: 18/18 working (100%)

See `docs/INSTANCE_SYSTEM_ENDPOINTS_TEST_RESULTS.md` for detailed test results.

#### 🔧 Job 132 Fix Applied

**Issue**: System Study Statuses endpoint was configured incorrectly.

- **Problem**: Endpoint path was `/api/v1/system/study-statuses/odata` (returned 404)
- **Root Cause**: According to OpenAPI spec, this endpoint returns a direct array, not OData format
- **Fix**: Updated endpoint to `/api/v1/system/study-statuses` (non-OData)
- **Status**: ✅ Fixed in database on January 1, 2026

**Files Created**:
- `scripts/test_instance_system_endpoints.py` - Test script for all endpoints
- `scripts/fix_job_132.py` - Automated fix script for Job 132
- `sql/fixes/fix_job_132_study_statuses.sql` - SQL fix script
- `docs/INSTANCE_SYSTEM_ENDPOINTS_REVIEW.md` - Comprehensive endpoint review
- `docs/INSTANCE_SYSTEM_ENDPOINTS_TEST_RESULTS.md` - Detailed test results

**Database Changes**:
```sql
UPDATE dw_etl_jobs 
SET source_endpoint = '/api/v1/system/study-statuses',
    requires_parameters = false,
    parameter_source_table = NULL,
    parameter_source_column = NULL,
    updated_at = NOW()
WHERE id = 132;
```

**Verification**:
- Endpoint tested and confirmed working (15 records returned)
- Configuration updated in database
- Test script validates all endpoints successfully

---

## Summary

All instance and system endpoints are now verified and working correctly. The only configuration issue (Job 132) has been resolved.

