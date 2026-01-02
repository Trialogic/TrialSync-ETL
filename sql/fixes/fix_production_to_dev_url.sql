-- ============================================================================
-- Fix Production API URL to Dev URL
-- ============================================================================
-- This script updates the API credential to point to dev instead of production
-- 
-- IMPORTANT: This prevents ETL jobs from connecting to production
-- ============================================================================

BEGIN;

-- Update credential ID 1 to point to dev environment
UPDATE dw_api_credentials
SET 
    base_url = 'https://usimportccs09-ccs.advarracloud.com/CCSWEB',
    updated_at = NOW()
WHERE id = 1
  AND base_url LIKE '%tektonresearch.clinicalconductor.com%';

-- Verify the update
SELECT 
    id,
    base_url,
    is_active,
    updated_at
FROM dw_api_credentials
WHERE id = 1;

COMMIT;

-- ============================================================================
-- Verification Query
-- ============================================================================
-- Run this to verify all jobs are now pointing to dev:
-- 
-- SELECT 
--     j.id,
--     j.name,
--     c.base_url
-- FROM dw_etl_jobs j
-- LEFT JOIN dw_api_credentials c ON j.source_instance_id = c.id
-- WHERE j.is_active = TRUE
-- ORDER BY j.id
-- LIMIT 10;
-- ============================================================================

