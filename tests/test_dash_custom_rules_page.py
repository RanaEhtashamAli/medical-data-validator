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
