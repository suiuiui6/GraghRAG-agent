"""SQLite I/O failures preserve identity; never return a temporary mirror."""
import pytest

from vector_errors import VectorStorageError
from vector_runtime import SyntheticIntegrationConfig
from vector_store import VectorStore


def test_corrupt_store_is_not_replaced_with_an_empty_mirror(tmp_path):
    root = tmp_path / 'synthetic'
    config = SyntheticIntegrationConfig.create(root)
    store = VectorStore(persist_dir=str(root / 'vectors'), embedding_dim=2, integration_config=config)
    store._collection.add(ids=['a'], embeddings=[[1.0, 0.0]], documents=['original'])
    store.path.write_bytes(b'corrupt registered database')
    before = store.path.read_bytes()
    with pytest.raises(VectorStorageError) as caught:
        VectorStore(persist_dir=store.persist_dir, embedding_dim=2, integration_config=config)
    assert caught.value.code == 'storage_unavailable'
    assert store.path.read_bytes() == before
    assert {p.name for p in root.iterdir()} == {'.synthetic-vector-integration.json', 'vectors'}


def test_existing_mirror_does_not_rescue_failed_authoritative_database(tmp_path, monkeypatch):
    import sqlite_vector_store
    root = tmp_path / 'synthetic'
    config = SyntheticIntegrationConfig.create(root)
    store = VectorStore(persist_dir=str(root / 'vectors'), embedding_dim=2, integration_config=config)
    store._collection.add(ids=['a'], embeddings=[[1.0, 0.0]], documents=['original'])
    mirror = root / 'graphrag_chroma' / 'vectordb'
    mirror.mkdir(parents=True)
    sentinel = mirror / 'do-not-use.txt'
    sentinel.write_bytes(b'unrelated mirror')
    before = store.path.read_bytes()
    def unavailable(*args, **kwargs):
        raise OSError('synthetic disk I/O failure')
    monkeypatch.setattr(sqlite_vector_store, 'connect', unavailable)
    with pytest.raises(VectorStorageError) as caught:
        store.search([1.0, 0.0])
    assert caught.value.code == 'storage_unavailable'
    assert store.path.read_bytes() == before
    assert sentinel.read_bytes() == b'unrelated mirror'
    assert store.persist_dir == str((root / 'vectors').resolve())
