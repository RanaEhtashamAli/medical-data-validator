"""Tests for the Dash Auth page's extracted callback logic."""

import pytest
import dash
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

from tests.conftest import _set_triggered


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


# --- Direct dispatcher tests: _handle_user_actions --------------------------
# Each test confirms the RIGHT branch fired and routed its result into the
# CORRECT output — this is what would catch a cross-wired routing bug (e.g.
# the create branch accidentally calling deactivate, or vice versa).

def test_handle_user_actions_create_routes_to_user_message_and_table():
    from medical_data_validator.dashboard.pages.auth import _handle_user_actions

    _set_triggered('auth-create-user-btn')
    table, message = _handle_user_actions(
        1, None, None, 'dispatch-create-user', 'password123', 'read-only', 'default'
    )

    assert 'dispatch-create-user' in message
    assert any(r['username'] == 'dispatch-create-user' for r in table)
    # Not routed to the tenant callback's side effects.
    assert 'dispatch-create-user' not in auth._TENANTS


def test_handle_user_actions_create_failure_does_not_deactivate_anyone():
    from medical_data_validator.dashboard.pages.auth import _handle_user_actions

    # 'admin' already exists, so this create attempt must fail...
    _set_triggered('auth-create-user-btn')
    table, message = _handle_user_actions(1, None, None, 'admin', 'password123', 'read-only', 'default')

    assert 'already exists' in message.lower()
    # ...and must NOT have deactivated the existing admin as a side effect
    # (which is what would happen if the create branch mistakenly routed to
    # the deactivate helper).
    row = next(r for r in table if r['username'] == 'admin')
    assert row['active'] is True


def test_handle_user_actions_deactivate_routes_to_user_message_and_table():
    from medical_data_validator.dashboard.pages.auth import _handle_user_actions, _create_user_from_form

    _create_user_from_form('dispatch-deactivate-user', 'password123', 'read-only', 'default')

    _set_triggered('auth-deactivate-btn')
    table, message = _handle_user_actions(None, 1, None, 'dispatch-deactivate-user', None, None, None)

    assert 'deactivated' in message.lower()
    assert 'dispatch-deactivate-user' in message
    row = next(r for r in table if r['username'] == 'dispatch-deactivate-user')
    assert row['active'] is False


def test_handle_user_actions_deactivate_unknown_user_does_not_create_one():
    from medical_data_validator.dashboard.pages.auth import _handle_user_actions

    _set_triggered('auth-deactivate-btn')
    table, message = _handle_user_actions(None, 1, None, 'never-created-user', None, None, None)

    assert 'not found' in message.lower()
    # If the deactivate branch mistakenly routed to the create helper, this
    # user would now exist.
    assert not any(r['username'] == 'never-created-user' for r in table)


def test_handle_user_actions_refresh_leaves_message_empty_and_ignores_form_fields():
    from medical_data_validator.dashboard.pages.auth import _handle_user_actions

    _set_triggered('auth-refresh-btn')
    table, message = _handle_user_actions(
        None, None, 1, 'admin', 'irrelevant-password', 'admin', 'default'
    )

    assert message == ""
    # Refresh must not create or deactivate anything, even though create/
    # deactivate-shaped form values were supplied alongside it.
    row = next(r for r in table if r['username'] == 'admin')
    assert row['active'] is True
    assert table == auth.list_user_accounts()


def test_handle_user_actions_initial_load_leaves_message_empty():
    from medical_data_validator.dashboard.pages.auth import _handle_user_actions

    _set_triggered(None)
    table, message = _handle_user_actions(None, None, None, None, None, None, None)

    assert message == ""
    assert table == auth.list_user_accounts()


# --- Direct dispatcher tests: _handle_tenant_actions ------------------------

def test_handle_tenant_actions_create_routes_to_tenant_message():
    from medical_data_validator.dashboard.pages.auth import _handle_tenant_actions

    users_before = dict(auth._USERS)

    _set_triggered('auth-create-tenant-btn')
    message = _handle_tenant_actions(1, 'dispatch-create-tenant')

    assert 'dispatch-create-tenant' in message
    assert 'dispatch-create-tenant' in auth._TENANTS
    # Not routed to the user callback's side effects.
    assert auth._USERS == users_before


def test_handle_tenant_actions_duplicate_tenant_reports_error():
    from medical_data_validator.dashboard.pages.auth import _handle_tenant_actions

    _set_triggered('auth-create-tenant-btn')
    message = _handle_tenant_actions(1, 'default')

    assert 'already exists' in message.lower()
