# Patients Staging: Source ID Update to Instance ID

**Date**: January 2, 2026  
**Purpose**: Document the change from using patient ID to instance ID as `source_id` in `dim_patients_staging`

---

## Overview

The `source_id` column in `dim_patients_staging` has been updated to use the **instance ID** (from `source_instance_id` in the ETL job configuration) instead of the patient ID from the API response. This change enables proper multi-tenant support where multiple Clinical Conductor instances can have patients with the same patient ID.

---

## Changes Made

### 1. DataLoader Updates (`src/db/loader.py`)

- Added `instance_id` parameter to `load_to_staging()` method
- Updated `_prepare_records()` to use `instance_id` as `source_id` when provided
- Updated deduplication logic to use composite key `(source_id, patient_id)` instead of just `source_id`
- Updated `_load_batch()` to include `source_instance_id` in INSERT statements
- Updated ON CONFLICT clause to use composite unique constraint: `(source_instance_id, data->>'id')`

### 2. JobExecutor Updates (`src/etl/executor.py`)

- Updated `_fetch_and_load()` to accept and pass `instance_id` parameter
- Updated calls to `load_to_staging()` to pass `job_config.source_instance_id` as `instance_id`
- Both parameterized and non-parameterized job paths now pass instance_id

### 3. Database Schema Updates

**Table Structure:**
- `source_id` (VARCHAR): Now stores instance_id as string (e.g., "1" for dev instance)
- `source_instance_id` (INTEGER): Stores instance_id as integer (for composite constraint)
- `data->>'id'`: Patient ID from API (unique per instance)

**Unique Constraint:**
- **Old**: `UNIQUE (source_id)` - This would fail with multiple patients from same instance
- **New**: `UNIQUE (source_instance_id, data->>'id')` - Composite constraint ensures uniqueness per instance

**Index:**
```sql
CREATE UNIQUE INDEX idx_dim_patients_staging_instance_patient 
ON dim_patients_staging(source_instance_id, (data->>'id'));
```

### 4. Missing Columns Added

The following columns were added to `dim_patients_staging` to support the DataLoader:
- `etl_job_id` (INTEGER)
- `etl_run_id` (INTEGER)
- `created_at` (TIMESTAMP)
- `updated_at` (TIMESTAMP)

---

## Benefits

1. **Multi-Tenant Support**: Multiple Clinical Conductor instances can have patients with the same patient ID, and they will be tracked separately
2. **Instance Tracking**: Easy to identify which instance each patient record came from
3. **Data Integrity**: Composite unique constraint prevents duplicate patients within the same instance
4. **Backward Compatible**: Existing records can be updated to use instance_id as source_id

---

## Migration Notes

### Existing Data

If you have existing data in `dim_patients_staging`:

```sql
-- Update existing records to use instance_id as source_id
UPDATE dim_patients_staging
SET source_id = source_instance_id::TEXT
WHERE source_id IS NULL OR source_id != source_instance_id::TEXT;
```

### New Loads

All new ETL runs will automatically use `instance_id` as `source_id`. The JobExecutor passes `source_instance_id` from the job configuration to the DataLoader.

---

## Example Data

**Before (source_id = patient_id):**
```
source_id: "123"
source_instance_id: 1
data->>'id': "123"
```

**After (source_id = instance_id):**
```
source_id: "1"  (instance_id from job config)
source_instance_id: 1
data->>'id': "123"  (patient_id from API)
```

---

## Testing

A test script was created to verify the changes:
- `scripts/test_load_1000_patients.py`: Loads 1000 patients and verifies data completeness
- All 1000 records loaded successfully with `source_id = instance_id`
- Composite unique constraint working correctly

---

## Related Files

- `src/db/loader.py`: DataLoader implementation
- `src/etl/executor.py`: JobExecutor implementation
- `scripts/test_load_1000_patients.py`: Test script
- `sql/fixes/add_source_id_to_patients_staging.sql`: SQL migration script

---

**Document End**

