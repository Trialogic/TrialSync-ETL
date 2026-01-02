-- ============================================================================
-- Transformation Procedure Schedules Table
-- ============================================================================
-- Stores schedules for transformation procedures (stored procedures)
-- that transform data from Bronze (staging) to Silver layer
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS dw_transformation_schedules (
    id SERIAL PRIMARY KEY,
    procedure_name VARCHAR(255) NOT NULL UNIQUE,
    schedule_cron VARCHAR(128),
    is_active BOOLEAN DEFAULT TRUE,
    description TEXT,
    last_run_at TIMESTAMP,
    last_run_status VARCHAR(50), -- 'success', 'failed', 'running'
    next_run_time TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_transformation_schedules_active ON dw_transformation_schedules(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_transformation_schedules_procedure ON dw_transformation_schedules(procedure_name);

COMMENT ON TABLE dw_transformation_schedules IS 'Schedules for transformation procedures (Bronze → Silver layer)';
COMMENT ON COLUMN dw_transformation_schedules.procedure_name IS 'Name of the stored procedure (e.g., load_all_new_dimensions, load_dw_dim_patient)';
COMMENT ON COLUMN dw_transformation_schedules.schedule_cron IS 'Cron expression for when to run the procedure (e.g., "0 2 * * *" for daily at 2 AM)';
COMMENT ON COLUMN dw_transformation_schedules.is_active IS 'Whether this schedule is active';
COMMENT ON COLUMN dw_transformation_schedules.next_run_time IS 'Calculated next run time based on schedule_cron';

-- ============================================================================
-- Transformation Procedure Execution Log
-- ============================================================================
-- Logs execution history for transformation procedures
-- ============================================================================

CREATE TABLE IF NOT EXISTS dw_transformation_runs (
    id SERIAL PRIMARY KEY,
    procedure_name VARCHAR(255) NOT NULL,
    run_status VARCHAR(50) NOT NULL, -- 'running', 'success', 'failed'
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_seconds NUMERIC(10, 2),
    rows_affected INTEGER, -- Total rows inserted/updated/expired
    error_message TEXT,
    execution_log TEXT, -- Captured RAISE NOTICE messages
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_transformation_runs_procedure ON dw_transformation_runs(procedure_name);
CREATE INDEX idx_transformation_runs_status ON dw_transformation_runs(run_status);
CREATE INDEX idx_transformation_runs_started ON dw_transformation_runs(started_at DESC);

COMMENT ON TABLE dw_transformation_runs IS 'Execution history for transformation procedures';
COMMENT ON COLUMN dw_transformation_runs.procedure_name IS 'Name of the stored procedure that was executed';
COMMENT ON COLUMN dw_transformation_runs.execution_log IS 'Captured RAISE NOTICE messages from procedure execution';

COMMIT;

