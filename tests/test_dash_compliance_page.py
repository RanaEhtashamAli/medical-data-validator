"""Tests for the Dash Compliance page's extracted callback logic.

Covers the three independent concerns of dashboard/pages/compliance.py:
report runner (build_v1_2_compliance_report wiring), custom template CRUD
(_upsert_custom_template/_delete_custom_template/_list_custom_templates
wiring), and read-only plugin listing (discover_plugins wiring).
"""

import json

import pytest

# dashboard.pages.compliance calls dash.register_page() at import time, which
# requires dash.Dash(use_pages=True) to have already run at least once in
# this process (it populates Dash's internal page-registry config). Building
# the dashboard app here -- before importing the page module directly below --
# lets this test file pass in isolation, not just as part of the full suite.
# (Same pattern as tests/test_dash_custom_rules_page.py, test_dash_jobs_page.py,
# and test_dash_security_page.py.)
from medical_data_validator.dashboard.app import create_dashboard_app
create_dashboard_app()

from tests.conftest import _make_upload_contents, _set_triggered


@pytest.fixture(autouse=True)
def _use_clean_custom_templates(_clean_custom_templates):
    """Activates conftest.py's shared (non-autouse) `_clean_custom_templates`
    fixture as autouse for every test in this file, so tests here don't leak
    state into each other or into test_compliance_plugins_templates.py, which
    shares the same session-wide SQLite-backed store (see conftest.py's
    _isolated_custom_rules_db)."""
    yield


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


PLAIN_CSV = b"patient_id,notes\nP1,hello\nP2,world\n"
FOOBAR_CSV = b"notes\nthis row has FOOBAR in it\nthis row does not\n"


# ---------------------------------------------------------------------------
# 1. Report runner
# ---------------------------------------------------------------------------

def test_run_compliance_report_from_upload_no_template_no_plugins_has_4_standard_keys():
    from medical_data_validator.dashboard.pages.compliance import _run_compliance_report_from_upload
    contents = _make_upload_contents(PLAIN_CSV)
    report = _run_compliance_report_from_upload(contents, 'patients.csv', None, False)
    assert 'error' not in report
    for key in ('hipaa', 'gdpr', 'fda', 'medical_coding'):
        assert key in report
    assert report['plugins_applied'] == []


def test_run_compliance_report_from_upload_use_plugins_true_lists_both_builtins():
    from medical_data_validator.dashboard.pages.compliance import _run_compliance_report_from_upload
    contents = _make_upload_contents(PLAIN_CSV)
    report = _run_compliance_report_from_upload(contents, 'patients.csv', None, True)
    assert 'error' not in report
    assert set(report['plugins_applied']) == {'fhir_r4', 'snomed_ct'}


def test_run_compliance_report_from_upload_unknown_template_returns_error_not_raise():
    from medical_data_validator.dashboard.pages.compliance import _run_compliance_report_from_upload
    contents = _make_upload_contents(PLAIN_CSV)
    report = _run_compliance_report_from_upload(contents, 'patients.csv', 'this_template_does_not_exist', False)
    assert 'error' in report


def test_run_compliance_report_from_upload_no_file_returns_error():
    from medical_data_validator.dashboard.pages.compliance import _run_compliance_report_from_upload
    report = _run_compliance_report_from_upload(None, None, None, False)
    assert 'error' in report


def test_render_compliance_report_shows_alert_on_error():
    from medical_data_validator.dashboard.pages.compliance import _render_compliance_report
    import dash_bootstrap_components as dbc
    rendered = _render_compliance_report({'error': 'boom'})
    assert isinstance(rendered, dbc.Alert)


def test_render_compliance_report_renders_a_block_per_standard_including_plugins():
    from medical_data_validator.dashboard.pages.compliance import (
        _run_compliance_report_from_upload, _render_compliance_report,
    )
    contents = _make_upload_contents(PLAIN_CSV)
    report = _run_compliance_report_from_upload(contents, 'patients.csv', None, True)
    text = _flatten_text(_render_compliance_report(report))
    for key in ('hipaa', 'gdpr', 'fda', 'medical_coding', 'fhir_r4', 'snomed_ct'):
        assert key in text


# ---------------------------------------------------------------------------
# 2. Custom template CRUD
# ---------------------------------------------------------------------------

def test_save_then_list_then_apply_in_report_then_delete_then_gone():
    from medical_data_validator.dashboard.pages.compliance import (
        _save_custom_template_from_form, _list_templates_table_data,
        _delete_custom_template_from_form, _run_compliance_report_from_upload,
    )
    rules_json = json.dumps([{
        'name': 'foobar_rule', 'pattern': 'FOOBAR', 'severity': 'high', 'field_pattern': 'notes',
    }])
    ok, message = _save_custom_template_from_form('dash_crud_template', 'a crud template', rules_json)
    assert ok is True
    assert "'dash_crud_template'" in message

    rows = _list_templates_table_data()
    entry = next((r for r in rows if r['name'] == 'dash_crud_template'), None)
    assert entry is not None
    assert entry['description'] == 'a crud template'
    assert entry['rule_count'] == 1

    contents = _make_upload_contents(FOOBAR_CSV)
    report = _run_compliance_report_from_upload(contents, 'test.csv', 'dash_crud_template', False)
    assert 'error' not in report
    assert any(v['rule_id'] == 'foobar_rule' for v in report['all_violations'])

    ok, message = _delete_custom_template_from_form('dash_crud_template')
    assert ok is True
    rows = _list_templates_table_data()
    assert not any(r['name'] == 'dash_crud_template' for r in rows)


def test_save_custom_template_requires_name():
    from medical_data_validator.dashboard.pages.compliance import _save_custom_template_from_form
    ok, message = _save_custom_template_from_form('', 'desc', '[{"name":"a","pattern":"b"}]')
    assert ok is False


def test_save_custom_template_defaults_optional_rule_fields():
    from medical_data_validator.dashboard.pages.compliance import _save_custom_template_from_form
    from medical_data_validator.dashboard.routes import _list_custom_templates
    ok, message = _save_custom_template_from_form(
        'defaults_dash_template', None, '[{"name":"bare","pattern":"x"}]')
    assert ok is True
    entry = next(t for t in _list_custom_templates() if t['name'] == 'defaults_dash_template')
    rule = entry['rules'][0]
    assert rule['severity'] == 'medium'
    assert rule['field_pattern'] is None
    assert rule['description'] == ''
    assert rule['recommendation'] is None


def test_save_custom_template_invalid_json_reports_clear_error_and_no_partial_row():
    from medical_data_validator.dashboard.pages.compliance import (
        _save_custom_template_from_form, _list_templates_table_data,
    )
    ok, message = _save_custom_template_from_form('bad_json_template', 'desc', 'not json')
    assert ok is False
    assert 'invalid json' in message.lower()
    rows = _list_templates_table_data()
    assert not any(r['name'] == 'bad_json_template' for r in rows)


def test_save_custom_template_rejects_empty_rules_list():
    from medical_data_validator.dashboard.pages.compliance import _save_custom_template_from_form
    ok, message = _save_custom_template_from_form('empty_rules_template', 'desc', '[]')
    assert ok is False


def test_save_custom_template_rejects_rule_missing_pattern():
    from medical_data_validator.dashboard.pages.compliance import _save_custom_template_from_form
    ok, message = _save_custom_template_from_form('bad_rule_template', 'desc', '[{"name":"only_name"}]')
    assert ok is False


def test_delete_custom_template_not_found():
    from medical_data_validator.dashboard.pages.compliance import _delete_custom_template_from_form
    ok, message = _delete_custom_template_from_form('nonexistent_template')
    assert ok is False
    assert 'not found' in message.lower()


def test_delete_custom_template_requires_name():
    from medical_data_validator.dashboard.pages.compliance import _delete_custom_template_from_form
    ok, message = _delete_custom_template_from_form('')
    assert ok is False


# --- dispatcher routing tests -------------------------------------------
# Confirms save/delete/refresh route to their own logic with no cross-talk
# (same standard as custom_rules.py's own dispatcher tests).

def test_handle_template_actions_save_routes_correctly_and_does_not_delete():
    from medical_data_validator.dashboard.pages.compliance import (
        _handle_template_actions, _save_custom_template_from_form,
    )
    _save_custom_template_from_form('pre_existing_dash_template', 'desc', '[{"name":"a","pattern":"b"}]')

    _set_triggered('compliance-tmpl-save-btn')
    rows, message, options = _handle_template_actions(
        1, None, None, 'dispatch_save_template', 'desc', '[{"name":"x","pattern":"y"}]', None)

    assert 'saved' in message.lower()
    assert any(r['name'] == 'dispatch_save_template' for r in rows)
    # The pre-existing template must still be present -- proves the delete
    # branch (which would use `delete_name`, here None) never ran.
    assert any(r['name'] == 'pre_existing_dash_template' for r in rows)


def test_handle_template_actions_delete_routes_correctly_and_does_not_save():
    from medical_data_validator.dashboard.pages.compliance import (
        _handle_template_actions, _save_custom_template_from_form,
    )
    _save_custom_template_from_form('dispatch_delete_template', 'desc', '[{"name":"a","pattern":"b"}]')

    _set_triggered('compliance-tmpl-delete-btn')
    rows, message, options = _handle_template_actions(
        None, 1, None, 'should-not-be-saved', 'desc', '[{"name":"z","pattern":"q"}]', 'dispatch_delete_template')

    assert 'deleted' in message.lower()
    assert not any(r['name'] == 'dispatch_delete_template' for r in rows)
    # Proves the save branch (which would use name/description/rules_json)
    # never ran.
    assert not any(r['name'] == 'should-not-be-saved' for r in rows)


def test_handle_template_actions_refresh_neither_saves_nor_deletes():
    from medical_data_validator.dashboard.pages.compliance import (
        _handle_template_actions, _save_custom_template_from_form,
    )
    _save_custom_template_from_form('refresh_visible_template', 'desc', '[{"name":"a","pattern":"b"}]')

    _set_triggered('compliance-tmpl-refresh-btn')
    rows, message, options = _handle_template_actions(
        None, None, 1, 'should-not-be-saved-either', 'desc', '[{"name":"z","pattern":"q"}]',
        'refresh_visible_template')

    assert message == ""
    assert any(r['name'] == 'refresh_visible_template' for r in rows)
    assert not any(r['name'] == 'should-not-be-saved-either' for r in rows)


def test_template_dropdown_options_include_builtins_and_custom():
    from medical_data_validator.dashboard.pages.compliance import (
        _template_dropdown_options, _save_custom_template_from_form,
    )
    _save_custom_template_from_form('dropdown_visible_template', 'desc', '[{"name":"a","pattern":"b"}]')
    options = _template_dropdown_options()
    values = {o['value'] for o in options}
    assert {'clinical_trials', 'ehr', 'laboratory', 'imaging', 'research'}.issubset(values)
    assert 'dropdown_visible_template' in values


# ---------------------------------------------------------------------------
# Report-runner callback: initial page load vs. an actual click
# ---------------------------------------------------------------------------

def test_handle_compliance_report_actions_no_click_yet_renders_nothing_but_populates_dropdown():
    from medical_data_validator.dashboard.pages.compliance import _handle_compliance_report_actions
    children, options = _handle_compliance_report_actions(None, None, None, None, False)
    assert len(options) >= 5


def test_handle_compliance_report_actions_click_runs_report():
    from medical_data_validator.dashboard.pages.compliance import _handle_compliance_report_actions
    contents = _make_upload_contents(PLAIN_CSV)
    children, options = _handle_compliance_report_actions(1, contents, 'patients.csv', None, False)
    text = _flatten_text(children).lower()
    assert 'hipaa' in text


# ---------------------------------------------------------------------------
# 3. Plugin listing (read-only)
# ---------------------------------------------------------------------------

def test_list_plugins_table_data_lists_builtin_plugins():
    from medical_data_validator.dashboard.pages.compliance import _list_plugins_table_data
    rows = _list_plugins_table_data()
    names = {r['name'] for r in rows}
    assert names == {'fhir_r4', 'snomed_ct'}
    for row in rows:
        assert row['module'] == 'medical_data_validator.plugins'
        assert row['class_name']


def test_handle_plugins_refresh_returns_table_data():
    from medical_data_validator.dashboard.pages.compliance import _handle_plugins_refresh
    rows = _handle_plugins_refresh(1)
    assert {r['name'] for r in rows} == {'fhir_r4', 'snomed_ct'}
