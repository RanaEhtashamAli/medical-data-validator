"""Tests for the Dash Security page's extracted callback logic."""

# dashboard.pages.security calls dash.register_page() at import time, which
# requires dash.Dash(use_pages=True) to have already run at least once in
# this process (it populates Dash's internal page-registry config). Building
# the dashboard app here — before importing the page module directly below —
# lets this test file pass in isolation, not just as part of the full suite.
# (Same pattern as tests/test_dash_custom_rules_page.py and
# tests/test_dash_registry_page.py.)
from medical_data_validator.dashboard.app import create_dashboard_app
create_dashboard_app()

from tests.conftest import _make_upload_contents, _set_triggered

SSN_CSV = b"patient_id,ssn\n1,123-45-6789\n2,987-65-4321\n"
SCRIPT_CSV = b"notes\n<script>alert(1)</script>hello\n"


def test_run_hipaa_check_from_upload_detects_ssn():
    from medical_data_validator.dashboard.pages.security import _run_hipaa_check_from_upload
    contents = _make_upload_contents(SSN_CSV)
    report = _run_hipaa_check_from_upload(contents, 'patients.csv', False)
    assert 'error' not in report
    assert report['compliant'] is False
    assert report['total_phi_instances'] >= 1
    assert any(item['column'] == 'ssn' for item in report['phi_detected'])
    # samples stripped down to a count since include_samples=False
    for item in report['phi_detected']:
        assert 'sample_values' not in item
        assert 'sample_count' in item


def test_run_hipaa_check_from_upload_include_samples_keeps_values():
    from medical_data_validator.dashboard.pages.security import _run_hipaa_check_from_upload
    contents = _make_upload_contents(SSN_CSV)
    report = _run_hipaa_check_from_upload(contents, 'patients.csv', True)
    assert any('sample_values' in item for item in report['phi_detected'])


def test_run_hipaa_check_from_upload_no_file_returns_error():
    from medical_data_validator.dashboard.pages.security import _run_hipaa_check_from_upload
    report = _run_hipaa_check_from_upload(None, None, False)
    assert 'error' in report


def test_run_security_audit_from_upload_returns_security_score():
    from medical_data_validator.dashboard.pages.security import _run_security_audit_from_upload
    contents = _make_upload_contents(SSN_CSV)
    result = _run_security_audit_from_upload(contents, 'patients.csv')
    assert 'error' not in result
    assert 'security_score' in result
    assert result['overall_status'] in ('SECURE', 'NEEDS_ATTENTION')


def test_run_sanitize_from_upload_strips_script_tag():
    from medical_data_validator.dashboard.pages.security import _run_sanitize_from_upload
    contents = _make_upload_contents(SCRIPT_CSV)
    records = _run_sanitize_from_upload(contents, 'notes.csv')
    assert isinstance(records, list)
    assert records[0]['notes'] == 'hello'


# --- dispatcher routing test -------------------------------------------
# Confirms clicking the HIPAA button routes to the HIPAA branch only, with
# no cross-talk into the audit or sanitize branches (same "proves the right
# branch fired" standard every existing page's dispatcher tests already
# meet, e.g. test_dash_custom_rules_page.py).

def _flatten_text(component):
    """Recursively collect string content (including dash_table 'data' rows)
    from a Dash component tree, so tests can assert on rendered output
    without depending on its exact structure."""
    texts = []

    def _walk(node):
        if isinstance(node, str):
            texts.append(node)
        elif isinstance(node, (list, tuple)):
            for child in node:
                _walk(child)
        else:
            data = getattr(node, 'data', None)
            if data is not None:
                texts.append(str(data))
            children = getattr(node, 'children', None)
            if children is not None:
                _walk(children)

    _walk(component)
    return ' '.join(texts)


def test_handle_security_actions_hipaa_routes_correctly_and_does_not_audit_or_sanitize():
    from medical_data_validator.dashboard.pages.security import _handle_security_actions
    contents = _make_upload_contents(SSN_CSV)

    _set_triggered('security-hipaa-btn')
    children, store_data = _handle_security_actions(1, None, None, contents, 'patients.csv', False)

    text = _flatten_text(children)
    assert 'Compliance score' in text
    # Proves the audit branch never ran (its summary text is distinct).
    assert 'Security score' not in text
    # Proves the sanitize branch never ran (its summary text is distinct).
    assert 'Sanitized' not in text
    # I4: the HIPAA branch must clear the sanitize-download store (not leave
    # it as dash.no_update), so a prior sanitize run's data can never be
    # served by the download button after a HIPAA check on a different file.
    assert store_data is None


def test_handle_security_actions_audit_routes_correctly_and_does_not_hipaa_or_sanitize():
    from medical_data_validator.dashboard.pages.security import _handle_security_actions
    contents = _make_upload_contents(SSN_CSV)

    _set_triggered('security-audit-btn')
    children, store_data = _handle_security_actions(None, 1, None, contents, 'patients.csv', False)

    text = _flatten_text(children)
    assert 'Security score' in text
    assert 'Compliance score' not in text
    assert 'Sanitized' not in text
    # I4: same rationale as the HIPAA branch above.
    assert store_data is None


def test_handle_security_actions_sanitize_routes_correctly_and_does_not_hipaa_or_audit():
    from medical_data_validator.dashboard.pages.security import _handle_security_actions
    contents = _make_upload_contents(SCRIPT_CSV)

    _set_triggered('security-sanitize-btn')
    children, store_data = _handle_security_actions(None, None, 1, contents, 'notes.csv', False)

    text = _flatten_text(children)
    assert 'Sanitized' in text
    assert 'Compliance score' not in text
    assert 'Security score' not in text
    assert store_data[0]['notes'] == 'hello'


def test_sanitize_then_hipaa_check_clears_the_sanitize_download_store():
    """I4 regression: a user who sanitizes file A, then runs a HIPAA check on
    file B, must not be left with a 'Download sanitized CSV' button that
    still serves file A's data."""
    from medical_data_validator.dashboard.pages.security import _handle_security_actions

    _set_triggered('security-sanitize-btn')
    _children, store_data = _handle_security_actions(
        None, None, 1, _make_upload_contents(SCRIPT_CSV), 'notes.csv', False)
    assert store_data[0]['notes'] == 'hello'

    _set_triggered('security-hipaa-btn')
    _children, store_data = _handle_security_actions(
        1, None, None, _make_upload_contents(SSN_CSV), 'patients.csv', False)
    assert store_data is None
