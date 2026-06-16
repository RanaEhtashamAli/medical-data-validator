"""Tests for the dataset registry and validation history (Phase 3d)."""

import os
import tempfile
import pytest

import medical_data_validator.registry as registry


@pytest.fixture(autouse=True)
def _isolated_registry_db():
    """Each test gets its own in-memory-equivalent fresh DB file."""
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()

    old_path = registry.REGISTRY_DB_PATH
    registry.REGISTRY_DB_PATH = tf.name
    if registry._conn is not None:
        registry._conn.close()
        registry._conn = None

    yield

    if registry._conn is not None:
        registry._conn.close()
        registry._conn = None
    registry.REGISTRY_DB_PATH = old_path
    try:
        os.unlink(tf.name)
    except FileNotFoundError:
        pass


class TestRegisterDataset:
    def test_returns_dict_with_id(self):
        ds = registry.register_dataset('ds1', tenant='acme')
        assert 'id' in ds and ds['name'] == 'ds1'

    def test_duplicate_name_same_tenant_raises(self):
        registry.register_dataset('ds1', tenant='acme')
        with pytest.raises(ValueError):
            registry.register_dataset('ds1', tenant='acme')

    def test_same_name_different_tenant_allowed(self):
        registry.register_dataset('ds1', tenant='acme')
        ds2 = registry.register_dataset('ds1', tenant='bigpharma')
        assert ds2['tenant'] == 'bigpharma'

    def test_tags_stored_as_list(self):
        ds = registry.register_dataset('ds1', tags=['ehr', 'clinical'])
        assert ds['tags'] == ['ehr', 'clinical']

    def test_metadata_stored_as_dict(self):
        ds = registry.register_dataset('ds1', metadata={'source': 'lab'})
        assert ds['metadata']['source'] == 'lab'


class TestGetDataset:
    def test_returns_dataset_by_id(self):
        created = registry.register_dataset('myds', tenant='t1')
        fetched = registry.get_dataset(created['id'])
        assert fetched['name'] == 'myds'

    def test_returns_none_for_unknown_id(self):
        assert registry.get_dataset('no-such-id') is None


class TestListDatasets:
    def test_lists_all(self):
        registry.register_dataset('a')
        registry.register_dataset('b')
        assert len(registry.list_datasets()) == 2

    def test_filter_by_tenant(self):
        registry.register_dataset('a', tenant='x')
        registry.register_dataset('b', tenant='y')
        assert len(registry.list_datasets(tenant='x')) == 1

    def test_filter_by_tag(self):
        registry.register_dataset('a', tags=['ehr'])
        registry.register_dataset('b', tags=['lab'])
        result = registry.list_datasets(tag='ehr')
        assert len(result) == 1 and result[0]['name'] == 'a'

    def test_limit_and_offset(self):
        for i in range(5):
            registry.register_dataset(f'ds{i}')
        page1 = registry.list_datasets(limit=3, offset=0)
        page2 = registry.list_datasets(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 2


class TestUpdateDataset:
    def test_update_description(self):
        ds = registry.register_dataset('ds1')
        updated = registry.update_dataset(ds['id'], description='new desc')
        assert updated['description'] == 'new desc'

    def test_update_tags(self):
        ds = registry.register_dataset('ds1', tags=['old'])
        updated = registry.update_dataset(ds['id'], tags=['new1', 'new2'])
        assert updated['tags'] == ['new1', 'new2']

    def test_returns_none_for_unknown_id(self):
        assert registry.update_dataset('no-such-id', description='x') is None

    def test_unspecified_fields_unchanged(self):
        ds = registry.register_dataset('ds1', description='original', tags=['t1'])
        registry.update_dataset(ds['id'], description='changed')
        fetched = registry.get_dataset(ds['id'])
        assert fetched['tags'] == ['t1']


class TestDeleteDataset:
    def test_delete_returns_true(self):
        ds = registry.register_dataset('ds1')
        assert registry.delete_dataset(ds['id']) is True

    def test_deleted_dataset_not_found(self):
        ds = registry.register_dataset('ds1')
        registry.delete_dataset(ds['id'])
        assert registry.get_dataset(ds['id']) is None

    def test_delete_unknown_returns_false(self):
        assert registry.delete_dataset('no-such-id') is False


class TestRunHistory:
    def test_record_run_returns_id(self):
        ds = registry.register_dataset('ds1')
        run_id = registry.record_run(ds['id'], is_valid=True, error_count=0)
        assert isinstance(run_id, str) and len(run_id) == 36

    def test_run_appears_in_history(self):
        ds = registry.register_dataset('ds1')
        run_id = registry.record_run(ds['id'], is_valid=False, error_count=3)
        history = registry.get_run_history(ds['id'])
        assert any(r['id'] == run_id for r in history)

    def test_multiple_runs_tracked(self):
        ds = registry.register_dataset('ds1')
        registry.record_run(ds['id'])
        registry.record_run(ds['id'])
        assert registry.count_runs(ds['id']) == 2

    def test_runs_ordered_newest_first(self):
        ds = registry.register_dataset('ds1')
        r1 = registry.record_run(ds['id'])
        r2 = registry.record_run(ds['id'])
        history = registry.get_run_history(ds['id'])
        assert history[0]['id'] == r2

    def test_runs_deleted_with_dataset(self):
        ds = registry.register_dataset('ds1')
        registry.record_run(ds['id'])
        registry.delete_dataset(ds['id'])
        assert registry.count_runs(ds['id']) == 0
