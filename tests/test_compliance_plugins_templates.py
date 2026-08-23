"""Tests for Task 1: compliance plugin discovery + custom compliance templates
(medical_data_validator/dashboard/routes.py).

Covers:
- GET /api/compliance/plugins -- discovery via the
  'medical_data_validator.compliance_plugins' entry-point group.
- Custom compliance TEMPLATE CRUD (GET/POST/DELETE /api/compliance/custom-templates),
  distinct from the read-only, built-in-only GET /api/compliance/templates.
- build_v1_2_compliance_report()'s new template=/use_plugins= wiring inside
  POST /api/compliance/v1.2, including the flattening bug fix that used to
  silently drop plugin standards from the response.

No new SQLite fixture is needed here: the session-scoped, autouse
`_isolated_custom_rules_db` fixture in tests/conftest.py already swaps
CUSTOM_RULES_DB_PATH to a fresh temp file and resets
routes_module._custom_rules_conn to None *before any test in the whole
session runs* (session-scoped autouse fixtures are set up before the first
test item executes). Every function under test here
(_get_custom_rules_conn/_list_custom_templates/_get_custom_template/
_upsert_custom_template/_delete_custom_template) only ever opens the
connection lazily, inside a function body -- there is no module-level call
that could run before the fixture swaps the path. The new `custom_templates`
table lives in that exact same connection/file as `custom_rules`.
"""

import io

import pytest

from medical_data_validator.dashboard.app import create_dashboard_app


@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def _use_clean_custom_templates(_clean_custom_templates):
    """Activates conftest.py's shared (non-autouse) `_clean_custom_templates`
    fixture as autouse for every test in this file, so tests here don't leak
    state into each other or into test_dash_compliance_page.py, which shares
    the same session-wide SQLite-backed store (see _isolated_custom_rules_db)."""
    yield


# ---------------------------------------------------------------------------
# api_compliance_plugins -- GET /api/compliance/plugins
# ---------------------------------------------------------------------------

class TestApiCompliancePlugins:
    def test_lists_the_two_builtin_plugins(self, client):
        resp = client.get('/api/compliance/plugins')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert body['count'] == 2
        assert len(body['plugins']) == 2

        by_name = {p['name']: p for p in body['plugins']}
        assert set(by_name) == {'fhir_r4', 'snomed_ct'}

        for name, cls_name in (('fhir_r4', 'FHIRCompliancePlugin'), ('snomed_ct', 'SNOMEDCompliancePlugin')):
            entry = by_name[name]
            assert entry['class_name'] == cls_name
            assert entry['module'] == 'medical_data_validator.plugins'
            assert isinstance(entry['description'], str) and entry['description']


# ---------------------------------------------------------------------------
# Custom compliance TEMPLATE CRUD -- /api/compliance/custom-templates
# ---------------------------------------------------------------------------

class TestApiCustomTemplatesCrud:
    def test_create_then_list_then_delete_then_404_on_redelete(self, client):
        resp = client.post('/api/compliance/custom-templates', json={
            'name': 'crud_template',
            'description': 'a crud test template',
            'rules': [{
                'name': 'r1', 'pattern': 'x', 'severity': 'medium',
                'field_pattern': None, 'description': '', 'recommendation': None,
            }],
        })
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'message': "Custom template 'crud_template' saved"}

        listed = client.get('/api/compliance/custom-templates').get_json()
        entry = next((t for t in listed if t['name'] == 'crud_template'), None)
        assert entry is not None
        assert entry['description'] == 'a crud test template'
        assert entry['rules'] == [{
            'name': 'r1', 'pattern': 'x', 'severity': 'medium',
            'field_pattern': None, 'description': '', 'recommendation': None,
        }]

        resp = client.delete('/api/compliance/custom-templates/crud_template')
        assert resp.status_code == 200
        assert resp.get_json() == {'success': True, 'message': 'Template "crud_template" removed successfully'}

        listed = client.get('/api/compliance/custom-templates').get_json()
        assert all(t['name'] != 'crud_template' for t in listed)

        resp = client.delete('/api/compliance/custom-templates/crud_template')
        assert resp.status_code == 404
        assert resp.get_json() == {'success': False, 'error': 'Template "crud_template" not found'}

    def test_upsert_by_name_replaces_rules(self, client):
        client.post('/api/compliance/custom-templates', json={
            'name': 'dup_template', 'description': 'first',
            'rules': [{'name': 'a', 'pattern': 'first-pattern'}],
        })
        resp = client.post('/api/compliance/custom-templates', json={
            'name': 'dup_template', 'description': 'second',
            'rules': [{'name': 'b', 'pattern': 'second-pattern'}],
        })
        assert resp.status_code == 200

        listed = client.get('/api/compliance/custom-templates').get_json()
        matching = [t for t in listed if t['name'] == 'dup_template']
        assert len(matching) == 1
        assert matching[0]['description'] == 'second'
        assert matching[0]['rules'][0]['name'] == 'b'

    def test_defaults_for_optional_rule_fields(self, client):
        client.post('/api/compliance/custom-templates', json={
            'name': 'defaults_template',
            'rules': [{'name': 'bare-rule', 'pattern': 'x'}],
        })
        listed = client.get('/api/compliance/custom-templates').get_json()
        entry = next(t for t in listed if t['name'] == 'defaults_template')
        rule = entry['rules'][0]
        assert rule['severity'] == 'medium'
        assert rule['field_pattern'] is None
        assert rule['description'] == ''
        assert rule['recommendation'] is None

    def test_missing_name_400(self, client):
        resp = client.post('/api/compliance/custom-templates', json={
            'rules': [{'name': 'a', 'pattern': 'b'}],
        })
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['success'] is False
        assert 'error' in body

    def test_missing_rules_400(self, client):
        resp = client.post('/api/compliance/custom-templates', json={'name': 'no_rules_template'})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['success'] is False

    def test_empty_rules_list_400(self, client):
        resp = client.post('/api/compliance/custom-templates', json={'name': 'empty_rules_template', 'rules': []})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_rule_missing_pattern_400(self, client):
        resp = client.post('/api/compliance/custom-templates', json={
            'name': 'bad_rule_template', 'rules': [{'name': 'only_name'}],
        })
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_rule_missing_name_400(self, client):
        resp = client.post('/api/compliance/custom-templates', json={
            'name': 'bad_rule_template2', 'rules': [{'pattern': 'only_pattern'}],
        })
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_empty_json_body_400(self, client):
        resp = client.post('/api/compliance/custom-templates', json={})
        assert resp.status_code == 400
        assert resp.get_json() == {'success': False, 'error': 'No data provided'}


# ---------------------------------------------------------------------------
# build_v1_2_compliance_report via POST /api/compliance/v1.2 -- custom template
# is opt-in (only applied when template=<name> is passed)
# ---------------------------------------------------------------------------

class TestCustomTemplateAppliedOptInViaV12Compliance:
    TEMPLATE_NAME = 'foobar_opt_in_template'
    RULE_ID = 'foobar_rule'

    @pytest.fixture(autouse=True)
    def _create_template(self, client):
        resp = client.post('/api/compliance/custom-templates', json={
            'name': self.TEMPLATE_NAME,
            'description': 'opt-in test template',
            'rules': [{
                'name': self.RULE_ID,
                'pattern': 'FOOBAR',
                'severity': 'high',
                'field_pattern': 'notes',
                'description': 'flags the literal FOOBAR marker',
                'recommendation': 'remove FOOBAR',
            }],
        })
        assert resp.status_code == 200

    @staticmethod
    def _csv():
        return io.BytesIO(b"notes\nthis row has FOOBAR in it\nthis row does not\n")

    def _rule_ids(self, report):
        return {v['rule_id'] for v in report['all_violations']}

    def test_with_template_param_produces_the_custom_violation(self, client):
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (self._csv(), 'test.csv'), 'template': self.TEMPLATE_NAME},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert self.RULE_ID in self._rule_ids(body['compliance_report'])

    def test_without_template_param_does_not_produce_the_violation(self, client):
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (self._csv(), 'test.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        assert self.RULE_ID not in self._rule_ids(body['compliance_report'])

    def test_unknown_template_name_returns_400(self, client):
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (self._csv(), 'test.csv'), 'template': 'this_template_does_not_exist'},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body['success'] is False
        assert 'error' in body


# ---------------------------------------------------------------------------
# build_v1_2_compliance_report via POST /api/compliance/v1.2 -- use_plugins=
# ---------------------------------------------------------------------------

class TestUsePluginsViaV12Compliance:
    @staticmethod
    def _csv():
        return io.BytesIO(b"col1,col2\na,1\nb,2\n")

    def test_use_plugins_true_lists_both_builtin_plugins(self, client):
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (self._csv(), 'test.csv'), 'use_plugins': 'true'},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        report = resp.get_json()['compliance_report']
        assert set(report['plugins_applied']) == {'fhir_r4', 'snomed_ct'}

    def test_use_plugins_absent_is_empty_list(self, client):
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (self._csv(), 'test.csv')},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        report = resp.get_json()['compliance_report']
        assert report['plugins_applied'] == []

    def test_use_plugins_false_is_empty_list(self, client):
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (self._csv(), 'test.csv'), 'use_plugins': 'false'},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        report = resp.get_json()['compliance_report']
        assert report['plugins_applied'] == []


# ---------------------------------------------------------------------------
# Regression guard: an existing built-in template=... request must keep
# returning the same shape it did before this task.
# ---------------------------------------------------------------------------

class TestBuiltinTemplateRegression:
    def test_ehr_template_shape_is_unchanged(self, client):
        csv = io.BytesIO(b"patient_id,notes\nP12345678,hello\n")
        resp = client.post(
            '/api/compliance/v1.2',
            data={'file': (csv, 'test.csv'), 'template': 'ehr'},
            content_type='multipart/form-data',
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        report = body['compliance_report']

        for key in ('hipaa', 'gdpr', 'fda', 'medical_coding', 'overall_score',
                    'risk_level', 'all_violations', 'template_applied', 'plugins_applied'):
            assert key in report

        assert report['template_applied'] == 'ehr'
        assert report['plugins_applied'] == []
        assert isinstance(report['hipaa'], dict) and 'score' in report['hipaa']
        assert isinstance(report['gdpr'], dict) and 'score' in report['gdpr']
        assert isinstance(report['fda'], dict) and 'score' in report['fda']
        assert isinstance(report['medical_coding'], dict) and 'icd10' in report['medical_coding']
