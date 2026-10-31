import hashlib
import json

import pytest
from fastapi import HTTPException

from services.document_publication import DocumentPublication
from services.document_runtime import configure_publication
from services.document_snapshot import document_graph
from vector_store import VectorStore
from vector_runtime import SyntheticStorageConfig


@pytest.fixture
def managed():
    with SyntheticStorageConfig.create() as config:
        store = VectorStore(persist_dir=str(config.root / 'db'), embedding_dim=2, embedding_model='fixed', synthetic_config=config)
        service = DocumentPublication(store, config.root / 'assets', {'model': 'fixed', 'revision': 'test', 'dimension': 2})
        configure_publication(service)
        try:
            yield service
        finally:
            configure_publication(None)


def publish_graph(service, task='t1', expected=None, label='first'):
    directory = service.asset_root / task / 'kg'
    directory.mkdir(parents=True)
    nodes = directory / 'nodes.json'
    edges = directory / 'edges.json'
    nodes.write_text(json.dumps([{'node_id': 'n1', 'label': label, 'grounding_status': 'grounded'}]))
    edges.write_text('[]')
    assets = [{'path': path.relative_to(service.asset_root).as_posix(), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in (nodes, edges)]
    return service.publish(task, 'doc1', {'owner_id': 'a', 'kg_path': str(directory), 'filename': 'source.docx'},
                           [], [], assets=assets, expected_revision=expected)


def test_graph_uses_registered_asset_root_and_revision(managed, tmp_path):
    doc = publish_graph(managed)
    graph = document_graph(doc, tmp_path / 'unrelated-legacy-kg')
    assert graph.nodes['doc1__n1']['label'] == 'first'
    assert graph.nodes['doc1__n1']['document_version'] == 1


def test_managed_graph_rejects_stale_snapshot(managed, tmp_path):
    old = publish_graph(managed)
    current = publish_graph(managed, 't2', expected=1, label='second')
    with pytest.raises(HTTPException) as failure:
        document_graph(old, tmp_path / 'legacy')
    assert failure.value.status_code == 409
    assert document_graph(current, tmp_path / 'legacy').nodes['doc1__n1']['label'] == 'second'


def test_graph_corruption_does_not_return_unverified_nodes(managed, tmp_path):
    doc = publish_graph(managed)
    (managed.asset_root / 't1/kg/nodes.json').write_text('[{"node_id":"injected"}]')
    with pytest.raises(HTTPException) as failure:
        document_graph(doc, tmp_path / 'legacy')
    assert failure.value.status_code == 409


@pytest.mark.parametrize('missing', ['nodes.json', 'edges.json'])
def test_registered_graph_missing_asset_fails_closed(managed, tmp_path, missing):
    doc = publish_graph(managed)
    (managed.asset_root / 't1/kg' / missing).unlink()
    with pytest.raises(HTTPException) as failure:
        document_graph(doc, tmp_path / 'legacy')
    assert failure.value.status_code == 409
