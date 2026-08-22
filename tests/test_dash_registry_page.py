"""Tests for the Dash Registry page's extracted callback logic."""

import tempfile
import pytest
import medical_data_validator.registry as registry

# dashboard.pages.registry calls dash.register_page() at import time, which
# requires dash.Dash(use_pages=True) to have already run at least once in
# this process (it populates Dash's internal page-registry config). Building
# the dashboard app here — before importing the page module directly below —
# lets this test file pass in isolation, not just as part of the full suite.
# (Same pattern as tests/test_dash_layout.py for the Validate page.)
from medical_data_validator.dashboard.app import create_dashboard_app
create_dashboard_app()


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
