-- ============================================================================
-- ETL Job Configurations for Not-Implemented API Categories
-- Clinical Conductor API to TrialSync Data Warehouse
-- Created: December 15, 2025
-- ============================================================================

-- ============================================================================
-- PART 1: Create Staging Tables for New Categories
-- ============================================================================

-- 1. Action Unit Completions
CREATE TABLE IF NOT EXISTS dim_action_unit_completions_staging (
    id SERIAL PRIMARY KEY,
    source_instance_id INTEGER NOT NULL DEFAULT 1,
    data JSONB NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_action_unit_completions_staging_instance ON dim_action_unit_completions_staging(source_instance_id);

-- 2. Invoices
CREATE TABLE IF NOT EXISTS dim_invoices_staging (
    id SERIAL PRIMARY KEY,
    source_instance_id INTEGER NOT NULL DEFAULT 1,
    data JSONB NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_invoices_staging_instance ON dim_invoices_staging(source_instance_id);

-- 3. Prospects
CREATE TABLE IF NOT EXISTS dim_prospects_staging (
    id SERIAL PRIMARY KEY,
    source_instance_id INTEGER NOT NULL DEFAULT 1,
    data JSONB NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_prospects_staging_instance ON dim_prospects_staging(source_instance_id);

-- 4. Remittances
CREATE TABLE IF NOT EXISTS dim_remittances_staging (
    id SERIAL PRIMARY KEY,
    source_instance_id INTEGER NOT NULL DEFAULT 1,
    data JSONB NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_remittances_staging_instance ON dim_remittances_staging(source_instance_id);

-- 5. Remittance Notes
CREATE TABLE IF NOT EXISTS dim_remittance_notes_staging (
    id SERIAL PRIMARY KEY,
    source_instance_id INTEGER NOT NULL DEFAULT 1,
    data JSONB NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_remittance_notes_staging_instance ON dim_remittance_notes_staging(source_instance_id);

-- 6. Site Payments
CREATE TABLE IF NOT EXISTS dim_site_payments_staging (
    id SERIAL PRIMARY KEY,
    source_instance_id INTEGER NOT NULL DEFAULT 1,
    data JSONB NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_site_payments_staging_instance ON dim_site_payments_staging(source_instance_id);

-- 7. Study Types
CREATE TABLE IF NOT EXISTS dim_study_types_staging (
    id SERIAL PRIMARY KEY,
    source_instance_id INTEGER NOT NULL DEFAULT 1,
    data JSONB NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_study_types_staging_instance ON dim_study_types_staging(source_instance_id);

-- 8. Study Visit Arms
CREATE TABLE IF NOT EXISTS dim_study_visit_arms_staging (
    id SERIAL PRIMARY KEY,
    source_instance_id INTEGER NOT NULL DEFAULT 1,
    data JSONB NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_study_visit_arms_staging_instance ON dim_study_visit_arms_staging(source_instance_id);

-- 9. Visit Element Relationships
CREATE TABLE IF NOT EXISTS dim_visit_element_relationships_staging (
    id SERIAL PRIMARY KEY,
    source_instance_id INTEGER NOT NULL DEFAULT 1,
    data JSONB NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_visit_element_relationships_staging_instance ON dim_visit_element_relationships_staging(source_instance_id);

-- 10. Patient Payments (was in disabled list)
CREATE TABLE IF NOT EXISTS dim_patient_payments_staging (
    id SERIAL PRIMARY KEY,
    source_instance_id INTEGER NOT NULL DEFAULT 1,
    data JSONB NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_patient_payments_staging_instance ON dim_patient_payments_staging(source_instance_id);

-- ============================================================================
-- PART 2: Insert ETL Job Configurations
-- ============================================================================

-- Get the next available ID
DO $$
DECLARE
    next_id INTEGER;
BEGIN
    SELECT COALESCE(MAX(id), 0) + 1 INTO next_id FROM dw_etl_jobs;
    
    -- 1. Action Unit Completions (Global endpoint)
    INSERT INTO dw_etl_jobs (
        id, name, source_endpoint, target_table, schedule_cron, is_active,
        requires_parameters, batch_size, rate_limit_ms, source_instance_id
    ) VALUES (
        next_id, 'Action Unit Completions', '/api/v1/action-unit-completions/odata',
        'dim_action_unit_completions_staging', '0 0 3 * * *', true,
        false, 1000, 100, 1
    ) ON CONFLICT DO NOTHING;
    next_id := next_id + 1;

    -- 2. Invoices
    INSERT INTO dw_etl_jobs (
        id, name, source_endpoint, target_table, schedule_cron, is_active,
        requires_parameters, batch_size, rate_limit_ms, source_instance_id
    ) VALUES (
        next_id, 'Invoices', '/api/v1/invoices/odata',
        'dim_invoices_staging', '0 0 4 * * *', true,
        false, 1000, 100, 1
    ) ON CONFLICT DO NOTHING;
    next_id := next_id + 1;

    -- 3. Prospects
    INSERT INTO dw_etl_jobs (
        id, name, source_endpoint, target_table, schedule_cron, is_active,
        requires_parameters, batch_size, rate_limit_ms, source_instance_id
    ) VALUES (
        next_id, 'Prospects', '/api/v1/prospects/odata',
        'dim_prospects_staging', '0 0 3 * * *', true,
        false, 1000, 100, 1
    ) ON CONFLICT DO NOTHING;
    next_id := next_id + 1;

    -- 4. Remittances
    INSERT INTO dw_etl_jobs (
        id, name, source_endpoint, target_table, schedule_cron, is_active,
        requires_parameters, batch_size, rate_limit_ms, source_instance_id
    ) VALUES (
        next_id, 'Remittances', '/api/v1/remittances/odata',
        'dim_remittances_staging', '0 0 4 * * *', true,
        false, 1000, 100, 1
    ) ON CONFLICT DO NOTHING;
    next_id := next_id + 1;

    -- 5. Remittance Notes
    INSERT INTO dw_etl_jobs (
        id, name, source_endpoint, target_table, schedule_cron, is_active,
        requires_parameters, batch_size, rate_limit_ms, source_instance_id
    ) VALUES (
        next_id, 'Remittance Notes', '/api/v1/remittance-notes/odata',
        'dim_remittance_notes_staging', '0 0 4 * * *', true,
        false, 1000, 100, 1
    ) ON CONFLICT DO NOTHING;
    next_id := next_id + 1;

    -- 6. Site Payments
    INSERT INTO dw_etl_jobs (
        id, name, source_endpoint, target_table, schedule_cron, is_active,
        requires_parameters, batch_size, rate_limit_ms, source_instance_id
    ) VALUES (
        next_id, 'Site Payments', '/api/v1/site-payments/odata',
        'dim_site_payments_staging', '0 0 4 * * *', true,
        false, 1000, 100, 1
    ) ON CONFLICT DO NOTHING;
    next_id := next_id + 1;

    -- 7. Study Types (non-OData endpoint)
    INSERT INTO dw_etl_jobs (
        id, name, source_endpoint, target_table, schedule_cron, is_active,
        requires_parameters, batch_size, rate_limit_ms, source_instance_id
    ) VALUES (
        next_id, 'Study Types', '/api/v1/study-types',
        'dim_study_types_staging', '0 0 2 * * *', true,
        false, 1000, 100, 1
    ) ON CONFLICT DO NOTHING;
    next_id := next_id + 1;

    -- 8. Study Visit Arms (requires studyId parameter)
    INSERT INTO dw_etl_jobs (
        id, name, source_endpoint, target_table, schedule_cron, is_active,
        requires_parameters, parameter_name, parameter_source_table, parameter_source_column,
        batch_size, rate_limit_ms, source_instance_id
    ) VALUES (
        next_id, 'Study Visit Arms', '/api/v1/studies/{studyId}/visit-arms/odata',
        'dim_study_visit_arms_staging', '0 0 3 * * *', true,
        true, 'studyId', 'dim_studies_staging', 'id',
        1000, 100, 1
    ) ON CONFLICT DO NOTHING;
    next_id := next_id + 1;

    -- 9. Visit Element Relationships (requires studyId and visitId - complex)
    -- This is a nested endpoint, we'll create a simpler version first
    INSERT INTO dw_etl_jobs (
        id, name, source_endpoint, target_table, schedule_cron, is_active,
        requires_parameters, parameter_name, parameter_source_table, parameter_source_column,
        batch_size, rate_limit_ms, source_instance_id
    ) VALUES (
        next_id, 'Visit Elements by Study', '/api/v1/studies/{studyId}/visit-elements/odata',
        'dim_visit_element_relationships_staging', '0 0 3 * * *', true,
        true, 'studyId', 'dim_studies_staging', 'id',
        1000, 100, 1
    ) ON CONFLICT DO NOTHING;
    next_id := next_id + 1;

    -- 10. Patient Payments
    INSERT INTO dw_etl_jobs (
        id, name, source_endpoint, target_table, schedule_cron, is_active,
        requires_parameters, batch_size, rate_limit_ms, source_instance_id
    ) VALUES (
        next_id, 'Patient Payments', '/api/v1/patient-payments/odata',
        'dim_patient_payments_staging', '0 0 4 * * *', true,
        false, 1000, 100, 1
    ) ON CONFLICT DO NOTHING;

END $$;

-- ============================================================================
-- PART 3: Verify Insertions
-- ============================================================================

SELECT id, name, source_endpoint, target_table, is_active
FROM dw_etl_jobs
WHERE name IN (
    'Action Unit Completions',
    'Invoices',
    'Prospects',
    'Remittances',
    'Remittance Notes',
    'Site Payments',
    'Study Types',
    'Study Visit Arms',
    'Visit Elements by Study',
    'Patient Payments'
)
ORDER BY name;
