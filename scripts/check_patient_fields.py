#!/usr/bin/env python3
"""Check what fields are available in a Patient record."""

import os
import json
import sys

os.environ["ENVIRONMENT"] = "production"
os.environ["DRY_RUN"] = "false"

from src.api.client import ClinicalConductorClient
from src.config import get_settings

settings = get_settings()
client = ClinicalConductorClient()

# Fetch one patient record
print("Fetching one patient record to check available fields...")
try:
    page = next(client.get_odata("/api/v1/patients/odata", page_mode="iterator", dry_run=False))
    if page.items and len(page.items) > 0:
        patient = page.items[0]
        print("\n✅ Patient record fields:")
        print(json.dumps(patient, indent=2, default=str))
        
        # Look for timestamp fields
        print("\n📅 Timestamp fields found:")
        timestamp_fields = []
        for key, value in patient.items():
            if any(ts in key.lower() for ts in ['date', 'time', 'modified', 'updated', 'created', 'changed']):
                timestamp_fields.append((key, value))
                print(f"  - {key}: {value}")
        
        if not timestamp_fields:
            print("  ⚠️  No timestamp fields found!")
    else:
        print("❌ No patient records found")
except Exception as e:
    print(f"❌ Error: {e}")

