# ETL Jobs and Staging Tables Reference

**Document Version**: 1.0  
**Last Updated**: December 15, 2025  
**Author**: Manus AI  
**Purpose**: Complete reference for ETL job configurations, staging table structures, and data loading patterns

---

## Table of Contents

1. [ETL System Overview](#etl-system-overview)
2. [ETL Job Configuration](#etl-job-configuration)
3. [Staging Table Architecture](#staging-table-architecture)
4. [Job Execution Patterns](#job-execution-patterns)
5. [Data Loading Scripts](#data-loading-scripts)
6. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)

---

## ETL System Overview

The TrialSync ETL system extracts data from the Clinical Conductor API and loads it into PostgreSQL staging tables (Bronze layer). The system is configured through database tables and executed by a GUI-based job scheduler.

### System Architecture

```
Clinical Conductor API
        ↓
  ETL Job Scheduler (GUI)
        ↓
   Staging Tables (Bronze Layer)
        ↓
  Transformation Logic (Silver Layer)
        ↓
   Analytics Tables (Gold Layer)
```

### Key Statistics

| Metric | Value |
|--------|-------|
| **Total ETL Jobs** | 90 |
| **Active Jobs** | 76 |
| **Disabled Jobs** | 14 |
| **Parameterized Jobs** | 40 |
| **Non-Parameterized Jobs** | 50 |
| **Total Staging Tables** | 106 |
| **Tables with Data** | 52 |
| **Total Records in Staging** | ~5.8 million |

### Database Configuration

**Host**: localhost  
**Port**: 5432  
**Database**: trialsync_dev  
**User**: chrisprader  
**Schema**: public  

**Connection String**:
```
postgresql://chrisprader@localhost:5432/trialsync_dev
```

**Note**: Database connection details are configured in `.env` file via `DATABASE_URL`.

---

## ETL Job Configuration

All ETL jobs are configured in the `dw_etl_jobs` table. Each job defines:
- Source API endpoint
- Target staging table
- Parameter requirements
- Execution status

### ETL Jobs Table Schema

```sql
CREATE TABLE dw_etl_jobs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    source_endpoint TEXT NOT NULL,
    target_table VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    requires_parameters BOOLEAN DEFAULT false,
    parameter_name VARCHAR(100),
    parameter_source_table VARCHAR(255),
    parameter_source_column VARCHAR(255),
    parent_job_id INTEGER REFERENCES dw_etl_jobs(id),
    source_instance_id INTEGER REFERENCES dw_api_credentials(id),
    last_run_status VARCHAR(50),
    last_run_at TIMESTAMP,
    last_run_records INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Complete ETL Job Inventory

The full list of 90 ETL jobs with their configurations is stored in:
- **File**: `/home/ubuntu/etl_jobs_export.txt`
- **Format**: Pipe-delimited (|)
- **Columns**: id|name|endpoint|target_table|status|parameterized|param_name|param_source|param_column|last_status|records

### Job Categories

**Dimension Tables (Master Data)** - 57 jobs:
- Core entities: Studies, Patients, Sites, Providers, Staff
- Reference data: System allergies, medications, conditions
- Lookup tables: Study statuses, subject statuses, document types

**Fact Tables (Transactional Data)** - 23 jobs:
- Patient visits, appointments, visit elements
- Subject statuses, patient touches
- Invoices, payments, remittances

**Metadata/Configuration** - 10 jobs:
- Instance details, topology
- Study arms, protocol versions, personnel

### Active vs Disabled Jobs

**Active Jobs (76)**:
These jobs are enabled and will execute when triggered by the ETL scheduler.

**Disabled Jobs (14)**:
| Job ID | Name | Reason |
|--------|------|--------|
| 4 | Users | Invalid endpoint (404) |
| 5 | Roles | Invalid endpoint (404) |
| 6 | Departments | Invalid endpoint (404) |
| 7 | Audits | Invalid endpoint (404) |
| 12 | Forms | Invalid endpoint (404) |
| 18 | ProtocolDeviations | Invalid endpoint (404) |
| 19 | AdverseEvents | Invalid endpoint (404) |
| 21 | LabResults | Invalid endpoint (404) |
| 22 | Vitals | Invalid endpoint (404) |
| 27 | StudyActions | Needs parameter fix (should be re-enabled) |
| 30 | MonitorQueries | CCE-only feature (501 error) |
| 31 | Engagements | CCE-only feature (501 error) |
| 143 | Study Roles | Needs parameter fix |
| 146 | Study Integration Info | Needs parameter fix |

---

## Staging Table Architecture

All staging tables follow a consistent naming convention and structure.

### Naming Convention

| Pattern | Example | Purpose |
|---------|---------|---------|
| `dim_*_staging` | `dim_patients_staging` | Dimension table staging |
| `fact_*_staging` | `fact_study_milestones_staging` | Fact table staging |
| `ghl_*_staging` | `ghl_contacts_staging` | GoHighLevel integration data |

### Standard Table Structure

All staging tables include these standard columns:

```sql
CREATE TABLE dim_example_staging (
    id SERIAL PRIMARY KEY,
    data JSONB NOT NULL,                    -- Full API response
    source_id VARCHAR(255),                 -- Instance ID (from source_instance_id in job config)
    source_instance_id INTEGER,            -- FK to dw_api_credentials (for composite unique constraint)
    etl_job_id INTEGER,                     -- Reference to dw_etl_jobs
    etl_run_id INTEGER,                     -- Reference to dw_etl_runs
    loaded_at TIMESTAMP DEFAULT NOW(),      -- Load timestamp
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Composite unique constraint for multi-tenant support
CREATE UNIQUE INDEX idx_example_instance_entity 
ON dim_example_staging(source_instance_id, (data->>'id'));

CREATE INDEX idx_example_source_id ON dim_example_staging(source_id);
CREATE INDEX idx_example_data_gin ON dim_example_staging USING gin(data);
```

### Data Storage Pattern

All API response data is stored in the `data` JSONB column. This provides:
- **Flexibility**: Schema changes don't require table alterations
- **Completeness**: Full API response preserved
- **Queryability**: JSONB operators enable complex queries

**Example Query**:
```sql
-- Extract specific fields from JSONB
SELECT 
    data->>'id' as study_id,
    data->>'name' as study_name,
    data->>'status' as status,
    (data->'sponsor'->>'name') as sponsor_name
FROM dim_studies_staging
WHERE data->>'status' = '07. Enrollment';
```

### Staging Tables with Data

The following tables contain loaded data (as of December 15, 2025):

| Table | Records | Size | Last Updated |
|-------|---------|------|--------------|
| `dim_patient_visits_staging` | 2,297,271 | 806 MB | Active |
| `dim_visit_elements_staging` | 2,090,584 | 806 MB | Active |
| `dim_appointments_staging` | 860,893 | 1.2 GB | Active |
| `dim_studies_staging` | 157,270 | 7.2 MB | Active |
| `dim_patients_staging` | 152,836 | 5.8 MB | Active |
| `dim_subject_statuses_staging` | 119,749 | 4.5 MB | Active |
| `dim_subjects_staging` | 88,773 | 3.3 MB | Active |
| `dim_elements_staging` | 31,672 | 1.2 MB | Active |
| `dim_visits_staging` | 9,506 | 7.2 MB | Active |
| `dim_system_allergies_staging` | 1,873 | 72 kB | Active |
| `dim_system_medications_staging` | 2,296 | 784 kB | Active |
| `dim_system_devices_staging` | 3,295 | 128 kB | Active |
| `dim_staff_staging` | 2,617 | 96 kB | Active |
| `dim_patient_medications_staging` | 899 | 32 kB | Active |
| `dim_sponsors_staging` | 798 | 32 kB | Active |
| `dim_patient_allergies_staging` | 674 | 24 kB | Active |
| `dim_system_procedures_staging` | 672 | 224 kB | Active |
| `dim_patient_campaign_touches_staging` | 554 | 24 kB | Active |
| `dim_sponsor_divisions_staging` | 548 | 24 kB | Active |
| `dim_sponsor_teams_staging` | 546 | 24 kB | Active |
| `dim_study_documents_staging` | 852 | 32 kB | Active |
| `dim_providers_staging` | 398 | 16 kB | Active |
| `dim_sites_staging` | 320 | 16 kB | Active |
| `dim_rooms_staging` | 116 | 8 kB | Active |
| `dim_patient_devices_staging` | 99 | 8 kB | Active |
| `dim_monitors_staging` | 68 | 8 kB | Active |
| `dim_patient_referral_touches_staging` | 28 | 8 kB | Active |
| `dim_schedules_staging` | 20 | 8 kB | Active |

### Empty Staging Tables

These tables exist but contain no data (either invalid endpoints or no data in source):

- `dim_action_unit_completions_staging` (0 records)
- `dim_adverse_events_staging` (0 records)
- `dim_concomitant_medications_staging` (0 records)
- `dim_enrollments_staging` (0 records)
- `dim_invoices_staging` (0 records)
- `dim_patient_payments_staging` (0 records)
- `dim_prospects_staging` (0 records)
- `dim_randomizations_staging` (0 records)
- `dim_remittances_staging` (0 records)
- `dim_screenings_staging` (0 records)
- `dim_withdrawals_staging` (0 records)
- And 25 more...

---

## Job Execution Patterns

### Non-Parameterized Jobs

These jobs call a single API endpoint and load all records.

**Example: Patients Job**

```python
def execute_patients_job():
    """
    Job ID: 3
    Endpoint: /api/v1/patients/odata
    Target: dim_patients_staging
    """
    endpoint = "/api/v1/patients/odata"
    target_table = "dim_patients_staging"
    
    # Paginate through all records
    top = 1000
    skip = 0
    total_records = 0
    
    while True:
        url = f"{base_url}{endpoint}?$top={top}&$skip={skip}"
        response = requests.get(url, headers={"X-ApiKey": api_key})
        
        if response.status_code != 200:
            log_error(f"HTTP {response.status_code}: {url}")
            break
        
        data = response.json()
        records = data.get('value', [])
        
        if not records:
            break
        
        # Insert into staging table
        for record in records:
            insert_staging_record(target_table, record, job_id=3)
        
        total_records += len(records)
        skip += top
    
    log_success(f"Loaded {total_records} patients")
```

### Parameterized Jobs

These jobs iterate through parent records and call the API for each parent ID.

**Example: Study Subjects Job**

```python
def execute_study_subjects_job():
    """
    Job ID: 10
    Endpoint: /api/v1/studies/{studyId}/subjects/odata
    Target: dim_subjects_staging
    Requires: studyId from dim_studies_staging
    """
    # Get all study IDs
    study_ids = get_parameter_values(
        source_table="dim_studies_staging",
        source_column="data->>'id'"
    )
    
    total_records = 0
    
    for study_id in study_ids:
        endpoint = f"/api/v1/studies/{study_id}/subjects/odata"
        
        # Paginate through subjects for this study
        subjects = fetch_all_records(endpoint)
        
        # Insert into staging
        for subject in subjects:
            insert_staging_record("dim_subjects_staging", subject, job_id=10)
        
        total_records += len(subjects)
    
    log_success(f"Loaded {total_records} subjects from {len(study_ids)} studies")
```

### Nested Parameterized Jobs

Some jobs require multiple levels of parameters.

**Example: Visit Elements Job**

```python
def execute_visit_elements_job():
    """
    Job ID: 175 (INVALID - needs correction)
    Correct Endpoint: /api/v1/studies/{studyId}/visits/{visitId}/elements/odata
    Target: dim_visit_element_relationships_staging
    Requires: studyId AND visitId
    """
    # Get all study-visit combinations
    query = """
        SELECT DISTINCT 
            s.data->>'id' as study_id,
            v.data->>'id' as visit_id
        FROM dim_studies_staging s
        JOIN dim_visits_staging v ON v.data->'study'->>'id' = s.data->>'id'
    """
    study_visits = execute_query(query)
    
    total_records = 0
    
    for row in study_visits:
        study_id = row['study_id']
        visit_id = row['visit_id']
        endpoint = f"/api/v1/studies/{study_id}/visits/{visit_id}/elements/odata"
        
        elements = fetch_all_records(endpoint)
        
        for element in elements:
            insert_staging_record(
                "dim_visit_element_relationships_staging",
                element,
                job_id=175
            )
        
        total_records += len(elements)
    
    log_success(f"Loaded {total_records} visit elements")
```

---

## Data Loading Scripts

### SQL Scripts Created

The following SQL scripts have been created for ETL job management:

**1. New Categories ETL Jobs** (`/home/ubuntu/sql/etl_new_categories.sql`):
- Creates 10 new ETL jobs for previously not-implemented categories
- Creates corresponding staging tables
- Jobs: Action Unit Completions, Invoices, Prospects, Remittances, Site Payments, Study Types, Study Visit Arms, Visit Elements, Patient Payments

**2. Patient Items ETL Jobs** (`/home/ubuntu/sql/etl_patient_items.sql`):
- Enables 14 patient-related ETL jobs
- Jobs: Patient Allergies, Conditions, Devices, Immunizations, Medications, Procedures, Social History, Family History, Providers, Visit Elements, Visit Stipends

**3. Re-enable Jobs** (`/home/ubuntu/sql/reenable_etl_jobs.sql`):
- Re-enables 9 previously disabled jobs with proven success records
- Jobs: Studies, Elements, Visits, StudyDocuments, Screenings, Providers, Rooms, Schedules, Sponsors

**4. Fix Parameter Configuration** (executed via command line):
- Fixed 6 jobs with missing parameter configuration
- Jobs: StudyActions (27), Study Protocol Versions (142), Study Roles (143), Study Warnings (145), Study Integration Info (146), Subject Patient Visits (160)

### Python ETL Script Template

A reusable Python script for ETL execution:

```python
#!/usr/bin/env python3
"""
TrialSync ETL Job Executor
Executes ETL jobs from dw_etl_jobs configuration
"""

import psycopg2
import requests
import json
from datetime import datetime
import time

# Database connection
DB_CONFIG = {
    'host': 'tl-dev01.trialogic.ai',
    'port': 5432,
    'database': 'trialsync',
    'user': 'trialsync',
    'password': '${PASSWORD}'
}

# API configuration
API_CONFIG = {
    'base_url': 'https://tektonresearch.clinicalconductor.com/CCSWEB',
    'api_key': '9ba73e89-0423-47c1-a50c-b78c7034efea'
}

class ETLExecutor:
    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.cursor = self.conn.cursor()
    
    def get_job_config(self, job_id):
        """Get ETL job configuration"""
        query = """
            SELECT id, name, source_endpoint, target_table,
                   requires_parameters, parameter_name,
                   parameter_source_table, parameter_source_column
            FROM dw_etl_jobs
            WHERE id = %s AND is_active = true
        """
        self.cursor.execute(query, (job_id,))
        return self.cursor.fetchone()
    
    def get_parameter_values(self, source_table, source_column):
        """Get parameter values for parameterized jobs"""
        query = f"SELECT DISTINCT {source_column} FROM {source_table}"
        self.cursor.execute(query)
        return [row[0] for row in self.cursor.fetchall()]
    
    def fetch_api_data(self, endpoint, params=None):
        """Fetch data from Clinical Conductor API"""
        url = f"{API_CONFIG['base_url']}{endpoint}"
        headers = {'X-ApiKey': API_CONFIG['api_key']}
        
        response = requests.get(url, headers=headers, params=params, timeout=60)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            print(f"Endpoint not found: {endpoint}")
            return None
        else:
            response.raise_for_status()
    
    def fetch_all_records(self, endpoint):
        """Fetch all records with pagination"""
        all_records = []
        top = 1000
        skip = 0
        
        while True:
            params = {'$top': top, '$skip': skip}
            data = self.fetch_api_data(endpoint, params)
            
            if not data:
                break
            
            records = data.get('value', data if isinstance(data, list) else [])
            if not records:
                break
            
            all_records.extend(records)
            skip += top
            
            # Rate limiting
            time.sleep(0.1)
        
        return all_records
    
    def insert_staging_record(self, table, data, job_id, run_id):
        """Insert record into staging table"""
        query = f"""
            INSERT INTO {table} (data, source_id, source_instance_id, etl_job_id, etl_run_id, loaded_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        source_id = instance_id  # From source_instance_id in job config
        self.cursor.execute(query, (
            json.dumps(data),
            source_id,
            job_id,
            run_id,
            datetime.now()
        ))
    
    def execute_job(self, job_id):
        """Execute an ETL job"""
        job = self.get_job_config(job_id)
        if not job:
            print(f"Job {job_id} not found or inactive")
            return
        
        job_id, name, endpoint, target_table, requires_params, \
            param_name, param_source_table, param_source_column = job
        
        print(f"Executing job {job_id}: {name}")
        
        # Create run record
        run_id = self.create_run_record(job_id)
        
        try:
            total_records = 0
            
            if requires_params:
                # Parameterized job
                param_values = self.get_parameter_values(
                    param_source_table,
                    param_source_column
                )
                
                for param_value in param_values:
                    param_endpoint = endpoint.replace(f"{{{param_name}}}", str(param_value))
                    records = self.fetch_all_records(param_endpoint)
                    
                    for record in records:
                        self.insert_staging_record(
                            target_table, record, job_id, run_id
                        )
                    
                    total_records += len(records)
                    self.conn.commit()
            else:
                # Non-parameterized job
                records = self.fetch_all_records(endpoint)
                
                for record in records:
                    self.insert_staging_record(
                        target_table, record, job_id, run_id
                    )
                
                total_records = len(records)
                self.conn.commit()
            
            self.complete_run_record(run_id, 'success', total_records)
            print(f"Job {job_id} completed: {total_records} records loaded")
            
        except Exception as e:
            self.conn.rollback()
            self.complete_run_record(run_id, 'failed', 0, str(e))
            print(f"Job {job_id} failed: {e}")
            raise
    
    def create_run_record(self, job_id):
        """Create ETL run record"""
        query = """
            INSERT INTO dw_etl_runs (job_id, run_status, started_at)
            VALUES (%s, 'running', %s)
            RETURNING run_id
        """
        self.cursor.execute(query, (job_id, datetime.now()))
        self.conn.commit()
        return self.cursor.fetchone()[0]
    
    def complete_run_record(self, run_id, status, records, error=None):
        """Complete ETL run record"""
        query = """
            UPDATE dw_etl_runs
            SET run_status = %s,
                records_loaded = %s,
                completed_at = %s,
                error_message = %s
            WHERE run_id = %s
        """
        self.cursor.execute(query, (status, records, datetime.now(), error, run_id))
        
        # Update job last run status
        query2 = """
            UPDATE dw_etl_jobs
            SET last_run_status = %s,
                last_run_at = %s,
                last_run_records = %s
            WHERE id = (SELECT job_id FROM dw_etl_runs WHERE run_id = %s)
        """
        self.cursor.execute(query2, (status, datetime.now(), records, run_id))
        self.conn.commit()
    
    def close(self):
        """Close database connection"""
        self.cursor.close()
        self.conn.close()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python etl_executor.py <job_id>")
        sys.exit(1)
    
    job_id = int(sys.argv[1])
    
    executor = ETLExecutor()
    try:
        executor.execute_job(job_id)
    finally:
        executor.close()
```

**Usage**:
```bash
# Execute a single job
python3 etl_executor.py 3  # Patients job

# Execute multiple jobs
for job_id in 1 2 3 8 9; do
    python3 etl_executor.py $job_id
done
```

---

## Monitoring and Troubleshooting

### ETL Runs Table

All job executions are logged in `dw_etl_runs`:

```sql
CREATE TABLE dw_etl_runs (
    run_id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES dw_etl_jobs(id),
    run_status VARCHAR(50),  -- 'running', 'success', 'failed'
    records_loaded INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    credential_id INTEGER REFERENCES dw_api_credentials(id)
);
```

### Monitoring Queries

**Check recent job executions**:
```sql
SELECT 
    j.id,
    j.name,
    r.run_status,
    r.records_loaded,
    r.started_at,
    r.completed_at,
    EXTRACT(EPOCH FROM (r.completed_at - r.started_at)) as duration_seconds
FROM dw_etl_runs r
JOIN dw_etl_jobs j ON r.job_id = j.id
WHERE r.started_at > NOW() - INTERVAL '24 hours'
ORDER BY r.started_at DESC;
```

**Find failed jobs**:
```sql
SELECT 
    j.id,
    j.name,
    r.run_status,
    r.error_message,
    r.started_at
FROM dw_etl_runs r
JOIN dw_etl_jobs j ON r.job_id = j.id
WHERE r.run_status = 'failed'
ORDER BY r.started_at DESC
LIMIT 20;
```

**Check job success rates**:
```sql
SELECT 
    j.id,
    j.name,
    COUNT(*) as total_runs,
    SUM(CASE WHEN r.run_status = 'success' THEN 1 ELSE 0 END) as successful_runs,
    SUM(CASE WHEN r.run_status = 'failed' THEN 1 ELSE 0 END) as failed_runs,
    ROUND(100.0 * SUM(CASE WHEN r.run_status = 'success' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM dw_etl_jobs j
LEFT JOIN dw_etl_runs r ON j.id = r.job_id
WHERE r.started_at > NOW() - INTERVAL '7 days'
GROUP BY j.id, j.name
ORDER BY success_rate DESC;
```

### Common Issues and Solutions

**Issue: 404 Errors**
- **Cause**: Invalid API endpoint
- **Solution**: Verify endpoint in OpenAPI spec, disable job if endpoint doesn't exist
- **Example**: Jobs #14, #15, #16, #17, #20 have invalid endpoints

**Issue: Missing Parameter Configuration**
- **Cause**: Parameterized job without `parameter_source_table` set
- **Solution**: Update job configuration with correct parameter source
- **Example**: Jobs #27, #142, #143, #145, #146, #160 were fixed

**Issue: Timeout Errors**
- **Cause**: Large dataset or slow API response
- **Solution**: Increase timeout, reduce batch size, add retry logic
- **Example**: Appointments job may timeout with large date ranges

**Issue: Duplicate Records**
- **Cause**: Job re-run without truncating staging table
- **Solution**: Truncate staging table before full refresh, or implement upsert logic
- **Query**: `TRUNCATE TABLE dim_patients_staging;`

**Issue: JSON Parsing Errors**
- **Cause**: Unexpected API response format
- **Solution**: Add error handling, log raw response, validate JSON structure
- **Example**: Some endpoints return arrays instead of OData format

### Monitoring Script

A monitoring script has been deployed:
- **Location**: `/home/rpmadmin/monitor_reenabled_jobs.sh` (on tl-dev01)
- **Purpose**: Check status of re-enabled jobs
- **Schedule**: Runs every 4 hours via Manus scheduled task

---

## Appendix: File Locations

### SQL Scripts
- `/home/ubuntu/sql/etl_new_categories.sql` - New category jobs
- `/home/ubuntu/sql/etl_patient_items.sql` - Patient-related jobs
- `/home/ubuntu/sql/reenable_etl_jobs.sql` - Re-enable jobs

### Data Exports
- `/home/ubuntu/etl_jobs_export.txt` - Full ETL job inventory
- `/home/ubuntu/cc_openapi.json` - Clinical Conductor API spec

### Documentation
- `/home/ubuntu/docs/01_Clinical_Conductor_API_Reference.md` - API documentation
- `/home/ubuntu/docs/02_ETL_Jobs_and_Staging_Tables.md` - This document
- `/home/ubuntu/invalid_endpoints_report.md` - Invalid endpoint analysis
- `/home/ubuntu/disabled_categories_analysis.md` - Disabled job analysis
- `/home/ubuntu/api_response_schemas.md` - API schema documentation

### Monitoring
- `/home/rpmadmin/monitor_reenabled_jobs.sh` - Job monitoring script (on tl-dev01)
- `/home/ubuntu/etl_monitoring_reports/` - Monitoring report output directory

---

**Document End**
