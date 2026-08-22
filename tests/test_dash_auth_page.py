"""Tests for the Dash Auth page's extracted callback logic."""

import pytest
import medical_data_validator.auth as auth

# dashboard.pages.auth calls dash.register_page() at import time, which
# requires dash.Dash(use_pages=True) to have already run at least once in
# this process (it populates Dash's internal page-registry config). Building
# the dashboard app here — before importing the page module directly below —
# lets this test file pass in isolation, not just as part of the full suite.
# (Same pattern as tests/test_dash_registry_page.py, test_dash_jobs_page.py,
# and test_dash_audit_page.py.)
from medical_data_validator.dashboard.app import create_dashboard_app
create_dashboard_app()


@pytest.fixture(autouse=True)
def _clean_users_and_tenants():
    users_before = dict(auth._USERS)
    tenants_before = dict(auth._TENANTS)
    yield
    auth._USERS.clear()
    auth._USERS.update(users_before)
    auth._TENANTS.clear()
    auth._TENANTS.update(tenants_before)


def test_list_users_table_data_includes_admin():
    from medical_data_validator.dashboard.pages.auth import _list_users_table_data
    rows = _list_users_table_data()
    assert any(r['username'] == 'admin' for r in rows)


def test_create_user_from_form_then_appears_in_list():
    from medical_data_validator.dashboard.pages.auth import _create_user_from_form, _list_users_table_data
    ok, message = _create_user_from_form('dash-created-user', 'password123', 'read-only', 'default')
    assert ok is True
    rows = _list_users_table_data()
    assert any(r['username'] == 'dash-created-user' for r in rows)


def test_deactivate_user_from_form():
    from medical_data_validator.dashboard.pages.auth import _create_user_from_form, _deactivate_user_from_form, _list_users_table_data
    _create_user_from_form('to-deactivate', 'password123', 'read-only', 'default')
    ok, message = _deactivate_user_from_form('to-deactivate')
    assert ok is True
    rows = _list_users_table_data()
    row = next(r for r in rows if r['username'] == 'to-deactivate')
    assert row['active'] is False


def test_create_tenant_from_form():
    from medical_data_validator.dashboard.pages.auth import _create_tenant_from_form
    ok, message = _create_tenant_from_form('new-tenant')
    assert ok is True
