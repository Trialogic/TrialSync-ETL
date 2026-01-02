## Feature Overview
Executes parameterized Bronze→Silver SQL transformations with transactional safety, dependency-aware ordering, and mode control (incremental vs full). Produces durable run records, structured logs, Prometheus metrics, and triggers configured materialized view refreshes. Designed for idempotent re-runs with guardrails for full refresh.

## Requirements

- Configuration
  - Source of truth: transformations.yaml (checked-in) defining:
    - name (string), type (dimension|fact), dependencies (list), default_mode (incremental|full)
    - allow_full_refresh (bool), transaction_scope (per_procedure|per_group)
    - params schema (pydantic-compatible), mv_refresh (list of MV names)
    - incremental watermark spec: strategy (timestamp|id), source (column|SQL), state_key (string)
  - Validated at load; invalid config blocks run request with 422.

- Execution semantics
  - Input parameters: mode, selection (all|group|subset of procedures), as_of (timestamp optional), idempotency_key, transaction_scope override, mv_refresh toggle/list, dry_run.
  - Dependency resolution: topological sort; enforce dimensions before facts; reject cycles (400).
  - Incremental mode:
    - Compute since watermark from etl_state by procedure.state_key; until = as_of or now().
    - Pass parameters to SQL: p_mode, p_since, p_until, p_run_id, plus config-defined params.
  - Full refresh mode:
    - Requires allow_full_refresh=true in config and confirm_full_refresh=true in request; otherwise 403.
    - Optional subset allowed only if all selected procedures allow full.
  - Transactions:
    - Scope per config or override: begin/commit per procedure or per dependency group.
    - On any failure: rollback current scope, mark failed, stop downstream; record error details.
  - Retries: transient errors (deadlock, serialization failure, connection reset) retried up to 3 attempts with exponential backoff; non-transient fail fast.
  - Concurrency: one active run for "bronze→silver" pipeline (pg_advisory_lock); parallelism within independent procedures may be enabled (max_concurrency configurable, default 2).

- Logging, state, and metrics
  - Tables:
    - etl_runs(id, requested_by, mode, status, started_at, ended_at, duration_ms, parameters JSONB, error_code, error_message, idempotency_key UNIQUE NULLS NOT DISTINCT)
    - etl_procedure_runs(id, run_id, procedure_name, order_index, mode, status, attempt, started_at, ended_at, duration_ms, rows_affected, tx_scope, error_code, error_message)
    - etl_state(state_key PRIMARY KEY, last_success_watermark, last_run_at, last_rowcount)
  - Structured logs (pino/structlog): run_id, procedure, mode, tx_scope, attempt, duration_ms, rows_affected, error_code, error_message.
  - Prometheus:
    - transformation_duration_seconds{procedure,mode,status} (histogram)
    - transformation_rows_affected_total{procedure,mode} (counter)
    - transformation_failures_total{procedure} (counter)
    - transformation_active_runs (gauge)
    - mv_refresh_duration_seconds{mv_name,status} (histogram)
  - Row counts captured via procedure-returned count or GET DIAGNOSTICS; persisted per procedure run.

- Materialized views
  - If configured, refresh after successful procedure/group or at run-end as specified.
  - Use REFRESH MATERIALIZED VIEW CONCURRENTLY when supported; fallback with warning.
  - MV timings and errors recorded; MV failures do not rollback data but mark run "completed_with_warnings".

- Idempotency and safety
  - Duplicate requests with same idempotency_key return existing run.
  - Re-runs safe: incremental uses stored watermark; full refresh requires explicit confirmation each time.
  - Guardrails: optional "freeze_full_refresh" flag (env/feature flag) to globally disable full.

- Security
  - Auth: service JWT with roles: etl_admin (full/incremental), etl_operator (incremental only), etl_reader (GET only).
  - Input validation against config param schema; reject unknown procedures/params.
  - Audit: requested_by captured from token; immutable run records.

## API Endpoints

- POST /api/transformations/runs
  - Body: mode, procedures[], groups[], as_of, transaction_scope, mv_refresh(true|false|[names]), idempotency_key, confirm_full_refresh(bool), dry_run(bool)
  - Responses: 202 {run_id,status} or 200 existing run if idempotent; 400/403/422 on validation/guardrails.

- GET /api/transformations/runs/{run_id}
  - Returns run status, timings, per-procedure details, rows_affected, errors, mv results.

- POST /api/transformations/runs/{run_id}/cancel
  - Best-effort cooperative cancel; marks remaining procedures as skipped.

- GET /api/transformations/procedures
  - Returns configured procedures with dependencies and capabilities.

## User Stories

- As a data engineer, I trigger an incremental Bronze→Silver run and receive per-procedure timings and row counts.
- As an operator, I attempt a full refresh and must confirm; the system blocks if the feature flag disables full.
- As an analyst, I view run history and MV refresh outcomes to validate SLAs.

## Technical Considerations

- Python worker (APScheduler) executes SQL via psycopg2; Node/Hono exposes API and persists state via Drizzle; both emit Prometheus metrics.
- Use SERIALIZABLE or REPEATABLE READ per scope as configured; ensure PgBouncer session pooling for REFRESH CONCURRENTLY and advisory locks.
- Parameter whitelisting only; no raw SQL from users.
- Timezone: UTC for all timestamps and watermarks.

## Success Criteria

- Parameterized procedures execute with transactional rollback on failure.
- Incremental and full modes supported with guardrails; idempotent re-runs.
- Dependency ordering enforced (dimensions before facts).
- Per-procedure logs with timings, row counts, and errors; durable run/state tables.
- Configured MVs refreshed with metrics.
- Prometheus exposes durations, rows affected, failures; structured logs present with run_ids.

