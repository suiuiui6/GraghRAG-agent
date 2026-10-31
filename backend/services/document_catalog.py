"""Transactional document publication directory on the vector DB connection.

The caller owns runtime admission, the connection, authorization and embedding.
This service never chooses a runtime or reads an application-global data path.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock, Timeout


_SAFE_CODES = frozenset({'publication_failed', 'invalid_identifier', 'invalid_identity', 'invalid_manifest',
                        'invalid_model_profile', 'invalid_document_scope', 'model_profile_mismatch',
                        'revision_conflict', 'task_identity_conflict', 'task_not_prepared', 'transaction_active',
                        'catalog_integrity', 'migration_required', 'unsafe_asset', 'asset_integrity',
                        'asset_still_referenced', 'not_deleted', 'publication_integrity', 'invalid_dimension',
                        'length_mismatch', 'ingest_interrupted'})


class CatalogConflict(ValueError):
    def __init__(self, code):
        self.code = code if code in _SAFE_CODES else 'publication_failed'
        super().__init__(self.code)


class CatalogNotFound(LookupError):
    def __init__(self, code='document_not_found'):
        self.code = code if code in {'document_not_found', 'task_not_found'} else 'document_not_found'
        super().__init__(self.code)


@dataclass(frozen=True)
class CatalogSnapshot:
    connection: object
    documents: list[dict]
    generation: int


def _identifier(value):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9_-]+', value) is None:
        raise CatalogConflict('invalid_identifier')
    return value


def _encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':'))


class DocumentCatalog:
    def __init__(self, connection, asset_root):
        self.connection = connection
        self.asset_root = Path(asset_root).resolve()
        self.asset_root.mkdir(parents=True, exist_ok=True)
        self.lock_root = self.asset_root / '.catalog-locks'
        self.lock_root.mkdir(exist_ok=True)

    @contextmanager
    def _write(self):
        if self.connection.in_transaction:
            raise CatalogConflict('transaction_active')
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def _bump_generation(self):
        self.connection.execute('UPDATE document_catalog_state SET generation=generation+1 WHERE id=1')

    def generation(self):
        return self.connection.execute('SELECT generation FROM document_catalog_state WHERE id=1').fetchone()[0]

    def _document(self, document_id):
        row = self.connection.execute('SELECT identity_json,active_revision,deleted FROM documents WHERE document_id=?', (document_id,)).fetchone()
        if row is None:
            return None
        return {**json.loads(row[0]), 'document_id': document_id, 'active_revision': row[1], '_deleted': bool(row[2])}

    def get_active(self, document_id):
        doc = self._document(document_id)
        if not doc or doc['_deleted'] or doc['active_revision'] is None:
            raise CatalogNotFound('document_not_found')
        doc.pop('_deleted')
        revision = self.connection.execute('SELECT assets_json,model_json,collection_name,metadata_json FROM document_revisions WHERE document_id=? AND revision=? AND state=?', (document_id, doc['active_revision'], 'committed')).fetchone()
        if revision is None:
            raise CatalogConflict('catalog_integrity')
        return {**doc, **json.loads(revision[3]),
                **{key: doc[key] for key in ('owner_id', 'org_id', 'project_id', 'document_id', 'active_revision') if key in doc},
                'assets': json.loads(revision[0]), 'model_profile': json.loads(revision[1]), 'collection_name': revision[2]}

    def visible_documents(self, legacy=()):
        rows = self.connection.execute('SELECT document_id FROM documents ORDER BY document_id').fetchall()
        known = {row[0] for row in rows}
        result = []
        for document_id, in rows:
            doc = self._document(document_id)
            if not doc['_deleted'] and doc['active_revision'] is not None:
                result.append(self.get_active(document_id))
        for doc in legacy:
            if doc.get('document_id') not in known:
                result.append({**doc, 'active_revision': None})
        return result

    @staticmethod
    def require_revision(document, expected):
        if document.get('active_revision') is None:
            raise CatalogConflict('migration_required')
        if type(expected) is not int or expected < 1 or document['active_revision'] != expected:
            raise CatalogConflict('revision_conflict')

    def _asset_path(self, asset):
        value = asset.get('path')
        if type(value) is not str or not value or '\x00' in value:
            raise CatalogConflict('unsafe_asset')
        relative = Path(value)
        if relative.is_absolute() or '..' in relative.parts:
            raise CatalogConflict('unsafe_asset')
        path = self.asset_root / relative
        for candidate in (path, *path.parents):
            if candidate == self.asset_root:
                break
            if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda: False)():
                raise CatalogConflict('unsafe_asset')
        if path.resolve() == self.asset_root or not path.resolve().is_relative_to(self.asset_root):
            raise CatalogConflict('unsafe_asset')
        return path

    def _verify_assets(self, assets):
        for asset in assets:
            path = self._asset_path(asset)
            digest = hashlib.sha256()
            try:
                with path.open('rb') as source:
                    while block := source.read(65536):
                        digest.update(block)
            except OSError as exc:
                raise CatalogConflict('asset_integrity') from exc
            if digest.hexdigest() != asset.get('sha256'):
                raise CatalogConflict('asset_integrity')

    def prepare(self, task_id, document_id, identity, *, expected_revision=None,
                model_profile, assets, collection_name):
        _identifier(task_id)
        _identifier(document_id)
        if type(identity) is not dict or not identity.get('owner_id'):
            raise CatalogConflict('invalid_identity')
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 1):
            raise CatalogConflict('revision_conflict')
        if type(assets) is not list or not assets or type(model_profile) is not dict:
            raise CatalogConflict('invalid_manifest')
        for asset in assets:
            self._asset_path(asset)
        request_hash = hashlib.sha256(_encode([document_id, expected_revision, identity, assets,
                                              model_profile, collection_name]).encode('utf-8')).hexdigest()
        with self._write():
            receipt = self.task_receipt(task_id)
            if receipt:
                if receipt['request_hash'] != request_hash:
                    raise CatalogConflict('task_identity_conflict')
                return receipt
            doc = self._document(document_id)
            if doc is None:
                if expected_revision is not None:
                    raise CatalogConflict('migration_required')
                trusted = {key: value for key, value in identity.items() if key not in {'document_id', 'active_revision', '_deleted'}}
                self.connection.execute('INSERT INTO documents(document_id,identity_json) VALUES (?,?)', (document_id, _encode(trusted)))
            else:
                if doc['_deleted']:
                    raise CatalogNotFound('document_not_found')
                if doc['active_revision'] is None or expected_revision != doc['active_revision']:
                    raise CatalogConflict('revision_conflict')
            revision = self.connection.execute('SELECT COALESCE(MAX(revision),0)+1 FROM document_revisions WHERE document_id=?', (document_id,)).fetchone()[0]
            metadata_fields = {'filename', 'filepath', 'kg_path', 'status', 'kg_nodes', 'kg_edges',
                               'pages', 'indexed_at', 'file_size_bytes', 'content_hash', 'build_config_hash'}
            metadata = {key: value for key, value in identity.items() if key in metadata_fields}
            self.connection.execute('INSERT INTO document_revisions VALUES (?,?,?,?,?,?,?,?)', (document_id, revision, task_id, 'prepared', _encode(assets), _encode(model_profile), collection_name, _encode(metadata)))
            self.connection.execute('INSERT INTO document_tasks VALUES (?,?,?,?,?,NULL,NULL,?)', (task_id, document_id, expected_revision, revision, 'prepared', request_hash))
        return self.task_receipt(task_id)

    def task_receipt(self, task_id):
        row = self.connection.execute('SELECT document_id,expected_revision,revision,status,error_code,result_json,request_hash FROM document_tasks WHERE task_id=?', (task_id,)).fetchone()
        if row is None:
            return None
        return dict(task_id=task_id, document_id=row[0], expected_revision=row[1], revision=row[2], status=row[3], error_code=row[4], result=json.loads(row[5]) if row[5] else None, request_hash=row[6])

    def commit(self, task_id, *, authorize=None, publish_vectors=None):
        try:
            with self._write():
                receipt = self.task_receipt(task_id)
                if not receipt:
                    raise CatalogNotFound('task_not_found')
                if receipt['status'] == 'done':
                    return receipt['result']
                if receipt['status'] != 'prepared':
                    raise CatalogConflict(receipt['error_code'] or 'task_not_prepared')
                doc = self._document(receipt['document_id'])
                if doc['_deleted']:
                    raise CatalogNotFound('document_not_found')
                if doc['active_revision'] != receipt['expected_revision']:
                    raise CatalogConflict('revision_conflict')
                if authorize is not None:
                    authorize({key: value for key, value in doc.items() if key != '_deleted'})
                revision = self.connection.execute('SELECT assets_json FROM document_revisions WHERE document_id=? AND revision=?', (receipt['document_id'], receipt['revision'])).fetchone()
                self._verify_assets(json.loads(revision[0]))
                if publish_vectors is not None:
                    publish_vectors(self.connection, receipt)
                self.connection.execute("UPDATE document_revisions SET state='committed' WHERE task_id=?", (task_id,))
                self.connection.execute('UPDATE documents SET active_revision=? WHERE document_id=?', (receipt['revision'], receipt['document_id']))
                self._bump_generation()
                result = self.get_active(receipt['document_id'])
                self.connection.execute("UPDATE document_tasks SET status='done',result_json=? WHERE task_id=?", (_encode(result), task_id))
                return result
        except (CatalogConflict, CatalogNotFound) as exc:
            # Persist a safe terminal receipt only after the publishing transaction rolls back.
            with self._write():
                self.connection.execute("UPDATE document_tasks SET status='failed',error_code=? WHERE task_id=? AND status='prepared'", (str(exc), task_id))
            raise

    def revisions(self, document_id):
        return [{'revision': row[0], 'state': row[1], 'collection_name': row[2]} for row in self.connection.execute('SELECT revision,state,collection_name FROM document_revisions WHERE document_id=? ORDER BY revision', (document_id,))]

    def delete(self, document_id, *, legacy=None, revoke_vectors=None):
        _identifier(document_id)
        with self._write():
            doc = self._document(document_id)
            if doc is None:
                if legacy is None or legacy.get('document_id') != document_id:
                    raise CatalogNotFound('document_not_found')
                self.connection.execute('INSERT INTO documents(document_id,identity_json,deleted) VALUES (?,?,1)', (document_id, _encode(legacy)))
            else:
                if doc['_deleted']:
                    raise CatalogNotFound('document_not_found')
                self.connection.execute('UPDATE documents SET deleted=1 WHERE document_id=?', (document_id,))
            for revision, assets_json in self.connection.execute('SELECT revision,assets_json FROM document_revisions WHERE document_id=?', (document_id,)).fetchall():
                status = 'pending'
                try:
                    assets = json.loads(assets_json)
                    if type(assets) is not list or any(type(asset) is not dict for asset in assets):
                        raise CatalogConflict('unsafe_asset')
                    for asset in assets:
                        self._asset_path(asset)
                except (CatalogConflict, ValueError, TypeError):
                    status = 'blocked'
                self.connection.execute('INSERT OR REPLACE INTO document_cleanup(document_id,revision,assets_json,status,error_code) VALUES (?,?,?,?,?)', (document_id, revision, assets_json, status, 'unsafe_asset' if status == 'blocked' else None))
            if revoke_vectors is not None:
                revoke_vectors(self.connection, document_id)
            self._bump_generation()
        return self.cleanup_status(document_id)

    def cleanup_status(self, document_id):
        statuses = [row[0] for row in self.connection.execute('SELECT status FROM document_cleanup WHERE document_id=?', (document_id,))]
        status = 'blocked' if 'blocked' in statuses else 'pending' if 'pending' in statuses else 'done'
        return {'document_id': document_id, 'status': 'deleted', 'cleanup_status': status, 'cleanup_pending': status != 'done'}

    def _revision_lock(self, document_id, revision):
        _identifier(document_id)
        return FileLock(str(self.lock_root / f'{document_id}_{revision}.lock'))

    def _pin_lock(self, token):
        _identifier(token)
        return FileLock(str(self.lock_root / ('pin_' + token + '.lock')))

    @contextmanager
    def pin(self, document_id, revision):
        token = uuid.uuid4().hex
        # Each reader owns a distinct kernel lock, allowing concurrent readers.
        # Pin registration and cleanup's pin inspection serialize in SQLite.
        with self._pin_lock(token).acquire(timeout=5):
            with self._write():
                doc = self._document(document_id)
                if not doc or doc['_deleted'] or self.connection.execute("SELECT 1 FROM document_revisions WHERE document_id=? AND revision=? AND state='committed'", (document_id, revision)).fetchone() is None:
                    raise CatalogNotFound('document_not_found')
                self.connection.execute('INSERT INTO document_pins VALUES (?,?,?,?)', (token, document_id, revision, os.getpid()))
            try:
                yield token
            finally:
                with self._write():
                    self.connection.execute('DELETE FROM document_pins WHERE token=?', (token,))

    def cleanup(self, document_id):
        _identifier(document_id)
        doc = self._document(document_id)
        if doc is None or not doc['_deleted']:
            raise CatalogConflict('not_deleted')
        rows = self.connection.execute("SELECT revision,assets_json FROM document_cleanup WHERE document_id=? AND status='pending'", (document_id,)).fetchall()
        for revision, assets_json in rows:
            lock = self._revision_lock(document_id, revision)
            try:
                lock.acquire(timeout=0)
            except Timeout:
                continue
            try:
                assets = json.loads(assets_json)
                try:
                    paths = [self._asset_path(asset) for asset in assets]
                    with ExitStack() as stale_pin_locks, self._write():
                        # The write transaction prevents a new prepared reference
                        # appearing between this check and unlink. Asset locks also
                        # protect readers of deleted/shared revisions and survive
                        # process crashes through kernel lock ownership.
                        references = self.connection.execute("SELECT r.document_id,r.revision,r.assets_json,r.state,d.deleted FROM document_revisions r JOIN documents d ON d.document_id=r.document_id").fetchall()
                        for ref_doc, ref_revision, ref_assets, ref_state, ref_deleted in references:
                            if not any(self._asset_path(asset) in paths for asset in json.loads(ref_assets)):
                                continue
                            if ((ref_doc, ref_revision) != (document_id, revision)
                                    and not ref_deleted and ref_state in {'prepared', 'committed'}):
                                raise CatalogConflict('asset_still_referenced')
                            pins = self.connection.execute('SELECT token FROM document_pins WHERE document_id=? AND revision=?', (ref_doc, ref_revision)).fetchall()
                            for token, in pins:
                                # A live reader's kernel lock cannot be acquired.
                                # Only genuinely abandoned pins are removed.
                                stale_pin_locks.enter_context(self._pin_lock(token).acquire(timeout=0))
                                self.connection.execute('DELETE FROM document_pins WHERE token=?', (token,))
                        for path in paths:
                            path.unlink(missing_ok=True)
                        self.connection.execute("UPDATE document_cleanup SET status='done',attempts=attempts+1,error_code=NULL WHERE document_id=? AND revision=?", (document_id, revision))
                        self.connection.execute('DELETE FROM document_pins WHERE document_id=? AND revision=?', (document_id, revision))
                except (OSError, CatalogConflict, Timeout):
                    with self._write():
                        self.connection.execute('UPDATE document_cleanup SET attempts=attempts+1,error_code=? WHERE document_id=? AND revision=?', ('cleanup_failed', document_id, revision))
                    continue
            finally:
                lock.release()
        return self.cleanup_status(document_id)

    @contextmanager
    def read_snapshot(self, *, document_ids=None):
        if self.connection.in_transaction:
            raise CatalogConflict('transaction_active')
        def selected_documents():
            documents = self.visible_documents()
            return documents if document_ids is None else [doc for doc in documents if doc['document_id'] in document_ids]
        documents = selected_documents()
        with ExitStack() as stack:
            for doc in sorted(documents, key=lambda item: item['document_id']):
                stack.enter_context(self.pin(doc['document_id'], doc['active_revision']))
            self.connection.execute('BEGIN')
            try:
                current = selected_documents()
                if current != documents:
                    raise CatalogConflict('revision_conflict')
                yield CatalogSnapshot(self.connection, current, self.generation())
            finally:
                self.connection.rollback()
