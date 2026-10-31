"""Public facade readback must reflect exactly one original Chroma log replay."""
import math
import struct

from vector_store import VectorStore
from vector_runtime import SyntheticStorageConfig


def test_write_uses_original_record_formatter_once(monkeypatch):
    import sqlite_vector_store
    from vector_numeric import record_ingress
    calls = []
    def observe(value):
        calls.append(value)
        return record_ingress(value)
    monkeypatch.setattr(sqlite_vector_store, 'record_ingress', observe, raising=False)
    with SyntheticStorageConfig.create() as config:
        store = VectorStore(persist_dir=str(config.root / 'db'), embedding_dim=2, synthetic_config=config)
        store._collection.add(ids=['one'], embeddings=[[1.0, 0.0]], documents=['one'],
                              metadatas=[{'number': 1.2345678901234567}])
        assert calls == [1.2345678901234567]
        before = len(calls)
        assert store.get_by_ids(['one'])[0]['metadata']['number'] == record_ingress(1.2345678901234567)[1]
        assert len(calls) == before


def test_record_formatter_projection_is_used_by_real_store():
    with SyntheticStorageConfig.create() as config:
        store = VectorStore(persist_dir=str(config.root / 'db'), embedding_dim=2, synthetic_config=config)
        original = math.nextafter(float(2**63), 0.0)
        store._collection.add(ids=['one'], embeddings=[[1.0, 0.0]], documents=['one'], metadatas=[{'number': original}])
        value = store.get_by_ids(['one'])[0]['metadata']['number']
        assert struct.pack('>d', value).hex() == '43e0000000000000'


def test_public_readback_never_projects_record_again(monkeypatch):
    import sqlite_vector_store
    with SyntheticStorageConfig.create() as config:
        store = VectorStore(persist_dir=str(config.root / 'db'), embedding_dim=2, synthetic_config=config)
        store._collection.add(ids=['one'], embeddings=[[1.0, 0.0]], documents=['one'], metadatas=[{'number': 1.2345678901234567}])
        before = store.get_by_ids(['one'])[0]['metadata']['number']
        def forbidden(*args, **kwargs):
            raise AssertionError('readback must not perform record ingress')
        monkeypatch.setattr(sqlite_vector_store, 'record_ingress', forbidden, raising=False)
        assert store.get_by_ids(['one'])[0]['metadata']['number'] == before
        assert store.search([1.0, 0.0])[0]['metadata']['number'] == before
