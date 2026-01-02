Feature Overview
Provide end-to-end monitoring and observability for the TrialSync ETL/orchestration platform: metrics (Prometheus), structured logging, alerting (Slack/Email), data quality (DQ) checks, health/readiness, and job/run history APIs for dashboarding. Scope covers both Node API/orchestrator and Python ETL workers, with PII-safe, secure, and configurable behavior.

Requirements
- Metrics (Prometheus, /metrics on API and workers)
  - Counters
    - trialsync_jobs_total{job_id, status} (success|failed|skipped)
    - trialsync_job_failures_total{job_id, error_category} (API|DB|Data|System)
    - trialsync_dq_schema_drift_total{job_id, table}
    - trialsync_api_requests_total{route, method, status_code}
    - trialsync_records_loaded_total{job_id, table}
  - Histograms
    - trialsync_job_duration_seconds{job_id, status}
    - trialsync_api_request_duration_seconds{route, method}
  - Gauges/Infos
    - trialsync_db_pool_in_use{component}
    - trialsync_db_pool_size{component}
    - trialsync_db_pool_waiters{component}
    - trialsync_uptime_seconds{service}
    - trialsync_build_info{service, version, git_sha}
  - Metric labels must avoid high cardinality (no run_id). Buckets and label sets are fixed and documented.
- Structured Logging (JSON to stdout)
  - Required fields: ts, level, msg, service, env, correlation_id, job_id, run_id, attempt, phase (extract|transform|load|dq), dataset/table, duration_ms, records_loaded, error_category, error_code, http_status (if applicable).
  - Correlation/trace: correlation_id must be propagated across API ↔ ETL; job_id/run_id present on all job lifecycle logs.
  - Redaction: secrets and PII must be masked; never log raw row values. Allowlist-only logging of field names; truncate error messages to 2KB.
- Alerts (Alertmanager → Slack/email)
  - Configurable via env/YAML:
    - retry_alert_threshold (e.g., N consecutive retries), job_failure_alert_threshold (consecutive failures/window), api_latency_p95_ms, db_pool_saturation_pct, dq_null_rate_threshold, dq_row_delta_pct_threshold.
  - Rules:
    - JobFailed, RetryExhausted, ConsecutiveFailures, APIHighLatencyP95, DBPoolSaturation, NoRecentRuns (per job), DQNullRateSpike, SchemaDriftDetected.
- Data Quality Checks (executed per job/table stage)
  - Row count delta vs previous successful run; flag when abs(delta_pct) > threshold.
  - Null-rate per configured key columns; flag when current - baseline > threshold or exceeds absolute threshold.
  - Schema drift: detect new/missing columns, type changes vs expected schema; record differences.
  - Emit metrics (trialsync_dq_*) and write findings to run record. Alerts on warn/fail per config.
- Health/Readiness
  - /healthz: liveness true when process running.
  - /readyz: checks DB connectivity, scheduler status, outbound network; returns component statuses.
- Job/Run History API (Hono, JSON)
  - Auth: JWT (HS/RS) with scope obs.read required; rate limit 60 rps/token.
  - GET /v1/obs/jobs?status=&q=&page=&page_size= (page_size ≤ 500)
    - Returns: job_id, last_run_at, last_run_status, success_rate_7d, avg_duration_ms_7d, records_loaded_24h.
  - GET /v1/obs/jobs/{job_id}/runs?from=&to=&status=&page=&page_size=
    - Returns run summaries for window (max 90 days).
  - GET /v1/obs/runs/{run_id}
    - Returns: run_id (UUID), job_id, scheduled_at, start_at, end_at, duration_ms, status (success|failed|running|queued|skipped), attempt_count, retries_exhausted, error_category, error_message (truncated), records_extracted, records_loaded, dq_status (pass|warn|fail), dq_findings[] {type, table, column?, metric, value, threshold, severity}.
- Configuration
  - OBS_METRICS_ENABLED, OBS_ALERTS_ENABLED, OBS_DQ_ENABLED
  - ALERT_SLACK_WEBHOOK, ALERT_EMAILS
  - Threshold keys listed above; defaults documented; override via env/YAML.

User Stories
- As Clinical Ops, I need alerts when a job fails repeatedly so we can intervene before data freshness degrades.
- As BI, I need a dashboard of job success rate, durations, and records loaded to trust data timeliness.
- As Data Engineering, I need DQ metrics and findings to quickly diagnose null spikes and schema drift.

Technical Considerations
- PII safety: APIs and logs return only metadata; no PHI/PII values.
- Performance: /metrics and /healthz p95 < 200 ms; history queries p95 < 500 ms with indexed job_id,start_at.
- DB pool metrics must reflect asyncpg/psycopg pools and/or PgBouncer exposure.
- Label cardinality guardrails; reject dynamic label values beyond documented sets.
- Versioning: include trialsync_build_info in all services for release traceability.

Success Criteria
- All acceptance criteria met with metrics visible in Prometheus and dashboards in Grafana.
- Alerts delivered to Slack/email per configured thresholds with <1 min detection-to-notification.
- History API returns accurate data for last 90 days and supports Grafana paneling.
- Logs are structured, correlated, PII-safe, and categorize errors consistently.

