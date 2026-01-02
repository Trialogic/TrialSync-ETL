-- ============================================================================
-- Silver Layer: dim_patients Table
-- ============================================================================
-- Type 2 Slowly Changing Dimension for Patients
-- Transforms data from dim_patients_staging (Bronze) to dim_patients (Silver)
-- ============================================================================

-- Drop if exists (for development)
-- DROP TABLE IF EXISTS dim_patients CASCADE;

CREATE TABLE IF NOT EXISTS dim_patients (
    -- Surrogate Key
    patient_key SERIAL PRIMARY KEY,
    
    -- Business Keys
    patient_id INTEGER NOT NULL,              -- From data->>'id'
    patient_uid UUID,                         -- From data->>'uid'
    
    -- Demographics
    first_name VARCHAR(100),
    middle_name VARCHAR(100),
    last_name VARCHAR(100),
    display_name VARCHAR(255),                -- From data->>'displayName'
    phonetic_name VARCHAR(100),
    preferred_name VARCHAR(100),
    title VARCHAR(50),
    
    -- Contact Information
    primary_email VARCHAR(255),               -- From data->'primaryEmail'->>'email'
    secondary_email VARCHAR(255),             -- From data->'secondaryEmail'->>'email'
    phone1_number VARCHAR(50),                -- From data->'phone1'->>'number'
    phone1_raw VARCHAR(50),                   -- From data->'phone1'->>'rawNumber'
    phone1_out_of_service BOOLEAN,            -- From data->'phone1'->>'outOfService'
    phone2_number VARCHAR(50),
    phone3_number VARCHAR(50),
    phone4_number VARCHAR(50),
    fax VARCHAR(50),
    
    -- Address
    address1 VARCHAR(200),
    address2 VARCHAR(200),
    address3 VARCHAR(200),
    city VARCHAR(200),
    state VARCHAR(25),
    zip VARCHAR(25),
    country VARCHAR(50),
    
    -- Demographics
    date_of_birth DATE,                       -- From data->>'dateOfBirth'
    date_of_death DATE,                       -- From data->>'dateOfDeath'
    gender_code VARCHAR(2),                    -- From data->>'genderCode'
    race VARCHAR(50),
    ethnicity VARCHAR(50),
    marital_status VARCHAR(50),
    native_language VARCHAR(50),
    
    -- Physical Attributes
    height_value NUMERIC(10,2),               -- From data->'height'->>'value'
    height_unit VARCHAR(20),                  -- From data->'height'->>'unit'
    weight_value NUMERIC(10,2),               -- From data->'weight'->>'value'
    weight_unit VARCHAR(20),                  -- From data->'weight'->>'unit'
    
    -- Medical Identifiers
    mrn VARCHAR(50),                          -- Medical Record Number
    ssn VARCHAR(50),                          -- Social Security Number
    
    -- Status and Flags
    status VARCHAR(50) NOT NULL,              -- From data->>'status' (Active, Inactive, etc.)
    status_reason VARCHAR(500),               -- From data->>'statusReason'
    do_not_mail BOOLEAN DEFAULT FALSE,
    recruitment_text_opt_in BOOLEAN DEFAULT FALSE,
    phone_type_to_text VARCHAR(20),           -- From data->>'phoneTypeToText'
    
    -- Site and Organization
    primary_site_id INTEGER,                  -- From data->'primarySite'->>'id'
    primary_site_uid UUID,                    -- From data->'primarySite'->>'uid'
    primary_site_name VARCHAR(255),          -- From data->'primarySite'->>'name'
    
    -- Import/Integration
    import_id INTEGER,                        -- From data->>'importId'
    import_source_id VARCHAR(50),             -- From data->>'importSourceId'
    import_patient_id VARCHAR(50),            -- From data->>'importPatientId'
    
    -- Guardian Information (stored as JSONB for flexibility)
    guardian_data JSONB,                      -- From data->>'guardian'
    
    -- Custom Fields (stored as JSONB array)
    custom_fields JSONB,                      -- From data->>'customFields'
    
    -- Active Studies (stored as JSONB array)
    active_studies JSONB,                     -- From data->>'activeStudies'
    
    -- Type 2 SCD Fields
    effective_start_date TIMESTAMP NOT NULL DEFAULT NOW(),
    effective_end_date TIMESTAMP DEFAULT '9999-12-31'::TIMESTAMP,
    is_current BOOLEAN DEFAULT TRUE,
    
    -- Audit Fields
    source_system VARCHAR(50) DEFAULT 'Clinical Conductor',
    etl_load_date TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_patients_business_key ON dim_patients(patient_id, is_current);
CREATE INDEX IF NOT EXISTS idx_patients_uid ON dim_patients(patient_uid) WHERE patient_uid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_patients_status ON dim_patients(status, is_current);
CREATE INDEX IF NOT EXISTS idx_patients_display_name ON dim_patients(display_name) WHERE display_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_patients_email ON dim_patients(primary_email) WHERE primary_email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_patients_phone ON dim_patients(phone1_number) WHERE phone1_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_patients_site ON dim_patients(primary_site_id) WHERE primary_site_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_patients_effective_dates ON dim_patients(effective_start_date, effective_end_date);
CREATE INDEX IF NOT EXISTS idx_patients_current ON dim_patients(is_current) WHERE is_current = TRUE;

-- Comments
COMMENT ON TABLE dim_patients IS 'Type 2 SCD dimension for patients. Tracks patient attributes and changes over time.';
COMMENT ON COLUMN dim_patients.patient_key IS 'Surrogate key (auto-increment). Use for joins.';
COMMENT ON COLUMN dim_patients.patient_id IS 'Business key from Clinical Conductor. Natural key.';
COMMENT ON COLUMN dim_patients.is_current IS 'TRUE for current version of patient, FALSE for historical.';
COMMENT ON COLUMN dim_patients.effective_start_date IS 'When this version of the patient record became effective.';
COMMENT ON COLUMN dim_patients.effective_end_date IS 'When this version of the patient record expired (9999-12-31 for current).';

-- ============================================================================
-- Transformation Procedure: load_dw_dim_patient()
-- ============================================================================
-- Loads data from dim_patients_staging (Bronze) to dim_patients (Silver)
-- Implements Type 2 SCD pattern
-- ============================================================================

CREATE OR REPLACE PROCEDURE load_dw_dim_patient()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows_inserted INTEGER := 0;
    v_rows_updated INTEGER := 0;
    v_rows_expired INTEGER := 0;
BEGIN
    RAISE NOTICE 'Starting load_dw_dim_patient() at %', NOW();
    
    -- Step 1: Expire changed records (set end_date and is_current = FALSE)
    UPDATE dim_patients dp
    SET
        effective_end_date = CURRENT_TIMESTAMP - INTERVAL '1 second',
        is_current = FALSE,
        updated_at = NOW()
    FROM dim_patients_staging stg
    WHERE dp.patient_id = (stg.data->>'id')::INTEGER
      AND dp.is_current = TRUE
      AND (
          -- Check for changes in key fields
          COALESCE(dp.status, '') != COALESCE(stg.data->>'status', '') OR
          COALESCE(dp.display_name, '') != COALESCE(stg.data->>'displayName', '') OR
          COALESCE(dp.first_name, '') != COALESCE(stg.data->>'firstName', '') OR
          COALESCE(dp.last_name, '') != COALESCE(stg.data->>'lastName', '') OR
          COALESCE(dp.primary_email, '') != COALESCE(stg.data->'primaryEmail'->>'email', '') OR
          COALESCE(dp.phone1_number, '') != COALESCE(stg.data->'phone1'->>'number', '') OR
          COALESCE(dp.primary_site_id::TEXT, '') != COALESCE(stg.data->'primarySite'->>'id', '')
      );
    
    GET DIAGNOSTICS v_rows_expired = ROW_COUNT;
    RAISE NOTICE 'Expired % changed patient records', v_rows_expired;
    
    -- Step 2: Insert new/changed records
    INSERT INTO dim_patients (
        patient_id,
        patient_uid,
        first_name,
        middle_name,
        last_name,
        display_name,
        phonetic_name,
        preferred_name,
        title,
        primary_email,
        secondary_email,
        phone1_number,
        phone1_raw,
        phone1_out_of_service,
        phone2_number,
        phone3_number,
        phone4_number,
        fax,
        address1,
        address2,
        address3,
        city,
        state,
        zip,
        country,
        date_of_birth,
        date_of_death,
        gender_code,
        race,
        ethnicity,
        marital_status,
        native_language,
        height_value,
        height_unit,
        weight_value,
        weight_unit,
        mrn,
        ssn,
        status,
        status_reason,
        do_not_mail,
        recruitment_text_opt_in,
        phone_type_to_text,
        primary_site_id,
        primary_site_uid,
        primary_site_name,
        import_id,
        import_source_id,
        import_patient_id,
        guardian_data,
        custom_fields,
        active_studies,
        effective_start_date,
        effective_end_date,
        is_current,
        source_system,
        etl_load_date
    )
    SELECT 
        (stg.data->>'id')::INTEGER,
        (stg.data->>'uid')::UUID,
        stg.data->>'firstName',
        stg.data->>'middleName',
        stg.data->>'lastName',
        stg.data->>'displayName',
        stg.data->>'phoneticName',
        stg.data->>'preferredName',
        stg.data->>'title',
        stg.data->'primaryEmail'->>'email',
        stg.data->'secondaryEmail'->>'email',
        stg.data->'phone1'->>'number',
        stg.data->'phone1'->>'rawNumber',
        (stg.data->'phone1'->>'outOfService')::BOOLEAN,
        stg.data->'phone2'->>'number',
        stg.data->'phone3'->>'number',
        stg.data->'phone4'->>'number',
        stg.data->>'fax',
        stg.data->>'address1',
        stg.data->>'address2',
        stg.data->>'address3',
        stg.data->>'city',
        stg.data->>'state',
        stg.data->>'zip',
        stg.data->>'country',
        CASE 
            WHEN stg.data->>'dateOfBirth' IS NOT NULL 
            THEN (stg.data->>'dateOfBirth')::DATE 
        END,
        CASE 
            WHEN stg.data->>'dateOfDeath' IS NOT NULL 
            THEN (stg.data->>'dateOfDeath')::DATE 
        END,
        stg.data->>'genderCode',
        stg.data->>'race',
        stg.data->>'ethnicity',
        stg.data->>'maritalStatus',
        stg.data->>'nativeLanguage',
        CASE 
            WHEN stg.data->'height'->>'value' IS NOT NULL 
            THEN (stg.data->'height'->>'value')::NUMERIC 
        END,
        stg.data->'height'->>'unit',
        CASE 
            WHEN stg.data->'weight'->>'value' IS NOT NULL 
            THEN (stg.data->'weight'->>'value')::NUMERIC 
        END,
        stg.data->'weight'->>'unit',
        stg.data->>'mrn',
        stg.data->>'ssn',
        stg.data->>'status',
        stg.data->>'statusReason',
        COALESCE((stg.data->>'doNotMail')::BOOLEAN, FALSE),
        COALESCE((stg.data->>'recruitmentTextOptIn')::BOOLEAN, FALSE),
        stg.data->>'phoneTypeToText',
        CASE 
            WHEN stg.data->'primarySite'->>'id' IS NOT NULL 
            THEN (stg.data->'primarySite'->>'id')::INTEGER 
        END,
        CASE 
            WHEN stg.data->'primarySite'->>'uid' IS NOT NULL 
            THEN (stg.data->'primarySite'->>'uid')::UUID 
        END,
        stg.data->'primarySite'->>'name',
        CASE 
            WHEN stg.data->>'importId' IS NOT NULL 
            THEN (stg.data->>'importId')::INTEGER 
        END,
        stg.data->>'importSourceId',
        stg.data->>'importPatientId',
        stg.data->'guardian',
        stg.data->'customFields',
        stg.data->'activeStudies',
        CURRENT_TIMESTAMP,
        '9999-12-31'::TIMESTAMP,
        TRUE,
        'Clinical Conductor',
        NOW()
    FROM dim_patients_staging stg
    WHERE stg.data->>'id' IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM dim_patients dp
          WHERE dp.patient_id = (stg.data->>'id')::INTEGER
            AND dp.is_current = TRUE
            AND dp.status = stg.data->>'status'
            AND COALESCE(dp.display_name, '') = COALESCE(stg.data->>'displayName', '')
            AND COALESCE(dp.first_name, '') = COALESCE(stg.data->>'firstName', '')
            AND COALESCE(dp.last_name, '') = COALESCE(stg.data->>'lastName', '')
            AND COALESCE(dp.primary_email, '') = COALESCE(stg.data->'primaryEmail'->>'email', '')
            AND COALESCE(dp.phone1_number, '') = COALESCE(stg.data->'phone1'->>'number', '')
      );
    
    GET DIAGNOSTICS v_rows_inserted = ROW_COUNT;
    RAISE NOTICE 'Inserted % new/changed patient records', v_rows_inserted;
    
    RAISE NOTICE 'load_dw_dim_patient() completed: Expired %, Inserted %', v_rows_expired, v_rows_inserted;
END;
$$;

COMMENT ON PROCEDURE load_dw_dim_patient() IS 'Transforms patient data from Bronze (staging) to Silver (dim_patients) layer with Type 2 SCD';

-- ============================================================================
-- Helper View: Current Patients
-- ============================================================================

CREATE OR REPLACE VIEW v_patients_current AS
SELECT *
FROM dim_patients
WHERE is_current = TRUE;

COMMENT ON VIEW v_patients_current IS 'Current version of all patients (is_current = TRUE)';

-- ============================================================================
-- Example Queries
-- ============================================================================

-- Get current patient by ID
-- SELECT * FROM v_patients_current WHERE patient_id = 12345;

-- Search by name
-- SELECT * FROM v_patients_current 
-- WHERE display_name ILIKE '%Smith%' OR first_name ILIKE '%John%';

-- Search by email
-- SELECT * FROM v_patients_current WHERE primary_email = 'patient@example.com';

-- Search by status
-- SELECT * FROM v_patients_current WHERE status = 'Active';

-- Get patient history (all versions)
-- SELECT * FROM dim_patients WHERE patient_id = 12345 ORDER BY effective_start_date;

