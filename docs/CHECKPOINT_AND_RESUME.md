# Checkpoint and Resume Functionality

**Date**: January 2, 2026  
**Purpose**: Document checkpoint/resume and timeout handling for ETL jobs

---

## Overview

ETL jobs can now automatically save checkpoints during execution and resume from where they left off if they timeout or fail. This prevents data loss and allows long-running jobs to complete across multiple executions.

---

## Features

### 1. Automatic Checkpointing

- **Periodic Checkpoints**: Jobs save progress every 60 seconds
- **Checkpoint Data**: Stores skip value, page index, and total records loaded
- **Storage**: Checkpoints are saved in `dw_etl_runs.run_context` as JSONB

### 2. Timeout Handling

- **Default Timeout**: 300 seconds (5 minutes) - configurable via `ETL_DEFAULT_TIMEOUT_SECONDS`
- **Timeout Behavior**: When timeout is reached:
  - Checkpoint is saved automatically
  - Run status remains `running` (not `failed`)
  - Error message includes resume instructions
- **Resume**: Retry the run to continue from checkpoint

### 3. Resume Capability

- **Automatic Detection**: When retrying a run, system automatically detects if a checkpoint exists
- **Resume from Checkpoint**: If checkpoint found, job resumes from saved skip value
- **New Run**: If no checkpoint, starts fresh

---

## How It Works

### Checkpoint Structure

Checkpoints are stored in `run_context` JSONB:

```json
{
  "checkpoint": {
    "skip": 50000,
    "page_index": 500,
    "total_records": 50000,
    "last_checkpoint_time": "2026-01-02T12:00:00"
  },
  "parameters": {...}  // Original parameters if parameterized job
}
```

### Execution Flow

1. **Start Job**: Job begins execution
2. **Periodic Checkpoints**: Every 60 seconds, save current progress
3. **Timeout Check**: Before each API call, check if timeout exceeded
4. **On Timeout**: Save checkpoint, keep status as `running`, raise `JobTimeoutError`
5. **On Success**: Clear checkpoint, mark as `success`
6. **On Failure**: Checkpoint remains for potential resume

### Resume Flow

1. **Retry Run**: Call `/runs/{run_id}/retry` or `execute_job(resume_from_checkpoint=True)`
2. **Checkpoint Detection**: System checks `run_context` for checkpoint
3. **Resume**: If found, start from saved `skip` value
4. **Continue**: Job continues pagination from checkpoint

---

## Usage

### Via API

```bash
# Retry a failed/timed-out run (automatically resumes from checkpoint if available)
curl -X POST http://localhost:8000/runs/1234/retry \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```

### Via Python

```python
from src.etl.executor import JobExecutor

executor = JobExecutor()

# Execute with resume from checkpoint
result = executor.execute_job(
    job_id=3,
    resume_from_checkpoint=True,  # Automatically detects checkpoint
    timeout_seconds=600,  # 10 minutes
)

# Or explicitly check for checkpoint first
from src.etl.executor import JobExecutor, CheckpointData

executor = JobExecutor()
checkpoint = executor.get_checkpoint(run_id=1234)
if checkpoint:
    print(f"Resume from skip={checkpoint.skip}, records={checkpoint.total_records}")
    result = executor.execute_job(
        job_id=3,
        resume_from_checkpoint=True,
    )
```

---

## Configuration

### Environment Variables

```bash
# Default timeout for ETL jobs (seconds)
ETL_DEFAULT_TIMEOUT_SECONDS=300  # 5 minutes

# For very large jobs, increase timeout
ETL_DEFAULT_TIMEOUT_SECONDS=3600  # 1 hour
```

### Checkpoint Interval

The checkpoint interval (60 seconds) is hardcoded in `_fetch_and_load()`. To change:

```python
checkpoint_interval = 120  # Save every 2 minutes instead
```

---

## Benefits

1. **No Data Loss**: Progress is saved even if job times out
2. **Resumable**: Long-running jobs can complete across multiple executions
3. **Efficient**: Only saves checkpoint periodically, not on every record
4. **Automatic**: No manual intervention required
5. **Transparent**: Checkpoints are stored in existing `run_context` column

---

## Troubleshooting

### Job Still Getting Stuck

If a job still gets stuck despite timeout:

1. **Check Timeout Setting**: Verify `ETL_DEFAULT_TIMEOUT_SECONDS` is set
2. **Check API Client**: The timeout only applies to the overall job, not individual API calls
3. **Check Network**: Network issues can cause hangs before timeout check
4. **Review Logs**: Check for patterns in stuck jobs

### Checkpoint Not Saving

If checkpoints aren't being saved:

1. **Check Database**: Verify `run_context` column exists and is JSONB
2. **Check Logs**: Look for "checkpoint_saved" log messages
3. **Check Interval**: Jobs must run for at least 60 seconds to save checkpoint

### Resume Not Working

If resume doesn't work:

1. **Check Checkpoint**: Verify checkpoint exists in `run_context`
2. **Check Status**: Run must be `running` or `failed` (not `success`)
3. **Check Parameters**: For parameterized jobs, parameters must match

---

## Example: Resuming a Large Job

```python
# Job times out after 5 minutes with 50,000 records loaded
# Checkpoint saved: skip=50000, total_records=50000

# Retry the run
result = executor.execute_job(
    job_id=3,  # Patients job
    resume_from_checkpoint=True,
)

# Job resumes from skip=50000 and continues loading
# Final result: 150,000 records loaded (50,000 from first run + 100,000 from resume)
```

---

## Database Schema

No schema changes required. Uses existing `dw_etl_runs.run_context` JSONB column.

---

## Related Documentation

- `docs/05_Job_Sequencing_and_Incremental_Loading.md` - Job execution patterns
- `docs/STAGING_DUPLICATE_AND_CHANGE_DETECTION.md` - Data loading logic
- `src/etl/executor.py` - Implementation details

