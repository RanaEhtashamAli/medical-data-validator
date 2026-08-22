# medical-data-validator Phase B: Coverage Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up four verified-but-unused/unconfigurable subsystems (per-request validator config, the security classes, batch/cache validation, and 5 new Dash admin pages) without touching the already-correct validation/compliance core.

**Architecture:** Extend the existing `create_validator()`/CLI config surface with a new `validators_config` block; add a `register_security_routes()` module mirroring the existing `register_auth_routes()`/`register_registry_routes()` pattern; wire `BatchValidator`/`ValidationCache` as opt-in query/form parameters on the existing validate endpoints; convert the Dash app from single-page to Dash's built-in multi-page framework (`use_pages=True`), with every new page calling the same module-level business-logic functions the REST routes already call, in-process, with no login gate.

**Tech Stack:** Flask, flask-restx, Dash 4.2.0 (`dash.register_page`/`dash.page_container`), dash-bootstrap-components, pandas, pytest.

**Spec:** `docs/superpowers/specs/2026-08-22-phase-b-coverage-gaps-design.md`

## Global Constraints

- No login/session gate for the Dash UI — every page acts as a fixed identity (tenant `'default'`), calling business-logic functions directly and bypassing `login_required`/`role_required` (spec Non-goals).
- Don't modify `ComplianceEngine`, `PHIDetector`, or other already-correct validation/compliance logic (spec Non-goals).
- `HIPAAComplianceChecker`'s PHI sample values are stripped from API responses by default; only returned when the caller passes `include_samples=true` (spec Section B).
- `SecurityAuditor.audit_security()` is called with the real temp file path when the request was a file upload (not always `None` as an earlier spec draft assumed) — verified `api_validate_file` already saves uploads to a `NamedTemporaryFile` before reading them.
- Every existing endpoint's current wire format is unchanged: `/api/validate/data`'s JSON body is still the raw column-dict itself (no envelope), and `/api/validate/file` is still multipart. New optional inputs (`validators`, `batch_size`, `use_cache`) are added as query parameters (`/validate/data`) or form fields (`/validate/file`) — **not** as new top-level JSON keys, since the JSON body has no envelope to add keys to and a data column could otherwise collide with a config key. This corrects the spec's illustrative `{"data": ..., "validators": ...}` JSON example, which didn't match the endpoint's real (envelope-less) contract.

---

### Task 1: Per-request validator configuration (API)

**Files:**
- Modify: `medical_data_validator/dashboard/routes.py` (`create_validator()` at line ~1114, `api_validate_data()` at line ~286, `api_validate_file()` at line ~423, imports at top)
- Test: `tests/test_validators_config.py` (new)

**Interfaces:**
- Produces: `create_validator(detect_phi, quality_checks, profile, enable_compliance=True, template=None, validators_config: Optional[dict] = None) -> MedicalDataValidator`. `validators_config` keys: `required_columns` (list), `column_types` (dict), `ranges` (dict of `{column: {min, max}}`), `date_columns` (list), `min_date`/`max_date` (str), `code_columns` (dict of `{column: standard}`).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_validators_config.py`:

```python
"""Tests for create_validator()'s new validators_config parameter."""

import pandas as pd
from medical_data_validator.dashboard.routes import create_validator


def test_no_config_is_unchanged():
    validator = create_validator(detect_phi=False, quality_checks=False, profile='')
    rule_names = [r.name for r in validator.rules]
    assert 'SchemaValidator' not in rule_names
    assert 'RangeValidator' not in rule_names
    assert 'DateValidator' not in rule_names
    assert 'MedicalCodeValidator' not in rule_names


def test_required_columns_adds_schema_validator():
    validator = create_validator(
        detect_phi=False, quality_checks=False, profile='',
        validators_config={'required_columns': ['patient_id']},
    )
    df = pd.DataFrame({'other_column': [1, 2]})
    result = validator.validate(df)
    assert any('patient_id' in i.message for i in result.issues)


def test_ranges_adds_range_validator():
    validator = create_validator(
        detect_phi=False, quality_checks=False, profile='',
        validators_config={'ranges': {'age': {'min': 0, 'max': 120}}},
    )
    df = pd.DataFrame({'age': [150]})
    result = validator.validate(df)
    assert any('above maximum' in i.message for i in result.issues)


def test_date_columns_with_min_max_adds_date_validator():
    validator = create_validator(
        detect_phi=False, quality_checks=False, profile='',
        validators_config={
            'date_columns': ['visit_date'],
            'min_date': '2020-01-01',
            'max_date': '2020-12-31',
        },
    )
    df = pd.DataFrame({'visit_date': ['2025-06-01']})
    result = validator.validate(df)
    assert any('after' in i.message for i in result.issues)


def test_code_columns_adds_medical_code_validator():
    validator = create_validator(
        detect_phi=False, quality_checks=False, profile='',
        validators_config={'code_columns': {'diagnosis_code': 'icd10'}},
    )
    rule_names = [r.name for r in validator.rules]
    assert 'MedicalCodeValidator' in rule_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/home/lenovo/Own Projects/medical-data-validator" && python3 -m pytest tests/test_validators_config.py -v`
Expected: FAIL — `create_validator()` doesn't accept `validators_config` yet (`TypeError: create_validator() got an unexpected keyword argument`).

- [ ] **Step 3: Add the imports**

In `medical_data_validator/dashboard/routes.py`, both the `try` and `except ImportError` blocks near the top currently read:

```python
try:
    from medical_data_validator.validators import PHIDetector, DataQualityChecker, MedicalCodeValidator
    ...
except ImportError:
    from ..validators import PHIDetector, DataQualityChecker, MedicalCodeValidator
    ...
```

Change both lines to:

```python
    from medical_data_validator.validators import PHIDetector, DataQualityChecker, MedicalCodeValidator, SchemaValidator, RangeValidator, DateValidator
```
```python
    from ..validators import PHIDetector, DataQualityChecker, MedicalCodeValidator, SchemaValidator, RangeValidator, DateValidator
```

- [ ] **Step 4: Extend `create_validator()`**

Replace the function (currently at line ~1114):

```python
def create_validator(detect_phi: bool, quality_checks: bool, profile: str, enable_compliance: bool = True, template: str | None = None, validators_config: Optional[dict] = None) -> MedicalDataValidator:
    """Create a validator with the specified configuration."""
    # Handle profile-based validation
    if profile and profile.strip():  # Check if profile is not empty
        profile_validator = get_profile(profile)
        if profile_validator:
            return profile_validator.create_validator()

    # Create basic validator with compliance support (v1.2) and optional template
    validator = MedicalDataValidator(enable_compliance=enable_compliance, compliance_template=template)

    # Always add basic quality checks to ensure we have some validation
    validator.add_rule(DataQualityChecker())

    # Add optional rules based on user selection
    if detect_phi:
        validator.add_rule(PHIDetector())

    # Add rules from per-request validators_config, if provided
    if validators_config:
        required_columns = validators_config.get('required_columns')
        column_types = validators_config.get('column_types')
        if required_columns or column_types:
            validator.add_rule(SchemaValidator(required_columns=required_columns, column_types=column_types))

        ranges = validators_config.get('ranges')
        if ranges:
            validator.add_rule(RangeValidator(ranges=ranges))

        date_columns = validators_config.get('date_columns')
        if date_columns:
            validator.add_rule(DateValidator(
                date_columns=date_columns,
                min_date=validators_config.get('min_date'),
                max_date=validators_config.get('max_date'),
            ))

        code_columns = validators_config.get('code_columns')
        if code_columns:
            validator.add_rule(MedicalCodeValidator(code_columns))

    return validator
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_validators_config.py -v`
Expected: PASS.

- [ ] **Step 6: Wire `validators_config` into `api_validate_data()`**

In `api_validate_data()` (line ~286), find:

```python
        # Get parameters
        detect_phi = request.args.get('detect_phi', 'true').lower() == 'true'
        quality_checks = request.args.get('quality_checks', 'true').lower() == 'true'
        profile = request.args.get('profile', '')
        standards = request.args.getlist('standards') or ["icd10", "loinc", "cpt"]
```

Change to:

```python
        # Get parameters
        detect_phi = request.args.get('detect_phi', 'true').lower() == 'true'
        quality_checks = request.args.get('quality_checks', 'true').lower() == 'true'
        profile = request.args.get('profile', '')
        standards = request.args.getlist('standards') or ["icd10", "loinc", "cpt"]

        validators_config = None
        if request.args.get('validators'):
            try:
                validators_config = json.loads(request.args.get('validators'))
            except (TypeError, ValueError) as e:
                return jsonify({"success": False, "error": f"Invalid 'validators' JSON: {e}"}), 400
```

Then find (still inside `api_validate_data()`):

```python
            validator = create_validator(detect_phi, quality_checks, profile)
```

Change to:

```python
            validator = create_validator(detect_phi, quality_checks, profile, validators_config=validators_config)
```

- [ ] **Step 7: Wire `validators_config` into `api_validate_file()`**

In `api_validate_file()` (line ~423), find:

```python
        # Get parameters
        detect_phi = request.form.get('detect_phi', 'true').lower() == 'true'
        quality_checks = request.form.get('quality_checks', 'true').lower() == 'true'
        profile = request.form.get('profile', '')
        standards = request.form.getlist('standards') or ["icd10", "loinc", "cpt"]
```

Change to:

```python
        # Get parameters
        detect_phi = request.form.get('detect_phi', 'true').lower() == 'true'
        quality_checks = request.form.get('quality_checks', 'true').lower() == 'true'
        profile = request.form.get('profile', '')
        standards = request.form.getlist('standards') or ["icd10", "loinc", "cpt"]

        validators_config = None
        if request.form.get('validators'):
            try:
                validators_config = json.loads(request.form.get('validators'))
            except (TypeError, ValueError) as e:
                return jsonify({"success": False, "error": f"Invalid 'validators' JSON: {e}"}), 400
```

Then find:

```python
            validator = create_validator(detect_phi, quality_checks, profile)
```

Change to:

```python
            validator = create_validator(detect_phi, quality_checks, profile, validators_config=validators_config)
```

- [ ] **Step 8: Add a route-level regression test**

Append to `tests/test_validators_config.py`:

```python
import json as _json
from medical_data_validator.dashboard.app import create_dashboard_app


def test_api_validate_data_accepts_validators_query_param():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        validators = _json.dumps({'required_columns': ['patient_id']})
        resp = client.post(
            f'/api/validate/data?validators={validators}',
            json={'other_column': [1, 2]},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert any('patient_id' in i['message'] for i in body['issues'])


def test_api_validate_data_rejects_malformed_validators_json():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        resp = client.post('/api/validate/data?validators=not-json', json={'a': [1]})
        assert resp.status_code == 400
```

- [ ] **Step 9: Run the full test file and the existing validate-endpoint suites**

Run: `python3 -m pytest tests/test_validators_config.py tests/test_flask_api_validation.py tests/test_flask_api_error.py -v`
Expected: all PASS (confirms the new optional parameter doesn't break existing behavior when `validators` is absent).

- [ ] **Step 10: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/routes.py tests/test_validators_config.py
git commit -m "Add per-request validator configuration to /api/validate/data and /api/validate/file"
```

---

### Task 2: Per-request validator configuration (CLI parity)

**Files:**
- Modify: `medical_data_validator/cli.py` (`create_validator_from_args()`, `main()`'s `validate_parser`, imports)
- Test: `tests/test_cli.py` (extend)

**Interfaces:**
- Consumes: same `RangeValidator`/`DateValidator`/`MedicalCodeValidator` constructors used in Task 1.
- Produces: `create_validator_from_args(args)` now also handles `args.range`, `args.date_column`, `args.min_date`, `args.max_date`, `args.code_column`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`, inside `class TestConsolidatedCLI` (or as a new class if that one is closed out — check the file first: append right before `if __name__ == "__main__":`):

```python
class TestValidatorConfigFlags:
    def test_range_flag_adds_range_validator(self):
        from medical_data_validator.cli import create_validator_from_args
        import argparse
        args = argparse.Namespace(
            required_columns=None, column_types=None, detect_phi=False,
            quality_checks=False, profile=None,
            range=['age:0:120'], date_column=None, min_date=None, max_date=None,
            code_column=None,
        )
        validator = create_validator_from_args(args)
        rule_names = [r.name for r in validator.rules]
        assert 'RangeValidator' in rule_names

    def test_date_column_flag_adds_date_validator(self):
        from medical_data_validator.cli import create_validator_from_args
        import argparse
        args = argparse.Namespace(
            required_columns=None, column_types=None, detect_phi=False,
            quality_checks=False, profile=None,
            range=None, date_column=['visit_date'], min_date='2020-01-01', max_date='2020-12-31',
            code_column=None,
        )
        validator = create_validator_from_args(args)
        rule_names = [r.name for r in validator.rules]
        assert 'DateValidator' in rule_names

    def test_code_column_flag_adds_medical_code_validator(self):
        from medical_data_validator.cli import create_validator_from_args
        import argparse
        args = argparse.Namespace(
            required_columns=None, column_types=None, detect_phi=False,
            quality_checks=False, profile=None,
            range=None, date_column=None, min_date=None, max_date=None,
            code_column=['diagnosis_code:icd10'],
        )
        validator = create_validator_from_args(args)
        rule_names = [r.name for r in validator.rules]
        assert 'MedicalCodeValidator' in rule_names

    def test_validate_subcommand_accepts_new_flags(self, tmp_path):
        import subprocess, sys
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("age,diagnosis_code\n150,E11.9\n")
        result = subprocess.run(
            [sys.executable, "-m", "medical_data_validator.cli", "validate", str(csv_path),
             "--range", "age:0:120", "--code-column", "diagnosis_code:icd10", "--format", "summary"],
            capture_output=True, text=True,
        )
        assert "Total Issues" in result.stdout
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cli.py::TestValidatorConfigFlags -v`
Expected: FAIL — `--range`/`--date-column`/`--code-column` aren't recognized argparse arguments yet, and `create_validator_from_args` doesn't branch on them.

- [ ] **Step 3: Add imports**

In `medical_data_validator/cli.py`, find:

```python
from . import (
    MedicalDataValidator,
    get_profile,
    list_available_profiles,
    SchemaValidator,
    PHIDetector,
    DataQualityChecker,
)
from .validators import MedicalCodeValidator
```

Change to:

```python
from . import (
    MedicalDataValidator,
    get_profile,
    list_available_profiles,
    SchemaValidator,
    RangeValidator,
    DateValidator,
    PHIDetector,
    DataQualityChecker,
)
from .validators import MedicalCodeValidator
```

- [ ] **Step 4: Extend `create_validator_from_args()`**

Find (in `medical_data_validator/cli.py`):

```python
    # Add profile-based validators
    if getattr(args, 'profile', None):
```

Insert immediately before it:

```python
    # Add range checks
    if getattr(args, 'range', None):
        ranges = {}
        for spec in args.range:
            column, min_str, max_str = spec.split(':', 2)
            ranges[column] = {'min': float(min_str), 'max': float(max_str)}
        validator.add_rule(RangeValidator(ranges=ranges))

    # Add date column checks
    if getattr(args, 'date_column', None):
        validator.add_rule(DateValidator(
            date_columns=args.date_column,
            min_date=getattr(args, 'min_date', None),
            max_date=getattr(args, 'max_date', None),
        ))

    # Add medical code column checks
    if getattr(args, 'code_column', None):
        code_columns = {}
        for spec in args.code_column:
            column, standard = spec.split(':', 1)
            code_columns[column] = standard
        validator.add_rule(MedicalCodeValidator(code_columns))

    # Add profile-based validators
    if getattr(args, 'profile', None):
```

- [ ] **Step 5: Add the new CLI flags**

In `main()`, find the `validate_parser` block:

```python
    validate_parser.add_argument('--column-types', help='JSON string specifying column types')
    validate_parser.add_argument('--detect-phi', action='store_true', help='Enable PHI/PII detection')
```

Insert between them:

```python
    validate_parser.add_argument('--column-types', help='JSON string specifying column types')
    validate_parser.add_argument('--range', action='append', metavar='COLUMN:MIN:MAX', help='Numeric range check (repeatable), e.g. --range age:0:120')
    validate_parser.add_argument('--date-column', action='append', metavar='COLUMN', help='Column to validate as a date (repeatable)')
    validate_parser.add_argument('--min-date', help='Minimum allowed date, applies to all --date-column columns')
    validate_parser.add_argument('--max-date', help='Maximum allowed date, applies to all --date-column columns')
    validate_parser.add_argument('--code-column', action='append', metavar='COLUMN:STANDARD', help='Medical code column check (repeatable), e.g. --code-column diagnosis_code:icd10')
    validate_parser.add_argument('--detect-phi', action='store_true', help='Enable PHI/PII detection')
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cli.py -v`
Expected: all PASS, including the pre-existing `TestMain`/`TestConsolidatedCLI` tests (confirms no regression).

- [ ] **Step 7: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/cli.py tests/test_cli.py
git commit -m "Add --range/--date-column/--code-column CLI flags, matching the API's validators_config"
```

---

### Task 3: Security endpoints (HIPAA check, security audit, sanitize)

**Files:**
- Modify: `medical_data_validator/dashboard/routes.py` (add `dataframe_from_request()` helper, register the new routes in `register_routes()`)
- Modify: `medical_data_validator/security.py` (add `register_security_routes()`)
- Test: `tests/test_security_endpoints.py` (new)

**Interfaces:**
- Produces: `dataframe_from_request() -> Tuple[pd.DataFrame, Optional[str]]` in `routes.py` — returns `(df, tmp_path)`; `tmp_path` is a real temp-file path (caller must `os.unlink` it) when the request was a multipart file upload, or `None` for a raw-JSON-body request. Raises `ValueError` with a user-facing message on bad input (no file/data, disallowed extension, empty filename).
- Consumes: `HIPAAComplianceChecker`, `SecurityAuditor`, `DataSanitizer` from `medical_data_validator/security.py` (all already implemented, zero changes needed to those classes).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_security_endpoints.py`:

```python
"""Tests for the new /api/security/* endpoints (Phase B)."""

import io
import pytest
from medical_data_validator.dashboard.app import create_dashboard_app


@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_hipaa_check_json_body(client):
    resp = client.post('/api/security/hipaa-check', json={'ssn': ['123-45-6789']})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['compliant'] is False
    assert body['total_phi_instances'] >= 1


def test_hipaa_check_redacts_samples_by_default(client):
    resp = client.post('/api/security/hipaa-check', json={'ssn': ['123-45-6789']})
    body = resp.get_json()
    for item in body['phi_detected']:
        assert 'sample_values' not in item
        assert 'sample_count' in item


def test_hipaa_check_include_samples_opt_in(client):
    resp = client.post('/api/security/hipaa-check?include_samples=true', json={'ssn': ['123-45-6789']})
    body = resp.get_json()
    assert any('sample_values' in item for item in body['phi_detected'])


def test_security_audit_json_body(client):
    resp = client.post('/api/security/audit', json={'email': ['a@b.com']})
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'security_score' in body
    assert body['overall_status'] in ('SECURE', 'NEEDS_ATTENTION')


def test_security_audit_file_upload_gets_real_file_path(client):
    data = {'file': (io.BytesIO(b'ssn\n123-45-6789\n'), 'test.csv')}
    resp = client.post('/api/security/audit', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['file_path'] is not None


def test_sanitize_removes_script_tags(client):
    resp = client.post('/api/security/sanitize', json={'notes': ['<script>alert(1)</script>hello']})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['sanitized_data'][0]['notes'] == 'hello'


def test_security_endpoints_reject_no_input(client):
    resp = client.post('/api/security/hipaa-check', data='', content_type='application/json')
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_security_endpoints.py -v`
Expected: FAIL with 404s (routes don't exist yet).

- [ ] **Step 3: Add `dataframe_from_request()` to `routes.py`**

In `medical_data_validator/dashboard/routes.py`, add this function right before `def create_validator(` (line ~1114):

```python
def dataframe_from_request():
    """
    Load a DataFrame from either a multipart file upload or a raw JSON body,
    matching the same input contract api_validate_data/api_validate_file use.

    Returns (df, tmp_path). tmp_path is a real temp-file path the caller must
    os.unlink() when the request was a file upload (so file-path-aware checks
    like SecurityAuditor's have something real to inspect), or None for a
    JSON-body request. Raises ValueError with a user-facing message on bad input.
    """
    if 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            raise ValueError("No file selected")
        allowed_extensions = {'csv', 'xlsx', 'xls', 'json', 'parquet'}
        if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            raise ValueError("File type not allowed. Supported formats: CSV, Excel, JSON, Parquet")
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.rsplit('.', 1)[1]}") as tmp_file:
            file.save(tmp_file.name)
            tmp_path = tmp_file.name
        return load_data(tmp_path), tmp_path

    data = request.get_json(silent=True)
    if not data:
        raise ValueError("No file or JSON data provided")
    if isinstance(data, dict):
        max_length = max(len(v) if isinstance(v, list) else 1 for v in data.values())
        padded = {}
        for key, value in data.items():
            if isinstance(value, list):
                padded[key] = value + [None] * (max_length - len(value)) if len(value) < max_length else value
            else:
                padded[key] = [value] * max_length
        df = pd.DataFrame(padded)
    else:
        df = pd.DataFrame(data)
    return df, None
```

- [ ] **Step 4: Add `register_security_routes()` to `security.py`**

In `medical_data_validator/security.py`, add near the top (after the existing imports, before `class HIPAAComplianceChecker`):

```python
from flask import request, jsonify
import os
```

Add at the end of the file (after `class DataSanitizer` and its methods):

```python
def register_security_routes(app) -> None:
    """Attach /api/security/* routes to a Flask app."""
    try:
        from medical_data_validator.dashboard.routes import dataframe_from_request
    except ImportError:
        from .dashboard.routes import dataframe_from_request

    def _load_or_400():
        """Returns (df, tmp_path) or raises a tuple-carrying ValueError the
        caller turns into a 400 response."""
        return dataframe_from_request()

    @app.route('/api/security/hipaa-check', methods=['POST'])
    def hipaa_check_endpoint():
        tmp_path = None
        try:
            df, tmp_path = _load_or_400()
            include_samples = request.args.get('include_samples', 'false').lower() == 'true'
            report = HIPAAComplianceChecker().check_hipaa_compliance(df)
            if not include_samples:
                for item in report.get('phi_detected', []):
                    item['sample_count'] = len(item.pop('sample_values', []))
            return jsonify(report)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        except Exception as exc:
            return jsonify({'success': False, 'error': str(exc)}), 500
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    @app.route('/api/security/audit', methods=['POST'])
    def security_audit_endpoint():
        tmp_path = None
        try:
            df, tmp_path = _load_or_400()
            result = SecurityAuditor().audit_security(df, file_path=tmp_path)
            return jsonify(result)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        except Exception as exc:
            return jsonify({'success': False, 'error': str(exc)}), 500
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    @app.route('/api/security/sanitize', methods=['POST'])
    def sanitize_endpoint():
        tmp_path = None
        try:
            df, tmp_path = _load_or_400()
            sanitized = DataSanitizer().sanitize_data(df)
            return jsonify({'success': True, 'sanitized_data': sanitized.to_dict(orient='records')})
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400
        except Exception as exc:
            return jsonify({'success': False, 'error': str(exc)}), 500
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
```

- [ ] **Step 5: Register the routes in `register_routes()`**

In `medical_data_validator/dashboard/routes.py`'s `register_routes(app)`, find the auth-routes registration block:

```python
    # Auth routes (/api/auth/*)
    try:
        from medical_data_validator.auth import register_auth_routes
    except ImportError:
        try:
            from ..auth import register_auth_routes
        except ImportError:
            register_auth_routes = None

    if register_auth_routes:
        register_auth_routes(app)
```

Insert immediately after it:

```python
    # Security routes (/api/security/*)
    try:
        from medical_data_validator.security import register_security_routes
    except ImportError:
        try:
            from ..security import register_security_routes
        except ImportError:
            register_security_routes = None

    if register_security_routes:
        register_security_routes(app)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_security_endpoints.py -v`
Expected: PASS.

- [ ] **Step 7: Run the full test suite**

Run: `python3 -m pytest --ignore=tests/test_web_ui.py -q`
Expected: no new failures (baseline was 350 passed after Phase A).

- [ ] **Step 8: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/routes.py medical_data_validator/security.py tests/test_security_endpoints.py
git commit -m "Wire HIPAAComplianceChecker/SecurityAuditor/DataSanitizer into new /api/security/* endpoints"
```

---

### Task 4: Batch + cache wiring

**Files:**
- Modify: `medical_data_validator/dashboard/routes.py` (imports, module-level `_validation_cache`, `api_validate_data()`, `api_validate_file()`)
- Test: `tests/test_batch_cache_endpoints.py` (new)

**Interfaces:**
- Consumes: `BatchValidator(validator, batch_size, cache)` and `ValidationCache(max_size)` from `medical_data_validator/performance.py` (unchanged, already implemented).
- Produces: module-level `_validation_cache: ValidationCache` in `routes.py`, shared across requests within one process.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_batch_cache_endpoints.py`:

```python
"""Tests for opt-in batch_size/use_cache on the validate endpoints (Phase B)."""

import pytest
from medical_data_validator.dashboard.app import create_dashboard_app


@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_validate_data_without_batch_size_is_unchanged(client):
    resp = client.post('/api/validate/data', json={'age': [200]})
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'batch_results' not in body.get('summary', {})


def test_validate_data_with_batch_size_uses_batch_validator(client):
    resp = client.post('/api/validate/data?batch_size=1', json={'age': [1, 2, 3]})
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'batch_results' in body['summary']
    assert body['summary']['total_batches'] == 3


def test_validate_data_batch_with_cache_produces_same_result_twice(client):
    resp1 = client.post('/api/validate/data?batch_size=1&use_cache=true', json={'age': [1]})
    resp2 = client.post('/api/validate/data?batch_size=1&use_cache=true', json={'age': [1]})
    assert resp1.get_json()['total_issues'] == resp2.get_json()['total_issues']
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_batch_cache_endpoints.py -v`
Expected: `test_validate_data_with_batch_size_uses_batch_validator` fails (no `batch_results` key produced — `batch_size` is currently ignored).

- [ ] **Step 3: Import `BatchValidator`/`ValidationCache` and add the module-level cache**

In `medical_data_validator/dashboard/routes.py`, in both import blocks, add:

```python
    from medical_data_validator.performance import BatchValidator, ValidationCache
```
```python
    from ..performance import BatchValidator, ValidationCache
```

Immediately after `logger = logging.getLogger(__name__)` near the top of the file, add:

```python
_validation_cache = ValidationCache(max_size=int(os.environ.get('VALIDATION_CACHE_MAX_SIZE', 1000)))
```

- [ ] **Step 4: Wire into `api_validate_data()`**

Find (added in Task 1, Step 6):

```python
        validators_config = None
        if request.args.get('validators'):
            try:
                validators_config = json.loads(request.args.get('validators'))
            except (TypeError, ValueError) as e:
                return jsonify({"success": False, "error": f"Invalid 'validators' JSON: {e}"}), 400
```

Insert immediately after it:

```python
        batch_size = request.args.get('batch_size', type=int)
        use_cache = request.args.get('use_cache', 'false').lower() == 'true'
```

Then find (modified in Task 1, Step 6):

```python
            validator = create_validator(detect_phi, quality_checks, profile, validators_config=validators_config)
            logger.debug("Validator created with %d rules", len(validator.rules))
        except Exception as e:
            logger.exception("Error creating validator: %s", e)
            return jsonify({
                "success": False,
                "error": f"Failed to create validator: {str(e)}",
                "traceback": traceback.format_exc() if current_app.debug else None
            }), 500

        # Validate data
        logger.debug("Validating data...")
        try:
            result = validator.validate(df)
            logger.debug("Validation completed: %d issues found", len(result.issues))
```

Change the validate call to:

```python
        # Validate data
        logger.debug("Validating data...")
        try:
            if batch_size:
                cache = _validation_cache if use_cache else None
                result = BatchValidator(validator, batch_size=batch_size, cache=cache).validate_batches(df)
            else:
                result = validator.validate(df)
            logger.debug("Validation completed: %d issues found", len(result.issues))
```

- [ ] **Step 5: Wire into `api_validate_file()`**

Find (added in Task 1, Step 7):

```python
        validators_config = None
        if request.form.get('validators'):
            try:
                validators_config = json.loads(request.form.get('validators'))
            except (TypeError, ValueError) as e:
                return jsonify({"success": False, "error": f"Invalid 'validators' JSON: {e}"}), 400
```

Insert immediately after it:

```python
        batch_size = request.form.get('batch_size', type=int)
        use_cache = request.form.get('use_cache', 'false').lower() == 'true'
```

Then find:

```python
            # Create validator
            validator = create_validator(detect_phi, quality_checks, profile, validators_config=validators_config)

            # Validate data
            result = validator.validate(data)
```

Change to:

```python
            # Create validator
            validator = create_validator(detect_phi, quality_checks, profile, validators_config=validators_config)

            # Validate data
            if batch_size:
                cache = _validation_cache if use_cache else None
                result = BatchValidator(validator, batch_size=batch_size, cache=cache).validate_batches(data)
            else:
                result = validator.validate(data)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_batch_cache_endpoints.py -v`
Expected: PASS.

- [ ] **Step 7: Run the full test suite**

Run: `python3 -m pytest --ignore=tests/test_web_ui.py -q`
Expected: no new failures.

- [ ] **Step 8: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/routes.py tests/test_batch_cache_endpoints.py
git commit -m "Wire BatchValidator/ValidationCache into /api/validate/data and /api/validate/file as opt-in params"
```

---

### Task 5: `auth.py` refactor — extract module-level account functions

**Files:**
- Modify: `medical_data_validator/auth.py`
- Test: `tests/test_auth.py` (new)

**Interfaces:**
- Produces (all module-level in `auth.py`, all raise `ValueError` with a user-facing message on failure — no Flask/`g` dependency):
  - `list_user_accounts() -> List[Dict[str, Any]]`
  - `create_user_account(username: str, password: str, role: str = 'read-only', tenant: str = 'default') -> Dict[str, Any]`
  - `deactivate_user_account(username: str) -> None`
  - `create_tenant_account(tenant_id: str, name: Optional[str] = None) -> Dict[str, Any]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth.py`:

```python
"""Tests for auth.py's module-level account functions (Phase B extraction)."""

import pytest
import medical_data_validator.auth as auth


@pytest.fixture(autouse=True)
def _clean_users_and_tenants():
    """Each test gets a snapshot/restore of the in-memory stores."""
    users_before = dict(auth._USERS)
    tenants_before = dict(auth._TENANTS)
    yield
    auth._USERS.clear()
    auth._USERS.update(users_before)
    auth._TENANTS.clear()
    auth._TENANTS.update(tenants_before)


def test_list_user_accounts_includes_seeded_admin():
    users = auth.list_user_accounts()
    assert any(u['username'] == 'admin' for u in users)


def test_create_user_account_then_appears_in_list():
    auth.create_user_account('alice', 'password123', role='read-only', tenant='default')
    usernames = [u['username'] for u in auth.list_user_accounts()]
    assert 'alice' in usernames


def test_create_user_account_rejects_duplicate():
    auth.create_user_account('bob', 'password123')
    with pytest.raises(ValueError, match="already exists"):
        auth.create_user_account('bob', 'password123')


def test_create_user_account_rejects_bad_role():
    with pytest.raises(ValueError, match="role must be one of"):
        auth.create_user_account('carol', 'password123', role='superuser')


def test_deactivate_user_account_sets_inactive():
    auth.create_user_account('dave', 'password123')
    auth.deactivate_user_account('dave')
    assert auth._USERS['dave']['active'] is False


def test_deactivate_user_account_missing_user_raises():
    with pytest.raises(ValueError, match="not found"):
        auth.deactivate_user_account('nobody')


def test_create_tenant_account_then_stored():
    result = auth.create_tenant_account('hospital-a', 'Hospital A')
    assert result['tenant_id'] == 'hospital-a'
    assert 'api_key' in result
    assert auth._TENANTS['hospital-a']['name'] == 'Hospital A'


def test_create_tenant_account_rejects_duplicate():
    auth.create_tenant_account('dup-tenant')
    with pytest.raises(ValueError, match="already exists"):
        auth.create_tenant_account('dup-tenant')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: FAIL — `list_user_accounts`/`create_user_account`/`deactivate_user_account`/`create_tenant_account` don't exist yet at module level.

- [ ] **Step 3: Extract the module-level functions**

In `medical_data_validator/auth.py`, add these four functions right before `def register_auth_routes(app):`:

```python
def list_user_accounts() -> List[Dict[str, Any]]:
    return [
        {'username': u, 'role': d['role'], 'tenant': d['tenant'], 'active': d['active']}
        for u, d in _USERS.items()
    ]


def create_user_account(username: str, password: str, role: str = 'read-only', tenant: str = 'default') -> Dict[str, Any]:
    username = (username or '').strip()
    if not username or not password:
        raise ValueError('username and password required')
    if username in _USERS:
        raise ValueError('User already exists')
    if role not in ROLES:
        raise ValueError(f'role must be one of {ROLES}')
    _USERS[username] = {
        'password_hash': _hash_password(password),
        'role': role,
        'tenant': tenant,
        'active': True,
    }
    return {'created': username, 'role': role, 'tenant': tenant}


def deactivate_user_account(username: str) -> None:
    if username not in _USERS:
        raise ValueError('User not found')
    _USERS[username]['active'] = False


def create_tenant_account(tenant_id: str, name: Optional[str] = None) -> Dict[str, Any]:
    tenant_id = (tenant_id or '').strip()
    if not tenant_id:
        raise ValueError('tenant_id required')
    if tenant_id in _TENANTS:
        raise ValueError('Tenant already exists')
    api_key = secrets.token_hex(32)
    _TENANTS[tenant_id] = {'name': name or tenant_id, 'api_key': api_key}
    return {'tenant_id': tenant_id, 'api_key': api_key}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: PASS.

- [ ] **Step 5: Rewrite the route closures to use the new functions**

In `register_auth_routes(app)`, replace the four route handlers (keep `get_token`/`me` unchanged — they have no module-level equivalent to extract to since login has no non-HTTP use case):

Replace:

```python
    @app.route('/api/auth/users', methods=['GET'])
    @role_required('admin')
    def list_users():
        return jsonify([
            {'username': u, 'role': d['role'], 'tenant': d['tenant'], 'active': d['active']}
            for u, d in _USERS.items()
        ])

    @app.route('/api/auth/users', methods=['POST'])
    @role_required('admin')
    def create_user():
        data = request.get_json(silent=True) or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        role = data.get('role', 'read-only')
        tenant = data.get('tenant', g.tenant)

        if not username or not password:
            return jsonify({'error': 'username and password required'}), 400
        if username in _USERS:
            return jsonify({'error': 'User already exists'}), 409
        if role not in ROLES:
            return jsonify({'error': f'role must be one of {ROLES}'}), 400

        _USERS[username] = {
            'password_hash': _hash_password(password),
            'role': role,
            'tenant': tenant,
            'active': True,
        }
        return jsonify({'created': username, 'role': role, 'tenant': tenant}), 201

    @app.route('/api/auth/users/<username>', methods=['DELETE'])
    @role_required('admin')
    def deactivate_user(username):
        if username not in _USERS:
            return jsonify({'error': 'User not found'}), 404
        if username == g.user:
            return jsonify({'error': 'Cannot deactivate yourself'}), 400
        _USERS[username]['active'] = False
        return jsonify({'deactivated': username})

    @app.route('/api/auth/tenants', methods=['POST'])
    @role_required('admin')
    def create_tenant():
        data = request.get_json(silent=True) or {}
        tenant_id = data.get('tenant_id', '').strip()
        name = data.get('name', tenant_id)
        if not tenant_id:
            return jsonify({'error': 'tenant_id required'}), 400
        if tenant_id in _TENANTS:
            return jsonify({'error': 'Tenant already exists'}), 409
        api_key = secrets.token_hex(32)
        _TENANTS[tenant_id] = {'name': name, 'api_key': api_key}
        return jsonify({'tenant_id': tenant_id, 'api_key': api_key}), 201
```

With:

```python
    @app.route('/api/auth/users', methods=['GET'])
    @role_required('admin')
    def list_users():
        return jsonify(list_user_accounts())

    @app.route('/api/auth/users', methods=['POST'])
    @role_required('admin')
    def create_user():
        data = request.get_json(silent=True) or {}
        try:
            result = create_user_account(
                data.get('username', ''), data.get('password', ''),
                role=data.get('role', 'read-only'), tenant=data.get('tenant', g.tenant),
            )
            return jsonify(result), 201
        except ValueError as exc:
            code = 409 if 'already exists' in str(exc) else 400
            return jsonify({'error': str(exc)}), code

    @app.route('/api/auth/users/<username>', methods=['DELETE'])
    @role_required('admin')
    def deactivate_user(username):
        if username == g.user:
            return jsonify({'error': 'Cannot deactivate yourself'}), 400
        try:
            deactivate_user_account(username)
            return jsonify({'deactivated': username})
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 404

    @app.route('/api/auth/tenants', methods=['POST'])
    @role_required('admin')
    def create_tenant():
        data = request.get_json(silent=True) or {}
        try:
            result = create_tenant_account(data.get('tenant_id', ''), data.get('name'))
            return jsonify(result), 201
        except ValueError as exc:
            code = 409 if 'already exists' in str(exc) else 400
            return jsonify({'error': str(exc)}), code
```

- [ ] **Step 6: Add route-level regression tests**

Append to `tests/test_auth.py`:

```python
from medical_data_validator.dashboard.app import create_dashboard_app


@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def _admin_token(client):
    import os
    resp = client.post('/api/auth/token', json={
        'username': 'admin',
        'password': os.environ.get('ADMIN_PASSWORD', 'change-me'),
    })
    return resp.get_json()['access_token']


def test_route_create_user_still_returns_201(client):
    token = _admin_token(client)
    resp = client.post('/api/auth/users', json={'username': 'route-test-user', 'password': 'pw123456'},
                        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 201


def test_route_create_duplicate_user_still_returns_409(client):
    token = _admin_token(client)
    client.post('/api/auth/users', json={'username': 'dup-route-user', 'password': 'pw123456'},
                headers={'Authorization': f'Bearer {token}'})
    resp = client.post('/api/auth/users', json={'username': 'dup-route-user', 'password': 'pw123456'},
                        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 409
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth.py -v`
Expected: PASS. (If `ADMIN_PASSWORD` isn't set in the test environment, the default `'change-me'` from `auth.py`'s own fallback applies — no extra setup needed.)

- [ ] **Step 8: Run the full test suite**

Run: `python3 -m pytest --ignore=tests/test_web_ui.py -q`
Expected: no new failures.

- [ ] **Step 9: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/auth.py tests/test_auth.py
git commit -m "Extract auth.py's user/tenant logic to module-level functions, matching registry.py/jobs.py/audit.py's shape"
```

---

### Task 6: Dash multi-page shell

**Files:**
- Create: `medical_data_validator/dashboard/pages/__init__.py` (empty)
- Create: `medical_data_validator/dashboard/pages/validate.py` (moved from `dash_layout.py`)
- Modify: `medical_data_validator/dashboard/dash_layout.py` (becomes the sidebar shell)
- Modify: `medical_data_validator/dashboard/app.py` (`create_dashboard_app()`)
- Test: `tests/test_dash_layout.py` (update imports — the tested functions move to `pages/validate.py`)

**Interfaces:**
- Produces: `medical_data_validator/dashboard/pages/validate.py` exposes `layout` (registered at Dash path `/`) and `_run_validation_for_upload(contents, filename, options, profile)` (unchanged signature/behavior from Phase A).
- Consumes: Dash's `use_pages=True` + `pages_folder` auto-discovery (default: a `pages/` directory next to the module where `dash.Dash(__name__, ...)` is constructed — that's `dashboard/app.py`, so `dashboard/pages/` is the correct location with no extra configuration).

- [ ] **Step 1: Create the pages package**

```bash
mkdir -p "/home/lenovo/Own Projects/medical-data-validator/medical_data_validator/dashboard/pages"
touch "/home/lenovo/Own Projects/medical-data-validator/medical_data_validator/dashboard/pages/__init__.py"
```

- [ ] **Step 2: Move the Validate page into `pages/validate.py`**

Create `medical_data_validator/dashboard/pages/validate.py` with the full content of the current `dash_layout.py` (the version from Phase A, with `_run_validation_for_upload` already extracted), converted to Dash Pages style — `@dash_app.callback` becomes the module-level `@callback` since page modules are imported before the `Dash()` instance exists:

```python
"""Dash page: upload a file and run validation against the real validator."""

import base64

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, callback

from ..utils import dataframe_from_upload_bytes, generate_charts

dash.register_page(__name__, path='/', name='Validate')

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Medical Data Validator Dashboard", className="text-center mb-4"),
            html.P("Upload your medical dataset for comprehensive validation", className="text-center")
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Upload(
                id='upload-data',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select Files')
                ]),
                style={
                    'width': '100%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px'
                },
                multiple=False
            ),
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Checklist(
                id='validation-options',
                options=[
                    {'label': 'Detect PHI/PII', 'value': 'phi'},
                    {'label': 'Quality Checks', 'value': 'quality'},
                ],
                value=['phi', 'quality'],
                inline=True
            )
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Dropdown(
                id='profile-dropdown',
                options=[
                    {'label': 'Clinical Trials', 'value': 'clinical_trials'},
                    {'label': 'EHR', 'value': 'ehr'},
                    {'label': 'Imaging', 'value': 'imaging'},
                    {'label': 'Lab Data', 'value': 'lab'},
                ],
                placeholder='Select validation profile (optional)',
                clearable=True
            )
        ])
    ]),
    dbc.Row([
        dbc.Col([
            html.Div(id='validation-results')
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='severity-chart')
        ], width=6),
        dbc.Col([
            dcc.Graph(id='column-chart')
        ], width=6)
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='missing-chart')
        ], width=6),
        dbc.Col([
            dcc.Graph(id='dtype-chart')
        ], width=6)
    ])
], fluid=True)


def _run_validation_for_upload(contents, filename, options, profile):
    """Parse an uploaded file, run validation, and build the 4 chart figures.
    Extracted from the Dash callback so it's directly testable without a
    running Dash app."""
    if contents is None:
        return "Upload a file to start validation", {}, {}, {}, {}

    from ..routes import create_validator

    _header, b64data = contents.split(',', 1)
    raw_bytes = base64.b64decode(b64data)

    try:
        df = dataframe_from_upload_bytes(filename or '', raw_bytes)
    except Exception as exc:
        return f"Could not parse {filename}: {exc}", {}, {}, {}, {}

    options = options or []
    validator = create_validator(
        detect_phi='phi' in options,
        quality_checks='quality' in options,
        profile=profile,
    )
    result = validator.validate(df)
    result_dict = result.to_dict()

    summary_lines = [
        f"Valid: {result_dict['is_valid']}",
        f"Compliant: {result_dict['is_compliant']}",
        f"Total issues: {result_dict['total_issues']} "
        f"(errors: {result_dict['error_count']}, warnings: {result_dict['warning_count']}, "
        f"info: {result_dict['info_count']})",
    ]
    summary = " | ".join(summary_lines)

    charts = generate_charts(df, result)
    return (
        summary,
        charts.get('severity_distribution', {}),
        charts.get('column_issues', {}),
        charts.get('missing_values', {}),
        charts.get('data_types', {}),
    )


@callback(
    [Output('validation-results', 'children'),
     Output('severity-chart', 'figure'),
     Output('column-chart', 'figure'),
     Output('missing-chart', 'figure'),
     Output('dtype-chart', 'figure')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename'),
     State('validation-options', 'value'),
     State('profile-dropdown', 'value')]
)
def update_output(contents, filename, options, profile):
    return _run_validation_for_upload(contents, filename, options, profile)
```

- [ ] **Step 3: Rewrite `dash_layout.py` as the sidebar shell**

Replace the full contents of `medical_data_validator/dashboard/dash_layout.py`:

```python
"""Dash app shell: persistent sidebar navigation + the active page's content."""

import dash
import dash_bootstrap_components as dbc
from dash import html


def setup_dash_layout(dash_app):
    sidebar = dbc.Nav(
        [
            dbc.NavLink(page['name'], href=page['relative_path'], active='exact')
            for page in dash.page_registry.values()
        ],
        vertical=True,
        pills=True,
        className="bg-light p-3",
    )
    dash_app.layout = dbc.Container([
        dbc.Row([
            dbc.Col(sidebar, width=2),
            dbc.Col(dash.page_container, width=10),
        ])
    ], fluid=True)
```

- [ ] **Step 4: Update `dashboard/app.py`**

In `medical_data_validator/dashboard/app.py`, find:

```python
try:
    from medical_data_validator.dashboard.routes import register_routes
    from medical_data_validator.dashboard.dash_layout import setup_dash_layout, setup_dash_callbacks
except ImportError:
    # Fallback for relative imports when used as package
    from .routes import register_routes
    from .dash_layout import setup_dash_layout, setup_dash_callbacks
```

Change to:

```python
try:
    from medical_data_validator.dashboard.routes import register_routes
    from medical_data_validator.dashboard.dash_layout import setup_dash_layout
except ImportError:
    # Fallback for relative imports when used as package
    from .routes import register_routes
    from .dash_layout import setup_dash_layout
```

Find:

```python
    # Initialize Dash
    dash_app = dash.Dash(
        __name__,
        server=app,
        url_base_pathname='/dash/',
        external_stylesheets=[dbc.themes.BOOTSTRAP]
    )
    setup_dash_layout(dash_app)
    setup_dash_callbacks(dash_app)

    return app
```

Change to:

```python
    # Initialize Dash (multi-page: auto-discovers modules under dashboard/pages/)
    dash_app = dash.Dash(
        __name__,
        server=app,
        url_base_pathname='/dash/',
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        use_pages=True,
    )
    setup_dash_layout(dash_app)

    return app
```

- [ ] **Step 5: Update `tests/test_dash_layout.py`'s imports**

The tested functions moved from `medical_data_validator.dashboard.dash_layout` to `medical_data_validator.dashboard.pages.validate`. In `tests/test_dash_layout.py`, change every:

```python
    from medical_data_validator.dashboard.dash_layout import _run_validation_for_upload
```

to:

```python
    from medical_data_validator.dashboard.pages.validate import _run_validation_for_upload
```

(There are 2 occurrences — in `test_update_output_no_upload_returns_placeholder` and `test_update_output_with_real_upload_calls_validator`.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dash_layout.py -v`
Expected: PASS (same 3 tests as Phase A, now importing from the new location).

- [ ] **Step 7: Manual verification against a running dashboard**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && python launch_dashboard.py &
sleep 2
curl -s -o /dev/null -w "root (validate page): %{http_code}\n" http://localhost:5000/dash/
kill %1
```

Expected: `200`. (Full sidebar navigation across pages gets exercised once later tasks add more pages — this step just confirms the multi-page shell itself serves correctly with one page registered.)

- [ ] **Step 8: Run the full test suite**

Run: `python3 -m pytest --ignore=tests/test_web_ui.py -q`
Expected: no new failures.

- [ ] **Step 9: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/pages medical_data_validator/dashboard/dash_layout.py medical_data_validator/dashboard/app.py tests/test_dash_layout.py
git commit -m "Convert the Dash UI to a multi-page app (sidebar shell + pages/validate.py), preparing for the new admin pages"
```

---

### Task 7: Dash Registry page

**Files:**
- Create: `medical_data_validator/dashboard/pages/registry.py`
- Test: `tests/test_dash_registry_page.py` (new)

**Interfaces:**
- Consumes: `list_datasets`, `register_dataset`, `get_dataset`, `delete_dataset`, `get_run_history` from `medical_data_validator/registry.py` (all module-level, unchanged).
- Produces: `_list_datasets_table_data(tenant='default') -> List[Dict]`, `_create_dataset_from_form(name, description, tags_csv) -> Tuple[bool, str]` in `pages/registry.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dash_registry_page.py`:

```python
"""Tests for the Dash Registry page's extracted callback logic."""

import tempfile
import pytest
import medical_data_validator.registry as registry


@pytest.fixture(autouse=True)
def _isolated_registry_db():
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()
    old_path = registry.REGISTRY_DB_PATH
    registry.REGISTRY_DB_PATH = tf.name
    if registry._conn is not None:
        registry._conn.close()
        registry._conn = None
    yield
    registry.REGISTRY_DB_PATH = old_path
    if registry._conn is not None:
        registry._conn.close()
        registry._conn = None


def test_list_datasets_table_data_empty_initially():
    from medical_data_validator.dashboard.pages.registry import _list_datasets_table_data
    assert _list_datasets_table_data() == []


def test_create_dataset_from_form_then_appears_in_list():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form, _list_datasets_table_data
    ok, message = _create_dataset_from_form('my-dataset', 'a test dataset', 'tag1,tag2')
    assert ok is True
    rows = _list_datasets_table_data()
    assert any(r['name'] == 'my-dataset' for r in rows)


def test_create_dataset_from_form_rejects_empty_name():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form
    ok, message = _create_dataset_from_form('', '', '')
    assert ok is False
    assert 'name' in message.lower()


def test_create_dataset_from_form_rejects_duplicate():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form
    _create_dataset_from_form('dup-name', '', '')
    ok, message = _create_dataset_from_form('dup-name', '', '')
    assert ok is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_dash_registry_page.py -v`
Expected: FAIL — `medical_data_validator.dashboard.pages.registry` doesn't exist yet.

- [ ] **Step 3: Create `pages/registry.py`**

```python
"""Dash page: dataset registry (list, create, view run history)."""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from ...registry import list_datasets, register_dataset, get_run_history

dash.register_page(__name__, path='/registry', name='Registry')

DASH_TENANT = 'default'

layout = dbc.Container([
    html.H2("Dataset Registry"),
    dbc.Row([
        dbc.Col(dbc.Input(id='registry-name-input', placeholder='Dataset name'), width=3),
        dbc.Col(dbc.Input(id='registry-description-input', placeholder='Description (optional)'), width=4),
        dbc.Col(dbc.Input(id='registry-tags-input', placeholder='Tags, comma-separated (optional)'), width=3),
        dbc.Col(dbc.Button('Register dataset', id='registry-create-btn', color='primary'), width=2),
    ], className='mb-3'),
    html.Div(id='registry-create-message'),
    dash_table.DataTable(id='registry-table', columns=[
        {'name': 'Name', 'id': 'name'},
        {'name': 'Description', 'id': 'description'},
        {'name': 'Tags', 'id': 'tags'},
        {'name': 'Created', 'id': 'created_at'},
    ]),
    dbc.Button('Refresh', id='registry-refresh-btn', className='mt-3'),
], fluid=True)


def _list_datasets_table_data(tenant=DASH_TENANT):
    datasets = list_datasets(tenant=tenant)
    return [
        {
            'name': d['name'],
            'description': d.get('description') or '',
            'tags': ', '.join(d.get('tags') or []),
            'created_at': d.get('created_at', ''),
        }
        for d in datasets
    ]


def _create_dataset_from_form(name, description, tags_csv):
    name = (name or '').strip()
    if not name:
        return False, "Dataset name is required"
    tags = [t.strip() for t in (tags_csv or '').split(',') if t.strip()]
    try:
        register_dataset(name, tenant=DASH_TENANT, description=description or None, tags=tags or None)
        return True, f"Registered '{name}'"
    except ValueError as exc:
        return False, str(exc)


@callback(
    [Output('registry-table', 'data'), Output('registry-create-message', 'children')],
    [Input('registry-create-btn', 'n_clicks'), Input('registry-refresh-btn', 'n_clicks')],
    [State('registry-name-input', 'value'),
     State('registry-description-input', 'value'),
     State('registry-tags-input', 'value')],
    prevent_initial_call=False,
)
def _handle_registry_actions(create_clicks, refresh_clicks, name, description, tags_csv):
    triggered = dash.ctx.triggered_id
    message = ""
    if triggered == 'registry-create-btn':
        ok, message = _create_dataset_from_form(name, description, tags_csv)
    return _list_datasets_table_data(), message
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dash_registry_page.py -v`
Expected: PASS.

- [ ] **Step 5: Manual verification**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && python launch_dashboard.py &
sleep 2
curl -s -o /dev/null -w "registry page: %{http_code}\n" http://localhost:5000/dash/registry
kill %1
```

Expected: `200`.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest --ignore=tests/test_web_ui.py -q`
Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/pages/registry.py tests/test_dash_registry_page.py
git commit -m "Add Dash Registry page: list and register datasets"
```

---

### Task 8: Dash Jobs page + report download buttons

**Files:**
- Create: `medical_data_validator/dashboard/pages/jobs.py`
- Modify: `medical_data_validator/dashboard/pages/validate.py` (add report download buttons)
- Test: `tests/test_dash_jobs_page.py` (new)

**Interfaces:**
- Consumes: `submit_job`, `get_job`, `list_jobs` from `medical_data_validator/jobs.py`; `generate_pdf_report`, `generate_csv_report` from `medical_data_validator/reports.py` (both take a `ValidationResult.to_dict()`-shaped dict).
- Produces: `_list_jobs_table_data(tenant='default') -> List[Dict]`, `_submit_job_from_form(job_type, data_json) -> Tuple[bool, str]` in `pages/jobs.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dash_jobs_page.py`:

```python
"""Tests for the Dash Jobs page's extracted callback logic."""

import tempfile
import time
import pytest
import medical_data_validator.jobs as jobs


@pytest.fixture(autouse=True)
def _isolated_jobs_db():
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()
    old_path = jobs.JOBS_DB_PATH
    jobs.JOBS_DB_PATH = tf.name
    if jobs._conn is not None:
        jobs._conn.close()
        jobs._conn = None
    yield
    jobs.JOBS_DB_PATH = old_path
    if jobs._conn is not None:
        jobs._conn.close()
        jobs._conn = None


def test_list_jobs_table_data_empty_initially():
    from medical_data_validator.dashboard.pages.jobs import _list_jobs_table_data
    assert _list_jobs_table_data() == []


def test_submit_job_from_form_then_appears_in_list():
    from medical_data_validator.dashboard.pages.jobs import _submit_job_from_form, _list_jobs_table_data
    ok, message = _submit_job_from_form('validate', '{"age": [200]}')
    assert ok is True
    for _ in range(20):
        rows = _list_jobs_table_data()
        if rows and rows[0]['status'] in ('completed', 'failed'):
            break
        time.sleep(0.1)
    assert rows[0]['job_type'] == 'validate'


def test_submit_job_from_form_rejects_bad_job_type():
    from medical_data_validator.dashboard.pages.jobs import _submit_job_from_form
    ok, message = _submit_job_from_form('not-a-real-type', '{}')
    assert ok is False


def test_submit_job_from_form_rejects_bad_json():
    from medical_data_validator.dashboard.pages.jobs import _submit_job_from_form
    ok, message = _submit_job_from_form('validate', 'not json')
    assert ok is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_dash_jobs_page.py -v`
Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Create `pages/jobs.py`**

```python
"""Dash page: async job submission and status polling."""

import json

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from ...jobs import submit_job, list_jobs

dash.register_page(__name__, path='/jobs', name='Jobs')

DASH_TENANT = 'default'

layout = dbc.Container([
    html.H2("Validation Jobs"),
    dbc.Row([
        dbc.Col(dcc.Dropdown(id='jobs-type-dropdown',
                              options=[{'label': 'Validate', 'value': 'validate'},
                                       {'label': 'Anonymize', 'value': 'anonymize'}],
                              value='validate'), width=2),
        dbc.Col(dbc.Textarea(id='jobs-payload-input', placeholder='{"data": {"age": [200]}}'), width=7),
        dbc.Col(dbc.Button('Submit job', id='jobs-submit-btn', color='primary'), width=3),
    ], className='mb-3'),
    html.Div(id='jobs-submit-message'),
    dash_table.DataTable(id='jobs-table', columns=[
        {'name': 'ID', 'id': 'id'},
        {'name': 'Type', 'id': 'job_type'},
        {'name': 'Status', 'id': 'status'},
        {'name': 'Created', 'id': 'created_at'},
    ]),
    dbc.Button('Refresh', id='jobs-refresh-btn', className='mt-3'),
], fluid=True)


def _list_jobs_table_data(tenant=DASH_TENANT):
    return [
        {
            'id': j['id'],
            'job_type': j['job_type'],
            'status': j['status'],
            'created_at': j.get('created_at', ''),
        }
        for j in list_jobs(tenant=tenant)
    ]


def _submit_job_from_form(job_type, payload_json):
    if job_type not in ('validate', 'anonymize'):
        return False, "job_type must be 'validate' or 'anonymize'"
    try:
        payload = json.loads(payload_json) if payload_json else {}
    except (TypeError, ValueError) as exc:
        return False, f"Invalid JSON payload: {exc}"
    if not isinstance(payload, dict):
        return False, "payload must be a JSON object"
    submit_job(job_type, payload, tenant=DASH_TENANT, username='dash-ui')
    return True, "Job submitted"


@callback(
    [Output('jobs-table', 'data'), Output('jobs-submit-message', 'children')],
    [Input('jobs-submit-btn', 'n_clicks'), Input('jobs-refresh-btn', 'n_clicks')],
    [State('jobs-type-dropdown', 'value'), State('jobs-payload-input', 'value')],
    prevent_initial_call=False,
)
def _handle_jobs_actions(submit_clicks, refresh_clicks, job_type, payload_json):
    triggered = dash.ctx.triggered_id
    message = ""
    if triggered == 'jobs-submit-btn':
        ok, message = _submit_job_from_form(job_type, payload_json)
    return _list_jobs_table_data(), message
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dash_jobs_page.py -v`
Expected: PASS.

- [ ] **Step 5: Add report download buttons to the Validate page**

In `medical_data_validator/dashboard/pages/validate.py`, add `dcc.Store`/`dcc.Download`/buttons to `layout` — find the last `dbc.Row` (the dtype/missing charts row) and add immediately after it, still inside the `dbc.Container([...])` list:

```python
    dbc.Row([
        dbc.Col([
            dbc.Button("Download PDF Report", id='download-pdf-btn', className='me-2'),
            dbc.Button("Download CSV Report", id='download-csv-btn'),
            dcc.Download(id='download-report'),
            dcc.Store(id='last-validation-result'),
        ])
    ]),
```

Change `_run_validation_for_upload`'s success return (the final `return (summary, charts.get(...), ...)`) to also emit the result dict, and update the callback's `Output`s to match. Replace:

```python
    charts = generate_charts(df, result)
    return (
        summary,
        charts.get('severity_distribution', {}),
        charts.get('column_issues', {}),
        charts.get('missing_values', {}),
        charts.get('data_types', {}),
    )
```

with:

```python
    charts = generate_charts(df, result)
    return (
        summary,
        charts.get('severity_distribution', {}),
        charts.get('column_issues', {}),
        charts.get('missing_values', {}),
        charts.get('data_types', {}),
        result_dict,
    )
```

And for the `if contents is None:` early return, change:

```python
    if contents is None:
        return "Upload a file to start validation", {}, {}, {}, {}
```

to:

```python
    if contents is None:
        return "Upload a file to start validation", {}, {}, {}, {}, None
```

And for the parse-failure early return, change:

```python
    except Exception as exc:
        return f"Could not parse {filename}: {exc}", {}, {}, {}, {}
```

to:

```python
    except Exception as exc:
        return f"Could not parse {filename}: {exc}", {}, {}, {}, {}, None
```

Update the `@callback` decorator's `Output` list — replace:

```python
@callback(
    [Output('validation-results', 'children'),
     Output('severity-chart', 'figure'),
     Output('column-chart', 'figure'),
     Output('missing-chart', 'figure'),
     Output('dtype-chart', 'figure')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename'),
     State('validation-options', 'value'),
     State('profile-dropdown', 'value')]
)
def update_output(contents, filename, options, profile):
    return _run_validation_for_upload(contents, filename, options, profile)
```

with:

```python
@callback(
    [Output('validation-results', 'children'),
     Output('severity-chart', 'figure'),
     Output('column-chart', 'figure'),
     Output('missing-chart', 'figure'),
     Output('dtype-chart', 'figure'),
     Output('last-validation-result', 'data')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename'),
     State('validation-options', 'value'),
     State('profile-dropdown', 'value')]
)
def update_output(contents, filename, options, profile):
    return _run_validation_for_upload(contents, filename, options, profile)


@callback(
    Output('download-report', 'data'),
    [Input('download-pdf-btn', 'n_clicks'), Input('download-csv-btn', 'n_clicks')],
    State('last-validation-result', 'data'),
    prevent_initial_call=True,
)
def _download_report(pdf_clicks, csv_clicks, result_dict):
    if not result_dict:
        return dash.no_update
    from ...reports import generate_pdf_report, generate_csv_report
    triggered = dash.ctx.triggered_id
    if triggered == 'download-pdf-btn':
        return dcc.send_bytes(generate_pdf_report(result_dict), "validation_report.pdf")
    return dcc.send_string(generate_csv_report(result_dict), "validation_report.csv")
```

- [ ] **Step 6: Update `test_dash_layout.py` for the new return arity**

In `tests/test_dash_layout.py`, `_run_validation_for_upload` now returns 6 values instead of 5. Update:

```python
def test_update_output_no_upload_returns_placeholder():
    from medical_data_validator.dashboard.pages.validate import _run_validation_for_upload
    result = _run_validation_for_upload(None, None, ["phi", "quality"], None)
    assert result[0] == "Upload a file to start validation"
```

(unchanged — only checks `result[0]`, still correct)

```python
def test_update_output_with_real_upload_calls_validator():
    from medical_data_validator.dashboard.pages.validate import _run_validation_for_upload
    df = pd.DataFrame({"ssn": ["123-45-6789", "000-00-0000"], "notes": ["a", "b"]})
    contents, filename = _make_upload_contents(df)

    summary, severity_fig, column_fig, missing_fig, dtype_fig, result_dict = _run_validation_for_upload(
        contents, filename, ["phi", "quality"], None
    )

    assert "coming soon" not in str(summary).lower()
    assert severity_fig != {}
    assert isinstance(severity_fig, dict) and "data" in severity_fig
    for fig in (column_fig, missing_fig, dtype_fig):
        assert fig != {}
    assert result_dict is not None
    assert "is_valid" in result_dict
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dash_layout.py tests/test_dash_jobs_page.py -v`
Expected: PASS.

- [ ] **Step 8: Manual verification**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && python launch_dashboard.py &
sleep 2
curl -s -o /dev/null -w "jobs page: %{http_code}\n" http://localhost:5000/dash/jobs
kill %1
```

Expected: `200`.

- [ ] **Step 9: Run the full test suite**

Run: `python3 -m pytest --ignore=tests/test_web_ui.py -q`
Expected: no new failures.

- [ ] **Step 10: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/pages/jobs.py medical_data_validator/dashboard/pages/validate.py tests/test_dash_jobs_page.py tests/test_dash_layout.py
git commit -m "Add Dash Jobs page and report download buttons on the Validate page"
```

---

### Task 9: Dash Custom Rules page

**Files:**
- Create: `medical_data_validator/dashboard/pages/custom_rules.py`
- Test: `tests/test_dash_custom_rules_page.py` (new)

**Interfaces:**
- Consumes: `_custom_rules_storage` (module-level list in `medical_data_validator/dashboard/routes.py`, already the real backing store for `/api/compliance/custom-rules`).
- Produces: `_list_custom_rules_table_data() -> List[Dict]`, `_add_custom_rule_from_form(name, pattern, severity) -> Tuple[bool, str]` in `pages/custom_rules.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dash_custom_rules_page.py`:

```python
"""Tests for the Dash Custom Rules page's extracted callback logic."""

import pytest
from medical_data_validator.dashboard import routes as routes_module


@pytest.fixture(autouse=True)
def _clean_custom_rules():
    before = list(routes_module._custom_rules_storage)
    yield
    routes_module._custom_rules_storage.clear()
    routes_module._custom_rules_storage.extend(before)


def test_list_custom_rules_table_data_empty_initially():
    from medical_data_validator.dashboard.pages.custom_rules import _list_custom_rules_table_data
    assert _list_custom_rules_table_data() == []


def test_add_custom_rule_from_form_then_appears_in_list():
    from medical_data_validator.dashboard.pages.custom_rules import _add_custom_rule_from_form, _list_custom_rules_table_data
    ok, message = _add_custom_rule_from_form('no-fax', r'\bfax\b', 'medium')
    assert ok is True
    rows = _list_custom_rules_table_data()
    assert any(r['name'] == 'no-fax' for r in rows)


def test_add_custom_rule_from_form_requires_name_and_pattern():
    from medical_data_validator.dashboard.pages.custom_rules import _add_custom_rule_from_form
    ok, message = _add_custom_rule_from_form('', '', 'medium')
    assert ok is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_dash_custom_rules_page.py -v`
Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Create `pages/custom_rules.py`**

```python
"""Dash page: compliance custom-rules CRUD (list, add, remove)."""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from ...dashboard.routes import _custom_rules_storage

dash.register_page(__name__, path='/custom-rules', name='Custom Rules')

layout = dbc.Container([
    html.H2("Custom Compliance Rules"),
    dbc.Row([
        dbc.Col(dbc.Input(id='rules-name-input', placeholder='Rule name'), width=3),
        dbc.Col(dbc.Input(id='rules-pattern-input', placeholder='Regex pattern'), width=4),
        dbc.Col(dcc.Dropdown(id='rules-severity-dropdown',
                              options=[{'label': s, 'value': s} for s in ('low', 'medium', 'high', 'critical')],
                              value='medium'), width=2),
        dbc.Col(dbc.Button('Add rule', id='rules-add-btn', color='primary'), width=3),
    ], className='mb-3'),
    html.Div(id='rules-add-message'),
    dash_table.DataTable(id='rules-table', columns=[
        {'name': 'Name', 'id': 'name'},
        {'name': 'Pattern', 'id': 'pattern'},
        {'name': 'Severity', 'id': 'severity'},
    ]),
    dbc.Button('Refresh', id='rules-refresh-btn', className='mt-3'),
], fluid=True)


def _list_custom_rules_table_data():
    return [
        {'name': r['name'], 'pattern': r['pattern'], 'severity': r.get('severity', 'medium')}
        for r in _custom_rules_storage
    ]


def _add_custom_rule_from_form(name, pattern, severity):
    name = (name or '').strip()
    pattern = (pattern or '').strip()
    if not name or not pattern:
        return False, "Both name and pattern are required"
    rule_data = {'name': name, 'pattern': pattern, 'severity': severity or 'medium',
                 'field_pattern': None, 'description': '', 'recommendation': None}
    for i, existing in enumerate(_custom_rules_storage):
        if existing['name'] == name:
            _custom_rules_storage[i] = rule_data
            return True, f"Updated rule '{name}'"
    _custom_rules_storage.append(rule_data)
    return True, f"Added rule '{name}'"


@callback(
    [Output('rules-table', 'data'), Output('rules-add-message', 'children')],
    [Input('rules-add-btn', 'n_clicks'), Input('rules-refresh-btn', 'n_clicks')],
    [State('rules-name-input', 'value'), State('rules-pattern-input', 'value'),
     State('rules-severity-dropdown', 'value')],
    prevent_initial_call=False,
)
def _handle_rules_actions(add_clicks, refresh_clicks, name, pattern, severity):
    triggered = dash.ctx.triggered_id
    message = ""
    if triggered == 'rules-add-btn':
        ok, message = _add_custom_rule_from_form(name, pattern, severity)
    return _list_custom_rules_table_data(), message
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dash_custom_rules_page.py -v`
Expected: PASS.

- [ ] **Step 5: Manual verification**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && python launch_dashboard.py &
sleep 2
curl -s -o /dev/null -w "custom rules page: %{http_code}\n" http://localhost:5000/dash/custom-rules
kill %1
```

Expected: `200`.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest --ignore=tests/test_web_ui.py -q`
Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/pages/custom_rules.py tests/test_dash_custom_rules_page.py
git commit -m "Add Dash Custom Rules page: list and add compliance rules"
```

---

### Task 10: Dash Audit page

**Files:**
- Create: `medical_data_validator/dashboard/pages/audit.py`
- Test: `tests/test_dash_audit_page.py` (new)

**Interfaces:**
- Consumes: `query_log`, `count_log` from `medical_data_validator/audit.py`.
- Produces: `_list_audit_log_table_data(tenant='default', limit=100) -> List[Dict]` in `pages/audit.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dash_audit_page.py`:

```python
"""Tests for the Dash Audit page's extracted callback logic."""

import tempfile
import pytest
import medical_data_validator.audit as audit


@pytest.fixture(autouse=True)
def _isolated_audit_db():
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()
    old_path = audit.AUDIT_DB_PATH
    audit.AUDIT_DB_PATH = tf.name
    if audit._conn is not None:
        audit._conn.close()
        audit._conn = None
    yield
    audit.AUDIT_DB_PATH = old_path
    if audit._conn is not None:
        audit._conn.close()
        audit._conn = None


def test_list_audit_log_table_data_empty_initially():
    from medical_data_validator.dashboard.pages.audit import _list_audit_log_table_data
    assert _list_audit_log_table_data() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_dash_audit_page.py -v`
Expected: FAIL — `medical_data_validator.dashboard.pages.audit` doesn't exist yet (`audit.AUDIT_DB_PATH`, used in the fixture above, is confirmed the correct constant name — verified directly against `medical_data_validator/audit.py:29`).

- [ ] **Step 3: Create `pages/audit.py`**

```python
"""Dash page: audit log viewer."""

import dash
import dash_bootstrap_components as dbc
from dash import html, dash_table, Input, Output, callback

from ...audit import query_log

dash.register_page(__name__, path='/audit', name='Audit Log')

DASH_TENANT = 'default'

layout = dbc.Container([
    html.H2("Audit Log"),
    dash_table.DataTable(id='audit-table', columns=[
        {'name': 'Timestamp', 'id': 'timestamp'},
        {'name': 'Username', 'id': 'username'},
        {'name': 'Event Type', 'id': 'event_type'},
        {'name': 'Dataset ID', 'id': 'dataset_id'},
    ], page_size=25),
    dbc.Button('Refresh', id='audit-refresh-btn', className='mt-3'),
], fluid=True)


def _list_audit_log_table_data(tenant=DASH_TENANT, limit=100):
    records = query_log(tenant=tenant, limit=limit)
    return [
        {
            'timestamp': r.get('timestamp', ''),
            'username': r.get('username', ''),
            'event_type': r.get('event_type', ''),
            'dataset_id': r.get('dataset_id', ''),
        }
        for r in records
    ]


@callback(
    Output('audit-table', 'data'),
    Input('audit-refresh-btn', 'n_clicks'),
    prevent_initial_call=False,
)
def _handle_audit_refresh(n_clicks):
    return _list_audit_log_table_data()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dash_audit_page.py -v`
Expected: PASS.

- [ ] **Step 5: Manual verification**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && python launch_dashboard.py &
sleep 2
curl -s -o /dev/null -w "audit page: %{http_code}\n" http://localhost:5000/dash/audit
kill %1
```

Expected: `200`.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest --ignore=tests/test_web_ui.py -q`
Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/pages/audit.py tests/test_dash_audit_page.py
git commit -m "Add Dash Audit Log page"
```

---

### Task 11: Dash Auth page

**Files:**
- Create: `medical_data_validator/dashboard/pages/auth.py`
- Test: `tests/test_dash_auth_page.py` (new)

**Interfaces:**
- Consumes: `list_user_accounts`, `create_user_account`, `deactivate_user_account`, `create_tenant_account` from `medical_data_validator/auth.py` (Task 5).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dash_auth_page.py`:

```python
"""Tests for the Dash Auth page's extracted callback logic."""

import pytest
import medical_data_validator.auth as auth


@pytest.fixture(autouse=True)
def _clean_users_and_tenants():
    users_before = dict(auth._USERS)
    tenants_before = dict(auth._TENANTS)
    yield
    auth._USERS.clear()
    auth._USERS.update(users_before)
    auth._TENANTS.clear()
    auth._TENANTS.update(tenants_before)


def test_list_users_table_data_includes_admin():
    from medical_data_validator.dashboard.pages.auth import _list_users_table_data
    rows = _list_users_table_data()
    assert any(r['username'] == 'admin' for r in rows)


def test_create_user_from_form_then_appears_in_list():
    from medical_data_validator.dashboard.pages.auth import _create_user_from_form, _list_users_table_data
    ok, message = _create_user_from_form('dash-created-user', 'password123', 'read-only', 'default')
    assert ok is True
    rows = _list_users_table_data()
    assert any(r['username'] == 'dash-created-user' for r in rows)


def test_deactivate_user_from_form():
    from medical_data_validator.dashboard.pages.auth import _create_user_from_form, _deactivate_user_from_form, _list_users_table_data
    _create_user_from_form('to-deactivate', 'password123', 'read-only', 'default')
    ok, message = _deactivate_user_from_form('to-deactivate')
    assert ok is True
    rows = _list_users_table_data()
    row = next(r for r in rows if r['username'] == 'to-deactivate')
    assert row['active'] is False


def test_create_tenant_from_form():
    from medical_data_validator.dashboard.pages.auth import _create_tenant_from_form
    ok, message = _create_tenant_from_form('new-tenant')
    assert ok is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_dash_auth_page.py -v`
Expected: FAIL — module doesn't exist yet.

- [ ] **Step 3: Create `pages/auth.py`**

```python
"""Dash page: user and tenant management (no login gate — see Global Constraints)."""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from ...auth import list_user_accounts, create_user_account, deactivate_user_account, create_tenant_account

dash.register_page(__name__, path='/auth', name='Users & Tenants')

layout = dbc.Container([
    html.H2("Users"),
    dbc.Row([
        dbc.Col(dbc.Input(id='auth-username-input', placeholder='Username'), width=2),
        dbc.Col(dbc.Input(id='auth-password-input', placeholder='Password', type='password'), width=2),
        dbc.Col(dcc.Dropdown(id='auth-role-dropdown',
                              options=[{'label': r, 'value': r} for r in ('admin', 'data-steward', 'read-only')],
                              value='read-only'), width=2),
        dbc.Col(dbc.Input(id='auth-tenant-input', placeholder='Tenant', value='default'), width=2),
        dbc.Col(dbc.Button('Create user', id='auth-create-user-btn', color='primary'), width=2),
        dbc.Col(dbc.Button('Deactivate', id='auth-deactivate-btn', color='danger'), width=2),
    ], className='mb-3'),
    html.Div(id='auth-user-message'),
    dash_table.DataTable(id='auth-users-table', columns=[
        {'name': 'Username', 'id': 'username'},
        {'name': 'Role', 'id': 'role'},
        {'name': 'Tenant', 'id': 'tenant'},
        {'name': 'Active', 'id': 'active'},
    ]),
    html.H2("Tenants", className='mt-4'),
    dbc.Row([
        dbc.Col(dbc.Input(id='auth-new-tenant-input', placeholder='New tenant ID'), width=4),
        dbc.Col(dbc.Button('Create tenant', id='auth-create-tenant-btn', color='primary'), width=2),
    ], className='mb-3'),
    html.Div(id='auth-tenant-message'),
    dbc.Button('Refresh', id='auth-refresh-btn', className='mt-3'),
], fluid=True)


def _list_users_table_data():
    return list_user_accounts()


def _create_user_from_form(username, password, role, tenant):
    try:
        create_user_account(username, password, role=role or 'read-only', tenant=tenant or 'default')
        return True, f"Created user '{username}'"
    except ValueError as exc:
        return False, str(exc)


def _deactivate_user_from_form(username):
    try:
        deactivate_user_account(username)
        return True, f"Deactivated '{username}'"
    except ValueError as exc:
        return False, str(exc)


def _create_tenant_from_form(tenant_id):
    try:
        create_tenant_account(tenant_id)
        return True, f"Created tenant '{tenant_id}'"
    except ValueError as exc:
        return False, str(exc)


@callback(
    [Output('auth-users-table', 'data'), Output('auth-user-message', 'children')],
    [Input('auth-create-user-btn', 'n_clicks'), Input('auth-deactivate-btn', 'n_clicks'),
     Input('auth-refresh-btn', 'n_clicks')],
    [State('auth-username-input', 'value'), State('auth-password-input', 'value'),
     State('auth-role-dropdown', 'value'), State('auth-tenant-input', 'value')],
    prevent_initial_call=False,
)
def _handle_user_actions(create_clicks, deactivate_clicks, refresh_clicks, username, password, role, tenant):
    triggered = dash.ctx.triggered_id
    message = ""
    if triggered == 'auth-create-user-btn':
        ok, message = _create_user_from_form(username, password, role, tenant)
    elif triggered == 'auth-deactivate-btn':
        ok, message = _deactivate_user_from_form(username)
    return _list_users_table_data(), message


@callback(
    Output('auth-tenant-message', 'children'),
    Input('auth-create-tenant-btn', 'n_clicks'),
    State('auth-new-tenant-input', 'value'),
    prevent_initial_call=True,
)
def _handle_tenant_actions(create_clicks, tenant_id):
    ok, message = _create_tenant_from_form(tenant_id)
    return message
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dash_auth_page.py -v`
Expected: PASS.

- [ ] **Step 5: Manual verification**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && python launch_dashboard.py &
sleep 2
curl -s -o /dev/null -w "auth page: %{http_code}\n" http://localhost:5000/dash/auth
kill %1
```

Expected: `200`.

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest --ignore=tests/test_web_ui.py -q`
Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/pages/auth.py tests/test_dash_auth_page.py
git commit -m "Add Dash Users & Tenants page"
```

---

### Task 12: End-to-end verification and push

**Files:** none (verification only).

- [ ] **Step 1: Full test suite**

Run: `python3 -m pytest --ignore=tests/test_web_ui.py -v --tb=short 2>&1 | tail -80`
Expected: all pass (350 from Phase A + all new tests from Tasks 1–11).

- [ ] **Step 2: Confirm every new Dash page navigates via the sidebar**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && python launch_dashboard.py &
sleep 2
for path in "" "registry" "jobs" "custom-rules" "audit" "auth"; do
  curl -s -o /dev/null -w "/dash/$path: %{http_code}\n" "http://localhost:5000/dash/$path"
done
kill %1
```

Expected: `200` for all 6 paths.

- [ ] **Step 3: Confirm the new API endpoints work end to end**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && python api.py --debug > /tmp/mdv_api_phaseb.log 2>&1 &
sleep 2
curl -s -X POST http://localhost:8000/api/security/hipaa-check -H "Content-Type: application/json" -d '{"ssn": ["123-45-6789"]}' | python3 -m json.tool
curl -s -X POST "http://localhost:8000/api/validate/data?batch_size=1" -H "Content-Type: application/json" -d '{"age": [1, 2, 3]}' | python3 -m json.tool
kill %1
rm -f /tmp/mdv_api_phaseb.log
```

Expected: `hipaa-check` returns `compliant: false` with `sample_count` (not `sample_values`) in `phi_detected`; `validate/data?batch_size=1` returns a `summary.batch_results` list with 3 entries.

- [ ] **Step 4: Confirm the CLI's new flags work end to end**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && echo '[{"age": 200, "diagnosis_code": "E11.9"}]' > /tmp/mdv_range_test.json
medical-validator validate /tmp/mdv_range_test.json --range age:0:120 --code-column diagnosis_code:icd10 --format summary
rm -f /tmp/mdv_range_test.json
```

Expected: runs without error and reports at least one issue (the out-of-range age).

- [ ] **Step 5: Push**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git log --oneline -15
git push origin master
```

---

## Self-Review

**Spec coverage:** Section A (per-request validator config, API + CLI) ✓ Tasks 1–2; Section B (security endpoints) ✓ Task 3; Section C (batch/cache) ✓ Task 4; Section D (Dash multi-page UI: shell, registry, jobs+reports, custom-rules, audit, auth, plus the auth.py refactor prerequisite) ✓ Tasks 5–11; end-to-end verification ✓ Task 12.

**Placeholder scan:** no TBD/TODO; every step has concrete, real code read from or verified against the actual current files rather than guessed, including `audit.py`'s `AUDIT_DB_PATH` constant name used in Task 10's test fixture.

**Type/interface consistency:** `validators_config` dict shape is identical across Task 1 (API) and Task 2 (CLI) — both produce/consume `required_columns`, `column_types`, `ranges`, `date_columns`, `min_date`, `max_date`, `code_columns`. `_run_validation_for_upload`'s return arity change (5 → 6 values, adding the result dict) is applied consistently across its Task 6 definition, Task 8's modification, and both call sites (the Dash callback and `tests/test_dash_layout.py`). `DASH_TENANT = 'default'` is used consistently across all 4 pages that need a tenant scope (registry, jobs, audit — auth has no tenant-scoping concept for its own CRUD).

**Corrections made during plan-writing (not left in the spec uncorrected):** the spec's illustrative JSON example for Section A used an envelope shape (`{"data": ..., "validators": ...}`) that doesn't match `/api/validate/data`'s real envelope-less wire format — the plan uses query/form parameters instead, documented in Global Constraints. The spec's Non-goals section assumed uploads are never persisted to disk; `api_validate_file` actually does save to a `NamedTemporaryFile`, so Task 3's `dataframe_from_request()` passes the real temp path to `SecurityAuditor` when available, giving its file-permission check genuine signal instead of always degrading to "no issues found."

---

## Phase B.1 Addendum: Complete the deferred Dash admin CRUD gaps

**Context:** Task 12's final whole-branch review (finding I2) found that Tasks 7, 8, 9, and 10 shipped list+create only for their respective pages, even though the design spec's Section D enumerated fuller CRUD (`get_dataset`/`update_dataset`/`delete_dataset` for Registry, `get_job` for Jobs, `count_log` for Audit, remove for Custom Rules) and report-download buttons on the Jobs page in addition to Validate. This was ruled a plan-vs-spec scope gap at the time (not a defect in what was built) and parked. The user has since asked for these gaps to be closed. This addendum adds 4 tasks (13-16) using the exact same pattern established by Tasks 6-11: pure, directly-testable helper functions; a single `@callback` per page keyed on `dash.ctx.triggered_id`; `register_page_once` for page registration (already in place, unaffected by these tasks).

**UI convention for the new actions (approved by the user):** an ID/name lookup `Input` field next to dedicated action buttons (View/Update/Delete/Remove), matching the existing create-form convention exactly — not Dash's native `row_selectable`/`row_deletable` DataTable props, to keep every page's interaction model consistent and every action a pure, unit-testable function.

---

### Task 13: Registry page — view/update/delete dataset

**Files:**
- Modify: `medical_data_validator/dashboard/pages/registry.py`
- Modify: `tests/test_dash_registry_page.py`

**Interfaces:**
- Consumes: `get_dataset(dataset_id) -> Optional[Dict]`, `update_dataset(dataset_id, *, description=None, tags=None) -> Optional[Dict]`, `delete_dataset(dataset_id) -> bool` (all in `medical_data_validator/registry.py`, verified signatures — `dataset_id` is the dataset's UUID `id`, not its `name`; there is no lookup-by-name function).
- Produces: `_get_dataset_details(dataset_id) -> Tuple[bool, str, str]` (ok, message, formatted-details-or-empty-string), `_update_dataset_from_form(dataset_id, description, tags_csv) -> Tuple[bool, str]`, `_delete_dataset_by_id(dataset_id) -> Tuple[bool, str]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dash_registry_page.py` (after the existing tests, keep everything above unchanged):

```python
def test_list_datasets_table_data_includes_id():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form, _list_datasets_table_data
    _create_dataset_from_form('id-check', '', '')
    rows = _list_datasets_table_data()
    row = next(r for r in rows if r['name'] == 'id-check')
    assert row['id']


def test_get_dataset_details_found():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form, _list_datasets_table_data, _get_dataset_details
    _create_dataset_from_form('lookup-me', 'a description', 'tag1')
    dataset_id = next(r['id'] for r in _list_datasets_table_data() if r['name'] == 'lookup-me')
    ok, message, details = _get_dataset_details(dataset_id)
    assert ok is True
    assert 'lookup-me' in details


def test_get_dataset_details_not_found():
    from medical_data_validator.dashboard.pages.registry import _get_dataset_details
    ok, message, details = _get_dataset_details('nonexistent-id')
    assert ok is False
    assert 'not found' in message.lower()


def test_get_dataset_details_requires_id():
    from medical_data_validator.dashboard.pages.registry import _get_dataset_details
    ok, message, details = _get_dataset_details('')
    assert ok is False


def test_update_dataset_from_form_changes_description():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form, _list_datasets_table_data, _update_dataset_from_form
    _create_dataset_from_form('update-me', 'old description', '')
    dataset_id = next(r['id'] for r in _list_datasets_table_data() if r['name'] == 'update-me')
    ok, message = _update_dataset_from_form(dataset_id, 'new description', '')
    assert ok is True
    rows = _list_datasets_table_data()
    row = next(r for r in rows if r['name'] == 'update-me')
    assert row['description'] == 'new description'


def test_update_dataset_from_form_not_found():
    from medical_data_validator.dashboard.pages.registry import _update_dataset_from_form
    ok, message = _update_dataset_from_form('nonexistent-id', 'x', '')
    assert ok is False


def test_delete_dataset_by_id_removes_it():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form, _list_datasets_table_data, _delete_dataset_by_id
    _create_dataset_from_form('delete-me', '', '')
    dataset_id = next(r['id'] for r in _list_datasets_table_data() if r['name'] == 'delete-me')
    ok, message = _delete_dataset_by_id(dataset_id)
    assert ok is True
    rows = _list_datasets_table_data()
    assert not any(r['name'] == 'delete-me' for r in rows)


def test_delete_dataset_by_id_not_found():
    from medical_data_validator.dashboard.pages.registry import _delete_dataset_by_id
    ok, message = _delete_dataset_by_id('nonexistent-id')
    assert ok is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python3 -m pytest tests/test_dash_registry_page.py -v`
Expected: FAIL — `id` not in `_list_datasets_table_data()`'s rows yet, and `_get_dataset_details`/`_update_dataset_from_form`/`_delete_dataset_by_id` don't exist yet.

- [ ] **Step 3: Replace `medical_data_validator/dashboard/pages/registry.py` entirely**

```python
"""Dash page: dataset registry (list, create, view, update, delete)."""

import dash
import dash_bootstrap_components as dbc
from dash import html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.utils import register_page_once
from medical_data_validator.registry import (
    list_datasets, register_dataset, get_dataset, update_dataset, delete_dataset,
)

register_page_once(__name__, path='/registry', name='Registry')

DASH_TENANT = 'default'

layout = dbc.Container([
    html.H2("Dataset Registry"),
    dbc.Row([
        dbc.Col(dbc.Input(id='registry-name-input', placeholder='Dataset name'), width=3),
        dbc.Col(dbc.Input(id='registry-description-input', placeholder='Description (optional)'), width=4),
        dbc.Col(dbc.Input(id='registry-tags-input', placeholder='Tags, comma-separated (optional)'), width=3),
        dbc.Col(dbc.Button('Register dataset', id='registry-create-btn', color='primary'), width=2),
    ], className='mb-3'),
    html.Div(id='registry-create-message'),
    dbc.Row([
        dbc.Col(dbc.Input(id='registry-lookup-id-input', placeholder='Dataset ID (see ID column below)'), width=5),
        dbc.Col(dbc.Button('View', id='registry-view-btn'), width=1),
        dbc.Col(dbc.Button('Update', id='registry-update-btn'), width=2),
        dbc.Col(dbc.Button('Delete', id='registry-delete-btn', color='danger'), width=2),
    ], className='mb-3'),
    html.Div(id='registry-lookup-message'),
    html.Pre(id='registry-details', className='bg-light p-2'),
    dash_table.DataTable(id='registry-table', columns=[
        {'name': 'ID', 'id': 'id'},
        {'name': 'Name', 'id': 'name'},
        {'name': 'Description', 'id': 'description'},
        {'name': 'Tags', 'id': 'tags'},
        {'name': 'Created', 'id': 'created_at'},
    ]),
    dbc.Button('Refresh', id='registry-refresh-btn', className='mt-3'),
], fluid=True)


def _list_datasets_table_data(tenant=DASH_TENANT):
    datasets = list_datasets(tenant=tenant)
    return [
        {
            'id': d['id'],
            'name': d['name'],
            'description': d.get('description') or '',
            'tags': ', '.join(d.get('tags') or []),
            'created_at': d.get('created_at', ''),
        }
        for d in datasets
    ]


def _create_dataset_from_form(name, description, tags_csv):
    name = (name or '').strip()
    if not name:
        return False, "Dataset name is required"
    tags = [t.strip() for t in (tags_csv or '').split(',') if t.strip()]
    try:
        register_dataset(name, tenant=DASH_TENANT, description=description or None, tags=tags or None)
        return True, f"Registered '{name}'"
    except ValueError as exc:
        return False, str(exc)


def _get_dataset_details(dataset_id):
    dataset_id = (dataset_id or '').strip()
    if not dataset_id:
        return False, "Dataset ID is required", ""
    dataset = get_dataset(dataset_id)
    if dataset is None:
        return False, f"Dataset '{dataset_id}' not found", ""
    lines = [f"{key}: {value}" for key, value in dataset.items()]
    return True, "", "\n".join(lines)


def _update_dataset_from_form(dataset_id, description, tags_csv):
    dataset_id = (dataset_id or '').strip()
    if not dataset_id:
        return False, "Dataset ID is required"
    tags = [t.strip() for t in (tags_csv or '').split(',') if t.strip()] if tags_csv else None
    updated = update_dataset(dataset_id, description=description or None, tags=tags)
    if updated is None:
        return False, f"Dataset '{dataset_id}' not found"
    return True, f"Updated '{updated['name']}'"


def _delete_dataset_by_id(dataset_id):
    dataset_id = (dataset_id or '').strip()
    if not dataset_id:
        return False, "Dataset ID is required"
    if delete_dataset(dataset_id):
        return True, f"Deleted dataset '{dataset_id}'"
    return False, f"Dataset '{dataset_id}' not found"


@callback(
    [Output('registry-table', 'data'), Output('registry-create-message', 'children'),
     Output('registry-lookup-message', 'children'), Output('registry-details', 'children')],
    [Input('registry-create-btn', 'n_clicks'), Input('registry-refresh-btn', 'n_clicks'),
     Input('registry-view-btn', 'n_clicks'), Input('registry-update-btn', 'n_clicks'),
     Input('registry-delete-btn', 'n_clicks')],
    [State('registry-name-input', 'value'),
     State('registry-description-input', 'value'),
     State('registry-tags-input', 'value'),
     State('registry-lookup-id-input', 'value')],
    prevent_initial_call=False,
)
def _handle_registry_actions(create_clicks, refresh_clicks, view_clicks, update_clicks, delete_clicks,
                              name, description, tags_csv, lookup_id):
    triggered = dash.ctx.triggered_id
    create_message = ""
    lookup_message = ""
    details = ""
    if triggered == 'registry-create-btn':
        _ok, create_message = _create_dataset_from_form(name, description, tags_csv)
    elif triggered == 'registry-view-btn':
        _ok, lookup_message, details = _get_dataset_details(lookup_id)
    elif triggered == 'registry-update-btn':
        _ok, lookup_message = _update_dataset_from_form(lookup_id, description, tags_csv)
    elif triggered == 'registry-delete-btn':
        _ok, lookup_message = _delete_dataset_by_id(lookup_id)
    return _list_datasets_table_data(), create_message, lookup_message, details
```

Note: `description`/`tags_csv` are shared `State`s between the create form and the update action (per the approved design — reusing the existing inputs rather than adding a second form). This means "Update" reads whatever is currently typed in the description/tags inputs, same as "Register dataset" does.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python3 -m pytest tests/test_dash_registry_page.py -v`
Expected: PASS (all tests, old and new).

- [ ] **Step 5: Manual verification**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && SECRET_KEY=test-secret .venv/bin/python launch_dashboard.py &
sleep 2
curl -s -o /dev/null -w "registry page: %{http_code}\n" http://localhost:5000/dash/registry
kill %1
```
Expected: `200`.

- [ ] **Step 6: Run the full test suite**

Run: `.venv/bin/python3 -m pytest --ignore=tests/test_web_ui.py --junitxml=/tmp/task13_junit.xml` (read the XML's `tests=`/`errors=`/`failures=`/`skipped=` attributes — do not trust a piped terminal summary line in this environment)
Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/pages/registry.py tests/test_dash_registry_page.py
git commit -m "Add view/update/delete dataset actions to the Dash Registry page"
```

---

### Task 14: Jobs page — view job detail + PDF/CSV downloads

**Files:**
- Modify: `medical_data_validator/dashboard/pages/jobs.py`
- Modify: `tests/test_dash_jobs_page.py`

**Interfaces:**
- Consumes: `get_job(job_id) -> Optional[Dict]` (`medical_data_validator/jobs.py`, verified signature). Verified: for `job_type='validate'` jobs, `job['result']` is exactly a `ValidationResult.to_dict()`-shaped dict — the same shape `generate_pdf_report`/`generate_csv_report` (`medical_data_validator/reports.py`) already consume on the Validate page (Task 8). For `job_type='anonymize'` jobs, `result` is `{'data': ..., 'rows': ...}` — NOT report-compatible, so downloads only apply to completed `validate` jobs.
- Produces: `_get_job_detail(job_id) -> Tuple[bool, str, Optional[dict]]` (ok, summary-message, the job dict or `None`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dash_jobs_page.py` (after the existing tests, keep everything above unchanged):

```python
def test_get_job_detail_found():
    from medical_data_validator.dashboard.pages.jobs import _submit_job_from_form, _list_jobs_table_data, _get_job_detail
    _submit_job_from_form('validate', '{"age": [200]}')
    for _ in range(20):
        rows = _list_jobs_table_data()
        if rows and rows[0]['status'] in ('completed', 'failed'):
            break
        time.sleep(0.1)
    job_id = rows[0]['id']
    ok, message, job = _get_job_detail(job_id)
    assert ok is True
    assert job is not None
    assert job['id'] == job_id
    assert job['job_type'] == 'validate'


def test_get_job_detail_not_found():
    from medical_data_validator.dashboard.pages.jobs import _get_job_detail
    ok, message, job = _get_job_detail('nonexistent-id')
    assert ok is False
    assert job is None
    assert 'not found' in message.lower()


def test_get_job_detail_requires_id():
    from medical_data_validator.dashboard.pages.jobs import _get_job_detail
    ok, message, job = _get_job_detail('')
    assert ok is False
    assert job is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python3 -m pytest tests/test_dash_jobs_page.py -v`
Expected: FAIL — `_get_job_detail` doesn't exist yet.

- [ ] **Step 3: Replace `medical_data_validator/dashboard/pages/jobs.py` entirely**

```python
"""Dash page: async job submission, status polling, detail view, and report downloads."""

import json

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.utils import register_page_once
from medical_data_validator.jobs import submit_job, list_jobs, get_job

register_page_once(__name__, path='/jobs', name='Jobs')

DASH_TENANT = 'default'

layout = dbc.Container([
    html.H2("Validation Jobs"),
    dbc.Row([
        dbc.Col(dcc.Dropdown(id='jobs-type-dropdown',
                              options=[{'label': 'Validate', 'value': 'validate'},
                                       {'label': 'Anonymize', 'value': 'anonymize'}],
                              value='validate'), width=2),
        dbc.Col(dbc.Textarea(id='jobs-payload-input', placeholder='{"data": {"age": [200]}}'), width=7),
        dbc.Col(dbc.Button('Submit job', id='jobs-submit-btn', color='primary'), width=3),
    ], className='mb-3'),
    html.Div(id='jobs-submit-message'),
    dbc.Row([
        dbc.Col(dbc.Input(id='jobs-lookup-id-input', placeholder='Job ID (see ID column below)'), width=5),
        dbc.Col(dbc.Button('View Result', id='jobs-view-btn'), width=2),
        dbc.Col(dbc.Button("Download PDF", id='jobs-download-pdf-btn'), width=2),
        dbc.Col(dbc.Button("Download CSV", id='jobs-download-csv-btn'), width=2),
    ], className='mb-3'),
    html.Div(id='jobs-detail-message'),
    dcc.Download(id='jobs-download-report'),
    dcc.Store(id='jobs-last-detail-result'),
    dash_table.DataTable(id='jobs-table', columns=[
        {'name': 'ID', 'id': 'id'},
        {'name': 'Type', 'id': 'job_type'},
        {'name': 'Status', 'id': 'status'},
        {'name': 'Created', 'id': 'created_at'},
    ]),
    dbc.Button('Refresh', id='jobs-refresh-btn', className='mt-3'),
], fluid=True)


def _list_jobs_table_data(tenant=DASH_TENANT):
    return [
        {
            'id': j['id'],
            'job_type': j['job_type'],
            'status': j['status'],
            'created_at': j.get('created_at', ''),
        }
        for j in list_jobs(tenant=tenant)
    ]


def _submit_job_from_form(job_type, payload_json):
    if job_type not in ('validate', 'anonymize'):
        return False, "job_type must be 'validate' or 'anonymize'"
    try:
        payload = json.loads(payload_json) if payload_json else {}
    except (TypeError, ValueError) as exc:
        return False, f"Invalid JSON payload: {exc}"
    if not isinstance(payload, dict):
        return False, "payload must be a JSON object"
    submit_job(job_type, payload, tenant=DASH_TENANT, username='dash-ui')
    return True, "Job submitted"


def _get_job_detail(job_id):
    job_id = (job_id or '').strip()
    if not job_id:
        return False, "Job ID is required", None
    job = get_job(job_id)
    if job is None:
        return False, f"Job '{job_id}' not found", None
    summary = f"status={job['status']} type={job['job_type']}"
    if job.get('error'):
        summary += f" error={job['error']}"
    return True, summary, job


@callback(
    [Output('jobs-table', 'data'), Output('jobs-submit-message', 'children'),
     Output('jobs-detail-message', 'children'), Output('jobs-last-detail-result', 'data')],
    [Input('jobs-submit-btn', 'n_clicks'), Input('jobs-refresh-btn', 'n_clicks'),
     Input('jobs-view-btn', 'n_clicks')],
    [State('jobs-type-dropdown', 'value'), State('jobs-payload-input', 'value'),
     State('jobs-lookup-id-input', 'value')],
    prevent_initial_call=False,
)
def _handle_jobs_actions(submit_clicks, refresh_clicks, view_clicks, job_type, payload_json, lookup_id):
    triggered = dash.ctx.triggered_id
    submit_message = ""
    detail_message = ""
    detail_job = dash.no_update
    if triggered == 'jobs-submit-btn':
        _ok, submit_message = _submit_job_from_form(job_type, payload_json)
    elif triggered == 'jobs-view-btn':
        _ok, detail_message, detail_job = _get_job_detail(lookup_id)
    return _list_jobs_table_data(), submit_message, detail_message, detail_job


@callback(
    Output('jobs-download-report', 'data'),
    [Input('jobs-download-pdf-btn', 'n_clicks'), Input('jobs-download-csv-btn', 'n_clicks')],
    State('jobs-last-detail-result', 'data'),
    prevent_initial_call=True,
)
def _download_job_report(pdf_clicks, csv_clicks, job):
    if not job or job.get('job_type') != 'validate' or job.get('status') != 'completed' or not job.get('result'):
        return dash.no_update
    from medical_data_validator.reports import generate_pdf_report, generate_csv_report
    triggered = dash.ctx.triggered_id
    result_dict = job['result']
    if triggered == 'jobs-download-pdf-btn':
        return dcc.send_bytes(generate_pdf_report(result_dict), f"job_{job['id']}_report.pdf")
    return dcc.send_string(generate_csv_report(result_dict), f"job_{job['id']}_report.csv")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python3 -m pytest tests/test_dash_jobs_page.py -v`
Expected: PASS (all tests, old and new).

- [ ] **Step 5: Manual verification**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && SECRET_KEY=test-secret .venv/bin/python launch_dashboard.py &
sleep 2
curl -s -o /dev/null -w "jobs page: %{http_code}\n" http://localhost:5000/dash/jobs
kill %1
```
Expected: `200`.

- [ ] **Step 6: Run the full test suite**

Run: `.venv/bin/python3 -m pytest --ignore=tests/test_web_ui.py --junitxml=/tmp/task14_junit.xml` (read the XML attributes, not a piped terminal summary)
Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/pages/jobs.py tests/test_dash_jobs_page.py
git commit -m "Add job detail view and PDF/CSV report downloads to the Dash Jobs page"
```

---

### Task 15: Audit page — total record count

**Files:**
- Modify: `medical_data_validator/dashboard/pages/audit.py`
- Modify: `tests/test_dash_audit_page.py`

**Interfaces:**
- Consumes: `count_log(**kwargs) -> int` (`medical_data_validator/audit.py`, verified signature — accepts the same filter kwargs as `query_log`, e.g. `tenant=`).
- Produces: `_count_audit_log(tenant=DASH_TENANT) -> int`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dash_audit_page.py` (after the existing tests, keep everything above unchanged):

```python
def test_count_audit_log_matches_number_logged():
    from medical_data_validator.dashboard.pages.audit import _count_audit_log
    for i in range(3):
        audit.log_event('validate', username=f'user-{i}', tenant='default')
    assert _count_audit_log() == 3


def test_count_audit_log_filters_by_tenant():
    from medical_data_validator.dashboard.pages.audit import _count_audit_log
    audit.log_event('validate', username='alice', tenant='default')
    audit.log_event('validate', username='bob', tenant='other-tenant')
    assert _count_audit_log(tenant='default') == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python3 -m pytest tests/test_dash_audit_page.py -v`
Expected: FAIL — `_count_audit_log` doesn't exist yet.

- [ ] **Step 3: Replace `medical_data_validator/dashboard/pages/audit.py` entirely**

```python
"""Dash page: audit log viewer."""

import dash_bootstrap_components as dbc
from dash import html, dash_table, Input, Output, callback

from medical_data_validator.dashboard.utils import register_page_once
from medical_data_validator.audit import query_log, count_log

register_page_once(__name__, path='/audit', name='Audit Log')

DASH_TENANT = 'default'

layout = dbc.Container([
    html.H2("Audit Log"),
    html.Div(id='audit-count-message', className='mb-2'),
    dash_table.DataTable(id='audit-table', columns=[
        {'name': 'Timestamp', 'id': 'timestamp'},
        {'name': 'Username', 'id': 'username'},
        {'name': 'Event Type', 'id': 'event_type'},
        {'name': 'Dataset ID', 'id': 'dataset_id'},
    ], page_size=25),
    dbc.Button('Refresh', id='audit-refresh-btn', className='mt-3'),
], fluid=True)


def _list_audit_log_table_data(tenant=DASH_TENANT, limit=100):
    records = query_log(tenant=tenant, limit=limit)
    return [
        {
            'timestamp': r.get('timestamp', ''),
            'username': r.get('username', ''),
            'event_type': r.get('event_type', ''),
            'dataset_id': r.get('dataset_id', ''),
        }
        for r in records
    ]


def _count_audit_log(tenant=DASH_TENANT):
    return count_log(tenant=tenant)


@callback(
    [Output('audit-table', 'data'), Output('audit-count-message', 'children')],
    Input('audit-refresh-btn', 'n_clicks'),
    prevent_initial_call=False,
)
def _handle_audit_refresh(n_clicks):
    rows = _list_audit_log_table_data()
    total = _count_audit_log()
    return rows, f"Showing {len(rows)} of {total} records"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python3 -m pytest tests/test_dash_audit_page.py -v`
Expected: PASS (all tests, old and new).

- [ ] **Step 5: Manual verification**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && SECRET_KEY=test-secret .venv/bin/python launch_dashboard.py &
sleep 2
curl -s -o /dev/null -w "audit page: %{http_code}\n" http://localhost:5000/dash/audit
kill %1
```
Expected: `200`.

- [ ] **Step 6: Run the full test suite**

Run: `.venv/bin/python3 -m pytest --ignore=tests/test_web_ui.py --junitxml=/tmp/task15_junit.xml` (read the XML attributes, not a piped terminal summary)
Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/pages/audit.py tests/test_dash_audit_page.py
git commit -m "Add total record count to the Dash Audit Log page"
```

---

### Task 16: Custom Rules page — remove a rule

**Files:**
- Modify: `medical_data_validator/dashboard/pages/custom_rules.py`
- Modify: `tests/test_dash_custom_rules_page.py`

**Interfaces:**
- Consumes: `_custom_rules_storage` (module-level list in `medical_data_validator/dashboard/routes.py`, same as Task 9). Mirrors `routes.py:api_remove_custom_rule`'s pop-by-name logic exactly (verified: iterate, find by `name`, `.pop(i)`, else "not found").
- Produces: `_remove_custom_rule_from_form(name) -> Tuple[bool, str]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dash_custom_rules_page.py` (after the existing tests, keep everything above unchanged):

```python
def test_remove_custom_rule_from_form_removes_it():
    from medical_data_validator.dashboard.pages.custom_rules import _add_custom_rule_from_form, _remove_custom_rule_from_form, _list_custom_rules_table_data
    _add_custom_rule_from_form('remove-me', r'\bfax\b', 'medium')
    ok, message = _remove_custom_rule_from_form('remove-me')
    assert ok is True
    rows = _list_custom_rules_table_data()
    assert not any(r['name'] == 'remove-me' for r in rows)


def test_remove_custom_rule_from_form_not_found():
    from medical_data_validator.dashboard.pages.custom_rules import _remove_custom_rule_from_form
    ok, message = _remove_custom_rule_from_form('nonexistent-rule')
    assert ok is False
    assert 'not found' in message.lower()


def test_remove_custom_rule_from_form_requires_name():
    from medical_data_validator.dashboard.pages.custom_rules import _remove_custom_rule_from_form
    ok, message = _remove_custom_rule_from_form('')
    assert ok is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python3 -m pytest tests/test_dash_custom_rules_page.py -v`
Expected: FAIL — `_remove_custom_rule_from_form` doesn't exist yet.

- [ ] **Step 3: Replace `medical_data_validator/dashboard/pages/custom_rules.py` entirely**

```python
"""Dash page: compliance custom-rules (list, add, remove)."""

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, dash_table, Input, Output, State, callback

from medical_data_validator.dashboard.routes import _custom_rules_storage
from medical_data_validator.dashboard.utils import register_page_once

register_page_once(__name__, path='/custom-rules', name='Custom Rules')

layout = dbc.Container([
    html.H2("Custom Compliance Rules"),
    dbc.Row([
        dbc.Col(dbc.Input(id='rules-name-input', placeholder='Rule name'), width=3),
        dbc.Col(dbc.Input(id='rules-pattern-input', placeholder='Regex pattern'), width=4),
        dbc.Col(dcc.Dropdown(id='rules-severity-dropdown',
                              options=[{'label': s, 'value': s} for s in ('low', 'medium', 'high', 'critical')],
                              value='medium'), width=2),
        dbc.Col(dbc.Button('Add rule', id='rules-add-btn', color='primary'), width=2),
        dbc.Col(dbc.Button('Remove', id='rules-remove-btn', color='danger'), width=1),
    ], className='mb-3'),
    html.Div(id='rules-add-message'),
    dash_table.DataTable(id='rules-table', columns=[
        {'name': 'Name', 'id': 'name'},
        {'name': 'Pattern', 'id': 'pattern'},
        {'name': 'Severity', 'id': 'severity'},
    ]),
    dbc.Button('Refresh', id='rules-refresh-btn', className='mt-3'),
], fluid=True)


def _list_custom_rules_table_data():
    return [
        {'name': r['name'], 'pattern': r['pattern'], 'severity': r.get('severity', 'medium')}
        for r in _custom_rules_storage
    ]


def _add_custom_rule_from_form(name, pattern, severity):
    name = (name or '').strip()
    pattern = (pattern or '').strip()
    if not name or not pattern:
        return False, "Both name and pattern are required"
    rule_data = {'name': name, 'pattern': pattern, 'severity': severity or 'medium',
                 'field_pattern': None, 'description': '', 'recommendation': None}
    for i, existing in enumerate(_custom_rules_storage):
        if existing['name'] == name:
            _custom_rules_storage[i] = rule_data
            return True, f"Updated rule '{name}'"
    _custom_rules_storage.append(rule_data)
    return True, f"Added rule '{name}'"


def _remove_custom_rule_from_form(name):
    name = (name or '').strip()
    if not name:
        return False, "Rule name is required"
    for i, existing in enumerate(_custom_rules_storage):
        if existing['name'] == name:
            _custom_rules_storage.pop(i)
            return True, f"Removed rule '{name}'"
    return False, f"Rule '{name}' not found"


@callback(
    [Output('rules-table', 'data'), Output('rules-add-message', 'children')],
    [Input('rules-add-btn', 'n_clicks'), Input('rules-remove-btn', 'n_clicks'), Input('rules-refresh-btn', 'n_clicks')],
    [State('rules-name-input', 'value'), State('rules-pattern-input', 'value'),
     State('rules-severity-dropdown', 'value')],
    prevent_initial_call=False,
)
def _handle_rules_actions(add_clicks, remove_clicks, refresh_clicks, name, pattern, severity):
    triggered = dash.ctx.triggered_id
    message = ""
    if triggered == 'rules-add-btn':
        _ok, message = _add_custom_rule_from_form(name, pattern, severity)
    elif triggered == 'rules-remove-btn':
        _ok, message = _remove_custom_rule_from_form(name)
    return _list_custom_rules_table_data(), message
```

Note: "Remove" reads the same `rules-name-input` State as "Add" (per the approved design — one name field, multiple action buttons), so the user types a rule name and clicks either Add (with a pattern) or Remove (pattern/severity ignored).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python3 -m pytest tests/test_dash_custom_rules_page.py -v`
Expected: PASS (all tests, old and new).

- [ ] **Step 5: Manual verification**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && SECRET_KEY=test-secret .venv/bin/python launch_dashboard.py &
sleep 2
curl -s -o /dev/null -w "custom rules page: %{http_code}\n" http://localhost:5000/dash/custom-rules
kill %1
```
Expected: `200`.

- [ ] **Step 6: Run the full test suite**

Run: `.venv/bin/python3 -m pytest --ignore=tests/test_web_ui.py --junitxml=/tmp/task16_junit.xml` (read the XML attributes, not a piped terminal summary)
Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
cd "/home/lenovo/Own Projects/medical-data-validator" && git add medical_data_validator/dashboard/pages/custom_rules.py tests/test_dash_custom_rules_page.py
git commit -m "Add remove-rule action to the Dash Custom Rules page"
```

---

### Task 17: End-to-end verification of the addendum

**Files:** none (verification only).

- [ ] **Step 1:** Full test suite: `.venv/bin/python3 -m pytest --ignore=tests/test_web_ui.py --junitxml=/tmp/task17_junit.xml` — expect all pass, no new failures.
- [ ] **Step 2:** Confirm all 6 Dash pages still navigate: `for path in "" "registry" "jobs" "custom-rules" "audit" "auth"; do curl -s -o /dev/null -w "/dash/$path: %{http_code}\n" "http://localhost:5000/dash/$path"; done` against a running `launch_dashboard.py` — expect `200` for all.
- [ ] **Step 3:** Update `docs/superpowers/specs/2026-08-22-phase-b-coverage-gaps-design.md`'s Section D or add a note that the Dash admin pages now match the originally-specified capability set (view/update/delete for Registry, job detail + downloads for Jobs, count for Audit, remove for Custom Rules), closing the gap Task 12's final review found.
- [ ] **Step 4:** Push: `git push origin master` (pending explicit user go-ahead, same as the original Task 12).
