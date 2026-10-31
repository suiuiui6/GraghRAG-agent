import sys, pathlib, json
from types import SimpleNamespace
sys.path.insert(0,r'C:/Users/14156/.codex/worktrees/safe-checkpoint-20261014/graghRAG-agent/backend')
from vector_runtime import SyntheticStorageConfig
from vector_store import VectorStore
from services.document_publication import DocumentPublication
from services.document_runtime import configure_publication
from services.vector_startup import initialize_vector_runtime, runtime_status
from routes import ingest
from routes.health import router
from fastapi import FastAPI
from fastapi.testclient import TestClient
profile={'model':'startup-review','revision':'fixture','dimension':2,'normalize':True}
with SyntheticStorageConfig.create() as config:
    store=VectorStore(persist_dir=config.root/'database',embedding_dim=2,embedding_model=profile['model'],synthetic_config=config)
    service=DocumentPublication(store,config.root/'assets',profile)
    configure_publication(service,SimpleNamespace(model_profile=profile,model=profile['model'],dim=2))
    def fail():raise OSError('synthetic-recovery-failure')
    recover=ingest.recover_orphaned_tasks
    ingest.recover_orphaned_tasks=fail
    state=initialize_vector_runtime()
    app=FastAPI();app.state.vector_runtime=state;app.include_router(router,prefix='/api/v1')
    response=TestClient(app).get('/api/v1/ready')
    result={'startup':state,'ready_http_status':response.status_code,'ready_body':response.json()}
    ingest.recover_orphaned_tasks=recover
    ingest.TASKS_STORE_PATH=str(config.root/'tasks.json')
    result['successful_retry']=initialize_vector_runtime()
    result['retry_ready_status']=TestClient(app).get('/api/v1/ready').status_code
    print(json.dumps(result,indent=2))
    pathlib.Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2))
    configure_publication(None)
