# Clinical Conductor API Reference Guide

**Document Version**: 1.0  
**Last Updated**: December 15, 2025  
**Author**: Manus AI  
**Purpose**: Comprehensive reference for Clinical Conductor API endpoints, validation status, and integration patterns

---

## Table of Contents

1. [API Overview](#api-overview)
2. [Authentication](#authentication)
3. [Validated Endpoints](#validated-endpoints)
4. [Invalid Endpoints](#invalid-endpoints)
5. [Endpoint Categories](#endpoint-categories)
6. [OData Query Patterns](#odata-query-patterns)
7. [Response Schemas](#response-schemas)
8. [Rate Limiting and Best Practices](#rate-limiting-and-best-practices)

---

## API Overview

The Clinical Conductor API provides RESTful access to clinical trial management data hosted at Tekton Research's instance.

### Base Configuration

| Property | Value |
|----------|-------|
| **Base URL** | `https://tektonresearch.clinicalconductor.com/CCSWEB` |
| **API Version** | v1 |
| **Authentication Method** | API Key (X-ApiKey header) |
| **Response Format** | JSON |
| **OData Support** | Yes (most list endpoints) |
| **OpenAPI Spec** | Available at `/api/docs` |

### Instance Details

The Tekton Research instance has been validated to contain:
- **Studies**: 157,270 records
- **Patients**: 152,836 records  
- **Patient Visits**: 2,297,271 records
- **Subjects**: 88,773 records
- **Appointments**: 860,893 records
- **Visit Elements**: 2,090,584 records

---

## Authentication

All API requests require authentication using an API key passed in the request header.

### Header Format

```http
X-ApiKey: 9ba73e89-0423-47c1-a50c-b78c7034efea
```

### Credential Storage

API credentials are stored in the `dw_api_credentials` table:

```sql
SELECT id, name, base_url, api_key, is_active
FROM dw_api_credentials
WHERE name = 'Tekton Research';
```

**Security Note**: The API key is stored in plaintext in the database. Access to the database should be restricted and encrypted connections should be used.

---

## Validated Endpoints

The following endpoints have been tested and verified as functional. They return HTTP 200 and valid JSON data.

### Core Entity Endpoints (Non-Parameterized)

These endpoints return all records without requiring path parameters:

| Endpoint | Records | Status | Notes |
|----------|---------|--------|-------|
| `/api/v1/studies/odata` | 157,270 | ✅ Valid | Primary study list |
| `/api/v1/patients/odata` | 152,836 | ✅ Valid | All patients |
| `/api/v1/patient-visits/odata` | 2,297,271 | ✅ Valid | All patient visits |
| `/api/v1/elements/odata` | 31,672 | ✅ Valid | Study elements/procedures |
| `/api/v1/sites/odata` | 320 | ✅ Valid | Clinical sites |
| `/api/v1/providers/odata` | 398 | ✅ Valid | Healthcare providers |
| `/api/v1/rooms/odata` | 116 | ✅ Valid | Facility rooms |
| `/api/v1/schedules/odata` | 20 | ✅ Valid | Scheduling templates |
| `/api/v1/sponsors/odata` | 798 | ✅ Valid | Study sponsors |
| `/api/v1/appointments/odata` | 860,893 | ✅ Valid | All appointments |
| `/api/v1/staff/odata` | 2,617 | ✅ Valid | Staff members |
| `/api/v1/invoices/odata` | 0 | ✅ Valid | Financial invoices |
| `/api/v1/prospects/odata` | 0 | ✅ Valid | Recruitment prospects |
| `/api/v1/remittances/odata` | 0 | ✅ Valid | Payment remittances |
| `/api/v1/remittance-notes/odata` | 0 | ✅ Valid | Remittance notes |
| `/api/v1/site-payments/odata` | 0 | ✅ Valid | Site payment records |
| `/api/v1/patient-payments/odata` | 0 | ✅ Valid | Patient stipend payments |
| `/api/v1/action-unit-completions/odata` | 0 | ✅ Valid | Action completions (CCE only) |

### Study-Scoped Endpoints (Parameterized by studyId)

These endpoints require a `{studyId}` path parameter and return data for a specific study:

| Endpoint | Status | Notes |
|----------|--------|-------|
| `/api/v1/studies/{studyId}/subjects/odata` | ✅ Valid | Subjects enrolled in study |
| `/api/v1/studies/{studyId}/visits/odata` | ✅ Valid | Study visit definitions |
| `/api/v1/studies/{studyId}/documents/odata` | ✅ Valid | Study documents |
| `/api/v1/studies/{studyId}/actions/odata` | ✅ Valid | Study actions/tasks |
| `/api/v1/studies/{studyId}/milestones/odata` | ✅ Valid | Study milestones |
| `/api/v1/studies/{studyId}/notes/odata` | ✅ Valid | Study notes |
| `/api/v1/studies/{studyId}/monitor-queries/odata` | ✅ Valid | Monitor queries (NOT `/queries`) |
| `/api/v1/studies/{studyId}/arms` | ✅ Valid | Study arms (NOT `/visit-arms`) |
| `/api/v1/studies/{studyId}/protocol-versions` | ✅ Valid | Protocol versions |
| `/api/v1/studies/{studyId}/roles` | ✅ Valid | Study role assignments |
| `/api/v1/studies/{studyId}/personnel` | ✅ Valid | Study personnel |
| `/api/v1/studies/{studyId}/warnings` | ✅ Valid | Study warnings |
| `/api/v1/studies/{studyId}/elements/odata` | ✅ Valid | Elements specific to study |
| `/api/v1/studies/{studyId}/visits/{visitId}/elements/odata` | ✅ Valid | Elements for specific visit |

### Patient-Scoped Endpoints (Parameterized by patientId)

These endpoints require a `{patientId}` path parameter:

| Endpoint | Records | Status | Notes |
|----------|---------|--------|-------|
| `/api/v1/patients/{patientId}/allergies` | 674 | ✅ Valid | Patient allergies |
| `/api/v1/patients/{patientId}/conditions` | 0 | ✅ Valid | Patient conditions |
| `/api/v1/patients/{patientId}/devices` | 99 | ✅ Valid | Medical devices |
| `/api/v1/patients/{patientId}/immunizations` | 0 | ✅ Valid | Immunization records |
| `/api/v1/patients/{patientId}/medications` | 899 | ✅ Valid | Current medications |
| `/api/v1/patients/{patientId}/procedures` | 0 | ✅ Valid | Medical procedures |
| `/api/v1/patients/{patientId}/social-history` | 0 | ✅ Valid | Social history |
| `/api/v1/patients/{patientId}/family-history` | 0 | ✅ Valid | Family medical history |
| `/api/v1/patients/{patientId}/providers` | 0 | ✅ Valid | Patient's providers |
| `/api/v1/patients/{patientId}/touches/campaign` | 554 | ✅ Valid | Campaign interactions |
| `/api/v1/patients/{patientId}/touches/referral` | 28 | ✅ Valid | Referral interactions |

### Patient Visit Endpoints (Parameterized by patientVisitId)

| Endpoint | Status | Notes |
|----------|--------|-------|
| `/api/v1/patient-visits/{patientVisitId}/elements/odata` | ✅ Valid | Visit element data |
| `/api/v1/patient-visits/{patientVisitId}/stipends/odata` | ✅ Valid | Visit stipend payments |

### System/Reference Data Endpoints

These endpoints return system-wide reference data:

| Endpoint | Records | Status |
|----------|---------|--------|
| `/api/v1/system/allergies/odata` | 1,873 | ✅ Valid |
| `/api/v1/system/conditions/odata` | 405 | ✅ Valid |
| `/api/v1/system/medications/odata` | 2,296 | ✅ Valid |
| `/api/v1/system/procedures/odata` | 672 | ✅ Valid |
| `/api/v1/system/immunizations/odata` | 79 | ✅ Valid |
| `/api/v1/system/devices/odata` | 3,295 | ✅ Valid |
| `/api/v1/system/social-history/odata` | 121 | ✅ Valid |
| `/api/v1/system/document-types` | 20 | ✅ Valid |
| `/api/v1/system/action-categories` | 30 | ✅ Valid |
| `/api/v1/system/study-categories` | 106 | ✅ Valid |
| `/api/v1/system/study-subcategories` | 8 | ✅ Valid |
| `/api/v1/system/study-statuses/odata` | 15 | ✅ Valid |
| `/api/v1/system/lookup-lists` | 108 | ✅ Valid |
| `/api/v1/system/patient-customfields` | 18 | ✅ Valid |
| `/api/v1/system/study-customfields` | 0 | ✅ Valid |
| `/api/v1/system/organizations` | 1 | ✅ Valid |
| `/api/v1/subject-statuses/odata` | 119,749 | ✅ Valid |
| `/api/v1/sponsor-divisions` | 548 | ✅ Valid |
| `/api/v1/sponsor-teams` | 546 | ✅ Valid |
| `/api/v1/monitors` | 68 | ✅ Valid |
| `/api/v1/room-groups` | 0 | ✅ Valid |
| `/api/v1/study-types` | 0 | ✅ Valid |

### Instance Metadata Endpoints

| Endpoint | Status | Notes |
|----------|--------|-------|
| `/api/v1/instance/details` | ✅ Valid | Instance configuration |
| `/api/v1/instance/topology` | ✅ Valid | System topology |

---

## Invalid Endpoints

The following endpoints **do not exist** in the Clinical Conductor API and return HTTP 404 errors. ETL jobs using these endpoints should be disabled or corrected.

### Confirmed Non-Existent Endpoints

| Endpoint | Job ID | Status | Recommendation |
|----------|--------|--------|----------------|
| `/api/v1/studies/{studyId}/screenings/odata` | 14 | ❌ Invalid | **Disable job** |
| `/api/v1/studies/{studyId}/enrollments/odata` | 15 | ❌ Invalid | **Disable job** |
| `/api/v1/studies/{studyId}/randomizations/odata` | 16 | ❌ Invalid | **Disable job** |
| `/api/v1/studies/{studyId}/withdrawals/odata` | 17 | ❌ Invalid | **Disable job** |
| `/api/v1/studies/{studyId}/concomitant-medications/odata` | 20 | ❌ Invalid | **Disable job** |
| `/api/v1/studies/{studyId}/queries/odata` | 23 | ❌ Invalid | **Use `/monitor-queries` instead** |
| `/api/v1/studies/{studyId}/visit-arms/odata` | 174 | ❌ Invalid | **Use `/arms` instead** |
| `/api/v1/studies/{studyId}/visit-elements/odata` | 175 | ❌ Invalid | **Use `/visits/{visitId}/elements` instead** |
| `/api/v1/studies/{studyId}/forms/odata` | 12 | ❌ Invalid | **Disable job** |
| `/api/v1/studies/{studyId}/protocol-deviations/odata` | 18 | ❌ Invalid | **Disable job** |
| `/api/v1/studies/{studyId}/adverse-events/odata` | 19 | ❌ Invalid | **Disable job** |
| `/api/v1/studies/{studyId}/lab-results/odata` | 21 | ❌ Invalid | **Disable job** |
| `/api/v1/studies/{studyId}/vitals/odata` | 22 | ❌ Invalid | **Disable job** |
| `/api/v1/users/odata` | 4 | ❌ Invalid | **Disable job** |
| `/api/v1/roles/odata` | 5 | ❌ Invalid | **Disable job** |
| `/api/v1/departments/odata` | 6 | ❌ Invalid | **Disable job** |
| `/api/v1/audits/odata` | 7 | ❌ Invalid | **Disable job** |
| `/api/v1/monitor-queries/odata` | 30 | ⚠️ CCE-only | Returns 501 (not implemented in CC) |
| `/api/v1/engagements/odata` | 31 | ⚠️ CCE-only | Returns 501 (not implemented in CC) |

### Endpoint Corrections

| Incorrect Endpoint | Correct Endpoint | Action Required |
|--------------------|------------------|-----------------|
| `/api/v1/studies/{studyId}/queries/odata` | `/api/v1/studies/{studyId}/monitor-queries/odata` | Update job #23 |
| `/api/v1/studies/{studyId}/visit-arms/odata` | `/api/v1/studies/{studyId}/arms` | Update job #174 |
| `/api/v1/studies/{studyId}/visit-elements/odata` | `/api/v1/studies/{studyId}/visits/{visitId}/elements/odata` | Update job #175 (requires nested params) |

---

## Endpoint Categories

### By Data Type

**Dimension Tables (Master Data)**:
- Studies, Patients, Sites, Providers, Staff, Sponsors
- Elements, Visits, Rooms, Schedules
- System reference data (allergies, medications, conditions, etc.)

**Fact Tables (Transactional Data)**:
- Patient Visits, Appointments
- Visit Elements, Patient Visit Elements
- Subject Statuses, Patient Touches
- Invoices, Payments, Remittances

**Hierarchical/Nested Data**:
- Study → Subjects → Patient Visits
- Study → Visits → Elements
- Patient → Allergies/Medications/Conditions

### By Parameterization

**Non-Parameterized** (57 endpoints):
- Direct access, no path parameters required
- Examples: `/api/v1/studies/odata`, `/api/v1/patients/odata`

**Parameterized** (40 endpoints):
- Require parent entity ID in path
- Examples: `/api/v1/studies/{studyId}/subjects/odata`
- Require iteration through parent records

---

## OData Query Patterns

Most list endpoints support OData query parameters for filtering, sorting, and pagination.

### Supported OData Parameters

| Parameter | Purpose | Example |
|-----------|---------|---------|
| `$top` | Limit results | `?$top=100` |
| `$skip` | Skip records (pagination) | `?$skip=100` |
| `$filter` | Filter results | `?$filter=status eq 'Active'` |
| `$orderby` | Sort results | `?$orderby=createdDate desc` |
| `$select` | Select specific fields | `?$select=id,name,status` |
| `$expand` | Include related entities | `?$expand=study,site` |
| `$count` | Include total count | `?$count=true` |

### Example Queries

**Get first 100 active studies**:
```
GET /api/v1/studies/odata?$top=100&$filter=status eq 'Active'
```

**Get patients created after a date**:
```
GET /api/v1/patients/odata?$filter=createdDate gt 2025-01-01
```

**Pagination (page 2, 100 per page)**:
```
GET /api/v1/appointments/odata?$top=100&$skip=100
```

### OData Response Format

```json
{
  "@odata.context": "https://tektonresearch.clinicalconductor.com/CCSWEB/api/v1/$metadata#Studies",
  "@odata.count": 157270,
  "value": [
    {
      "id": 1,
      "name": "Study Name",
      "status": "Active",
      ...
    }
  ]
}
```

---

## Response Schemas

### Common Field Patterns

Most entities include these standard fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Primary key |
| `uid` | string (uuid) | Global unique identifier |
| `createdDate` | datetime | Record creation timestamp |
| `modifiedDate` | datetime | Last modification timestamp |
| `createdBy` | object | User who created record |
| `modifiedBy` | object | User who last modified record |

### Key Entity Schemas

**Study**:
```json
{
  "id": 2388,
  "name": "Study Name",
  "status": "07. Enrollment",
  "sponsor": { "id": 123, "name": "Sponsor Name" },
  "site": { "id": 456, "name": "Site Name" },
  "principalInvestigator": { "id": 789, "name": "PI Name" },
  "startDate": "2024-01-15T00:00:00",
  "expectedCompletionDate": "2026-12-31T00:00:00"
}
```

**Patient**:
```json
{
  "id": 12345,
  "firstName": "John",
  "lastName": "Doe",
  "dateOfBirth": "1980-05-15",
  "gender": "Male",
  "email": "john.doe@example.com",
  "phone": "555-1234",
  "site": { "id": 456, "name": "Site Name" }
}
```

**Patient Visit**:
```json
{
  "id": 98765,
  "patient": { "id": 12345, "name": "John Doe" },
  "visit": { "id": 111, "name": "Week 4 Visit" },
  "scheduledDate": "2025-02-01T10:00:00",
  "actualDate": "2025-02-01T10:15:00",
  "status": "Completed",
  "room": { "id": 5, "name": "Exam Room 1" }
}
```

**Invoice**:
```json
{
  "id": 5001,
  "invoiceName": "INV-2025-001",
  "invoiceDate": "2025-01-15T00:00:00",
  "invoiceAmount": 15000.00,
  "currency": "USD",
  "recipient": {
    "id": 123,
    "name": "Site Name",
    "type": "Site"
  },
  "study": {
    "id": 2388,
    "name": "Study Name"
  },
  "lineItems": [
    {
      "description": "Patient Visit - Week 4",
      "quantity": 10,
      "unitPrice": 1500.00,
      "totalAmount": 15000.00
    }
  ]
}
```

**Remittance**:
```json
{
  "id": 3001,
  "amount": 50000.00,
  "checkNumber": "CHK-12345",
  "receivedDate": "2025-01-20T00:00:00",
  "currencyCode": "USD",
  "payer": {
    "id": 456,
    "name": "Sponsor Name",
    "type": "Sponsor"
  },
  "categories": [
    { "id": 1, "name": "Clinical Services" }
  ],
  "invoices": [
    {
      "invoiceId": 5001,
      "totalAppliedAmount": 15000.00
    }
  ]
}
```

Full schema definitions are available in the OpenAPI specification at `/home/ubuntu/cc_openapi.json`.

---

## Rate Limiting and Best Practices

### Rate Limits

Clinical Conductor does not publicly document rate limits, but based on ETL execution patterns:

- **Recommended**: Max 10 requests per second
- **Batch Size**: 1000 records per request using `$top=1000`
- **Timeout**: 60 seconds for large queries
- **Retry Logic**: Exponential backoff on 429/503 errors

### Best Practices

**Pagination for Large Datasets**:
```python
top = 1000
skip = 0
while True:
    response = requests.get(
        f"{base_url}/api/v1/patients/odata?$top={top}&$skip={skip}",
        headers={"X-ApiKey": api_key}
    )
    data = response.json()
    records = data.get('value', [])
    if not records:
        break
    # Process records
    skip += top
```

**Parameterized Job Pattern**:
```python
# Get parent IDs
studies = get_all_studies()

# Iterate through each parent
for study in studies:
    study_id = study['id']
    endpoint = f"/api/v1/studies/{study_id}/subjects/odata"
    subjects = fetch_data(endpoint)
    # Process subjects
```

**Error Handling**:
```python
def fetch_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=60)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"Endpoint not found: {url}")
                return None
            elif response.status_code in [429, 503]:
                wait_time = 2 ** attempt
                time.sleep(wait_time)
                continue
            else:
                response.raise_for_status()
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on attempt {attempt + 1}")
            if attempt == max_retries - 1:
                raise
    return None
```

**Data Freshness**:
- Most entities include `modifiedDate` field
- Use incremental loads: `?$filter=modifiedDate gt {last_run_timestamp}`
- Full refresh recommended weekly for dimension tables

---

## Appendix: OpenAPI Specification

The complete OpenAPI specification is stored at:
- **Local Path**: `/home/ubuntu/cc_openapi.json`
- **Remote URL**: `https://tektonresearch.clinicalconductor.com/CCSWEB/api/docs`

To extract endpoint details programmatically:

```python
import json

with open('/home/ubuntu/cc_openapi.json', 'r') as f:
    spec = json.load(f)

# List all endpoints
for path in spec['paths']:
    methods = list(spec['paths'][path].keys())
    print(f"{path} [{', '.join(methods)}]")

# Get schema for an entity
schema = spec['definitions']['StudyViewModel']
properties = schema['properties']
```

---

**Document End**
