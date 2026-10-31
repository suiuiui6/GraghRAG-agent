"""Public storage reads cannot bypass the authoritative publication directory."""
import pytest
from doc_processor import Chunk
from vector_store import VectorStore
from tests.test_vector_publication_service import service, publish, PROFILE


@pytest.mark.parametrize('state', ['inactive', 'prepared', 'deleted'])
def test_public_collection_cannot_read_nonactive_revision(service, state):
    publish(service, text='retracted-secret')
    with service.catalog() as catalog:
        old = catalog.get_active('doc1')
    collection = old['collection_name']
    if state == 'prepared':
        collection = 'document_pending'
        with service.catalog() as catalog:
            catalog.prepare('pending', 'doc1', {'owner_id': 'a', 'filename': 'same.docx'},
                            expected_revision=1, assets=old['assets'], model_profile=PROFILE,
                            collection_name=collection)
        staged = VectorStore(collection_name=collection, persist_dir=service.store.persist_dir,
                             embedding_dim=2, embedding_model=PROFILE['model'],
                             synthetic_config=service.store.synthetic_config)
        staged._collection.add(ids=['prepared-secret'], embeddings=[[1., 0.]], documents=['prepared-secret'])
    elif state == 'inactive':
        publish(service, 'v2', expected=1, text='active-visible')
        assert service.search([1., 0.], allowed_document_ids={'doc1'})[0]['text'] == 'active-visible'
    else:
        service.delete('doc1')
    public = VectorStore(collection_name=collection, persist_dir=service.store.persist_dir,
                         embedding_dim=2, embedding_model=PROFILE['model'],
                         synthetic_config=service.store.synthetic_config)
    assert public.count() == 0
    assert public._collection.get()['ids'] == []
    assert public.search([1., 0.]) == []
    assert list(public.iter_record_pages(1)) == []
