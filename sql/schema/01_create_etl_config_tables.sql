-- ============================================================================
-- ETL Configuration Tables
-- ============================================================================
-- These tables store ETL job configurations and execution history
-- Database: trialsync
-- Schema: public
-- ============================================================================

-- Drop tables if they exist (for clean reinstall)
-- DROP TABLE IF EXISTS dw_etl_runs CASCADE;
-- DROP TABLE IF EXISTS dw_etl_jobs CASCADE;
-- DROP TABLE IF EXISTS dw_api_credentials CASCADE;

-- ============================================================================
-- API Credentials Table
-- ============================================================================
-- Stores credentials for different Clinical Conductor instances
-- ============================================================================

CREATE TABLE IF NOT EXISTS dw_api_credentials (
    id SERIAL PRIMARY KEY,
    instance_name VARCHAR(255) NOT NULL UNIQUE,
    base_url VARCHAR(500) NOT NULL,
    api_key VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE dw_api_credentials IS 'API credentials for Clinical Conductor instances';
COMMENT ON COLUMN dw_api_credentials.instance_name IS 'Unique name for this instance (e.g., "Tekton Research")';
COMMENT ON COLUMN dw_api_credentials.base_url IS 'Base URL for API (e.g., "https://tektonresearch.clinicalconductor.com/CCSWEB")';
COMMENT ON COLUMN dw_api_credentials.api_key IS 'API key for authentication';
COMMENT ON COLUMN dw_api_credentials.is_active IS 'Whether this credential is currently active';

-- Insert default credential
INSERT INTO dw_api_credentials (instance_name, base_url, api_key, description)
VALUES (
    'Tekton Research',
    'https://tektonresearch.clinicalconductor.com/CCSWEB',
    '9ba73e89-0423-47c1-a50c-b78c7034efea',
    'Primary Clinical Conductor instance for Tekton Research'
)
ON CONFLICT (instance_name) DO NOTHING;

-- ============================================================================
-- ETL Jobs Table
-- ============================================================================
-- Stores configuration for each ETL job
-- ============================================================================

CREATE TABLE IF NOT EXISTS dw_etl_jobs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    source_endpoint VARCHAR(500) NOT NULL,
    target_table VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    requires_parameters BOOLEAN DEFAULT FALSE,
    parameter_source_table VARCHAR(255),
    parameter_source_column VARCHAR(255),
    source_instance_id INTEGER REFERENCES dw_api_credentials(id),
    last_run_at TIMESTAMP,
    last_run_status VARCHAR(50),
    last_run_records INTEGER,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE dw_etl_jobs IS 'Configuration for ETL jobs that extract data from Clinical Conductor API';
COMMENT ON COLUMN dw_etl_jobs.name IS 'Human-readable name for the job';
COMMENT ON COLUMN dw_etl_jobs.source_endpoint IS 'API endpoint to call (e.g., "/api/v1/studies/odata")';
COMMENT ON COLUMN dw_etl_jobs.target_table IS 'Staging table to load data into';
COMMENT ON COLUMN dw_etl_jobs.is_active IS 'Whether this job should be executed';
COMMENT ON COLUMN dw_etl_jobs.requires_parameters IS 'Whether this job needs parameters (e.g., {studyId})';
COMMENT ON COLUMN dw_etl_jobs.parameter_source_table IS 'Table to query for parameter values';
COMMENT ON COLUMN dw_etl_jobs.parameter_source_column IS 'Column to extract parameter values from (JSONB path)';
COMMENT ON COLUMN dw_etl_jobs.source_instance_id IS 'FK to dw_api_credentials';
COMMENT ON COLUMN dw_etl_jobs.last_run_at IS 'Timestamp of last execution';
COMMENT ON COLUMN dw_etl_jobs.last_run_status IS 'Status of last execution (success, failed, running)';
COMMENT ON COLUMN dw_etl_jobs.last_run_records IS 'Number of records loaded in last execution';

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_etl_jobs_active ON dw_etl_jobs(is_active);
CREATE INDEX IF NOT EXISTS idx_etl_jobs_target_table ON dw_etl_jobs(target_table);
CREATE INDEX IF NOT EXISTS idx_etl_jobs_source_instance ON dw_etl_jobs(source_instance_id);

-- ============================================================================
-- ETL Runs Table
-- ============================================================================
-- Stores execution history for each ETL job run
-- ============================================================================

CREATE TABLE IF NOT EXISTS dw_etl_runs (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES dw_etl_jobs(id) ON DELETE CASCADE,
    run_status VARCHAR(50) NOT NULL,  -- running, success, failed
    records_loaded INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_seconds INTEGER,
    parameters JSONB,  -- Store parameters used for this run
    CONSTRAINT chk_run_status CHECK (run_status IN ('running', 'success', 'failed'))
);

COMMENT ON TABLE dw_etl_runs IS 'Execution history for ETL jobs';
COMMENT ON COLUMN dw_etl_runs.job_id IS 'FK to dw_etl_jobs';
COMMENT ON COLUMN dw_etl_runs.run_status IS 'Status: running, success, failed';
COMMENT ON COLUMN dw_etl_runs.records_loaded IS 'Number of records loaded in this run';
COMMENT ON COLUMN dw_etl_runs.error_message IS 'Error details if run failed';
COMMENT ON COLUMN dw_etl_runs.started_at IS 'When the job started';
COMMENT ON COLUMN dw_etl_runs.completed_at IS 'When the job completed';
COMMENT ON COLUMN dw_etl_runs.duration_seconds IS 'How long the job took';
COMMENT ON COLUMN dw_etl_runs.parameters IS 'Parameters used for this run (for parameterized jobs)';

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_etl_runs_job_id ON dw_etl_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_etl_runs_status ON dw_etl_runs(run_status);
CREATE INDEX IF NOT EXISTS idx_etl_runs_started_at ON dw_etl_runs(started_at DESC);

-- ============================================================================
-- Helper Views
-- ============================================================================

-- View: Recent job execution history
CREATE OR REPLACE VIEW v_etl_job_history AS
SELECT 
    j.id as job_id,
    j.name as job_name,
    j.is_active,
    r.id as run_id,
    r.run_status,
    r.records_loaded,
    r.started_at,
    r.completed_at,
    r.duration_seconds,
    r.error_message
FROM dw_etl_jobs j
LEFT JOIN dw_etl_runs r ON j.id = r.job_id
ORDER BY r.started_at DESC;

COMMENT ON VIEW v_etl_job_history IS 'Recent execution history for all ETL jobs';

-- View: Job success rate
CREATE OR REPLACE VIEW v_etl_job_success_rate AS
SELECT 
    j.id as job_id,
    j.name as job_name,
    COUNT(r.id) as total_runs,
    SUM(CASE WHEN r.run_status = 'success' THEN 1 ELSE 0 END) as successful_runs,
    SUM(CASE WHEN r.run_status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
    ROUND(100.0 * SUM(CASE WHEN r.run_status = 'success' THEN 1 ELSE 0 END) / NULLIF(COUNT(r.id), 0), 2) as success_rate,
    AVG(r.duration_seconds) as avg_duration_seconds,
    MAX(r.started_at) as last_run_at
FROM dw_etl_jobs j
LEFT JOIN dw_etl_runs r ON j.id = r.job_id
GROUP BY j.id, j.name
ORDER BY j.id;

COMMENT ON VIEW v_etl_job_success_rate IS 'Success rate and statistics for each ETL job';

-- ============================================================================
-- Helper Functions
-- ============================================================================

-- Function: Get active jobs
CREATE OR REPLACE FUNCTION get_active_etl_jobs()
RETURNS TABLE (
    job_id INTEGER,
    job_name VARCHAR(255),
    source_endpoint VARCHAR(500),
    target_table VARCHAR(255),
    requires_parameters BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT id, name, dw_etl_jobs.source_endpoint, dw_etl_jobs.target_table, dw_etl_jobs.requires_parameters
    FROM dw_etl_jobs
    WHERE is_active = TRUE
    ORDER BY id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_active_etl_jobs() IS 'Returns all active ETL jobs';

-- Function: Create ETL run record
CREATE OR REPLACE FUNCTION create_etl_run(p_job_id INTEGER, p_parameters JSONB DEFAULT NULL)
RETURNS INTEGER AS $$
DECLARE
    v_run_id INTEGER;
BEGIN
    INSERT INTO dw_etl_runs (job_id, run_status, parameters)
    VALUES (p_job_id, 'running', p_parameters)
    RETURNING id INTO v_run_id;
    
    RETURN v_run_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION create_etl_run(INTEGER, JSONB) IS 'Creates a new ETL run record and returns the run_id';

-- Function: Update ETL run record
CREATE OR REPLACE FUNCTION update_etl_run(
    p_run_id INTEGER,
    p_status VARCHAR(50),
    p_records_loaded INTEGER DEFAULT 0,
    p_error_message TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE dw_etl_runs
    SET 
        run_status = p_status,
        records_loaded = p_records_loaded,
        error_message = p_error_message,
        completed_at = NOW(),
        duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER
    WHERE id = p_run_id;
    
    -- Update last_run_* fields in dw_etl_jobs
    UPDATE dw_etl_jobs
    SET 
        last_run_at = NOW(),
        last_run_status = p_status,
        last_run_records = p_records_loaded,
        updated_at = NOW()
    WHERE id = (SELECT job_id FROM dw_etl_runs WHERE id = p_run_id);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_etl_run(INTEGER, VARCHAR, INTEGER, TEXT) IS 'Updates an ETL run record with completion status';

-- ============================================================================
-- Sample Queries
-- ============================================================================

-- View all active jobs
-- SELECT * FROM get_active_etl_jobs();

-- View recent job history
-- SELECT * FROM v_etl_job_history LIMIT 20;

-- View job success rates
-- SELECT * FROM v_etl_job_success_rate;

-- Get jobs that failed in last 24 hours
-- SELECT * FROM v_etl_job_history 
-- WHERE run_status = 'failed' 
--   AND started_at > NOW() - INTERVAL '24 hours';

-- ============================================================================
-- End of Script
-- ============================================================================
