## Feature Overview
Persist configuration, observability, and state for a resilient Clinical Conductor API client using X-ApiKey and OData. Data enables robust pagination, rate limit coordination, retries/backoff, and strict response parsing/validation, feeding the Bronze layer and operational monitoring.

## Requirements
- Store API client configurations (base_url, auth reference, retry/backoff, timeouts) with activation flags and audit fields.
- Record all request attempts and responses (headers, payloads, timing, sizes), including validation outcomes and OData metadata.
- Track rate limit state per scope (global/endpoint) from response headers to coordinate throttling.
- Maintain pagination cursors per resource and filter to support $top/$skip and resumption after failures.
- Catalog reusable OData query templates for scheduled or ad-hoc syncs with parameter hashing for idempotency.
- Capture typed error events (retryable vs non-retryable) linked to attempts and runs.
- Track sync runs for correlation and SLA reporting.
- Optionally track schema validation results for response shape drift.

## Data Model & Schema Design
- cc_api_client_config (1) —< cc_odata_query_template, cc_pagination_state, cc_rate_limit_state, cc_api_request_log
- cc_api_request_log (1) — 0..1 cc_api_response_log; cc_error_event references request/response
- cc_sync_run (1) —< cc_api_request_log, cc_error_event
- Uniqueness: one pagination row per (config_id, resource_path, filter_hash); one rate-limit scope per config.

## Table Structures & Relationships
- Keys are UUID primary keys. FKs enforce referential integrity. JSONB for headers, params, and payloads. Request and response logs form the Bronze audit trail.

## Indexes & Constraints
- Unique: cc_api_client_config.name; cc_odata_query_template (config_id, resource_path, params_hash); cc_pagination_state (config_id, resource_path, filter_hash); cc_rate_limit_state (config_id, scope).
- B-tree indexes: request_log(run_id, sent_at), request_log(endpoint_path, sent_at), response_log(status_code), error_event(occurred_at), pagination_state(last_sync_at), rate_limit_state(reset_at).
- GIN indexes: request_log.query_params, response_log.headers; optionally response_log.body on limited keys (e.g., '@odata.nextLink', 'value').
- Constraints: status fields via CHECK (e.g., sync_run.status IN('running','succeeded','failed','partial')).

## Data Migration Strategies
- Create new tables alongside legacy feature-api-client; backfill last 30–90 days of request/response history where available.
- Compute params_hash and filter_hash during backfill for idempotency; initialize pagination_state from latest successful responses per resource.
- Gradual cutover: dual-write logs for one release cycle; verify parity via counts and sampled payload hashes.
- Retention: partition request/response logs monthly; retain detailed logs 90 days, aggregate metrics elsewhere if needed.

## Query Optimization Considerations
- Use run_id + time-window predicates and endpoint_path filters to constrain scans.
- Avoid unbounded JSONB body scans; rely on selective GIN indexes and narrow projections.
- Precompute hashes (params_hash, filter_hash) to enable targeted lookups for pagination/idempotency.

## User Stories
- As a data engineer, I can resume a failed sync from the last $skip for a resource/filter without data loss.
- As SRE, I can correlate 429 spikes to endpoints and runs to tune backoff.
- As compliance, I can audit every request/response with headers and timestamps.

## Technical Considerations
- Do not store raw API keys; persist a reference (e.g., secret_id). Mask/scrub sensitive headers.
- Validate and store parse_ok and validation_errors for downstream quality checks.
- Capture odata_count and presence of @odata.nextLink to drive pagination decisions.

## Success Criteria
- 100% of requests and responses logged with correlation to runs.
- Accurate resumption: pagination_state enables idempotent continuation with zero duplicate primary keys in Silver.
- Rate limit adherence evidenced by decreasing 429s over time.
- Validation coverage: >= 95% parse_ok on expected endpoints; drift surfaced via schema_validation entries.
