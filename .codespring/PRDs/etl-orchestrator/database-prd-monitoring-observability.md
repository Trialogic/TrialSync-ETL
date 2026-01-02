## Feature Overview
Provide end‑to‑end observability for TrialSync ETL orchestration: structured logs with correlation, job/run history, data quality (DQ) results, alerting (Slack/Email), and persisted operational metrics. Prometheus/Grafana cover real‑time, while the database stores audit-grade history, summaries, and alert state for APIs and dashboards.

## Requirements
- Metrics (persisted and exposed via Prometheus): jobs executed, success/failure rate, durations, records loaded, API latency (p95), DB pool usage; uptime/version per service.
- Structured logging: JSON fields with correlation IDs (job_id, run_id, task_run_id, request_id), error categories (API/DB/Data/System), and PII-safe redaction.
- Alerts: configurable rules (env/YAML) for job failures and repeated retries, DQ rule violations; delivery via Slack/Email; deduplication and resolution tracking.
- Data Quality: checks for row delta, null-rate spikes, schema drift; store definitions and results; emit metrics and alerts.
- History API: time-range queries for job/run/task history, DQ results, and alert events to power Grafana/custom UI.
- Health/Readiness: service heartbeats with version, status, and uptime.

## Data Model & Schema Design
- Namespace: observability schema (logical) holding audit-grade entities. Core entities: etl_jobs (reference), job_runs, run_attempts, task_runs, dq_check_definitions/results, alert_channels/rules/events, metric_snapshots, service_heartbeats, log_events, alert_rule_channels (mapping).
- Run-centric model: every log/DQ/alert links to a run when applicable for correlation and drill‑down.

## Table Relationships
- etl_jobs → job_runs (1:N); job_runs → task_runs (1:N); job_runs → run_attempts (1:N).
- dq_check_definitions → dq_check_results (1:N). Optional linkage of dq_check_results and alert_rules to job context.
- alert_rules → alert_rule_channels (1:N) and alert_events (1:N); alert_events may reference job_runs and dq_check_results.
- log_events optionally references job_runs and task_runs.

## Indexes & Constraints
- Primary keys: all tables use UUID PKs; uniqueness on run_id, (run_id, attempt_no) in run_attempts.
- Foreign keys: enforce relationships listed above; nullable where context is optional (e.g., system alerts).
- Time-series indexes: job_runs(job_id, scheduled_at DESC), job_runs(status, finished_at DESC); task_runs(run_id), task_runs(status); dq_check_results(check_id, created_at DESC); alert_events(status, fired_at DESC), alert_events(dedupe_key);
- JSONB GIN: metric_snapshots(labels), log_events(context), dq_check_results(details).
- Partial indexes: job_runs where status='failed'; log_events where level='ERROR'; dq_check_results where status IN ('warn','fail').
- Check constraints (logical enums): status ∈ {queued,running,success,failed,cancelled}; error_category ∈ {API,DB,Data,System}; value_type ∈ {counter,gauge,histogram}; DQ status ∈ {pass,warn,fail}.

## Data Migration Strategy
- Create new observability tables without impacting existing ETL schemas.
- Backfill etl_jobs from current job registry/configs.
- Optional backfill of recent job_runs and DQ results from existing logs/staging metadata if available; otherwise start forward‑fill.
- Initialize baseline alert_channels and alert_rules from env/YAML; validate references.
- No bulk import of high‑cardinality logs; only audit‑level events should be migrated.

## Query Optimization Considerations
- Partition high‑volume tables by time: log_events (daily/weekly), metric_snapshots (daily), job_runs (monthly), dq_check_results (monthly). Use BRIN on time columns for large partitions.
- Precompute materialized summaries for dashboards: daily job success rate, p95 durations, records loaded by job, DQ failure counts.
- Keep JSONB selective; index frequently filtered keys via GIN and promote hot keys to columns when necessary.
- Limit log payload size; store large payloads in context JSONB with redaction flags.
- Use covering indexes for History API: filter by time range, job_id, status; avoid full scans.

## User Stories
- As a Data Engineer, I can filter failed runs in the last 24h with error category to triage quickly.
- As an Analyst, I can view DQ failures and drill into the related job run and table/column.
- As an SRE, I receive a Slack alert when a job exceeds N retries within 30 minutes and can see deduped alert state.
- As a Platform Lead, I can report weekly success rates, average duration, and records loaded per job.

## Technical Considerations
- All timestamps UTC; redact secrets/PII before insert; store pii_safe/redacted flags.
- Configuration-driven toggles for metrics/alerts/DQ checks via env/YAML persisted in definitions/rules.
- Prometheus remains source for real‑time; DB persists aggregated snapshots and run-scoped metrics for auditability.
- Ensure idempotent writes for runs/alerts using dedupe_key and unique constraints.

## Success Criteria
- Stored history for all runs/tasks with correlation IDs and metrics; DQ results persisted and queryable.
- Alerts configurable and delivered; deduped events with resolution tracking.
- Health/uptime/version captured per service instance.
- History API can power Grafana/custom dashboards with sub‑second filters on recent data.
- Logs are PII-safe with secrets redacted; failure triage by category is possible.

