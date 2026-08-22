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
