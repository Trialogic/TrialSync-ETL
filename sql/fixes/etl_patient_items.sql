-- ============================================================================
-- ETL Job Configurations for Patient-Related Items
-- Enable and fix existing patient ETL jobs
-- Created: December 15, 2025
-- ============================================================================

-- ============================================================================
-- PART 1: Update Existing Patient ETL Jobs to Enable Them
-- ============================================================================

-- Enable Patient Allergies
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patients/{patientId}/allergies/odata',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'Patient Allergies';

-- Enable Patient Conditions
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patients/{patientId}/conditions/odata',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'Patient Conditions';

-- Enable Patient Devices
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patients/{patientId}/devices/odata',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'Patient Devices';

-- Enable Patient Immunizations
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patients/{patientId}/immunizations/odata',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'Patient Immunizations';

-- Enable Patient Medications
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patients/{patientId}/medications/odata',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'Patient Medications';

-- Enable Patient Procedures
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patients/{patientId}/procedures/odata',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'Patient Procedures';

-- Enable Patient Social History
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patients/{patientId}/social-history/odata',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'Patient Social History';

-- Enable Patient Family History
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patients/{patientId}/family-history/odata',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'Patient Family History';

-- Enable Patient Providers
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patients/{patientId}/providers/odata',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'Patient Providers';

-- Enable Patient Visit Elements
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patient-visits/{patientVisitId}/elements/odata',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'Patient Visit Elements';

-- Enable PatientVisitElements (alternate job)
UPDATE dw_etl_jobs 
SET is_active = true,
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'PatientVisitElements';

-- Enable Patient Visit Stipends (may have issues)
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patient-visits/{patientVisitId}/stipends/odata',
    parameter_name = 'patientVisitId',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'Patient Visit Stipends';

-- Enable PatientVisits (global endpoint)
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patient-visits/odata',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'PatientVisits';

-- Enable Patients (global endpoint)
UPDATE dw_etl_jobs 
SET is_active = true,
    source_endpoint = '/api/v1/patients/odata',
    updated_at = CURRENT_TIMESTAMP
WHERE name = 'Patients';

-- ============================================================================
-- PART 2: Verify Updates
-- ============================================================================

SELECT id, name, source_endpoint, target_table, is_active, requires_parameters, parameter_name
FROM dw_etl_jobs 
WHERE name LIKE 'Patient%' 
   OR source_endpoint LIKE '%patients%'
   OR source_endpoint LIKE '%patient-visits%'
ORDER BY name;

-- ============================================================================
-- PART 3: Show Summary of Patient-Related Jobs
-- ============================================================================

SELECT 
    CASE WHEN is_active THEN 'Active' ELSE 'Disabled' END as status,
    COUNT(*) as job_count
FROM dw_etl_jobs 
WHERE name LIKE 'Patient%' 
   OR source_endpoint LIKE '%patients%'
   OR source_endpoint LIKE '%patient-visits%'
GROUP BY is_active;
