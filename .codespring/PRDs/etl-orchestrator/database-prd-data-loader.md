## Feature Overview
Bulk load and upsert JSONB payloads into staging tables with batched writes (~1000 records, configurable via ETL_BATCH_SIZE), source_id-based deduplication, lineage (etl_job_id, etl_run_id), and lightweight validation. Per-batch transactional integrity, retries on transient errors, and full observability (counts, durations, structured logs) are required.

## Data Model & Schema Design
- Applies to all staging tables (stg_*). Each must expose a consistent contract for the Data Loader.
- Core columns: source_id (unique), data (JSONB), lineage (etl_job_id, etl_run_id), timestamps (loaded_at, created_at, updated_at), validation flags, and optional source_updated_at for incremental loads.
- Lineage references etl_jobs and etl_runs for auditability and orchestration linkage.

### Table Structures & Relationships
- All stg_* tables must include:
  - source_id: unique business key for dedupe and ON CONFLICT target
  - data: raw JSONB payload from source system
  - etl_job_id: FK to etl_jobs.id
  - etl_run_id: FK to etl_runs.id
  - loaded_at: time of write to staging
  - created_at/updated_at: audit timestamps
  - is_valid, validation_errors: outcomes of lightweight validation
  - source_updated_at: optional, for incremental change detection
- Relationships:
  - stg_* (etl_job_id) → etl_jobs(id)
  - stg_* (etl_run_id) → etl_runs(id)

### Indexes & Constraints
- stg_*:
  - UNIQUE(source_id)
  - INDEX(etl_run_id, loaded_at)
  - INDEX(etl_job_id)
  - INDEX(source_updated_at) when present
  - GIN INDEX on data for ad hoc filters (if needed for diagnostics)
  - NOT NULL: source_id, data, etl_job_id, etl_run_id, loaded_at, created_at, updated_at, is_valid
- etl_runs:
  - INDEX(etl_job_id, started_at)
  - CHECK(status IN ('pending','running','success','failed','partial'))

## Requirements
- Batch ingest: default 1000 records; override via ETL_BATCH_SIZE.
- Upsert with ON CONFLICT (source_id) DO UPDATE SET data, updated_at, loaded_at, etl_run_id; preserve etl_job_id.
- Deduplication is strictly by source_id.
- Lineage: persist etl_job_id and etl_run_id on every row.
- Validation: required fields present in JSON, basic shape checks; mark is_valid and store validation_errors.
- Per-batch transactionality; on failure, batch rolls back without impacting others; retry transient DB errors.
- Efficient I/O: prefer COPY/execute_values pathways; use connection pooling.
- Observability: per-run and per-batch metrics (rows_inserted, rows_updated, batch_duration_ms); structured logs with job/run IDs.

## Technical Considerations
- Migration for existing 106 stg_* tables:
  - Add missing columns and NOT NULLs (with safe defaults), backfill lineage for historical if available.
  - Resolve duplicates by source_id selecting latest by source_updated_at then loaded_at; build UNIQUE(source_id) CONCURRENTLY.
  - Create required indexes CONCURRENTLY.
- Query optimization: maintain narrow ON CONFLICT target; avoid wide row updates; update only changed rows optionally using hash_digest to reduce writes.
- Timeouts and retry policies tuned for PgBouncer and PostgreSQL 16; idempotent upserts guarded by source_id.

## User Stories
- As a data engineer, I can upsert 5.8M+ JSONB records with batch isolation and lineage for audit.
- As an analyst, I can trust that staging reflects latest source per source_id without duplicates.

## Success Criteria
- Meets acceptance criteria: batch upsert, lineage set, transactional batches with retries, efficient I/O, validation, and metrics.
- p95 batch duration and error rate visible in Prometheus/Grafana.
- Zero duplicate source_id in stg_* after migration and ongoing loads.

