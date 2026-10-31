"""Real authenticated HTTP/catalog integration; synthetic embeddings are explicit."""
from models import TaskResult, DocumentItem, TaskError


def test_revision_wire_contract():
    assert 'active_revision' in TaskResult.model_fields
    assert 'active_revision' in DocumentItem.model_fields
    assert 'http_status' in TaskError.model_fields

import hashlib
import time
from io import BytesIO

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import create_auth_middleware
from middleware.jwt_middleware import create_jwt_middleware
from services import auth_service
from models import User
from doc_processor import Chunk
from vector_runtime import SyntheticStorageConfig
from vector_store import VectorStore
from services.document_publication import DocumentPublication

PROFILE = {'model': 'synthetic-fixed-projection', 'revision': 'fixture-v1', 'dimension': 2, 'normalize': True}
SECRET = 'synthetic-http-only-0123456789abcdef0123456789'


class SyntheticEmbedding:
    model = PROFILE['model']
    dim = PROFILE['dimension']
    model_profile = PROFILE

    calls = 0

    def embed_texts(self, texts):
        self.calls += 1
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return self.embed_text(text)

    def embed_text(self, text):
        return self.embed_texts([text])[0]


@pytest.fixture
def http_env(monkeypatch, tmp_path):
    import routes
    from routes import ingest, documents, rag_query
    from services.document_runtime import configure_publication
    monkeypatch.setenv('JWT_SECRET_KEY', SECRET)
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.delenv('AUTH_ALLOW_ANONYMOUS', raising=False)
    monkeypatch.delenv('ADMIN_API_KEY', raising=False)
    monkeypatch.setattr(auth_service, 'USERS_DIR', tmp_path / 'users')
    users = auth_service.AuthService()
    monkeypatch.setattr(auth_service, '_service', users)
    for name in ('alice', 'bob'):
        users._save_user(User(user_id=name, username=name, email='', display_name=name,
                              roles=['viewer'], created_at=users._now()))
    monkeypatch.setattr(routes, '_docs_store', [])
    monkeypatch.setattr(routes, 'DOCS_JSON_PATH', str(tmp_path / 'legacy.json'))
    monkeypatch.setattr(ingest, '_tasks', {})
    monkeypatch.setattr(ingest, 'TASKS_STORE_PATH', str(tmp_path / 'tasks.json'))
    monkeypatch.setattr(ingest, 'UPLOADS_DIR', str(tmp_path))
    with SyntheticStorageConfig.create() as config:
        store = VectorStore(persist_dir=str(config.root / 'database'), embedding_dim=2, embedding_model=PROFILE['model'], synthetic_config=config)
        service = DocumentPublication(store, config.root / 'assets', PROFILE)
        configure_publication(service, SyntheticEmbedding())
        app = FastAPI()
        for router in (ingest.router, documents.router, rag_query.router):
            app.include_router(router, prefix='/api/v1')
        app.middleware('http')(create_auth_middleware())
        app.middleware('http')(create_jwt_middleware())
        client = TestClient(app)
        def headers(name='alice'):
            token = jwt.encode({'sub': name, 'type': 'access', 'iss': 'graphrag-backend',
                                'exp': time.time() + 600}, SECRET, algorithm='HS256')
            return {'Authorization': 'Bearer ' + token}
        yield client, service, headers, config
        configure_publication(None)


def seed(service, task='task_a', document='doc_a', text='old-only-text', owner='alice', expected=None):
    path = service.asset_root / (task + '.txt')
    path.write_text(text)
    return service.publish(task, document, {'owner_id': owner, 'filename': 'same.docx', 'status': 'indexed'},
                           [Chunk('c00001', text, 'text')], [[1.0, 0.0]],
                           assets=[{'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}],
                           expected_revision=expected)


def test_http_catalog_authority_and_owner_filter(http_env):
    client, service, headers, _ = http_env
    seed(service)
    seed(service, 'task_b', 'doc_b', owner='bob')
    assert client.get('/api/v1/documents').status_code == 401
    response = client.get('/api/v1/documents', headers=headers())
    assert response.status_code == 200
    assert [(d['document_id'], d['active_revision']) for d in response.json()['documents']] == [('doc_a', 1)]


@pytest.mark.parametrize('data', [{'replace_document_id': 'doc_a'}, {'expected_revision': '1'},
                                 {'replace_document_id': '', 'expected_revision': '1'},
                                 {'replace_document_id': 'doc_a', 'expected_revision': '1.0'},
                                 {'replace_document_id': 'doc_a', 'expected_revision': '0'}])
def test_http_update_requires_exact_pair(http_env, data):
    client, service, headers, _ = http_env
    seed(service)
    response = client.post('/api/v1/ingest', headers=headers(), data=data,
                           files={'file': ('same.docx', b'irrelevant')})
    assert response.status_code == 422, response.text


def test_http_stale_update_and_cross_owner_are_rejected_before_processing(http_env):
    client, service, headers, _ = http_env
    seed(service)
    seed(service, 'task_update', expected=1)
    for who, revision, expected_code in [('alice', '1', 409), ('bob', '2', 404)]:
        response = client.post('/api/v1/ingest', headers=headers(who),
                               data={'replace_document_id': 'doc_a', 'expected_revision': revision},
                               files={'file': ('same.docx', b'irrelevant')})
        assert response.status_code == expected_code, response.text

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import json


@pytest.fixture
def provider_boundary(monkeypatch):
    """Local HTTP shape contract only, not a real model quality test."""
    control = {'callback': None}
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            callback = control['callback']
            control['callback'] = None
            if callback:
                callback()
            if self.path == '/api/chat':
                value = {'message': {'content': json.dumps({'entities': [], 'relations': []})}}
            else:
                source = next((m['content'] for m in body['messages'] if m['role'] == 'system'), '')
                value = {'choices': [{'message': {'content': source}, 'finish_reason': 'stop'}], 'usage': {}}
            data = json.dumps(value).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(data)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = 'http://127.0.0.1:' + str(server.server_port)
    monkeypatch.setenv('LANGEXTRACT_BASE_URL', url)
    monkeypatch.setenv('LANGEXTRACT_API_KEY', 'local-boundary-only')
    monkeypatch.setenv('OLLAMA_CHAT_URL', url + '/api/chat')
    control['url'] = url
    yield control
    server.shutdown()
    thread.join(timeout=3)
    server.server_close()


def vector_query(client, headers, doc='doc_a'):
    return client.post('/api/v1/rag/query', headers=headers(), json={
        'query': 'what content', 'document_id': doc,
        'options': {'enabled_sources': ['vector'], 'enable_multi_query': False,
                    'enable_cross_encoder': False}})


def test_authenticated_vector_update_delete_and_reopen(http_env, provider_boundary):
    from services.document_runtime import configure_publication
    client, service, headers, _ = http_env
    seed(service)
    seed(service, 'task_b', 'doc_b', text='other-doc-only', owner='bob')
    response = vector_query(client, headers)
    assert response.status_code == 200, response.text
    assert 'old-only-text' in response.text
    assert 'other-doc-only' not in response.text
    seed(service, 'task_v2', text='new-only-text', expected=1)
    configure_publication(DocumentPublication(service.store, service.asset_root, PROFILE), SyntheticEmbedding())
    response = vector_query(client, headers)
    assert response.status_code == 200, response.text
    assert 'new-only-text' in response.text and 'old-only-text' not in response.text
    response = client.delete('/api/v1/documents/doc_a', headers=headers())
    assert response.status_code == 200, response.text
    assert response.json()['cleanup_status'] == 'done'
    configure_publication(DocumentPublication(service.store, service.asset_root, PROFILE), SyntheticEmbedding())
    assert vector_query(client, headers).status_code == 404
    assert client.get('/api/v1/documents', headers=headers()).json()['total'] == 0
    assert vector_query(client, lambda: headers('bob'), 'doc_b').status_code == 200


def test_legacy_deleted_catalog_tombstone_survives_retained_json(http_env):
    import routes
    from services.document_runtime import configure_publication
    client, service, headers, _ = http_env
    routes._docs_store.append({'document_id': 'old_doc', 'owner_id': 'alice',
                               'filename': 'same.docx', 'status': 'indexed'})
    response = client.delete('/api/v1/documents/old_doc', headers=headers())
    assert response.status_code == 200, response.text
    assert routes._docs_store[0]['document_id'] == 'old_doc'
    configure_publication(DocumentPublication(service.store, service.asset_root, PROFILE), SyntheticEmbedding())
    assert client.get('/api/v1/documents', headers=headers()).json()['total'] == 0


def test_vector_embedding_revision_mismatch_is_unavailable(http_env, provider_boundary):
    from services.document_runtime import configure_publication
    client, service, headers, _ = http_env
    seed(service)
    class OtherRevision(SyntheticEmbedding):
        model_profile = {**PROFILE, 'revision': 'wrong-same-dimension'}
    configure_publication(service, OtherRevision())
    response = vector_query(client, headers)
    assert response.status_code == 503, response.text


def docx_bytes(text):
    from docx import Document
    document = Document()
    document.add_heading('Synthetic document', 1)
    document.add_paragraph(text)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def test_real_docx_upload_update_publish_receipt_and_download(http_env, provider_boundary):
    client, service, headers, _ = http_env
    first_bytes = docx_bytes('v1-exclusive-text')
    response = client.post('/api/v1/ingest', headers=headers(),
                           files={'file': ('same.docx', first_bytes)})
    assert response.status_code == 200, response.text
    task_id = response.json()['task_id']
    status = client.get('/api/v1/status/' + task_id, headers=headers())
    assert status.status_code == 200, status.text
    assert status.json()['status'] == 'done', status.text
    document = status.json()['result']['document_id']
    assert status.json()['result']['active_revision'] == 1
    with service.catalog() as catalog:
        assert catalog.task_receipt(task_id)['status'] == 'done'
    assert client.get('/api/v1/documents/' + document + '/download', headers=headers()).content == first_bytes
    second_bytes = docx_bytes('v2-exclusive-text')
    response = client.post('/api/v1/ingest', headers=headers(),
                           data={'replace_document_id': document, 'expected_revision': '1'},
                           files={'file': ('new-name.docx', second_bytes)})
    assert response.status_code == 200, response.text
    status = client.get('/api/v1/status/' + response.json()['task_id'], headers=headers())
    assert status.json()['status'] == 'done', status.text
    assert status.json()['result']['active_revision'] == 2
    listed = client.get('/api/v1/documents', headers=headers()).json()['documents']
    assert [(doc['document_id'], doc['filename'], doc['active_revision']) for doc in listed] == [(document, 'new-name.docx', 2)]
    assert client.get('/api/v1/documents/' + document + '/download', headers=headers()).content == second_bytes
    response = vector_query(client, headers, document)
    assert response.status_code == 200, response.text
    assert 'v2-exclusive-text' in response.text and 'v1-exclusive-text' not in response.text



def test_completed_receipt_replay_skips_worker_providers(http_env, provider_boundary):
    from routes import ingest
    from services.document_runtime import get_embedding_client
    client, service, headers, _ = http_env
    response = client.post('/api/v1/ingest', headers=headers(), files={'file': ('same.docx', docx_bytes('receipt text'))})
    task_id = response.json()['task_id']
    task = ingest._tasks[task_id]
    assert task['status'] == 'done'
    calls = get_embedding_client().calls
    ingest._run_indexing(task_id, str(__import__('pathlib').Path(ingest.UPLOADS_DIR) / (task_id + '.docx')),
                         'same.docx', task['file_size_bytes'],
                         {'identity': {'owner_id': 'alice', 'org_id': None, 'project_id': None},
                          'principal': {'user_id': 'alice', 'roles': ['viewer']}})
    assert get_embedding_client().calls == calls
    assert task['status'] == 'done'
    assert task['result']['active_revision'] == 1


def test_background_cas_conflict_is_failed_status_200_with_409_detail(http_env, provider_boundary):
    client, service, headers, _ = http_env
    seed(service)
    provider_boundary['callback'] = lambda: seed(service, 'concurrent_winner', expected=1, text='winner-only')
    response = client.post('/api/v1/ingest', headers=headers(),
                           data={'replace_document_id': 'doc_a', 'expected_revision': '1'},
                           files={'file': ('same.docx', docx_bytes('loser-only'))})
    assert response.status_code == 200, response.text
    status = client.get('/api/v1/status/' + response.json()['task_id'], headers=headers())
    assert status.status_code == 200, status.text
    assert status.json()['status'] == 'failed', status.text
    assert status.json()['error']['code'] == 'revision_conflict'
    assert status.json()['error']['http_status'] == 409
    assert service.documents()[0]['active_revision'] == 2


@pytest.mark.parametrize('change,expected', [('delete', 404), ('update', 200), ('revoke', 404)])
def test_generation_final_check_discards_changed_scope(http_env, provider_boundary, change, expected):
    from pathlib import Path
    client, service, headers, _ = http_env
    seed(service)
    def modify():
        if change == 'delete':
            service.delete('doc_a')
        elif change == 'update':
            seed(service, 'during_generation', expected=1, text='new-only')
        else:
            # Real auth registry removal, not a substituted authorizer.
            from services import auth_service
            (auth_service.USERS_DIR / 'alice.json').unlink()
    provider_boundary['callback'] = modify
    response = vector_query(client, headers)
    assert response.status_code == expected, response.text
    assert 'old-only-text' not in response.text
    if change == 'update':
        assert 'new-only' in response.text
        assert response.json()['metadata']['active_revisions'] == {'doc_a': 2}
        assert all(source['properties']['active_revision'] == 2
                   for source in response.json().get('sources', []))

import os
import subprocess
import sys
from pathlib import Path


def child_http_query(config, service, headers, doc, provider_url):
    """Rebuild all service objects in a genuinely new process and call real HTTP routes."""
    program = r'''
import json, os, sys
args = json.load(sys.stdin)
# Prepare the trusted model library before importing the application graph.
# The actual pinned model still loads below after its manifest is verified.
if 'files_sha256' in args['profile']:
    import sentence_transformers
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from auth import create_auth_middleware
from middleware.jwt_middleware import create_jwt_middleware
from services import auth_service
from services.document_publication import DocumentPublication
from services.document_runtime import configure_publication, create_pinned_embedding
from vector_runtime import SyntheticStorageConfig
from vector_store import VectorStore
from tests.test_vector_http_lifecycle import PROFILE, SyntheticEmbedding
import routes
from routes import documents, rag_query
auth_service.USERS_DIR = Path(args['users'])
auth_service._service = auth_service.AuthService()
routes._docs_store = []
config = SyntheticStorageConfig.from_root(args['root'])
profile = args['profile']
store = VectorStore(persist_dir=str(config.root / 'database'), embedding_dim=profile['dimension'], embedding_model=profile['model'], synthetic_config=config)
if 'files_sha256' in profile:
    receipt = json.loads(Path(os.environ['GRAPHRAG_TEST_MODEL_RECEIPT']).read_text(encoding='utf-8'))
    embedding = create_pinned_embedding(receipt['snapshot'], profile)
else:
    embedding = SyntheticEmbedding()
configure_publication(DocumentPublication(store, config.root / 'assets', profile), embedding)
app = FastAPI()
app.include_router(documents.router, prefix='/api/v1')
app.include_router(rag_query.router, prefix='/api/v1')
app.middleware('http')(create_auth_middleware())
app.middleware('http')(create_jwt_middleware())
with TestClient(app) as client:
    response = client.post('/api/v1/rag/query', headers=args['headers'], json={'query':'what content', 'document_id':args['doc'], 'options':{'enabled_sources':['vector']}})
    print('CHILD_RESULT=' + json.dumps({'status':response.status_code, 'body':response.json()}))
'''
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]),
           'JWT_SECRET_KEY': SECRET, 'LANGEXTRACT_BASE_URL': provider_url,
           'LANGEXTRACT_API_KEY': 'local-boundary-only'}
    result = subprocess.run([sys.executable, '-c', program], input=json.dumps({'root': str(config.root),
                              'users': str(auth_service.USERS_DIR), 'doc': doc, 'headers': headers,
                              'profile': service.model_profile}),
                            env=env, capture_output=True, text=True,
                            timeout=60 if 'files_sha256' in service.model_profile else 35)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(next(line[len('CHILD_RESULT='):] for line in result.stdout.splitlines() if line.startswith('CHILD_RESULT=')))


def test_fresh_process_http_reopen_after_update_and_after_delete(http_env, provider_boundary):
    client, service, headers, config = http_env
    seed(service)
    seed(service, 'other_task', 'doc_b', text='other-live', owner='bob')
    seed(service, 'second_revision', text='new-child-only', expected=1)
    response = child_http_query(config, service, headers(), 'doc_a', provider_boundary['url'])
    assert response['status'] == 200, response
    assert 'new-child-only' in json.dumps(response) and 'old-only-text' not in json.dumps(response)
    assert client.delete('/api/v1/documents/doc_a', headers=headers()).status_code == 200
    response = child_http_query(config, service, headers(), 'doc_a', provider_boundary['url'])
    assert response['status'] == 404, response
    response = child_http_query(config, service, headers('bob'), 'doc_b', provider_boundary['url'])
    assert response['status'] == 200, response
    assert 'other-live' in json.dumps(response)


def test_catalog_storage_corruption_returns_503_not_success_empty(http_env):
    client, service, headers, _ = http_env
    seed(service)
    # Actual file mutation, no storage exception mock.
    with service.catalog() as catalog:
        catalog.connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    service.store.path.write_bytes(b'invalid sqlite database')
    response = client.get('/api/v1/documents', headers=headers())
    assert response.status_code == 503, response.text


def test_status_recovers_committed_receipt_when_task_json_lags(http_env, provider_boundary):
    from routes import ingest
    client, service, headers, _ = http_env
    response = client.post('/api/v1/ingest', headers=headers(), files={'file': ('same.docx', docx_bytes('durable-only'))})
    task_id = response.json()['task_id']
    ingest._tasks[task_id].update(status='running', result=None, stage='kg_build')
    ingest._save_tasks(ingest._tasks)
    response = client.get('/api/v1/status/' + task_id, headers=headers())
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'done'
    assert response.json()['result']['active_revision'] == 1


def test_embedding_failure_never_publishes_done(http_env, provider_boundary):
    from services.document_runtime import configure_publication
    client, service, headers, _ = http_env
    class FailingEmbedding(SyntheticEmbedding):
        def embed_texts(self, texts):
            raise RuntimeError('synthetic provider unavailable')
    configure_publication(service, FailingEmbedding())
    response = client.post('/api/v1/ingest', headers=headers(), files={'file': ('same.docx', docx_bytes('no visible document'))})
    task_id = response.json()['task_id']
    status = client.get('/api/v1/status/' + task_id, headers=headers())
    assert status.status_code == 200, status.text
    assert status.json()['status'] == 'failed'
    assert service.documents() == []
    with service.catalog() as catalog:
        assert catalog.task_receipt(task_id) is None


# This is a correctness chain with a parent and two fresh loads of the pinned
# 96MB model, not a latency SLA. Measured call times: 118.87s uninstrumented,
# 157.24s with fixed-scope coverage; the full suite exceeded the old 180s.
# Independent review accepted 1.5x instrumented time (240s), while retaining
# global 60s and each real/synthetic child 60s/35s limits. A new timeout requires
# diagnosis, not another automatic budget increase.
@pytest.mark.timeout(240)
def test_fixed_local_model_http_upload_update_delete_restart(http_env, provider_boundary, monkeypatch):
    """Opt-in real offline model acceptance; no network/model substitute."""
    import services.document_runtime as runtime
    assert hasattr(runtime, 'create_pinned_embedding')
    receipt_path = os.environ.get('GRAPHRAG_TEST_MODEL_RECEIPT')
    if not receipt_path:
        pytest.skip('Real offline model receipt is an explicit integration dependency')
    receipt = json.loads(Path(receipt_path).read_text(encoding='utf-8'))
    profile = {'model': 'BAAI/bge-small-zh-v1.5', 'revision': receipt['revision'], 'dimension': 512,
               'normalize': True, 'files_sha256': {name: item['sha256'] for name, item in receipt['files'].items()}}
    client, _, headers, _ = http_env
    monkeypatch.setenv('HF_HUB_OFFLINE', '1')
    monkeypatch.setenv('TRANSFORMERS_OFFLINE', '1')
    with SyntheticStorageConfig.create() as config:
        store = VectorStore(persist_dir=str(config.root / 'database'), embedding_dim=512, embedding_model=profile['model'], synthetic_config=config)
        service = DocumentPublication(store, config.root / 'assets', profile)
        embedding = runtime.create_pinned_embedding(receipt['snapshot'], profile)
        runtime.configure_publication(service, embedding)
        first = client.post('/api/v1/ingest', headers=headers(), files={'file': ('same.docx', docx_bytes('第一版独有内容：锅炉检修负责人是张三。'))})
        status = client.get('/api/v1/status/' + first.json()['task_id'], headers=headers())
        assert status.json()['status'] == 'done', status.text
        doc_id = status.json()['result']['document_id']
        response = vector_query(client, headers, doc_id)
        assert response.status_code == 200, response.text
        assert '第一版独有内容' in response.text
        second = client.post('/api/v1/ingest', headers=headers(), data={'replace_document_id': doc_id, 'expected_revision': '1'},
                             files={'file': ('new.docx', docx_bytes('第二版独有内容：当前检修负责人是李四。'))})
        status = client.get('/api/v1/status/' + second.json()['task_id'], headers=headers())
        assert status.json()['status'] == 'done', status.text
        assert status.json()['result']['active_revision'] == 2
        response = vector_query(client, headers, doc_id)
        assert response.status_code == 200 and '第二版独有内容' in response.text and '第一版独有内容' not in response.text
        response = child_http_query(config, service, headers(), doc_id, provider_boundary['url'])
        assert response['status'] == 200 and '第二版独有内容' in json.dumps(response, ensure_ascii=False)
        assert client.delete('/api/v1/documents/' + doc_id, headers=headers()).status_code == 200
        response = child_http_query(config, service, headers(), doc_id, provider_boundary['url'])
        assert response['status'] == 404, response
