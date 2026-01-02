-- ============================================================================
-- Migration: Standardize Patient Sub-Endpoint Staging Table Schemas
-- ============================================================================
-- Purpose: Aligns patient sub-endpoint staging tables with dim_patients_staging
--          schema to enable the standard DataLoader to work with these tables.
--
-- Tables affected:
--   - dim_patient_allergies_staging
--   - dim_patient_conditions_staging
--   - dim_patient_devices_staging
--   - dim_patient_medications_staging
--   - dim_patient_procedures_staging
--   - dim_patient_immunizations_staging
--   - dim_patient_providers_staging
--   - dim_patient_family_history_staging
--   - dim_patient_social_history_staging
--   - dim_patient_campaign_touches_staging
--   - dim_patient_referral_touches_staging
--
-- Changes per table:
--   - Adds: source_id, etl_job_id, etl_run_id, created_at, updated_at
--   - Adds: Unique constraint on (source_instance_id, data->>'id')
--   - Backfills: Existing data with metadata from JSON
--   - Keeps: patient_id column (for query convenience)
--
-- Dependencies:
--   - None (can run independently)
--
-- Rollback:
--   - See bottom of file for rollback statements
-- ============================================================================

BEGIN;

-- ============================================================================
-- Helper function to migrate a single table
-- ============================================================================
CREATE OR REPLACE FUNCTION migrate_patient_staging_table(table_name TEXT)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    col_exists BOOLEAN;
    idx_name TEXT;
    result TEXT := '';
    rows_deleted INTEGER;
BEGIN
    -- 1. Add source_id column if not exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE information_schema.columns.table_name = migrate_patient_staging_table.table_name
        AND column_name = 'source_id'
    ) INTO col_exists;

    IF NOT col_exists THEN
        EXECUTE format('ALTER TABLE %I ADD COLUMN source_id VARCHAR(255)', table_name);
        result := result || 'Added source_id, ';
    END IF;

    -- 2. Add etl_job_id column if not exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE information_schema.columns.table_name = migrate_patient_staging_table.table_name
        AND column_name = 'etl_job_id'
    ) INTO col_exists;

    IF NOT col_exists THEN
        EXECUTE format('ALTER TABLE %I ADD COLUMN etl_job_id INTEGER', table_name);
        result := result || 'Added etl_job_id, ';
    END IF;

    -- 3. Add etl_run_id column if not exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE information_schema.columns.table_name = migrate_patient_staging_table.table_name
        AND column_name = 'etl_run_id'
    ) INTO col_exists;

    IF NOT col_exists THEN
        EXECUTE format('ALTER TABLE %I ADD COLUMN etl_run_id INTEGER', table_name);
        result := result || 'Added etl_run_id, ';
    END IF;

    -- 4. Add created_at column if not exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE information_schema.columns.table_name = migrate_patient_staging_table.table_name
        AND column_name = 'created_at'
    ) INTO col_exists;

    IF NOT col_exists THEN
        EXECUTE format('ALTER TABLE %I ADD COLUMN created_at TIMESTAMP DEFAULT NOW()', table_name);
        result := result || 'Added created_at, ';
    END IF;

    -- 5. Add updated_at column if not exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE information_schema.columns.table_name = migrate_patient_staging_table.table_name
        AND column_name = 'updated_at'
    ) INTO col_exists;

    IF NOT col_exists THEN
        EXECUTE format('ALTER TABLE %I ADD COLUMN updated_at TIMESTAMP DEFAULT NOW()', table_name);
        result := result || 'Added updated_at, ';
    END IF;

    -- 6. Backfill existing data with metadata from JSON (if etl_job_id in data)
    EXECUTE format('
        UPDATE %I
        SET
            source_id = COALESCE(source_id, source_instance_id::TEXT),
            etl_job_id = COALESCE(etl_job_id, (data->>''etl_job_id'')::INTEGER),
            created_at = COALESCE(created_at, loaded_at),
            updated_at = COALESCE(updated_at, loaded_at)
        WHERE etl_job_id IS NULL
    ', table_name);

    result := result || 'Backfilled metadata, ';

    -- 7. Remove duplicates before creating unique index
    -- Keep the most recently loaded record for each (source_instance_id, data->>'id')
    EXECUTE format('
        DELETE FROM %I a
        USING (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY source_instance_id, data->>''id''
                ORDER BY loaded_at DESC NULLS LAST, id DESC
            ) as rn
            FROM %I
        ) b
        WHERE a.id = b.id AND b.rn > 1
    ', table_name, table_name);

    GET DIAGNOSTICS rows_deleted = ROW_COUNT;
    IF rows_deleted > 0 THEN
        result := result || format('Removed %s duplicates, ', rows_deleted);
    END IF;

    -- 8. Create unique index for upsert (if not exists)
    idx_name := 'idx_' || replace(table_name, 'dim_', '') || '_upsert';

    -- Check if index exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = idx_name
    ) THEN
        EXECUTE format('
            CREATE UNIQUE INDEX %I ON %I (source_instance_id, (data->>''id''))
        ', idx_name, table_name);
        result := result || 'Created unique index';
    ELSE
        result := result || 'Index already exists';
    END IF;

    RETURN result;
END;
$$;

-- ============================================================================
-- Migrate all patient sub-endpoint staging tables
-- ============================================================================

DO $$
DECLARE
    tables TEXT[] := ARRAY[
        'dim_patient_allergies_staging',
        'dim_patient_conditions_staging',
        'dim_patient_devices_staging',
        'dim_patient_medications_staging',
        'dim_patient_procedures_staging',
        'dim_patient_immunizations_staging',
        'dim_patient_providers_staging',
        'dim_patient_family_history_staging',
        'dim_patient_social_history_staging',
        'dim_patient_campaign_touches_staging',
        'dim_patient_referral_touches_staging'
    ];
    tbl TEXT;
    migration_result TEXT;
BEGIN
    FOREACH tbl IN ARRAY tables
    LOOP
        -- Check if table exists
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = tbl
        ) THEN
            migration_result := migrate_patient_staging_table(tbl);
            RAISE NOTICE 'Migrated %: %', tbl, migration_result;
        ELSE
            RAISE NOTICE 'Table % does not exist, skipping', tbl;
        END IF;
    END LOOP;
END;
$$;

-- ============================================================================
-- Clean up helper function
-- ============================================================================
DROP FUNCTION IF EXISTS migrate_patient_staging_table(TEXT);

-- ============================================================================
-- Step 2: Create trigger to auto-populate patient_id from data
-- ============================================================================
-- This trigger extracts patient_id from the _parentId field in the JSON data
-- which is injected by the executor for parameterized jobs.

CREATE OR REPLACE FUNCTION set_patient_id_from_data()
RETURNS TRIGGER AS $$
BEGIN
    -- Extract patient_id from _parentId in data JSON
    IF NEW.patient_id IS NULL AND NEW.data IS NOT NULL THEN
        NEW.patient_id := COALESCE(
            (NEW.data->>'_parentId')::INTEGER,
            (NEW.data->>'patientId')::INTEGER
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION set_patient_id_from_data IS
    'Trigger function to auto-populate patient_id from JSON data._parentId field.
     The executor injects _parentId for parameterized jobs.';

-- Create triggers on all patient staging tables
DO $$
DECLARE
    tables TEXT[] := ARRAY[
        'dim_patient_allergies_staging',
        'dim_patient_conditions_staging',
        'dim_patient_devices_staging',
        'dim_patient_medications_staging',
        'dim_patient_procedures_staging',
        'dim_patient_immunizations_staging',
        'dim_patient_providers_staging',
        'dim_patient_family_history_staging',
        'dim_patient_social_history_staging',
        'dim_patient_campaign_touches_staging',
        'dim_patient_referral_touches_staging'
    ];
    tbl TEXT;
    trigger_name TEXT;
BEGIN
    FOREACH tbl IN ARRAY tables
    LOOP
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = tbl) THEN
            trigger_name := 'trg_' || tbl || '_set_patient_id';
            EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I', trigger_name, tbl);
            EXECUTE format('
                CREATE TRIGGER %I
                BEFORE INSERT OR UPDATE ON %I
                FOR EACH ROW
                EXECUTE FUNCTION set_patient_id_from_data()
            ', trigger_name, tbl);
            RAISE NOTICE 'Created trigger % on %', trigger_name, tbl;
        END IF;
    END LOOP;
END;
$$;

-- ============================================================================
-- Verification: Show updated schema for one table
-- ============================================================================
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'dim_patient_allergies_staging'
ORDER BY ordinal_position;

-- Show all indexes on patient staging tables
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename LIKE 'dim_patient_%_staging'
ORDER BY tablename, indexname;

COMMIT;

-- ============================================================================
-- ROLLBACK SCRIPT (run separately if needed)
-- ============================================================================
-- WARNING: This will drop the new columns and indexes. Data in those columns
-- will be lost. Only run if you need to revert the migration.
--
-- BEGIN;
--
-- DO $$
-- DECLARE
--     tables TEXT[] := ARRAY[
--         'dim_patient_allergies_staging',
--         'dim_patient_conditions_staging',
--         'dim_patient_devices_staging',
--         'dim_patient_medications_staging',
--         'dim_patient_procedures_staging',
--         'dim_patient_immunizations_staging',
--         'dim_patient_providers_staging',
--         'dim_patient_family_history_staging',
--         'dim_patient_social_history_staging',
--         'dim_patient_campaign_touches_staging',
--         'dim_patient_referral_touches_staging'
--     ];
--     tbl TEXT;
--     idx_name TEXT;
-- BEGIN
--     FOREACH tbl IN ARRAY tables
--     LOOP
--         IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = tbl) THEN
--             -- Drop index
--             idx_name := 'idx_' || replace(tbl, 'dim_', '') || '_upsert';
--             EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
--
--             -- Drop columns (only if they exist)
--             EXECUTE format('ALTER TABLE %I DROP COLUMN IF EXISTS source_id', tbl);
--             EXECUTE format('ALTER TABLE %I DROP COLUMN IF EXISTS etl_job_id', tbl);
--             EXECUTE format('ALTER TABLE %I DROP COLUMN IF EXISTS etl_run_id', tbl);
--             EXECUTE format('ALTER TABLE %I DROP COLUMN IF EXISTS created_at', tbl);
--             EXECUTE format('ALTER TABLE %I DROP COLUMN IF EXISTS updated_at', tbl);
--
--             RAISE NOTICE 'Rolled back %', tbl;
--         END IF;
--     END LOOP;
-- END;
-- $$;
--
-- COMMIT;
