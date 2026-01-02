-- ============================================================================
-- Migration: Create Dual Job Pattern for Patient-Parameterized ETL Jobs
-- ============================================================================
-- Purpose: Creates paired jobs for each patient sub-endpoint:
--          - Full Load: Processes all current patients (weekly/monthly)
--          - Changed Patients: Processes only recently changed patients (hourly/daily)
--
-- This pattern reduces API calls from 150K+ to only changed patients (~100-1000).
--
-- Dependencies:
--   - Requires create_changed_patients_view.sql to be run first
--   - Requires dim_patients table with Type 2 SCD tracking
-- ============================================================================

BEGIN;

-- ============================================================================
-- Step 1: Add load_mode column to dw_etl_jobs if not exists
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'dw_etl_jobs'
        AND column_name = 'load_mode'
    ) THEN
        ALTER TABLE dw_etl_jobs
        ADD COLUMN load_mode VARCHAR(20) DEFAULT 'full';
    END IF;
END $$;

-- ============================================================================
-- Step 2: Add job_group column for pairing related jobs
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'dw_etl_jobs'
        AND column_name = 'job_group'
    ) THEN
        ALTER TABLE dw_etl_jobs
        ADD COLUMN job_group VARCHAR(100);
    END IF;
END $$;

-- ============================================================================
-- Step 3: Update existing patient jobs to be "Full Load" variants
-- ============================================================================

UPDATE dw_etl_jobs
SET
    load_mode = 'full',
    job_group = CASE
        WHEN name = 'Patient Devices' THEN 'patient_devices'
        WHEN name = 'Patient Allergies' THEN 'patient_allergies'
        WHEN name = 'Patient Providers' THEN 'patient_providers'
        WHEN name = 'Patient Conditions' THEN 'patient_conditions'
        WHEN name = 'Patient Procedures' THEN 'patient_procedures'
        WHEN name = 'Patient Medications' THEN 'patient_medications'
        WHEN name = 'Patient Immunizations' THEN 'patient_immunizations'
        WHEN name = 'Patient Family History' THEN 'patient_family_history'
        WHEN name = 'Patient Social History' THEN 'patient_social_history'
        WHEN name = 'Patient Campaign Touches' THEN 'patient_campaign_touches'
        WHEN name = 'Patient Referral Touches' THEN 'patient_referral_touches'
    END,
    name = name || ' - Full',
    is_active = FALSE,
    updated_at = NOW()
WHERE id IN (147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157)
  AND name NOT LIKE '% - Full'
  AND name NOT LIKE '% - Changed';

-- ============================================================================
-- Step 4: Create "Changed Patients" Job Variants
-- ============================================================================

-- Patient Allergies - Changed
INSERT INTO dw_etl_jobs (
    name, source_endpoint, target_table, is_active,
    requires_parameters, parameter_source_table, parameter_source_column,
    parameter_name, incremental_load, load_mode, job_group,
    depends_on, created_at, updated_at
)
SELECT
    'Patient Allergies - Changed',
    '/api/v1/patients/{patientId}/allergies',
    'dim_patient_allergies_staging',
    TRUE, TRUE,
    'v_recently_changed_patients', 'patient_id', 'patientId',
    FALSE, 'changed_parents', 'patient_allergies',
    ARRAY[3], NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM dw_etl_jobs WHERE name = 'Patient Allergies - Changed');

-- Patient Conditions - Changed
INSERT INTO dw_etl_jobs (
    name, source_endpoint, target_table, is_active,
    requires_parameters, parameter_source_table, parameter_source_column,
    parameter_name, incremental_load, load_mode, job_group,
    depends_on, created_at, updated_at
)
SELECT
    'Patient Conditions - Changed',
    '/api/v1/patients/{patientId}/conditions',
    'dim_patient_conditions_staging',
    TRUE, TRUE,
    'v_recently_changed_patients', 'patient_id', 'patientId',
    FALSE, 'changed_parents', 'patient_conditions',
    ARRAY[3], NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM dw_etl_jobs WHERE name = 'Patient Conditions - Changed');

-- Patient Devices - Changed
INSERT INTO dw_etl_jobs (
    name, source_endpoint, target_table, is_active,
    requires_parameters, parameter_source_table, parameter_source_column,
    parameter_name, incremental_load, load_mode, job_group,
    depends_on, created_at, updated_at
)
SELECT
    'Patient Devices - Changed',
    '/api/v1/patients/{patientId}/devices',
    'dim_patient_devices_staging',
    TRUE, TRUE,
    'v_recently_changed_patients', 'patient_id', 'patientId',
    FALSE, 'changed_parents', 'patient_devices',
    ARRAY[3], NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM dw_etl_jobs WHERE name = 'Patient Devices - Changed');

-- Patient Medications - Changed
INSERT INTO dw_etl_jobs (
    name, source_endpoint, target_table, is_active,
    requires_parameters, parameter_source_table, parameter_source_column,
    parameter_name, incremental_load, load_mode, job_group,
    depends_on, created_at, updated_at
)
SELECT
    'Patient Medications - Changed',
    '/api/v1/patients/{patientId}/medications',
    'dim_patient_medications_staging',
    TRUE, TRUE,
    'v_recently_changed_patients', 'patient_id', 'patientId',
    FALSE, 'changed_parents', 'patient_medications',
    ARRAY[3], NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM dw_etl_jobs WHERE name = 'Patient Medications - Changed');

-- Patient Procedures - Changed
INSERT INTO dw_etl_jobs (
    name, source_endpoint, target_table, is_active,
    requires_parameters, parameter_source_table, parameter_source_column,
    parameter_name, incremental_load, load_mode, job_group,
    depends_on, created_at, updated_at
)
SELECT
    'Patient Procedures - Changed',
    '/api/v1/patients/{patientId}/procedures',
    'dim_patient_procedures_staging',
    TRUE, TRUE,
    'v_recently_changed_patients', 'patient_id', 'patientId',
    FALSE, 'changed_parents', 'patient_procedures',
    ARRAY[3], NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM dw_etl_jobs WHERE name = 'Patient Procedures - Changed');

-- Patient Immunizations - Changed
INSERT INTO dw_etl_jobs (
    name, source_endpoint, target_table, is_active,
    requires_parameters, parameter_source_table, parameter_source_column,
    parameter_name, incremental_load, load_mode, job_group,
    depends_on, created_at, updated_at
)
SELECT
    'Patient Immunizations - Changed',
    '/api/v1/patients/{patientId}/immunizations',
    'dim_patient_immunizations_staging',
    TRUE, TRUE,
    'v_recently_changed_patients', 'patient_id', 'patientId',
    FALSE, 'changed_parents', 'patient_immunizations',
    ARRAY[3], NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM dw_etl_jobs WHERE name = 'Patient Immunizations - Changed');

-- Patient Providers - Changed
INSERT INTO dw_etl_jobs (
    name, source_endpoint, target_table, is_active,
    requires_parameters, parameter_source_table, parameter_source_column,
    parameter_name, incremental_load, load_mode, job_group,
    depends_on, created_at, updated_at
)
SELECT
    'Patient Providers - Changed',
    '/api/v1/patients/{patientId}/providers',
    'dim_patient_providers_staging',
    TRUE, TRUE,
    'v_recently_changed_patients', 'patient_id', 'patientId',
    FALSE, 'changed_parents', 'patient_providers',
    ARRAY[3], NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM dw_etl_jobs WHERE name = 'Patient Providers - Changed');

-- Patient Family History - Changed
INSERT INTO dw_etl_jobs (
    name, source_endpoint, target_table, is_active,
    requires_parameters, parameter_source_table, parameter_source_column,
    parameter_name, incremental_load, load_mode, job_group,
    depends_on, created_at, updated_at
)
SELECT
    'Patient Family History - Changed',
    '/api/v1/patients/{patientId}/family-history',
    'dim_patient_family_history_staging',
    TRUE, TRUE,
    'v_recently_changed_patients', 'patient_id', 'patientId',
    FALSE, 'changed_parents', 'patient_family_history',
    ARRAY[3], NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM dw_etl_jobs WHERE name = 'Patient Family History - Changed');

-- Patient Social History - Changed
INSERT INTO dw_etl_jobs (
    name, source_endpoint, target_table, is_active,
    requires_parameters, parameter_source_table, parameter_source_column,
    parameter_name, incremental_load, load_mode, job_group,
    depends_on, created_at, updated_at
)
SELECT
    'Patient Social History - Changed',
    '/api/v1/patients/{patientId}/social-history',
    'dim_patient_social_history_staging',
    TRUE, TRUE,
    'v_recently_changed_patients', 'patient_id', 'patientId',
    FALSE, 'changed_parents', 'patient_social_history',
    ARRAY[3], NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM dw_etl_jobs WHERE name = 'Patient Social History - Changed');

-- Patient Campaign Touches - Changed
INSERT INTO dw_etl_jobs (
    name, source_endpoint, target_table, is_active,
    requires_parameters, parameter_source_table, parameter_source_column,
    parameter_name, incremental_load, load_mode, job_group,
    depends_on, created_at, updated_at
)
SELECT
    'Patient Campaign Touches - Changed',
    '/api/v1/patients/{patientId}/touches/campaign',
    'dim_patient_campaign_touches_staging',
    TRUE, TRUE,
    'v_recently_changed_patients', 'patient_id', 'patientId',
    FALSE, 'changed_parents', 'patient_campaign_touches',
    ARRAY[3], NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM dw_etl_jobs WHERE name = 'Patient Campaign Touches - Changed');

-- Patient Referral Touches - Changed
INSERT INTO dw_etl_jobs (
    name, source_endpoint, target_table, is_active,
    requires_parameters, parameter_source_table, parameter_source_column,
    parameter_name, incremental_load, load_mode, job_group,
    depends_on, created_at, updated_at
)
SELECT
    'Patient Referral Touches - Changed',
    '/api/v1/patients/{patientId}/touches/referral',
    'dim_patient_referral_touches_staging',
    TRUE, TRUE,
    'v_recently_changed_patients', 'patient_id', 'patientId',
    FALSE, 'changed_parents', 'patient_referral_touches',
    ARRAY[3], NOW(), NOW()
WHERE NOT EXISTS (SELECT 1 FROM dw_etl_jobs WHERE name = 'Patient Referral Touches - Changed');

-- ============================================================================
-- Step 5: Update Full Load jobs to use v_all_current_patients
-- ============================================================================

UPDATE dw_etl_jobs
SET
    parameter_source_table = 'v_all_current_patients',
    parameter_source_column = 'patient_id',
    updated_at = NOW()
WHERE name LIKE 'Patient % - Full'
  AND parameter_source_table = 'dim_patients_staging';

COMMIT;

-- ============================================================================
-- Verification: Show all patient-related jobs
-- ============================================================================

SELECT
    id,
    name,
    job_group,
    load_mode,
    is_active,
    parameter_source_table
FROM dw_etl_jobs
WHERE job_group LIKE 'patient_%'
   OR name LIKE 'Patient %'
ORDER BY job_group NULLS LAST, load_mode;
