"""Document-scoped vector publication over one admitted SQLite database.

HTTP authorization and provider calls remain at their explicit application
boundaries. This service receives server-authorized IDs, never SQL predicates.
"""
from __future__ import annotations

import copy
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path

from vector_store import VectorStore, _build_chroma_metadata
from vector_runtime import connect
from services.document_catalog import DocumentCatalog, CatalogConflict, CatalogNotFound


class DocumentPublication:
    def __init__(self, store, asset_root, model_profile):
        self.store = store
        self.asset_root = Path(asset_root).resolve()
        self.asset_root.mkdir(parents=True, exist_ok=True)
        self.model_profile = dict(model_profile)
        if (type(self.model_profile.get('dimension')) is not int
                or self.model_profile['dimension'] < 1
                or not self.model_profile.get('model') or not self.model_profile.get('revision')):
            raise CatalogConflict('invalid_model_profile')
        if (self.model_profile['model'] != store.embedding_model
                or self.model_profile['dimension'] != store.embedding_dim):
            raise CatalogConflict('model_profile_mismatch')

    @contextmanager
    def catalog(self):
        connection = connect(self.store.path)
        connection.isolation_level = None
        try:
            yield DocumentCatalog(connection, self.asset_root)
        finally:
            connection.close()

    def documents(self, legacy=()):
        with self.catalog() as catalog:
            return catalog.visible_documents(legacy)

    def publish(self, task_id, document_id, identity, chunks, embeddings, *, assets,
                expected_revision=None, authorize=None):
        # The hash is a namespace, not an identity inferred from source filenames.
        collection = 'document_' + hashlib.sha256(json.dumps([document_id, task_id], separators=(',', ':')).encode()).hexdigest()
        with self.catalog() as catalog:
            receipt = catalog.prepare(task_id, document_id, identity,
                                      expected_revision=expected_revision,
                                      model_profile=self.model_profile, assets=assets,
                                      collection_name=collection)
            if receipt['status'] == 'done':
                if authorize is not None:
                    authorize(catalog.get_active(document_id))
                return receipt['result']
            if receipt['status'] != 'prepared':
                raise CatalogConflict(receipt['error_code'] or 'task_not_prepared')
            revision = receipt['revision']
            trusted = catalog._document(document_id)
        try:
            if len(chunks) != len(embeddings):
                raise CatalogConflict('length_mismatch')
            if any(len(vector) != self.model_profile['dimension'] for vector in embeddings):
                raise CatalogConflict('invalid_dimension')
            target = VectorStore(collection_name=collection, persist_dir=self.store.persist_dir,
                                 embedding_dim=self.model_profile['dimension'],
                                 embedding_model=self.store.embedding_model,
                                 synthetic_config=self.store.synthetic_config)
            metadata = []
            ids = []
            for chunk in chunks:
                values = _build_chroma_metadata(chunk)
                if chunk.table_json is not None:
                    values['table_json'] = json.dumps(chunk.table_json, ensure_ascii=False, allow_nan=False)
                values = {key: '' if value is None else value for key, value in values.items()}
                values.update(document_id=document_id, document_version=revision,
                              owner_id=trusted.get('owner_id', ''), org_id=trusted.get('org_id') or '',
                              project_id=trusted.get('project_id') or '', source_file=identity.get('filename', trusted.get('filename', '')),
                              local_chunk_id=chunk.chunk_id)
                metadata.append(values)
                ids.append(f'{document_id}:{revision}:{chunk.chunk_id}')
            if chunks:
                target._collection.add(ids=ids, embeddings=embeddings, documents=[chunk.text for chunk in chunks], metadatas=metadata)
            with self.catalog() as catalog:
                def validate_vectors(connection, current_receipt):
                    count = connection.execute('SELECT COUNT(*) FROM records WHERE collection=?', (collection,)).fetchone()[0]
                    if count != len(chunks):
                        raise CatalogConflict('publication_integrity')
                return catalog.commit(task_id, authorize=authorize, publish_vectors=validate_vectors)
        except BaseException:
            with self.catalog() as catalog:
                with catalog._write():
                    catalog.connection.execute("UPDATE document_tasks SET status='failed',error_code='publication_failed' WHERE task_id=? AND status='prepared'", (task_id,))
            raise

    @contextmanager
    def read_snapshot(self, *, allowed_document_ids, authorize=None, page_size=256):
        from services.scoped_vector_snapshot import ScopedVectorSnapshot
        if type(allowed_document_ids) not in (set, frozenset):
            raise CatalogConflict('invalid_document_scope')
        with self.catalog() as catalog:
            with catalog.read_snapshot(document_ids=allowed_document_ids) as snapshot:
                for document in snapshot.documents:
                    if document['model_profile'] != self.model_profile:
                        raise CatalogConflict('model_profile_mismatch')
                    if authorize is not None:
                        authorize(document)
                collections = tuple(doc['collection_name'] for doc in snapshot.documents)
                with self.store.read_snapshot_connection(snapshot.connection, collection_names=collections):
                    yield ScopedVectorSnapshot(self.store, snapshot, page_size=page_size, asset_root=self.asset_root)

    def validate_snapshot(self, versions, *, authorize=None):
        # This method opens a new connection and transaction after generation.
        with self.catalog() as catalog:
            with catalog.read_snapshot(document_ids=set(versions)) as snapshot:
                current = {doc['document_id']: doc for doc in snapshot.documents}
                for document_id, revision in versions.items():
                    document = current.get(document_id)
                    if document is None:
                        raise CatalogNotFound()
                    if authorize is not None:
                        authorize(document)
                    if document['active_revision'] != revision:
                        raise CatalogConflict('revision_conflict')

    def search(self, query_vector, *, allowed_document_ids, top_k=20, where=None,
               text_char_limit=None, metadata_keys=None, authorize=None):
        if type(allowed_document_ids) not in (set, frozenset):
            raise CatalogConflict('invalid_document_scope')
        with self.catalog() as catalog:
            with catalog.read_snapshot(document_ids=allowed_document_ids) as snapshot:
                if not snapshot.documents:
                    return []
                for document in snapshot.documents:
                    if document['model_profile'] != self.model_profile:
                        raise CatalogConflict('model_profile_mismatch')
                    if authorize is not None:
                        authorize(document)
                collections = tuple(doc['collection_name'] for doc in snapshot.documents)
                # The adapter uses one unrounded-score heap across all collections.
                with self.store.read_snapshot_connection(snapshot.connection, collection_names=collections):
                    result = self.store.search(query_vector, top_k=top_k, where=where,
                                               text_char_limit=text_char_limit, metadata_keys=metadata_keys)
                versions = {doc['document_id']: doc['active_revision'] for doc in snapshot.documents}
            # The old transaction and its asset pins have closed. Re-authorize from
            # current directory/tenant state, never from the preceding snapshot.
            for document_id, revision in versions.items():
                current = catalog.get_active(document_id)
                if authorize is not None:
                    authorize(current)
                if current['active_revision'] != revision:
                    raise CatalogConflict('revision_conflict')
            return result

    def delete(self, document_id, *, legacy=None):
        with self.catalog() as catalog:
            def revoke_vectors(connection, target):
                connection.execute('DELETE FROM records WHERE collection IN (SELECT collection_name FROM document_revisions WHERE document_id=?)', (target,))
            catalog.delete(document_id, legacy=legacy, revoke_vectors=revoke_vectors)
            catalog.cleanup(document_id)
            return catalog.cleanup_status(document_id)
