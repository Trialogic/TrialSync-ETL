# Clinical Conductor API OData Limits

**Date**: January 2, 2026  
**Source**: Clinical Conductor API Documentation  
**Status**: ✅ **Enforced in Code**

---

## ⚠️ Critical Limits

### Supported OData Parameters

The Clinical Conductor API supports the following OData query parameters:

- ✅ `$filter` - Filter results
- ✅ `$top` - Limit number of records returned
- ✅ `$skip` - Skip records for pagination
- ✅ `$count` - Get total count of records
- ✅ `$orderby` - Sort results

### Record Limit and Page Size

**Default Behavior:**
- **Default page size**: 50 records per request
- Any request will stop after 50 records unless `$top` is explicitly set

**Maximum Limits:**
- **Maximum page size**: 1000 records per request
- This is a hard limit enforced by the API
- Requests with `$top > 1000` will be rejected or truncated

**Best Practice:**
- Use `$top=1000` for maximum efficiency when fetching large datasets
- This minimizes the number of API calls needed
- Reduces overall execution time for large jobs

---

## Impact on ETL Jobs

### Current Implementation

The ETL system automatically enforces these limits:

1. **Default `$top` value**: 100 (within limits ✅)
2. **Maximum enforcement**: Code automatically caps `$top` at 1000
3. **Validation**: Warnings logged if limits are exceeded

### Performance Optimization

**Before (default 100):**
- Patients (152,836 records): ~1,529 API calls
- PatientVisits (2,297,271 records): ~22,973 API calls

**After (using 1000):**
- Patients (152,836 records): ~153 API calls (10x fewer)
- PatientVisits (2,297,271 records): ~2,298 API calls (10x fewer)

**Recommendation**: Consider increasing `default_top` to 1000 for better performance.

---

## Code Enforcement

### API Client Validation

The `ClinicalConductorClient` class automatically enforces limits:

```python
# In src/api/client.py
if params.top > 1000:
    logger.warning("CC API maximum is 1000, capping to 1000")
    params.top = 1000
```

### Configuration

Current default can be changed in `ClinicalConductorClient` initialization:

```python
from src.api import ClinicalConductorClient

# Use maximum for better performance
client = ClinicalConductorClient(default_top=1000)
```

---

## Examples

### Correct Usage

```python
# ✅ Good: Within limits
params = ODataParams(top=1000)  # Maximum allowed

# ✅ Good: Default (100)
params = ODataParams()  # Uses default_top (100)

# ✅ Good: Small request
params = ODataParams(top=50)  # Within limits
```

### Incorrect Usage (Auto-Corrected)

```python
# ⚠️ Will be capped to 1000
params = ODataParams(top=5000)  # Exceeds maximum, auto-capped

# ⚠️ Will be set to 1
params = ODataParams(top=0)  # Too low, auto-corrected
```

---

## Troubleshooting

### Jobs Getting Stuck

If jobs are getting stuck, check:

1. **Page size too small**: Using default 50 instead of 1000 can cause many API calls
2. **API rate limiting**: Too many requests due to small page size
3. **Timeout issues**: Large number of API calls may exceed timeout

**Solution**: Increase `default_top` to 1000 for better performance.

### API Errors

If you see errors about record limits:

1. **Check `$top` value**: Ensure it's ≤ 1000
2. **Check logs**: Look for "top_exceeds_maximum" warnings
3. **Verify API response**: API may truncate results silently

---

## Related Documentation

- `docs/01_Clinical_Conductor_API_Reference.md` - Full API reference
- `src/api/client.py` - Implementation details
- `docs/CHECKPOINT_AND_RESUME.md` - Job execution patterns

---

## Summary

✅ **Limits Documented**: Default 50, Maximum 1000  
✅ **Code Enforcement**: Automatic validation and capping  
✅ **Performance Impact**: Using 1000 reduces API calls by 10x  
✅ **Best Practice**: Use `$top=1000` for large datasets  

---

*Last Updated: January 2, 2026*

