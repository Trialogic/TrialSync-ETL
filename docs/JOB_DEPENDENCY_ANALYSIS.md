# Job Dependency Analysis and Execution Plan

**Generated**: 2025-12-31  
**Total Jobs**: 90  
**Active Jobs**: 67

---

## Executive Summary

This document provides:
1. **Dependency Graph**: Proper execution sequence for all ETL jobs
2. **Incremental Loading Analysis**: Which jobs support timestamp-based filtering
3. **Execution Phases**: Recommended parallel execution groups
4. **Schedule Recommendations**: Optimal timing for each phase

---

## Dependency Graph

### Phase 0: Foundation (No Dependencies)
**Execute First - Can Run in Parallel**

| Job ID | Name | Endpoint | Target Table | Notes |
|--------|------|----------|--------------|-------|
| 1 | Sites | `/api/v1/sites` | `dim_sites_staging` | Reference data |
| 35 | Sponsors | `/api/v1/sponsors/odata` | `dim_sponsors_staging` | Reference data |
| 120 | System Allergies | `/api/v1/system/allergies/odata` | `dim_system_allergies_staging` | System reference |
| 121 | System Conditions | `/api/v1/system/conditions/odata` | `dim_system_conditions_staging` | System reference |
| 122 | System Medications | `/api/v1/system/medications/odata` | `dim_system_medications_staging` | System reference |
| 123 | System Procedures | `/api/v1/system/procedures/odata` | `dim_system_procedures_staging` | System reference |
| 124 | System Immunizations | `/api/v1/system/immunizations/odata` | `dim_system_immunizations_staging` | System reference |
| 125 | System Devices | `/api/v1/system/devices/odata` | `dim_system_devices_staging` | System reference |
| 126 | System Social History | `/api/v1/system/social-history/odata` | `dim_system_social_history_staging` | System reference |
| 127 | Subject Statuses | `/api/v1/subject-statuses/odata` | `dim_subject_statuses_staging` | Reference data |
| 128 | System Document Types | `/api/v1/system/document-types` | `dim_system_document_types_staging` | System reference |
| 129 | System Action Categories | `/api/v1/system/action-categories` | `dim_system_action_categories_staging` | System reference |
| 130 | System Study Categories | `/api/v1/system/study-categories` | `dim_system_study_categories_staging` | System reference |
| 131 | System Study Subcategories | `/api/v1/system/study-subcategories` | `dim_system_study_subcategories_staging` | System reference |
| 132 | System Study Statuses | `/api/v1/system/study-statuses/odata` | `dim_system_study_statuses_staging` | System reference |
| 133 | System Lookup Lists | `/api/v1/system/lookup-lists` | `dim_system_lookup_lists_staging` | System reference |
| 134 | System Patient Custom Fields | `/api/v1/system/patient-customfields` | `dim_system_patient_customfields_staging` | System reference |
| 135 | System Study Custom Fields | `/api/v1/system/study-customfields` | `dim_system_study_customfields_staging` | System reference |
| 136 | System Organizations | `/api/v1/system/organizations` | `dim_system_organizations_staging` | System reference |
| 137 | Sponsor Divisions | `/api/v1/sponsor-divisions` | `dim_sponsor_divisions_staging` | Reference data |
| 138 | Sponsor Teams | `/api/v1/sponsor-teams` | `dim_sponsor_teams_staging` | Reference data |
| 139 | Monitors | `/api/v1/monitors` | `dim_monitors_staging` | Reference data |
| 140 | Room Groups | `/api/v1/room-groups` | `dim_room_groups_staging` | Reference data |
| 158 | Instance Details | `/api/v1/instance/details` | `dim_instance_details_staging` | Instance metadata |
| 159 | Instance Topology | `/api/v1/instance/topology` | `dim_instance_topology_staging` | Instance metadata |
| 173 | Study Types | `/api/v1/study-types` | `dim_study_types_staging` | Reference data |

**Total**: 26 jobs (all can run in parallel)

---

### Phase 1: Core Entities (Depends on Phase 0)
**Execute After Phase 0 - Can Run in Parallel**

| Job ID | Name | Endpoint | Target Table | Dependencies |
|--------|------|----------|--------------|--------------|
| 2 | Studies | `/api/v1/studies/odata` | `dim_studies_staging` | None (but benefits from Phase 0) |
| 164 | Studies List | `/api/v1/studies` | `dim_studies_staging` | None |
| 3 | Patients | `/api/v1/patients/odata` | `dim_patients_staging` | None |
| 8 | Elements | `/api/v1/elements/odata` | `dim_elements_staging` | None |
| 9 | PatientVisits | `/api/v1/patient-visits/odata` | `dim_patient_visits_staging` | None |
| 25 | Appointments | `/api/v1/appointments/odata` | `dim_appointments_staging` | None |
| 26 | Staff | `/api/v1/staff/odata` | `dim_staff_staging` | None |
| 32 | Providers | `/api/v1/providers/odata` | `dim_providers_staging` | None |
| 33 | Rooms | `/api/v1/rooms/odata` | `dim_rooms_staging` | None |
| 34 | Schedules | `/api/v1/schedules/odata` | `dim_schedules_staging` | None |
| 31 | Engagements | `/api/v1/engagements/odata` | `dim_engagements_staging` | None |
| 167 | Action Unit Completions | `/api/v1/action-unit-completions/odata` | `dim_action_unit_completions_staging` | None |
| 168 | Invoices | `/api/v1/invoices/odata` | `dim_invoices_staging` | None |
| 169 | Prospects | `/api/v1/prospects/odata` | `dim_prospects_staging` | None |
| 170 | Remittances | `/api/v1/remittances/odata` | `dim_remittances_staging` | None |
| 171 | Remittance Notes | `/api/v1/remittance-notes/odata` | `dim_remittance_notes_staging` | None |
| 172 | Site Payments | `/api/v1/site-payments/odata` | `dim_site_payments_staging` | None |
| 176 | Patient Payments | `/api/v1/patient-payments/odata` | `dim_patient_payments_staging` | None |

**Total**: 18 jobs (all can run in parallel)

---

### Phase 2: Study-Dependent Jobs (Depends on Phase 1 - Studies)
**Execute After Studies Complete - Parameterized by Study ID**

| Job ID | Name | Endpoint | Target Table | Parameter Source |
|--------|------|----------|--------------|------------------|
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
| 141 | Study Arms | `/api/v1/studies/{studyId}/arms` | `dim_study_arms_staging` | `dim_studies_staging.id` |
| 142 | Study Protocol Versions | `/api/v1/studies/{studyId}/protocol-versions` | `dim_study_protocol_versions_staging` | `dim_studies_staging.data->>'id'` |
| 144 | Study Personnel | `/api/v1/studies/{studyId}/personnel` | `dim_study_personnel_staging` | `dim_studies_staging.data->>'id'` |
| 145 | Study Warnings | `/api/v1/studies/{studyId}/warnings` | `dim_study_warnings_staging` | `dim_studies_staging.data->>'id'` |
| 165 | Study Detail | `/api/v1/studies/{studyId}` | `dim_study_detail_staging` | None (but needs studies) |
| 174 | Study Visit Arms | `/api/v1/studies/{studyId}/visit-arms/odata` | `dim_study_visit_arms_staging` | `dim_studies_staging.id` |
| 175 | Visit Elements by Study | `/api/v1/studies/{studyId}/visit-elements/odata` | `dim_visit_element_relationships_staging` | `dim_studies_staging.id` |

**Total**: 19 jobs (parameterized, can run in parallel per study)

---

### Phase 3: Patient-Dependent Jobs (Depends on Phase 1 - Patients)
**Execute After Patients Complete - Parameterized by Patient ID**

| Job ID | Name | Endpoint | Target Table | Parameter Source |
|--------|------|----------|--------------|------------------|
| 147 | Patient Devices | `/api/v1/patients/{patientId}/devices` | `dim_patient_devices_staging` | `dim_patients_staging.data->>'id'` |
| 148 | Patient Allergies | `/api/v1/patients/{patientId}/allergies` | `dim_patient_allergies_staging` | `dim_patients_staging.data->>'id'` |
| 149 | Patient Providers | `/api/v1/patients/{patientId}/providers` | `dim_patient_providers_staging` | `dim_patients_staging.data->>'id'` |
| 150 | Patient Conditions | `/api/v1/patients/{patientId}/conditions` | `dim_patient_conditions_staging` | `dim_patients_staging.data->>'id'` |
| 151 | Patient Procedures | `/api/v1/patients/{patientId}/procedures` | `dim_patient_procedures_staging` | `dim_patients_staging.data->>'id'` |
| 152 | Patient Medications | `/api/v1/patients/{patientId}/medications` | `dim_patient_medications_staging` | `dim_patients_staging.data->>'id'` |
| 153 | Patient Immunizations | `/api/v1/patients/{patientId}/immunizations` | `dim_patient_immunizations_staging` | `dim_patients_staging.data->>'id'` |
| 154 | Patient Family History | `/api/v1/patients/{patientId}/family-history` | `dim_patient_family_history_staging` | `dim_patients_staging.data->>'id'` |
| 155 | Patient Social History | `/api/v1/patients/{patientId}/social-history` | `dim_patient_social_history_staging` | `dim_patients_staging.data->>'id'` |
| 156 | Patient Campaign Touches | `/api/v1/patients/{patientId}/touches/campaign` | `dim_patient_campaign_touches_staging` | `dim_patients_staging.data->>'id'` |
| 157 | Patient Referral Touches | `/api/v1/patients/{patientId}/touches/referral` | `dim_patient_referral_touches_staging` | `dim_patients_staging.data->>'id'` |

**Total**: 11 jobs (parameterized, can run in parallel per patient)

---

### Phase 4: Subject-Dependent Jobs (Depends on Phase 2 - Subjects)
**Execute After Subjects Complete - Parameterized by Subject ID**

| Job ID | Name | Endpoint | Target Table | Parameter Source |
|--------|------|----------|--------------|------------------|
| 160 | Subject Patient Visits | `/api/v1/studies/{studyId}/subjects/{subjectId}/patient-visits` | `dim_patient_visits_staging` | `dim_subjects_staging.data->>'id'` |

**Total**: 1 job (parameterized)

---

### Phase 5: Patient Visit-Dependent Jobs (Depends on Phase 1/4 - Patient Visits)
**Execute After Patient Visits Complete - Parameterized by Patient Visit ID**

| Job ID | Name | Endpoint | Target Table | Parameter Source |
|--------|------|----------|--------------|------------------|
| 24 | PatientVisitElements | `/api/v1/patient-visits/{patientVisitId}/elements/odata` | `dim_patient_visit_elements_staging` | `dim_patient_visits_staging.id` |
| 161 | Patient Visit Stipends | `/api/v1/patient-visits/{patientVisitId}/stipends/odata` | `dim_patient_visit_stipends_staging` | `dim_patient_visits_staging.data->>'id'` |
| 166 | Patient Visit Elements | `/api/v1/patient-visits/{patientVisitId}/elements/odata` | `dim_visit_elements_staging` | `dim_patient_visits_staging.data->>'id'` |

**Total**: 3 jobs (parameterized, can run in parallel per visit)

---

## Incremental Loading Analysis

### API Support for Timestamp Filtering

**Status**: ⚠️ **VERIFICATION NEEDED**

The Clinical Conductor API documentation indicates:
- Most entities include `modifiedDate` or similar timestamp fields
- OData `$filter` supports date comparisons
- Recommended pattern: `?$filter=modifiedDate gt {last_run_timestamp}`

### Field Name Verification Required

Before implementing incremental loading, verify the actual field names in API responses:

**Potential Field Names** (to test):
- `modifiedDate`
- `modifiedOn`
- `lastModified`
- `updatedAt`
- `updatedDate`
- `changedDate`
- `createdDate` (for new records only)

### Jobs Likely Supporting Incremental Loading

**Non-Parameterized Jobs** (Full Load with Filter):
- ✅ Sites (Job 1)
- ✅ Studies (Job 2, 164)
- ✅ Patients (Job 3)
- ✅ PatientVisits (Job 9)
- ✅ Appointments (Job 25)
- ✅ Staff (Job 26)
- ✅ Elements (Job 8)
- ✅ Providers (Job 32)
- ✅ Rooms (Job 33)
- ✅ Schedules (Job 34)
- ✅ Engagements (Job 31)
- ✅ All System Reference Jobs (Jobs 120-136)
- ✅ All Financial Jobs (Jobs 167-176)

**Parameterized Jobs** (Per-Parent Filter):
- ✅ All Study-Dependent Jobs (Jobs 10-29, 141-145, 174-175)
- ✅ All Patient-Dependent Jobs (Jobs 147-157)
- ✅ All Patient Visit-Dependent Jobs (Jobs 24, 161, 166)
- ✅ Subject Patient Visits (Job 160)

### Implementation Strategy

**For Non-Parameterized Jobs**:
```python
# Get last successful run timestamp
last_run = get_last_successful_run(job_id)
if last_run and last_run.completed_at:
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
    last_run = get_last_successful_run(
        job_id, 
        parameters={'studyId': study.id}
    )
    if last_run and last_run.completed_at:
        filter_date = last_run.completed_at.isoformat()
        params = ODataParams(
            filter=f"modifiedDate gt {filter_date}"
        )
    else:
        params = None
    
    # Fetch with filter
    fetch_data(endpoint, params=params)
```

### Next Steps for Incremental Loading

1. **Test API Responses**: Inspect actual responses to identify timestamp field names
2. **Test OData Filter Syntax**: Verify date format requirements
3. **Implement Filter Logic**: Add to `JobExecutor._fetch_and_load()`
4. **Add Configuration**: Allow per-job enable/disable of incremental loading
5. **Add Monitoring**: Track incremental vs full load statistics

---

## Recommended Execution Schedule

### Daily Full Refresh (Weekly Recommended)

**Phase 0** (Reference Data - Run Daily at 1:00 AM):
- All system reference jobs
- Sites, Sponsors, Study Types
- Instance metadata

**Phase 1** (Core Entities - Run Daily at 2:00 AM):
- Studies, Patients, PatientVisits
- Appointments, Staff, Elements
- All non-parameterized core entities

**Phase 2** (Study-Dependent - Run Daily at 3:00 AM):
- Subjects, Visits, StudyDocuments
- All study-specific data
- Parallel execution per study

**Phase 3** (Patient-Dependent - Run Daily at 4:00 AM):
- Patient medical history
- Patient relationships
- Parallel execution per patient

**Phase 4** (Subject-Dependent - Run Daily at 5:00 AM):
- Subject-specific patient visits

**Phase 5** (Visit-Dependent - Run Daily at 6:00 AM):
- Visit elements and stipends
- Parallel execution per visit

### Incremental Refresh (Recommended Daily)

**Same phases, but with `modifiedDate` filters**:
- Only fetch records modified since last successful run
- Reduces API load by 80-95% for most jobs
- Maintains data freshness
- Faster execution times

---

## Implementation Priority

1. **Immediate**: Clean up stuck jobs and verify current runs
2. **Short-term**: Implement dependency-aware orchestration
3. **Medium-term**: Add incremental loading support
4. **Long-term**: Add monitoring and alerting for job failures

---

## Notes

- **Parameterized Jobs**: These jobs require parent entities to exist first
- **Parallel Execution**: Within each phase, jobs can run in parallel
- **Rate Limiting**: Respect API rate limits (currently 5 RPS)
- **Error Handling**: Failed upstream jobs should skip downstream jobs
- **Monitoring**: Track execution times and success rates per phase

