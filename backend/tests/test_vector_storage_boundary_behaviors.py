"""Real SQLite boundary behavior; synthetic data, no storage mocks."""
import hashlib
import json
import sqlite3
from contextlib import closing
from types import SimpleNamespace

import pytest

from sqlite_vector_store import VectorStore
from vector_errors import VectorInputError, VectorStorageError
from vector_runtime import SyntheticIntegrationConfig, connect


@pytest.fixture
def storage(tmp_path):
    root = tmp_path / 'synthetic'
    config = SyntheticIntegrationConfig.create(root)
    store = VectorStore('boundary', root / 'vectors', 2,
                        embedding_model='synthetic/boundary-v1', integration_config=config)
    return store, config, root


def add_records(store):
    store._collection.add(
        ids=['one', 'two', 'three', 'four'],
        embeddings=[[1., 0.], [0., 1.], [-1., 0.], [0., -1.]],
        documents=['first', 'second', 'third', 'fourth'],
        metadatas=[{'n': 1, 'group': 'a', 'flag': True},
                   {'n': 2, 'group': 'b', 'flag': False},
                   {'n': 3, 'group': 'a', 'flag': True}, {'group': 'c'}])


@pytest.mark.parametrize(('where', 'expected'), [
    ({'n': {'$gt': 1}}, ['two', 'three']),
    ({'n': {'$gte': 2}}, ['two', 'three']),
    ({'n': {'$lt': 2}}, ['one']),
    ({'n': {'$lte': 2}}, ['one', 'two']),
    ({'n': {'$ne': 2}}, ['one', 'three', 'four']),
    ({'n': {'$in': [1, 3]}}, ['one', 'three']),
    ({'n': {'$nin': [1, 3]}}, ['two', 'four']),
    ({'flag': {'$in': [True]}}, ['one', 'three']),
    ({'n': '1'}, []),
    ({'n': {'$ne': '1'}}, ['one', 'two', 'three', 'four']),
    ({'group': {'$nin': ['a', 'b']}}, ['four']),
    ({'$and': [{'group': 'a'}, {'$or': [{'n': 3}, {'n': 4}]}]}, ['three']),
    ({'$or': [{'group': 'c'}, {'n': {'$lt': 2}}]}, ['one', 'four']),
    ({'n': {'$in': [1., 2.]}}, ['one', 'two']),
])
def test_filters_select_same_records_in_get_and_search(storage, where, expected):
    store, _, _ = storage
    add_records(store)
    assert store._collection.get(where=where)['ids'] == expected
    assert {row['chunk_id'] for row in store.search([1., 0.], where=where)} == set(expected)
    assert store.count() == 4


@pytest.mark.parametrize('where', [
    [], {}, {'n': 1, 'group': 'a'}, {1: 'a'}, {'$unknown': 1},
    {'$and': [{'n': 1}]}, {'$or': 'n'}, {'n': {}},
    {'n': {'$unknown': 1}}, {'n': {'$gt': 'one'}},
    {'n': {'$in': []}}, {'n': {'$in': [1, '2']}},
    {'n': {'$in': [None]}}, {'n': {'$eq': None}},
    {'n': {'$in': [2 ** 63]}}, {'n': {'$in': [1e400]}},
])
def test_bad_filters_fail_without_deleting_records(storage, where):
    store, _, _ = storage
    add_records(store)
    with pytest.raises(VectorInputError) as caught:
        store._collection.delete(where=where)
    assert (caught.value.code, caught.value.operation) == ('invalid_filter', 'compile')
    assert store._collection.get()['ids'] == ['one', 'two', 'three', 'four']


def test_cyclic_filter_is_rejected_without_traversal_hang(storage):
    store, _, _ = storage
    add_records(store)
    cycle = {'$and': []}
    cycle['$and'] = [{'n': 1}, cycle]
    with pytest.raises(VectorInputError, match='过滤条件'):
        store.search([1., 0.], where=cycle)
    assert store.count() == 4


def test_filter_offset_counts_only_matching_ids_and_releases_reader(storage):
    store, _, _ = storage
    add_records(store)
    result = store._collection.get(ids=['four', 'three', 'one'],
                                   where={'group': {'$in': ['a', 'c']}}, offset=1, limit=1)
    assert result == {'ids': ['three'], 'documents': ['third'],
                      'metadatas': [{'n': 3, 'group': 'a', 'flag': True}]}
    assert store._collection.get(limit=0) == {'ids': [], 'documents': [], 'metadatas': []}
    with closing(connect(store.path)) as connection:
        assert connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0] == 0


def test_empty_scope_then_nested_scope_restore_and_external_connection_survives(storage):
    store, config, root = storage
    add_records(store)
    other = VectorStore('other', root / 'vectors', 2,
                        embedding_model=store.embedding_model, integration_config=config)
    other._collection.add(ids=['other-id'], embeddings=[[1., 0.]], documents=['other'])
    with store.read_snapshot() as connection:
        with store.read_snapshot_connection(connection, collection_names=()):
            assert store.count() == 0
            assert list(store.iter_record_pages()) == []
            assert store.search([1., 0.]) == []
            with store.read_snapshot_connection(connection, collection_names=('other',)):
                assert store._collection.get()['ids'] == ['other-id']
            assert store.count() == 0
        assert store.count(connection=connection) == 4
        assert connection.in_transaction
    assert store.count() == 4
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        connection.execute('SELECT 1')


@pytest.mark.parametrize('bad_scope', [[], ('',), (1,), 'boundary'])
def test_snapshot_rejects_invalid_scope_and_preserves_transaction(storage, bad_scope):
    store, _, _ = storage
    add_records(store)
    with store.read_snapshot() as connection:
        with pytest.raises(VectorInputError):
            with store.read_snapshot_connection(connection, collection_names=bad_scope):
                pytest.fail('invalid collection scope was accepted')
        assert connection.in_transaction
        assert store.count(connection=connection) == 4


def test_snapshot_rejects_other_database_and_inactive_transaction(storage, tmp_path):
    store, _, _ = storage
    add_records(store)
    with closing(connect(tmp_path / 'foreign.sqlite')) as connection:
        with pytest.raises(VectorInputError):
            with store.read_snapshot_connection(connection):
                pytest.fail('inactive connection was accepted')
        connection.execute('BEGIN')
        with pytest.raises(VectorInputError):
            with store.read_snapshot_connection(connection):
                pytest.fail('foreign database was accepted')
        with pytest.raises(VectorInputError):
            store.count(connection=connection)
        connection.rollback()
    assert store.count() == 4


@pytest.mark.parametrize(('column', 'value', 'code'), [
    ('dimension', 3, 'dimension_conflict'),
    ('embedding_model', 'different-model', 'model_conflict'),
    ('model_fingerprint', 'wrong-fingerprint', 'model_conflict'),
])
def test_manifest_change_is_detected_by_new_and_caller_owned_readers(storage, column, value, code):
    store, _, _ = storage
    add_records(store)
    with closing(connect(store.path)) as writer, writer:
        writer.execute('UPDATE collections SET ' + column + '=? WHERE name=?', (value, store.collection_name))
    with pytest.raises(VectorStorageError) as caught:
        store.count()
    assert caught.value.code == code
    with closing(connect(store.path, True)) as connection:
        connection.execute('BEGIN')
        with pytest.raises(VectorStorageError) as caught:
            store.count(connection=connection)
        assert caught.value.code == code
        connection.rollback()


def test_missing_collection_is_not_successful_empty_read(storage):
    store, _, _ = storage
    with closing(connect(store.path)) as writer, writer:
        writer.execute('DELETE FROM collections')
    with pytest.raises(VectorStorageError) as caught:
        store.count()
    assert caught.value.code == 'schema_mismatch'
    with closing(connect(store.path, True)) as connection:
        connection.execute('BEGIN')
        with pytest.raises(VectorStorageError) as caught:
            store.count(connection=connection)
        assert caught.value.code == 'schema_mismatch'


def test_generator_early_close_releases_wal_reader(storage):
    store, _, _ = storage
    add_records(store)
    pages = store.iter_record_pages(1)
    assert next(pages)['ids'] == ['one']
    store.delete_by_chunk_ids(['two'])
    pages.close()
    with closing(connect(store.path)) as writer:
        assert writer.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0] == 0
    assert store._collection.get()['ids'] == ['one', 'three', 'four']


def test_corrupt_payload_raises_safe_scan_error_and_releases_wal_reader(storage):
    store, _, _ = storage
    add_records(store)
    with closing(connect(store.path)) as writer, writer:
        writer.execute("UPDATE payload SET data=? WHERE field='metadata'", (b'{not-json',))
    with pytest.raises(VectorStorageError) as caught:
        list(store.iter_record_pages(1))
    assert caught.value.public_dict()['code'] == 'storage_unavailable'
    assert caught.value.operation == 'scan'
    assert 'not-json' not in str(caught.value)
    with closing(connect(store.path)) as writer:
        assert writer.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0] == 0


def test_page_byte_budget_splits_large_unicode_records_without_losing_bytes(storage):
    store, _, _ = storage
    text = '甲😀' * 650000
    store._collection.add(ids=['large-a', 'large-b'], embeddings=[[1., 0.], [0., 1.]],
                          documents=[text, text], metadatas=[{'source_file': 'a'}, {'source_file': 'b'}])
    pages = list(store.iter_record_pages(256))
    assert [page['ids'] for page in pages] == [['large-a'], ['large-b']]
    assert [doc for page in pages for doc in page['documents']] == [text, text]
    assert [row['chunk_id'] for row in store.search([0., 1.], top_k=1, text_char_limit=2,
                                                 metadata_keys=['source_file', 'missing'])] == ['large-b']
    assert store.search([0., 1.], top_k=1, text_char_limit=2,
                        metadata_keys=['source_file', 'missing'])[0]['metadata'] == {'source_file': 'b'}


def chunk_with_metadata(identifier, *, entity_types, section_path, entity_ids):
    return SimpleNamespace(chunk_id=identifier, text='text', content_type='paragraph',
                           metadata=SimpleNamespace(source_file='source', source_format='docx',
                               page_idx=0, content_type='paragraph', project_id='p', token_count=1,
                               entity_types=entity_types, section_path=section_path, entity_ids=entity_ids,
                               char_start=0, char_end=4))


def test_nested_chunk_metadata_streams_unicode_escapes_and_nulls(storage):
    store, _, _ = storage
    entities = ['甲"\\\n' * 9000, {'name': ('β', None, True, 3.5), 'nested': {'x': []}}]
    chunk = chunk_with_metadata('nested', entity_types=entities,
                                section_path=['章', '节'], entity_ids=['id'])
    store.add_chunks([chunk], [[1., 0.]])
    metadata = store.get_by_ids(['nested'])[0]['metadata']
    assert metadata['entity_types'] == json.loads(json.dumps(entities))
    assert metadata['section_path'] == ['章', '节']
    assert metadata['entity_ids'] == ['id']


@pytest.mark.parametrize('bad_value', ['cycle', 'bad-key', 'object'])
def test_invalid_nested_metadata_batch_is_atomic_and_stage_is_removed(storage, bad_value):
    store, _, _ = storage
    add_records(store)
    if bad_value == 'cycle':
        value = []; value.append(value)
    elif bad_value == 'bad-key':
        value = {1: 'bad'}
    else:
        value = [object()]
    chunk = chunk_with_metadata('invalid', entity_types=value, section_path=[], entity_ids=[])
    with pytest.raises(VectorInputError):
        store.add_chunks([chunk], [[1., 0.]])
    assert store.count() == 4
    assert not list(store.path.parent.glob('private-*'))


def test_reopen_rejects_orphan_payload_in_exact_schema(storage):
    store, config, _ = storage
    with closing(sqlite3.connect(store.path)) as connection, connection:
        connection.execute('PRAGMA foreign_keys=OFF')
        connection.execute("INSERT INTO payload VALUES (999,'document',0,?)", (b'orphan',))
    with pytest.raises(VectorStorageError) as caught:
        VectorStore(store.collection_name, store.persist_dir, 2,
                    embedding_model=store.embedding_model, integration_config=config)
    assert caught.value.code == 'schema_mismatch'


@pytest.mark.parametrize('damage', ['too-small', 'too-large', 'wrong-model', 'bad-schema'])
def test_restore_failure_leaves_target_and_temporary_stage_absent(storage, damage):
    store, config, root = storage
    add_records(store)
    backup = root / 'backup.sqlite'
    identity = store.backup(backup)
    model = store.embedding_model
    if damage == 'too-small':
        identity['size'] -= 1
    elif damage == 'too-large':
        identity['size'] += 1
    elif damage == 'wrong-model':
        model = 'wrong-model'
    else:
        with closing(sqlite3.connect(backup)) as connection, connection:
            connection.execute('CREATE TABLE untrusted(data TEXT)')
        identity = {'size': backup.stat().st_size, 'sha256': hashlib.sha256(backup.read_bytes()).hexdigest()}
    target = root / 'restored'
    with pytest.raises((VectorInputError, VectorStorageError)):
        VectorStore.restore(backup, target, **identity, collection_name=store.collection_name,
                            embedding_dim=2, embedding_model=model, integration_config=config)
    assert not target.exists()
    assert not list(root.glob('private-*'))
    assert store.count() == 4


def test_empty_batches_are_noops_and_mismatched_batch_preserves_existing_data(storage):
    store, _, _ = storage
    add_records(store)
    store.add_chunks([], [])
    store.delete_by_chunk_ids([])
    assert store.get_by_ids([]) == []
    with pytest.raises(VectorInputError) as caught:
        store.add_chunks([], [[1., 0.]])
    assert caught.value.code == 'invalid_input'
    assert store.count() == 4


def test_collection_info_deduplicates_sources_and_delete_targets_only_exact_source(storage):
    store, _, _ = storage
    store._collection.add(ids=['a', 'b', 'c', 'd'], embeddings=[[1., 0.]] * 4,
                          metadatas=[{'source_file': 'same'}, {'source_file': 'same'},
                                     {'source_file': ''}, {'source_file': 'same-prefix'}])
    assert store.get_collection_info() == dict(name='boundary', count=4, dimension=2,
                                             sources=2, persist_dir=store.persist_dir)
    assert store.list_sources() == ['same', 'same-prefix']
    store.delete_by_source('same')
    assert store._collection.get()['ids'] == ['c', 'd']
    assert store.list_sources() == ['same-prefix']


def test_compatibility_reads_empty_metadata_and_replaces_malformed_nested_json(storage):
    store, _, _ = storage
    store._collection.add(ids=['empty', 'legacy'], embeddings=[[1., 0.], [0., 1.]],
                          metadatas=[{}, {'entity_types': '{broken', 'section_path': '["章"]',
                                         'entity_ids': 'not-json'}])
    rows = store.get_by_ids(['empty', 'legacy'])
    assert rows[0]['metadata'] == {}
    assert rows[1]['metadata'] == {'entity_types': [], 'section_path': ['章'], 'entity_ids': []}


def test_missing_database_backup_failure_removes_incomplete_snapshot(storage):
    store, _, root = storage
    store.path.unlink()
    snapshot = root / 'incomplete.sqlite'
    with pytest.raises(VectorStorageError) as caught:
        store.backup(snapshot)
    assert (caught.value.code, caught.value.operation) == ('storage_unavailable', 'read')
    assert not snapshot.exists()
    assert not store.path.exists()


def test_nonfinite_scalar_filter_rejects_without_mutation(storage):
    store, _, _ = storage
    add_records(store)
    with pytest.raises(VectorInputError) as caught:
        store._collection.delete(where={'n': float('inf')})
    assert caught.value.code == 'invalid_filter'
    assert store.count() == 4


def test_unrepresentable_integer_vector_batch_does_not_partially_insert(storage):
    store, _, _ = storage
    add_records(store)
    with pytest.raises(VectorInputError) as caught:
        store._collection.add(ids=['valid', 'too-large'], embeddings=[[1., 0.], [10 ** 400, 0]])
    assert caught.value.code == 'invalid_input'
    assert store.count() == 4
    assert not list(store.path.parent.glob('private-*'))
