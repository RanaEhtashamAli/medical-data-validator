"""Tests for the async job queue (Phase 3g)."""

import os
import tempfile
import time
import pytest
import pandas as pd

import medical_data_validator.jobs as jobs


@pytest.fixture(autouse=True)
def _isolated_jobs_db():
    """Give each test its own fresh SQLite DB and a clean worker state."""
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()

    old_path = jobs.JOBS_DB_PATH
    jobs.JOBS_DB_PATH = tf.name
    if jobs._conn is not None:
        jobs._conn.close()
        jobs._conn = None
    # Reset worker flag so each test gets a fresh worker thread
    jobs._worker_started = False

    yield

    if jobs._conn is not None:
        jobs._conn.close()
        jobs._conn = None
    jobs.JOBS_DB_PATH = old_path
    try:
        os.unlink(tf.name)
    except FileNotFoundError:
        pass


def _wait_for_job(job_id: str, timeout: float = 5.0) -> dict:
    """Poll until a job leaves 'pending'/'running' or the timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = jobs.get_job(job_id)
        if job and job['status'] not in ('pending', 'running'):
            return job
        time.sleep(0.05)
    return jobs.get_job(job_id)


class TestCreateJob:
    def test_returns_uuid(self):
        jid = jobs.create_job('validate', {'data': {}})
        assert isinstance(jid, str) and len(jid) == 36

    def test_initial_status_pending(self):
        jid = jobs.create_job('validate', {'data': {}})
        job = jobs.get_job(jid)
        assert job['status'] == 'pending'

    def test_fields_stored(self):
        jid = jobs.create_job('validate', {'x': 1}, tenant='acme', username='alice')
        job = jobs.get_job(jid)
        assert job['tenant'] == 'acme'
        assert job['username'] == 'alice'
        assert job['payload'] == {'x': 1}


class TestGetJob:
    def test_returns_none_for_unknown_id(self):
        assert jobs.get_job('no-such-id') is None

    def test_returns_job_dict(self):
        jid = jobs.create_job('anonymize', {})
        job = jobs.get_job(jid)
        assert job['id'] == jid
        assert job['job_type'] == 'anonymize'


class TestListJobs:
    def test_lists_all(self):
        jobs.create_job('validate', {})
        jobs.create_job('validate', {})
        assert len(jobs.list_jobs()) == 2

    def test_filter_by_tenant(self):
        jobs.create_job('validate', {}, tenant='x')
        jobs.create_job('validate', {}, tenant='y')
        assert len(jobs.list_jobs(tenant='x')) == 1

    def test_filter_by_status(self):
        jobs.create_job('validate', {})  # pending
        assert len(jobs.list_jobs(status='pending')) == 1
        assert len(jobs.list_jobs(status='completed')) == 0

    def test_limit_offset(self):
        for _ in range(5):
            jobs.create_job('validate', {})
        assert len(jobs.list_jobs(limit=3)) == 3
        assert len(jobs.list_jobs(limit=3, offset=3)) == 2


class TestSubmitJob:
    def test_submit_validate_completes(self):
        data = {'patient_id': [1, 2, 3], 'age': [25, 30, 45]}
        jid = jobs.submit_job('validate', {'data': data, 'enable_compliance': False})
        job = _wait_for_job(jid)
        assert job['status'] == 'completed'
        assert isinstance(job['result'], dict)
        assert 'is_valid' in job['result']

    def test_submit_anonymize_completes(self):
        data = {'patient_name': ['Alice', 'Bob'], 'age': [30, 45]}
        jid = jobs.submit_job('anonymize', {
            'data': data,
            'columns': ['patient_name'],
            'method': 'hash',
        })
        job = _wait_for_job(jid)
        assert job['status'] == 'completed'
        assert 'data' in job['result']

    def test_failed_job_captures_error(self):
        jid = jobs.submit_job('validate', {'data': 'not-a-dict'})
        job = _wait_for_job(jid)
        assert job['status'] == 'failed'
        assert job['error'] is not None

    def test_unknown_job_type_fails(self):
        jid = jobs.create_job('unknown_type', {})
        jobs._ensure_worker()
        jobs._job_queue.put((jid, 'unknown_type', {}))
        job = _wait_for_job(jid)
        assert job['status'] == 'failed'

    def test_completed_job_has_timestamps(self):
        jid = jobs.submit_job('validate', {'data': {'x': [1]}, 'enable_compliance': False})
        job = _wait_for_job(jid)
        assert job['started_at'] is not None
        assert job['finished_at'] is not None
