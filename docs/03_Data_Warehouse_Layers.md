# Data Warehouse Layers: Bronze, Silver, and Gold

**Document Version**: 1.0  
**Last Updated**: December 15, 2025  
**Author**: Manus AI  
**Purpose**: Documentation of data warehouse architecture, transformation logic, and layer-specific processing

---

## Table of Contents

1. [Data Warehouse Architecture](#data-warehouse-architecture)
2. [Bronze Layer (Staging)](#bronze-layer-staging)
3. [Silver Layer (Dimensional Model)](#silver-layer-dimensional-model)
4. [Gold Layer (Analytics)](#gold-layer-analytics)
5. [Transformation Procedures](#transformation-procedures)
6. [Data Quality and Governance](#data-quality-and-governance)

---

## Data Warehouse Architecture

The TrialSync data warehouse follows a medallion architecture with three layers: Bronze (raw staging), Silver (dimensional model), and Gold (analytics-ready).

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Clinical Conductor API                       │
│                  (Source System - Read Only)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │ ETL Jobs (GET requests)
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    BRONZE LAYER (Staging)                        │
│  • Raw JSON data from API                                        │
│  • 106 staging tables (*_staging)                                │
│  • ~5.8M records                                                 │
│  • Full API response preserved in JSONB                          │
│  • No transformations applied                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │ Transformation Procedures
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                  SILVER LAYER (Dimensional)                      │
│  • Normalized dimensional model                                  │
│  • Type 2 Slowly Changing Dimensions (SCD2)                      │
│  • 10+ dimension tables (dim_*)                                  │
│  • 5+ fact tables (fact_*)                                       │
│  • Surrogate keys, business keys                                 │
│  • Data quality rules applied                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │ Aggregation & Analytics
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    GOLD LAYER (Analytics)                        │
│  • Pre-aggregated metrics                                        │
│  • Business-specific views                                       │
│  • Performance dashboards                                        │
│  • Reporting tables                                              │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Characteristics

| Layer | Purpose | Data Format | Transformations | Users |
|-------|---------|-------------|-----------------|-------|
| **Bronze** | Raw data landing | JSONB (full API response) | None | ETL processes |
| **Silver** | Dimensional model | Normalized tables | Type 2 SCD, data quality | Data engineers, analysts |
| **Gold** | Analytics-ready | Aggregated metrics | Business logic | Business users, dashboards |

---

## Bronze Layer (Staging)

The Bronze layer contains raw data extracted from the Clinical Conductor API with minimal processing.

### Design Principles

**1. Preserve Source Data**: Store complete API responses in JSONB format to maintain full fidelity with source system.

**2. Idempotent Loads**: Support re-running ETL jobs without creating duplicates (upsert pattern).

**3. Audit Trail**: Track when data was loaded, which ETL job loaded it, and from which source.

**4. Schema Flexibility**: JSONB storage allows API schema changes without table alterations.

### Standard Staging Table Structure

All 106 staging tables follow this pattern:

```sql
CREATE TABLE dim_example_staging (
    id SERIAL PRIMARY KEY,
    data JSONB NOT NULL,                    -- Full API response
    source_id VARCHAR(255),                 -- Instance ID (from source_instance_id in job config)
    source_instance_id INTEGER,             -- FK to dw_api_credentials (for composite unique constraint)
    etl_job_id INTEGER,                     -- FK to dw_etl_jobs
    etl_run_id INTEGER,                     -- FK to dw_etl_runs
    loaded_at TIMESTAMP DEFAULT NOW(),      -- Load timestamp
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Composite unique constraint: (source_instance_id, data->>'id')
-- Ensures uniqueness per instance (multi-tenant support)
CREATE UNIQUE INDEX idx_example_instance_entity 
ON dim_example_staging(source_instance_id, (data->>'id'));

-- Indexes for performance
CREATE INDEX idx_example_source_id ON dim_example_staging(source_id);
CREATE INDEX idx_example_data_gin ON dim_example_staging USING gin(data);
CREATE INDEX idx_example_loaded_at ON dim_example_staging(loaded_at);
```

### Bronze Layer Tables

**Dimension Staging Tables** (57 tables):
- Core entities: `dim_studies_staging`, `dim_patients_staging`, `dim_sites_staging`
- Reference data: `dim_system_allergies_staging`, `dim_system_medications_staging`
- Relationships: `dim_subjects_staging`, `dim_patient_visits_staging`

**Fact Staging Tables** (23 tables):
- Transactions: `fact_study_milestones_staging`, `fact_patient_contacts_staging`
- Events: `fact_adverse_events_staging`, `fact_engagements_staging`

**Integration Tables** (26 tables):
- GoHighLevel: `ghl_contacts_staging`, `ghl_custom_fields_staging`

### Data Volume (as of December 15, 2025)

| Table | Records | Size | Growth Rate |
|-------|---------|------|-------------|
| `dim_patient_visits_staging` | 2,297,271 | 806 MB | High |
| `dim_visit_elements_staging` | 2,090,584 | 806 MB | High |
| `dim_appointments_staging` | 860,893 | 1.2 GB | High |
| `dim_studies_staging` | 157,270 | 7.2 MB | Medium |
| `dim_patients_staging` | 152,836 | 5.8 MB | Medium |
| `dim_subject_statuses_staging` | 119,749 | 4.5 MB | High |
| `dim_subjects_staging` | 88,773 | 3.3 MB | Medium |

### Querying Bronze Layer

Extract data from JSONB using PostgreSQL operators:

```sql
-- Extract top-level fields
SELECT 
    data->>'id' as study_id,
    data->>'name' as study_name,
    data->>'status' as status
FROM dim_studies_staging;

-- Extract nested objects
SELECT 
    data->>'id' as study_id,
    data->'sponsor'->>'name' as sponsor_name,
    data->'site'->>'name' as site_name
FROM dim_studies_staging;

-- Filter on JSONB fields
SELECT *
FROM dim_studies_staging
WHERE data->>'status' = '07. Enrollment'
  AND (data->'sponsor'->>'id')::int = 123;

-- Array operations
SELECT 
    data->>'id' as patient_id,
    jsonb_array_length(data->'allergies') as allergy_count
FROM dim_patients_staging
WHERE data->'allergies' IS NOT NULL;
```

### Bronze Layer Maintenance

**Full Refresh Pattern**:
```sql
-- Truncate and reload
TRUNCATE TABLE dim_studies_staging;
-- Run ETL job to reload
```

**Incremental Load Pattern**:
```sql
-- Upsert based on source_id
INSERT INTO dim_patients_staging (data, source_id, etl_job_id, loaded_at)
SELECT data, data->>'id', job_id, NOW()
FROM new_patient_records
ON CONFLICT (source_id) 
DO UPDATE SET 
    data = EXCLUDED.data,
    updated_at = NOW();
```

**Data Retention**:
- Staging data retained for 90 days
- After transformation to Silver layer, older Bronze data can be archived
- Backup before truncating for full refreshes

---

## Silver Layer (Dimensional Model)

The Silver layer transforms raw Bronze data into a normalized dimensional model following Kimball methodology.

### Design Principles

**1. Type 2 Slowly Changing Dimensions**: Track historical changes with effective dates and current flags.

**2. Surrogate Keys**: Use auto-incrementing keys for dimensions, natural keys for lookups.

**3. Conformed Dimensions**: Share dimensions across fact tables (e.g., dim_date used by all facts).

**4. Data Quality**: Apply validation rules, handle nulls, standardize formats.

**5. Grain Definition**: Each fact table has clearly defined grain (one row per what?).

### Dimensional Model

**Dimension Tables** (10 tables):

| Table | Purpose | Key Fields | SCD Type | Records |
|-------|---------|------------|----------|---------|
| `dim_studies` | Study master | study_key, study_id, study_name, status | Type 2 | ~160K |
| `dim_subjects` | Subject master | subject_key, subject_id, patient_id, study_id | Type 2 | ~90K |
| `dim_sites` | Clinical sites | site_key, site_id, site_name, address | Type 1 | ~320 |
| `dim_sponsors` | Study sponsors | sponsor_key, sponsor_id, sponsor_name | Type 1 | ~800 |
| `dim_staff` | Staff members | staff_key, staff_id, name, role | Type 1 | ~2,600 |
| `dim_date` | Date dimension | date_key, full_date, year, quarter, month | Type 0 | ~3,650 |
| `dim_patients` | Patient demographics (backup) | - | - | ~153K |

**Fact Tables** (5 tables):

| Table | Grain | Dimensions | Measures | Records |
|-------|-------|------------|----------|---------|
| `fact_study_performance` | One row per study per day | study, sponsor, snapshot_date | subjects, enrollment_velocity, completion_rate | ~400M |
| `fact_enrollment` | One row per subject enrollment | subject, study, site, sponsor, dates | age, days_to_enrollment, status flags | ~90K |
| `fact_element_completions` | One row per visit element completion | study, visit, element, staff | completion_date, duration_minutes | ~2M |
| `fact_visit_timelines` | One row per visit per day | study, visit, date, staff | duration, element_counts | ~10K |

### Type 2 SCD Implementation

Dimensions track changes over time using effective dates:

```sql
CREATE TABLE dim_studies (
    study_key SERIAL PRIMARY KEY,           -- Surrogate key
    study_id INTEGER NOT NULL,              -- Business key
    study_uid UUID,
    
    -- Attributes that can change
    study_name VARCHAR(500),
    study_status VARCHAR(100),
    protocol_number VARCHAR(100),
    sponsor_id INTEGER,
    sponsor_name VARCHAR(500),
    principal_investigator VARCHAR(500),
    
    -- SCD Type 2 fields
    effective_start_date TIMESTAMP NOT NULL DEFAULT NOW(),
    effective_end_date TIMESTAMP DEFAULT '9999-12-31',
    is_current BOOLEAN DEFAULT TRUE,
    
    -- Audit fields
    source_system VARCHAR(50) DEFAULT 'Clinical Conductor',
    etl_load_date TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_studies_business_key ON dim_studies(study_id, is_current);
CREATE INDEX idx_studies_effective_dates ON dim_studies(effective_start_date, effective_end_date);
```

**Example: Tracking Study Status Changes**

| study_key | study_id | study_name | study_status | effective_start_date | effective_end_date | is_current |
|-----------|----------|------------|--------------|----------------------|--------------------|------------|
| 1001 | 2388 | ACME Trial | 05. Start-up | 2024-01-01 | 2024-06-30 | FALSE |
| 1002 | 2388 | ACME Trial | 07. Enrollment | 2024-07-01 | 2025-03-31 | FALSE |
| 1003 | 2388 | ACME Trial | 09. Closeout | 2025-04-01 | 9999-12-31 | TRUE |

**Query Current State**:
```sql
SELECT * FROM dim_studies WHERE study_id = 2388 AND is_current = TRUE;
```

**Query Historical State**:
```sql
SELECT * 
FROM dim_studies 
WHERE study_id = 2388 
  AND '2024-08-15' BETWEEN effective_start_date AND effective_end_date;
```

### Fact Table Design

**fact_study_performance** - Daily study metrics:

```sql
CREATE TABLE fact_study_performance (
    performance_key SERIAL PRIMARY KEY,
    
    -- Dimension foreign keys
    study_key INTEGER REFERENCES dim_studies(study_key),
    sponsor_key INTEGER REFERENCES dim_sponsors(sponsor_key),
    snapshot_date_key INTEGER REFERENCES dim_date(date_key),
    
    -- Additive measures
    total_subjects INTEGER,
    screened_subjects INTEGER,
    enrolled_subjects INTEGER,
    randomized_subjects INTEGER,
    completed_subjects INTEGER,
    withdrawn_subjects INTEGER,
    screen_failure_subjects INTEGER,
    on_treatment_subjects INTEGER,
    
    -- Semi-additive measures (rates)
    screen_failure_rate NUMERIC(5,2),
    randomization_rate NUMERIC(5,2),
    completion_rate NUMERIC(5,2),
    withdrawal_rate NUMERIC(5,2),
    
    -- Non-additive measures (averages)
    avg_days_to_enrollment NUMERIC(10,2),
    avg_days_to_randomization NUMERIC(10,2),
    avg_days_to_completion NUMERIC(10,2),
    enrollment_velocity NUMERIC(10,2),  -- subjects per month
    
    -- Calculated fields
    days_since_start INTEGER,
    days_to_target INTEGER,
    percent_to_target NUMERIC(5,2),
    
    etl_load_date TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fact_study_perf_study ON fact_study_performance(study_key);
CREATE INDEX idx_fact_study_perf_date ON fact_study_performance(snapshot_date_key);
```

**fact_enrollment** - Subject enrollment events:

```sql
CREATE TABLE fact_enrollment (
    enrollment_key SERIAL PRIMARY KEY,
    
    -- Dimension foreign keys
    subject_key INTEGER REFERENCES dim_subjects(subject_key),
    study_key INTEGER REFERENCES dim_studies(study_key),
    site_key INTEGER REFERENCES dim_sites(site_key),
    sponsor_key INTEGER REFERENCES dim_sponsors(sponsor_key),
    enrollment_date_key INTEGER REFERENCES dim_date(date_key),
    randomization_date_key INTEGER REFERENCES dim_date(date_key),
    completion_date_key INTEGER REFERENCES dim_date(date_key),
    withdrawal_date_key INTEGER REFERENCES dim_date(date_key),
    
    -- Degenerate dimensions (attributes without separate dimension table)
    subject_status VARCHAR(100),
    treatment_status VARCHAR(100),
    screening_number VARCHAR(100),
    age_at_enrollment INTEGER,
    gender_code VARCHAR(10),
    race VARCHAR(100),
    
    -- Measures
    days_screening_to_enrollment INTEGER,
    days_enrollment_to_randomization INTEGER,
    days_randomization_to_completion INTEGER,
    
    -- Flags (for easy filtering)
    is_screen_failure BOOLEAN,
    is_randomized BOOLEAN,
    is_completed BOOLEAN,
    is_withdrawn BOOLEAN,
    
    etl_load_date TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_fact_enrollment_subject ON fact_enrollment(subject_key);
CREATE INDEX idx_fact_enrollment_study ON fact_enrollment(study_key);
CREATE INDEX idx_fact_enrollment_date ON fact_enrollment(enrollment_date_key);
```

### Date Dimension

A conformed date dimension used by all fact tables:

```sql
CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,           -- YYYYMMDD format
    full_date DATE NOT NULL,
    
    -- Date parts
    day_of_week INTEGER,
    day_of_month INTEGER,
    day_of_year INTEGER,
    week_of_year INTEGER,
    month_number INTEGER,
    month_name VARCHAR(20),
    quarter INTEGER,
    year INTEGER,
    
    -- Business calendar
    is_weekend BOOLEAN,
    is_holiday BOOLEAN,
    fiscal_year INTEGER,
    fiscal_quarter INTEGER,
    fiscal_month INTEGER,
    
    -- Relative periods
    is_current_day BOOLEAN,
    is_current_week BOOLEAN,
    is_current_month BOOLEAN,
    is_current_quarter BOOLEAN,
    is_current_year BOOLEAN
);

-- Populate date dimension for 10 years
SELECT populate_dw_dim_date('2020-01-01', '2030-12-31');
```

---

## Gold Layer (Analytics)

The Gold layer contains pre-aggregated metrics and business-specific views optimized for reporting and dashboards.

### Design Principles

**1. Business-Aligned**: Tables and views match business terminology and reporting needs.

**2. Performance-Optimized**: Pre-aggregated to reduce query complexity and improve response time.

**3. Self-Service Ready**: Documented, intuitive structure for business analysts.

**4. Incremental Updates**: Refresh only changed data, not full recompute.

### Analytics Views

**v_study_enrollment_summary** - Current enrollment status by study:

```sql
CREATE OR REPLACE VIEW v_study_enrollment_summary AS
SELECT 
    s.study_name,
    s.study_status,
    s.sponsor_name,
    s.site_name,
    COUNT(DISTINCT sub.subject_key) as total_subjects,
    SUM(CASE WHEN e.is_screen_failure THEN 1 ELSE 0 END) as screen_failures,
    SUM(CASE WHEN e.is_randomized THEN 1 ELSE 0 END) as randomized,
    SUM(CASE WHEN e.is_completed THEN 1 ELSE 0 END) as completed,
    SUM(CASE WHEN e.is_withdrawn THEN 1 ELSE 0 END) as withdrawn,
    ROUND(100.0 * SUM(CASE WHEN e.is_screen_failure THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as screen_failure_rate,
    AVG(e.days_enrollment_to_randomization) as avg_days_to_randomization
FROM dim_studies s
JOIN fact_enrollment e ON s.study_key = e.study_key
JOIN dim_subjects sub ON e.subject_key = sub.subject_key
WHERE s.is_current = TRUE
GROUP BY s.study_name, s.study_status, s.sponsor_name, s.site_name;
```

**v_subject_status_summary** - Subject counts by study and status:

```sql
CREATE OR REPLACE VIEW v_subject_status_summary AS
SELECT 
    (data->'study'->>'name') as study_name,
    data->>'status' as subject_status,
    data->>'treatmentStatus' as treatment_status,
    COUNT(*) as subject_count,
    SUM(CASE WHEN (data->>'enrollmentDate') IS NOT NULL THEN 1 ELSE 0 END) as enrolled_count
FROM dim_subjects_staging
GROUP BY 
    (data->'study'->>'name'),
    data->>'status',
    data->>'treatmentStatus'
ORDER BY study_name, subject_count DESC;
```

### Materialized Views

For expensive queries, use materialized views with scheduled refreshes:

```sql
CREATE MATERIALIZED VIEW mv_study_performance_metrics AS
SELECT 
    s.study_id,
    s.study_name,
    s.sponsor_name,
    sp.snapshot_date_key,
    d.full_date as snapshot_date,
    sp.total_subjects,
    sp.enrolled_subjects,
    sp.enrollment_velocity,
    sp.completion_rate,
    sp.percent_to_target
FROM fact_study_performance sp
JOIN dim_studies s ON sp.study_key = s.study_key
JOIN dim_date d ON sp.snapshot_date_key = d.date_key
WHERE s.is_current = TRUE
  AND d.full_date >= CURRENT_DATE - INTERVAL '90 days';

CREATE INDEX idx_mv_study_perf_study ON mv_study_performance_metrics(study_id);
CREATE INDEX idx_mv_study_perf_date ON mv_study_performance_metrics(snapshot_date);

-- Refresh daily
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_study_performance_metrics;
```

---

## Transformation Procedures

The transformation from Bronze to Silver layer is orchestrated by PostgreSQL stored procedures.

### Master ETL Procedures

**load_all_new_dimensions()** - Orchestrates all dimension loads:

```sql
CREATE OR REPLACE PROCEDURE load_all_new_dimensions()
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE NOTICE 'Starting load_all_new_dimensions()';
    
    CALL load_dw_dim_site();
    CALL load_dw_dim_monitor();
    CALL load_dw_dim_medical_code();
    CALL load_dw_dim_patient_engagement();
    CALL load_dw_dim_patient();  -- Added: Patient dimension (Type 2 SCD)
    CALL load_dw_dim_study();
    CALL load_dw_dim_subject();
    CALL load_dw_dim_visit();
    CALL load_dw_dim_visit_element();
    CALL load_dw_dim_study_arm();
    
    RAISE NOTICE 'load_all_new_dimensions() completed';
END;
$$;
```

**Note**: To add `load_dw_dim_patient()` to the master procedure, run:
```sql
-- See sql/transformations/update_load_all_new_dimensions.sql
```

**load_all_new_facts()** - Orchestrates all fact loads:

```sql
CREATE OR REPLACE PROCEDURE load_all_new_facts()
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE NOTICE 'Starting load_all_new_facts()';
    
    CALL load_dw_fact_subject_status_change();
    CALL load_dw_fact_patient_engagement();
    CALL load_dw_fact_visit();
    CALL load_dw_fact_visit_element_response();
    CALL load_dw_fact_subject_arm();
    
    RAISE NOTICE 'load_all_new_facts() completed';
END;
$$;
```

### Dimension Load Pattern (Type 2 SCD)

**load_dw_dim_study()** - Example of Type 2 SCD transformation:

```sql
CREATE OR REPLACE PROCEDURE load_dw_dim_study()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows_inserted INTEGER := 0;
    v_rows_updated INTEGER := 0;
BEGIN
    -- Step 1: Expire changed records (set end_date)
    UPDATE dim_studies ds
    SET
        effective_end_date = CURRENT_DATE - INTERVAL '1 day',
        is_current = FALSE,
        updated_at = NOW()
    FROM dim_studies_staging stg
    WHERE ds.study_id = (stg.data->>'id')::INTEGER
      AND ds.is_current = TRUE
      AND (
          ds.study_name != stg.data->>'name' OR
          COALESCE(ds.study_status, '') != COALESCE(stg.data->>'status', '')
      );
    
    GET DIAGNOSTICS v_rows_updated = ROW_COUNT;
    
    -- Step 2: Insert new/changed records
    INSERT INTO dim_studies (
        study_id,
        study_uid,
        study_name,
        protocol_number,
        study_status,
        sponsor_id,
        sponsor_name,
        site_id,
        site_name,
        principal_investigator,
        effective_start_date,
        effective_end_date,
        is_current,
        source_system,
        etl_load_date
    )
    SELECT 
        (data->>'id')::INTEGER,
        (data->>'uid')::UUID,
        data->>'name',
        data->>'protocolNumber',
        data->>'status',
        (data->'sponsor'->>'id')::INTEGER,
        data->'sponsor'->>'name',
        (data->'site'->>'id')::INTEGER,
        data->'site'->>'name',
        data->>'principalInvestigator',
        CURRENT_DATE,
        '9999-12-31'::DATE,
        TRUE,
        'Clinical Conductor',
        NOW()
    FROM dim_studies_staging stg
    WHERE NOT EXISTS (
        SELECT 1 FROM dim_studies ds
        WHERE ds.study_id = (stg.data->>'id')::INTEGER
          AND ds.is_current = TRUE
          AND ds.study_name = stg.data->>'name'
          AND COALESCE(ds.study_status, '') = COALESCE(stg.data->>'status', '')
    );
    
    GET DIAGNOSTICS v_rows_inserted = ROW_COUNT;
    
    RAISE NOTICE 'load_dw_dim_study: Updated %, Inserted %', v_rows_updated, v_rows_inserted;
END;
$$;
```

### Fact Load Pattern

**load_dw_fact_enrollment()** - Example fact table load:

```sql
CREATE OR REPLACE PROCEDURE load_dw_fact_enrollment()
LANGUAGE plpgsql
AS $$
DECLARE
    v_rows_inserted INTEGER := 0;
BEGIN
    -- Truncate and reload (full refresh pattern)
    TRUNCATE TABLE fact_enrollment;
    
    INSERT INTO fact_enrollment (
        subject_key,
        study_key,
        site_key,
        sponsor_key,
        enrollment_date_key,
        subject_status,
        treatment_status,
        screening_number,
        age_at_enrollment,
        gender_code,
        race,
        days_enrollment_to_randomization,
        is_screen_failure,
        is_randomized,
        is_completed,
        is_withdrawn,
        etl_load_date
    )
    SELECT 
        sub.subject_key,
        s.study_key,
        site.site_key,
        sp.sponsor_key,
        get_date_key((stg.data->>'enrollmentDate')::DATE),
        stg.data->>'status',
        stg.data->>'treatmentStatus',
        stg.data->>'screeningNumber',
        EXTRACT(YEAR FROM AGE((stg.data->>'enrollmentDate')::DATE, (stg.data->>'dateOfBirth')::DATE)),
        stg.data->>'gender',
        stg.data->>'race',
        EXTRACT(DAY FROM (stg.data->>'randomizationDate')::TIMESTAMP - (stg.data->>'enrollmentDate')::TIMESTAMP),
        (stg.data->>'status' LIKE '%Screen Failure%'),
        (stg.data->>'randomizationDate' IS NOT NULL),
        (stg.data->>'completionDate' IS NOT NULL),
        (stg.data->>'withdrawalDate' IS NOT NULL),
        NOW()
    FROM dim_subjects_staging stg
    JOIN dim_subjects sub ON sub.subject_id = (stg.data->>'id')::INTEGER AND sub.is_current = TRUE
    JOIN dim_studies s ON s.study_id = (stg.data->'study'->>'id')::INTEGER AND s.is_current = TRUE
    LEFT JOIN dim_sites site ON site.site_id = (stg.data->'site'->>'id')::INTEGER
    LEFT JOIN dim_sponsors sp ON sp.sponsor_id = (stg.data->'sponsor'->>'id')::INTEGER
    WHERE stg.data->>'enrollmentDate' IS NOT NULL;
    
    GET DIAGNOSTICS v_rows_inserted = ROW_COUNT;
    
    RAISE NOTICE 'load_dw_fact_enrollment: Inserted %', v_rows_inserted;
END;
$$;
```

### Helper Functions

**get_date_key()** - Convert date to date dimension key:

```sql
CREATE OR REPLACE FUNCTION get_date_key(p_date DATE)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN TO_CHAR(p_date, 'YYYYMMDD')::INTEGER;
END;
$$;
```

**get_element_category()** - Categorize visit elements:

```sql
CREATE OR REPLACE FUNCTION get_element_category(p_element_name VARCHAR)
RETURNS VARCHAR
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN CASE
        WHEN p_element_name ILIKE '%lab%' THEN 'Laboratory'
        WHEN p_element_name ILIKE '%vital%' THEN 'Vitals'
        WHEN p_element_name ILIKE '%assessment%' THEN 'Assessment'
        WHEN p_element_name ILIKE '%procedure%' THEN 'Procedure'
        WHEN p_element_name ILIKE '%consent%' THEN 'Consent'
        ELSE 'Other'
    END;
END;
$$;
```

### Execution Schedule

Transformations run on a scheduled basis:

| Procedure | Frequency | Duration | Dependencies |
|-----------|-----------|----------|--------------|
| `load_all_new_dimensions()` | Daily, 2 AM | ~15 min | Bronze layer loaded |
| `load_all_new_facts()` | Daily, 3 AM | ~30 min | Dimensions loaded |
| `REFRESH MATERIALIZED VIEW` | Daily, 4 AM | ~5 min | Facts loaded |

**Manual Execution**:
```sql
-- Run full ETL
CALL load_all_new_dimensions();
CALL load_all_new_facts();

-- Refresh materialized views
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_study_performance_metrics;
```

---

## Data Quality and Governance

### Data Quality Rules

**Dimension Quality Checks**:

```sql
-- Check for duplicate business keys
SELECT study_id, COUNT(*)
FROM dim_studies
WHERE is_current = TRUE
GROUP BY study_id
HAVING COUNT(*) > 1;

-- Check for orphaned records
SELECT COUNT(*)
FROM fact_enrollment e
LEFT JOIN dim_studies s ON e.study_key = s.study_key
WHERE s.study_key IS NULL;

-- Check for invalid dates
SELECT COUNT(*)
FROM fact_enrollment
WHERE enrollment_date_key NOT IN (SELECT date_key FROM dim_date);
```

**Fact Quality Checks**:

```sql
-- Check for negative measures
SELECT COUNT(*)
FROM fact_study_performance
WHERE total_subjects < 0 OR enrolled_subjects < 0;

-- Check for logical inconsistencies
SELECT COUNT(*)
FROM fact_study_performance
WHERE enrolled_subjects > total_subjects;

-- Check for missing dimension keys
SELECT COUNT(*)
FROM fact_enrollment
WHERE subject_key IS NULL OR study_key IS NULL;
```

### Data Lineage

Track data flow from source to target:

```sql
-- Lineage query: Bronze → Silver → Gold
SELECT 
    'Bronze' as layer,
    'dim_studies_staging' as table_name,
    COUNT(*) as record_count,
    MAX(loaded_at) as last_loaded
FROM dim_studies_staging
UNION ALL
SELECT 
    'Silver' as layer,
    'dim_studies' as table_name,
    COUNT(*) as record_count,
    MAX(etl_load_date) as last_loaded
FROM dim_studies
UNION ALL
SELECT 
    'Gold' as layer,
    'fact_study_performance' as table_name,
    COUNT(*) as record_count,
    MAX(etl_load_date) as last_loaded
FROM fact_study_performance;
```

### Documentation Standards

**Table Documentation**:
```sql
COMMENT ON TABLE dim_studies IS 'Type 2 SCD dimension for clinical studies. Tracks study attributes and changes over time.';
COMMENT ON COLUMN dim_studies.study_key IS 'Surrogate key (auto-increment). Use for joins.';
COMMENT ON COLUMN dim_studies.study_id IS 'Business key from Clinical Conductor. Natural key.';
COMMENT ON COLUMN dim_studies.is_current IS 'TRUE for current version of study, FALSE for historical.';
```

---

## Appendix: File Locations

### Transformation Scripts
- `/home/ubuntu/transformation_procedures.txt` - Full procedure definitions
- Database: `trialsync` on `tl-dev01.trialogic.ai:5432`

### Documentation
- `/home/ubuntu/docs/01_Clinical_Conductor_API_Reference.md` - API documentation
- `/home/ubuntu/docs/02_ETL_Jobs_and_Staging_Tables.md` - Bronze layer documentation
- `/home/ubuntu/docs/03_Data_Warehouse_Layers.md` - This document

### Related GitHub Repository
- Repository: `Trialogic/TrialSync`
- Backend: `backend/src/` (Node.js/TypeScript)
- Database migrations: `backend/migrations/` (if exists)

---

**Document End**
