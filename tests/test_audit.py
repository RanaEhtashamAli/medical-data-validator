"""Tests for the immutable audit trail (Phase 3b)."""

import os
import tempfile
import pytest
import pandas as pd

import medical_data_validator.audit as audit
import medical_data_validator.auth as auth


@pytest.fixture(autouse=True)
def _isolated_audit_db():
    """Give each test its own fresh SQLite DB so validate() calls from other
    test modules cannot bleed into the audit log assertions."""
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()

    old_path = audit.AUDIT_DB_PATH
    audit.AUDIT_DB_PATH = tf.name
    if audit._conn is not None:
        audit._conn.close()
        audit._conn = None

    yield

    if audit._conn is not None:
        audit._conn.close()
        audit._conn = None
    audit.AUDIT_DB_PATH = old_path
    try:
        os.unlink(tf.name)
    except FileNotFoundError:
        pass


class TestLogEvent:
    def test_returns_uuid_string(self):
        rid = audit.log_event('validation')
        assert isinstance(rid, str) and len(rid) == 36

    def test_record_persists_in_db(self):
        rid = audit.log_event('validation', username='alice', tenant='acme')
        rows = audit.query_log()
        assert any(r['id'] == rid for r in rows)

    def test_all_fields_stored(self):
        rid = audit.log_event(
            'compliance_check',
            username='bob',
            tenant='hospital',
            dataset_id='ds-001',
            dataset_hash='abc123',
            rules_applied=['RuleA', 'RuleB'],
            result_summary={'is_valid': True},
            ip_address='10.0.0.1',
            extra={'note': 'test'},
        )
        rows = audit.query_log()
        row = next(r for r in rows if r['id'] == rid)
        assert row['event_type'] == 'compliance_check'
        assert row['username'] == 'bob'
        assert row['tenant'] == 'hospital'
        assert row['dataset_id'] == 'ds-001'
        assert row['dataset_hash'] == 'abc123'
        assert row['rules_applied'] == ['RuleA', 'RuleB']
        assert row['result_summary'] == {'is_valid': True}
        assert row['ip_address'] == '10.0.0.1'
        assert row['extra'] == {'note': 'test'}

    def test_multiple_events_all_persist(self):
        audit.log_event('validation', tenant='t1')
        audit.log_event('validation', tenant='t1')
        audit.log_event('validation', tenant='t2')
        assert audit.count_log() == 3


class TestQueryLog:
    def test_filter_by_tenant(self):
        audit.log_event('validation', tenant='acme')
        audit.log_event('validation', tenant='bigpharma')
        rows = audit.query_log(tenant='acme')
        assert len(rows) == 1 and rows[0]['tenant'] == 'acme'

    def test_filter_by_username(self):
        audit.log_event('validation', username='alice')
        audit.log_event('validation', username='bob')
        rows = audit.query_log(username='alice')
        assert len(rows) == 1 and rows[0]['username'] == 'alice'

    def test_filter_by_event_type(self):
        audit.log_event('validation')
        audit.log_event('anonymization')
        rows = audit.query_log(event_type='anonymization')
        assert len(rows) == 1 and rows[0]['event_type'] == 'anonymization'

    def test_filter_by_dataset_id(self):
        audit.log_event('validation', dataset_id='ds-42')
        audit.log_event('validation', dataset_id='ds-99')
        rows = audit.query_log(dataset_id='ds-42')
        assert len(rows) == 1

    def test_limit_and_offset(self):
        for _ in range(5):
            audit.log_event('validation')
        page1 = audit.query_log(limit=3, offset=0)
        page2 = audit.query_log(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 2
        all_ids = {r['id'] for r in page1} | {r['id'] for r in page2}
        assert len(all_ids) == 5

    def test_returns_newest_first(self):
        rid1 = audit.log_event('validation')
        rid2 = audit.log_event('validation')
        rows = audit.query_log()
        assert rows[0]['id'] == rid2
        assert rows[1]['id'] == rid1


class TestCountLog:
    def test_count_all(self):
        audit.log_event('validation')
        audit.log_event('validation')
        assert audit.count_log() == 2

    def test_count_filtered(self):
        audit.log_event('validation', tenant='x')
        audit.log_event('validation', tenant='y')
        assert audit.count_log(tenant='x') == 1


class TestHashDataframe:
    def test_same_df_same_hash(self):
        df = pd.DataFrame({'a': [1, 2, 3], 'b': ['x', 'y', 'z']})
        assert audit.hash_dataframe(df) == audit.hash_dataframe(df)

    def test_different_content_different_hash(self):
        df1 = pd.DataFrame({'a': [1, 2, 3]})
        df2 = pd.DataFrame({'a': [1, 2, 4]})
        assert audit.hash_dataframe(df1) != audit.hash_dataframe(df2)

    def test_returns_64_char_hex(self):
        df = pd.DataFrame({'col': [1]})
        h = audit.hash_dataframe(df)
        assert len(h) == 64 and all(c in '0123456789abcdef' for c in h)


class TestCoreIntegration:
    """Verify that MedicalDataValidator.validate() writes to the audit log."""

    def test_validate_creates_audit_record(self):
        from medical_data_validator.core import MedicalDataValidator
        validator = MedicalDataValidator(
            enable_compliance=False, enable_analytics=False, enable_monitoring=False
        )
        df = pd.DataFrame({'patient_id': [1, 2, 3], 'age': [25, 30, 45]})
        validator.validate(df)
        rows = audit.query_log(event_type='validation')
        assert len(rows) >= 1
        assert rows[0]['dataset_hash'] is not None


class TestGetAuditLogRoute:
    """Minimal REST-route regression tests for GET /api/audit
    (register_audit_routes' get_audit_log), which was previously untested
    at the HTTP layer. get_audit_log is decorated with
    `@role_required('data-steward', 'admin')`; before the role_required()
    fix (auth.py's min()-vs-max() bug), a data-steward -- despite being
    explicitly named as an allowed role -- was incorrectly rejected with
    403. Covers a lightweight happy-path check that a data-steward can now
    reach the endpoint, plus a negative/cross-tenant test proving the
    endpoint's non-admin tenant clamp (previously dead code, unreachable
    for the same reason) actually works now that it's reachable. Broader
    coverage of get_audit_log's filtering was not part of this effort's
    original scope."""

    def test_data_steward_can_get_audit_log(self):
        from medical_data_validator.dashboard.app import create_dashboard_app

        username = 'audit-route-steward'
        if username not in auth._USERS:
            auth.create_user_account(username, 'password123', role='data-steward', tenant='audit-route-tenant')
        try:
            app = create_dashboard_app()
            app.config['TESTING'] = True
            with app.test_client() as client:
                token_resp = client.post('/api/auth/token', json={
                    'username': username, 'password': 'password123',
                })
                assert token_resp.status_code == 200
                token = token_resp.get_json()['access_token']

                resp = client.get('/api/audit', headers={'Authorization': f'Bearer {token}'})
                assert resp.status_code == 200
                body = resp.get_json()
                assert 'total' in body
                assert 'records' in body
        finally:
            auth._USERS.pop(username, None)

    def test_data_steward_tenant_query_param_is_ignored_for_other_tenant(self):
        """Regression test for previously-dead code: get_audit_log's
        non-admin branch (`tenant_filter = args.get('tenant') if g.role ==
        'admin' else g.tenant`, audit.py:215) was unreachable before the
        role_required() fix -- only admin could ever pass the decorator,
        and admin's branch always takes the query-param path regardless.
        Now that a data-steward can reach this endpoint, this is the first
        test to exercise the non-admin branch: a data-steward from tenant A
        must not be able to use ?tenant=<tenant-B> to read tenant B's audit
        records -- the override must be genuinely discarded, not merely
        return 200."""
        from medical_data_validator.dashboard.app import create_dashboard_app

        audit.log_event('validation', tenant='audit-route-tenant-a')
        audit.log_event('validation', tenant='audit-route-tenant-b')
        audit.log_event('validation', tenant='audit-route-tenant-b')

        username = 'audit-route-steward-a'
        if username not in auth._USERS:
            auth.create_user_account(username, 'password123', role='data-steward', tenant='audit-route-tenant-a')
        try:
            app = create_dashboard_app()
            app.config['TESTING'] = True
            with app.test_client() as client:
                token_resp = client.post('/api/auth/token', json={
                    'username': username, 'password': 'password123',
                })
                assert token_resp.status_code == 200
                token = token_resp.get_json()['access_token']

                resp = client.get(
                    '/api/audit?tenant=audit-route-tenant-b',
                    headers={'Authorization': f'Bearer {token}'},
                )
                assert resp.status_code == 200
                body = resp.get_json()
                tenants_seen = {r['tenant'] for r in body['records']}
                assert 'audit-route-tenant-b' not in tenants_seen
                assert tenants_seen <= {'audit-route-tenant-a'}
        finally:
            auth._USERS.pop(username, None)
