# Incremental Loading Guide

**Purpose**: Enable incremental loading for ETL jobs to only fetch records that have been updated since the last run, reducing API load and processing time.

**Last Updated**: January 1, 2026

---

## Overview

The ETL system supports **incremental loading** using timestamp fields from the Clinical Conductor API. Instead of pulling all records every time, the system can filter to only fetch records modified since the last successful run.

### How It Works

1. **First Run**: Full load (all records)
2. **Subsequent Runs**: Only records where `{timestamp_field} > {last_run_timestamp}`
3. **OData Filter**: `?$filter=modifiedDate gt 2025-12-01T20:30:52.000Z`

### Benefits

- ✅ **Reduced API Load**: Only fetch changed records
- ✅ **Faster Execution**: Process fewer records
- ✅ **Lower Costs**: Less network and compute usage
- ✅ **Real-time Updates**: Keep data fresh without full refreshes

---

## Timestamp Field Names

The Clinical Conductor API uses different timestamp field names across endpoints. Common fields:

| Field Name | Usage | Endpoints |
|------------|-------|-----------|
| `modifiedDate` | Most common | Studies, Patients, PatientVisits, Appointments, Staff, Elements |
| `lastUpdatedOn` | Alternative | Some endpoints |
| `modifiedOn` | Less common | Some system endpoints |
| `createdDate` | Creation only | All endpoints (for new records) |

**Note**: The actual field name varies by endpoint. Use the `check_timestamp_fields.py` script to verify.

---

## Enabling Incremental Loading

### Step 1: Verify Timestamp Field Name

Run the timestamp field checker script:

```bash
source .venv/bin/activate
python scripts/check_timestamp_fields.py
```

This will show which timestamp fields are available for each endpoint.

### Step 2: Enable for a Single Job

```sql
UPDATE dw_etl_jobs
SET incremental_load = TRUE,
    timestamp_field_name = 'modifiedDate'  -- or 'lastUpdatedOn' based on endpoint
WHERE id = 3;  -- Patients job
```

### Step 3: Verify the Configuration

```sql
SELECT id, name, incremental_load, timestamp_field_name
FROM dw_etl_jobs
WHERE id = 3;
```

### Step 4: Test Incremental Loading

```bash
# First run (full load)
trialsync-etl run --job-id 3

# Second run (incremental - should fetch fewer records)
trialsync-etl run --job-id 3
```

---

## Recommended Jobs for Incremental Loading

### High Priority (Patient-Related)

These jobs handle large datasets and benefit most from incremental loading:

| Job ID | Name | Endpoint | Recommended Field |
|--------|------|----------|-------------------|
| **3** | **Patients** | `/api/v1/patients/odata` | `modifiedDate` |
| **9** | **PatientVisits** | `/api/v1/patient-visits/odata` | `modifiedDate` |
| **25** | **Appointments** | `/api/v1/appointments/odata` | `modifiedDate` |
| **127** | **Subject Statuses** | `/api/v1/subject-statuses/odata` | `modifiedDate` |

### Medium Priority (Study-Related)

| Job ID | Name | Endpoint | Recommended Field |
|--------|------|----------|-------------------|
| **2** | **Studies** | `/api/v1/studies/odata` | `modifiedDate` |
| **10** | **Subjects** | `/api/v1/studies/{studyId}/subjects/odata` | `modifiedDate` |
| **8** | **Elements** | `/api/v1/elements/odata` | `modifiedDate` |

### Lower Priority (Reference Data)

System reference tables change infrequently but can still benefit:

| Job ID | Name | Endpoint | Recommended Field |
|--------|------|----------|-------------------|
| **1** | **Sites** | `/api/v1/sites` | `modifiedDate` |
| **26** | **Staff** | `/api/v1/staff/odata` | `modifiedDate` |
| **32** | **Providers** | `/api/v1/providers/odata` | `modifiedDate` |

---

## Bulk Enable Script

Enable incremental loading for all recommended jobs:

```sql
-- Patient-related jobs (high priority)
UPDATE dw_etl_jobs
SET incremental_load = TRUE,
    timestamp_field_name = 'modifiedDate',
    updated_at = NOW()
WHERE id IN (3, 9, 25, 127);

-- Study-related jobs
UPDATE dw_etl_jobs
SET incremental_load = TRUE,
    timestamp_field_name = 'modifiedDate',
    updated_at = NOW()
WHERE id IN (2, 10, 8);

-- Reference data jobs
UPDATE dw_etl_jobs
SET incremental_load = TRUE,
    timestamp_field_name = 'modifiedDate',
    updated_at = NOW()
WHERE id IN (1, 26, 32);
```

---

## Parameterized Jobs

For parameterized jobs (e.g., patient-dependent endpoints), incremental loading works per parameter:

**Example**: Job 147 (Patient Devices) depends on patients
- For each patient, only fetch devices modified since the last run for that patient
- Uses the same timestamp field but filters per patient context

**Enable for parameterized jobs**:

```sql
-- Patient-dependent jobs
UPDATE dw_etl_jobs
SET incremental_load = TRUE,
    timestamp_field_name = 'modifiedDate',
    updated_at = NOW()
WHERE id IN (147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157);

-- Study-dependent jobs
UPDATE dw_etl_jobs
SET incremental_load = TRUE,
    timestamp_field_name = 'modifiedDate',
    updated_at = NOW()
WHERE id IN (10, 11, 13, 14, 15, 16, 17, 20, 23, 27, 28, 29);
```

---

## Verification

### Check Which Jobs Have Incremental Loading Enabled

```sql
SELECT 
    id,
    name,
    incremental_load,
    timestamp_field_name,
    last_run_at,
    last_run_records
FROM dw_etl_jobs
WHERE incremental_load = TRUE
ORDER BY id;
```

### Monitor Incremental Load Performance

```sql
-- Compare record counts between runs
SELECT 
    job_id,
    run_status,
    records_loaded,
    started_at,
    completed_at
FROM dw_etl_runs
WHERE job_id = 3  -- Patients job
ORDER BY started_at DESC
LIMIT 5;
```

**Expected Pattern**:
- First run: Full load (e.g., 152,751 records)
- Second run: Incremental (e.g., 50 records - only changed since first run)
- Third run: Incremental (e.g., 12 records - only changed since second run)

---

## Troubleshooting

### Issue: No Records Returned After Enabling Incremental Loading

**Possible Causes**:
1. **Wrong timestamp field name**: The endpoint might use a different field
2. **Date format issue**: OData date format must be `YYYY-MM-DDTHH:mm:ss.fffZ`
3. **No successful previous run**: First run should be full load

**Solution**:
```sql
-- Temporarily disable to test
UPDATE dw_etl_jobs
SET incremental_load = FALSE
WHERE id = <job_id>;

-- Run once to establish baseline
-- Then re-enable incremental loading
```

### Issue: Still Fetching All Records

**Check**:
1. Verify `incremental_load = TRUE` in database
2. Check that there's a previous successful run
3. Verify `timestamp_field_name` matches actual API response field

**Debug**:
```python
from src.etl import JobExecutor

executor = JobExecutor()
config = executor.get_job_config(3)  # Patients job
print(f"Incremental: {config.incremental_load}")
print(f"Timestamp field: {config.timestamp_field_name}")

# Check last run timestamp
last_run = executor._get_last_successful_run_timestamp(3)
print(f"Last run: {last_run}")
```

---

## Implementation Details

### Code Location

- **Executor**: `src/etl/executor.py`
  - `_get_last_successful_run_timestamp()` - Gets last successful run time
  - `_fetch_and_load()` - Applies OData filter when `incremental_load=True`

### Database Schema

The `dw_etl_jobs` table includes:
- `incremental_load BOOLEAN` - Enable/disable flag
- `timestamp_field_name VARCHAR(100)` - Field name for filtering (default: 'lastUpdatedOn')

### OData Filter Format

The system builds filters like:
```
?$filter=modifiedDate gt 2025-12-01T20:30:52.000Z
```

Format: `YYYY-MM-DDTHH:mm:ss.fffZ` (ISO 8601 with milliseconds)

---

## Best Practices

1. **Start with High-Volume Jobs**: Enable incremental loading for jobs with the most records first (Patients, PatientVisits, Appointments)

2. **Verify Field Names**: Use `check_timestamp_fields.py` to confirm the actual timestamp field name for each endpoint

3. **Test Before Production**: Enable incremental loading in development/test first, verify it works correctly

4. **Monitor Record Counts**: Track record counts over time to ensure incremental loading is working

5. **Periodic Full Refresh**: Consider running a full refresh weekly/monthly to catch any edge cases

6. **Document Field Names**: Keep a record of which timestamp field each endpoint uses

---

## Related Documentation

- `docs/IMPLEMENTATION_SUMMARY.md` - Implementation details
- `docs/05_Job_Sequencing_and_Incremental_Loading.md` - Job sequencing with incremental loads
- `docs/JOB_DEPENDENCY_ANALYSIS.md` - Dependency analysis
- `scripts/check_timestamp_fields.py` - Script to verify timestamp fields

---

## Quick Reference

**Enable for Patients job**:
```sql
UPDATE dw_etl_jobs
SET incremental_load = TRUE,
    timestamp_field_name = 'modifiedDate'
WHERE id = 3;
```

**Check current status**:
```sql
SELECT id, name, incremental_load, timestamp_field_name
FROM dw_etl_jobs
WHERE id = 3;
```

**Test incremental loading**:
```bash
trialsync-etl run --job-id 3  # Run twice to see difference
```

