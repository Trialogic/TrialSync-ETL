## Feature Overview
UI for orchestrating ETL jobs: visualize dependencies, monitor schedules, execute jobs on demand with parameters/dry-run, observe retries/backoff, and inspect lineage from dw_etl_runs. Surfaces metrics, statuses, and run details with accessible, real-time updates. Supports parallelism configuration and operational controls with minimal friction.

## Requirements
- Global
  - Display system banner with ETL_PARALLEL_JOBS value and environment (e.g., Prod/Stage).
  - Role-based access: Viewer (read-only), Operator (trigger/cancel runs), Admin (edit settings).
  - Timezone: display timestamps in UTC with local-time tooltip.
  - Polling: auto-refresh active views every 5s; pause on user request.
- Jobs List
  - Paginated, sortable table (server-side) of dw_etl_jobs (job_id, name, enabled, cron, next run, last run status/duration, dependencies count, priority/tags).
  - Filters: status (enabled/disabled), last run outcome (success/fail), tags, data domain, text search (job_id/name).
  - Row actions: Run (opens modal), Dry-run, View details, Disable/Enable (Admin only).
  - Bulk actions: Run (normal/dry), Enable/Disable for selected jobs.
  - Badge indicators: transient failure rate (last 24h), backoff active, parameterized job.
- Job Detail
  - Tabs: Overview, Runs, Logs (current), Metrics.
  - Overview: job config JSON (read-only), cron with human-readable summary, next/previous run, retry policy, parameter schema (if any).
  - Dependency Graph (DAG): interactive view with pan/zoom; nodes colored by last run status; edge tooltips show dependency type. Show topological level grouping.
  - Runs: paginated table of dw_etl_runs (run_id, started/ended, status, attempt count, records, error excerpt). Clicking a run opens a side drawer with:
    - Status timeline (queued → running → retry/backoff steps → completed).
    - Attempts list with timestamps, durations, error classifications (transient/permanent).
    - Lineage metrics: records read/written, affected tables, checksum/hash (if provided).
    - Actions: Retry, Cancel (if running), Rerun with parameters/dry-run.
  - Logs (current run): streamed viewer with level filters, text search, tail/freeze, copy/download. Auto-scroll toggle.
  - Metrics: sparkline charts for duration, success rate, throughput; counters for total runs, failures last 24h. Link to Grafana panel.
- Run Modal (On-demand)
  - For parameterized jobs: dynamic form from parameter schema (JSONB/pydantic-compatible), validation and defaults.
  - Options: Dry-run toggle, Concurrency override (optional), Reason text (required for audit).
  - Confirmation showing expected impacts (read-only summary).
- Settings (Admin)
  - Edit ETL_PARALLEL_JOBS (bounded input, requires confirmation).
  - Toggle alerts on failure visibility in UI (Slack/email destinations shown read-only).
  - Save requires reason and displays effective time.
- Notifications
  - In-app toasts for run queued/started/failed/completed, with link to run detail.
  - Alert banner on systemic failures (e.g., scheduler unhealthy) based on health endpoint/metric.

## User Stories
- As a Data Engineer, I can run a job now (normal or dry-run), pass parameters, and see retries/backoff and logs in real time.
- As an Operator, I can visualize the DAG to confirm correct dependency order and identify blocked jobs.
- As BI, I can view lineage and records loaded to validate data freshness and completeness.
- As Leadership, I can see success rate and duration trends to assess operational health.
- As On-Call, I receive failure alerts in Slack/email and can deep-link into the failed run in the UI.

## Technical Considerations
- Next.js 14 App Router; server components fetch via Hono APIs (Drizzle/asyncpg) with cursor-based pagination.
- Logs stream via SSE; fallback to 5s polling. Large logs virtualized rendering.
- DAG rendered with React Flow (keyboard accessible); colorblind-safe palette with text labels.
- Prometheus metrics queried via read-only API; Grafana panels embedded (signed URL or anonymous view).
- Accessibility: WCAG AA, keyboard navigable tables/graphs, ARIA live regions for status updates, non-color indicators for status.
- Performance: Debounced filters/search; table virtualization; limit log payloads; lazy-load DAG and metrics.
- Audit: All manual actions record user, timestamp, params, reason; surfaced in run metadata.
- Error states: empty results, scheduler offline, metrics unavailable; clear messaging and retry controls.

## Success Criteria
- Visual DAG accurately reflects dependency order; jobs execute in parallel where independent, with ETL_PARALLEL_JOBS visibly enforced.
- UI surfaces retries with exponential backoff and classifies transient vs permanent errors in run detail.
- Schedules display cron expressions with next run times; users can trigger on-demand runs (with parameters/dry-run) successfully.
- dw_etl_runs lineage is visible per run (status, timings, records, error); logs view streams during execution.
- Metrics view shows jobs executed, durations, success rate; links to Grafana function.
- Alerts are mirrored in UI and deep-link to failed runs; role-based access enforced; UI remains responsive and accessible.

