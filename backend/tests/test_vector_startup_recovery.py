import json
from services.vector_startup import initialize_vector_runtime
from tests.test_vector_runtime_health import service


def test_real_startup_reconciles_orphaned_task_before_ready(service, monkeypatch, tmp_path):
    from routes import ingest
    monkeypatch.setattr(ingest, 'TASKS_STORE_PATH', str(tmp_path / 'tasks.json'))
    monkeypatch.setattr(ingest, '_tasks', {'orphan': {'status': 'running', 'stage': 'embed'}})
    ingest._save_tasks(ingest._tasks)
    result = initialize_vector_runtime()
    assert result['ready'] is True
    persisted = json.loads((tmp_path / 'tasks.json').read_text())
    assert persisted['orphan']['status'] == 'failed'
    assert persisted['orphan']['error']['code'] == 'ingest_interrupted'


def test_startup_recovery_failure_never_reports_ready(service, monkeypatch, tmp_path):
    from routes import ingest
    from tests.test_vector_runtime_health import client
    monkeypatch.setattr(ingest, 'TASKS_STORE_PATH', str(tmp_path / 'tasks.json'))
    monkeypatch.setattr(ingest, '_tasks', {})
    def fail():
        raise OSError('synthetic-private-recovery-marker')
    original = ingest.recover_orphaned_tasks
    monkeypatch.setattr(ingest, 'recover_orphaned_tasks', fail)
    result = initialize_vector_runtime()
    assert result['ready'] is False
    assert result['code'] == 'ingest_recovery_failed'
    assert 'synthetic-private-recovery-marker' not in repr(result)
    response = client().get('/api/v1/ready')
    assert response.status_code == 503
    assert response.json()['code'] == 'ingest_recovery_failed'
    assert client().get('/api/v1/health').json()['status'] == 'unhealthy'
    monkeypatch.setattr(ingest, 'recover_orphaned_tasks', original)
    assert initialize_vector_runtime()['ready'] is True
    assert client().get('/api/v1/ready').status_code == 200
