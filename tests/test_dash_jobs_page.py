"""Tests for the Dash Jobs page's extracted callback logic."""

import tempfile
import time
import pytest
import dash
from dash._callback_context import context_value
from dash._utils import AttributeDict
import medical_data_validator.jobs as jobs

# dashboard.pages.jobs calls dash.register_page() at import time, which
# requires dash.Dash(use_pages=True) to have already run at least once in
# this process (it populates Dash's internal page-registry config). Building
# the dashboard app here — before importing the page module directly below —
# lets this test file pass in isolation, not just as part of the full suite.
# (Same pattern as tests/test_dash_layout.py and test_dash_registry_page.py.)
from medical_data_validator.dashboard.app import create_dashboard_app
create_dashboard_app()


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


def test_get_job_detail_rejects_other_tenant_job():
    from medical_data_validator.dashboard.pages.jobs import _get_job_detail
    from medical_data_validator.jobs import submit_job

    other_tenant_job_id = submit_job('validate', {"age": [200]}, tenant='other-tenant', username='someone-else')
    for _ in range(20):
        job = jobs.get_job(other_tenant_job_id)
        if job and job['status'] in ('completed', 'failed'):
            break
        time.sleep(0.1)

    ok, message, job = _get_job_detail(other_tenant_job_id)
    assert ok is False
    assert job is None
    assert 'not found' in message.lower()


def _set_triggered(component_id):
    """Make dash.ctx.triggered_id resolve to component_id inside a directly-called callback."""
    context_value.set(AttributeDict(triggered_inputs=[{'prop_id': f'{component_id}.n_clicks'}]))


# --- Fix 2: directly test the `_handle_jobs_actions` dispatcher ------------
# Confirms submit routes to submit_message (not detail_message) and view
# routes to detail_message + the store (not submit_message) — this is what
# would catch a cross-wired routing bug between the two branches.

def test_handle_jobs_actions_submit_routes_to_submit_message_only():
    # Uses an invalid job_type so `_submit_job_from_form` takes its
    # validation-failure branch (submit_message gets set, submit_job() is
    # never called) — this proves the submit trigger routes into
    # submit_message without starting a real background job thread, which
    # would otherwise race the per-test DB-swap fixture teardown.
    from medical_data_validator.dashboard.pages.jobs import _handle_jobs_actions

    _set_triggered('jobs-submit-btn')
    _table, submit_message, detail_message, detail_job = _handle_jobs_actions(
        1, None, None, 'not-a-real-type', '{}', None)

    assert submit_message != ""
    assert 'job_type' in submit_message.lower()
    assert detail_message == ""
    assert detail_job is dash.no_update


def test_handle_jobs_actions_view_routes_to_detail_message_and_store_only():
    # Uses jobs.create_job() directly (synchronous, no worker thread involved)
    # rather than submitting a real async job, to avoid racing the background
    # job-worker thread against this test's DB-swap fixture teardown.
    from medical_data_validator.dashboard.pages.jobs import _handle_jobs_actions
    from medical_data_validator.jobs import create_job

    job_id = create_job('validate', {'data': {}}, tenant='default', username='dash-ui')

    _set_triggered('jobs-view-btn')
    _table, submit_message, detail_message, detail_job = _handle_jobs_actions(
        None, None, 1, None, None, job_id)

    assert submit_message == ""
    assert detail_message != ""
    assert detail_job is not None
    assert detail_job['id'] == job_id


# --- Fix 2: directly test the `_download_job_report` dispatcher -----------
# Confirms the 4-part gate blocks non-downloadable jobs, and that the two
# download buttons route to the correct report generator (pdf vs csv) — a
# swapped routing would flip which filename extension / base64 encoding
# comes back for a given button.

def test_download_job_report_returns_no_update_when_job_missing():
    from medical_data_validator.dashboard.pages.jobs import _download_job_report

    _set_triggered('jobs-download-pdf-btn')
    assert _download_job_report(1, None, None) is dash.no_update


def test_download_job_report_returns_no_update_when_job_type_not_validate():
    from medical_data_validator.dashboard.pages.jobs import _download_job_report

    job = {'id': 'j1', 'job_type': 'anonymize', 'status': 'completed', 'result': {'is_valid': True}}
    _set_triggered('jobs-download-pdf-btn')
    assert _download_job_report(1, None, job) is dash.no_update


def test_download_job_report_returns_no_update_when_not_completed():
    from medical_data_validator.dashboard.pages.jobs import _download_job_report

    job = {'id': 'j1', 'job_type': 'validate', 'status': 'running', 'result': None}
    _set_triggered('jobs-download-pdf-btn')
    assert _download_job_report(1, None, job) is dash.no_update


def test_download_job_report_returns_no_update_when_result_missing():
    from medical_data_validator.dashboard.pages.jobs import _download_job_report

    job = {'id': 'j1', 'job_type': 'validate', 'status': 'completed', 'result': None}
    _set_triggered('jobs-download-pdf-btn')
    assert _download_job_report(1, None, job) is dash.no_update


def _completed_validate_job():
    return {
        'id': 'j1', 'job_type': 'validate', 'status': 'completed',
        'result': {'is_valid': True, 'total_issues': 0, 'issues': [], 'summary': {}},
    }


def test_download_job_report_pdf_button_routes_to_pdf_not_csv():
    from medical_data_validator.dashboard.pages.jobs import _download_job_report

    job = _completed_validate_job()
    _set_triggered('jobs-download-pdf-btn')
    result = _download_job_report(1, None, job)

    assert result['filename'] == 'job_j1_report.pdf'
    assert result['base64'] is True


def test_download_job_report_csv_button_routes_to_csv_not_pdf():
    from medical_data_validator.dashboard.pages.jobs import _download_job_report

    job = _completed_validate_job()
    _set_triggered('jobs-download-csv-btn')
    result = _download_job_report(None, 1, job)

    assert result['filename'] == 'job_j1_report.csv'
    assert result['base64'] is False
