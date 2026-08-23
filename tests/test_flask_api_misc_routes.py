"""Characterization tests for the remaining untested parts of
medical_data_validator/dashboard/routes.py (Task 3 of the coverage plan;
Task 2 covered the v1.2/compliance/analytics/monitoring/custom-rules/
anonymize endpoints in tests/test_flask_api_v12_endpoints.py).

Covers:
- The legacy /upload endpoint (full validate-and-chart flow + its own
  inlined file-type/size/filename checks).
- Trivial routes: /health (legacy), /home, /about, /profiles (legacy).
- api_validate_data / api_validate_file's previously-untested edge branches
  (non-JSON body, DataFrame-construction failure, validator-construction
  failure, validation-itself failure, compliance-disabled branch, oversized
  file, unsafe filename, malformed 'validators' JSON).
- Pure helper functions with no Flask involved: generate_compliance_report,
  convert_validation_issue_to_dict, convert_numpy_types.
- dataframe_from_request's remaining branches (empty filename, bad
  extension, non-dict JSON payload), exercised via /api/security/hipaa-check
  since that's the real endpoint that calls it.

Per the task brief, explicitly NOT targeted here (would require breaking
the install or chasing an edge-case-within-an-edge-case):
- routes.py lines 35-41, 1254-1258, 1266-1270, 1278-1282, 1290-1294,
  1302-1306, 1314-1318, 1332-1337 (all `except ImportError` route
  registration fallbacks).
- routes.py lines 84-90 (convert_numpy_types' exotic-type str() fallback,
  both the plain else-branch and the outer except-Exception handler).
"""

import io
import json

import numpy as np
import pandas as pd
import pytest

from medical_data_validator.dashboard.app import create_dashboard_app
from medical_data_validator.dashboard.routes import (
    api_validate_data,
    convert_numpy_types,
    convert_validation_issue_to_dict,
    generate_compliance_report,
)
from medical_data_validator.core import MedicalDataValidator, ValidationIssue, ValidationResult
import medical_data_validator.core as core_module
from medical_data_validator import __version__


@pytest.fixture(scope="module")
def app():
    application = create_dashboard_app()
    application.config['TESTING'] = True
    return application


@pytest.fixture(scope="module")
def client(app):
    with app.test_client() as client:
        yield client


# ---------------------------------------------------------------------------
# Trivial routes: /health, /home, /about, /profiles
# ---------------------------------------------------------------------------

class TestTrivialRoutes:
    def test_legacy_health_endpoint(self, client):
        resp = client.get('/health')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['status'] == 'healthy'
        assert body['version'] == __version__
        assert 'timestamp' in body
        # Unlike /api/health, the legacy endpoint has no standards_supported key.
        assert 'standards_supported' not in body

    def test_bare_root_redirects_to_home(self, client):
        # "/" has no @app.route of its own — flask_restx.Api (constructed
        # with no prefix) already owns that endpoint name ("root") and always
        # 404s there by design, so the redirect is implemented via the 404
        # handler instead. Guard against that wiring regressing silently.
        resp = client.get('/')
        assert resp.status_code == 302
        assert resp.headers['Location'] == '/home'

    def test_unknown_path_still_404s(self, client):
        resp = client.get('/this-path-does-not-exist')
        assert resp.status_code == 404

    def test_home_renders_html(self, client):
        resp = client.get('/home')
        assert resp.status_code == 200
        assert 'text/html' in resp.content_type
        assert len(resp.data) > 0

    def test_about_renders_html(self, client):
        resp = client.get('/about')
        assert resp.status_code == 200
        assert 'text/html' in resp.content_type
        assert len(resp.data) > 0

    def test_legacy_profiles_endpoint(self, client):
        resp = client.get('/profiles')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body == {
            'clinical_trials': 'Clinical trial data validation',
            'ehr': 'Electronic health records validation',
            'imaging': 'Medical imaging metadata validation',
            'lab': 'Laboratory data validation',
        }


# ---------------------------------------------------------------------------
# Legacy /upload endpoint
# ---------------------------------------------------------------------------

class TestLegacyUpload:
    def test_happy_path_full_flow(self, client):
        csv_bytes = b"ssn,name\n123-45-6789,Alice\n987-65-4321,Bob\n"
        resp = client.post(
            '/upload',
            data={
                'file': (io.BytesIO(csv_bytes), 'patients.csv'),
                'detect_phi': 'true',
                'quality_checks': 'true',
            },
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        for key in ('result', 'charts', 'compliance_report', 'summary'):
            assert key in body

        summary = body['summary']
        assert summary['total_rows'] == 2
        assert summary['total_columns'] == 2
        assert summary['total_issues'] == summary['error_count'] + summary['warning_count'] + summary['info_count']

        # generate_compliance_report was called with the full 6-standard list.
        report = body['compliance_report']
        for standard in ('hipaa', 'icd10', 'loinc', 'cpt', 'fhir', 'omop'):
            assert standard in report
        # PHI (SSN) is present in the uploaded CSV, so HIPAA must flag it.
        assert report['hipaa']['compliant'] is False
        assert any('SSN' in issue for issue in report['hipaa']['issues'])

    def test_no_file_provided_400(self, client):
        resp = client.post('/upload')
        assert resp.status_code == 400
        assert resp.get_json() == {'error': 'No file provided'}

    def test_empty_filename_400(self, client):
        resp = client.post(
            '/upload',
            data={'file': (io.BytesIO(b''), '')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert resp.get_json() == {'error': 'No file selected'}

    def test_unsupported_extension_400(self, client):
        resp = client.post(
            '/upload',
            data={'file': (io.BytesIO(b'x'), 'notes.txt')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert resp.get_json() == {'error': 'File type not allowed. Supported formats: CSV, Excel, JSON, Parquet'}

    def test_unsafe_filename_400(self, client):
        resp = client.post(
            '/upload',
            data={'file': (io.BytesIO(b'a,b\n1,2\n'), 'bad name.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert resp.get_json() == {'error': 'Invalid filename characters'}

    def test_corrupt_content_returns_500(self, client):
        """A .xlsx extension with non-Excel bytes passes the extension/size/
        filename checks but fails at load_data(), landing in the endpoint's
        blanket except-Exception handler."""
        resp = client.post(
            '/upload',
            data={'file': (io.BytesIO(b'not an excel file'), 'broken.xlsx')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 500
        body = resp.get_json()
        assert 'error' in body
        assert body['error'].startswith('Validation failed:')

    def test_oversized_file_bypasses_the_manual_400_check(self, client):
        """Discovered bug: this endpoint's manual 16MB file-size check
        (`if file_size > 16 * 1024 * 1024: return 400 'File too large'...`)
        is dead code in practice. Flask's app.config['MAX_CONTENT_LENGTH'] is
        set to the exact same 16MB (dashboard/app.py), which Werkzeug
        enforces at the WSGI layer BEFORE the view function body ever runs.
        Since the uploaded file's bytes are a strict subset of the total
        request body, file_size can never exceed 16MB while the request
        itself is still small enough to reach the manual check. In practice,
        any oversized upload is intercepted earlier as a
        RequestEntityTooLarge, which this endpoint's blanket
        `except Exception` then reports as a generic 500 instead of the
        intended clean 400. Same issue affects api_validate_file (routes.py
        ~465)."""
        big_csv = b'a,b\n' + b'1,2\n' * (5 * 1024 * 1024)  # ~20MB, well over the cap
        resp = client.post(
            '/upload',
            data={'file': (io.BytesIO(big_csv), 'big.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 500
        body = resp.get_json()
        assert 'error' in body
        assert '413' in body['error'] or 'Request Entity Too Large' in body['error']


# ---------------------------------------------------------------------------
# api_validate_data edge branches -- called directly via test_request_context
# so the exact function-level response is inspected without flask-restx's
# marshal_with reshaping the body (routes.py's api_validate_data is wired to
# /api/validate/data exclusively through medical_data_validator/dashboard/docs.py).
# ---------------------------------------------------------------------------

class TestApiValidateDataEdgeBranches:
    def test_json_literal_null_yields_none_data_400(self, app):
        """A JSON body that is the literal `null` decodes to Python None,
        which is the real, reachable way to hit the `if data is None`
        branch (routes.py ~299-301) -- request.get_json() raises on
        malformed JSON rather than returning None, so a syntactically valid
        `null` body is the only legitimate trigger."""
        with app.test_request_context(
            '/api/validate/data', method='POST', data='null', content_type='application/json'
        ):
            resp, status = api_validate_data()
            assert status == 400
            assert resp.get_json() == {'success': False, 'error': 'Invalid JSON data'}

    def test_dataframe_construction_failure_500(self, app):
        """A JSON body that decodes to a bare string is neither falsy nor a
        dict, so it falls to `df = pd.DataFrame(data)` (~368), which pandas
        rejects outright -- exercising the DataFrame-construction failure
        branch (~372-374)."""
        with app.test_request_context(
            '/api/validate/data', method='POST', data='"just a string"', content_type='application/json'
        ):
            resp, status = api_validate_data()
            assert status == 500
            body = resp.get_json()
            assert body['success'] is False
            assert 'Failed to create DataFrame' in body['error']

    def test_validator_construction_failure_500(self, app):
        """An invalid min_date in validators_config reaches DateValidator's
        constructor (`pd.to_datetime(min_date)`), which raises immediately
        -- inside create_validator(), exercising the validator-construction
        failure branch (~385-387)."""
        validators_config = json.dumps({'date_columns': ['visit_date'], 'min_date': 'not-a-real-date-xyz'})
        with app.test_request_context(
            f'/api/validate/data?validators={validators_config}',
            method='POST',
            json={'visit_date': ['2020-01-01']},
        ):
            resp, status = api_validate_data()
            assert status == 500
            body = resp.get_json()
            assert body['success'] is False
            assert 'Failed to create validator' in body['error']

    def test_validation_itself_failure_500(self, app, monkeypatch):
        """Simulates a validator whose .validate() call raises, to exercise
        the "Error during validation" branch (~405-407). No rule in the
        current codebase naturally raises out of MedicalDataValidator.validate
        (per-rule and per-engine exceptions are all caught internally and
        turned into issues), so MedicalDataValidator.validate itself -- a
        collaborator, not the route code under test -- is monkeypatched for
        the duration of this one test to simulate an unexpected crash."""
        def boom(self, data):
            raise RuntimeError('simulated validation crash')

        monkeypatch.setattr(MedicalDataValidator, 'validate', boom)

        with app.test_request_context('/api/validate/data', method='POST', json={'a': [1, 2]}):
            resp, status = api_validate_data()
            assert status == 500
            body = resp.get_json()
            assert body['success'] is False
            assert 'Validation failed: simulated validation crash' in body['error']

    def test_dict_payload_with_scalar_value_gets_broadcast(self, app):
        """Mirrors dataframe_from_request's scalar-broadcast branch: a JSON
        dict body with a non-list value takes the
        `padded_data[key] = [value] * max_length` branch (~362-364)."""
        with app.test_request_context(
            '/api/validate/data', method='POST', json={'ssn': '123-45-6789', 'notes': ['a', 'b', 'c']}
        ):
            resp = api_validate_data()
            assert not isinstance(resp, tuple)
            body = resp.get_json()
            assert body['success'] is True
            assert body['summary']['total_rows'] == 3

    def test_compliance_disabled_or_unavailable_yields_empty_report(self, app, monkeypatch):
        """When the compliance engine is unavailable, MedicalDataValidator
        still records enable_compliance=True but never populates
        result.summary['compliance_report'] -- exercising the "else:
        compliance_report = {}" branch (~414-417). Simulated by temporarily
        making ComplianceEngine unavailable in medical_data_validator.core
        (a collaborator's availability, not the route logic under test),
        mirroring the ImportError-fallback simulation already used in
        tests/test_security_flask_optional_import.py."""
        monkeypatch.setattr(core_module, 'ComplianceEngine', None)

        with app.test_request_context('/api/validate/data', method='POST', json={'a': [1, 2]}):
            resp = api_validate_data()
            # A 200 success response is a bare jsonify() Response, not a
            # (response, status) tuple like the error branches return.
            assert not isinstance(resp, tuple)
            body = resp.get_json()
            assert body['success'] is True
            assert body['compliance_report'] == {}


# ---------------------------------------------------------------------------
# api_validate_file edge branches
# ---------------------------------------------------------------------------

class TestApiValidateFileEdgeBranches:
    def test_empty_filename_400(self, client):
        resp = client.post(
            '/api/validate/file',
            data={'file': (io.BytesIO(b''), '')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'No file selected'

    def test_unsafe_filename_400(self, client):
        resp = client.post(
            '/api/validate/file',
            data={'file': (io.BytesIO(b'a,b\n1,2\n'), 'bad name.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Invalid filename characters'

    def test_malformed_validators_json_400(self, client):
        resp = client.post(
            '/api/validate/file',
            data={
                'file': (io.BytesIO(b'a,b\n1,2\n'), 'ok.csv'),
                'validators': 'not-json',
            },
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert "Invalid 'validators' JSON" in resp.get_json()['error']

    def test_oversized_file_bypasses_the_manual_400_check(self, client):
        """Same discovered issue as the legacy /upload endpoint (see
        TestLegacyUpload.test_oversized_file_bypasses_the_manual_400_check):
        the manual 16MB check at routes.py ~464-465 is unreachable because
        Flask's MAX_CONTENT_LENGTH is configured to the identical 16MB limit
        and is enforced first, at the WSGI layer."""
        big_csv = b'a,b\n' + b'1,2\n' * (5 * 1024 * 1024)
        resp = client.post(
            '/api/validate/file',
            data={'file': (io.BytesIO(big_csv), 'big.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 500
        body = resp.get_json()
        assert 'error' in body
        assert '413' in body['error'] or 'Request Entity Too Large' in body['error']


# ---------------------------------------------------------------------------
# dataframe_from_request's remaining branches, exercised through the real
# endpoint that calls it: /api/security/hipaa-check.
# ---------------------------------------------------------------------------

class TestDataframeFromRequestBranches:
    def test_file_upload_empty_filename_raises_no_file_selected(self, client):
        resp = client.post(
            '/api/security/hipaa-check',
            data={'file': (io.BytesIO(b''), '')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'error': 'No file selected'}

    def test_file_upload_bad_extension_raises_file_type_not_allowed(self, client):
        resp = client.post(
            '/api/security/hipaa-check',
            data={'file': (io.BytesIO(b'x'), 'notes.txt')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['success'] is False
        assert 'File type not allowed' in body['error']

    def test_non_dict_json_payload_list_of_records(self, client):
        """A JSON list body (not a dict) takes the `else: df = pd.DataFrame(data)`
        branch (~1190-1191) rather than the dict-padding branch."""
        resp = client.post(
            '/api/security/hipaa-check',
            json=[{'ssn': '123-45-6789'}, {'ssn': 'no-phi-here'}],
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['total_phi_instances'] >= 1
        assert any(item['column'] == 'ssn' for item in body['phi_detected'])

    def test_dict_payload_with_scalar_value_gets_broadcast(self, client):
        """A dict payload whose value is a bare scalar (not a list) takes the
        `else: padded[key] = [value] * max_length` branch (~1187-1188),
        broadcasting the single value across every padded row."""
        resp = client.post(
            '/api/security/hipaa-check',
            json={'ssn': '123-45-6789', 'notes': ['a', 'b', 'c']},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        # The scalar 'ssn' value was broadcast to all 3 rows (matching the
        # 'notes' list length), so PHI detection still finds it.
        assert body['total_phi_instances'] >= 1
        match = next(item for item in body['phi_detected'] if item['column'] == 'ssn')
        assert match['instances'] == 3


# ---------------------------------------------------------------------------
# convert_numpy_types -- direct unit tests, no Flask involved.
# The dict/list/None/native-type branches are already exercised by other
# endpoint tests; only the four numpy-specific branches were uncovered.
# ---------------------------------------------------------------------------

class TestConvertNumpyTypes:
    def test_ndarray_converts_to_list(self):
        result = convert_numpy_types(np.array([1, 2, 3]))
        assert result == [1, 2, 3]
        assert isinstance(result, list)

    def test_numpy_integer_converts_to_python_int(self):
        result = convert_numpy_types(np.int64(42))
        assert result == 42
        assert type(result) is int

    def test_numpy_floating_converts_to_python_float(self):
        result = convert_numpy_types(np.float64(3.14))
        assert result == pytest.approx(3.14)
        assert type(result) is float

    def test_numpy_bool_converts_to_python_bool(self):
        result = convert_numpy_types(np.bool_(True))
        assert result is True
        assert type(result) is bool


# ---------------------------------------------------------------------------
# convert_validation_issue_to_dict -- direct unit tests, no Flask involved.
# ---------------------------------------------------------------------------

class TestConvertValidationIssueToDict:
    def test_normal_issue_converts_all_fields(self):
        issue = ValidationIssue(
            severity='error', message='Column missing', column='ssn', row=3,
            value='xyz', rule_name='SchemaValidator',
        )
        result = convert_validation_issue_to_dict(issue)
        assert result == {
            'severity': 'error',
            'description': 'Column missing',
            'column': 'ssn',
            'row': 3,
            'value': 'xyz',
            'rule_name': 'SchemaValidator',
        }

    def test_object_missing_attributes_uses_defaults(self):
        plain = object()
        result = convert_validation_issue_to_dict(plain)
        assert result['severity'] == 'unknown'
        assert result['description'] == str(plain)
        assert result['column'] is None
        assert result['row'] is None
        assert result['value'] is None
        assert result['rule_name'] is None

    def test_exception_during_conversion_returns_error_dict(self):
        class ExplodingIssue:
            @property
            def severity(self):
                raise RuntimeError('boom')

        result = convert_validation_issue_to_dict(ExplodingIssue())
        assert result['severity'] == 'error'
        assert result['description'] == 'Failed to convert issue: boom'
        assert result['column'] is None
        assert result['row'] is None
        assert result['value'] is None
        assert result['rule_name'] is None


# ---------------------------------------------------------------------------
# generate_compliance_report -- direct unit tests, no Flask involved.
# ---------------------------------------------------------------------------

def _result(issues=None, summary=None):
    r = ValidationResult(is_valid=True)
    for issue in issues or []:
        r.issues.append(issue)
    r.summary = summary or {}
    return r


class TestGenerateComplianceReportHipaa:
    def test_ssn_pattern_in_data_flags_hipaa(self):
        df = pd.DataFrame({'ssn': ['123-45-6789']})
        report = generate_compliance_report(df, _result(), ['hipaa'])
        assert report['hipaa']['compliant'] is False
        assert report['hipaa']['score'] == 50
        assert any('SSN detected in column: ssn' in msg for msg in report['hipaa']['issues'])

    def test_email_pattern_in_data_flags_hipaa(self):
        df = pd.DataFrame({'contact': ['alice@example.com']})
        report = generate_compliance_report(df, _result(), ['hipaa'])
        assert report['hipaa']['compliant'] is False
        assert any('Email detected in column: contact' in msg for msg in report['hipaa']['issues'])

    def test_phi_mentioned_in_issue_message_flags_hipaa(self):
        df = pd.DataFrame({'notes': ['nothing sensitive']})
        issue = ValidationIssue(severity='warning', message='Possible PHI found in notes field')
        report = generate_compliance_report(df, _result(issues=[issue]), ['hipaa'])
        assert report['hipaa']['compliant'] is False
        assert 'Possible PHI found in notes field' in report['hipaa']['issues']

    def test_clean_data_is_hipaa_compliant(self):
        df = pd.DataFrame({'age': [30, 45]})
        report = generate_compliance_report(df, _result(), ['hipaa'])
        assert report['hipaa'] == {'compliant': True, 'issues': [], 'score': 100}


class TestGenerateComplianceReportOtherStandards:
    def test_icd10_issues_reduce_score(self):
        df = pd.DataFrame({'diagnosis_code': ['E11.9']})
        issues = [
            ValidationIssue(severity='warning', message='Invalid icd10 code'),
            ValidationIssue(severity='warning', message='diagnosis field malformed'),
        ]
        report = generate_compliance_report(df, _result(issues=issues), ['icd10'])
        assert report['icd10']['compliant'] is False
        assert report['icd10']['score'] == 80
        assert len(report['icd10']['issues']) == 2

    def test_loinc_issues_matched_by_lab_keyword(self):
        df = pd.DataFrame({'a': [1]})
        issue = ValidationIssue(severity='warning', message='lab result code missing')
        report = generate_compliance_report(df, _result(issues=[issue]), ['loinc'])
        assert report['loinc']['compliant'] is False
        assert report['loinc']['score'] == 90

    def test_cpt_issues_matched_by_procedure_keyword(self):
        df = pd.DataFrame({'a': [1]})
        issue = ValidationIssue(severity='warning', message='procedure code invalid')
        report = generate_compliance_report(df, _result(issues=[issue]), ['cpt'])
        assert report['cpt']['compliant'] is False
        assert report['cpt']['score'] == 90

    def test_fhir_issues(self):
        df = pd.DataFrame({'a': [1]})
        issue = ValidationIssue(severity='warning', message='fhir resource malformed')
        report = generate_compliance_report(df, _result(issues=[issue]), ['fhir'])
        assert report['fhir']['compliant'] is False
        assert report['fhir']['score'] == 90

    def test_omop_issues(self):
        df = pd.DataFrame({'a': [1]})
        issue = ValidationIssue(severity='warning', message='omop mapping missing')
        report = generate_compliance_report(df, _result(issues=[issue]), ['omop'])
        assert report['omop']['compliant'] is False
        assert report['omop']['score'] == 90

    def test_unknown_standard_produces_no_entry(self):
        df = pd.DataFrame({'a': [1]})
        report = generate_compliance_report(df, _result(), ['totally_unknown_standard'])
        assert report == {}


class TestGenerateComplianceReportV12Flattening:
    """Covers the `if 'compliance_report' in result.summary:` branch
    (~184-238), which flattens a v1.2-shaped compliance_report into the
    legacy per-standard shape this function otherwise builds by hand."""

    def _df(self):
        return pd.DataFrame({'a': [1]})

    def test_violation_dict_with_message_key(self):
        summary = {'compliance_report': {'standards': {
            'hipaa': {'compliant': False, 'score': 60, 'risk_level': 'medium',
                      'violations': [{'message': 'SSN found', 'rule_id': 'X'}]},
        }}}
        report = generate_compliance_report(self._df(), _result(summary=summary), [])
        assert report['hipaa']['issues'] == ['SSN found']

    def test_violation_dict_with_description_key_no_message(self):
        summary = {'compliance_report': {'standards': {
            'gdpr': {'compliant': False, 'score': 70, 'risk_level': 'medium',
                     'violations': [{'description': 'missing consent field'}]},
        }}}
        report = generate_compliance_report(self._df(), _result(summary=summary), [])
        assert report['gdpr']['issues'] == ['missing consent field']

    def test_violation_dict_with_neither_message_nor_description(self):
        violation = {'rule_id': 'X', 'severity': 'high'}
        summary = {'compliance_report': {'standards': {
            'fda': {'compliant': False, 'score': 50, 'risk_level': 'high',
                    'violations': [violation]},
        }}}
        report = generate_compliance_report(self._df(), _result(summary=summary), [])
        assert report['fda']['issues'] == [str(violation)]

    def test_violation_as_plain_string(self):
        summary = {'compliance_report': {'standards': {
            'hipaa': {'compliant': False, 'score': 80, 'risk_level': 'low',
                      'violations': ['a raw string violation']},
        }}}
        report = generate_compliance_report(self._df(), _result(summary=summary), [])
        assert report['hipaa']['issues'] == ['a raw string violation']

    def test_violation_of_other_type_falls_back_to_str(self):
        summary = {'compliance_report': {'standards': {
            'hipaa': {'compliant': False, 'score': 80, 'risk_level': 'low',
                      'violations': [12345]},
        }}}
        report = generate_compliance_report(self._df(), _result(summary=summary), [])
        assert report['hipaa']['issues'] == ['12345']

    def test_empty_violations_falls_back_to_recommendations(self):
        summary = {'compliance_report': {'standards': {
            'hipaa': {'compliant': True, 'score': 100, 'risk_level': 'low',
                      'violations': [], 'recommendations': ['Consider periodic audits']},
        }}}
        report = generate_compliance_report(self._df(), _result(summary=summary), [])
        assert report['hipaa']['issues'] == ['Consider periodic audits']

    def test_empty_violations_and_no_recommendations_yields_no_issues(self):
        summary = {'compliance_report': {'standards': {
            'hipaa': {'compliant': True, 'score': 100, 'risk_level': 'low', 'violations': []},
        }}}
        report = generate_compliance_report(self._df(), _result(summary=summary), [])
        assert report['hipaa']['issues'] == []

    def test_overall_fields_are_flattened_to_top_level(self):
        summary = {'compliance_report': {
            'standards': {'hipaa': {'compliant': True, 'score': 100, 'risk_level': 'low', 'violations': []}},
            'overall_score': 87.5,
            'risk_level': 'medium',
            'all_violations': [{'message': 'x'}],
            'template_applied': 'clinical_trials',
        }}
        report = generate_compliance_report(self._df(), _result(summary=summary), [])
        assert report['overall_score'] == 87.5
        assert report['risk_level'] == 'medium'
        assert report['all_violations'] == [{'message': 'x'}]
        assert report['template_applied'] == 'clinical_trials'

    def test_compliance_report_without_standards_key_stored_verbatim(self):
        """Covers the `else` branch (~236-237): when the v1.2 report has no
        'standards' key, it's stashed under 'v1_2_compliance' unmodified."""
        v1_2_compliance = {'some_other_shape': True, 'score': 42}
        summary = {'compliance_report': v1_2_compliance}
        report = generate_compliance_report(self._df(), _result(summary=summary), [])
        assert report['v1_2_compliance'] == v1_2_compliance
