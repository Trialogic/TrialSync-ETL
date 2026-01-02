-- ============================================================================
-- Enable Incremental Loading for ETL Jobs
-- ============================================================================
-- This script enables incremental loading for jobs that support timestamp-based
-- filtering. Only records modified since the last successful run will be fetched.
--
-- Usage: Run this script to enable incremental loading for recommended jobs.
--        Adjust timestamp_field_name if needed based on actual API responses.
-- ============================================================================

BEGIN;

-- ============================================================================
-- Step 1: Ensure incremental_load and timestamp_field_name columns exist
-- ============================================================================

-- Add incremental_load column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'dw_etl_jobs' 
        AND column_name = 'incremental_load'
    ) THEN
        ALTER TABLE dw_etl_jobs 
        ADD COLUMN incremental_load BOOLEAN DEFAULT FALSE;
        
        COMMENT ON COLUMN dw_etl_jobs.incremental_load IS 
            'Enable incremental loading - only fetch records modified since last run';
    END IF;
END $$;

-- Add timestamp_field_name column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'dw_etl_jobs' 
        AND column_name = 'timestamp_field_name'
    ) THEN
        ALTER TABLE dw_etl_jobs 
        ADD COLUMN timestamp_field_name VARCHAR(100) DEFAULT 'lastUpdatedOn';
        
        COMMENT ON COLUMN dw_etl_jobs.timestamp_field_name IS 
            'Name of timestamp field in API response for filtering (e.g., modifiedDate, lastUpdatedOn)';
    END IF;
END $$;

-- ============================================================================
-- Step 2: Enable incremental loading for high-priority patient-related jobs
-- ============================================================================

UPDATE dw_etl_jobs
SET 
    incremental_load = TRUE,
    timestamp_field_name = 'modifiedDate',  -- Most common field name
    updated_at = NOW()
WHERE id IN (
    3,   -- Patients (152,751 records - HIGH PRIORITY)
    9,   -- PatientVisits
    25,  -- Appointments (40,893 records)
    127  -- Subject Statuses (119,749 records)
)
AND is_active = TRUE;

-- ============================================================================
-- Step 3: Enable for study-related jobs
-- ============================================================================

UPDATE dw_etl_jobs
SET 
    incremental_load = TRUE,
    timestamp_field_name = 'modifiedDate',
    updated_at = NOW()
WHERE id IN (
    2,   -- Studies (1,050 records)
    8,   -- Elements (15,836 records)
    10   -- Subjects (17,238 records)
)
AND is_active = TRUE;

-- ============================================================================
-- Step 4: Enable for reference data jobs
-- ============================================================================

UPDATE dw_etl_jobs
SET 
    incremental_load = TRUE,
    timestamp_field_name = 'modifiedDate',
    updated_at = NOW()
WHERE id IN (
    1,   -- Sites (40 records)
    26,  -- Staff (884 records)
    32   -- Providers (149 records)
)
AND is_active = TRUE;

-- ============================================================================
-- Step 5: Enable for patient-dependent parameterized jobs
-- ============================================================================
-- These jobs iterate through patients, so incremental loading filters per patient

UPDATE dw_etl_jobs
SET 
    incremental_load = TRUE,
    timestamp_field_name = 'modifiedDate',
    updated_at = NOW()
WHERE id IN (
    147, -- Patient Devices
    148, -- Patient Allergies
    149, -- Patient Providers
    150, -- Patient Conditions
    151, -- Patient Procedures
    152, -- Patient Medications
    153, -- Patient Immunizations
    154, -- Patient Family History
    155, -- Patient Social History
    156, -- Patient Campaign Touches
    157  -- Patient Referral Touches
)
AND is_active = TRUE
AND requires_parameters = TRUE;

-- ============================================================================
-- Step 6: Enable for study-dependent parameterized jobs
-- ============================================================================

UPDATE dw_etl_jobs
SET 
    incremental_load = TRUE,
    timestamp_field_name = 'modifiedDate',
    updated_at = NOW()
WHERE id IN (
    11,  -- Visits
    13,  -- StudyDocuments
    14,  -- Screenings
    15,  -- Enrollments
    16, -- Randomizations (note: may need different field)
    17,  -- Withdrawals
    20,  -- ConcomitantMedications
    23,  -- Queries
    27,  -- StudyActions
    28,  -- StudyMilestones
    29   -- StudyNotes
)
AND is_active = TRUE
AND requires_parameters = TRUE;

-- ============================================================================
-- Verification: Show which jobs now have incremental loading enabled
-- ============================================================================

SELECT 
    id,
    name,
    incremental_load,
    timestamp_field_name,
    is_active,
    last_run_records
FROM dw_etl_jobs
WHERE incremental_load = TRUE
ORDER BY id;

-- ============================================================================
-- Summary
-- ============================================================================

SELECT 
    COUNT(*) as total_jobs_with_incremental,
    COUNT(CASE WHEN is_active THEN 1 END) as active_jobs_with_incremental
FROM dw_etl_jobs
WHERE incremental_load = TRUE;

COMMIT;

-- ============================================================================
-- Next Steps
-- ============================================================================
-- 1. Run: python scripts/check_timestamp_fields.py
--    This will verify the actual timestamp field names in API responses
--
-- 2. If field names differ, update timestamp_field_name:
--    UPDATE dw_etl_jobs 
--    SET timestamp_field_name = 'actualFieldName' 
--    WHERE id = <job_id>;
--
-- 3. Test incremental loading:
--    trialsync-etl run --job-id 3  # Run twice to see difference
--
-- 4. Monitor record counts in dw_etl_runs to verify incremental loading works
-- ============================================================================

