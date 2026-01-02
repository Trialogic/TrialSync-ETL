## Feature Overview
Job Executor orchestrates per-job execution (parameterized and non-parameterized), supports incremental loads via watermarks/cursors, and records detailed metrics per run, attempt, and item. It provides a dry-run mode that simulates execution without mutating target tables or advancing cursors, while still emitting metrics and logs.

## Requirements
- Execute jobs with optional parameter iteration (parent-child), recording each item's params, status, and metrics.
- Incremental load strategies: modifiedDate watermark and last_run cursor. Persist and advance cursors only on successful, non-dry-run completion.
- Metrics: records_read, records_written, durations, attempts, page_count. Persist at run, attempt, and item levels.
- Status model: PENDING, RUNNING, SUCCESS, PARTIAL_SUCCESS, FAILED, SKIPPED, CANCELLED. Error categories: API, DB, DATA, SYSTEM, NONE.
- Dry-run flag per run; no writes to target or cursor progression when true.
- Retry visibility: attempts stored with backoff and error details; unique attempt ordering per run.
- Structured logging with job_id/run_id/attempt_id alignment for observability queries.
- Idempotency: deduplicate parameterized items using param_hash; ensure unique cursor rows per (job_id, param_hash).

## User Stories
- As a Data Engineer, I can see per-run/attempt metrics and errors to diagnose failures.
- As an Operator, I can dry-run a job to validate parameters and expected counts without modifying data.
- As an ETL system, I can resume incremental loads using stored cursors per job and parameter set.

## Technical Considerations
### Data Model & Schema
- Jobs (dw_etl_jobs) define capabilities (supports_params, supports_incremental, strategy).
- Runs (dw_etl_runs) capture lifecycle, metrics, and dry-run intent; FK to jobs.
- Attempts (dw_etl_run_attempts) capture retries with ordered attempt_no.
- Items (dw_etl_run_items) represent parameterized units; store params, param_hash, per-item metrics and cursors.
- Incremental Cursors (dw_etl_incremental_cursors) persist per (job, param) cursor state and metadata.
- Run Logs (dw_etl_run_logs) persist structured logs with contextual fields.

### Table Relationships
- dw_etl_runs.job_id -> dw_etl_jobs.job_id (RESTRICT on delete).
- dw_etl_run_attempts.run_id -> dw_etl_runs.run_id.
- dw_etl_run_items.run_id -> dw_etl_runs.run_id.
- dw_etl_incremental_cursors.job_id -> dw_etl_jobs.job_id.
- dw_etl_run_logs.run_id/attempt_id -> runs/attempts.

### Indexes & Constraints
- dw_etl_runs: idx(job_id, started_at desc), idx(status, started_at desc); CHECK status, error_category; UNIQUE run_id.
- dw_etl_run_attempts: UNIQUE(run_id, attempt_no); idx(run_id, ended_at desc).
- dw_etl_run_items: UNIQUE(run_id, item_no); UNIQUE(run_id, param_hash); idx(status); idx(run_id, ended_at desc).
- dw_etl_incremental_cursors: UNIQUE(job_id, param_hash); idx(job_id, cursor_value desc); GIN params (jsonb_path_ops) if needed.
- dw_etl_run_logs: idx(run_id, ts), idx(level, ts), GIN(fields jsonb_path_ops).

### Data Migration Strategy
- If dw_etl_runs exists, add missing columns (dry_run, attempt_count, metrics) as NULLable, backfill duration_ms from timestamps, then consider NOT NULL where safe.
- Create new tables with defaults; backfill incremental cursors from prior operational sources if available.
- Use transactional migrations; avoid locking by adding columns with defaults set post-population.

### Query Optimization
- Use param_hash for equality on params to avoid expensive JSON comparisons.
- Cover last-success cursor lookup with UNIQUE(job_id, param_hash) and idx(job_id, cursor_value desc).
- Paginate run history by (job_id, started_at desc).
- Partial indexes for frequent filters (e.g., status = 'FAILED') if high cardinality.

## Success Criteria
- 100% of runs and attempts recorded with accurate metrics and statuses.
- Dry-run executes without target mutations or cursor advancement; metrics/logs present.
- Incremental cursors advance only on successful, non-dry-run runs; retrievable in O(log n) via indexes.
- Parameterized jobs deduplicate items via param_hash; no duplicate processing within a run.
- Observability: query runs/attempts/logs by job_id/run_id within p95 < 100 ms for recent 30 days.

