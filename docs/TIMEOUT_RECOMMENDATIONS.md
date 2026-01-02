# ETL Job Timeout Recommendations

**Date**: January 2, 2026  
**Purpose**: Recommended timeout settings for different job sizes

---

## Overview

ETL jobs now have configurable timeouts to prevent indefinite hangs. The default timeout is 300 seconds (5 minutes), but this may need adjustment based on job size and data volume.

---

## Timeout Configuration

### Environment Variable

```bash
# Default: 300 seconds (5 minutes)
ETL_DEFAULT_TIMEOUT_SECONDS=300

# For large jobs, increase:
ETL_DEFAULT_TIMEOUT_SECONDS=3600  # 1 hour
ETL_DEFAULT_TIMEOUT_SECONDS=7200  # 2 hours
```

### Per-Job Override

You can also override timeout per job execution:

```python
from src.etl.executor import JobExecutor

executor = JobExecutor()
result = executor.execute_job(
    job_id=3,  # Patients job
    timeout_seconds=3600,  # 1 hour for large job
)
```

---

## Recommended Timeouts by Job Size

### Small Jobs (< 1,000 records)
- **Recommended**: 300 seconds (5 minutes)
- **Examples**: Sites (40 records), Staff (884 records)
- **Rationale**: These jobs complete quickly, default timeout is sufficient

### Medium Jobs (1,000 - 50,000 records)
- **Recommended**: 600-1800 seconds (10-30 minutes)
- **Examples**: Studies (1,050), Elements (15,836), Subjects (17,238)
- **Rationale**: May need more time for API pagination and data loading

### Large Jobs (50,000 - 200,000 records)
- **Recommended**: 3600-7200 seconds (1-2 hours)
- **Examples**: 
  - Patients (152,751 records) → 3600 seconds (1 hour)
  - PatientVisits (large volume) → 3600-7200 seconds (1-2 hours)
  - Subject Statuses (119,749 records) → 3600 seconds (1 hour)
- **Rationale**: Large datasets require extensive pagination and processing time

### Very Large Jobs (> 200,000 records)
- **Recommended**: 7200+ seconds (2+ hours)
- **Examples**: PatientVisits with full history
- **Rationale**: May need multiple checkpoint/resume cycles

---

## Job-Specific Recommendations

### High-Priority Jobs

| Job ID | Name | Record Count | Recommended Timeout |
|--------|------|--------------|-------------------|
| 3 | Patients | 152,751 | 3600s (1 hour) |
| 9 | PatientVisits | Variable | 3600-7200s (1-2 hours) |
| 127 | Subject Statuses | 119,749 | 3600s (1 hour) |
| 25 | Appointments | 40,893 | 1800s (30 minutes) |

### Reference Data Jobs

| Job ID | Name | Record Count | Recommended Timeout |
|--------|------|--------------|-------------------|
| 1 | Sites | 40 | 300s (5 minutes) |
| 2 | Studies | 1,050 | 600s (10 minutes) |
| 26 | Staff | 884 | 300s (5 minutes) |
| 8 | Elements | 15,836 | 1200s (20 minutes) |

---

## Checkpoint Behavior

### When Checkpoints Are Saved

- **Periodic**: Every 60 seconds during execution
- **On Timeout**: Automatically saved before timeout error
- **On Success**: Checkpoint is cleared (not needed)

### Checkpoint Data

- `skip`: Current pagination offset
- `page_index`: Current page number
- `total_records`: Total records loaded so far
- `last_checkpoint_time`: Timestamp of last checkpoint

### Resume Behavior

- **Automatic**: When retrying a run, checkpoint is automatically detected
- **Seamless**: Job resumes from saved `skip` value
- **Progress Preserved**: Total records accumulate across resume cycles

---

## Example: Large Job with Timeout

```python
from src.etl.executor import JobExecutor, JobTimeoutError

executor = JobExecutor()

try:
    # Run Patients job with 1-hour timeout
    result = executor.execute_job(
        job_id=3,  # Patients
        timeout_seconds=3600,  # 1 hour
    )
    
    if result.status == "success":
        print(f"✅ Loaded {result.records_loaded:,} records")
    elif result.status == "running":
        # Timeout occurred, checkpoint saved
        print(f"⏱️  Timeout after {result.records_loaded:,} records")
        print("   Retry to resume from checkpoint")
        
except JobTimeoutError as e:
    print(f"Timeout: {e}")
    # Retry with resume
    result = executor.execute_job(
        job_id=3,
        resume_from_checkpoint=True,
        timeout_seconds=3600,
    )
```

---

## Monitoring and Adjustment

### Signs You Need to Increase Timeout

1. **Frequent Timeouts**: Jobs consistently timing out before completion
2. **Low Progress**: Jobs timing out with very few records loaded
3. **Large Datasets**: Jobs processing 100K+ records

### Signs Timeout Is Too High

1. **Stuck Jobs**: Jobs running for hours without progress
2. **Resource Exhaustion**: System resources being held too long
3. **No Checkpoints**: Jobs failing before checkpoint can be saved

### Best Practices

1. **Start Conservative**: Begin with default timeout, increase as needed
2. **Monitor Progress**: Check `records_loaded` in run history
3. **Use Checkpoints**: Don't be afraid to use shorter timeouts with resume
4. **Adjust Per Job**: Different jobs may need different timeouts

---

## Troubleshooting

### Job Times Out Immediately

- **Check API**: Verify API is responding
- **Check Network**: Network issues can cause immediate failures
- **Check Credentials**: Authentication failures cause immediate errors

### Job Never Times Out

- **Check Timeout Setting**: Verify `ETL_DEFAULT_TIMEOUT_SECONDS` is set
- **Check Code**: Ensure timeout check is being executed
- **Check Logs**: Look for timeout-related log messages

### Checkpoint Not Saving

- **Check Duration**: Job must run for at least 60 seconds
- **Check Database**: Verify `run_context` column exists
- **Check Logs**: Look for "checkpoint_saved" messages

---

## Related Documentation

- `docs/CHECKPOINT_AND_RESUME.md` - Checkpoint/resume functionality
- `docs/05_Job_Sequencing_and_Incremental_Loading.md` - Job execution patterns
- `src/etl/executor.py` - Implementation details

