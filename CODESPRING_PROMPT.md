# CodeSpring Prompt: TrialSync API/ETL System

## Project Overview

Build a production-ready ETL (Extract, Transform, Load) system that synchronizes clinical trial data from the Clinical Conductor API into a PostgreSQL data warehouse following a medallion architecture (Bronze → Silver → Gold layers).

---

## Context and Background

**What This System Does**: TrialSync extracts clinical trial data from Clinical Conductor (a clinical trial management system) via REST API, stores raw data in staging tables (Bronze layer), transforms it into a dimensional model (Silver layer), and creates analytics-ready views (Gold layer).

**Current State**: The system has 90 ETL jobs configured, 106 staging tables created, and ~5.8 million records loaded. The data warehouse schema is defined, transformation procedures exist, but the ETL execution engine needs to be built/improved.

**Your Mission**: Build a robust, scalable ETL orchestration system that can execute these jobs reliably, handle errors gracefully, support incremental loads, and provide monitoring/observability.

---

## Repository Information

**GitHub Repository**: `Trialogic/TrialSync-ETL`

**Clone Command**:
```bash
gh repo clone Trialogic/TrialSync-ETL
```

**Repository Structure**:
```
TrialSync-ETL/
├── docs/                          # Complete documentation (5 documents)
│   ├── 00_Master_Handoff_Document.md
│   ├── 01_Clinical_Conductor_API_Reference.md
│   ├── 02_ETL_Jobs_and_Staging_Tables.md
│   ├── 03_Data_Warehouse_Layers.md
│   └── 04_Codebase_and_Repository_Guide.md
├── sql/                           # Database schema and transformations
│   ├── schema/                    # Table definitions
│   ├── transformations/           # Bronze → Silver procedures
│   └── fixes/                     # Bug fixes and corrections
├── src/                           # Source code (to be built)
│   ├── etl/                       # ETL engine
│   ├── api/                       # Clinical Conductor API client
│   ├── db/                        # Database access layer
│   └── config/                    # Configuration management
├── tests/                         # Test suite
├── config/                        # Configuration files
├── .env.example                   # Environment variables template
└── README.md                      # Project documentation
```

---

## Technical Requirements

### 1. Technology Stack

**Required**:
- **Language**: Python 3.12+ (primary) OR Node.js 22+ (alternative)
- **Database**: PostgreSQL 16 with JSONB support
- **API Client**: Requests (Python) or Axios (Node.js)
- **Scheduling**: APScheduler (Python) or node-cron (Node.js)
- **Logging**: Structured logging with log levels
- **Configuration**: Environment variables + YAML config files

**Optional but Recommended**:
- **Monitoring**: Prometheus metrics
- **Alerting**: Email/Slack notifications on failures
- **Testing**: pytest (Python) or Jest (Node.js)
- **Documentation**: Sphinx (Python) or JSDoc (Node.js)

### 2. Core Components to Build

#### A. ETL Orchestrator

**Purpose**: Coordinate execution of ETL jobs based on configuration.

**Requirements**:
- Load job configurations from `dw_etl_jobs` table
- Execute jobs in dependency order (respect parent-child relationships)
- Support parallel execution of independent jobs
- Handle job scheduling (cron-like expressions)
- Implement retry logic with exponential backoff
- Track job execution in `dw_etl_runs` table

**Key Features**:
```python
class ETLOrchestrator:
    def execute_job(self, job_id: int) -> ETLRunResult
    def execute_all_active_jobs(self) -> List[ETLRunResult]
    def execute_jobs_by_category(self, category: str) -> List[ETLRunResult]
    def schedule_job(self, job_id: int, cron_expression: str)
    def get_job_status(self, job_id: int) -> JobStatus
```

#### B. API Client

**Purpose**: Interact with Clinical Conductor API.

**Requirements**:
- Support authentication via X-ApiKey header
- Handle OData query parameters ($top, $skip, $filter, $orderby)
- Implement rate limiting (respect API limits)
- Retry failed requests with exponential backoff
- Parse and validate API responses
- Handle pagination for large result sets

**Key Features**:
```python
class ClinicalConductorClient:
    def get(self, endpoint: str, params: dict = None) -> dict
    def get_odata(self, endpoint: str, filter: str = None, top: int = 1000) -> List[dict]
    def get_paginated(self, endpoint: str, page_size: int = 1000) -> Iterator[dict]
    def get_with_parameters(self, endpoint: str, parameters: dict) -> dict
```

**API Details**:
- Base URL: `https://tektonresearch.clinicalconductor.com/CCSWEB`
- Authentication: Header `X-ApiKey: 9ba73e89-0423-47c1-a50c-b78c7034efea`
- All endpoints documented in `docs/01_Clinical_Conductor_API_Reference.md`

#### C. Data Loader

**Purpose**: Load extracted data into staging tables.

**Requirements**:
- Insert data into JSONB staging tables
- Support upsert operations (INSERT ... ON CONFLICT)
- Handle bulk inserts efficiently (batch processing)
- Track source_id for deduplication
- Record etl_job_id and etl_run_id for lineage
- Validate data before insertion

**Key Features**:
```python
class DataLoader:
    def load_to_staging(self, table_name: str, records: List[dict], job_id: int, run_id: int)
    def upsert_records(self, table_name: str, records: List[dict], key_field: str)
    def bulk_insert(self, table_name: str, records: List[dict], batch_size: int = 1000)
    def truncate_and_reload(self, table_name: str, records: List[dict])
```

#### D. Transformation Engine

**Purpose**: Execute Bronze → Silver layer transformations.

**Requirements**:
- Execute stored procedures from SQL files
- Support parameterized procedure calls
- Handle transaction management
- Log transformation results
- Support incremental vs full refresh

**Key Features**:
```python
class TransformationEngine:
    def execute_procedure(self, procedure_name: str, params: dict = None)
    def load_all_dimensions(self)
    def load_all_facts(self)
    def refresh_materialized_views(self)
```

#### E. Job Executor

**Purpose**: Execute individual ETL jobs.

**Requirements**:
- Support both parameterized and non-parameterized jobs
- Handle parent-child job relationships (e.g., iterate through study IDs)
- Implement incremental load logic (delta detection)
- Track execution metrics (duration, records loaded, errors)
- Support dry-run mode for testing

**Job Execution Flow**:
```
1. Load job configuration from dw_etl_jobs
2. Create run record in dw_etl_runs (status: running)
3. If parameterized:
   a. Query parameter_source_table for parameter values
   b. For each parameter value:
      - Substitute {parameter} in endpoint
      - Call API
      - Load data to staging
4. If non-parameterized:
   - Call API endpoint directly
   - Load data to staging
5. Update run record (status: success/failed, records_loaded, duration)
6. Log results
```

#### F. Monitoring & Observability

**Purpose**: Track system health and job performance.

**Requirements**:
- Expose metrics (jobs executed, success rate, duration, records loaded)
- Log all operations with structured logging
- Send alerts on job failures
- Provide dashboard/API for monitoring
- Track data quality metrics

**Key Metrics**:
- Jobs executed per hour/day
- Success vs failure rate
- Average job duration
- Records loaded per job
- API response times
- Database connection pool usage

### 3. Database Schema

**ETL Configuration Tables** (already exist):

```sql
-- Job configuration
CREATE TABLE dw_etl_jobs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    source_endpoint VARCHAR(500) NOT NULL,
    target_table VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    requires_parameters BOOLEAN DEFAULT FALSE,
    parameter_source_table VARCHAR(255),
    parameter_source_column VARCHAR(255),
    source_instance_id INTEGER,
    last_run_at TIMESTAMP,
    last_run_status VARCHAR(50),
    last_run_records INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Job execution log
CREATE TABLE dw_etl_runs (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES dw_etl_jobs(id),
    run_status VARCHAR(50) NOT NULL,  -- running, success, failed
    records_loaded INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_seconds INTEGER
);

-- API credentials
CREATE TABLE dw_api_credentials (
    id SERIAL PRIMARY KEY,
    instance_name VARCHAR(255) NOT NULL,
    base_url VARCHAR(500) NOT NULL,
    api_key VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);
```

**Staging Tables** (106 tables, all follow this pattern):

```sql
CREATE TABLE dim_example_staging (
    id SERIAL PRIMARY KEY,
    data JSONB NOT NULL,
    source_id VARCHAR(255),
    etl_job_id INTEGER,
    etl_run_id INTEGER,
    loaded_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 4. Configuration Management

**Environment Variables** (.env file):

```env
# Database
DATABASE_HOST=tl-dev01.trialogic.ai
DATABASE_PORT=5432
DATABASE_NAME=trialsync
DATABASE_USER=trialsync
DATABASE_PASSWORD=<provided separately>

# Clinical Conductor API
CC_API_BASE_URL=https://tektonresearch.clinicalconductor.com/CCSWEB
CC_API_KEY=9ba73e89-0423-47c1-a50c-b78c7034efea

# ETL Settings
ETL_BATCH_SIZE=1000
ETL_MAX_RETRIES=3
ETL_RETRY_DELAY_SECONDS=5
ETL_PARALLEL_JOBS=5
ETL_TIMEOUT_SECONDS=300

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/trialsync/etl.log

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
ALERT_EMAIL=admin@trialogic.ai
```

**Job Configuration** (YAML example):

```yaml
# config/jobs.yaml
jobs:
  studies:
    enabled: true
    schedule: "0 2 * * *"  # Daily at 2 AM
    priority: 1
    timeout_seconds: 300
    
  subjects:
    enabled: true
    schedule: "0 3 * * *"  # Daily at 3 AM
    priority: 2
    depends_on: [studies]
    
  patient_visits:
    enabled: true
    schedule: "0 4 * * *"  # Daily at 4 AM
    priority: 3
    depends_on: [subjects]
```

### 5. Error Handling

**Requirements**:
- Catch and log all exceptions
- Distinguish between transient (retry) and permanent (fail) errors
- Record error details in dw_etl_runs table
- Send alerts for critical failures
- Support manual retry of failed jobs

**Error Categories**:
- **API Errors**: 404 (invalid endpoint), 401 (auth), 429 (rate limit), 500 (server error)
- **Database Errors**: Connection timeout, deadlock, constraint violation
- **Data Errors**: Invalid JSON, missing required fields, type mismatch
- **System Errors**: Out of memory, disk full, network timeout

**Retry Strategy**:
```python
def retry_with_backoff(func, max_retries=3, base_delay=5):
    for attempt in range(max_retries):
        try:
            return func()
        except TransientError as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)  # Exponential backoff
            time.sleep(delay)
```

### 6. Testing Requirements

**Unit Tests**:
- Test each component in isolation
- Mock external dependencies (API, database)
- Cover error scenarios
- Aim for >80% code coverage

**Integration Tests**:
- Test API client with real endpoints (or mock server)
- Test database operations with test database
- Test end-to-end job execution

**Test Scenarios**:
- Successful job execution
- API returns 404 (invalid endpoint)
- API returns 429 (rate limit exceeded)
- Database connection failure
- Parameterized job with no parameters
- Duplicate records (upsert logic)
- Large dataset (pagination)

### 7. Documentation Requirements

**Code Documentation**:
- Docstrings for all classes and functions
- Type hints for all function signatures
- Inline comments for complex logic

**User Documentation**:
- README with quick start guide
- Installation instructions
- Configuration guide
- Troubleshooting guide
- API reference

**Operational Documentation**:
- Deployment guide
- Monitoring setup
- Backup and recovery procedures
- Performance tuning guide

---

## Specific Implementation Tasks

### Phase 1: Core ETL Engine (Week 1)

**Tasks**:
1. Set up project structure and dependencies
2. Implement database connection pooling
3. Build API client with authentication and error handling
4. Create data loader with upsert logic
5. Implement basic job executor (non-parameterized jobs)
6. Add structured logging
7. Write unit tests for core components

**Deliverables**:
- Working API client that can fetch data from Clinical Conductor
- Data loader that can insert records into staging tables
- Job executor that can run a single non-parameterized job
- Test suite with >70% coverage

### Phase 2: Job Orchestration (Week 2)

**Tasks**:
1. Implement ETL orchestrator
2. Add support for parameterized jobs
3. Implement job scheduling (cron-like)
4. Add parallel job execution
5. Implement retry logic with exponential backoff
6. Add job dependency management
7. Create CLI for manual job execution

**Deliverables**:
- Orchestrator that can execute all 90 ETL jobs
- Scheduler that runs jobs on defined schedules
- CLI tool: `trialsync-etl run --job-id 1` or `trialsync-etl run --all`

### Phase 3: Monitoring & Observability (Week 3)

**Tasks**:
1. Add Prometheus metrics
2. Implement email/Slack alerting
3. Create monitoring dashboard (Grafana or custom)
4. Add data quality checks
5. Implement job execution history API
6. Create admin UI for job management (optional)

**Deliverables**:
- Metrics endpoint exposing job statistics
- Alert notifications on job failures
- Dashboard showing job execution history

### Phase 4: Optimization & Production Readiness (Week 4)

**Tasks**:
1. Implement incremental load logic (delta detection)
2. Optimize database queries and indexes
3. Add connection pooling and caching
4. Implement graceful shutdown
5. Add health check endpoints
6. Create Docker deployment
7. Write operational documentation

**Deliverables**:
- Production-ready ETL system
- Docker Compose deployment
- Complete documentation
- Performance benchmarks

---

## Known Issues to Address

### 1. Invalid API Endpoints (18 jobs)

**Problem**: Some ETL jobs are configured with endpoints that don't exist in the Clinical Conductor API.

**Jobs to Fix**:
- Job #14 (Screenings) - Endpoint doesn't exist, disable job
- Job #15 (Enrollments) - Endpoint doesn't exist, disable job
- Job #16 (Randomizations) - Endpoint doesn't exist, disable job
- Job #17 (Withdrawals) - Endpoint doesn't exist, disable job
- Job #20 (ConcomitantMedications) - Endpoint doesn't exist, disable job
- Job #23 (Queries) - Use `/monitor-queries` instead of `/queries`
- Job #174 (Study Visit Arms) - Use `/arms` instead of `/visit-arms`
- Job #175 (Visit Elements) - Fix path structure

**Solution**: SQL scripts provided in `sql/fixes/disable_invalid_jobs.sql` and `sql/fixes/correct_endpoints.sql`

### 2. Missing Parameter Configuration (6 jobs)

**Problem**: Parameterized jobs missing `parameter_source_table` and `parameter_source_column`.

**Jobs to Fix**: #27, #142, #143, #145, #146, #160

**Solution**: SQL script provided in `sql/fixes/fix_parameter_config.sql`

### 3. Rate Limiting

**Problem**: Clinical Conductor API may have rate limits (not documented).

**Solution**: Implement rate limiting in API client with configurable delay between requests.

### 4. Large Datasets

**Problem**: Some endpoints return millions of records (e.g., patient visits).

**Solution**: Implement pagination and batch processing. Process in chunks of 1000 records.

---

## Success Criteria

**Functional Requirements**:
- ✅ All 72 valid ETL jobs execute successfully
- ✅ Data loads into staging tables correctly
- ✅ Parameterized jobs iterate through parent records
- ✅ Failed jobs retry automatically
- ✅ Job execution history tracked in database
- ✅ Alerts sent on critical failures

**Non-Functional Requirements**:
- ✅ System processes 1M+ records per day
- ✅ Average job execution time < 5 minutes
- ✅ System uptime > 99%
- ✅ Code coverage > 80%
- ✅ API response time < 2 seconds (p95)
- ✅ Database queries optimized (< 100ms for most queries)

**Documentation**:
- ✅ README with quick start guide
- ✅ API reference documentation
- ✅ Deployment guide
- ✅ Troubleshooting guide

---

## Example Code Structure

### Python Implementation

```python
# src/etl/orchestrator.py
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ETLJob:
    id: int
    name: str
    source_endpoint: str
    target_table: str
    is_active: bool
    requires_parameters: bool
    parameter_source_table: Optional[str]
    parameter_source_column: Optional[str]

@dataclass
class ETLRunResult:
    job_id: int
    run_id: int
    status: str  # success, failed
    records_loaded: int
    duration_seconds: float
    error_message: Optional[str]

class ETLOrchestrator:
    def __init__(self, db_connection, api_client, data_loader):
        self.db = db_connection
        self.api = api_client
        self.loader = data_loader
        
    def execute_job(self, job_id: int) -> ETLRunResult:
        """Execute a single ETL job."""
        job = self._load_job_config(job_id)
        run_id = self._create_run_record(job_id)
        
        try:
            if job.requires_parameters:
                records = self._execute_parameterized_job(job)
            else:
                records = self._execute_simple_job(job)
            
            self.loader.load_to_staging(
                table_name=job.target_table,
                records=records,
                job_id=job_id,
                run_id=run_id
            )
            
            self._update_run_record(run_id, 'success', len(records))
            return ETLRunResult(
                job_id=job_id,
                run_id=run_id,
                status='success',
                records_loaded=len(records),
                duration_seconds=self._get_run_duration(run_id),
                error_message=None
            )
            
        except Exception as e:
            self._update_run_record(run_id, 'failed', 0, str(e))
            raise
    
    def _execute_simple_job(self, job: ETLJob) -> List[dict]:
        """Execute non-parameterized job."""
        return self.api.get_odata(job.source_endpoint)
    
    def _execute_parameterized_job(self, job: ETLJob) -> List[dict]:
        """Execute parameterized job (iterate through parameters)."""
        parameters = self._get_parameters(
            job.parameter_source_table,
            job.parameter_source_column
        )
        
        all_records = []
        for param_value in parameters:
            endpoint = job.source_endpoint.replace(
                f"{{{job.parameter_source_column}}}",
                str(param_value)
            )
            records = self.api.get_odata(endpoint)
            all_records.extend(records)
        
        return all_records

# src/api/client.py
import requests
from typing import List, Dict, Optional
import time

class ClinicalConductorClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({'X-ApiKey': api_key})
    
    def get_odata(self, endpoint: str, filter: Optional[str] = None, 
                  top: int = 1000) -> List[dict]:
        """Fetch data from OData endpoint with pagination."""
        all_records = []
        skip = 0
        
        while True:
            params = {'$top': top, '$skip': skip}
            if filter:
                params['$filter'] = filter
            
            response = self._request('GET', endpoint, params=params)
            data = response.json()
            
            records = data.get('value', [])
            all_records.extend(records)
            
            if len(records) < top:
                break
            
            skip += top
            time.sleep(0.1)  # Rate limiting
        
        return all_records
    
    def _request(self, method: str, endpoint: str, **kwargs):
        """Make HTTP request with retry logic."""
        url = f"{self.base_url}{endpoint}"
        
        for attempt in range(3):
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limit
                    time.sleep(2 ** attempt)
                    continue
                raise
        
        raise Exception(f"Failed after 3 retries: {url}")

# src/db/loader.py
import psycopg2
from psycopg2.extras import execute_values
import json

class DataLoader:
    def __init__(self, db_connection):
        self.conn = db_connection
    
    def load_to_staging(self, table_name: str, records: List[dict],
                       job_id: int, run_id: int):
        """Load records into staging table."""
        if not records:
            return
        
        values = [
            (
                json.dumps(record),
                record.get('id'),
                job_id,
                run_id
            )
            for record in records
        ]
        
        query = f"""
            INSERT INTO {table_name} 
            (data, source_id, etl_job_id, etl_run_id)
            VALUES %s
            ON CONFLICT (source_id) 
            DO UPDATE SET 
                data = EXCLUDED.data,
                updated_at = NOW()
        """
        
        with self.conn.cursor() as cursor:
            execute_values(cursor, query, values)
        
        self.conn.commit()
```

### Node.js Implementation (Alternative)

```typescript
// src/etl/orchestrator.ts
import { Pool } from 'pg';
import { ClinicalConductorClient } from '../api/client';
import { DataLoader } from '../db/loader';

interface ETLJob {
  id: number;
  name: string;
  source_endpoint: string;
  target_table: string;
  is_active: boolean;
  requires_parameters: boolean;
  parameter_source_table?: string;
  parameter_source_column?: string;
}

interface ETLRunResult {
  jobId: number;
  runId: number;
  status: 'success' | 'failed';
  recordsLoaded: number;
  durationSeconds: number;
  errorMessage?: string;
}

export class ETLOrchestrator {
  constructor(
    private db: Pool,
    private api: ClinicalConductorClient,
    private loader: DataLoader
  ) {}

  async executeJob(jobId: number): Promise<ETLRunResult> {
    const job = await this.loadJobConfig(jobId);
    const runId = await this.createRunRecord(jobId);

    try {
      const records = job.requires_parameters
        ? await this.executeParameterizedJob(job)
        : await this.executeSimpleJob(job);

      await this.loader.loadToStaging(
        job.target_table,
        records,
        jobId,
        runId
      );

      await this.updateRunRecord(runId, 'success', records.length);

      return {
        jobId,
        runId,
        status: 'success',
        recordsLoaded: records.length,
        durationSeconds: await this.getRunDuration(runId),
      };
    } catch (error) {
      await this.updateRunRecord(runId, 'failed', 0, error.message);
      throw error;
    }
  }

  private async executeSimpleJob(job: ETLJob): Promise<any[]> {
    return this.api.getOData(job.source_endpoint);
  }

  private async executeParameterizedJob(job: ETLJob): Promise<any[]> {
    const parameters = await this.getParameters(
      job.parameter_source_table!,
      job.parameter_source_column!
    );

    const allRecords: any[] = [];

    for (const paramValue of parameters) {
      const endpoint = job.source_endpoint.replace(
        `{${job.parameter_source_column}}`,
        String(paramValue)
      );

      const records = await this.api.getOData(endpoint);
      allRecords.push(...records);
    }

    return allRecords;
  }
}
```

---

## CLI Usage Examples

```bash
# Execute a single job
trialsync-etl run --job-id 1

# Execute all active jobs
trialsync-etl run --all

# Execute jobs by category
trialsync-etl run --category studies

# Dry run (validate without executing)
trialsync-etl run --job-id 1 --dry-run

# Schedule a job
trialsync-etl schedule --job-id 1 --cron "0 2 * * *"

# View job status
trialsync-etl status --job-id 1

# View execution history
trialsync-etl history --job-id 1 --limit 10

# Retry failed job
trialsync-etl retry --run-id 12345
```

---

## Additional Resources

**Documentation**: All 5 comprehensive documents in `docs/` directory
- Master handoff document with executive summary
- Complete API reference with 72 valid endpoints
- ETL jobs and staging tables documentation
- Data warehouse architecture (Bronze/Silver/Gold)
- Codebase and repository guide

**SQL Scripts**: All database schemas and transformations in `sql/` directory
- Schema definitions for 106 staging tables
- Transformation procedures (Bronze → Silver)
- Bug fixes for invalid endpoints

**Configuration**: Example configurations in `config/` directory
- Environment variables template
- Job scheduling configuration
- Logging configuration

---

## Questions to Answer

As you build this system, consider:

1. **Architecture**: Should this be a monolithic service or microservices? (Recommendation: Start monolithic, can split later)

2. **Scheduling**: Use built-in scheduler or external tool like Airflow? (Recommendation: Built-in for simplicity)

3. **Parallelization**: How many jobs can run concurrently? (Recommendation: 5-10 based on database connection pool)

4. **Incremental Loads**: How to detect changed records? (Recommendation: Use `modifiedDate` field if available)

5. **Error Recovery**: How to handle partial failures? (Recommendation: Transactional per-job, retry failed jobs)

6. **Monitoring**: What metrics matter most? (Recommendation: Success rate, duration, records loaded, API response time)

---

## Success Checklist

Before considering the project complete, verify:

- [ ] All 72 valid ETL jobs execute successfully
- [ ] Parameterized jobs iterate through parent records correctly
- [ ] Failed jobs retry automatically with exponential backoff
- [ ] Job execution history tracked in `dw_etl_runs` table
- [ ] Alerts sent on critical failures (email/Slack)
- [ ] API client handles rate limiting and pagination
- [ ] Data loader supports upsert operations
- [ ] System can process 1M+ records per day
- [ ] Code coverage > 80%
- [ ] Documentation complete (README, API reference, deployment guide)
- [ ] Docker deployment working
- [ ] Health check endpoints implemented
- [ ] Monitoring dashboard showing job statistics

---

## Getting Started

1. **Clone the repository**: `gh repo clone Trialogic/TrialSync-ETL`
2. **Read the documentation**: Start with `docs/00_Master_Handoff_Document.md`
3. **Set up environment**: Copy `.env.example` to `.env` and configure
4. **Install dependencies**: `pip install -r requirements.txt` or `npm install`
5. **Test database connection**: `python src/db/test_connection.py`
6. **Test API client**: `python src/api/test_client.py`
7. **Run a simple job**: `python src/etl/run_job.py --job-id 1`
8. **Build from there**: Follow the phased implementation plan

---

## Contact and Support

**Repository**: https://github.com/Trialogic/TrialSync-ETL  
**Database**: trialsync@tl-dev01.trialogic.ai:5432  
**API**: https://tektonresearch.clinicalconductor.com/CCSWEB  

For questions or clarifications, refer to the comprehensive documentation in the `docs/` directory.

---

**Good luck building! This is a well-documented, well-architected system with clear requirements. Focus on building robust, testable code that handles errors gracefully.**
