"""Tests for the Dash Anonymize page's extracted callback logic."""

import base64

import pytest

# dashboard.pages.anonymize calls dash.register_page() at import time, which
# requires dash.Dash(use_pages=True) to have already run at least once in
# this process (it populates Dash's internal page-registry config). Building
# the dashboard app here — before importing the page module directly below —
# lets this test file pass in isolation, not just as part of the full suite.
# (Same pattern as tests/test_dash_security_page.py and
# tests/test_dash_custom_rules_page.py.)
from medical_data_validator.dashboard.app import create_dashboard_app
create_dashboard_app()


def _make_upload_contents(raw_bytes: bytes, mime: str = 'text/csv') -> str:
    """Build a dcc.Upload-style 'contents' string: 'data:<mime>;base64,<b64>'."""
    encoded = base64.b64encode(raw_bytes).decode()
    return f"data:{mime};base64,{encoded}"


NAME_CSV = b"patient_id,name,notes\n1,John Smith,fine\n2,Jane Doe,ok\n"


def test_run_anonymize_from_upload_auto_detects_phi_like_columns():
    from medical_data_validator.dashboard.pages.anonymize import _run_anonymize_from_upload
    contents = _make_upload_contents(NAME_CSV)

    success, message, records = _run_anonymize_from_upload(contents, 'patients.csv', 'mask', '')

    assert success is True
    assert 'Anonymized' in message
    assert records is not None
    # 'name' is auto-detected as PHI-like and anonymized; 'notes' is not.
    assert records[0]['name'] != 'John Smith'
    assert records[1]['name'] != 'Jane Doe'
    assert records[0]['notes'] == 'fine'
    assert records[1]['notes'] == 'ok'


def test_run_anonymize_from_upload_explicit_columns_hash_leaves_others_untouched():
    from medical_data_validator.dashboard.pages.anonymize import _run_anonymize_from_upload
    contents = _make_upload_contents(NAME_CSV)

    success, message, records = _run_anonymize_from_upload(contents, 'patients.csv', 'hash', 'name')

    assert success is True
    assert records is not None
    assert records[0]['name'] != 'John Smith'
    assert records[1]['name'] != 'Jane Doe'
    # patient_id was not listed, so it must be untouched.
    assert records[0]['patient_id'] == 1
    assert records[1]['patient_id'] == 2


def test_run_anonymize_from_upload_invalid_method_returns_error_tuple():
    from medical_data_validator.dashboard.pages.anonymize import _run_anonymize_from_upload
    contents = _make_upload_contents(NAME_CSV)

    success, message, records = _run_anonymize_from_upload(contents, 'patients.csv', 'not-a-method', 'name')

    assert success is False
    assert 'not-a-method' in message or 'Unknown method' in message
    assert records is None


def test_run_anonymize_from_upload_no_file_returns_error():
    from medical_data_validator.dashboard.pages.anonymize import _run_anonymize_from_upload
    success, message, records = _run_anonymize_from_upload(None, None, 'mask', '')
    assert success is False
    assert records is None


@pytest.mark.parametrize("columns_csv", ["   ", "  ,  ", "\t"])
def test_run_anonymize_from_upload_whitespace_only_columns_auto_detects(columns_csv):
    """A stray space (or comma-separated blanks) in the Columns field must
    behave exactly like an empty field — auto-detect PHI-like columns —
    not silently degrade to an empty column list that anonymizes nothing
    while still reporting success."""
    from medical_data_validator.dashboard.pages.anonymize import _run_anonymize_from_upload
    contents = _make_upload_contents(NAME_CSV)

    auto_success, auto_message, auto_records = _run_anonymize_from_upload(
        contents, 'patients.csv', 'mask', ''
    )
    whitespace_success, whitespace_message, whitespace_records = _run_anonymize_from_upload(
        contents, 'patients.csv', 'mask', columns_csv
    )

    assert whitespace_success is True
    assert whitespace_success == auto_success
    assert whitespace_records == auto_records
    # Explicitly confirm PHI actually got anonymized, not silently skipped.
    assert whitespace_records[0]['name'] != 'John Smith'
    assert whitespace_records[1]['name'] != 'Jane Doe'
