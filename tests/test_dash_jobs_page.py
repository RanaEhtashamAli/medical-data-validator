"""Tests for the Dash Jobs page's extracted callback logic."""

import tempfile
import time
import pytest
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
