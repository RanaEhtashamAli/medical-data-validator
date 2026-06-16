# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install for development (all extras)
pip install -e ".[all,dev,test]"

# Run all tests
pytest

# Run a single test file
pytest tests/test_core.py

# Run a single test
pytest tests/test_core.py::TestMedicalDataValidator::test_validate_basic

# Run with coverage
pytest --cov=medical_data_validator --cov-report=term-missing

# Skip slow/integration tests
pytest -m "not slow and not integration"

# Lint
flake8 medical_data_validator/
black --check medical_data_validator/
isort --check-only medical_data_validator/

# Format
black medical_data_validator/
isort medical_data_validator/

# Type check
mypy medical_data_validator/

# Security scan
bandit -r medical_data_validator/

# Run the web dashboard (requires [web] extras)
SECRET_KEY=your-secret python launch_dashboard.py

# Run the REST API server
python api.py --host 0.0.0.0 --port 8000

# Run the CLI
medical-validator validate --file data.csv --detect-phi --quality-checks
```

## Architecture

### Package layout

```
medical_data_validator/
├── core.py                  # MedicalDataValidator, ValidationResult, ValidationIssue, ValidationRule
├── validators.py            # Concrete rules: SchemaValidator, PHIDetector, DataQualityChecker,
│                            #   MedicalCodeValidator, RangeValidator, DateValidator
├── extensions.py            # CustomValidator, ValidationProfile, MedicalProfiles, ValidationRegistry
├── compliance.py            # ComplianceEngine — HIPAA/GDPR/FDA scoring (v1.2)
├── compliance_templates.py  # ComplianceTemplateManager — pre-built rule sets (clinical_trials, etc.)
├── analytics.py             # AdvancedAnalytics — quality metrics, anomaly detection, trends (v1.2)
├── monitoring.py            # RealTimeMonitor singleton — background thread, alerts (v1.2)
├── performance.py           # ValidationCache, BatchValidator, OptimizedMedicalDataValidator
├── security.py              # HIPAAComplianceChecker, DataAnonymizer, SecurityAuditor, DataSanitizer
└── dashboard/               # Flask + Dash web UI and REST API
    ├── app.py               # create_dashboard_app() factory
    ├── routes.py            # Flask blueprints — /validate, /health, /docs, /api/*
    ├── dash_layout.py       # Dash layout + callbacks
    ├── utils.py             # load_data(), generate_charts(), convert_numpy_types()
    └── templates/           # Jinja2 HTML templates
```

### Data flow

1. **Entry point** — `MedicalDataValidator.validate(data)` in `core.py` accepts a DataFrame, dict, or list of dicts.
2. **Rule pipeline** — Each `ValidationRule` subclass in `validators.py` receives the full DataFrame and returns `List[ValidationIssue]`.
3. **v1.2 engines** — After the rule pipeline, three optional engines run in sequence: `ComplianceEngine` → `AdvancedAnalytics` → `RealTimeMonitor`. All three are imported at module level via a `try/except ImportError` block and fall back to `None` silently.
4. **Result** — `ValidationResult.to_dict()` is the serialization contract used by the REST API, monitoring, and the dashboard.

### Key design decisions

**Global singletons** — `monitoring.py` and `performance.py` each export a module-level singleton (`monitor`, `performance_monitor`). `monitor.start_monitoring()` spawns a background daemon thread the first time any `MedicalDataValidator` is constructed with `enable_monitoring=True` (the default). This means importing the package and constructing a validator in a test or script starts the thread.

**Optional v1.2 features** — `ComplianceEngine`, `AdvancedAnalytics`, and `monitor` are imported inside a `try/except ImportError` in `core.py`. If any of those modules fails to import, all three are silently set to `None` with no warning emitted.

**ValidationProfile** — `extensions.py` profiles (`clinical_trials`, `ehr`, `imaging`, `lab`) are pre-registered in the global `registry` singleton at import time. `ValidationProfile.create_validator()` calls `MedicalDataValidator(self.rules)` with no keyword arguments, which means all three v1.2 engines are enabled by default for every profile.

**Dashboard vs. legacy dashboard.py** — There are two dashboard implementations: the refactored `medical_data_validator/dashboard/` package (used by `api.py` and `launch_dashboard.py`) and a legacy monolithic `medical_data_validator/dashboard.py` module. The active one is the subpackage.

**Compliance report structure** — `ComplianceEngine.comprehensive_compliance_validation()` returns a dict with this shape:
```python
{
  'standards': {
    'hipaa':  {'score', 'risk_level', 'violations': [...], 'violations_count', 'recommendations', 'compliant'},
    'gdpr':   { same shape },
    'fda':    { same shape },
    'medical_coding': {  # different — no top-level 'violations' key
      'icd10': {'score', 'risk_level', 'violations_count', 'compliant'},
      'loinc': { same },
      'cpt':   { same }
    }
  },
  'all_violations': [...],   # flat list of all violation dicts
  'overall_score': float,
  'risk_level': str,
  'template_applied': str | None
}
```
This is nested under `result['summary']['compliance_report']` in `ValidationResult.to_dict()`, not at the top level.

### Known bugs (from code review)

These are confirmed bugs to be aware of when working on the codebase:

- **`performance.py:154`** — `BatchValidator` mutates `issue.row` in-place on cached `ValidationResult` objects, corrupting cached row numbers on subsequent cache hits. Fix: `copy.deepcopy(cached_result)` before mutating.
- **`monitoring.py:181`** — `_check_anomalies` calls `result.get('compliance_report', {})` but the key is nested at `result['summary']['compliance_report']` — compliance alerts never fire.
- **`monitoring.py:188`** — The `medical_coding` standard dict has no top-level `violations` key, so ICD-10/LOINC/CPT violations are silently excluded from alerts.
- **`monitoring.py:163` and `:330`** — Alert storm: failure-rate and stale-data alerts fire on every call/loop iteration with no deduplication.
- **`analytics.py:229`** — R² confidence uses `np.mean(y)` as the intercept instead of the fitted intercept from `np.polyfit`, making trend confidence wrong.
- **`analytics.py:114`** — `NaT.days` crashes when the first datetime column is all-null.
- **`compliance.py:125`** — GDPR loop adds one violation per pattern match per column (up to 4×), inflating violation count.
- **`security.py:406`** — Missing `re.DOTALL` — multi-line HTML injection bypasses `DataSanitizer`.
- **`security.py:22`** — SSN pattern `\b\d{9}\b` matches any 9-digit number.
- **`dashboard/app.py:9`** — `SECRET_KEY` is hardcoded as `'dev-secret-key'` with no env-var override.
