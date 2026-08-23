"""Tests for the Dash Registry page's extracted callback logic."""

import tempfile
import pytest
import dash
import medical_data_validator.registry as registry

# dashboard.pages.registry calls dash.register_page() at import time, which
# requires dash.Dash(use_pages=True) to have already run at least once in
# this process (it populates Dash's internal page-registry config). Building
# the dashboard app here — before importing the page module directly below —
# lets this test file pass in isolation, not just as part of the full suite.
# (Same pattern as tests/test_dash_layout.py for the Validate page.)
from medical_data_validator.dashboard.app import create_dashboard_app
create_dashboard_app()

from tests.conftest import _set_triggered


@pytest.fixture(autouse=True)
def _isolated_registry_db():
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()
    old_path = registry.REGISTRY_DB_PATH
    registry.REGISTRY_DB_PATH = tf.name
    if registry._conn is not None:
        registry._conn.close()
        registry._conn = None
    yield
    registry.REGISTRY_DB_PATH = old_path
    if registry._conn is not None:
        registry._conn.close()
        registry._conn = None


def test_list_datasets_table_data_empty_initially():
    from medical_data_validator.dashboard.pages.registry import _list_datasets_table_data
    assert _list_datasets_table_data() == []


def test_create_dataset_from_form_then_appears_in_list():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form, _list_datasets_table_data
    ok, message = _create_dataset_from_form('my-dataset', 'a test dataset', 'tag1,tag2')
    assert ok is True
    rows = _list_datasets_table_data()
    assert any(r['name'] == 'my-dataset' for r in rows)


def test_create_dataset_from_form_rejects_empty_name():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form
    ok, message = _create_dataset_from_form('', '', '')
    assert ok is False
    assert 'name' in message.lower()


def test_create_dataset_from_form_rejects_duplicate():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form
    _create_dataset_from_form('dup-name', '', '')
    ok, message = _create_dataset_from_form('dup-name', '', '')
    assert ok is False


def test_list_datasets_table_data_includes_id():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form, _list_datasets_table_data
    _create_dataset_from_form('id-check', '', '')
    rows = _list_datasets_table_data()
    row = next(r for r in rows if r['name'] == 'id-check')
    assert row['id']


def test_get_dataset_details_found():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form, _list_datasets_table_data, _get_dataset_details
    _create_dataset_from_form('lookup-me', 'a description', 'tag1')
    dataset_id = next(r['id'] for r in _list_datasets_table_data() if r['name'] == 'lookup-me')
    ok, message, details = _get_dataset_details(dataset_id)
    assert ok is True
    assert 'lookup-me' in details


def test_get_dataset_details_not_found():
    from medical_data_validator.dashboard.pages.registry import _get_dataset_details
    ok, message, details = _get_dataset_details('nonexistent-id')
    assert ok is False
    assert 'not found' in message.lower()


def test_get_dataset_details_requires_id():
    from medical_data_validator.dashboard.pages.registry import _get_dataset_details
    ok, message, details = _get_dataset_details('')
    assert ok is False


def test_update_dataset_from_form_changes_description():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form, _list_datasets_table_data, _update_dataset_from_form
    _create_dataset_from_form('update-me', 'old description', '')
    dataset_id = next(r['id'] for r in _list_datasets_table_data() if r['name'] == 'update-me')
    ok, message = _update_dataset_from_form(dataset_id, 'new description', '')
    assert ok is True
    rows = _list_datasets_table_data()
    row = next(r for r in rows if r['name'] == 'update-me')
    assert row['description'] == 'new description'


def test_update_dataset_from_form_not_found():
    from medical_data_validator.dashboard.pages.registry import _update_dataset_from_form
    ok, message = _update_dataset_from_form('nonexistent-id', 'x', '')
    assert ok is False


def test_delete_dataset_by_id_removes_it():
    from medical_data_validator.dashboard.pages.registry import _create_dataset_from_form, _list_datasets_table_data, _delete_dataset_by_id
    _create_dataset_from_form('delete-me', '', '')
    dataset_id = next(r['id'] for r in _list_datasets_table_data() if r['name'] == 'delete-me')
    ok, message = _delete_dataset_by_id(dataset_id)
    assert ok is True
    rows = _list_datasets_table_data()
    assert not any(r['name'] == 'delete-me' for r in rows)


def test_delete_dataset_by_id_not_found():
    from medical_data_validator.dashboard.pages.registry import _delete_dataset_by_id
    ok, message = _delete_dataset_by_id('nonexistent-id')
    assert ok is False


def test_get_dataset_details_rejects_other_tenant():
    from medical_data_validator.dashboard.pages.registry import _get_dataset_details
    other = registry.register_dataset('other-tenants-dataset', tenant='not-default', description='secret')
    ok, message, details = _get_dataset_details(other['id'])
    assert ok is False
    assert 'not found' in message.lower()
    assert details == ""


def test_update_dataset_from_form_rejects_other_tenant():
    from medical_data_validator.dashboard.pages.registry import _update_dataset_from_form
    other = registry.register_dataset('other-tenants-update', tenant='not-default', description='original')
    ok, message = _update_dataset_from_form(other['id'], 'new description', '')
    assert ok is False
    unchanged = registry.get_dataset(other['id'])
    assert unchanged['description'] == 'original'


def test_delete_dataset_by_id_rejects_other_tenant():
    from medical_data_validator.dashboard.pages.registry import _delete_dataset_by_id
    other = registry.register_dataset('other-tenants-delete', tenant='not-default')
    ok, message = _delete_dataset_by_id(other['id'])
    assert ok is False
    assert registry.get_dataset(other['id']) is not None


# --- Fix 1 Part B: Update must not report success on a no-op ---------------

def test_update_dataset_from_form_rejects_blank_both_fields_as_noop():
    from medical_data_validator.dashboard.pages.registry import (
        _create_dataset_from_form, _list_datasets_table_data, _update_dataset_from_form,
    )
    _create_dataset_from_form('noop-update', 'original description', 'tag1')
    dataset_id = next(r['id'] for r in _list_datasets_table_data() if r['name'] == 'noop-update')
    before = registry.get_dataset(dataset_id)

    ok, message = _update_dataset_from_form(dataset_id, '', '')

    assert ok is False
    assert 'nothing to update' in message.lower()
    after = registry.get_dataset(dataset_id)
    assert after['description'] == before['description'] == 'original description'
    assert after['tags'] == before['tags'] == ['tag1']
    assert after['updated_at'] == before['updated_at']


def test_update_dataset_from_form_accepts_description_only():
    from medical_data_validator.dashboard.pages.registry import (
        _create_dataset_from_form, _list_datasets_table_data, _update_dataset_from_form,
    )
    _create_dataset_from_form('desc-only-update', 'original', 'tag1')
    dataset_id = next(r['id'] for r in _list_datasets_table_data() if r['name'] == 'desc-only-update')
    ok, message = _update_dataset_from_form(dataset_id, 'brand new description', '')
    assert ok is True
    assert registry.get_dataset(dataset_id)['description'] == 'brand new description'


# --- Fix 1 Part A: View chains into the Update form's inputs ---------------

def test_registry_view_action_populates_description_and_tags_inputs():
    from medical_data_validator.dashboard.pages.registry import (
        _handle_registry_actions, _create_dataset_from_form, _list_datasets_table_data,
    )
    _create_dataset_from_form('view-chain', 'real description', 'tagA,tagB')
    dataset_id = next(r['id'] for r in _list_datasets_table_data() if r['name'] == 'view-chain')

    _set_triggered('registry-view-btn')
    result = _handle_registry_actions(None, None, 1, None, None, None, None, None, dataset_id)
    _, create_message, lookup_message, details, description_value, tags_value = result

    assert description_value == 'real description'
    assert tags_value == 'tagA, tagB'
    assert 'view-chain' in details


def test_registry_view_action_on_not_found_does_not_touch_form_inputs():
    from medical_data_validator.dashboard.pages.registry import _handle_registry_actions

    _set_triggered('registry-view-btn')
    result = _handle_registry_actions(None, None, 1, None, None, None, None, None, 'nonexistent-id')
    _, create_message, lookup_message, details, description_value, tags_value = result

    assert description_value is dash.no_update
    assert tags_value is dash.no_update
    assert 'not found' in lookup_message.lower()


# --- Fix 2: directly test the `_handle_registry_actions` dispatcher --------
# Each test confirms the RIGHT branch fired and routed its result into the
# CORRECT Output — this is what would catch a cross-wired routing bug (e.g.
# the update branch's message landing in create_message instead of
# lookup_message).

def test_handle_registry_actions_create_routes_to_create_message_only():
    from medical_data_validator.dashboard.pages.registry import _handle_registry_actions

    _set_triggered('registry-create-btn')
    _table, create_message, lookup_message, details, description_value, tags_value = \
        _handle_registry_actions(1, None, None, None, None, 'dispatch-create', 'a description', 'tag1', None)

    assert 'dispatch-create' in create_message
    assert lookup_message == ""
    assert details == ""
    assert description_value is dash.no_update
    assert tags_value is dash.no_update


def test_handle_registry_actions_view_routes_to_lookup_message_and_details_only():
    from medical_data_validator.dashboard.pages.registry import (
        _handle_registry_actions, _create_dataset_from_form, _list_datasets_table_data,
    )
    _create_dataset_from_form('dispatch-view', 'view description', 'vtag')
    dataset_id = next(r['id'] for r in _list_datasets_table_data() if r['name'] == 'dispatch-view')

    _set_triggered('registry-view-btn')
    _table, create_message, lookup_message, details, description_value, tags_value = \
        _handle_registry_actions(None, None, 1, None, None, None, None, None, dataset_id)

    assert create_message == ""
    assert lookup_message == ""
    assert 'dispatch-view' in details
    assert description_value == 'view description'
    assert tags_value == 'vtag'


def test_handle_registry_actions_update_routes_to_lookup_message_only():
    from medical_data_validator.dashboard.pages.registry import (
        _handle_registry_actions, _create_dataset_from_form, _list_datasets_table_data,
    )
    _create_dataset_from_form('dispatch-update', 'old description', '')
    dataset_id = next(r['id'] for r in _list_datasets_table_data() if r['name'] == 'dispatch-update')

    _set_triggered('registry-update-btn')
    _table, create_message, lookup_message, details, description_value, tags_value = \
        _handle_registry_actions(None, None, None, 1, None, None, 'new description', '', dataset_id)

    assert create_message == ""
    assert 'updated' in lookup_message.lower()
    assert details == ""
    assert description_value is dash.no_update
    assert tags_value is dash.no_update
    assert registry.get_dataset(dataset_id)['description'] == 'new description'


def test_handle_registry_actions_delete_routes_to_lookup_message_only():
    from medical_data_validator.dashboard.pages.registry import (
        _handle_registry_actions, _create_dataset_from_form, _list_datasets_table_data,
    )
    _create_dataset_from_form('dispatch-delete', '', '')
    dataset_id = next(r['id'] for r in _list_datasets_table_data() if r['name'] == 'dispatch-delete')

    _set_triggered('registry-delete-btn')
    _table, create_message, lookup_message, details, description_value, tags_value = \
        _handle_registry_actions(None, None, None, None, 1, None, None, None, dataset_id)

    assert create_message == ""
    assert 'deleted' in lookup_message.lower()
    assert details == ""
    assert description_value is dash.no_update
    assert tags_value is dash.no_update
    assert registry.get_dataset(dataset_id) is None
