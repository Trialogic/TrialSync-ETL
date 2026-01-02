-- ============================================================================
-- Migration: Create Changed Patients View and Functions
-- ============================================================================
-- Purpose: Provides infrastructure for tracking recently changed patients
--          to optimize patient-parameterized ETL jobs.
--
-- Usage: Jobs can query v_recently_changed_patients instead of all patients
--        to only process patients that have been modified since the last run.
-- ============================================================================

BEGIN;

-- ============================================================================
-- Step 1: Create View for Recently Changed Patients
-- ============================================================================
-- This view returns patient IDs that have been modified since the last
-- successful run of the Patients ETL job (job_id = 3).
--
-- A patient is considered "changed" if:
-- 1. It's a current record (is_current = TRUE)
-- 2. Its effective_start_date is after the last successful Patients job run

CREATE OR REPLACE VIEW v_recently_changed_patients AS
SELECT
    dp.patient_id,
    dp.patient_uid,
    dp.display_name,
    dp.effective_start_date AS changed_at
FROM dim_patients dp
WHERE dp.is_current = TRUE
  AND dp.effective_start_date > COALESCE(
      (
          SELECT MAX(completed_at)
          FROM dw_etl_runs
          WHERE job_id = 3  -- Patients job
            AND run_status = 'success'
      ),
      '1970-01-01'::TIMESTAMP  -- Default to epoch if no runs exist
  );

COMMENT ON VIEW v_recently_changed_patients IS
    'Returns patient IDs that have been modified since the last successful Patients ETL run.
     Use this view as the parameter source for "Changed Patients" job variants.';

-- ============================================================================
-- Step 2: Create Function for Parameterized Changed Patients Query
-- ============================================================================
-- This function allows specifying a custom lookback window instead of using
-- the last Patients job run time.

CREATE OR REPLACE FUNCTION get_changed_patient_ids(
    since_timestamp TIMESTAMP DEFAULT NULL,
    max_patients INTEGER DEFAULT NULL
)
RETURNS TABLE (patient_id INTEGER, patient_uid UUID, changed_at TIMESTAMP)
LANGUAGE plpgsql
AS $$
DECLARE
    v_since TIMESTAMP;
BEGIN
    -- Default to last Patients job run if not specified
    IF since_timestamp IS NULL THEN
        SELECT MAX(completed_at) INTO v_since
        FROM dw_etl_runs
        WHERE job_id = 3  -- Patients job
          AND run_status = 'success';

        -- Default to 24 hours ago if no runs exist
        IF v_since IS NULL THEN
            v_since := NOW() - INTERVAL '24 hours';
        END IF;
    ELSE
        v_since := since_timestamp;
    END IF;

    RETURN QUERY
    SELECT
        dp.patient_id,
        dp.patient_uid,
        dp.effective_start_date AS changed_at
    FROM dim_patients dp
    WHERE dp.is_current = TRUE
      AND dp.effective_start_date > v_since
    ORDER BY dp.effective_start_date DESC
    LIMIT max_patients;
END;
$$;

COMMENT ON FUNCTION get_changed_patient_ids IS
    'Returns patient IDs changed since a given timestamp.
     If since_timestamp is NULL, uses the last successful Patients job run time.
     Use max_patients to limit results for testing.';

-- ============================================================================
-- Step 3: Create View for All Current Patients (for Full Load jobs)
-- ============================================================================
-- This view returns all current patient IDs for full load operations.

CREATE OR REPLACE VIEW v_all_current_patients AS
SELECT
    dp.patient_id,
    dp.patient_uid,
    dp.display_name,
    dp.status
FROM dim_patients dp
WHERE dp.is_current = TRUE
ORDER BY dp.patient_id;

COMMENT ON VIEW v_all_current_patients IS
    'Returns all current patient IDs. Use this view as the parameter source for "Full Load" job variants.';

-- ============================================================================
-- Step 4: Create Stats View for Monitoring
-- ============================================================================

CREATE OR REPLACE VIEW v_patient_change_stats AS
SELECT
    (SELECT COUNT(*) FROM dim_patients WHERE is_current = TRUE) AS total_current_patients,
    (SELECT COUNT(*) FROM v_recently_changed_patients) AS recently_changed_patients,
    (SELECT MAX(completed_at) FROM dw_etl_runs WHERE job_id = 3 AND run_status = 'success') AS last_patients_sync,
    (SELECT MAX(effective_start_date) FROM dim_patients WHERE is_current = TRUE) AS latest_patient_change;

COMMENT ON VIEW v_patient_change_stats IS
    'Statistics about patient changes for monitoring ETL efficiency.';

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Show stats
SELECT * FROM v_patient_change_stats;

-- Show sample of recently changed patients
SELECT * FROM v_recently_changed_patients LIMIT 10;

COMMIT;

-- ============================================================================
-- Usage Examples
-- ============================================================================
--
-- 1. Get all changed patients since last sync:
--    SELECT patient_id FROM v_recently_changed_patients;
--
-- 2. Get patients changed in last 4 hours:
--    SELECT * FROM get_changed_patient_ids(NOW() - INTERVAL '4 hours');
--
-- 3. Get top 100 most recently changed patients:
--    SELECT * FROM get_changed_patient_ids(NULL, 100);
--
-- 4. Monitor change volume:
--    SELECT * FROM v_patient_change_stats;
-- ============================================================================
