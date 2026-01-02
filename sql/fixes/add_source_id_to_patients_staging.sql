-- ============================================================================
-- Add source_id column to dim_patients_staging for upsert support
-- ============================================================================
-- The DataLoader requires a source_id column for ON CONFLICT upserts
-- ============================================================================

BEGIN;

-- Add source_id column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'dim_patients_staging' 
        AND column_name = 'source_id'
    ) THEN
        ALTER TABLE dim_patients_staging 
        ADD COLUMN source_id VARCHAR(255);
        
        -- Populate source_id from data->>'id' for existing records
        UPDATE dim_patients_staging
        SET source_id = data->>'id'
        WHERE source_id IS NULL AND data->>'id' IS NOT NULL;
        
        -- Create unique index on source_id for upsert
        CREATE UNIQUE INDEX IF NOT EXISTS idx_dim_patients_staging_source_id 
        ON dim_patients_staging(source_id) 
        WHERE source_id IS NOT NULL;
        
        RAISE NOTICE 'Added source_id column and unique index';
    ELSE
        RAISE NOTICE 'source_id column already exists';
    END IF;
END $$;

-- Verify
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'dim_patients_staging'
AND column_name = 'source_id';

COMMIT;

