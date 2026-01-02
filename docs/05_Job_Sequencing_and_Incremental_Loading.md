# Job Sequencing and Incremental Loading Analysis

**Document Version**: 1.0  
**Last Updated**: December 31, 2025  
**Purpose**: Comprehensive analysis of ETL job dependencies, execution sequence, and incremental loading capabilities

---

## Executive Summary

- **Total Jobs**: 90
- **Active Jobs**: ~50
- **Non-Parameterized**: 57 jobs (can run independently)
- **Parameterized**: 33 jobs (require parent entity data)
- **Incremental Loading**: Supported via OData `$filter` with `modifiedDate`

---

## Job Dependency Analysis

### Phase 1: Core Dimensions (No Dependencies)

These jobs can run in parallel as they have no dependencies:

| Job ID | Name | Endpoint | Target Table | Supports Incremental? |
|--------|------|----------|-------------|----------------------|
| 1 | Sites | `/api/v1/sites` | `dim_sites_staging` | ✅ Yes (modifiedDate) |
| 2 | Studies | `/api/v1/studies/odata` | `dim_studies_staging` | ✅ Yes (modifiedDate) |
| 3 | Patients | `/api/v1/patients/odata` | `dim_patients_staging` | ✅ Yes (modifiedDate) |
| 8 | Elements | `/api/v1/elements/odata` | `dim_elements_staging` | ✅ Yes (modifiedDate) |
| 9 | PatientVisits | `/api/v1/patient-visits/odata` | `dim_patient_visits_staging` | ✅ Yes (modifiedDate) |
| 25 | Appointments | `/api/v1/appointments/odata` | `dim_appointments_staging` | ✅ Yes (modifiedDate) |
| 26 | Staff | `/api/v1/staff/odata` | `dim_staff_staging` | ✅ Yes (modifiedDate) |

**Execution Strategy**: Run all Phase 1 jobs in parallel (bounded by `ETL_PARALLEL_JOBS` setting)

---

### Phase 2: Study-Dependent Jobs

These jobs require `dim_studies_staging` to be populated first:

| Job ID | Name | Endpoint Pattern | Target Table | Parameter Source |
|--------|------|------------------|-------------|------------------|
| 10 | Subjects | `/api/v1/studies/{studyId}/subjects/odata` | `dim_subjects_staging` | `dim_studies_staging.data->>'id'` |
| 11 | Visits | `/api/v1/studies/{studyId}/visits/odata` | `dim_visits_staging` | `dim_studies_staging.id` |
| 13 | StudyDocuments | `/api/v1/studies/{studyId}/documents/odata` | `dim_study_documents_staging` | `dim_studies_staging.id` |
| 14 | Screenings | `/api/v1/studies/{studyId}/screenings/odata` | `dim_screenings_staging` | `dim_studies_staging.id` |
| 15 | Enrollments | `/api/v1/studies/{studyId}/enrollments/odata` | `dim_enrollments_staging` | `dim_studies_staging.id` |
| 16 | Randomizations | `/api/v1/studies/{studyId}/randomizations/odata` | `dim_randomizations_staging` | `dim_studies_staging.id` |
| 17 | Withdrawals | `/api/v1/studies/{studyId}/withdrawals/odata` | `dim_withdrawals_staging` | `dim_studies_staging.id` |
| 20 | ConcomitantMedications | `/api/v1/studies/{studyId}/concomitant-medications/odata` | `dim_concomitant_medications_staging` | `dim_studies_staging.id` |
| 23 | Queries | `/api/v1/studies/{studyId}/queries/odata` | `dim_queries_staging` | `dim_studies_staging.id` |
| 27 | StudyActions | `/api/v1/studies/{studyId}/actions/odata` | `dim_study_actions_staging` | `dim_studies_staging.data->>'id'` |
| 28 | StudyMilestones | `/api/v1/studies/{studyId}/milestones/odata` | `fact_study_milestones_staging` | `dim_studies_staging.data->>'id'` |
| 29 | StudyNotes | `/api/v1/studies/{studyId}/notes/odata` | `fact_study_documents_staging` | `dim_studies_staging.data->>'id'` |

**Execution Strategy**: 
1. Wait for Phase 1 "Studies" job to complete
2. Extract study IDs from `dim_studies_staging`
3. Run each parameterized job for each study (can parallelize by study)

**Incremental Loading**: 
- ✅ Can filter by `modifiedDate` within each study
- Example: `?$filter=modifiedDate gt 2025-12-24T00:00:00`

---

### Phase 3: Patient Visit-Dependent Jobs

These jobs require `dim_patient_visits_staging` to be populated:

| Job ID | Name | Endpoint Pattern | Target Table |
|--------|------|------------------|-------------|
| 24 | PatientVisitElements | `/api/v1/patient-visits/{patientVisitId}/elements/odata` | `dim_patient_visit_elements_staging` |

**Execution Strategy**:
1. Wait for Phase 1 "PatientVisits" job to complete
2. Extract patient visit IDs from `dim_patient_visits_staging`
3. Run job for each patient visit

**Incremental Loading**: ✅ Can filter by `modifiedDate`

---

## Incremental Loading Analysis

### API Support

According to the Clinical Conductor API documentation:
- ✅ Most entities include `modifiedDate` field
- ✅ OData `$filter` supports date comparisons
- ✅ Recommended pattern: `?$filter=modifiedDate gt {last_run_timestamp}`

### Implementation Strategy

**For Non-Parameterized Jobs**:
```python
# Get last successful run timestamp
last_run = get_last_successful_run(job_id)
if last_run:
    filter_date = last_run.completed_at.isoformat()
    params = ODataParams(
        filter=f"modifiedDate gt {filter_date}"
    )
else:
    # Full load on first run
    params = None
```

**For Parameterized Jobs**:
```python
# For each parent entity (e.g., study)
for study in studies:
    last_run = get_last_successful_run(job_id, parameters={'studyId': study.id})
    if last_run:
        filter_date = last_run.completed_at.isoformat()
        params = ODataParams(
            filter=f"modifiedDate gt {filter_date}"
        )
    else:
        params = None
    
    # Fetch with filter
    fetch_data(endpoint, params=params)
```

### Jobs Supporting Incremental Loading

**Status**: ⚠️ **VERIFICATION NEEDED**

The API documentation indicates that most entities include `modifiedDate` fields, and OData `$filter` should support date comparisons. However, testing revealed:

1. **Date Format Issues**: The API requires a specific OData DateTimeOffset format that needs further investigation
2. **Field Name Verification**: Need to confirm actual field names in API responses (may be `modifiedDate`, `modifiedOn`, `lastModified`, etc.)

**Recommended Approach**:
1. **First**: Inspect actual API responses to identify timestamp field names
2. **Second**: Test OData filter syntax with correct date format
3. **Third**: Implement incremental loading once format is confirmed

**Potential Field Names** (to verify):
- `modifiedDate`
- `modifiedOn`
- `lastModified`
- `updatedAt`
- `updatedDate`

**Jobs Likely to Support Incremental Loading** (once format is confirmed):
- ✅ Sites (Job 1)
- ✅ Studies (Job 2)
- ✅ Patients (Job 3)
- ✅ PatientVisits (Job 9)
- ✅ Appointments (Job 25)
- ✅ Staff (Job 26)
- ✅ All study-dependent jobs (Jobs 10-29)
- ✅ PatientVisitElements (Job 24)

### Staging Table Requirements

To support incremental loading, staging tables should track:
1. **Last successful run timestamp** - stored in `dw_etl_runs.completed_at`
2. **Last modified timestamp per record** - stored in `data->>'modifiedDate'` (JSONB)
3. **Run context** - stored in `dw_etl_runs.run_context` (for parameterized jobs)

---

## Recommended Execution Sequence

### Daily Full Refresh (Recommended Weekly)

```
Phase 1 (Parallel - 7 jobs):
  1. Sites
  2. Studies
  3. Patients
  4. Elements
  5. PatientVisits
  6. Appointments
  7. Staff

Phase 2 (After Studies complete - 12 jobs):
  For each study in dim_studies_staging:
    10. Subjects
    11. Visits
    13. StudyDocuments
    14. Screenings
    15. Enrollments
    16. Randomizations
    17. Withdrawals
    20. ConcomitantMedications
    23. Queries
    27. StudyActions
    28. StudyMilestones
    29. StudyNotes

Phase 3 (After PatientVisits complete - 1 job):
  For each patient visit in dim_patient_visits_staging:
    24. PatientVisitElements
```

### Incremental Refresh (Recommended Daily)

```
Same sequence, but with modifiedDate filters:
- Only fetch records modified since last successful run
- Reduces API load and processing time
- Maintains data freshness
```

---

## Implementation Recommendations

### 1. Add Incremental Loading Support

**Database Changes**:
- ✅ Already have `dw_etl_runs.completed_at` for tracking last run
- ✅ Already have `run_context` for parameterized job parameters
- ✅ Staging tables store full JSONB with `modifiedDate`

**Code Changes Needed**:
1. Add `incremental_load` flag to `dw_etl_jobs` table
2. Modify `JobExecutor` to:
   - Query last successful run timestamp
   - Build `$filter` clause with `modifiedDate gt {timestamp}`
   - Apply filter to OData requests
3. Add configuration option: `ETL_INCREMENTAL_LOAD=true`

### 2. Dependency Management

**Current State**: Jobs are executed independently

**Recommended**: 
- Implement dependency graph in `ETLOrchestrator`
- Add `depends_on` column to `dw_etl_jobs` table
- Validate DAG before execution
- Execute in topological order

### 3. Scheduling

**Current State**: Individual cron schedules per job

**Recommended**:
- Phase-based scheduling:
  - Phase 1: Daily at 2 AM
  - Phase 2: Daily at 3 AM (after Phase 1 completes)
  - Phase 3: Daily at 4 AM (after Phase 2 completes)
- Or use dependency-aware scheduler that triggers Phase 2 after Phase 1 completes

---

## Next Steps

1. ✅ **Cleanup stuck runs** - COMPLETED
2. ⏳ **Test incremental loading** - Verify `modifiedDate` filtering works
3. ⏳ **Add dependency tracking** - Update `dw_etl_jobs` with `depends_on`
4. ⏳ **Implement incremental logic** - Update `JobExecutor`
5. ⏳ **Update orchestrator** - Add dependency-aware execution
6. ⏳ **Create scheduling plan** - Set up phase-based schedules

---

**Document End**

