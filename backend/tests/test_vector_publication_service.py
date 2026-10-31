"""Real adapter and catalog publication, without provider or authorization mocks."""
import hashlib

import pytest

from doc_processor import Chunk
from vector_store import VectorStore
from vector_runtime import SyntheticStorageConfig
from services.document_publication import DocumentPublication
from services.document_catalog import CatalogConflict, CatalogNotFound

PROFILE = {'model': 'fixed-test-model', 'revision': 'test-sha', 'dimension': 2, 'normalize': True}


@pytest.fixture
def service():
    with SyntheticStorageConfig.create() as config:
        store = VectorStore(persist_dir=str(config.root / 'database'), embedding_dim=2, embedding_model=PROFILE['model'], synthetic_config=config)
        yield DocumentPublication(store, config.root / 'assets', PROFILE)


def test_service_refuses_same_dimension_different_store_model(tmp_path):
    with SyntheticStorageConfig.create() as config:
        store = VectorStore(persist_dir=str(config.root / 'database'), embedding_dim=2,
                            embedding_model='different-model', synthetic_config=config)
        with pytest.raises(CatalogConflict) as caught:
            DocumentPublication(store, config.root / 'assets', PROFILE)
        assert caught.value.code == 'model_profile_mismatch'


def test_published_collection_retains_authoritative_store_model():
    with SyntheticStorageConfig.create() as config:
        store = VectorStore(persist_dir=str(config.root / 'database'), embedding_dim=2,
                            embedding_model=PROFILE['model'], synthetic_config=config)
        service = DocumentPublication(store, config.root / 'assets', PROFILE)
        publish(service)
        with service.catalog() as catalog:
            active = catalog.get_active('doc1')
            stored = catalog.connection.execute('SELECT embedding_model FROM collections WHERE name=?',
                                                 (active['collection_name'],)).fetchone()
            assert stored == (PROFILE['model'],)


def publish(service, task='task1', document='doc1', expected=None, text='alpha', owner='a'):
    asset = service.asset_root / (task + '.txt')
    asset.parent.mkdir(exist_ok=True)
    asset.write_text(text)
    return service.publish(task, document, {'owner_id': owner, 'filename': 'same.docx'},
                           [Chunk('c00001', text, 'text')], [[1.0, 0.0]],
                           assets=[{'path': asset.name, 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}],
                           expected_revision=expected)


def test_two_same_name_local_chunk_ids_preserve_both_documents(service):
    publish(service)
    publish(service, 'task2', 'doc2', text='beta', owner='b')
    a = service.search([1.0, 0.0], allowed_document_ids={'doc1'})
    b = service.search([1.0, 0.0], allowed_document_ids={'doc2'})
    assert [row['text'] for row in a] == ['alpha']
    assert [row['text'] for row in b] == ['beta']
    assert a[0]['chunk_id'] != b[0]['chunk_id']
    assert a[0]['metadata']['owner_id'] == 'a'
    assert b[0]['metadata']['document_id'] == 'doc2'


def test_update_hides_old_unique_text_and_is_reopenable(service):
    publish(service, text='only-v1')
    updated = publish(service, 'task2', expected=1, text='only-v2')
    assert updated['active_revision'] == 2
    again = DocumentPublication(service.store, service.asset_root, PROFILE)
    results = again.search([1.0, 0.0], allowed_document_ids={'doc1'})
    assert [row['text'] for row in results] == ['only-v2']
    assert results[0]['metadata']['document_version'] == 2


def test_deleted_doc_never_reappears_but_other_document_survives(service):
    publish(service)
    publish(service, 'task2', 'doc2', text='beta')
    service.delete('doc1')
    again = DocumentPublication(service.store, service.asset_root, PROFILE)
    assert again.search([1.0, 0.0], allowed_document_ids={'doc1'}) == []
    assert [r['text'] for r in again.search([1.0, 0.0], allowed_document_ids={'doc2'})] == ['beta']


def test_embedding_count_failure_never_publishes_done(service):
    asset = service.asset_root / 'bad.txt'
    asset.write_text('bad')
    with pytest.raises(Exception):
        service.publish('bad_task', 'bad_doc', {'owner_id': 'a'}, [Chunk('c1', 'bad', 'text')], [],
                        assets=[{'path': asset.name, 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}])
    assert service.documents() == []


def test_same_dimension_wrong_model_is_rejected(service):
    publish(service)
    with pytest.raises(CatalogConflict, match='model_profile_mismatch'):
        DocumentPublication(service.store, service.asset_root, {**PROFILE, 'model': 'different'})


def test_empty_scope_does_not_fall_back_to_all_records(service):
    publish(service)
    assert service.search([1.0, 0.0], allowed_document_ids=set()) == []


def test_task_replay_does_not_duplicate_vectors(service):
    first = publish(service)
    second = publish(service)
    assert first == second
    assert len(service.search([1.0, 0.0], allowed_document_ids={'doc1'})) == 1


def test_precommit_authorization_failure_keeps_previous_version(service):
    publish(service)
    asset = service.asset_root / 'next.txt'
    asset.write_text('not-published')
    def reject(doc):
        raise PermissionError('revoked')
    with pytest.raises(PermissionError):
        service.publish('task2', 'doc1', {'owner_id': 'a'}, [Chunk('c1', 'not-published', 'text')], [[1, 0]],
                        assets=[{'path': asset.name, 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}],
                        expected_revision=1, authorize=reject)
    assert [r['text'] for r in service.search([1, 0], allowed_document_ids={'doc1'})] == ['alpha']
