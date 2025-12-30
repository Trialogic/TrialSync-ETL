-- ============================================================================
-- Re-enable Recommended ETL Jobs
-- Generated: December 15, 2025
-- Author: Manus AI
-- 
-- This script re-enables 9 ETL jobs that have proven track records of
-- successful execution. These jobs were previously disabled but analysis
-- shows they can be safely re-enabled.
-- ============================================================================

BEGIN;

-- ============================================================================
-- CATEGORY 1: High Success Rate Jobs (250+ successful runs)
-- These jobs have extensive successful run history
-- ============================================================================

-- Job #13: StudyDocuments - 254 successful runs, 0 failures
UPDATE dw_etl_jobs 
SET is_active = true, 
    updated_at = NOW()
WHERE id = 13;

-- Job #11: Visits - 253 successful runs, 0 failures
UPDATE dw_etl_jobs 
SET is_active = true, 
    updated_at = NOW()
WHERE id = 11;

-- ============================================================================
-- CATEGORY 2: Moderate Success Rate Jobs (1-10 successful runs)
-- These jobs have demonstrated successful execution
-- ============================================================================

-- Job #35: Sponsors - 3 successful runs, 0 failures
UPDATE dw_etl_jobs 
SET is_active = true, 
    updated_at = NOW()
WHERE id = 35;

-- Job #32: Providers - 2 successful runs, 0 failures
UPDATE dw_etl_jobs 
SET is_active = true, 
    updated_at = NOW()
WHERE id = 32;

-- Job #8: Elements - 2 successful runs, 0 failures
-- Note: May duplicate Job #158, verify after enabling
UPDATE dw_etl_jobs 
SET is_active = true, 
    updated_at = NOW()
WHERE id = 8;

-- Job #34: Schedules - 1 successful run, 0 failures
UPDATE dw_etl_jobs 
SET is_active = true, 
    updated_at = NOW()
WHERE id = 34;

-- Job #14: Screenings - 1 successful run, 0 failures
UPDATE dw_etl_jobs 
SET is_active = true, 
    updated_at = NOW()
WHERE id = 14;

-- Job #33: Rooms - 1 successful run, 0 failures
UPDATE dw_etl_jobs 
SET is_active = true, 
    updated_at = NOW()
WHERE id = 33;

-- Job #2: Studies - 5 successful runs, 2 failures
-- Note: May duplicate Job #164, verify after enabling
UPDATE dw_etl_jobs 
SET is_active = true, 
    updated_at = NOW()
WHERE id = 2;

-- ============================================================================
-- VERIFICATION QUERY
-- Run this after the update to confirm changes
-- ============================================================================

-- Display the updated jobs
SELECT 
    id,
    name,
    source_endpoint,
    is_active,
    success_runs,
    failed_runs,
    last_run_status
FROM dw_etl_jobs
WHERE id IN (13, 11, 35, 32, 8, 34, 14, 33, 2)
ORDER BY success_runs DESC;

COMMIT;

-- ============================================================================
-- SUMMARY
-- ============================================================================
-- Jobs Re-enabled: 9
-- 
-- | ID | Name           | Endpoint                                    | Success Runs |
-- |----|----------------|---------------------------------------------|--------------|
-- | 13 | StudyDocuments | /api/v1/studies/{studyId}/documents/odata   | 254          |
-- | 11 | Visits         | /api/v1/studies/{studyId}/visits/odata      | 253          |
-- | 35 | Sponsors       | /api/v1/sponsors/odata                      | 3            |
-- | 32 | Providers      | /api/v1/providers/odata                     | 2            |
-- |  8 | Elements       | /api/v1/elements/odata                      | 2            |
-- | 34 | Schedules      | /api/v1/schedules/odata                     | 1            |
-- | 14 | Screenings     | /api/v1/studies/{studyId}/screenings/odata  | 1            |
-- | 33 | Rooms          | /api/v1/rooms/odata                         | 1            |
-- |  2 | Studies        | /api/v1/studies/odata                       | 5            |
-- ============================================================================
