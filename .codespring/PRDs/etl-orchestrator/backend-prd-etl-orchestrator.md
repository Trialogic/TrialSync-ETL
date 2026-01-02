# ETL Orchestrator

## Feature Overview
Dependency-aware orchestration of ETL jobs with bounded parallel execution, cron-based scheduling, retries with exponential backoff, structured run logging, and alerting. Supports parameterized and non-parameterized jobs, on-demand execution, dry-run mode, and Prometheus metrics for observability in a Medallion (Bronze→Silver→Gold) pipeline.

## Requirements
- Dependency management
  - Load job graph from dw_etl_jobs; validate acyclic DAG and existence of dependencies.
  - Execute in topological order; allow parallel execution of independent jobs bounded by ETL_PARALLEL_JOBS.
  - If an upstream job fails, mark downstream jobs as skipped for that window/run.

- Scheduling and execution
  - Cron-like schedules (tz-aware) per job; support on-demand triggers via API/CLI.
  - Prevent overlapping runs of the same job (per-job concurrency = 1 unless overridden by job.concurrency_limit).
  - Parameterized jobs fan-out into child runs; respect a per-job fan-out limit and global ETL_PARALLEL_JOBS.
  - Dry-run mode: execute validations and planning without mutating target tables; log intended actions.

- Retries and error classification
  - Transient errors retried with exponential backoff + jitter; permanent errors fail fast.
  - Default classification: transient = HTTP 5xx/429/408, connection timeouts/resets, deadlocks; permanent = 4xx (excl. 408/429), schema/validation errors.
  - Retry policy per job: max_retries, initial_delay_sec, backoff_multiplier, max_delay_sec.

- Run logging and lineage
  - Persist each run in dw_etl_runs with: run_id (UUID), job_id, status [queued|running|retrying|success|failed|skipped|canceled], attempt, scheduled_for, started_at, finished_at, duration_ms, records_loaded, error_type, error_code, error_message, correlation_id, params (JSONB), metrics (JSONB), idempotency_key, parent_run_id.
  - Generate and propagate correlation_id across logs (structlog/pino) and runs.
  - Idempotency: POST triggers accept idempotency_key; duplicate keys must not create duplicate runs.

- Metrics and alerting
  - Prometheus: etl_jobs_total, etl_job_duration_seconds (histogram), etl_job_success_total, etl_job_failure_total, etl_active_runs, etl_queue_depth, etl_retries_total, etl_records_loaded_total.
  - Alerts: send Slack and email on permanent failures and when retries exhausted; include job_id, run_id, attempts, error summary, and deep link to run.

- Security
  - All APIs require Bearer token (service role etl_admin for mutation; etl_reader for read-only).
  - Validate inputs; rate-limit mutation endpoints; audit log all admin actions.

## API Endpoints (Hono/Next.js)
- GET /etl/jobs
  - Query: enabled, stage, search. 200: [{job_id, name, enabled, schedule_cron, dependencies, priority}]
- GET /etl/jobs/:job_id
  - 200: full job config including retry policy, concurrency_limit, params_template, owner_email.
- POST /etl/jobs/:job_id/run
  - Auth: etl_admin. Body: {params?: object|object[], dry_run?: boolean, idempotency_key?: string, priority_override?: number}
  - 202: {run_id(s), status: "queued"}
- POST /etl/scheduler/pause | /etl/scheduler/resume
  - Auth: etl_admin. 200: {state}
- GET /etl/runs
  - Query: job_id, status, since, until, page, limit. 200: paged runs.
- GET /etl/runs/:run_id
  - 200: run detail with logs pointer and metrics.
- GET /metrics
  - Prometheus plaintext.

## Data Model Constraints (PostgreSQL 16)
- dw_etl_jobs
  - job_id TEXT PK; enabled BOOLEAN; schedule_cron TEXT NULL; dependencies TEXT[]; priority INT DEFAULT 0; retry_policy JSONB; concurrency_limit INT DEFAULT 1; timeout_sec INT; params_template JSONB; stage TEXT CHECK IN ('bronze','silver','gold').
  - Validate cron syntax; all dependencies must exist; reject cycles (enforced at orchestrator load).
- dw_etl_runs
  - run_id UUID PK; job_id FK; UNIQUE(job_id, scheduled_for, idempotency_key) WHERE idempotency_key IS NOT NULL.
  - INDEX on (job_id, started_at desc), (status), (scheduled_for).

## User Stories
- As a data engineer, I can trigger a job with parameters and view run status and logs to validate a backfill.
- As an SRE, I can pause/resume scheduling during maintenance and see active runs and queue depth.
- As Clinical Ops leadership, I receive alerts when critical Gold jobs fail after retries.

## Technical Considerations
- Time zone for scheduling: default UTC with per-job override.
- Misfire handling: coalesce missed schedules; misfire_grace_time configurable per job.
- Timeout: enforce per job; mark as failed with error_type=timeout.
- Parameterized fan-out: cap concurrent children via job.concurrency_limit; aggregate child metrics into parent run.
- Dry-run must not write to target tables; still log run with status=success_dryrun (mapped to success with dry_run=true flag).

## Success Criteria
- Executes 72 jobs in correct dependency order with configurable parallelism (ETL_PARALLEL_JOBS).
- Retries transient failures with exponential backoff; marks permanent failures without retry.
- Honors cron schedules, supports on-demand API/CLI, and prevents overlapping runs.
- Records complete lineage in dw_etl_runs including timings, records, errors, and correlation IDs.
- Exposes Prometheus metrics and sends Slack/email alerts on failures.
- Supports parameterized and non-parameterized jobs, including dry-run behavior.

