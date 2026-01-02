# Data Loader

## Feature Overview
Bulk ingest and upsert JSONB records into PostgreSQL staging tables with batching, source_id-based deduplication, lineage capture (etl_job_id, etl_run_id), and lightweight validation. Ensures per-batch transactional integrity, retries on transient database errors, and full observability for throughput and failures.

## Requirements

- Supported targets
  - Only whitelisted staging tables (config: ETL_STAGING_TABLES) are writable.
  - Each staging table must have columns: source_id (TEXT, unique), data (JSONB), etl_job_id (UUID), etl_run_id (UUID), loaded_at (timestamptz), created_at (timestamptz default now()), updated_at (timestamptz default now()).
  - Required unique index: UNIQUE (source_id). Updated_at maintained on upsert.

- API (internal HTTP, service-to-service)
  - POST /etl/staging/{table}/load
  - Auth: service token (JWT or API key) required; table name validated against whitelist; no dynamic SQL.
  - Request body:
    - etl_job_id: UUID (required)
    - etl_run_id: UUID (required)
    - records: array (1..ETL_MAX_REQUEST_RECORDS, default cap 10,000) of:
      - source_id: non-empty string (required)
      - data: JSON object (required)
      - loaded_at: RFC3339 timestamp (optional; default server now())
    - options:
      - batch_size: int (optional; 1..ETL_MAX_BATCH_SIZE; default ETL_BATCH_SIZE=1000)
  - Response 200:
    - table, etl_job_id, etl_run_id
    - batches_total, batches_succeeded, batches_failed
    - rows_inserted, rows_updated
    - duration_ms
    - errors: array of {batch_index, error_code, message} for failed batches
  - Error codes: 400 (validation), 401/403 (auth), 404 (table not whitelisted), 413 (payload too large), 429 (backpressure), 500 (unexpected).

- Processing and business logic
  - Validate envelope and each record (source_id, data is JSON object; reject null/array root).
  - Enforce lineage: etl_job_id and etl_run_id must reference existing metadata rows (reject 400 if unknown).
  - Dedupe within-request by source_id; last occurrence wins; emit deduped_count metric.
  - Partition records into batches of size options.batch_size or ETL_BATCH_SIZE (default 1000).
  - Per-batch transactionality: all-or-nothing per batch; failures do not affect other batches.
  - Upsert semantics:
    - INSERT (source_id, data, etl_job_id, etl_run_id, loaded_at)
    - ON CONFLICT (source_id) DO UPDATE SET
      - data = EXCLUDED.data
      - etl_job_id = EXCLUDED.etl_job_id
      - etl_run_id = EXCLUDED.etl_run_id
      - loaded_at = EXCLUDED.loaded_at
      - updated_at = now()
    - Preserve created_at on update; set created_at on insert; set updated_at on both paths.
  - Retries: retry transient DB errors (deadlock, serialization failure, connection reset/timeout) up to ETL_MAX_RETRIES (default 3) with exponential backoff (jitter). Do not retry validation or unique index definition errors.
  - Limits: enforce ETL_MAX_PAYLOAD_MB (default 20MB), ETL_MAX_REQUEST_RECORDS (default 10k).

- Performance
  - Use COPY or execute_values-style bulk upserts; single round-trip per batch.
  - Connection pooling via PgBouncer or driver pool; cap concurrency to avoid saturation (configurable).
  - Statement timeout (ETL_DB_STATEMENT_TIMEOUT_MS) applied per batch.

- Observability
  - Metrics (Prometheus):
    - etl_loader_rows_inserted_total{table, job}
    - etl_loader_rows_updated_total{table, job}
    - etl_loader_batch_duration_seconds{table, job} (histogram)
    - etl_loader_batches_failed_total{table, job, reason}
    - etl_loader_deduped_records_total{table, job}
  - Structured logs per batch with table, etl_job_id, etl_run_id, counts, latency, retries, error (if any).
  - Trace context propagation: include etl_run_id as trace/span attribute.

- Security
  - Service-auth only; least-privilege DB role limited to staging schema.
  - Input size limits; JSON parsing hardened; table name is validated against whitelist and quoted identifiers are not accepted from clients.
  - TLS in transit.

## User Stories
- As a data engineer, I can submit 50k records for a staging table and get a summary of inserted vs updated with run lineage.
- As an operator, I can rely on per-batch retries and isolation so partial failures don't corrupt other batches.
- As an analyst, I can audit when and by which run a record was loaded via lineage and timestamps.

## Technical Considerations
- Idempotency: repeated submissions of the same source_id are safe; last-write-wins within the request and across runs.
- Ordering: no cross-batch ordering guarantees beyond upsert semantics.
- Multi-tenant expansion: if needed later, extend conflict target to (tenant_id, source_id) consistently across tables.
- Backpressure: return 429 when pool saturation or queue depth exceeds thresholds; include Retry-After.

## Success Criteria
- Meets acceptance tests: correct upserts using source_id; accurate lineage/timestamps; per-batch transactions with transient retries; configurable batching; validated inputs.
- Sustains ≥10k rows/sec aggregate with default batch size on target hardware without error rate >1%.
- Metrics and logs visible in Prometheus/Grafana with per-table/job labels; alerts on batch failures and retry spikes.

