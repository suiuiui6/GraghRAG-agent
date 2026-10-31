"""Authorized active-revision retrieval against real SQLite and table dependencies."""
import hashlib
import sqlite3
import pytest
from doc_processor import Chunk
from services.document_publication import DocumentPublication
from services.document_catalog import CatalogConflict, CatalogNotFound
from vector_runtime import SyntheticStorageConfig
from vector_store import VectorStore

PROFILE = {'model': 'fixed-test-model', 'revision': 'test-sha', 'dimension': 2, 'normalize': True}

@pytest.fixture
def service():
    with SyntheticStorageConfig.create() as config:
        store = VectorStore(persist_dir=str(config.root / 'database'), embedding_dim=2, embedding_model=PROFILE['model'], synthetic_config=config)
        yield DocumentPublication(store, config.root / 'assets', PROFILE)

def publish(service, task, doc, chunks, expected=None, owner='alice'):
    asset = service.asset_root / (task + '.txt')
    asset.write_text(task)
    return service.publish(task, doc, {'owner_id': owner, 'filename': 'same.xlsx'}, chunks,
        [[1., 0.] for _ in chunks], assets=[{'path': asset.name,
        'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}], expected_revision=expected)

@pytest.mark.parametrize('page_size', [1, 17, 256])
def test_bm25_last_page_is_scoped_to_active_revision(service, page_size):
    publish(service, 'a1', 'a', [Chunk('old', 'retiredunique', 'text')])
    chunks = [Chunk(str(i), 'ordinary filler text', 'text') for i in range(136)]
    chunks.append(Chunk('last', 'lastpageneedle', 'text'))
    publish(service, 'a2', 'a', chunks, expected=1)
    publish(service, 'b1', 'b', [Chunk('last', 'lastpageneedle forbidden', 'text')], owner='bob')
    with service.read_snapshot(allowed_document_ids={'a'}, page_size=page_size) as snapshot:
        rows = snapshot.retrieve('lastpageneedle', enabled_sources={'bm25'}, top_k=3)
        assert [r['metadata']['document_id'] for r in rows] == ['a']
        assert rows[0]['metadata']['document_version'] == 2
        assert rows[0]['text'] == 'lastpageneedle'
        assert snapshot.retrieve('retiredunique', enabled_sources={'bm25'}) == []
        assert snapshot.connection.in_transaction
    with pytest.raises(sqlite3.ProgrammingError):
        snapshot.connection.execute('SELECT 1')


def test_table_identity_survives_same_filename_and_reopen(service):
    def table(value):
        return Chunk('same', 'budget ' + str(value), 'table', table_json={
            'sheet_name': 'Budget', 'headers': ['name', 'budget'], 'rows': [['test', value]]})
    publish(service, 'a1', 'a', [table(10)])
    publish(service, 'a2', 'a', [table(20)], expected=1)
    publish(service, 'b1', 'b', [table(999)], owner='bob')
    again = DocumentPublication(service.store, service.asset_root, PROFILE)
    with again.read_snapshot(allowed_document_ids={'a'}) as snapshot:
        rows = snapshot.retrieve('budget', enabled_sources={'table'}, table_conditions=["column_name = 'budget' AND column_value_numeric >= 15"])
        assert rows
        wide = snapshot.retrieve('budget', enabled_sources={'table'}, table_conditions=["name = 'test'"])
        assert wide and all(row['metadata']['document_id'] == 'a' for row in wide)
        assert all(r['metadata']['document_id'] == 'a' and r['metadata']['document_version'] == 2 for r in rows)
        assert all('999' not in r['text'] for r in rows)
    service.delete('a')
    with again.read_snapshot(allowed_document_ids={'a'}) as snapshot:
        assert snapshot.retrieve('budget', enabled_sources={'table', 'bm25'}) == []


def test_fresh_validation_rejects_update_delete_and_revocation(service):
    publish(service, 'a1', 'a', [Chunk('c', 'old', 'text')])
    with service.read_snapshot(allowed_document_ids={'a'}) as snapshot:
        versions = snapshot.versions
    publish(service, 'a2', 'a', [Chunk('c', 'new', 'text')], expected=1)
    with pytest.raises(CatalogConflict, match='revision_conflict'):
        service.validate_snapshot(versions)
    def revoked(doc):
        raise PermissionError('revoked')
    with pytest.raises(PermissionError):
        service.validate_snapshot({'a': 2}, authorize=revoked)
    service.delete('a')
    with pytest.raises(CatalogNotFound):
        service.validate_snapshot({'a': 2})


def test_authorization_and_early_exit_close_snapshot(service):
    publish(service, 'a1', 'a', [Chunk('c', 'one', 'text')])
    def reject(doc):
        raise PermissionError('not allowed')
    with pytest.raises(PermissionError):
        with service.read_snapshot(allowed_document_ids={'a'}, authorize=reject):
            pytest.fail('unauthorized snapshot exposed')
    with pytest.raises(RuntimeError):
        with service.read_snapshot(allowed_document_ids={'a'}) as snapshot:
            list(snapshot.store.iter_record_pages(page_size=1))
            raise RuntimeError('consumer stopped')
    with pytest.raises(sqlite3.ProgrammingError):
        snapshot.connection.execute('SELECT 1')
    with service.catalog() as catalog:
        assert catalog.connection.execute('SELECT COUNT(*) FROM document_pins').fetchone()[0] == 0

from tests.test_vector_http_lifecycle import http_env, provider_boundary, seed

@pytest.mark.parametrize('source', ['bm25', 'table'])
def test_authenticated_scoped_sources_use_only_active_authorized_data(http_env, provider_boundary, source):
    client, service, headers, _ = http_env
    table = {'sheet_name': 'Budget', 'headers': ['budget'], 'rows': [[20]]}
    publish(service, 'a1', 'a', [Chunk('c', 'budget authorizedneedle 20', 'table', table_json=table)])
    publish(service, 'b1', 'b', [Chunk('c', 'budget forbidden 999', 'table', table_json=table)], owner='bob')
    result = client.post('/api/v1/rag/query', headers=headers(), json={
        'query': 'budget authorizedneedle', 'document_id': 'a',
        'options': {'enabled_sources': [source], 'include_sources': True}})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['metadata']['enabled_sources'] == [source]
    assert body['sources']
    assert all(row['properties']['document_id'] == 'a' for row in body['sources'])
    assert 'forbidden' not in body['answer']


def test_generation_version_change_retries_entire_retrieval_once(http_env, provider_boundary):
    client, service, headers, _ = http_env
    seed(service, text='oldunique')
    provider_boundary['callback'] = lambda: seed(service, task='next', text='newunique', expected=1)
    result = client.post('/api/v1/rag/query', headers=headers(), json={
        'query': 'content', 'document_id': 'doc_a', 'options': {'enabled_sources': ['vector']}})
    assert result.status_code == 200, result.text
    assert 'oldunique' not in result.json()['answer']
    assert 'newunique' in result.json()['answer']
    assert result.json()['metadata']['active_revisions'] == {'doc_a': 2}



def test_vector_and_bm25_keep_same_snapshot_when_update_commits(service):
    publish(service, 'a1', 'a', [Chunk('c', 'oldunique', 'text')])
    with service.read_snapshot(allowed_document_ids={'a'}) as snapshot:
        first = snapshot.retrieve('oldunique', enabled_sources={'vector'}, query_vector=[1., 0.])
        publish(service, 'a2', 'a', [Chunk('c', 'newunique', 'text')], expected=1)
        second = snapshot.retrieve('oldunique', enabled_sources={'bm25'})
        assert first[0]['metadata']['document_version'] == second[0]['metadata']['document_version'] == 1
        assert first[0]['text'] == second[0]['text'] == 'oldunique'
    with pytest.raises(CatalogConflict, match='revision_conflict'):
        service.validate_snapshot(snapshot.versions)


def seed_graph(service):
    import json
    directory = service.asset_root / 'graph1' / 'kg'
    directory.mkdir(parents=True)
    nodes, edges = directory / 'nodes.json', directory / 'edges.json'
    nodes.write_text(json.dumps([{'node_id': 'n1', 'label': 'authorizedneedle',
                                 'entity_type': 'Budget', 'grounding_status': 'grounded'}]))
    edges.write_text('[]')
    assets = [{'path': p.relative_to(service.asset_root).as_posix(),
               'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in (nodes, edges)]
    return service.publish('graph1', 'graphdoc', {'owner_id': 'alice', 'kg_path': str(directory),
                           'filename': 'same.docx'}, [], [], assets=assets)


@pytest.mark.parametrize('change', ['delete', 'revoke'])
def test_managed_kg_generation_discards_on_delete_or_revocation(http_env, provider_boundary, change):
    from services import auth_service
    client, service, headers, _ = http_env
    seed_graph(service)
    def mutate():
        if change == 'delete':
            service.delete('graphdoc')
        else:
            (auth_service.USERS_DIR / 'alice.json').unlink()
    provider_boundary['callback'] = mutate
    result = client.post('/api/v1/rag/query', headers=headers(), json={
        'query': 'authorizedneedle', 'document_id': 'graphdoc',
        'options': {'enabled_sources': ['kg']}})
    assert result.status_code == 404, result.text
    assert 'authorizedneedle' not in result.text


@pytest.mark.parametrize('sources', [None, ['kg'], ['kg', 'bm25']])
def test_managed_kg_kept_in_default_and_mixed_recall(http_env, provider_boundary, sources):
    client, service, headers, _ = http_env
    seed_graph(service)
    options = {} if sources is None else {'enabled_sources': sources}
    result = client.post('/api/v1/rag/query', headers=headers(), json={
        'query': 'authorizedneedle', 'document_id': 'graphdoc', 'options': options})
    assert result.status_code == 200, result.text
    body = result.json()
    assert 'kg' in body['metadata']['enabled_sources']
    assert body['sources'] and body['sources'][0]['properties']['document_id'] == 'graphdoc'

