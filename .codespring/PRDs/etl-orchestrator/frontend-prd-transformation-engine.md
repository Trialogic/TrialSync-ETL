## Feature Overview
UI to configure, execute, and monitor Bronze→Silver SQL transformations. Supports parameterized procedures, transaction scope selection, incremental vs full refresh with guardrails, dependency-aware ordering (dimensions before facts), structured logs, metrics, and materialized view refresh.

## Requirements
- Views
  - Runs: configure/execute current run (left), real-time progress (center), details/logs (right).
  - History: past runs with filters, drill-in to details.
  - Metrics: aggregate durations, rows affected, failures; per-procedure trends.
- Procedure catalog
  - Load list with: name, schema, type (dimension/fact), dependencies[], parameters[], supportsIncremental, supportsFull, refreshesMVs[].
  - Search, filter by type/status, show computed execution order; lock "Respect dependencies" toggle on by default.
- Run configuration
  - Scope: All, Group (by tag), or Selected procedures. Multi-select with dependency resolution preview.
  - Mode: Incremental or Full. Incremental default; Full requires Admin role and double-confirm ("TYPE FULL REFRESH") + dry-run impact summary (count of affected procedures).
  - Transaction scope: Per-procedure (default) or Per-group.
  - Parameters: dynamic inputs per procedure or global (e.g., start_date, end_date, site_id); validate types and required flags.
  - Materialized views: toggle "Refresh MVs after run"; show list if applicable.
  - Notifications: optional Slack/Email toggles.
- Execution & progress
  - Start Run: validates config, shows assigned Run ID; disable while validating.
  - Real-time statuses: Pending, Running, Succeeded (duration, rows), Failed (error), Skipped (dependency failure), Retried(n).
  - Controls: Cancel (Admin/Operator), Retry failed only, Re-run with same config (idempotent).
  - Ordering badge: "Dims→Facts" with step index; tooltip explains dependency chain.
- Logs & details
  - Per-procedure expandable panel: timings (queued/start/end), rows affected, structured error (code/message), retry history.
  - Live log stream with tailing; copy-to-clipboard; download NDJSON for entire run.
- History
  - List with runId, user, mode, scope, outcome, duration, total rows; quick filters (Failed last 24h, Full refreshes).
- Metrics
  - Cards: total duration, total rows, succeeded/failed count.
  - Charts: duration by procedure, failure rate over time; link to Prometheus/Grafana dashboards.
- Empty/error states
  - No procedures configured, backend unavailable, partial updates; provide retry and diagnostics link.
- Responsive
  - Desktop ≥1280px: 3-column; 768–1279px: 2-column (config collapsible); <768px: stacked with sticky run toolbar.
- Accessibility
  - Keyboard navigable; ARIA live region for status updates; dialogs focus-trapped; color+iconography for statuses; contrast AA; structured logs readable by screen readers.

## User Stories
- As an Operator, I run incremental transforms for selected procedures with dependencies auto-ordered and monitor progress live.
- As an Admin, I execute a full refresh with explicit confirmation and see an impact summary before starting.
- As a Data Engineer, I inspect a failed procedure's logs, retry failed steps only, and download NDJSON for analysis.
- As BI, I review prior runs and metrics to verify row counts and durations before reporting.

## Technical Considerations
- API contracts (frontend expectations)
  - GET /api/transformations/procedures → [{name, schema, type, dependencies[], parameters[{key,type,required,default}], supportsIncremental, supportsFull, refreshesMVs[]}]
  - POST /api/transformations/runs → {runId}
  - GET /api/transformations/runs/{runId} → summary + steps[{name,status,durationMs,rows,error,retries,startedAt,endedAt}]
  - SSE GET /api/transformations/runs/{runId}/events → events: run_started, procedure_started, procedure_finished, procedure_failed, run_finished.
  - GET /api/transformations/runs/{runId}/logs.ndjson; GET /api/transformations/metrics
- State/UX
  - Persist runId in URL (?runId=) for deep-linking; reconnect SSE on reload.
  - Virtualize procedure list (>200 items); cap live log buffer with "Load more."
- Permissions
  - Viewer: read-only; Operator: run incremental/cancel/retry; Admin: full refresh, transaction scope changes.
- Time/formatting
  - Local timezone display; ISO timestamps in tooltips; thousand separators for rows.

## Success Criteria
- Users can execute parameterized runs with transaction safety and dependency-aware order.
- Full refresh requires admin and confirmation; accidental full refresh is prevented.
- UI logs timings, rows, and errors per procedure; supports retry failed-only and idempotent re-runs.
- Materialized view refreshes can be toggled and observed.
- Real-time status updates with >99% stable streaming; responsive and accessible (WCAG AA).
- Metrics view shows per-procedure durations, rows, and failure counts; export/download works.

