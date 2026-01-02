# Patient Silver Layer Setup - Step-by-Step Guide

**Purpose**: Complete guide to populate `dim_patients` and set up automatic scheduling after `dim_patients_staging` refresh completes.

**Last Updated**: January 2, 2026

---

## Overview

After `dim_patients_staging` is refreshed, you need to:
1. **Verify staging data is complete**
2. **Update the master transformation procedure** to include `load_dw_dim_patient()`
3. **Run the transformation manually** (first time)
4. **Set up automatic scheduling** for future runs

---

## Step 1: Verify Staging Data is Complete

```sql
-- Check staging record count
SELECT COUNT(*) as staging_records FROM dim_patients_staging;

-- Check for any NULL patient IDs
SELECT COUNT(*) as null_ids 
FROM dim_patients_staging 
WHERE data->>'id' IS NULL;

-- Sample a few records to verify data structure
SELECT 
    data->>'id' as patient_id,
    data->>'displayName' as display_name,
    data->>'status' as status,
    data->'primaryEmail'->>'email' as email
FROM dim_patients_staging 
LIMIT 5;
```

**Expected**: All records should have valid `id` fields, and you should see the expected total count.

---

## Step 2: Update Master Transformation Procedure

This adds `load_dw_dim_patient()` to the master procedure `load_all_new_dimensions()` so it runs automatically.

```bash
# Using DATABASE_URL from .env file
psql $DATABASE_URL -f sql/transformations/update_load_all_new_dimensions.sql

# Or explicitly:
psql -h localhost -U chrisprader -d trialsync_dev -f sql/transformations/update_load_all_new_dimensions.sql
```

**What this does**:
- Updates `load_all_new_dimensions()` to include `load_dw_dim_patient()`
- Ensures it runs in the correct order (after patient_engagement, before study)
- Adds error handling

**Verify the update**:
```sql
-- Check that the procedure includes load_dw_dim_patient
SELECT routine_definition 
FROM information_schema.routines 
WHERE routine_name = 'load_all_new_dimensions' 
  AND routine_schema = 'public';
```

You should see `CALL load_dw_dim_patient();` in the procedure definition.

---

## Step 3: Run Transformation Manually (First Time)

Since this is the first time populating `dim_patients`, run it manually to verify everything works:

```sql
-- Run the patient dimension transformation
CALL load_dw_dim_patient();
```

**What this does**:
1. Compares all records in `dim_patients_staging` to `dim_patients`
2. Since `dim_patients` is empty (first run), all staging records are new
3. Inserts all records into `dim_patients` with `is_current = TRUE`

**Verify the results**:
```sql
-- Check total records in silver layer
SELECT 
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE is_current = TRUE) as current_records,
    COUNT(*) FILTER (WHERE is_current = FALSE) as historical_records
FROM dim_patients;

-- Compare counts (should match)
SELECT 
    (SELECT COUNT(*) FROM dim_patients_staging) as staging_count,
    (SELECT COUNT(*) FROM dim_patients WHERE is_current = TRUE) as silver_current_count;

-- Sample records
SELECT 
    patient_id,
    display_name,
    status,
    primary_email,
    effective_start_date,
    is_current
FROM dim_patients 
WHERE is_current = TRUE
LIMIT 10;
```

**Expected**: 
- `total_records` = `staging_count`
- `current_records` = `staging_count` (all are current on first run)
- `historical_records` = 0 (no history yet)

---

## Step 4: Set Up Automatic Scheduling

**Important Distinction**: 
- The **ETL Scheduler** (`trialsync-etl scheduler`) schedules **ETL jobs** (API → staging tables)
- **Transformation procedures** (stored procedures like `load_all_new_dimensions()`) are **separate** and need their own scheduling

You have **three options** for scheduling transformation procedures:

### Option A: Create a Database Job/Scheduled Task (Recommended)

PostgreSQL doesn't have built-in job scheduling, but you can use one of these approaches:

#### Option A1: Use pg_cron Extension (if available)

```sql
-- Install pg_cron extension (requires superuser)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule load_all_new_dimensions() to run daily at 2 AM UTC
SELECT cron.schedule(
    'load-all-dimensions-daily',
    '0 2 * * *',  -- Daily at 2 AM UTC
    $$CALL load_all_new_dimensions();$$
);
```

#### Option A2: Use Python Script with APScheduler

Create a script that calls the stored procedure:

```python
# scripts/schedule_transformations.py
import psycopg2
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from src.config import get_settings

def run_transformations():
    settings = get_settings()
    conn = psycopg2.connect(settings.database.url)
    cursor = conn.cursor()
    cursor.execute("CALL load_all_new_dimensions();")
    conn.commit()
    cursor.close()
    conn.close()
    print("Transformation procedures executed successfully")

scheduler = BlockingScheduler()
scheduler.add_job(
    run_transformations,
    trigger=CronTrigger(hour=2, minute=0),  # Daily at 2 AM
    id='load_dimensions',
    name='Load All Dimensions Daily'
)
scheduler.start()
```

Run it:
```bash
python scripts/schedule_transformations.py
```

#### Option A3: Use System Cron (Linux/Mac)

Create a cron job that calls the procedure:

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * psql -h localhost -U chrisprader -d trialsync_dev -c "CALL load_all_new_dimensions();" >> /var/log/trialsync_transformations.log 2>&1
```

### Option B: Use ETL Scheduler (Future Enhancement)

**Note**: The ETL scheduler (`trialsync-etl scheduler`) currently only schedules ETL jobs from `dw_etl_jobs` table (API → staging). It does NOT execute stored procedures. 

To use the ETL scheduler for transformations, you would need to:
1. Create a special ETL job type that executes stored procedures
2. Add it to `dw_etl_jobs` with a schedule
3. Extend `JobExecutor` to handle stored procedure execution

This is a future enhancement and not currently implemented. For now, use Option A (pg_cron, Python script, or system cron).

---

## Step 5: Verify Automatic Execution

After setting up scheduling, verify it works:

### For pg_cron:
```sql
-- Check scheduled jobs
SELECT * FROM cron.job;

-- Check job run history
SELECT * FROM cron.job_run_details 
WHERE jobid = (SELECT jobid FROM cron.job WHERE jobname = 'load-all-dimensions-daily')
ORDER BY start_time DESC 
LIMIT 10;
```

### For Python Script:
- Check the script logs
- Verify `dim_patients` is updated daily

### For System Cron:
```bash
# Check cron logs
tail -f /var/log/trialsync_transformations.log

# Or check system logs
grep "load_all_new_dimensions" /var/log/syslog
```

---

## Step 6: Monitor Future Runs

After the first manual run, future runs will be incremental (only changed records):

```sql
-- Check transformation execution (if logged)
SELECT 
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE is_current = TRUE) as current_records,
    COUNT(*) FILTER (WHERE is_current = FALSE) as historical_records,
    MAX(etl_load_date) as last_load_date
FROM dim_patients;

-- Check for records in staging not yet in silver (should be 0 after transformation runs)
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

### Issue: Procedure Not Found

**Error**: `procedure "load_dw_dim_patient" does not exist`

**Solution**: 
```sql
-- Verify procedure exists
SELECT routine_name 
FROM information_schema.routines 
WHERE routine_name = 'load_dw_dim_patient';

-- If missing, create it:
\i sql/silver/create_dim_patients.sql
```

### Issue: No Records Inserted

**Possible Causes**:
- Staging table is empty
- Patient IDs are NULL in staging
- Procedure ran but all records already exist

**Solution**:
```sql
-- Check staging data
SELECT COUNT(*) FROM dim_patients_staging;

-- Check for NULL IDs
SELECT COUNT(*) FROM dim_patients_staging WHERE data->>'id' IS NULL;

-- Check if records already exist
SELECT COUNT(*) FROM dim_patients WHERE is_current = TRUE;
```

### Issue: Transformation Not Running Automatically

**Solution**:
1. Verify the scheduler/job is set up correctly
2. Check logs for errors
3. Test manual execution: `CALL load_all_new_dimensions();`
4. Verify cron/scheduler is running

---

## Summary Checklist

- [ ] Step 1: Verified staging data is complete
- [ ] Step 2: Updated `load_all_new_dimensions()` to include `load_dw_dim_patient()`
- [ ] Step 3: Ran `CALL load_dw_dim_patient();` manually and verified results
- [ ] Step 4: Set up automatic scheduling (chose one option)
- [ ] Step 5: Verified automatic execution works
- [ ] Step 6: Monitored future runs

---

**Document End**

