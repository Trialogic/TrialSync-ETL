# Transformation Procedure Execution Guide

**Purpose**: Document when and how transformation procedures (Bronze → Silver) are executed.

**Last Updated**: January 2, 2026

---

## Overview

Transformation procedures move data from the Bronze (staging) layer to the Silver (normalized) layer. They implement Type 2 Slowly Changing Dimensions (SCD Type 2) to track historical changes.

---

## Master Transformation Procedures

### `load_all_new_dimensions()`

**Purpose**: Orchestrates all dimension table loads from staging to silver layer.

**Schedule**: Daily at 2 AM (after ETL jobs complete)

**Execution Order**:
1. `load_dw_dim_site()` - Clinical sites
2. `load_dw_dim_monitor()` - Study monitors
3. `load_dw_dim_medical_code()` - Medical codes
4. `load_dw_dim_patient_engagement()` - Patient engagement data
5. **`load_dw_dim_patient()`** - **Patient demographics (Type 2 SCD)** ← Added via update script
6. `load_dw_dim_study()` - Studies
7. `load_dw_dim_subject()` - Subjects
8. `load_dw_dim_visit()` - Patient visits
9. `load_dw_dim_visit_element()` - Visit elements
10. `load_dw_dim_study_arm()` - Study arms

**Dependencies**: 
- Must run after all ETL staging jobs complete
- Should run before fact table loads

**Duration**: ~15 minutes

### `load_all_new_facts()`

**Purpose**: Orchestrates all fact table loads from staging to silver layer.

**Schedule**: Daily at 3 AM (after dimensions are loaded)

**Dependencies**: All dimensions must be loaded first

**Duration**: ~30 minutes

---

## Patient Dimension: `load_dw_dim_patient()`

### Current Status

**Before Update**: Manual execution only
- Must be called manually: `CALL load_dw_dim_patient();`
- Not included in `load_all_new_dimensions()`

**After Update**: Automatic execution
- Included in `load_all_new_dimensions()`
- Runs daily at 2 AM automatically
- Executes after `load_dw_dim_patient_engagement()` and before `load_dw_dim_study()`

### When It Runs

**Automated (Recommended)**:
- Daily at 2 AM via `load_all_new_dimensions()`
- After Patients ETL job (Job ID 3) completes successfully
- Before fact table loads that reference patient data

**Manual Execution**:
```sql
-- Run immediately after patient ETL job
CALL load_dw_dim_patient();

-- Or run the full dimension load
CALL load_all_new_dimensions();
```

### What It Does

1. **Expires Changed Records**: Compares staging data to current silver records field-by-field. If any field changed, expires the old record (sets `is_current = FALSE`, `effective_end_date = NOW()`).

2. **Inserts New/Changed Records**: Creates new records for:
   - New patients (never seen before)
   - Changed patients (old record was expired in step 1)

3. **Type 2 SCD**: Maintains historical versions with `effective_start_date` and `effective_end_date`.

### Example Workflow

```
Day 1, 1:00 AM: Patients ETL Job runs
  → Loads 146,415 patients to dim_patients_staging

Day 1, 2:00 AM: load_all_new_dimensions() runs
  → Calls load_dw_dim_patient()
  → Compares staging to silver (first run, all are new)
  → Inserts 146,415 new records into dim_patients
  → All records have is_current = TRUE

Day 2, 1:00 AM: Patients ETL Job runs (incremental)
  → Loads 50 changed patients to dim_patients_staging
  → Updates existing records in staging (ON CONFLICT)

Day 2, 2:00 AM: load_all_new_dimensions() runs
  → Calls load_dw_dim_patient()
  → Compares staging to silver
  → Detects 50 patients with changed fields
  → Expires 50 old records (is_current = FALSE)
  → Inserts 50 new records (is_current = TRUE)
  → Result: 146,415 total records (146,365 historical + 50 current)
```

---

## Enabling Automatic Execution

To add `load_dw_dim_patient()` to the master procedure:

```bash
# Using DATABASE_URL from .env file
psql $DATABASE_URL -f sql/transformations/update_load_all_new_dimensions.sql

# Or explicitly:
psql -h localhost -U chrisprader -d trialsync_dev -f sql/transformations/update_load_all_new_dimensions.sql
```

This will:
- Update `load_all_new_dimensions()` to include `load_dw_dim_patient()`
- Add error handling for the patient dimension load
- Ensure it runs in the correct order (after patient_engagement, before study)

---

## Manual Execution (Before Update)

If you haven't run the update script yet, you must call it manually:

```sql
-- After Patients ETL job completes
CALL load_dw_dim_patient();

-- Verify results
SELECT 
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE is_current = TRUE) as current_records,
    COUNT(*) FILTER (WHERE is_current = FALSE) as historical_records
FROM dim_patients;
```

---

## Monitoring Transformation Execution

### Check Last Execution Time

```sql
-- Check when procedures were last executed (if logged)
SELECT 
    routine_name,
    last_altered
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name LIKE 'load_dw_dim%'
ORDER BY last_altered DESC;
```

### Verify Data Flow

```sql
-- Check staging records
SELECT COUNT(*) FROM dim_patients_staging;

-- Check silver records
SELECT 
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE is_current = TRUE) as current,
    COUNT(*) FILTER (WHERE is_current = FALSE) as historical
FROM dim_patients;

-- Check for records in staging not yet in silver
SELECT COUNT(*)
FROM dim_patients_staging stg
WHERE NOT EXISTS (
    SELECT 1 FROM dim_patients dp
    WHERE dp.patient_id = (stg.data->>'id')::INTEGER
      AND dp.is_current = TRUE
);
```

---

## Troubleshooting

### Procedure Not Running Automatically

**Issue**: `load_dw_dim_patient()` not executing automatically.

**Solution**: 
1. Verify the update script was run: `sql/transformations/update_load_all_new_dimensions.sql`
2. Check if `load_all_new_dimensions()` includes the call
3. Verify the scheduler is running `load_all_new_dimensions()` at 2 AM

### No Changes Detected

**Issue**: Patient data changed in staging but silver layer shows no changes.

**Possible Causes**:
- Transformation procedure hasn't run yet
- Field comparison logic doesn't include the changed field
- Staging data wasn't actually updated (check `updated_at`)

**Solution**:
1. Manually run: `CALL load_dw_dim_patient();`
2. Check which fields are compared in the procedure
3. Verify staging data has `updated_at` > last transformation run

---

**Document End**

