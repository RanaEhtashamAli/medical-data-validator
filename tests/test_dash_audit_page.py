"""Tests for the Dash Audit page's extracted callback logic."""

import tempfile
import pytest
import medical_data_validator.audit as audit

# dashboard.pages.audit calls dash.register_page() at import time, which
# requires dash.Dash(use_pages=True) to have already run at least once in
# this process (it populates Dash's internal page-registry config). Building
# the dashboard app here — before importing the page module directly below —
# lets this test file pass in isolation, not just as part of the full suite.
# (Same pattern as tests/test_dash_registry_page.py and test_dash_jobs_page.py.)
from medical_data_validator.dashboard.app import create_dashboard_app
create_dashboard_app()


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


def test_list_audit_log_table_data_reflects_logged_event():
    from medical_data_validator.dashboard.pages.audit import _list_audit_log_table_data
    audit.log_event(
        'validate',
        username='alice',
        tenant='default',
        dataset_id='ds-1',
    )
    rows = _list_audit_log_table_data()
    assert len(rows) == 1
    assert rows[0]['username'] == 'alice'
    assert rows[0]['event_type'] == 'validate'
    assert rows[0]['dataset_id'] == 'ds-1'
    assert rows[0]['timestamp'] != ''


def test_list_audit_log_table_data_filters_by_tenant():
    from medical_data_validator.dashboard.pages.audit import _list_audit_log_table_data
    audit.log_event('validate', username='alice', tenant='default')
    audit.log_event('validate', username='bob', tenant='other-tenant')
    rows = _list_audit_log_table_data(tenant='default')
    assert len(rows) == 1
    assert rows[0]['username'] == 'alice'


def test_list_audit_log_table_data_respects_limit():
    from medical_data_validator.dashboard.pages.audit import _list_audit_log_table_data
    for i in range(5):
        audit.log_event('validate', username=f'user-{i}', tenant='default')
    rows = _list_audit_log_table_data(limit=2)
    assert len(rows) == 2


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


def test_handle_audit_refresh_shows_true_total_not_capped_list_length():
    from medical_data_validator.dashboard.pages.audit import _handle_audit_refresh
    for i in range(105):
        audit.log_event('validate', username=f'user-{i}', tenant='default')
    rows, message = _handle_audit_refresh(1)
    assert len(rows) == 100  # _list_audit_log_table_data's default limit
    assert message == "Showing 100 of 105 records"
