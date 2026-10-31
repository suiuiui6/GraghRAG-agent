"""Runtime health uses admitted, active SQLite snapshots and real HTTP."""
from contextlib import closing
import hashlib
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from doc_processor import Chunk
from services.document_publication import DocumentPublication
from services.document_runtime import configure_publication
from vector_runtime import SyntheticStorageConfig
from vector_store import VectorStore

PROFILE = {'model': 'fixed-health', 'revision': 'fixture-v1', 'dimension': 2, 'normalize': True}


@pytest.fixture
def service():
    with SyntheticStorageConfig.create() as admission:
        store = VectorStore(persist_dir=admission.root / 'database', embedding_dim=2,
                            embedding_model=PROFILE['model'], synthetic_config=admission)
        service = DocumentPublication(store, admission.root / 'assets', PROFILE)
        configure_publication(service, SimpleNamespace(model_profile=PROFILE, model=PROFILE['model'], dim=2))
        yield service
        configure_publication(None)


def publish(service, task, expected=None):
    asset = service.asset_root / (task + '.txt')
    asset.write_text(task)
    return service.publish(task, 'doc1', {'owner_id': 'owner'},
                           [Chunk('c1', task, 'text')], [[1., 0.]],
                           assets=[{'path': asset.name, 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}],
                           expected_revision=expected)


def client():
    from auth import create_auth_middleware
    from routes.health import router
    app = FastAPI()
    app.include_router(router, prefix='/api/v1')
    app.middleware('http')(create_auth_middleware())
    return TestClient(app)


def test_default_readiness_is_blocked_without_admission(monkeypatch):
    configure_publication(None)
    monkeypatch.setenv('VECTOR_COMPATIBILITY_APPROVED', 'true')
    response = client().get('/api/v1/ready')
    assert response.status_code == 503
    assert response.json()['code'] == 'compatibility_not_approved'
    health = client().get('/api/v1/health').json()
    assert health['status'] == 'unhealthy'
    assert health['components']['vector_store'] == 'down'


def test_active_count_ignores_inactive_and_prepared(service):
    from services.catalog import CatalogBuilder
    from services.health_checker import HealthChecker
    publish(service, 'v1')
    publish(service, 'v2', 1)
    prepared = service.store.create_migration_collection(2, suffix='_prepared')
    prepared.add_chunks([Chunk('unpublished', 'hidden', 'text')], [[0., 1.]])
    response = client().get('/api/v1/ready')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'ready': True, 'code': 'synthetic_only'}
    from services.vector_startup import runtime_status
    assert runtime_status()['chunks'] == 1
    assert runtime_status()['documents'] == 1
    assert CatalogBuilder()._count_chunks() == 1
    assert HealthChecker()._probe_vector_store()['chunks'] == 1
    service.delete('doc1')
    assert runtime_status()['chunks'] == 0


@pytest.mark.parametrize('damage,code', [
    ('DROP TABLE payload', 'schema_mismatch'),
    ("UPDATE collections SET embedding_model='different'", 'model_conflict'),
])
def test_live_schema_or_same_dimension_model_damage_is_not_ready(service, damage, code):
    publish(service, 'v1')
    with closing(sqlite3.connect(service.store.path)) as connection, connection:
        connection.execute(damage)
    response = client().get('/api/v1/ready')
    assert response.status_code == 503
    assert response.json()['code'] == code
    assert 'Traceback' not in response.text
    assert client().get('/api/v1/health').json()['status'] == 'unhealthy'


def test_catalog_profile_mismatch_is_not_ready(service):
    publish(service, 'v1')
    service.model_profile = {**PROFILE, 'revision': 'wrong'}
    assert client().get('/api/v1/ready').status_code == 503


def test_active_collection_model_corruption_is_not_ready(service):
    publish(service, 'v1')
    collection = service.documents()[0]['collection_name']
    with closing(sqlite3.connect(service.store.path)) as connection, connection:
        connection.execute("UPDATE collections SET embedding_model='wrong' WHERE name=?", (collection,))
    assert client().get('/api/v1/ready').json()['code'] == 'model_conflict'


def test_exclusive_database_lock_never_reports_ready(service):
    publish(service, 'v1')
    with closing(sqlite3.connect(service.store.path)) as connection:
        connection.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        connection.execute('PRAGMA journal_mode=DELETE')
        connection.execute('BEGIN EXCLUSIVE')
        try:
            response = client().get('/api/v1/ready')
            assert response.status_code == 503
            assert response.json()['code'] == 'storage_unavailable'
        finally:
            connection.rollback()


def test_explicit_synthetic_composition_and_default_no_bypass():
    from types import SimpleNamespace
    from services.vector_startup import compose_synthetic_runtime, initialize_vector_runtime
    from vector_errors import VectorStorageError
    configure_publication(None)
    assert initialize_vector_runtime()['code'] == 'compatibility_not_approved'
    encoder = SimpleNamespace(model_profile=PROFILE, model=PROFILE['model'], dim=2)
    with pytest.raises(VectorStorageError):
        compose_synthetic_runtime(None, PROFILE, encoder)
    with SyntheticStorageConfig.create() as admission:
        try:
            service = compose_synthetic_runtime(admission, PROFILE, encoder)
            publish(service, 'v1')
            assert initialize_vector_runtime()['chunks'] == 1
        finally:
            configure_publication(None)


def test_explicit_embedding_required_for_readiness(service):
    from services.vector_startup import runtime_status
    configure_publication(service, None)
    assert runtime_status()['ready'] is False


def test_ready_whitelist_does_not_allow_other_private_routes(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    configure_publication(None)
    response = client().get('/api/v1/ready')
    assert response.status_code == 503
    assert set(response.json()) == {'status', 'ready', 'code'}
    assert client().get('/api/v1/ready/extra').status_code == 401
    assert client().get('/api/v1/documents').status_code == 401
