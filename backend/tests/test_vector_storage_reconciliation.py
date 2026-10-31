import struct
import vector_store as vs
import vector_numeric as numeric

def test_both_admissions_and_external_snapshot(tmp_path):
    cfg=vs.SyntheticIntegrationConfig.create(tmp_path)
    store=vs.VectorStore(persist_dir=tmp_path/'db',embedding_dim=2,embedding_model='synthetic-fixed',integration_config=cfg)
    store._collection.add(ids=['a'],embeddings=[[1.,0.]],metadatas=[{'number':1}])
    with store.read_snapshot() as connection:
        with store.read_snapshot_connection(connection,collection_names=(store.collection_name,)):
            assert store.count()==store.count(connection=connection)==1
            assert len(store.search([1.,0.]))==1
    with vs.SyntheticStorageConfig.create() as second:
        assert vs.VectorStore(persist_dir=second.root/'db',embedding_dim=2,synthetic_config=second).count()==0

def test_i64_record_identity_without_subprocess(monkeypatch):
    def forbidden(*args): raise AssertionError('signed integer spawned native process')
    monkeypatch.setattr(numeric,'_exchange',forbidden)
    for number in [-(1<<63),-1,0,1,(1<<63)-1]:
        assert numeric.record_ingress(number)==('i64',number)


def test_declared_dimension_large_legal_and_reopen():
    with vs.SyntheticStorageConfig.create() as config:
        store=vs.VectorStore(persist_dir=config.root/'db',embedding_dim=2,synthetic_config=config)
        identifiers=[str(n) for n in range(11001)]
        store._collection.add(ids=identifiers,embeddings=[[1.,0.]]*11001,metadatas=[{'n':n} for n in range(11001)])
        assert store.count()==11001
        assert len(store.search([1.,0.],1001))==1001
        reopened=vs.VectorStore(persist_dir=store.persist_dir,embedding_dim=2,synthetic_config=config)
        assert reopened.count()==11001
        assert reopened.search([1.,0.],1)[0]['chunk_id']=='0'


def test_unadmitted_legacy_reports_migration_without_empty_database(tmp_path):
    import pytest
    original=b'legacy-byte-identity'
    (tmp_path/'chroma.sqlite3').write_bytes(original)
    with pytest.raises(vs.VectorStorageError) as caught:
        vs.VectorStore(persist_dir=tmp_path)
    assert caught.value.code=='migration_required'
    assert (tmp_path/'chroma.sqlite3').read_bytes()==original
    assert not (tmp_path/'vectors.sqlite').exists()
