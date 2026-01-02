## Feature Overview
Executes parameterized Bronze → Silver SQL procedures with deterministic ordering, transaction safety, and observability. Supports incremental and full refresh modes, enforces dependency rules (dimensions before facts), and triggers materialized view refreshes. Provides idempotent runs, detailed logging, and metrics for durations, rows affected, and failures.

## Requirements
- Store procedures, parameters, and dependency graph; flag support for incremental and full refresh.
- Configure transaction scope per run (per_procedure or per_group) and optional execution groups.
- Maintain run and step records with idempotency keys, statuses, timings, rows affected, and errors.
- Enforce ordering: dimensions before facts; honor explicit dependencies.
- Persist parameter snapshots used for each step and watermarks for incremental processing.
- Configure materialized views to refresh on success/always after specific procedures.
- Guard rails for full refresh: record confirmation flag, approver, reason; prevent unconfirmed full runs.
- Emit structured step logs; enable downstream metrics scraping from persisted data.

## User Stories
- As a data engineer, I define procedures, dependencies, and parameters, then trigger a run that executes in order with rollback on failure.
- As an operator, I perform a full refresh with explicit approval and audit trail.
- As an analyst, I see which procedures ran, how long they took, and how many rows they affected.

## Technical Considerations
### Data model and schema design; Table structures and relationships
- transformation_procedure: catalog of executable procedures; links to dependencies, groups, tags, refresh targets, watermarks, and steps.
- transformation_dependency: DAG edges parent → child.
- transformation_parameter: default and mode-scoped parameters per procedure.
- transformation_group and transformation_group_member: optional ordered grouping for per-group transactions.
- transformation_run: one orchestration instance; unique idempotency_key; approval fields for full refresh.
- transformation_step: per-procedure execution within a run; attempts, metrics, parameter snapshot, dependency snapshot, SQL executed.
- transformation_step_log: structured logs per step.
- refresh_target and procedure_refresh_link: materialized view configs and trigger mapping.
- procedure_tag and procedure_tag_link: labeling for selection/filters.
- transformation_watermark: per-procedure incremental cursor state.

### Indexes and constraints
- Unique: procedure (schema_name, procedure_name); refresh_target (schema_name, view_name); run.idempotency_key; group_member (group_id, sequence); step (run_id, procedure_id, attempt_no); tag.name.
- FKs: all UUID references; ON DELETE RESTRICT for configuration, CASCADE for logs.
- Performance indexes: dependency (child_procedure_id), dependency (parent_procedure_id); step (run_id, status, started_at); run (status, started_at); parameter (procedure_id, name). Consider GIN on JSONB fields parameters and dependency_snapshot.
- Optional partitioning: transformation_step_log by ts (monthly) for retention and query speed.

### Data migration strategies
- Create new tables; seed transformation_procedure, dependencies, parameters, groups from existing YAML/SQL registry.
- Backfill refresh_target from database introspection of materialized views; link to procedures where applicable.
- Initialize watermarks from current incremental load cursors; set allow_full_refresh conservatively.
- Migrate recent execution history (if available) into transformation_run/step for baseline metrics.

### Query optimization considerations
- Runnable set resolution: join dependencies and latest successful steps within the same run; cover with indexes on dependency and step by run_id/status.
- Metrics dashboards: aggregate duration and rows_affected by procedure over time; index finished_at.
- Failure triage: filter steps by status=failed and recent window; index finished_at.
- MV refresh planning: prefetch refresh_target links by procedure_id; index link (procedure_id, sequence).

## Success Criteria
- All Bronze → Silver procedures execute with correct ordering and transactional rollback on failure.
- Incremental and full modes honored; full refresh requires recorded confirmation and approver.
- Per-procedure logs persist timings, rows affected, errors; materialized views refreshed as configured.
- Idempotent re-runs via idempotency_key with clear, queryable run/step statuses.
- Metrics derivable from tables: procedure durations, rows affected, failure counts.

