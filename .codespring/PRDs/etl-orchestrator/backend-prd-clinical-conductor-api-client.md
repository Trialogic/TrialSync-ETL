Feature Overview
Clinical Conductor API Client provides a production-grade, configurable, and fault-tolerant HTTP client for extracting OData resources from Clinical Conductor using X-ApiKey authentication. It supports OData query options, robust pagination, rate limit handling, exponential backoff retries, and strict response parsing/validation suitable for ETL into a Medallion data warehouse.

Requirements
- Authentication
  - Use X-ApiKey header with TLS; never log or persist secrets.
  - Reject missing/empty key with configuration validation error.
- Configuration (env + YAML via pydantic; env takes precedence)
  - base_url (required, https only), api_key (required)
  - timeout_connect (default 10s), timeout_read (default 30s)
  - max_retries (default 5), backoff_initial (0.5s), backoff_max (60s), jitter (full jitter)
  - rate_limit_rps (default 5), concurrency=1 (per-instance)
  - default_top (default 100, range 1–1000), max_pages (default 10,000), max_records (optional cap)
  - strict_validation (default false)
- API Contract
  - Method: get_odata(resource: str, params: ODataParams, page_mode: "iterator"|"aggregate"=iterator)
    - resource: path relative to base_url (e.g., /odata/v1/Studies)
    - ODataParams: $top:int, $skip:int, $filter:str, $orderby:str (omit nulls); validate types; URL-encode values.
    - Returns:
      - iterator: yields Page objects {items: list[dict], count?: int, next_link?: str, page_index:int}
      - aggregate: returns list[dict] of all items (enforces max_pages/max_records)
  - Headers: Accept: application/json; X-ApiKey: <key>
  - Query handling: honor server-provided @odata.nextLink when present; else continue via $skip += $top until zero items.
- Pagination
  - Start with provided $skip or 0; enforce $top from params or default_top.
  - Stop when:
    - no nextLink and returned items < $top, or
    - nextLink absent after empty page, or
    - max_pages/max_records reached (raise PaginationLimitExceeded).
- Retry and Backoff
  - Retry on 429, 408, 5xx (excluding 501/505) with exponential backoff + jitter; respect Retry-After header (seconds or HTTP-date).
  - Do not retry 400, 401, 403, 404, 422; map to typed non-retry errors.
- Rate Limiting
  - In-process token bucket to not exceed rate_limit_rps per client instance.
  - Always back off on 429 regardless of local limiter.
- Response Parsing and Validation
  - Require Content-Type application/json; parse to dict.
  - Expected structure:
    - For OData: value: array (required), optional @odata.nextLink (str), @odata.count (int)
  - strict_validation=true: enforce required keys/types, reject unknown types; false: warn and continue if value is array.
  - On parse/validation failure: raise ParseError/ValidationError with correlation id.
- Errors (typed)
  - AuthenticationError (401/403), NotFoundError (404), RateLimitError (429), ServerError (5xx), ClientError (other 4xx), TimeoutError, NetworkError, ParseError, ValidationError, PaginationLimitExceeded.
- Observability
  - Structured logs (structlog): request_id, method, path, status, retry_attempt, backoff, rate_limited, page_index, items_count, duration_ms. Redact headers and PII.
  - Prometheus metrics:
    - cc_client_http_requests_total{status,endpoint}
    - cc_client_http_latency_seconds_bucket{endpoint}
    - cc_client_retries_total{reason}
    - cc_client_rate_limited_total
    - cc_client_pages_fetched_total{endpoint}
    - cc_client_items_fetched_total{endpoint}
- Security
  - Enforce HTTPS; verify certificates; configurable CA bundle; prevent API key in logs/metrics; rotate key without restart via config reload.

User Stories
- As a data engineer, I can page through all Clinical Conductor OData entities reliably without exceeding API limits.
- As an SRE, I can monitor request rates, latencies, and retries via Prometheus/Grafana and alert on anomalies.
- As a developer, I can detect and handle malformed responses via typed exceptions and optional strict validation.

Technical Considerations
- Synchronous client using requests with persistent session and connection pooling; thread-safe rate limiter in-process.
- Encode OData params exactly ($top,$skip,$filter,$orderby) and preserve server-provided nextLink URLs verbatim.
- Cap memory by preferring iterator mode for large extracts; aggregate mode only when bounded by max_records.
- Unit tests with requests-mock: happy path, nextLink and $skip flows, 429 with Retry-After (seconds/date), 5xx retry/backoff, 401/404 non-retry, strict vs non-strict validation, pagination caps, timeouts.

Success Criteria
- 99% of transient 5xx/429 errors recovered via retries without manual intervention.
- Zero occurrences of API key in logs/metrics; HTTPS enforced in all requests.
- End-to-end pagination correctness: all records fetched exactly once; no infinite loops; validated via unit tests.
- Metrics emitted for 100% of requests; dashboards show RPS, latency, retries, and rate-limit events.
- Test coverage ≥85% for client module, including pagination and error paths.
