"""Crash recovery uses durable receipts and real cross-process kernel leases."""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import pytest
from tests.test_vector_http_lifecycle import http_env, PROFILE


def task():
    now = datetime.now(timezone.utc).isoformat()
    return dict(task_id='crash_task', owner_id='alice', filename='original.pdf', status='running',
                stage='embed', created_at=now, updated_at=now, error=None, result=None, progress=None)


CHILD = r"""
import sys, os, hashlib, socket
def refuse_network(*args, **kwargs):
    raise AssertionError('Crash fixture must not access any network')
socket.socket.connect = refuse_network
from pathlib import Path
from vector_runtime import SyntheticStorageConfig
from vector_store import VectorStore
from services.document_publication import DocumentPublication
from services.document_runtime import configure_publication
from services.document_catalog import DocumentCatalog
from doc_processor import Chunk
from routes import ingest
import worker
root, task_store, phase = sys.argv[1:]
config = SyntheticStorageConfig.from_root(root)
store = VectorStore(persist_dir=str(config.root/'database'), embedding_dim=2,
                    embedding_model='synthetic-fixed-projection', synthetic_config=config)
service = DocumentPublication(store, config.root/'assets',
    {'model':'synthetic-fixed-projection','revision':'fixture-v1','dimension':2,'normalize':True})
configure_publication(service)
ingest.TASKS_STORE_PATH = task_store
ingest._tasks = ingest._load_tasks()
path = config.root/'original.pdf'
path.write_bytes(b'synthetic-original')
def pipeline(*args):
    if phase == 'live':
        print('locked', flush=True)
        sys.stdin.readline()
        os._exit(73)
    return {'document_id':'doc_crash','kg_nodes':0,'kg_edges':0,'pages_parsed':1,
            'grounded_entities':0,'entity_types':0,'kg_path':'',
            '_publication_chunks':[Chunk('c1','synthetic source','text')],
            '_publication_embeddings':[[1.0,0.0]]}
worker.run_real_pipeline = pipeline
if phase == 'before_commit':
    DocumentCatalog.commit = lambda *args, **kwargs: os._exit(73)
if phase == 'after_commit':
    save = ingest._save_tasks
    def crash_before_done(tasks, *args):
        if tasks['crash_task']['status'] == 'done':
            os._exit(73)
        return save(tasks, *args)
    ingest._save_tasks = crash_before_done
ingest._run_indexing('crash_task', str(path), 'original.pdf', path.stat().st_size,
                     {'identity':{'owner_id':'alice'}, 'principal':{'user_id':'alice', 'roles':['viewer'], 'auth_type':'synthetic'}})
"""


@pytest.mark.parametrize('phase,status', [('before_commit','failed'), ('after_commit','done')])
def test_child_crash_reconciles_http_status_without_reembedding(http_env, phase, status):
    from routes import ingest
    client, service, headers, config = http_env
    ingest._tasks['crash_task'] = task()
    ingest._save_tasks(ingest._tasks)
    result = subprocess.run([sys.executable, '-B', '-c', CHILD, str(config.root),
                             ingest.TASKS_STORE_PATH, phase], capture_output=True, text=True, timeout=30,
                            env={**os.environ, 'PYTHON_DOTENV_DISABLED':'1'})
    assert result.returncode == 73, result.stderr + Path(ingest.TASKS_STORE_PATH).read_text()
    ingest._tasks = ingest._load_tasks()
    ingest.recover_orphaned_tasks()
    response = client.get('/api/v1/status/crash_task', headers=headers())
    assert response.status_code == 200, response.text
    assert response.json()['status'] == status
    assert client.get('/api/v1/status/crash_task', headers=headers('bob')).status_code == 404
    if status == 'done':
        assert response.json()['result']['document_id'] == 'doc_crash'
        assert response.json()['result']['active_revision'] == 1
    else:
        assert response.json()['error']['code'] == 'ingest_interrupted'
        with service.catalog() as catalog:
            assert catalog.task_receipt('crash_task')['status'] == 'failed'
        assert service.documents() == []
    first = response.json()
    ingest.recover_orphaned_tasks()
    assert client.get('/api/v1/status/crash_task', headers=headers()).json() == first


def test_startup_recovery_does_not_interrupt_live_other_process(http_env):
    from routes import ingest
    client, service, headers, config = http_env
    ingest._tasks['crash_task'] = task()
    ingest._save_tasks(ingest._tasks)
    child = subprocess.Popen([sys.executable, '-B', '-c', CHILD, str(config.root),
                               ingest.TASKS_STORE_PATH, 'live'], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == 'locked'
        ingest.recover_orphaned_tasks()
        assert client.get('/api/v1/status/crash_task', headers=headers()).json()['status'] == 'running'
    finally:
        child.terminate()
        child.communicate(timeout=15)
    ingest.recover_orphaned_tasks()
    assert client.get('/api/v1/status/crash_task', headers=headers()).json()['error']['code'] == 'ingest_interrupted'


def test_failed_receipt_remains_failed_on_restart(http_env):
    from routes import ingest
    from services.document_catalog import CatalogConflict
    client, service, headers, config = http_env
    ingest._tasks['crash_task'] = task()
    ingest._save_tasks(ingest._tasks)
    result = subprocess.run([sys.executable,'-B','-c',CHILD,str(config.root),ingest.TASKS_STORE_PATH,'before_commit'],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 73, result.stderr + Path(ingest.TASKS_STORE_PATH).read_text()
    with service.catalog() as catalog:
        (service.asset_root/'crash_task'/'original.pdf').write_bytes(b'changed')
        with pytest.raises(CatalogConflict):
            catalog.commit('crash_task')
    ingest.recover_orphaned_tasks()
    response = client.get('/api/v1/status/crash_task', headers=headers()).json()
    assert response['status'] == 'failed'
    assert response['error']['code'] == 'asset_integrity'


def test_gate_closed_does_not_reclassify_legacy_tasks(http_env):
    from routes import ingest
    from services.document_runtime import configure_publication
    ingest._tasks['crash_task'] = task()
    ingest._save_tasks(ingest._tasks)
    configure_publication(None)
    before = Path(ingest.TASKS_STORE_PATH).read_bytes()
    ingest.recover_orphaned_tasks()
    assert Path(ingest.TASKS_STORE_PATH).read_bytes() == before


def test_scheduled_pending_task_holds_kernel_lease(http_env):
    from routes import ingest
    from fastapi import BackgroundTasks
    client, service, headers, config = http_env
    ingest._tasks['crash_task'] = {**task(), 'status':'pending'}
    ingest._schedule_indexing(BackgroundTasks(), 'crash_task', 'unused', 'source.pdf', 0, {})
    try:
        ingest.recover_orphaned_tasks()
        assert ingest._tasks['crash_task']['status'] == 'pending'
        from filelock import Timeout
        from services.vector_ingest import task_lock
        with pytest.raises(Timeout):
            task_lock(ingest.TASKS_STORE_PATH, 'crash_task').acquire(timeout=0)
    finally:
        ingest._scheduled_leases.pop('crash_task').release()
