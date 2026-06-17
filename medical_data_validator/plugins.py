"""
Built-in ComplianceStandard plugins and plugin-discovery SDK (Phase 3e/3f).

Provides two ready-to-use plugins and a discovery mechanism that loads any
third-party plugins registered under the 'medical_data_validator.compliance_plugins'
setuptools entry-point group.

Usage — built-in plugins:
    from medical_data_validator.compliance import ComplianceEngine
    from medical_data_validator.plugins import FHIRCompliancePlugin, SNOMEDCompliancePlugin

    engine = ComplianceEngine()
    engine.register_plugin(FHIRCompliancePlugin())
    engine.register_plugin(SNOMEDCompliancePlugin())

Usage — auto-discover all installed plugins:
    from medical_data_validator.plugins import load_compliance_plugins
    engine = load_compliance_plugins()          # returns a ComplianceEngine

Usage — third-party plugin package (in its own pyproject.toml):
    [project.entry-points."medical_data_validator.compliance_plugins"]
    my_standard = "my_package.module:MyPlugin"
"""

import re
from typing import List

import pandas as pd

from .compliance import ComplianceStandard, ComplianceViolation


# ── FHIR R4 plugin ────────────────────────────────────────────────────────────

# FHIR R4 resource types that may appear in medical datasets
_FHIR_RESOURCE_TYPES = {
    'Patient', 'Observation', 'Condition', 'MedicationRequest',
    'Encounter', 'Procedure', 'DiagnosticReport', 'AllergyIntolerance',
    'Immunization', 'CarePlan', 'Practitioner', 'Organization',
}

# FHIR date/time pattern: YYYY, YYYY-MM, YYYY-MM-DD, or full datetime
_FHIR_DATE_RE = re.compile(
    r'^\d{4}(-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?)?)?$'
)

# FHIR resource identifier pattern (urn:uuid: or a relative URL like Patient/123)
_FHIR_ID_RE = re.compile(r'^[A-Za-z0-9\-\.]{1,64}$')


class FHIRCompliancePlugin(ComplianceStandard):
    """
    Validates FHIR R4 structural requirements.

    Checks performed:
    - Columns named 'resourceType' must contain valid FHIR R4 resource names.
    - Columns named 'id' must match the FHIR logical-id pattern ([A-Za-z0-9-.]{1,64}).
    - Date/datetime columns that look like FHIR date fields must conform to the
      FHIR date format (YYYY, YYYY-MM, YYYY-MM-DD, or full ISO 8601 with timezone).
    """

    @property
    def name(self) -> str:
        return 'fhir_r4'

    def validate(self, df: pd.DataFrame) -> List[ComplianceViolation]:
        violations: List[ComplianceViolation] = []

        # Check resourceType column
        for col in df.columns:
            if col.lower() in ('resourcetype', 'resource_type'):
                invalid = df[col].dropna().astype(str)
                invalid = invalid[~invalid.isin(_FHIR_RESOURCE_TYPES)]
                if not invalid.empty:
                    sample = ', '.join(invalid.unique()[:3].tolist())
                    violations.append(ComplianceViolation(
                        standard='FHIR R4',
                        rule_id='FHIR_INVALID_RESOURCE_TYPE',
                        severity='high',
                        field=col,
                        message=(
                            f"Column '{col}' contains unrecognised FHIR R4 resource "
                            f"types: {sample}"
                        ),
                        recommendation=(
                            "Use a valid FHIR R4 resource type such as Patient, "
                            "Observation, Condition, etc."
                        ),
                    ))

        # Check id columns
        for col in df.columns:
            if col.lower() == 'id':
                invalid_ids = df[col].dropna().astype(str)
                invalid_ids = invalid_ids[~invalid_ids.str.match(r'^[A-Za-z0-9\-\.]{1,64}$')]
                if not invalid_ids.empty:
                    violations.append(ComplianceViolation(
                        standard='FHIR R4',
                        rule_id='FHIR_INVALID_ID',
                        severity='medium',
                        field=col,
                        message=(
                            f"Column '{col}' contains {len(invalid_ids)} values that "
                            f"do not conform to the FHIR logical-id format "
                            f"([A-Za-z0-9-.] up to 64 chars)"
                        ),
                        recommendation="FHIR logical IDs must match [A-Za-z0-9-.]{1,64}.",
                    ))

        # Check FHIR date columns
        date_col_keywords = {'date', 'datetime', 'time', 'period', 'onset', 'recorded'}
        for col in df.columns:
            if any(kw in col.lower() for kw in date_col_keywords):
                str_col = df[col].dropna().astype(str)
                if str_col.empty:
                    continue
                non_conforming = str_col[~str_col.str.match(
                    r'^\d{4}(-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?)?)?$'
                )]
                if len(non_conforming) > 0:
                    violations.append(ComplianceViolation(
                        standard='FHIR R4',
                        rule_id='FHIR_INVALID_DATE_FORMAT',
                        severity='low',
                        field=col,
                        message=(
                            f"Column '{col}' contains {len(non_conforming)} values "
                            f"that do not match the FHIR date/dateTime format."
                        ),
                        recommendation=(
                            "Use ISO 8601 dates: YYYY, YYYY-MM, YYYY-MM-DD, "
                            "or YYYY-MM-DDThh:mm:ss+zz:zz"
                        ),
                    ))

        return violations


# ── SNOMED CT plugin ──────────────────────────────────────────────────────────

# SNOMED CT concept IDs are 6–18 digit integers
_SNOMED_ID_RE = re.compile(r'^\d{6,18}$')

# Common SNOMED column name patterns
_SNOMED_COL_KEYWORDS = {
    'snomed', 'snomedct', 'snomed_ct', 'concept', 'conceptid',
    'concept_id', 'clinicalfinding', 'disorder',
}


class SNOMEDCompliancePlugin(ComplianceStandard):
    """
    Validates SNOMED CT concept ID format.

    Checks performed:
    - Columns whose names suggest SNOMED CT codes (e.g., 'snomed_code',
      'concept_id') must contain only 6-18 digit integers.
    - Flags columns that mix SNOMED IDs with free-text descriptions.
    """

    @property
    def name(self) -> str:
        return 'snomed_ct'

    def validate(self, df: pd.DataFrame) -> List[ComplianceViolation]:
        violations: List[ComplianceViolation] = []

        for col in df.columns:
            col_lower = col.lower().replace('-', '_').replace(' ', '_')
            if not any(kw in col_lower for kw in _SNOMED_COL_KEYWORDS):
                continue

            str_col = df[col].dropna().astype(str)
            if str_col.empty:
                continue

            invalid = str_col[~str_col.str.match(r'^\d{6,18}$')]
            if not invalid.empty:
                sample = ', '.join(repr(v) for v in invalid.unique()[:3].tolist())
                violations.append(ComplianceViolation(
                    standard='SNOMED CT',
                    rule_id='SNOMED_INVALID_CONCEPT_ID',
                    severity='medium',
                    field=col,
                    message=(
                        f"Column '{col}' contains {len(invalid)} values that are not "
                        f"valid SNOMED CT concept IDs (6-18 digit integers). "
                        f"Examples: {sample}"
                    ),
                    recommendation=(
                        "SNOMED CT concept IDs must be 6-18 digit integers "
                        "(e.g., 73211009 for Diabetes mellitus). "
                        "Store display text in a separate '_display' column."
                    ),
                ))

        return violations


# ── Plugin discovery SDK ──────────────────────────────────────────────────────

_ENTRY_POINT_GROUP = 'medical_data_validator.compliance_plugins'

# Names of built-in plugins that ship with this package
_BUILTIN_PLUGIN_NAMES = {'fhir_r4', 'snomed_ct'}


def discover_plugins(include_builtin: bool = True) -> List[ComplianceStandard]:
    """
    Return all compliance plugins registered via the
    ``medical_data_validator.compliance_plugins`` entry-point group.

    Args:
        include_builtin: When False, skip plugins whose names match the
            built-in set ('fhir_r4', 'snomed_ct').  Useful for testing
            third-party plugins in isolation.

    Returns:
        A list of instantiated ComplianceStandard objects, one per entry-point.
        Entry-points that fail to load are silently skipped.
    """
    import importlib.metadata as importlib_metadata

    plugins: List[ComplianceStandard] = []
    try:
        eps = importlib_metadata.entry_points(group=_ENTRY_POINT_GROUP)
    except Exception:
        return plugins

    for ep in eps:
        if not include_builtin and ep.name in _BUILTIN_PLUGIN_NAMES:
            continue
        try:
            cls = ep.load()
            plugin = cls()
            plugins.append(plugin)
        except Exception:
            pass

    return plugins


def load_compliance_plugins(
    engine=None,
    include_builtin: bool = True,
):
    """
    Discover all installed compliance plugins and register them with *engine*.

    If *engine* is None, a new :class:`~medical_data_validator.compliance.ComplianceEngine`
    is created and returned.

    This is the recommended one-liner for getting a fully loaded engine:

        engine = load_compliance_plugins()
    """
    from .compliance import ComplianceEngine

    if engine is None:
        engine = ComplianceEngine()

    for plugin in discover_plugins(include_builtin=include_builtin):
        engine.register_plugin(plugin)

    return engine
