Feature Overview
UI to configure, trigger, and monitor the Data Loader that bulk inserts/upserts JSONB records into staging tables in batches (~1000). Surfaces lineage (etl_job_id, etl_run_id), validation results, per-batch transactionality, retries, and performance metrics (rows inserted/updated, batch durations) with real-time updates.

Requirements
- Navigation and Routing
  - Dedicated route: /etl/data-loader
  - Deep-linkable run detail: /etl/data-loader/:etl_job_id/:etl_run_id
  - Preserve selected etl_job_id, etl_run_id, and filters in URL query params

- Layout and Components
  - Left panel: Run Configuration
    - Select: ETL Job (autocomplete from configured jobs; required)
    - Text: Run ID (default generated; editable, validated as UUID or slug)
    - Number: Batch Size (default 1000, min 100, max 10000; helper "Env: ETL_BATCH_SIZE")
    - Info callout: Deduplication uses source_id; ON CONFLICT upsert updates data and updated_at
    - Button: Start Load (primary); disabled until valid config
  - Right panel: Run Monitor (appears after run starts or when deep-linked)
    - Header: status badge, etl_job_id, etl_run_id, loaded_at/started_at timestamps
    - Metrics strip (cards):
      - Rows inserted, Rows updated, Rows validated
      - Batches total/succeeded/failed
      - Retries attempted
      - Duration (elapsed, avg batch, p95 batch)
      - Throughput (rows/sec)
    - Validation summary (expandable):
      - Required field errors count
      - JSON shape errors count
      - First 10 examples with path and message
    - Batches table (virtualized if >1000):
      - Columns: Batch #, Attempt(s), Rows attempted, Inserted, Updated, Validation fails, Duration, Status, Committed at, Error
      - Row expand: structured logs (JSON view), error stack, retry timeline
    - Actions:
      - Retry failed batches (bulk and per-batch) when run is in failed/partial state
      - Download logs (NDJSON) and metrics (CSV)
    - Live updates indicator and last refreshed timestamp

- States and Feedback
  - Run states: idle, queued, validating, loading, committing, partial_success, success, failed, canceled
  - Batch states: pending, running, retried(n), succeeded, failed
  - Real-time updates via streaming; fallback polling every 2s
  - Toasts for: run started, transient DB error (will retry), run completed, run failed
  - Empty states: no runs yet; no batches; no validation issues

- Interactions and Validation
  - Client-side validation for batch size range and non-empty etl_job_id
  - Disable Start Load while a run is in progress for the same etl_job_id unless explicitly confirmed (modal)
  - Confirm dialogs for retry-all and cancel run

- Accessibility and Responsiveness
  - Keyboard navigation for all interactive controls; focus states visible
  - ARIA live region for status/metrics updates
  - Color-independent status indicators (icon + text)
  - Responsive: two-column layout ≥1024px; stacked cards and horizontal scroll table <1024px

User Stories
- As a data engineer, I start a manual Data Loader run for a job with a custom batch size and track progress in real time.
- As a platform owner, I quickly identify validation failures and download a sample of error records.
- As an operator, I see which batches failed due to transient DB errors and trigger retries without restarting the entire run.
- As an analyst, I verify lineage (etl_job_id, etl_run_id) and observe rows inserted/updated to confirm load completeness.

Technical Considerations
- Data contracts required by UI (per run):
  - etl_job_id, etl_run_id, batch_size, status, started_at, completed_at, loaded_at
  - metrics: rows_inserted, rows_updated, rows_validated, batches_total, batches_succeeded, batches_failed, retries, throughput_rps, batch_duration_ms_avg, batch_duration_ms_p95
  - validation_summary: required_field_errors, json_shape_errors, examples[{path, message, sample_value}]
  - batches[]: index, status, attempts, rows_attempted, rows_inserted, rows_updated, validation_failures, duration_ms, retries, committed_at, error_code, error_message, logs_fragment
  - logs_url, metrics_download_url
- Updates via SSE or WebSocket; polling fallback supported
- Timestamps displayed in user local time; tooltip shows UTC ISO8601
- Large tables use row virtualization; truncation with expand for long errors

Success Criteria
- Users can configure and start a run with batch size defaulting to 1000 and see lineage fields immediately.
- UI displays accurate, live metrics: rows inserted/updated, batch durations, retries, and per-batch outcomes.
- Validation errors are surfaced with counts and examples; download of logs/metrics works.
- Per-batch transaction and retry status is visible; users can retry failed batches.
- Page performs smoothly for 10k+ batches (virtualized) and updates within 2 seconds of backend changes.
- Meets accessibility requirements (WCAG AA contrast, ARIA live updates, keyboard operability).

