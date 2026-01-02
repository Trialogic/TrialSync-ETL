# Failing Jobs Analysis Report

Generated: 2026-01-01

## Summary

- **Total jobs analyzed**: 80
- **Jobs with 3+ failures**: 3
- **Total failures (last 7 days)**: 88
- **Total successes (last 7 days)**: 36

## Critical Issues

### Job 4 - Users (100% Failure Rate)
- **Status**: 3 failures, 0 successes
- **Endpoint**: `/api/v1/users/odata`
- **Error**: Resource not found (404)
- **Recommendation**: **DISABLE** - This endpoint does not exist in the Clinical Conductor API
- **Last Failure**: 2026-01-01 09:31:38

### Job 5 - Roles (100% Failure Rate)
- **Status**: 2 failures, 0 successes
- **Error**: Resource not found (404)
- **Recommendation**: **CHECK ENDPOINT** - Verify if this endpoint exists in the API
- **Last Failure**: 2026-01-01 09:31:07

### Job 9 - PatientVisits (100% Failure Rate)
- **Status**: 2 failures, 0 successes
- **Errors**: 
  - Type comparison error: `'>=' not supported between instances of 'int' and 'function'`
  - Stuck job (cleaned up)
- **Recommendation**: **INVESTIGATE** - Code issue with type comparison, likely in incremental loading logic
- **Last Failure**: 2026-01-01 08:21:37

## High Failure Rate Jobs

### Job 1 - Sites (75% Failure Rate)
- **Status**: 21 failures, 7 successes
- **Endpoint**: `/api/v1/sites`
- **Recent Issues**:
  - DRY_RUN mode errors (expected in test environment)
  - API response parsing: `'list' object has no attribute 'get'`
- **Status**: **WORKING** - Last success: 2026-01-01 09:31:15
- **Recommendation**: Monitor - Most recent failures appear to be resolved

### Job 3 - Patients (50% Failure Rate)
- **Status**: 3 failures, 3 successes
- **Endpoint**: `/api/v1/patients/odata`
- **Recent Issues**:
  - Type comparison error: `'>=' not supported between instances of 'int' and 'function'`
  - Broken pipe errors (network issues)
- **Status**: **WORKING** - Last success: 2026-01-01 06:42:24
- **Recommendation**: Monitor - Has recent successes, but type comparison error needs investigation

## Other Failing Jobs

### Job 6 - Departments (100% Failure Rate)
- **Status**: 1 failure, 0 successes
- **Error**: Resource not found (404)
- **Recommendation**: **CHECK ENDPOINT** - Verify if this endpoint exists

## Recommendations

1. **Immediate Actions**:
   - Disable Job 4 (Users) - endpoint doesn't exist
   - Investigate type comparison error in Jobs 3 and 9 (likely in incremental loading code)
   - Verify endpoints for Jobs 5 and 6

2. **Code Fixes Needed**:
   - Fix type comparison error: `'>=' not supported between instances of 'int' and 'function'`
   - This appears in both Patients and PatientVisits jobs
   - Likely related to timestamp field comparison in incremental loading

3. **Monitoring**:
   - Job 1 (Sites) is working but has high failure rate historically
   - Continue monitoring Jobs 3 and 9 for the type comparison issue

## Tools Available

- `scripts/analyze_failing_jobs.py` - Analyze failing jobs
- `scripts/check_stuck_jobs.py` - Check for stuck jobs
- `scripts/cleanup_stuck_jobs.py` - Clean up stuck jobs

