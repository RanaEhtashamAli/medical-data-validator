"""
Shared utilities for the medical data validator.
"""

import hashlib
from typing import Any

import numpy as np


# Canonical PHI patterns shared across HIPAAComplianceChecker, ComplianceEngine,
# and PHIDetector so all three enforce the same rules.
PHI_PATTERNS = {
    'ssn': r'\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b',
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    'date': r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b',
    'address': r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b',
    'medical_record': r'\bMRN\s*\d+\b|\bMedical\s*Record\s*\d+\b',
    'account_number': r'\bAccount\s*#?\s*\d+\b|\bAcct\s*#?\s*\d+\b',
    'insurance_id': r'\bInsurance\s*ID\s*\d+\b|\bPolicy\s*#\s*\d+\b',
    'license_number': r'\bLicense\s*#\s*\d+\b|\bLic\s*#\s*\d+\b',
    'vehicle_id': r'\bVIN\s*\d+\b|\bVehicle\s*ID\s*\d+\b',
    'device_id': r'\bDevice\s*ID\s*\d+\b|\bSerial\s*#\s*\d+\b',
    'ip_address': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
    'url': r'\bhttps?://[^\s]+\b',
    'biometric': r'\bFingerprint|Retina|Iris|Voice\s*Pattern\b',
    'names': r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',
}


def convert_numpy_types(obj: Any) -> Any:
    """Recursively convert numpy scalar/array types to native Python types for JSON serialisation."""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {str(k): convert_numpy_types(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_numpy_types(v) for v in obj]
    return obj


def dataframe_fingerprint(df) -> str:
    """Return a stable, deterministic hex digest that identifies a DataFrame's content.

    Uses hashlib (not Python's built-in hash()) so the result is consistent
    across process restarts and worker processes regardless of PYTHONHASHSEED.
    """
    import pandas as pd
    shape_part = f"{df.shape[0]}x{df.shape[1]}"
    cols_part = ",".join(sorted(df.columns.astype(str)))
    sample_part = df.head(10).to_csv(index=False)
    raw = f"{shape_part}|{cols_part}|{sample_part}"
    return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()
