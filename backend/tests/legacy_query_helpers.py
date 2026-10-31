"""Physical, registered legacy KG inputs for model-boundary route tests."""
import json


def register_legacy_query_graph(monkeypatch, root):
    import routes
    import routes.query as query
    from services import document_runtime

    graph_root = root / 'output' / 'kg'
    directory = graph_root / 'legacy-fixture'
    version = directory / 'v1'
    version.mkdir(parents=True)
    (directory / 'versions.json').write_text(
        json.dumps({'doc_id': 'legacy-fixture', 'active_version': 1,
                    'versions': [{'version': 1}]}), encoding='utf-8')
    (version / 'nodes.json').write_text(json.dumps({'nodes': [{
        'node_id': 'claim', 'entity_type': 'claim', 'label': 'fixture evidence',
        'properties': {}, 'page_idx': 0, 'grounding_status': 'grounded',
    }]}), encoding='utf-8')
    (version / 'edges.json').write_text('{"edges": []}', encoding='utf-8')
    original = root / 'uploads' / 'fixture.md'
    original.parent.mkdir()
    original.write_text('fixture evidence', encoding='utf-8')
    docs_path = root / 'output' / 'docs_store.json'
    document = {'document_id': 'legacy-fixture', 'owner_id': 'compat-admin',
                'filename': original.name, 'filepath': str(original),
                'kg_path': str(directory), 'status': 'indexed'}
    docs_path.write_text(json.dumps([document]), encoding='utf-8')
    monkeypatch.setattr(routes, 'DOCS_JSON_PATH', str(docs_path))
    monkeypatch.setattr(routes, '_docs_store', routes._load_docs())
    monkeypatch.setattr(document_runtime, '_publication', None)
    monkeypatch.setattr(query, 'KG_DIR', str(graph_root))
    return document


def assert_registered_query_graph(graph, document):
    assert set(graph) == {document['document_id'] + '__claim'}
    node = graph.nodes[document['document_id'] + '__claim']
    assert node['grounding_status'] == 'grounded'
    assert node['document_id'] == document['document_id']
    assert node['document_version'] == 1
