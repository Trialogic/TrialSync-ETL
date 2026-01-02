# Staging Table Duplicate Detection and Change Tracking

**Purpose**: Document how the ETL system handles duplicate records, detects changes, and how downstream processes identify new/changed records.

**Last Updated**: January 2, 2026

---

## Overview

The ETL system uses a two-layer approach for duplicate detection and change tracking:

1. **Bronze (Staging) Layer**: Uses database unique constraints to prevent duplicates and always overwrites on conflict
2. **Silver Layer**: Compares staging data to existing silver records field-by-field to detect actual changes and implement Type 2 SCD

---

## Bronze Layer: Staging Table Duplicate Detection

### Unique Constraint

The `dim_patients_staging` table uses a **composite unique constraint** to identify duplicate records:

```sql
CREATE UNIQUE INDEX idx_dim_patients_staging_composite_unique
ON dim_patients_staging (source_instance_id, (data->>'id'));
```

**Key**: `(source_instance_id, patient_id_from_json)`

This ensures:
- Each patient ID is unique **per Clinical Conductor instance**
- Multiple instances can have patients with the same patient ID (multi-tenant support)
- The same patient from the same instance cannot be inserted twice

### Upsert Logic

When the ETL runs and encounters a record that already exists in staging:

```sql
INSERT INTO dim_patients_staging (
    source_id, 
    source_instance_id, 
    data, 
    etl_job_id, 
    etl_run_id, 
    loaded_at, 
    created_at, 
    updated_at
)
VALUES (...)
ON CONFLICT (source_instance_id, (data->>'id')) DO UPDATE SET
    data = EXCLUDED.data,                    -- Always overwrites JSONB data
    etl_job_id = EXCLUDED.etl_job_id,     -- Updates lineage
    etl_run_id = EXCLUDED.etl_run_id,     -- Updates lineage
    loaded_at = EXCLUDED.loaded_at,       -- Updates load timestamp
    updated_at = EXCLUDED.loaded_at,      -- Updates modification timestamp
    source_id = EXCLUDED.source_id        -- Updates source_id
```

### Important Points

1. **No Change Detection in Staging**: The staging layer does **NOT** compare old vs new data to detect if anything actually changed. It always overwrites on conflict.

2. **Always Updates**: If a record with the same `(source_instance_id, patient_id)` exists, it is **always updated**, even if the JSONB data is identical.

3. **Timestamp Tracking**: 
   - `created_at`: Set on first insert, never changed
   - `updated_at`: Set to `loaded_at` on every upsert (insert or update)
   - `loaded_at`: Timestamp of the current ETL run

4. **Lineage Tracking**: 
   - `etl_job_id`: Always updated to the current job
   - `etl_run_id`: Always updated to the current run

### Example

**First ETL Run** (patient ID 123, instance 1):
```json
{
  "source_instance_id": 1,
  "data": {"id": 123, "firstName": "John", "lastName": "Doe"},
  "created_at": "2026-01-01 10:00:00",
  "updated_at": "2026-01-01 10:00:00",
  "loaded_at": "2026-01-01 10:00:00",
  "etl_run_id": 100
}
```

**Second ETL Run** (same patient, no changes):
```json
{
  "source_instance_id": 1,
  "data": {"id": 123, "firstName": "John", "lastName": "Doe"},  -- Same data
  "created_at": "2026-01-01 10:00:00",  -- Preserved
  "updated_at": "2026-01-01 14:00:00",  -- Updated (even though data didn't change)
  "loaded_at": "2026-01-01 14:00:00",  -- Updated
  "etl_run_id": 200  -- Updated
}
```

**Third ETL Run** (same patient, name changed):
```json
{
  "source_instance_id": 1,
  "data": {"id": 123, "firstName": "John", "lastName": "Smith"},  -- Changed
  "created_at": "2026-01-01 10:00:00",  -- Preserved
  "updated_at": "2026-01-01 18:00:00",  -- Updated
  "loaded_at": "2026-01-01 18:00:00",  -- Updated
  "etl_run_id": 300  -- Updated
}
```

---

## Silver Layer: Change Detection and Type 2 SCD

The Silver layer (`dim_patients`) implements **Type 2 Slowly Changing Dimension (SCD Type 2)** pattern, which tracks historical changes.

### How It Identifies New/Changed Records

The transformation procedure `load_dw_dim_patient()` compares staging data to existing silver records **field-by-field** to detect actual changes.

#### Step 1: Expire Changed Records

```sql
UPDATE dim_patients dp
SET
    effective_end_date = CURRENT_TIMESTAMP - INTERVAL '1 second',
    is_current = FALSE,
    updated_at = NOW()
FROM dim_patients_staging stg
WHERE dp.patient_id = (stg.data->>'id')::INTEGER
  AND dp.is_current = TRUE
  AND (
      -- Field-by-field comparison to detect changes
      COALESCE(dp.status, '') != COALESCE(stg.data->>'status', '') OR
      COALESCE(dp.display_name, '') != COALESCE(stg.data->>'displayName', '') OR
      COALESCE(dp.first_name, '') != COALESCE(stg.data->>'firstName', '') OR
      COALESCE(dp.last_name, '') != COALESCE(stg.data->>'lastName', '') OR
      COALESCE(dp.primary_email, '') != COALESCE(stg.data->'primaryEmail'->>'email', '') OR
      COALESCE(dp.phone1_number, '') != COALESCE(stg.data->'phone1'->>'number', '') OR
      COALESCE(dp.primary_site_id::TEXT, '') != COALESCE(stg.data->'primarySite'->>'id', '')
      -- ... more fields ...
  );
```

**What This Does**:
- Finds all current (`is_current = TRUE`) patient records in silver layer
- Compares them field-by-field to staging data
- If **any** field differs, marks the old record as expired (`is_current = FALSE`, sets `effective_end_date`)
- This creates a historical record of the old state

#### Step 2: Insert New/Changed Records

```sql
INSERT INTO dim_patients (...)
SELECT 
    (stg.data->>'id')::INTEGER,
    stg.data->>'firstName',
    stg.data->>'lastName',
    -- ... all fields from staging ...
    NOW() as effective_start_date,
    '9999-12-31 23:59:59'::TIMESTAMP as effective_end_date,
    TRUE as is_current
FROM dim_patients_staging stg
WHERE NOT EXISTS (
    -- Only insert if no current record with same data exists
    SELECT 1 FROM dim_patients dp
    WHERE dp.patient_id = (stg.data->>'id')::INTEGER
      AND dp.is_current = TRUE
      AND -- All fields match (no changes detected)
);
```

**What This Does**:
- Inserts new records from staging that are either:
  - Completely new patients (never seen before)
  - Changed patients (old record was expired in Step 1)
- Sets `is_current = TRUE` and `effective_start_date = NOW()`
- Sets `effective_end_date = '9999-12-31'` (infinity) for current records

### Example: Change Detection Flow

**Initial State** (Silver layer):
```
patient_id: 123
first_name: "John"
last_name: "Doe"
is_current: TRUE
effective_start_date: 2026-01-01 10:00:00
effective_end_date: 9999-12-31 23:59:59
```

**After ETL Run** (staging has `lastName: "Smith"`):

**Step 1 - Expire Old Record**:
```
patient_id: 123
first_name: "John"
last_name: "Doe"
is_current: FALSE  ← Changed
effective_end_date: 2026-01-01 18:00:00  ← Set to now
```

**Step 2 - Insert New Record**:
```
patient_id: 123
first_name: "John"
last_name: "Smith"  ← New value
is_current: TRUE
effective_start_date: 2026-01-01 18:00:00  ← New record
effective_end_date: 9999-12-31 23:59:59
```

**Result**: Two records for patient 123:
- Historical: `last_name = "Doe"` (2026-01-01 10:00:00 to 2026-01-01 18:00:00)
- Current: `last_name = "Smith"` (2026-01-01 18:00:00 onwards)

---

## How Downstream Processes Identify New/Changed Records

### Option 1: Compare `etl_run_id`

The most common approach is to identify records loaded in a specific ETL run:

```sql
-- Get all records loaded in the latest run
SELECT *
FROM dim_patients_staging
WHERE etl_run_id = 3432  -- Latest run ID
ORDER BY loaded_at;
```

**Limitation**: This includes **all** records processed in that run, even if they didn't change.

### Option 2: Compare `updated_at` to Last Run Time

```sql
-- Get records updated since last successful run
SELECT *
FROM dim_patients_staging
WHERE updated_at > (
    SELECT MAX(completed_at)
    FROM dw_etl_runs
    WHERE job_id = 3
      AND run_status = 'success'
      AND id < 3432  -- Current run
);
```

**Limitation**: Since staging always updates `updated_at` on conflict, this will include all records processed, not just changed ones.

### Option 3: Compare Staging to Silver (Recommended)

The Silver layer transformation procedure (`load_dw_dim_patient()`) is the **only** place that actually detects changes by comparing field values.

To identify new/changed records for downstream processing:

```sql
-- New records (never seen in silver)
SELECT stg.*
FROM dim_patients_staging stg
WHERE NOT EXISTS (
    SELECT 1 FROM dim_patients dp
    WHERE dp.patient_id = (stg.data->>'id')::INTEGER
);

-- Changed records (current silver record differs from staging)
SELECT stg.*
FROM dim_patients_staging stg
JOIN dim_patients dp ON dp.patient_id = (stg.data->>'id')::INTEGER
WHERE dp.is_current = TRUE
  AND (
      COALESCE(dp.first_name, '') != COALESCE(stg.data->>'firstName', '') OR
      COALESCE(dp.last_name, '') != COALESCE(stg.data->>'lastName', '') OR
      -- ... compare all relevant fields ...
  );
```

### Option 4: Use Silver Layer `effective_start_date`

After running the transformation procedure, query the silver layer:

```sql
-- Records that became current in the last run
SELECT *
FROM dim_patients
WHERE is_current = TRUE
  AND effective_start_date >= (
      SELECT MAX(completed_at)
      FROM dw_etl_runs
      WHERE job_id = 3
        AND run_status = 'success'
  );
```

This identifies:
- New patients (first time seen)
- Changed patients (new version created)

---

## Summary

### Staging Layer (Bronze)

- **Duplicate Detection**: Composite unique constraint `(source_instance_id, data->>'id')`
- **Change Detection**: **None** - always overwrites on conflict
- **Behavior**: Always updates `updated_at`, `etl_run_id`, and `data` even if data is identical
- **Use Case**: Raw data storage, always reflects latest API state

### Silver Layer

- **Duplicate Detection**: Business key `patient_id` with `is_current` flag
- **Change Detection**: **Field-by-field comparison** between staging and current silver records
- **Behavior**: 
  - Expires old records when changes detected
  - Creates new records with `is_current = TRUE`
  - Maintains historical versions (Type 2 SCD)
- **Use Case**: Normalized, queryable data with historical tracking

### Key Takeaway

**The staging layer does NOT detect if data changed** - it always overwrites. **Only the Silver layer transformation procedure detects actual changes** by comparing field values and implements Type 2 SCD to track history.

---

---

## When Does `load_dw_dim_patient()` Run?

### Current Status (Before Update)

**Manual Execution Only**: `load_dw_dim_patient()` currently runs **manually** and is **not automatically scheduled**.

You must call it manually after the Patients ETL job completes:
```sql
CALL load_dw_dim_patient();
```

### After Update (Recommended)

Once you run `sql/transformations/update_load_all_new_dimensions.sql`, the procedure will be included in the master transformation procedure and will run automatically:

**Schedule**: Daily at 2 AM (via `load_all_new_dimensions()`)

**Execution Order**:
1. `load_dw_dim_site()` - Sites dimension
2. `load_dw_dim_monitor()` - Monitors dimension
3. `load_dw_dim_medical_code()` - Medical codes dimension
4. `load_dw_dim_patient_engagement()` - Patient engagement dimension
5. **`load_dw_dim_patient()`** - **Patients dimension** ← Added
6. `load_dw_dim_study()` - Studies dimension
7. `load_dw_dim_subject()` - Subjects dimension
8. `load_dw_dim_visit()` - Visits dimension
9. `load_dw_dim_visit_element()` - Visit elements dimension
10. `load_dw_dim_study_arm()` - Study arms dimension

**Dependencies**:
- Must run **after** the Patients ETL job (Job ID 3) completes successfully
- Should run **before** fact table loads that reference `dim_patients`

### Workflow

**Current Manual Workflow**:
```
1. Patients ETL Job (Job ID 3) runs → loads data to dim_patients_staging
2. Manual step: CALL load_dw_dim_patient(); → transforms to dim_patients
3. Query dim_patients or v_patients_current for normalized data
```

**Recommended Automated Workflow** (after update):
```
1. Patients ETL Job (Job ID 3) runs → loads data to dim_patients_staging
2. Daily at 2 AM: load_all_new_dimensions() runs automatically
   → includes load_dw_dim_patient() → transforms to dim_patients
3. Query dim_patients or v_patients_current for normalized data
```

### To Enable Automatic Execution

Run the update script:
```bash
# Using DATABASE_URL from .env file
psql $DATABASE_URL -f sql/transformations/update_load_all_new_dimensions.sql

# Or explicitly:
psql -h localhost -U chrisprader -d trialsync_dev -f sql/transformations/update_load_all_new_dimensions.sql
```

This will add `load_dw_dim_patient()` to the master procedure so it runs automatically daily at 2 AM.

---

**Document End**

