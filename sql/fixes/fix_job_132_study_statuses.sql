-- ============================================================================
-- Fix Job 132: System Study Statuses Endpoint Path
-- ============================================================================
-- Issue: Endpoint was configured as '/api/v1/system/study-statuses/odata'
--        but the correct endpoint is '/api/v1/system/study-statuses' (non-OData)
-- 
-- Root Cause: According to OpenAPI spec, this endpoint returns a direct array,
--             not OData format, so it should not have the '/odata' suffix.
--
-- Test Results: Endpoint confirmed working with correct path (15 records)
-- ============================================================================

-- Update Job 132 endpoint path and ensure it's not parameterized
UPDATE dw_etl_jobs 
SET 
    source_endpoint = '/api/v1/system/study-statuses',
    requires_parameters = false,
    parameter_source_table = NULL,
    parameter_source_column = NULL,
    updated_at = NOW()
WHERE id = 132 
  AND name = 'System Study Statuses';

-- Verify the update
SELECT 
    id,
    name,
    source_endpoint,
    target_table,
    is_active,
    requires_parameters,
    parameter_source_table,
    parameter_source_column,
    last_run_status,
    last_run_records,
    updated_at
FROM dw_etl_jobs
WHERE id = 132;

-- Expected result:
-- id  | name                  | source_endpoint                    | target_table                        | is_active | requires_parameters | parameter_source_table | parameter_source_column | last_run_status | last_run_records | updated_at
-- ----|-----------------------|-----------------------------------|-------------------------------------|-----------|---------------------|----------------------|------------------------|-----------------|------------------|------------
-- 132 | System Study Statuses | /api/v1/system/study-statuses     | dim_system_study_statuses_staging   | t         | f                   | NULL                 | NULL                    | Never run       | 15               | 2026-01-01 ...

COMMENT ON TABLE dw_etl_jobs IS 'Job 132 endpoint path fixed: Changed from /odata to direct array endpoint';

