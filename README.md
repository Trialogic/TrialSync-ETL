# TrialSync ETL System

ETL system for synchronizing clinical trial data from Clinical Conductor API to PostgreSQL data warehouse.

---

## 🎯 Project Overview

TrialSync ETL is a production-ready data pipeline that extracts clinical trial data from the Clinical Conductor API, transforms it through a medallion architecture (Bronze → Silver → Gold), and loads it into a PostgreSQL data warehouse for analytics and reporting.

### Key Features

- **90 ETL Jobs** configured to extract data from Clinical Conductor
- **106 Staging Tables** (Bronze layer) storing raw API responses
- **15 Dimensional Tables** (Silver layer) with Type 2 SCD
- **Parameterized Jobs** supporting parent-child relationships
- **Automatic Retry** with exponential backoff
- **Monitoring & Alerting** for job execution
- **~5.8M Records** processed across all tables

---

## 📚 Documentation

Complete documentation is available in the `docs/` directory:

| Document | Description |
|----------|-------------|
| [Master Handoff Document](docs/00_Master_Handoff_Document.md) | Executive summary and navigation guide |
| [API Reference](docs/01_Clinical_Conductor_API_Reference.md) | Complete Clinical Conductor API documentation |
| [ETL Jobs & Staging](docs/02_ETL_Jobs_and_Staging_Tables.md) | ETL job configurations and Bronze layer |
| [Data Warehouse Layers](docs/03_Data_Warehouse_Layers.md) | Bronze/Silver/Gold architecture |
| [Codebase Guide](docs/04_Codebase_and_Repository_Guide.md) | Repository structure and development setup |

**Start here**: Read [CODESPRING_PROMPT.md](CODESPRING_PROMPT.md) for detailed implementation requirements.

---

## 🏗️ Architecture

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
└────────────────────────────┬────────────────────────────────────┘
                             │ Transformation Procedures
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                  SILVER LAYER (Dimensional)                      │
│  • Normalized dimensional model                                  │
│  • Type 2 Slowly Changing Dimensions                             │
│  • 10 dimension + 5 fact tables                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ Aggregation & Analytics
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    GOLD LAYER (Analytics)                        │
│  • Pre-aggregated metrics                                        │
│  • Business-specific views                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** or **Node.js 22+**
- **PostgreSQL 16**
- **Docker** (optional, for containerized deployment)

### Installation

```bash
# Clone the repository
git clone https://github.com/Trialogic/TrialSync-ETL.git
cd TrialSync-ETL

# Copy environment variables
cp .env.example .env
# Edit .env with your credentials

# Install dependencies (Python)
pip install -r requirements.txt

# Or install dependencies (Node.js)
npm install
```

### Configuration

Edit `.env` file with your credentials:

```env
# Database
DATABASE_HOST=tl-dev01.trialogic.ai
DATABASE_PORT=5432
DATABASE_NAME=trialsync
DATABASE_USER=trialsync
DATABASE_PASSWORD=<your-password>

# Clinical Conductor API
CC_API_BASE_URL=https://tektonresearch.clinicalconductor.com/CCSWEB
CC_API_KEY=9ba73e89-0423-47c1-a50c-b78c7034efea
```

### Running ETL Jobs

```bash
# Execute a single job
python src/etl/run_job.py --job-id 1

# Execute all active jobs
python src/etl/run_all.py

# Schedule jobs
python src/etl/scheduler.py
```

---

## 📁 Repository Structure

```
TrialSync-ETL/
├── docs/                          # Complete documentation
│   ├── 00_Master_Handoff_Document.md
│   ├── 01_Clinical_Conductor_API_Reference.md
│   ├── 02_ETL_Jobs_and_Staging_Tables.md
│   ├── 03_Data_Warehouse_Layers.md
│   └── 04_Codebase_and_Repository_Guide.md
│
├── sql/                           # Database scripts
│   ├── schema/                    # Table definitions
│   ├── transformations/           # Bronze → Silver procedures
│   │   └── transformation_procedures.txt
│   └── fixes/                     # Bug fixes
│       ├── etl_new_categories.sql
│       ├── etl_patient_items.sql
│       └── reenable_etl_jobs.sql
│
├── src/                           # Source code (to be implemented)
│   ├── etl/                       # ETL engine
│   ├── api/                       # Clinical Conductor API client
│   ├── db/                        # Database access layer
│   └── config/                    # Configuration management
│
├── tests/                         # Test suite
├── config/                        # Configuration files
├── cc_openapi.json                # Clinical Conductor API spec
├── etl_jobs_export.txt            # All 90 ETL job configurations
├── CODESPRING_PROMPT.md           # Detailed implementation guide
├── .env.example                   # Environment variables template
└── README.md                      # This file
```

---

## 🔧 Development

### Database Setup

```bash
# Connect to database
psql -h tl-dev01.trialogic.ai -U trialsync -d trialsync

# View ETL jobs
SELECT id, name, source_endpoint, is_active, last_run_status
FROM dw_etl_jobs
ORDER BY id;

# View staging data
SELECT COUNT(*) FROM dim_studies_staging;
```

### Running Tests

```bash
# Python
pytest tests/

# Node.js
npm test
```

### Code Quality

```bash
# Python
black src/
flake8 src/
mypy src/

# Node.js
npm run lint
npm run format
```

---

## 📊 System Status

### Current Statistics

| Metric | Value |
|--------|-------|
| **Total ETL Jobs** | 90 |
| **Active Jobs** | 76 |
| **Valid API Endpoints** | 72 |
| **Invalid Endpoints** | 18 (documented in docs) |
| **Staging Tables** | 106 |
| **Total Records** | ~5.8M |
| **Largest Table** | dim_patient_visits_staging (2.3M records) |

### Known Issues

**18 Invalid API Endpoints** - Some jobs configured with non-existent endpoints:
- 5 jobs need to be disabled (endpoints don't exist)
- 3 jobs need endpoint corrections (wrong paths)
- SQL fix scripts provided in `sql/fixes/`

See [API Reference](docs/01_Clinical_Conductor_API_Reference.md) for complete list.

---

## 🎯 Implementation Roadmap

### Phase 1: Core ETL Engine (Week 1)
- [ ] Set up project structure
- [ ] Implement API client
- [ ] Create data loader
- [ ] Build job executor
- [ ] Add logging

### Phase 2: Job Orchestration (Week 2)
- [ ] Implement orchestrator
- [ ] Add parameterized job support
- [ ] Implement scheduling
- [ ] Add retry logic
- [ ] Create CLI

### Phase 3: Monitoring (Week 3)
- [ ] Add metrics
- [ ] Implement alerting
- [ ] Create dashboard
- [ ] Add data quality checks

### Phase 4: Production Ready (Week 4)
- [ ] Implement incremental loads
- [ ] Optimize performance
- [ ] Add Docker deployment
- [ ] Complete documentation

---

## 🔍 Key Concepts

### Medallion Architecture

- **Bronze Layer**: Raw data from API stored in JSONB format (106 staging tables)
- **Silver Layer**: Normalized dimensional model with Type 2 SCD (10 dims + 5 facts)
- **Gold Layer**: Pre-aggregated metrics and business views

### ETL Job Types

**Non-Parameterized Jobs**: Call API endpoint directly
```
GET /api/v1/studies/odata
→ Load all studies into dim_studies_staging
```

**Parameterized Jobs**: Iterate through parent records
```
For each study_id in dim_studies_staging:
  GET /api/v1/studies/{study_id}/visits/odata
  → Load visits for that study
```

### Type 2 Slowly Changing Dimensions

Track historical changes with effective dates:
- `effective_start_date`: When this version became active
- `effective_end_date`: When this version was superseded
- `is_current`: TRUE for current version, FALSE for historical

---

## 📖 API Reference

**Base URL**: `https://tektonresearch.clinicalconductor.com/CCSWEB`  
**Authentication**: Header `X-ApiKey: 9ba73e89-0423-47c1-a50c-b78c7034efea`

**Example Request**:
```bash
curl -H "X-ApiKey: 9ba73e89-0423-47c1-a50c-b78c7034efea" \
  "https://tektonresearch.clinicalconductor.com/CCSWEB/api/v1/studies/odata?\$top=10"
```

**OpenAPI Specification**: See `cc_openapi.json`

**Complete Documentation**: See [API Reference](docs/01_Clinical_Conductor_API_Reference.md)

---

## 🐛 Troubleshooting

### Job Fails with 404 Error

**Cause**: Invalid API endpoint

**Solution**: Check `docs/01_Clinical_Conductor_API_Reference.md` for list of invalid endpoints. Either disable the job or correct the endpoint using SQL scripts in `sql/fixes/`.

### Staging Table Empty After Job Runs

**Possible Causes**:
1. Invalid endpoint (returns 404)
2. No data in source system
3. Parameterized job with no parent records

**Diagnosis**:
```sql
-- Check job status
SELECT id, name, last_run_status, last_run_records, last_run_at
FROM dw_etl_jobs
WHERE target_table = 'dim_example_staging';

-- Check run logs
SELECT run_status, records_loaded, error_message, started_at
FROM dw_etl_runs
WHERE job_id = <job_id>
ORDER BY started_at DESC
LIMIT 10;
```

### Database Connection Issues

```bash
# Test connection
psql -h tl-dev01.trialogic.ai -U trialsync -d trialsync -c "SELECT 1;"

# Check if server is accessible
ping tl-dev01.trialogic.ai
```

---

## 📝 Contributing

### Code Style

- **Python**: Follow PEP 8, use Black for formatting
- **Node.js**: Follow Airbnb style guide, use Prettier
- **SQL**: Use uppercase keywords, snake_case for identifiers
- **Documentation**: Use Markdown, keep lines under 100 characters

### Commit Messages

```
feat: Add support for incremental loads
fix: Correct endpoint path for Queries job
docs: Update API reference with new endpoints
test: Add unit tests for API client
```

### Pull Request Process

1. Create feature branch from `main`
2. Write tests for new features
3. Update documentation
4. Run linters and tests
5. Submit PR with clear description

---

## 📄 License

UNLICENSED - Proprietary software of Trial Logic

---

## 👥 Authors

**Trial Logic** - https://trialogic.ai

---

## 🆘 Support

For questions or issues:

1. Check the [documentation](docs/)
2. Review [CODESPRING_PROMPT.md](CODESPRING_PROMPT.md)
3. Search existing issues
4. Create new issue with details

---

## 🔗 Related Projects

- **TrialSync**: Main clinical trial synchronization platform
- **TrialSync Dashboard**: Analytics and reporting UI

---

## 📚 Additional Resources

- [Clinical Conductor API Documentation](https://tektonresearch.clinicalconductor.com/CCSWEB/api/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/16/)
- [Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture)
- [Type 2 Slowly Changing Dimensions](https://en.wikipedia.org/wiki/Slowly_changing_dimension)

---

**Ready to build? Start with [CODESPRING_PROMPT.md](CODESPRING_PROMPT.md) for detailed implementation requirements!**
