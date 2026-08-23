"""Tests for the Dash Custom Rules page's extracted callback logic."""

import pytest
from medical_data_validator.dashboard import routes as routes_module

# dashboard.pages.custom_rules calls dash.register_page() at import time,
# which requires dash.Dash(use_pages=True) to have already run at least once
# in this process (it populates Dash's internal page-registry config).
# Building the dashboard app here — before importing the page module
# directly below — lets this test file pass in isolation, not just as part
# of the full suite. (Same pattern as tests/test_dash_jobs_page.py and
# tests/test_dash_registry_page.py.)
from medical_data_validator.dashboard.app import create_dashboard_app
create_dashboard_app()

from tests.conftest import _set_triggered


@pytest.fixture(autouse=True)
def _clean_custom_rules():
    before = list(routes_module._custom_rules_storage)
    yield
    routes_module._custom_rules_storage.clear()
    routes_module._custom_rules_storage.extend(before)


def test_list_custom_rules_table_data_empty_initially():
    from medical_data_validator.dashboard.pages.custom_rules import _list_custom_rules_table_data
    assert _list_custom_rules_table_data() == []


def test_add_custom_rule_from_form_then_appears_in_list():
    from medical_data_validator.dashboard.pages.custom_rules import _add_custom_rule_from_form, _list_custom_rules_table_data
    ok, message = _add_custom_rule_from_form('no-fax', r'\bfax\b', 'medium')
    assert ok is True
    rows = _list_custom_rules_table_data()
    assert any(r['name'] == 'no-fax' for r in rows)


def test_add_custom_rule_from_form_requires_name_and_pattern():
    from medical_data_validator.dashboard.pages.custom_rules import _add_custom_rule_from_form
    ok, message = _add_custom_rule_from_form('', '', 'medium')
    assert ok is False


def test_remove_custom_rule_from_form_removes_it():
    from medical_data_validator.dashboard.pages.custom_rules import _add_custom_rule_from_form, _remove_custom_rule_from_form, _list_custom_rules_table_data
    _add_custom_rule_from_form('remove-me', r'\bfax\b', 'medium')
    ok, message = _remove_custom_rule_from_form('remove-me')
    assert ok is True
    rows = _list_custom_rules_table_data()
    assert not any(r['name'] == 'remove-me' for r in rows)


def test_remove_custom_rule_from_form_not_found():
    from medical_data_validator.dashboard.pages.custom_rules import _remove_custom_rule_from_form
    ok, message = _remove_custom_rule_from_form('nonexistent-rule')
    assert ok is False
    assert 'not found' in message.lower()


def test_remove_custom_rule_from_form_requires_name():
    from medical_data_validator.dashboard.pages.custom_rules import _remove_custom_rule_from_form
    ok, message = _remove_custom_rule_from_form('')
    assert ok is False


# --- Fix 2: directly test the `_handle_rules_actions` dispatcher -----------
# Confirms add and remove route to their own logic with no cross-talk (e.g.
# clicking Add doesn't also run the remove branch or vice versa).

def test_handle_rules_actions_add_routes_correctly_and_does_not_remove():
    from medical_data_validator.dashboard.pages.custom_rules import (
        _handle_rules_actions, _add_custom_rule_from_form,
    )
    _add_custom_rule_from_form('pre-existing-rule', r'\bexisting\b', 'low')

    _set_triggered('rules-add-btn')
    rows, message = _handle_rules_actions(1, None, None, 'dispatch-add-rule', r'\badd\b', 'high')

    assert 'added' in message.lower()
    assert any(r['name'] == 'dispatch-add-rule' for r in rows)
    # The pre-existing rule must still be present — proves the remove branch
    # (which would have deleted a rule by this same `name` field) never ran.
    assert any(r['name'] == 'pre-existing-rule' for r in rows)


def test_handle_rules_actions_remove_routes_correctly_and_does_not_add():
    from medical_data_validator.dashboard.pages.custom_rules import (
        _handle_rules_actions, _add_custom_rule_from_form,
    )
    _add_custom_rule_from_form('dispatch-remove-rule', r'\bremove\b', 'medium')

    _set_triggered('rules-remove-btn')
    rows, message = _handle_rules_actions(
        None, 1, None, 'dispatch-remove-rule', r'\bshould-not-be-added\b', 'critical')

    assert 'removed' in message.lower()
    assert not any(r['name'] == 'dispatch-remove-rule' for r in rows)
    # Proves the add branch (which would use the pattern/severity args) never
    # ran — no rule was (re-)created from the same form fields.
    assert not any(r['pattern'] == r'\bshould-not-be-added\b' for r in rows)


def test_rule_added_before_a_connection_reset_is_still_visible_after():
    """Regression coverage for the bug this SQLite migration fixes: a plain
    in-memory list was invisible across Gunicorn's separate worker
    processes, so a rule added on one worker didn't exist as far as
    another was concerned. Each worker only ever opens its own
    sqlite3.Connection once (routes._get_custom_rules_conn() caches it in
    `routes._custom_rules_conn`), so dropping and recreating that
    connection mid-test stands in for "a different worker process reads
    the same file"."""
    from medical_data_validator.dashboard.pages.custom_rules import _add_custom_rule_from_form, _list_custom_rules_table_data

    _add_custom_rule_from_form('persist-check-rule', r'\bpersist\b', 'high')

    routes_module._custom_rules_conn.close()
    routes_module._custom_rules_conn = None

    rows = _list_custom_rules_table_data()
    assert any(r['name'] == 'persist-check-rule' and r['severity'] == 'high' for r in rows)
