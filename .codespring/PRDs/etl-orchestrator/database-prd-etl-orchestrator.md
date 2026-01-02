Feature Overview
Dependency-aware ETL Orchestrator metadata to schedule, parallelize, retry, and audit job executions across Bronze→Silver→Gold layers. Supports cron scheduling, on-demand runs, parameterized jobs, exponential backoff, lineage, and observability.

Requirements
- Represent ETL jobs, DAG dependencies, schedules, locks, runs, and run events.
- Enforce single active lock per concurrency key to prevent overlapping runs.
- Support parameterized and non-parameterized jobs with JSONB parameters and deterministic parameter_fingerprint for idempotency/concurrency.
- Persist run lifecycle (queued→running→success/failed/skipped/cancelled), attempts, timings, records, error classification, and metrics.
- Allow multiple schedules per job; ensure at most one active schedule per job.
- Capture structured events per run for audit and troubleshooting.
- Track notifications emitted on failures (Slack/Email) for auditability.

Data Model & Relationships
- dw_etl_jobs (1) ← dw_etl_schedules (N)
- dw_etl_jobs (parent) → dw_etl_job_dependencies (N:M) → dw_etl_jobs (child)
- dw_etl_jobs (1) ← dw_etl_runs (N) ← dw_etl_run_events (N)
- dw_etl_jobs/dw_etl_runs ← dw_etl_job_locks (N) [transient]
- dw_etl_runs (1) ← dw_etl_alerts (N)
- dw_etl_jobs (1) ← dw_etl_job_tags (N)

Indexes & Constraints
- dw_etl_jobs: UNIQUE(slug). CHECK(priority>=0).
- dw_etl_schedules: FK(job_id) ON DELETE CASCADE; UNIQUE(job_id) WHERE is_active=true to allow a single active schedule; INDEX(job_id, next_run_at).
- dw_etl_job_dependencies: PK(parent_job_id, child_job_id); FK ON DELETE CASCADE; INDEX(child_job_id), INDEX(parent_job_id).
- dw_etl_runs: FK(job_id) ON DELETE RESTRICT; UNIQUE(correlation_id) for idempotency; INDEX(job_id, scheduled_at), INDEX(job_id, started_at DESC), INDEX(status, scheduled_at), INDEX(job_id, status, ended_at), INDEX(parameter_fingerprint).
- dw_etl_run_events: FK(run_id) ON DELETE CASCADE; INDEX(run_id, ts), INDEX(event_type).
- dw_etl_job_locks: FK(job_id) RESTRICT, FK(run_id) RESTRICT; UNIQUE(concurrency_key) WHERE status='active'; INDEX(expires_at).
- dw_etl_alerts: FK(run_id) RESTRICT; INDEX(run_id), INDEX(channel, sent_at).
- dw_etl_job_tags: UNIQUE(job_id, tag).

Data Migration Strategy
- Phase 1: Create tables IF NOT EXISTS; add indexes/constraints concurrently to avoid locks.
- Phase 2: Seed dw_etl_jobs from repository config; set slugs, priorities, retry/backoff defaults; load dependencies and schedules.
- Phase 3: Import historical run logs (if any); compute parameter_fingerprint as stable SHA256 of canonicalized parameters; backfill correlation_id when available.
- Phase 4: Enable partial unique constraints (active schedule, active lock) after data hygiene.

Query Optimization Considerations
- Runnable selection: Use dependencies indexes and dw_etl_runs(job_id,status,ended_at) to retrieve latest success per parent quickly; consider a materialized view of latest successful run per job (not required by schema).
- Scheduling: Query dw_etl_schedules by next_run_at with covering index; ensure minimal JSONB filtering by storing parameter_fingerprint.
- Run history/metrics: Filter by job_id/time range via composite indexes; avoid large text projections by selecting columns explicitly.

User Stories
- As a Data Engineer, I need to run a job on demand with parameters and see its lineage and logs.
- As SRE, I need to detect stuck/overlapping runs and prevent duplicates via locks.
- As BI Lead, I need job success/failure and durations to drive Prometheus/Grafana dashboards.

Technical Considerations
- Status values: queued, running, success, failed, skipped, cancelled.
- Error classification: is_transient_error + error_type to drive retry/backoff.
- Concurrency keys allow cross-job mutual exclusion if identical.

Success Criteria
- 72 jobs execute in dependency order with bounded parallelism; retries/backoff applied; runs logged with lineage; alerts recorded on failures; queries for latest successes and recent failures complete within 100ms on 1M-row dw_etl_runs.

