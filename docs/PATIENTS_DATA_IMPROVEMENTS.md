# Patients Data Improvements

**Date**: January 1, 2026  
**Purpose**: Document improvements to patients data structure for better searching and updating

---

## Current State

### Bronze Layer (Staging)
- **Table**: `dim_patients_staging`
- **Structure**: JSONB column with full API response
- **Records**: ~153,000 patients
- **Fields**: All 43+ fields from API are captured in JSONB

### Issues Identified
1. ✅ **Data Completeness**: All fields are present in JSONB
2. ⚠️ **Searchability**: Querying requires JSONB operators (`data->>'field'`)
3. ⚠️ **Performance**: No indexes on commonly searched fields
4. ⚠️ **No Silver Layer**: No normalized table for easy querying

---

## Solution: Silver Layer Implementation

### Recommended Approach: Create `dim_patients` in Silver Layer

**Benefits**:
- ✅ Normalized columns for easy querying
- ✅ Proper indexes on searchable fields
- ✅ Type 2 SCD for historical tracking
- ✅ Preserves full JSONB in staging for flexibility
- ✅ Follows data warehouse best practices

### Implementation

#### Step 1: Create Silver Layer Table

```sql
-- Run the creation script
\i sql/silver/create_dim_patients.sql
```

This creates:
- `dim_patients` table with all important fields as columns
- Type 2 SCD support (tracks changes over time)
- Proper indexes on searchable fields
- Transformation procedure `load_dw_dim_patient()`

#### Step 2: Rebuild Staging (Optional)

If you want to ensure all fields are captured:

```bash
# Rebuild staging table
python scripts/rebuild_patients_staging.py
```

This will:
- Truncate `dim_patients_staging`
- Re-run Patients ETL job (Job ID 3)
- Load all patient records fresh from API

#### Step 3: Transform to Silver Layer

```sql
-- Load data from staging to silver
CALL load_dw_dim_patient();
```

This will:
- Extract all fields from JSONB
- Create normalized rows in `dim_patients`
- Handle Type 2 SCD (track changes)
- Set up proper indexes

---

## Silver Layer Table Structure

### Key Columns

| Column | Type | Source | Indexed | Purpose |
|--------|------|--------|---------|---------|
| `patient_key` | SERIAL | Auto | ✅ PK | Surrogate key |
| `patient_id` | INTEGER | `data->>'id'` | ✅ | Business key |
| `patient_uid` | UUID | `data->>'uid'` | ✅ | Global unique ID |
| `display_name` | VARCHAR | `data->>'displayName'` | ✅ | Full name |
| `first_name` | VARCHAR | `data->>'firstName'` | | First name |
| `last_name` | VARCHAR | `data->>'lastName'` | | Last name |
| `status` | VARCHAR | `data->>'status'` | ✅ | Active/Inactive/etc |
| `primary_email` | VARCHAR | `data->'primaryEmail'->>'email'` | ✅ | Email address |
| `phone1_number` | VARCHAR | `data->'phone1'->>'number'` | ✅ | Primary phone |
| `primary_site_id` | INTEGER | `data->'primarySite'->>'id'` | ✅ | Site reference |
| `date_of_birth` | DATE | `data->>'dateOfBirth'` | | DOB |
| `gender_code` | VARCHAR | `data->>'genderCode'` | | Gender |
| `is_current` | BOOLEAN | Auto | ✅ | Current version flag |

### Type 2 SCD Fields

- `effective_start_date`: When this version became active
- `effective_end_date`: When this version expired (9999-12-31 for current)
- `is_current`: TRUE for current version, FALSE for historical

---

## Usage Examples

### Query Current Patients

```sql
-- Use the view for current patients
SELECT * FROM v_patients_current 
WHERE status = 'Active'
LIMIT 10;
```

### Search by Name

```sql
SELECT patient_id, display_name, primary_email, status
FROM v_patients_current
WHERE display_name ILIKE '%Smith%'
   OR first_name ILIKE '%John%'
   OR last_name ILIKE '%Doe%';
```

### Search by Email

```sql
SELECT patient_id, display_name, primary_email, phone1_number
FROM v_patients_current
WHERE primary_email = 'patient@example.com';
```

### Search by Status

```sql
SELECT COUNT(*) as count, status
FROM v_patients_current
GROUP BY status
ORDER BY count DESC;
```

### Get Patient History

```sql
-- See all versions of a patient (Type 2 SCD)
SELECT 
    patient_id,
    display_name,
    status,
    effective_start_date,
    effective_end_date,
    is_current
FROM dim_patients
WHERE patient_id = 12345
ORDER BY effective_start_date;
```

### Join with Other Tables

```sql
-- Join with visits
SELECT 
    p.display_name,
    p.status,
    COUNT(v.visit_id) as visit_count
FROM v_patients_current p
LEFT JOIN dim_patient_visits v ON v.patient_id = p.patient_id
GROUP BY p.patient_id, p.display_name, p.status
ORDER BY visit_count DESC;
```

---

## Maintenance

### Daily Load

```sql
-- Run after ETL jobs complete
CALL load_dw_dim_patient();
```

### Verify Data Quality

```sql
-- Check for duplicates
SELECT patient_id, COUNT(*)
FROM dim_patients
WHERE is_current = TRUE
GROUP BY patient_id
HAVING COUNT(*) > 1;

-- Check for missing required fields
SELECT COUNT(*) 
FROM v_patients_current
WHERE patient_id IS NULL OR status IS NULL;
```

---

## Alternative: Enhanced Staging (Not Recommended)

If you prefer to keep everything in staging, you could add computed columns:

```sql
-- Add computed columns
ALTER TABLE dim_patients_staging
ADD COLUMN patient_id INTEGER GENERATED ALWAYS AS ((data->>'id')::INTEGER) STORED,
ADD COLUMN status VARCHAR(50) GENERATED ALWAYS AS (data->>'status') STORED,
ADD COLUMN display_name VARCHAR(255) GENERATED ALWAYS AS (data->>'displayName') STORED,
ADD COLUMN primary_email VARCHAR(255) GENERATED ALWAYS AS (data->'primaryEmail'->>'email') STORED;

-- Add indexes
CREATE INDEX idx_patients_staging_patient_id ON dim_patients_staging(patient_id);
CREATE INDEX idx_patients_staging_status ON dim_patients_staging(status);
CREATE INDEX idx_patients_staging_display_name ON dim_patients_staging(display_name);
CREATE INDEX idx_patients_staging_email ON dim_patients_staging(primary_email);
```

**Why Silver Layer is Better**:
- ✅ Follows data warehouse best practices
- ✅ Type 2 SCD for historical tracking
- ✅ Cleaner separation of concerns
- ✅ Better for reporting and analytics
- ✅ Easier to maintain and query

---

## Files Created

1. **`sql/silver/create_dim_patients.sql`**: Table creation and transformation procedure
2. **`scripts/rebuild_patients_staging.py`**: Script to rebuild staging table
3. **`scripts/analyze_patients_staging.py`**: Analysis script for staging data

---

## Next Steps

1. ✅ Review the silver layer table structure
2. ✅ Run `create_dim_patients.sql` to create the table
3. ⏳ Optionally rebuild staging: `python scripts/rebuild_patients_staging.py`
4. ⏳ Transform to silver: `CALL load_dw_dim_patient();`
5. ⏳ Verify: `SELECT * FROM v_patients_current LIMIT 10;`

---

**Status**: ✅ Silver layer solution ready for implementation

