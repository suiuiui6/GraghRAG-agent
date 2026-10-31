"""Fail-closed runtime composition and live admitted-snapshot readiness.

Compatibility and native package admission remain open. Production receives no
override flag; explicit synthetic capabilities are the only current composition.
"""
from __future__ import annotations

import hashlib
from services.document_runtime import get_publication, configure_publication, get_embedding_client
from vector_errors import VectorStoreError

_recovery_failure_service = None


def compose_synthetic_runtime(admission, model_profile, embedding_client):
    from vector_runtime import SyntheticStorageConfig
    from vector_store import VectorStore
    from services.document_publication import DocumentPublication
    if type(admission) is not SyntheticStorageConfig:
        from vector_errors import VectorStorageError
        raise VectorStorageError('compatibility_not_approved', 'open')
    if (getattr(embedding_client, 'model_profile', None) != model_profile
            or getattr(embedding_client, 'model', None) != model_profile.get('model')
            or getattr(embedding_client, 'dim', None) != model_profile.get('dimension')):
        raise ValueError('model_profile_mismatch')
    store = VectorStore(persist_dir=admission.root / 'database',
                        embedding_dim=model_profile['dimension'],
                        embedding_model=model_profile['model'], synthetic_config=admission)
    service = DocumentPublication(store, admission.root / 'assets', model_profile)
    configure_publication(service, embedding_client)
    return service


def runtime_status():
    service = get_publication()
    if service is not None and service is _recovery_failure_service:
        return {'status': 'down', 'ready': False, 'code': 'ingest_recovery_failed'}
    return _probe_runtime_status()


def _probe_runtime_status():
    """Probe each request; a prior successful probe is never readiness evidence."""
    service = get_publication()
    if service is None:
        return {'status': 'down', 'ready': False, 'code': 'compatibility_not_approved'}
    try:
        from vector_runtime import require_admission, probe_runtime
        from sqlite_vector_store import validate_schema
        from services.document_catalog import CatalogConflict
        require_admission(service.store.persist_dir, service.store.integration_config)
        runtime = probe_runtime()
        get_embedding_client()
        with service.store.read_snapshot() as connection:
            validate_schema(connection)
        # One catalog snapshot pins assets and fixes active collections. Counts
        # never include prepared, previous revisions, or unpublished base rows.
        with service.catalog() as catalog:
            with catalog.read_snapshot() as snapshot:
                for document in snapshot.documents:
                    if document['model_profile'] != service.model_profile:
                        raise CatalogConflict('model_profile_mismatch')
                    manifest = snapshot.connection.execute(
                        'SELECT dimension,embedding_model,model_fingerprint FROM collections WHERE name=?',
                        (document['collection_name'],)).fetchone()
                    expected = (service.model_profile['dimension'], service.store.embedding_model,
                                hashlib.sha256(service.store.embedding_model.encode('utf-8')).hexdigest())
                    if manifest != expected:
                        from vector_errors import VectorStorageError
                        raise VectorStorageError('model_conflict', 'read')
                collections = tuple(doc['collection_name'] for doc in snapshot.documents)
                with service.store.read_snapshot_connection(snapshot.connection, collection_names=collections):
                    chunks = service.store.count(connection=snapshot.connection)
                return {'status': 'ok', 'ready': True, 'code': 'synthetic_only',
                        'documents': len(snapshot.documents), 'chunks': chunks,
                        'generation': snapshot.generation, **runtime}
    except VectorStoreError as exc:
        code = exc.code
    except Exception as exc:
        # Only finite catalog error identities are public, never raw exceptions.
        code = getattr(exc, 'code', '')
        if code not in {'model_profile_mismatch', 'asset_integrity', 'unsafe_asset',
                        'catalog_integrity', 'revision_conflict'}:
            code = 'storage_unavailable'
    return {'status': 'down', 'ready': False, 'code': code}


def initialize_vector_runtime():
    """Default startup is blocked; no data migration or environment admission."""
    global _recovery_failure_service
    service = get_publication()
    # Retry the actual probe without clearing a failure visible to concurrent
    # readiness requests. Only successful reconciliation releases the latch.
    state = _probe_runtime_status()
    if state['ready']:
        try:
            from routes.ingest import recover_orphaned_tasks
            recover_orphaned_tasks()
        except Exception:
            _recovery_failure_service = service
            return {'status': 'down', 'ready': False, 'code': 'ingest_recovery_failed'}
        state = _probe_runtime_status()
        if state['ready'] and _recovery_failure_service is service:
            _recovery_failure_service = None
        return state
    return state
