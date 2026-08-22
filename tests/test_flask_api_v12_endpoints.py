"""Characterization tests for v1.2/compliance/analytics/monitoring/custom-rules/
anonymize REST endpoints in medical_data_validator/dashboard/routes.py.

These endpoints (api_v1_2_compliance, api_templates, api_custom_rules,
api_add_custom_rule, api_remove_custom_rule, api_anonymize, api_analytics,
api_monitoring_stats, api_monitoring_alerts, api_acknowledge_alert,
api_resolve_alert, api_quality_trends, api_compliance_check) had zero test
coverage before this file. None of them are behind login_required/
role_required (verified by inspecting routes.py/docs.py directly), so a plain
Flask test client is used throughout.

Two endpoints touch process-wide mutable global state:
- `_custom_rules_storage` (routes.py) — shared with the Dash Custom Rules
  page and reset/restored per-test the same way tests/test_dash_custom_rules_page.py
  does.
- `monitor` (medical_data_validator.monitoring) — a module-level singleton
  that accumulates validation stats/alerts for the whole process. Tests for
  /api/monitoring/* create their own alerts directly on `monitor` for
  deterministic assertions, and save/restore its mutable state so they don't
  leak into other test files.
"""

import io
import json

import pytest

from medical_data_validator.dashboard.app import create_dashboard_app
from medical_data_validator.dashboard import routes as routes_module
from medical_data_validator.monitoring import monitor


@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def _clean_custom_rules():
    """Save/restore the global custom-rules list so tests don't leak state
    into each other or into the Dash Custom Rules page tests."""
    before = list(routes_module._custom_rules_storage)
    yield
    routes_module._custom_rules_storage.clear()
    routes_module._custom_rules_storage.extend(before)


@pytest.fixture
def clean_monitor():
    """Save/restore the global monitor's mutable state around a test that
    needs deterministic alerts/quality-history."""
    alerts_before = list(monitor.alerts)
    history_before = {k: list(v) for k, v in monitor.quality_history.items()}
    counter_before = monitor.alert_id_counter
    yield monitor
    monitor.alerts = alerts_before
    monitor.quality_history = history_before
    monitor.alert_id_counter = counter_before


PHI_CSV = b"ssn,email,name\n123-45-6789,alice@example.com,Alice Smith\n987-65-4321,bob@example.com,Bob Jones\n"


# ---------------------------------------------------------------------------
# api_v1_2_compliance -- POST /api/compliance/v1.2 (multipart file upload)
# ---------------------------------------------------------------------------

class TestApiV12Compliance:
    def test_happy_path_with_phi_csv(self, client):
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (io.BytesIO(PHI_CSV), 'test.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        report = body['compliance_report']
        for key in ('hipaa', 'gdpr', 'fda', 'medical_coding', 'overall_score', 'risk_level', 'all_violations'):
            assert key in report
        # PHI in the CSV should produce at least one HIPAA/GDPR violation.
        assert report['overall_score'] < 100

    def test_happy_path_with_template(self, client):
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (io.BytesIO(PHI_CSV), 'test.csv'), 'template': 'clinical_trials'},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_applies_custom_rules_from_global_storage(self, client):
        routes_module._custom_rules_storage.append({
            'name': 'no-fax', 'pattern': r'\bfax\b', 'severity': 'medium',
            'field_pattern': None, 'description': '', 'recommendation': None,
        })
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (io.BytesIO(PHI_CSV), 'test.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_no_file_provided_400(self, client):
        resp = client.post('/api/compliance/v1.2', data={}, content_type='multipart/form-data')
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'error': 'No file provided'}

    def test_empty_filename_400(self, client):
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (io.BytesIO(b''), '')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'error': 'No file selected'}

    def test_unsupported_extension_400(self, client):
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (io.BytesIO(b'a,b\n1,2\n'), 'test.txt')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'error': 'Unsupported file format'}

    def test_corrupt_xlsx_returns_500(self, client):
        """Cheap way to force the 'Failed to read file' 500 branch: claim an
        .xlsx extension but send bytes that aren't a real Excel file."""
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (io.BytesIO(b'not an excel file'), 'test.xlsx')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 500
        body = resp.get_json()
        assert body['success'] is False
        assert 'Failed to read file' in body['error']

    def test_empty_dataframe_returns_placeholder_report(self, client):
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (io.BytesIO(b'col1,col2\n'), 'empty.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert 'Empty Dataset' in body['message']
        report = body['compliance_report']
        assert report['overall_score'] == 100
        assert report['hipaa'] == {'score': 100, 'risk_level': 'low', 'violations': [], 'violations_count': 0}


# ---------------------------------------------------------------------------
# api_templates -- GET /api/compliance/templates
# ---------------------------------------------------------------------------

class TestApiTemplates:
    def test_returns_list_of_name_description_dicts(self, client):
        resp = client.get('/api/compliance/templates')
        assert resp.status_code == 200
        body = resp.get_json()
        assert isinstance(body, list)
        assert len(body) > 0
        names = {t['name'] for t in body}
        assert 'clinical_trials' in names
        for t in body:
            assert set(t.keys()) == {'name', 'description'}


# ---------------------------------------------------------------------------
# api_custom_rules (GET), api_add_custom_rule (POST), api_remove_custom_rule (DELETE)
# -- /api/compliance/custom-rules[/<rule_name>]
# ---------------------------------------------------------------------------

class TestCustomRulesCrud:
    def test_get_custom_rules_initially_reflects_storage(self, client):
        routes_module._custom_rules_storage.clear()
        resp = client.get('/api/compliance/custom-rules')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_add_rule_then_list_contains_it(self, client):
        resp = client.post('/api/compliance/custom-rules', json={
            'name': 'no-fax', 'pattern': r'\bfax\b', 'severity': 'high',
            'field_pattern': 'notes', 'description': 'no fax numbers', 'recommendation': 'remove it',
        })
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'message': 'Custom rule added successfully'}

        resp = client.get('/api/compliance/custom-rules')
        rules = resp.get_json()
        assert len(rules) == 1
        assert rules[0]['name'] == 'no-fax'
        assert rules[0]['pattern'] == r'\bfax\b'
        assert rules[0]['severity'] == 'high'
        assert rules[0]['field_pattern'] == 'notes'

    def test_add_rule_defaults_optional_fields(self, client):
        resp = client.post('/api/compliance/custom-rules', json={'name': 'bare-rule', 'pattern': 'x'})
        assert resp.status_code == 200
        rules = client.get('/api/compliance/custom-rules').get_json()
        rule = next(r for r in rules if r['name'] == 'bare-rule')
        assert rule['severity'] == 'medium'
        assert rule['field_pattern'] is None
        assert rule['description'] == ''
        assert rule['recommendation'] is None

    def test_add_rule_with_same_name_updates_in_place(self, client):
        client.post('/api/compliance/custom-rules', json={'name': 'dup', 'pattern': 'first'})
        resp = client.post('/api/compliance/custom-rules', json={'name': 'dup', 'pattern': 'second'})
        assert resp.status_code == 200
        assert resp.get_json()['message'] == 'Custom rule updated successfully'

        rules = client.get('/api/compliance/custom-rules').get_json()
        matching = [r for r in rules if r['name'] == 'dup']
        assert len(matching) == 1
        assert matching[0]['pattern'] == 'second'

    def test_add_rule_missing_name_400(self, client):
        resp = client.post('/api/compliance/custom-rules', json={'pattern': 'x'})
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'error': 'Missing required field: name'}

    def test_add_rule_missing_pattern_400(self, client):
        resp = client.post('/api/compliance/custom-rules', json={'name': 'x'})
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'error': 'Missing required field: pattern'}

    def test_add_rule_empty_json_body_400(self, client):
        resp = client.post('/api/compliance/custom-rules', json={})
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'error': 'No data provided'}

    def test_add_rule_no_body_no_content_type_returns_500(self, client):
        """Discovered quirk: api_add_custom_rule calls request.get_json()
        without silent=True. A POST with no JSON content-type makes Flask
        raise a 415 UnsupportedMediaType internally; the endpoint's blanket
        except Exception catches it and reports it as a generic 500 rather
        than the clean 400 'No data provided' path used for an empty {}
        body. Documented here as real, observed behavior (not asserting it
        as *desired* behavior)."""
        resp = client.post('/api/compliance/custom-rules')
        assert resp.status_code == 500
        body = resp.get_json()
        assert body['success'] is False
        assert 'error' in body

    def test_remove_existing_rule_200(self, client):
        client.post('/api/compliance/custom-rules', json={'name': 'to-remove', 'pattern': 'x'})
        resp = client.delete('/api/compliance/custom-rules/to-remove')
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'message': 'Rule "to-remove" removed successfully'}
        rules = client.get('/api/compliance/custom-rules').get_json()
        assert all(r['name'] != 'to-remove' for r in rules)

    def test_remove_missing_rule_404(self, client):
        resp = client.delete('/api/compliance/custom-rules/does-not-exist')
        assert resp.status_code == 404
        assert resp.get_json() == {'success': False, 'error': 'Rule "does-not-exist" not found'}


# ---------------------------------------------------------------------------
# api_anonymize -- POST /api/anonymize
# ---------------------------------------------------------------------------

class TestApiAnonymize:
    def test_json_payload_with_explicit_columns(self, client):
        resp = client.post('/api/anonymize', json={
            'data': {'ssn': ['123-45-6789'], 'name': ['Alice']},
            'columns': 'ssn',
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['method'] == 'hipaa_safe_harbor'
        assert body['columns_anonymized'] == ['ssn']
        assert body['rows'] == 1
        assert body['data'][0]['ssn'] != '123-45-6789'
        # Only the requested column was touched.
        assert body['data'][0]['name'] == 'Alice'

    def test_json_payload_columns_as_list(self, client):
        resp = client.post('/api/anonymize', json={
            'data': {'ssn': ['123-45-6789']},
            'columns': ['ssn'],
        })
        assert resp.status_code == 200
        assert resp.get_json()['columns_anonymized'] == ['ssn']

    def test_bare_dict_payload_without_data_wrapper(self, client):
        resp = client.post('/api/anonymize', json={'ssn': ['123-45-6789']}, query_string={'method': 'hash'})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['method'] == 'hash'

    def test_no_columns_auto_detects_but_response_underreports_them(self, client):
        """Discovered bug: when the caller omits `columns`, the endpoint lets
        MedicalDataValidator.anonymize() auto-detect PHI columns internally
        (columns=None), and it DOES anonymize them -- but the JSON response's
        'columns_anonymized' field is computed as `columns or []`, which is
        the caller-supplied `columns` variable, still None/absent at that
        point. So the response always reports columns_anonymized=[] on the
        auto-detect path even though PHI columns were in fact anonymized."""
        resp = client.post('/api/anonymize', json={'ssn': ['123-45-6789'], 'name': ['Alice Smith']})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['columns_anonymized'] == []
        # Yet the data was actually anonymized (auto-detected 'ssn' and 'name').
        assert body['data'][0]['ssn'] != '123-45-6789'
        assert body['data'][0]['name'] != 'Alice Smith'

    def test_file_upload_csv(self, client):
        resp = client.post(
            '/api/anonymize',
            data={'file': (io.BytesIO(b'ssn,name\n123-45-6789,Alice\n'), 'test.csv'), 'columns': 'ssn'},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['columns_anonymized'] == ['ssn']
        assert body['data'][0]['name'] == 'Alice'

    def test_file_upload_xlsx(self, client):
        import pandas as pd
        buf = io.BytesIO()
        pd.DataFrame({'ssn': ['123-45-6789'], 'name': ['Alice']}).to_excel(buf, index=False)
        buf.seek(0)
        resp = client.post(
            '/api/anonymize',
            data={'file': (buf, 'test.xlsx'), 'columns': 'ssn'},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['columns_anonymized'] == ['ssn']

    def test_file_upload_empty_filename_400(self, client):
        resp = client.post(
            '/api/anonymize',
            data={'file': (io.BytesIO(b''), '')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'error': 'No file selected'}

    def test_file_upload_unsupported_format_400(self, client):
        resp = client.post(
            '/api/anonymize',
            data={'file': (io.BytesIO(b'x'), 'test.txt')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'error': 'Unsupported file format'}

    def test_unknown_method_400(self, client):
        resp = client.post('/api/anonymize?method=bogus', json={'ssn': ['1']})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['success'] is False
        assert 'bogus' in body['error']

    def test_no_data_provided_400(self, client):
        resp = client.post('/api/anonymize')
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'error': 'No data provided'}


# ---------------------------------------------------------------------------
# api_analytics -- POST /api/analytics
# ---------------------------------------------------------------------------

class TestApiAnalytics:
    def test_happy_path_csv(self, client):
        csv_bytes = b"age,visit_date\n30,2024-01-01\n45,2024-02-01\n50,2024-03-01\n"
        resp = client.post(
            '/api/analytics',
            data={'file': (io.BytesIO(csv_bytes), 'test.csv'), 'time_column': 'visit_date'},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        for key in ('quality_metrics', 'anomalies', 'trends', 'statistical_summary', 'overall_quality_score'):
            assert key in body
        assert isinstance(body['quality_metrics'], dict)
        assert 'completeness' in body['quality_metrics']

    def test_happy_path_without_time_column(self, client):
        csv_bytes = b"age,weight\n30,70\n45,80\n"
        resp = client.post(
            '/api/analytics',
            data={'file': (io.BytesIO(csv_bytes), 'test.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True

    def test_no_file_400(self, client):
        resp = client.post('/api/analytics', data={}, content_type='multipart/form-data')
        assert resp.status_code == 400
        assert resp.get_json() == {"success": False, "error": "No file provided"}

    def test_empty_filename_400(self, client):
        resp = client.post(
            '/api/analytics',
            data={'file': (io.BytesIO(b''), '')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert resp.get_json() == {"success": False, "error": "No file selected"}

    def test_unsupported_format_400(self, client):
        resp = client.post(
            '/api/analytics',
            data={'file': (io.BytesIO(b'x'), 'test.txt')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        assert resp.get_json() == {"success": False, "error": "Unsupported file format"}

    def test_corrupt_file_returns_500(self, client):
        resp = client.post(
            '/api/analytics',
            data={'file': (io.BytesIO(b'not an excel file'), 'test.xlsx')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 500
        body = resp.get_json()
        assert body['success'] is False
        assert 'Failed to read file' in body['error']


# ---------------------------------------------------------------------------
# api_monitoring_stats -- GET /api/monitoring/stats
# ---------------------------------------------------------------------------

class TestApiMonitoringStats:
    def test_returns_expected_shape(self, client):
        resp = client.get('/api/monitoring/stats')
        assert resp.status_code == 200
        body = resp.get_json()
        for key in ('total_validations', 'successful_validations', 'failed_validations',
                    'success_rate', 'average_processing_time', 'active_alerts',
                    'last_validation_time', 'monitoring_active'):
            assert key in body
        assert isinstance(body['total_validations'], int)
        assert isinstance(body['monitoring_active'], bool)

    def test_reflects_a_recorded_validation(self, client, clean_monitor):
        before = monitor.get_monitoring_stats()['total_validations']
        monitor.record_validation_result({'is_valid': True, 'summary': {}}, 0.01)
        resp = client.get('/api/monitoring/stats')
        assert resp.status_code == 200
        assert resp.get_json()['total_validations'] == before + 1


# ---------------------------------------------------------------------------
# api_monitoring_alerts -- GET /api/monitoring/alerts
# ---------------------------------------------------------------------------

class TestApiMonitoringAlerts:
    def test_returns_list_shape(self, client):
        resp = client.get('/api/monitoring/alerts')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_includes_a_freshly_created_unresolved_alert(self, client, clean_monitor):
        monitor._create_alert(
            alert_type='test_alert_type',
            severity='medium',
            message='characterization test alert',
            details={'foo': 'bar'},
        )
        new_id = monitor.alerts[-1].id
        resp = client.get('/api/monitoring/alerts')
        assert resp.status_code == 200
        alerts = resp.get_json()
        match = next(a for a in alerts if a['id'] == new_id)
        assert match['alert_type'] == 'test_alert_type'
        assert match['severity'] == 'medium'
        assert match['message'] == 'characterization test alert'
        assert match['details'] == {'foo': 'bar'}
        assert match['acknowledged'] is False

    def test_resolved_alerts_are_excluded(self, client, clean_monitor):
        monitor._create_alert('test_alert_type2', 'low', 'will resolve', {})
        resolved_id = monitor.alerts[-1].id
        monitor.resolve_alert(resolved_id)
        resp = client.get('/api/monitoring/alerts')
        ids = {a['id'] for a in resp.get_json()}
        assert resolved_id not in ids


# ---------------------------------------------------------------------------
# api_acknowledge_alert -- POST /api/monitoring/alerts/<alert_id>/acknowledge
# ---------------------------------------------------------------------------

class TestApiMonitoringAcknowledge:
    def test_acknowledge_existing_alert(self, client, clean_monitor):
        monitor._create_alert('ack_test', 'low', 'ack me', {})
        alert_id = monitor.alerts[-1].id
        resp = client.post(f'/api/monitoring/alerts/{alert_id}/acknowledge')
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'message': f'Alert {alert_id} acknowledged'}
        assert next(a for a in monitor.alerts if a.id == alert_id).acknowledged is True

    def test_acknowledge_missing_alert_404(self, client):
        resp = client.post('/api/monitoring/alerts/does-not-exist/acknowledge')
        assert resp.status_code == 404
        assert resp.get_json() == {'success': False, 'error': 'Alert does-not-exist not found'}


# ---------------------------------------------------------------------------
# api_resolve_alert -- POST /api/monitoring/alerts/<alert_id>/resolve
# ---------------------------------------------------------------------------

class TestApiMonitoringResolve:
    def test_resolve_existing_alert(self, client, clean_monitor):
        monitor._create_alert('resolve_test', 'low', 'resolve me', {})
        alert_id = monitor.alerts[-1].id
        resp = client.post(f'/api/monitoring/alerts/{alert_id}/resolve')
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'message': f'Alert {alert_id} acknowledged'}
        assert next(a for a in monitor.alerts if a.id == alert_id).resolved is True
        # Resolved alerts must disappear from the active-alerts endpoint.
        active_ids = {a['id'] for a in client.get('/api/monitoring/alerts').get_json()}
        assert alert_id not in active_ids

    def test_resolve_missing_alert_404(self, client):
        resp = client.post('/api/monitoring/alerts/does-not-exist/resolve')
        assert resp.status_code == 404
        assert resp.get_json() == {'success': False, 'error': 'Alert does-not-exist not found'}


# ---------------------------------------------------------------------------
# api_quality_trends -- GET /api/monitoring/trends/<metric_name>
# ---------------------------------------------------------------------------

class TestApiQualityTrends:
    def test_returns_recorded_metric_history(self, client, clean_monitor):
        monitor._record_quality_metric('completeness', 0.9)
        monitor._record_quality_metric('completeness', 0.85)
        resp = client.get('/api/monitoring/trends/completeness')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert len(body['trends']) >= 2
        for point in body['trends']:
            assert set(point.keys()) == {'timestamp', 'value', 'status'}

    def test_unknown_metric_returns_empty_list(self, client):
        resp = client.get('/api/monitoring/trends/totally_unknown_metric_xyz')
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'trends': []}

    def test_hours_query_param_is_accepted(self, client, clean_monitor):
        monitor._record_quality_metric('completeness', 0.9)
        resp = client.get('/api/monitoring/trends/completeness?hours=1')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True


# ---------------------------------------------------------------------------
# api_compliance_check -- POST /api/compliance/check
# (registered exclusively via the flask-restx legacy namespace in docs.py;
# /api/compliance/check is not present in create_api_blueprint(). The 3
# straightforward JSON-body happy-path cases are already covered by
# tests/test_flask_api_compliance.py -- this class adds the file-upload
# contract and the error branches, which had no coverage at all.)
# ---------------------------------------------------------------------------

class TestApiComplianceCheck:
    def test_csv_file_upload_happy_path(self, client):
        resp = client.post(
            '/api/compliance/check',
            data={'file': (io.BytesIO(PHI_CSV), 'test.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        body = resp.get_json()
        for key in ('hipaa_compliant', 'icd10_compliant', 'loinc_compliant',
                    'cpt_compliant', 'fhir_compliant', 'omop_compliant', 'details'):
            assert key in body
        assert body['fhir_compliant'] is True
        assert body['omop_compliant'] is True

    def test_file_upload_empty_filename_400(self, client):
        resp = client.post(
            '/api/compliance/check',
            data={'file': (io.BytesIO(b''), '')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False

    def test_file_upload_unsupported_format_400(self, client):
        resp = client.post(
            '/api/compliance/check',
            data={'file': (io.BytesIO(b'x'), 'test.txt')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False

    def test_malformed_json_body_returns_500(self, client):
        """Discovered quirk (same shape as api_add_custom_rule's): the JSON
        branch does `data = request.get_json()` without silent=True, and
        checks `if data is None` for the "Invalid JSON data" 400 response.
        In practice Werkzeug's get_json() never returns None on a decode
        failure -- it raises BadRequest -- so that 400 branch is dead code,
        and a malformed JSON body actually falls through to the generic
        except-Exception handler and comes back as a 500."""
        resp = client.post(
            '/api/compliance/check',
            data='not json',
            content_type='application/json',
        )
        assert resp.status_code == 500
        body = resp.get_json()
        assert body.get('success') is False

    def test_corrupt_xlsx_returns_500(self, client):
        resp = client.post(
            '/api/compliance/check',
            data={'file': (io.BytesIO(b'not an excel file'), 'test.xlsx')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 500
        body = resp.get_json()
        assert body.get('success') is False
