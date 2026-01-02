# Clinical Conductor API Client

## Feature Overview
Provide an authenticated REST/OData API client within the TrialSync console to query Clinical Conductor endpoints with X-ApiKey, OData parameters, pagination, and resiliency controls. Expose real-time visibility into retries, rate limits, latency, and validation. Enable developers to test queries, inspect responses, and export results safely without persisting secrets in the browser.

## Requirements
- Configuration
  - Base URL: prefilled from env or dw_api_credentials; editable; validation (HTTPS required).
  - X-ApiKey: required, masked by default with show/hide; never logged; not stored client-side.
  - Test Connection: runs a lightweight GET; displays status, latency, and server time.
- Request Builder
  - Endpoint input with autocomplete from known CC endpoints (optional list).
  - Modes (radio):
    - get (endpoint, params?)
    - get_odata (endpoint, $filter?, $orderby?, $top=1000, $skip?)
    - get_paginated (endpoint, page_size=1000) with Iterator vs List modes
    - get_with_parameters (key/value)
  - OData parameter fields with validation and helpful errors; $top/$skip numeric constraints; syntax assist for $filter.
  - Page size control (default 1000), max pages soft limit (configurable).
- Execution & Feedback
  - Execute button; Cancel/Abort support mid-flight.
  - Streaming progress for Iterator mode: pages fetched, records count, current backoff if any.
  - Result views: Table (first 100 rows), JSON (raw, collapsible), Headers; Download JSON (respect 5 MB preview limit, full export via server stream).
  - Copy as cURL (redacts X-ApiKey unless explicitly revealed).
- Resilience & Rate Limiting
  - Display retries with attempt count, backoff duration (with jitter), and reason (429/timeouts/transient).
  - Honors ETL_MAX_RETRIES and ETL_RETRY_DELAY_SECONDS; show effective config.
  - Timeout surfaced with actionable message; idempotent GET notice.
- Validation & Errors
  - Guard for missing value[] in OData payloads; warning banner with sample path.
  - Typed error presentation: status, endpoint, params, trace id; classify transient vs permanent.
- Observability
  - Metrics panel: request count, error count, rate-limit events, latency (p50/p95), last 5 requests.
  - Log stream: structured entries (endpoint, status, latency, retries, page index); filter by endpoint/status.
  - Link-outs to Grafana dashboards (open new tab).
- Security & Access
  - Access gated to Data Engineering/Platform role.
  - API key never sent to client logs or analytics; masked in UI; audit trail of executions (who/when/endpoint).
- UX & Accessibility
  - Responsive layout (desktop first, usable on tablets); sticky action bar.
  - Keyboard accessible, labeled inputs, focus states; live regions for progress; color-contrast AA.
  - Clear empty, loading, success, error, and cancelled states.

## User Stories
- As a Data Engineer, I configure base URL and API key, test connectivity, and run a paginated query to validate incremental load behavior.
- As a Platform engineer, I observe rate-limit handling during a long fetch and verify retries/backoff respect configured limits.
- As an Analyst, I build an OData filter, preview first 100 rows, and export sample JSON.

## Technical Considerations
- Next.js 14 (App Router) UI invokes server-side routes (Hono) that wrap the API client; secrets handled server-side only.
- Real-time progress via server streaming; cancel with AbortController mapped to server abort.
- Components: SettingsForm, EndpointInput, ODataBuilder, ModeToggle, ExecuteBar, ProgressStream, ResultsTable, JsonViewer, HeadersPanel, MetricsPanel, LogStream, ErrorCallout, BackoffBanner, CurlDialog.
- Limits: preview cap 100 rows/5 MB; enforce pagination guardrails; configurable max pages.

## Success Criteria
- Auth: Uses X-ApiKey; base URL configurable; Test Connection succeeds with valid creds.
- OData: Supports $top, $skip, $filter, $orderby with input validation.
- Pagination: Iterator and List modes handle large datasets (≥1k pages) with progress and cancel.
- Resilience: Detects 429; exponential backoff with jitter displayed; respects ETL_MAX_RETRIES/ETL_RETRY_DELAY_SECONDS.
- Errors: Transient retried; permanent surfaced with typed context (status, endpoint, params).
- Timeouts: Visible with guidance; requests are GET/idempotent pathways.
- Validation: Warns on missing value[]; shows lightweight schema checks.
- Observability: Metrics for request count/latency/errors/rate-limits; structured logs visible in UI; link to Grafana.
- Performance: p95 single-page fetch latency < 2s in UI; progress updates within 500 ms during pagination.
- Accessibility: Meets WCAG 2.1 AA for forms, focus, and contrast.

