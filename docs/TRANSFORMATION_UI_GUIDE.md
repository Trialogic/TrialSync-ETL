# Transformation Procedures UI Guide

**Purpose**: Document the new UI features for managing transformation procedures (Bronze → Silver layer transformations).

**Last Updated**: January 2, 2026

---

## Overview

The ETL Scheduler UI now includes a **Transformations** tab that allows you to:

- **View** all transformation procedures (stored procedures)
- **Execute** procedures manually
- **Schedule** procedures for automatic execution
- **Monitor** execution history and logs
- **Manage** schedules (add, edit, remove)

---

## Database Schema

Two new tables were created to support transformation procedure management:

### `dw_transformation_schedules`

Stores schedule information for transformation procedures:

- `procedure_name` (VARCHAR, UNIQUE) - Name of the stored procedure
- `schedule_cron` (VARCHAR) - Cron expression for scheduling
- `is_active` (BOOLEAN) - Whether the schedule is active
- `last_run_at` (TIMESTAMP) - Last execution time
- `last_run_status` (VARCHAR) - Last execution status
- `next_run_time` (TIMESTAMP) - Calculated next run time

### `dw_transformation_runs`

Logs execution history for transformation procedures:

- `procedure_name` (VARCHAR) - Name of the procedure executed
- `run_status` (VARCHAR) - 'running', 'success', 'failed'
- `started_at` (TIMESTAMP) - Execution start time
- `completed_at` (TIMESTAMP) - Execution completion time
- `duration_seconds` (NUMERIC) - Execution duration
- `rows_affected` (INTEGER) - Rows inserted/updated/expired
- `error_message` (TEXT) - Error details if failed
- `execution_log` (TEXT) - Captured RAISE NOTICE messages

**SQL Script**: `sql/schema/02_create_transformation_schedules.sql`

---

## API Endpoints

New REST API endpoints for transformation procedures:

### List Transformations
```
GET /transformations
```
Returns list of all transformation procedures with their schedules and last run info.

### Execute Transformation
```
POST /transformations/{procedure_name}/execute
```
Executes a transformation procedure manually and returns execution results.

### Get Schedule
```
GET /transformations/{procedure_name}/schedule
```
Returns schedule information for a specific procedure.

### Update Schedule
```
PUT /transformations/{procedure_name}/schedule
Body: { "schedule_cron": "0 2 * * *", "is_active": true }
```
Updates or creates a schedule for a transformation procedure.

### Delete Schedule
```
DELETE /transformations/{procedure_name}/schedule
```
Removes the schedule for a transformation procedure.

### Get Execution History
```
GET /transformations/{procedure_name}/history?limit=20
```
Returns execution history for a specific procedure.

---

## UI Features

### Transformations Tab

The new **Transformations** tab in the ETL Scheduler UI provides:

1. **Procedure List Table**
   - Procedure name
   - Description (from PostgreSQL comments)
   - Last run time and status
   - Current schedule (cron expression)
   - Next scheduled run time
   - Action buttons

2. **Manual Execution**
   - Click **Run** button to execute a procedure immediately
   - Confirmation dialog before execution
   - Success/error messages displayed

3. **Schedule Management**
   - Click **Schedule** or **Edit** to open the cron editor
   - Supports:
     - Daily schedules (specify time)
     - Weekly schedules (specify day and time)
     - Monthly schedules (specify day of month and time)
     - Custom cron expressions
   - Click **Remove** to delete a schedule

4. **Execution History**
   - Click **History** button to view execution logs
   - Shows:
     - Run ID
     - Status (success/failed/running)
     - Start and completion times
     - Duration
     - Rows affected
     - Error messages (if any)

---

## Setup Instructions

### Step 1: Create Database Tables

Run the SQL script to create the necessary tables:

```bash
psql $DATABASE_URL -f sql/schema/02_create_transformation_schedules.sql
```

Or explicitly:
```bash
psql -h localhost -U chrisprader -d trialsync_dev -f sql/schema/02_create_transformation_schedules.sql
```

### Step 2: Start the Web Server

```bash
# Using Makefile
make start-server

# Or directly
python -m src.web.server
```

### Step 3: Access the UI

Navigate to: http://localhost:8000/ui

Click on the **Transformations** tab to see all available transformation procedures.

---

## Usage Examples

### Schedule `load_all_new_dimensions()` to Run Daily at 2 AM

1. Open the **Transformations** tab
2. Find `load_all_new_dimensions` in the list
3. Click **Schedule** button
4. Select "Daily" recurrence
5. Set time to 02:00 (2 AM)
6. Click **Save Schedule**

The cron expression `0 2 * * *` will be saved.

### Execute `load_dw_dim_patient()` Manually

1. Open the **Transformations** tab
2. Find `load_dw_dim_patient` in the list
3. Click **Run** button
4. Confirm execution
5. Wait for completion message
6. Click **History** to see execution details

### View Execution History

1. Open the **Transformations** tab
2. Find the procedure you want to check
3. Click **History** button
4. Review the execution history table

---

## Important Notes

### Scheduler Service

**Important**: The transformation procedure schedules are stored in the database, but they are **NOT automatically executed** by the ETL scheduler service (`trialsync-etl scheduler`).

The ETL scheduler only executes ETL jobs from `dw_etl_jobs` table. To actually run transformation procedures on schedule, you need to:

1. **Use a separate scheduler** (pg_cron, system cron, or Python script with APScheduler)
2. **Query `dw_transformation_schedules`** for active schedules
3. **Execute procedures** based on their `next_run_time`

See `docs/PATIENT_SILVER_LAYER_SETUP.md` for scheduling options.

### Procedure Execution

- Procedures are executed synchronously (blocking)
- Execution time varies by procedure (typically 1-30 minutes)
- Errors are captured and stored in `dw_transformation_runs.error_message`
- RAISE NOTICE messages from procedures are captured when possible

### Schedule Calculation

Next run times are calculated using the `croniter` library when schedules are saved. If `croniter` is not installed, next run times will be `NULL`.

---

## Troubleshooting

### Procedures Not Appearing in UI

- Verify procedures exist: `SELECT routine_name FROM information_schema.routines WHERE routine_type = 'PROCEDURE'`
- Check procedure names match pattern: `load_dw_dim%`, `load_dw_fact%`, or `load_all_new%`
- Refresh the page

### Schedule Not Saving

- Verify cron expression is valid
- Check database connection
- Review API error messages in browser console

### Execution Failing

- Check `dw_transformation_runs.error_message` for details
- Verify database permissions for executing procedures
- Check PostgreSQL logs for detailed error messages

---

**Document End**

