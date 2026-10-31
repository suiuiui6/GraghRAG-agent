"""Health graph statistics from real legacy/per-document disk artifacts.

No graph counting function, JSON decoder, filesystem call or HTTP handler is
mocked. Synthetic vector publication keeps readiness independent of graph data.
"""
import hashlib
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from doc_processor import Chunk
from services.document_publication import DocumentPublication
from services.document_runtime import configure_publication
from vector_runtime import SyntheticStorageConfig
from vector_store import VectorStore


PROFILE = {'model': 'health-artifact-fixture', 'revision': 'v1', 'dimension': 2, 'normalize': True}


@pytest.fixture
def graph_health(monkeypatch, tmp_path):
    import index_registry
    import routes
    from auth import create_auth_middleware
    from routes import health
    from services import document_runtime, health_checker

    graph_root = tmp_path / 'kg'
    monkeypatch.setattr(health, 'KG_DIR', str(graph_root))
    # Isolate unrelated persisted/singleton state; use the real snapshot/probes.
    monkeypatch.setattr(routes, '_docs_store', [])
    monkeypatch.setattr(routes, 'query_count', 3)
    monkeypatch.setattr(health_checker, '_checker', health_checker.HealthChecker())
    monkeypatch.setattr(index_registry, 'BM25_ARTIFACT_PATH', tmp_path / 'bm25.json')
    monkeypatch.setattr(index_registry, 'TABLE_ARTIFACT_PATH', tmp_path / 'table.json')
    previous = (document_runtime._publication, document_runtime._embedding_client)
    with SyntheticStorageConfig.create() as admission:
        store = VectorStore(persist_dir=admission.root / 'database', embedding_dim=2,
                            embedding_model=PROFILE['model'], synthetic_config=admission)
        service = DocumentPublication(store, admission.root / 'assets', PROFILE)
        asset = service.asset_root / 'source.txt'
        asset.write_text('A synthetic health document.', encoding='utf-8')
        service.publish('health-task', 'health-document', {'owner_id': 'fixture-owner'},
                        [Chunk('health-chunk', asset.read_text(encoding='utf-8'), 'text')], [[1., 0.]],
                        assets=[{'path': asset.name,
                                 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}])
        configure_publication(service, SimpleNamespace(model_profile=PROFILE, model=PROFILE['model'], dim=2))
        app = FastAPI()
        app.include_router(health.router, prefix='/api/v1')
        app.middleware('http')(create_auth_middleware())
        try:
            with TestClient(app) as client:
                assert client.get('/api/v1/ready').json() == {
                    'status': 'ok', 'ready': True, 'code': 'synthetic_only'}
                yield graph_root, client
        finally:
            configure_publication(*previous)


def write_graph(directory, nodes, edges):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'nodes.json').write_text(json.dumps({'nodes': nodes}), encoding='utf-8')
    (directory / 'edges.json').write_text(json.dumps({'edges': edges}), encoding='utf-8')


def assert_counts(client, nodes, edges):
    response = client.get('/api/v1/health')
    assert response.status_code == 200
    body = response.json()
    assert body['stats'] == {
        'total_documents': 1, 'total_kg_nodes': nodes, 'total_kg_edges': edges,
        'total_queries_served': 3, 'queries_today': 0}
    assert body['components']['vector_store'] == 'ok'
    assert body['dependencies']['vector_store']['ready'] is True
    assert body['dependencies']['vector_store']['chunks'] == 1
    assert body['dependencies']['vector_store']['documents'] == 1
    return body


@pytest.mark.parametrize('layout', ['missing', 'empty', 'stray-file', 'empty-document'])
def test_absent_graph_artifacts_report_zero_without_losing_publication(graph_health, layout):
    root, client = graph_health
    if layout != 'missing':
        root.mkdir()
    if layout == 'stray-file':
        (root / 'README.txt').write_text('not a document directory', encoding='utf-8')
    elif layout == 'empty-document':
        (root / 'doc-empty').mkdir()
    assert_counts(client, 0, 0)


def test_legacy_flat_graph_counts_survive_empty_directory_and_stray_file(graph_health):
    root, client = graph_health
    write_graph(root, [{'id': '甲'}, {'id': '乙'}, {'id': '丙'}],
                [{'source': '甲', 'target': '乙'}, {'source': '乙', 'target': '丙'}])
    (root / 'doc-without-artifacts').mkdir()
    (root / 'README.txt').write_text('ignored', encoding='utf-8')
    assert_counts(client, 3, 2)


def test_two_document_graphs_are_summed_without_double_counting_flat_default(graph_health):
    root, client = graph_health
    write_graph(root, [{'id': f'legacy-{i}'} for i in range(11)], [{'id': i} for i in range(7)])
    write_graph(root / 'doc-a', [{'id': 'a'}, {'id': 'b'}], [{'source': 'a', 'target': 'b'}])
    write_graph(root / 'doc-b', [{'id': 'c'}, {'id': 'd'}, {'id': 'e'}],
                [{'source': 'c', 'target': 'd'}, {'source': 'd', 'target': 'e'}])
    (root / 'empty-document').mkdir()
    (root / 'stray.json').write_text('{}', encoding='utf-8')
    assert_counts(client, 5, 3)


@pytest.mark.parametrize('damaged', ['nodes', 'edges'])
@pytest.mark.parametrize('content', ['{broken', '[]'])
def test_one_corrupt_document_artifact_preserves_other_document_and_statistic(
        graph_health, damaged, content):
    root, client = graph_health
    write_graph(root / 'good', [{'id': 'g1'}, {'id': 'g2'}], [{'source': 'g1', 'target': 'g2'}])
    write_graph(root / 'partial', [{'id': 'p1'}, {'id': 'p2'}, {'id': 'p3'}],
                [{'source': 'p1', 'target': 'p2'}, {'source': 'p2', 'target': 'p3'}])
    (root / 'partial' / (damaged + '.json')).write_text(content, encoding='utf-8')
    assert_counts(client, 2 if damaged == 'nodes' else 5, 1 if damaged == 'edges' else 3)


@pytest.mark.parametrize('damaged', ['nodes', 'edges'])
def test_corrupt_flat_artifact_does_not_zero_its_sibling(graph_health, damaged):
    root, client = graph_health
    write_graph(root, [{'id': 'a'}, {'id': 'b'}], [{'source': 'a', 'target': 'b'}])
    (root / (damaged + '.json')).write_text('{broken', encoding='utf-8')
    assert_counts(client, 0 if damaged == 'nodes' else 2, 0 if damaged == 'edges' else 1)


def test_valid_empty_objects_and_arrays_have_zero_counts(graph_health):
    root, client = graph_health
    write_graph(root, [], [])
    assert_counts(client, 0, 0)
    (root / 'nodes.json').write_text('{}', encoding='utf-8')
    (root / 'edges.json').write_text('{}', encoding='utf-8')
    assert_counts(client, 0, 0)


def test_repeated_health_requests_read_updated_disk_artifacts(graph_health):
    root, client = graph_health
    write_graph(root / 'live-document', [{'id': 'first'}], [])
    assert_counts(client, 1, 0)
    write_graph(root / 'live-document', [{'id': 'first'}, {'id': 'second'}],
                [{'source': 'first', 'target': 'second'}])
    assert_counts(client, 2, 1)
