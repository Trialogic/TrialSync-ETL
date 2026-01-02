# TrialSync Codebase and Repository Guide

**Document Version**: 1.0  
**Last Updated**: December 15, 2025  
**Author**: Manus AI  
**Purpose**: Complete reference for TrialSync codebase structure, file locations, and development setup

---

## Table of Contents

1. [Repository Overview](#repository-overview)
2. [Project Structure](#project-structure)
3. [Backend (Node.js/TypeScript)](#backend-nodejstypescript)
4. [Python Services](#python-services)
5. [SQL Scripts and Migrations](#sql-scripts-and-migrations)
6. [Frontend](#frontend)
7. [Development Setup](#development-setup)
8. [Deployment](#deployment)

---

## Repository Overview

**Repository**: `Trialogic/TrialSync`  
**GitHub URL**: `https://github.com/Trialogic/TrialSync`  
**License**: UNLICENSED (Proprietary)  
**Owner**: Trial Logic (https://trialogic.ai)

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Backend** | Node.js + TypeScript + Express.js | Node 22+ |
| **AI Services** | Python + FastAPI | Python 3.12+ |
| **Database** | PostgreSQL | 16 |
| **Frontend** | React + TypeScript + Vite | - |
| **ORM** | Prisma | - |
| **Deployment** | Docker + Docker Compose | Docker 20.10+ |
| **Authentication** | Azure AD (MSAL) | - |

### Architecture

TrialSync uses a hybrid architecture combining Node.js for API services and Python for data processing and AI features.

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│                    Vite + TypeScript + Tailwind              │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP/REST
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                   Backend (Node.js/Express)                  │
│              TypeScript + Prisma ORM + Azure AD              │
└────────────┬──────────────────────────────┬─────────────────┘
             │                              │
             ↓                              ↓
┌────────────────────────┐    ┌───────────────────────────────┐
│  Python Services       │    │    PostgreSQL Database        │
│  FastAPI + AI/ML       │    │    trialsync_dev@localhost   │
└────────────────────────┘    └───────────────────────────────┘
```

---

## Project Structure

```
TrialSync/
├── backend/                    # Node.js/TypeScript backend
│   ├── prisma/                # Prisma ORM schema and migrations
│   ├── src/
│   │   ├── api/               # API route handlers
│   │   │   ├── auth.routes.ts
│   │   │   ├── trials.routes.ts
│   │   │   └── index.ts
│   │   ├── config/            # Configuration files
│   │   │   ├── auth.ts
│   │   │   └── env.ts
│   │   ├── middleware/        # Express middleware
│   │   │   ├── auth.ts
│   │   │   └── error.ts
│   │   ├── services/          # Business logic services
│   │   │   └── user.service.ts
│   │   ├── utils/             # Utility functions
│   │   │   └── logger.ts
│   │   └── index.ts           # Application entry point
│   ├── package.json
│   └── tsconfig.json
│
├── python-services/            # Python AI/data processing
│   ├── src/
│   │   ├── api/               # FastAPI endpoints
│   │   ├── config/            # Python configuration
│   │   ├── models/            # Data models
│   │   ├── services/          # Python services
│   │   └── utils/             # Python utilities
│   ├── requirements.txt
│   └── requirements-dev.txt
│
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── config/            # Frontend config
│   │   │   └── authConfig.ts
│   │   ├── contexts/          # React contexts
│   │   ├── pages/             # Page components
│   │   ├── services/          # API client services
│   │   │   └── dashboardApi.ts
│   │   └── types/             # TypeScript types
│   │       └── dashboard.ts
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── sql/                        # Database scripts
│   ├── dimensional-model/     # Data warehouse schema
│   │   ├── create_all_staging_tables.sql
│   │   ├── create_dimensions.sql
│   │   ├── create_fact_tables.sql
│   │   ├── create_etl_procedures.sql
│   │   ├── create_functions.sql
│   │   ├── create_fresh_dw_schema.sql
│   │   ├── create_visit_element_dimensional_tables.sql
│   │   └── visit_element_etl_procedures.sql
│   └── silver_layer_expansion/ # Silver layer transformations
│       ├── create_new_dimensions.sql
│       ├── create_new_facts.sql
│       ├── create_etl_jsonb_dimensions_v2.sql
│       ├── create_etl_jsonb_facts.sql
│       └── etl_procedures/
│           ├── load_medical_codes_fixed_v2.sql
│           ├── load_patient_engagement_dimension.sql
│           ├── load_subject_status_change_fact.sql
│           └── load_patient_engagement_fact.sql
│
├── docs/                       # Documentation
│   ├── analytics/             # Analytics documentation
│   ├── dimensional-model/     # Data model docs
│   ├── fixes/                 # Bug fix documentation
│   └── silver_layer_expansion/ # Transformation docs
│       ├── load_medical_codes_fixed_v2.sql
│       ├── load_patient_engagement_dimension.sql
│       ├── load_subject_status_change_fact.sql
│       └── load_patient_engagement_fact.sql
│
├── scripts/                    # Utility scripts
│   └── ghl_cleanup/           # GoHighLevel cleanup scripts
│
├── workflows/                  # n8n workflows
│   ├── development/           # Dev workflows
│   │   └── webhook-test-workflow.json
│   └── docs/                  # Workflow documentation
│
├── docker-compose.yml          # Production deployment
├── docker-compose.dev.yml      # Development environment
├── .env.example               # Environment variables template
└── README.md                  # Project documentation
```

---

## Backend (Node.js/TypeScript)

The backend provides RESTful API endpoints for the TrialSync platform.

### Key Files

**Entry Point**: `backend/src/index.ts`
- Initializes Express server
- Sets up middleware
- Registers routes
- Connects to database

**API Routes**: `backend/src/api/`
- `auth.routes.ts` - Authentication endpoints (Azure AD integration)
- `trials.routes.ts` - Clinical trial data endpoints
- `index.ts` - Route aggregation

**Configuration**: `backend/src/config/`
- `auth.ts` - Azure AD/MSAL configuration
- `env.ts` - Environment variable management

**Middleware**: `backend/src/middleware/`
- `auth.ts` - JWT authentication middleware
- `error.ts` - Global error handling

**Services**: `backend/src/services/`
- `user.service.ts` - User management business logic

### Package.json Scripts

```json
{
  "scripts": {
    "dev": "nodemon --exec ts-node src/index.ts",
    "build": "tsc",
    "start": "node dist/index.js",
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage",
    "lint": "eslint src --ext .ts",
    "lint:fix": "eslint src --ext .ts --fix",
    "format": "prettier --write \"src/**/*.ts\"",
    "prisma:generate": "prisma generate",
    "prisma:migrate": "prisma migrate dev",
    "prisma:studio": "prisma studio",
    "prisma:seed": "ts-node prisma/seed.ts"
  }
}
```

### Key Dependencies

```json
{
  "dependencies": {
    "@azure/msal-node": "^3.8.2",
    "express": "^4.x",
    "prisma": "^5.x",
    "@prisma/client": "^5.x",
    "jsonwebtoken": "^9.x",
    "dotenv": "^16.x"
  },
  "devDependencies": {
    "@types/node": "^20.x",
    "@types/express": "^4.x",
    "typescript": "^5.x",
    "ts-node": "^10.x",
    "nodemon": "^3.x",
    "jest": "^29.x",
    "eslint": "^8.x",
    "prettier": "^3.x"
  }
}
```

### Database Access

The backend uses Prisma ORM for database access. Schema is defined in `backend/prisma/schema.prisma`.

**Example Prisma Query**:
```typescript
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

// Get all active studies
const studies = await prisma.dim_studies.findMany({
  where: { is_current: true }
});

// Get study with subjects
const study = await prisma.dim_studies.findUnique({
  where: { study_id: 2388 },
  include: { subjects: true }
});
```

### Authentication

Azure AD authentication using MSAL (Microsoft Authentication Library):

```typescript
// backend/src/config/auth.ts
import { ConfidentialClientApplication } from '@azure/msal-node';

const msalConfig = {
  auth: {
    clientId: process.env.AZURE_AD_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID}`,
    clientSecret: process.env.AZURE_AD_CLIENT_SECRET,
  }
};

const cca = new ConfidentialClientApplication(msalConfig);
```

---

## Python Services

Python services handle data processing, AI/ML features, and ETL operations.

### Key Files

**Entry Point**: `python-services/src/api/main.py`
- FastAPI application
- API endpoint definitions
- CORS configuration

**Services**: `python-services/src/services/`
- Data processing services
- AI/ML model inference
- ETL job execution

**Models**: `python-services/src/models/`
- Pydantic data models
- Database models (SQLAlchemy)

**Configuration**: `python-services/src/config/`
- Environment configuration
- Database connection settings

### Dependencies

**requirements.txt**:
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.4.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.0
requests>=2.31.0
python-dotenv>=1.0.0
```

**requirements-dev.txt**:
```
pytest>=7.4.0
pytest-cov>=4.1.0
black>=23.10.0
flake8>=6.1.0
mypy>=1.6.0
```

### Running Python Services

```bash
cd python-services
pip install -r requirements.txt
uvicorn src.api.main:app --reload --port 8000
```

**API Documentation**: `http://localhost:8000/docs` (Swagger UI)

---

## SQL Scripts and Migrations

All database schema definitions and transformation logic are stored in SQL scripts.

### Dimensional Model Scripts

Located in `sql/dimensional-model/`:

| Script | Purpose | Size |
|--------|---------|------|
| `create_fresh_dw_schema.sql` | Complete data warehouse schema | 8.8 KB |
| `create_all_staging_tables.sql` | All Bronze layer staging tables | 7.6 KB |
| `create_new_staging_tables.sql` | Additional staging tables | 17 KB |
| `create_dimensions.sql` | Silver layer dimension tables | 8.5 KB |
| `create_fact_tables.sql` | Silver layer fact tables | 2.5 KB |
| `create_facts.sql` | Additional fact tables | 4.0 KB |
| `create_etl_procedures.sql` | Bronze → Silver transformations | 8.0 KB |
| `create_functions.sql` | Helper functions | 3.0 KB |
| `create_visit_element_dimensional_tables.sql` | Visit element schema | 16 KB |
| `visit_element_etl_procedures.sql` | Visit element transformations | 16 KB |
| `create_screening_enrollment_views.sql` | Analytics views | 5.2 KB |
| `create_staff_schema.sql` | Staff dimension schema | 2.2 KB |
| `create_batch_progress.sql` | ETL progress tracking | 407 B |

### Silver Layer Expansion Scripts

Located in `sql/silver_layer_expansion/`:

| Script | Purpose | Size |
|--------|---------|------|
| `create_new_dimensions.sql` | Additional dimension tables | 13 KB |
| `create_new_facts.sql` | Additional fact tables | 12 KB |
| `create_etl_jsonb_dimensions_v2.sql` | JSONB dimension transformations | 13 KB |
| `create_etl_jsonb_facts.sql` | JSONB fact transformations | 7.3 KB |

### ETL Procedures

Located in `sql/silver_layer_expansion/etl_procedures/`:

| Procedure | Purpose | Size |
|-----------|---------|------|
| `load_medical_codes_fixed_v2.sql` | Load medical code dimensions | - |
| `load_patient_engagement_dimension.sql` | Load patient engagement dim | - |
| `load_subject_status_change_fact.sql` | Load subject status changes | - |
| `load_patient_engagement_fact.sql` | Load patient engagement facts | - |

### Executing SQL Scripts

**From local machine** (Local Development):
```bash
# Connect to database (using DATABASE_URL from .env)
psql $DATABASE_URL

# Or explicitly:
psql -h localhost -U chrisprader -d trialsync_dev

# Execute script
\i sql/dimensional-model/create_fresh_dw_schema.sql

# Or via command line
psql $DATABASE_URL -f sql/dimensional-model/create_dimensions.sql
# Or explicitly:
psql -h localhost -U chrisprader -d trialsync_dev -f sql/dimensional-model/create_dimensions.sql
```

**Note**: For remote server access (production/staging on tl-dev01), use:
```bash
psql -h tl-dev01.trialogic.ai -U trialsync -d trialsync
```

**From Docker container**:
```bash
# Copy script to container
docker cp sql/dimensional-model/create_dimensions.sql trialsync-db:/tmp/

# Execute in container
docker exec trialsync-db psql -U trialsync -d trialsync -f /tmp/create_dimensions.sql
```

**From remote server**:
```bash
# SSH and execute
ssh rpmadmin@tl-dev01.trialogic.ai
docker exec trialsync-db psql -U trialsync -d trialsync -f /path/to/script.sql
```

---

## Frontend

React-based frontend with TypeScript and Vite.

### Key Files

**Entry Point**: `frontend/src/main.tsx`

**Configuration**:
- `frontend/src/config/authConfig.ts` - Azure AD authentication config
- `frontend/vite.config.ts` - Vite build configuration
- `frontend/tailwind.config.js` - Tailwind CSS configuration

**API Services**:
- `frontend/src/services/dashboardApi.ts` - Dashboard API client

**Types**:
- `frontend/src/types/dashboard.ts` - TypeScript type definitions

### Running Frontend

```bash
cd frontend
npm install
npm run dev
```

**Development Server**: `http://localhost:5173`

### Build for Production

```bash
cd frontend
npm run build
npm run preview  # Preview production build
```

---

## Development Setup

### Prerequisites

- **Docker Engine**: 20.10+
- **Docker Compose**: 2.0+
- **Node.js**: 22+
- **Python**: 3.12+
- **PostgreSQL Client**: 16 (for database access)

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

**Required Variables**:

```env
# Database
DATABASE_URL=postgresql://trialsync:${PASSWORD}@tl-dev01.trialogic.ai:5432/trialsync

# Authentication
JWT_SECRET=your-jwt-secret-here
AZURE_AD_CLIENT_ID=your-azure-ad-client-id
AZURE_AD_TENANT_ID=your-azure-ad-tenant-id
AZURE_AD_CLIENT_SECRET=your-azure-ad-client-secret

# Clinical Conductor API
CC_API_BASE_URL=https://tektonresearch.clinicalconductor.com/CCSWEB
CC_API_KEY=9ba73e89-0423-47c1-a50c-b78c7034efea

# AI Services (Optional)
OPENAI_API_KEY=your-openai-api-key

# Application
NODE_ENV=development
PORT=3000
PYTHON_SERVICE_URL=http://localhost:8000
```

### Local Development (Without Docker)

**1. Start Backend**:
```bash
cd backend
npm install
npm run prisma:generate
npm run dev
```

**2. Start Python Services**:
```bash
cd python-services
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.api.main:app --reload --port 8000
```

**3. Start Frontend**:
```bash
cd frontend
npm install
npm run dev
```

### Development with Docker

**Start all services**:
```bash
docker-compose -f docker-compose.dev.yml up -d
```

**View logs**:
```bash
docker-compose -f docker-compose.dev.yml logs -f
```

**Stop services**:
```bash
docker-compose -f docker-compose.dev.yml down
```

### Database Access

**Using psql**:
```bash
psql -h tl-dev01.trialogic.ai -U trialsync -d trialsync
```

**Using Prisma Studio** (GUI):
```bash
cd backend
npm run prisma:studio
```

**Using Docker**:
```bash
docker exec -it trialsync-db psql -U trialsync -d trialsync
```

### Running Tests

**Backend Tests**:
```bash
cd backend
npm test
npm run test:coverage
```

**Python Tests**:
```bash
cd python-services
pytest
pytest --cov
```

---

## Deployment

### Production Deployment (Docker)

**1. Build and start services**:
```bash
docker-compose up -d --build
```

**2. Check service health**:
```bash
docker-compose ps
docker-compose logs
```

**3. Stop services**:
```bash
docker-compose down
```

### Docker Services

The `docker-compose.yml` defines these services:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `trialsync-app` | Node.js 22 | 3000 | Backend API |
| `trialsync-python` | Python 3.12 | 8000 | AI/data services |
| `trialsync-db` | PostgreSQL 16 | 5432 | Database |
| `trialsync-frontend` | Nginx | 80 | Frontend |

### Current Deployment

**Server**: tl-dev01.trialogic.ai  
**Access**: SSH as `rpmadmin@tl-dev01.trialogic.ai`  
**Database**: `trialsync` on localhost:5432 (inside Docker network)

**Services Running**:
```bash
# Check running containers
docker ps | grep trialsync

# View logs
docker logs trialsync-app
docker logs trialsync-python
docker logs trialsync-db
```

### Database Backups

**Manual Backup**:
```bash
docker exec trialsync-db pg_dump -U trialsync trialsync > backup_$(date +%Y%m%d).sql
```

**Restore from Backup**:
```bash
docker exec -i trialsync-db psql -U trialsync -d trialsync < backup_20251215.sql
```

---

## Appendix: File Locations Reference

### Local Development Files (Sandbox)

| File | Path |
|------|------|
| **ETL Job Export** | `/home/ubuntu/etl_jobs_export.txt` |
| **OpenAPI Spec** | `/home/ubuntu/cc_openapi.json` |
| **Transformation Procedures** | `/home/ubuntu/transformation_procedures.txt` |
| **SQL Scripts** | `/home/ubuntu/sql/` |
| **Documentation** | `/home/ubuntu/docs/` |
| **Monitoring Reports** | `/home/ubuntu/etl_monitoring_reports/` |

### GitHub Repository

| Component | Path |
|-----------|------|
| **Backend Source** | `backend/src/` |
| **Python Services** | `python-services/src/` |
| **Frontend Source** | `frontend/src/` |
| **SQL Scripts** | `sql/dimensional-model/` |
| **Silver Layer Scripts** | `sql/silver_layer_expansion/` |
| **Documentation** | `docs/` |
| **Workflows** | `workflows/` |

### Remote Server (tl-dev01)

| Resource | Location |
|----------|----------|
| **Docker Containers** | `docker ps` |
| **Database** | `docker exec trialsync-db psql -U trialsync -d trialsync` |
| **Application Logs** | `docker logs trialsync-app` |
| **Monitoring Script** | `/home/rpmadmin/monitor_reenabled_jobs.sh` |

### Database Tables

| Layer | Schema | Tables |
|-------|--------|--------|
| **Bronze** | public | `*_staging` (106 tables) |
| **Silver** | public | `dim_*` (10 tables), `fact_*` (5 tables) |
| **Gold** | public | `v_*` (views), `mv_*` (materialized views) |
| **ETL Config** | public | `dw_etl_jobs`, `dw_etl_runs`, `dw_api_credentials` |

---

## Quick Reference Commands

### Git Operations
```bash
# Clone repository
gh repo clone Trialogic/TrialSync

# Pull latest changes
cd TrialSync && git pull

# Create feature branch
git checkout -b feature/new-etl-job

# Commit and push
git add .
git commit -m "Add new ETL job for invoices"
git push origin feature/new-etl-job
```

### Database Operations
```bash
# Connect to database
psql -h tl-dev01.trialogic.ai -U trialsync -d trialsync

# Execute SQL file
psql -h tl-dev01.trialogic.ai -U trialsync -d trialsync -f script.sql

# Backup database
pg_dump -h tl-dev01.trialogic.ai -U trialsync trialsync > backup.sql

# Restore database
psql -h tl-dev01.trialogic.ai -U trialsync -d trialsync < backup.sql
```

### Docker Operations
```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f trialsync-app

# Restart service
docker-compose restart trialsync-app

# Execute command in container
docker exec -it trialsync-app npm run prisma:studio

# Access database
docker exec -it trialsync-db psql -U trialsync -d trialsync
```

### Development Workflow
```bash
# 1. Pull latest code
git pull origin main

# 2. Install dependencies
cd backend && npm install
cd ../python-services && pip install -r requirements.txt

# 3. Run migrations
cd ../backend && npm run prisma:migrate

# 4. Start services
npm run dev  # Backend
# In another terminal:
cd ../python-services && uvicorn src.api.main:app --reload

# 5. Run tests
npm test  # Backend
pytest    # Python
```

---

**Document End**
