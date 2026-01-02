# Monitoring & Observability

## Feature Overview
A unified monitoring UI to observe ETL job health, performance, and data quality across the TrialSync platform. Provides real-time metrics, job/run history, structured log visibility with correlation IDs, alert visibility, and system health with uptime/version. Designed for leadership visibility and engineering triage while ensuring PII-safe, redacted outputs.

## Requirements

- Navigation/Layout
  - Route: /monitoring with tabs: Overview, Jobs, Data Quality, Alerts, Health.
  - Time range selector (last 1h, 6h, 24h, 7d, custom absolute) persistent across tabs.
  - Filters: job name (multi-select), status (success, failed, running, queued, retried, skipped), error category (API/DB/Data/System).
  - Local/UTC time toggle.

- Overview (metrics + trends)
  - KPI cards: jobs executed, success rate, avg/median duration, records loaded, API latency p95, DB pool usage %.
  - Trend charts (time series) for above metrics; show tooltips with timestamp, value, job where applicable.
  - Prometheus connectivity banner if metrics unavailable; degrade gracefully with cached/summary data.

- Jobs & Run History
  - Jobs table: columns job_name, last_run_status, last_run_at, success_rate (time range), avg_duration, last_records_loaded; link to runs.
  - Runs table (filterable): run_id, job_name, started_at, ended_at, duration, status, retries, records_loaded, error_category; actions: View details, Copy run_id, Export CSV (current filtered set).
  - Status pills with color mapping: success (green), failed (red), running (blue), queued (gray), retried (amber), skipped (slate).

- Run Detail & Logs
  - Drawer/page showing:
    - Header: job_name, run_id, status, duration, started/ended, attempts.
    - Stage timeline: extract → transform → load with durations and per-stage errors.
    - Metrics snapshot: records_loaded, API latency p95, DB pool usage during run.
    - Error summary with category (API/DB/Data/System) and message.
    - Data Quality results (see below).
  - Log viewer:
    - Stream or poll with auto-scroll; pause/resume live tail.
    - Columns: ts, level, category, message, fields; always display job_id and run_id.
    - Filters: level, category, text search, has_error, JSON key filter.
    - JSON/pretty toggle; copy line; download logs (current run).
    - Redaction badges when secrets/PII replaced; never render redacted values.

- Data Quality
  - DQ panel per run and aggregate tab:
    - Row count delta vs prior run and vs baseline (median of last N); flag anomalies.
    - Null-rate spikes by column (top offenders); show delta percentage.
    - Schema drift events (added/removed/changed types); display impacted tables/columns.
  - DQ metrics surfaced as pass/warn/fail with badges; link to alert if triggered.

- Alerts
  - Active and recent alerts list: type (job failure, repeated retries, DQ anomaly), severity, started_at, affected job(s), threshold context (read-only), status (active/ack/resolved).
  - Actions: acknowledge/unacknowledge (frontend state sent to API), copy alert link, view related runs/logs.
  - Alert detail shows rule metadata (source threshold, window, channel), last notification time.

- Health & Readiness
  - Services grid: API, Scheduler, Workers, DB, Prometheus, Grafana, Alertmanager, PgBouncer (if present).
  - Indicators: healthy/unhealthy/degraded; uptime, version, last check, latency.
  - Maintenance/incident banner if any critical component unhealthy.

- Accessibility & UX
  - Keyboard nav for tables/logs; ARIA live region for streaming logs; color contrast AA; non-color status indicators.
  - Empty/errored states with retry; loading skeletons; large dataset virtualization for logs and tables.

- Security & Privacy
  - Never show secrets; display "[REDACTED]" placeholder.
  - PII-safe by default; no raw payload preview; downloads honor redaction.
  - Audit-friendly: include who acknowledged alerts (from API).

## User Stories
- As Clinical Ops, I see overall success rate and recent failures in the last 24h to assess system health at a glance.
- As a Data Engineer, I filter failed runs, open a run, and correlate logs via run_id/job_id to diagnose API vs DB errors.
- As BI, I verify data freshness and row deltas for key jobs to ensure dashboards reflect current data.
- As On-call, I view active alerts, acknowledge them, and jump to related run details and logs.

## Technical Considerations
- Next.js App Router pages: /monitoring/(overview|jobs|dq|alerts|health).
- Components: KpiCard, TimeRangePicker, StatusPill, JobsTable, RunsTable, RunDetailsDrawer, StageTimeline, LogViewer, DQPanel, AlertList, HealthGrid.
- Data contracts (read-only):
  - Summary: { jobs_executed, success_rate, duration_ms_avg, records_loaded, api_latency_p95_ms, db_pool_usage_pct, timeseries[] }
  - Jobs: [{ job_name, last_run_at, last_run_status, success_rate, avg_duration_ms, last_records_loaded }]
  - Runs: [{ run_id, job_name, started_at, ended_at, duration_ms, status, retries, records_loaded, error_category }]
  - Run detail: { stages[], metrics{}, dq_checks{ row_delta, null_rates[], schema_drift[] }, errors[], logs_stream_url }
  - Alerts: [{ id, type, severity, status, started_at, acknowledged_by, related_runs[] , threshold_summary }]
  - Health: [{ service, status, uptime_s, version, last_check_at, latency_ms }]
- Real-time expectations: Overview refresh ≤15s; log tail latency ≤5s; health refresh ≤30s.

## Success Criteria
- Overview shows required Prometheus-backed KPIs and trends within selected time range.
- Runs and details display success/failure, durations, records loaded, retries, and error categories with correlation IDs visible in logs.
- Alerts list updates with failures and repeated retries; thresholds displayed; acknowledge flows work.
- DQ checks (row deltas, null-rate spikes, schema drift) visible per run and aggregate, with flagged anomalies.
- Health/readiness view shows uptime and version for core services; degraded/unavailable states clearly indicated.
- All views responsive, accessible, performant (virtualized tables/logs), and PII-safe with secret redaction.

