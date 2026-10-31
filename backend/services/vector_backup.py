"""Coherent publication snapshots and isolated, validated restore activation.

The database read transaction is fixed while a writer registers kernel-owned
pins for every revision, including prepared/inactive/deleted revisions. Cleanup
therefore cannot remove any asset in that transaction until copying completes.
Restores remove process-local pin leases; receipts and cleanup rows survive.
"""
from __future__ import annotations

from contextlib import ExitStack, closing, contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import tempfile
from uuid import uuid4

from services.document_catalog import DocumentCatalog
from sqlite_vector_store import validate_schema
from vector_runtime import connect, require_admission


def _digest(path):
    digest = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
            size += len(block)
    return {'sha256': digest.hexdigest(), 'size': size}


def _path(root, name):
    if (type(name) is not str or not name or '\\' in name or ':' in name or '\x00' in name
            or PureWindowsPath(name).drive or PurePosixPath(name).is_absolute()
            or any(part in {'', '.', '..', '.catalog-locks'} for part in name.split('/'))):
        raise ValueError('unsafe_backup_asset')
    result = root / name
    for candidate in (result, *result.parents):
        if candidate == root:
            break
        if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda: False)():
            raise ValueError('unsafe_backup_asset')
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError('unsafe_backup_asset')
    return result


class PublicationBackup:
    def __init__(self, service):
        self.service = service

    @contextmanager
    def _snapshot(self):
        # A separate writer is necessary: SQLite backup on a source connection
        # with an uncommitted write transaction cannot finish. The reader fixes
        # its WAL snapshot before the writer commits the pin registrations.
        with ExitStack() as stack:
            guard = stack.enter_context(closing(connect(self.service.store.path)))
            guard.isolation_level = None
            reader = stack.enter_context(closing(connect(self.service.store.path, True)))
            catalog = DocumentCatalog(guard, self.service.asset_root)
            tokens = []
            try:
                with catalog._write():
                    validate_schema(guard)
                    rows = guard.execute('SELECT document_id,revision FROM document_revisions ORDER BY document_id,revision').fetchall()
                    for document_id, revision in rows:
                        token = uuid4().hex
                        stack.enter_context(catalog._pin_lock(token).acquire(timeout=5))
                        guard.execute('INSERT INTO document_pins VALUES (?,?,?,?)', (token, document_id, revision, os.getpid()))
                        tokens.append(token)
                    reader.execute('BEGIN')
                    reader.execute('SELECT generation FROM document_catalog_state').fetchone()
                yield reader
            finally:
                reader.rollback()
                if tokens:
                    with catalog._write():
                        guard.executemany('DELETE FROM document_pins WHERE token=?', [(token,) for token in tokens])

    def _validate_catalog(self, connection):
        """Validate durable relationships missing from the legacy SQL schema."""
        def invalid():
            raise ValueError('backup_catalog_integrity')
        documents = {}
        for identifier, identity, active, deleted in connection.execute(
                'SELECT document_id,identity_json,active_revision,deleted FROM documents'):
            identity = json.loads(identity)
            if (type(identity) is not dict or not identity.get('owner_id')
                    or deleted not in (0, 1)
                    or (active is not None and (type(active) is not int or active < 1))):
                invalid()
            documents[identifier] = (active, deleted)
        revisions = {}
        for document, revision, task, state, assets, model, collection, metadata in connection.execute(
                'SELECT * FROM document_revisions'):
            if (document not in documents or type(revision) is not int or revision < 1
                    or json.loads(model) != self.service.model_profile
                    or type(json.loads(metadata)) is not dict):
                invalid()
            revisions[document, revision] = (task, state, json.loads(assets), collection)
        for document, (active, deleted) in documents.items():
            if active is not None:
                revision = revisions.get((document, active))
                if revision is None or revision[1] != 'committed':
                    invalid()
                collection = connection.execute('SELECT dimension FROM collections WHERE name=?', (revision[3],)).fetchone()
                if collection != (self.service.model_profile['dimension'],):
                    invalid()
        tasks = {}
        for task, document, expected, revision, status, error, result, request_hash in connection.execute(
                'SELECT * FROM document_tasks'):
            published = revisions.get((document, revision))
            if (published is None or published[0] != task
                    or status not in {'prepared', 'done', 'failed'}
                    or (status == 'done') != (published[1] == 'committed')):
                invalid()
            if status == 'done':
                result = json.loads(result) if result is not None else None
                if (type(result) is not dict or result.get('document_id') != document
                        or result.get('active_revision') != revision
                        or result.get('assets') != published[2]
                        or result.get('collection_name') != published[3]
                        or result.get('model_profile') != self.service.model_profile):
                    invalid()
            tasks[task] = True
        if any(revision[0] not in tasks for revision in revisions.values()):
            invalid()
        for document, revision, assets, status, error, attempts in connection.execute('SELECT * FROM document_cleanup'):
            published = revisions.get((document, revision))
            if (published is None or not documents[document][1]
                    or json.loads(assets) != published[2]
                    or status not in {'pending', 'blocked', 'done'}
                    or type(attempts) is not int or attempts < 0):
                invalid()

    def _references(self, connection):
        assets = {}
        for encoded, deleted, cleanup in connection.execute(
                'SELECT r.assets_json,d.deleted,c.status FROM document_revisions r '
                'JOIN documents d ON d.document_id=r.document_id LEFT JOIN document_cleanup c '
                'ON c.document_id=r.document_id AND c.revision=r.revision'):
            values = json.loads(encoded)
            if type(values) is not list:
                raise ValueError('invalid_backup_manifest')
            for asset in values:
                if type(asset) is not dict:
                    raise ValueError('invalid_backup_manifest')
                name, sha = asset.get('path'), asset.get('sha256')
                _path(Path('.').resolve(), name)
                if (type(sha) is not str or len(sha) != 64
                        or any(c not in '0123456789abcdef' for c in sha)):
                    raise ValueError('invalid_backup_manifest')
                required = not deleted or cleanup not in {'done', 'pending', 'blocked'}
                if name in assets and assets[name]['sha256'] != sha:
                    raise ValueError('conflicting_backup_asset')
                old = assets.get(name, {})
                assets[name] = {'path': name, 'sha256': sha, 'required': required or old.get('required', False)}
        return [assets[name] for name in sorted(assets)]

    def _copy_asset(self, source, target, expected):
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as inp, target.open('xb') as out:
            shutil.copyfileobj(inp, out, 65536)
            out.flush()
            os.fsync(out.fileno())
        actual = _digest(target)
        if actual['sha256'] != expected:
            raise ValueError('backup_asset_integrity')
        return actual['size']

    def create(self, destination):
        destination = Path(destination).absolute()
        if destination.exists():
            raise FileExistsError('backup_target_exists')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.publication-', dir=destination.parent) as temporary:
            stage = Path(temporary) / 'sealed'
            (stage / 'database').mkdir(parents=True)
            (stage / 'assets').mkdir()
            database = stage / 'database' / 'vectors.sqlite'
            with self._snapshot() as reader:
                references = self._references(reader)
                with closing(connect(database)) as target:
                    reader.backup(target, pages=256)
                    validate_schema(target)
                    if target.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                        raise ValueError('backup_database_integrity')
                assets = []
                for reference in references:
                    source = _path(self.service.asset_root, reference['path'])
                    asset = {key: reference[key] for key in ('path', 'sha256')}
                    asset['present'] = source.exists()
                    if asset['present']:
                        asset['size'] = self._copy_asset(source, _path(stage / 'assets', asset['path']), asset['sha256'])
                    elif reference['required']:
                        raise ValueError('backup_asset_missing')
                    assets.append(asset)
                manifest = {'format': 1, 'database': _digest(database), 'assets': assets,
                            'source_asset_root': str(self.service.asset_root),
                            'model_profile': self.service.model_profile}
                (stage / 'publication.json').write_text(json.dumps(manifest, ensure_ascii=False, allow_nan=False, sort_keys=True), encoding='utf-8')
                # Verify the sealed bytes, not only the live originals.
                self.verify(stage)
                if destination.exists():
                    raise FileExistsError('backup_target_exists')
                stage.rename(destination)
        return manifest

    @contextmanager
    def _sealed_database(self, database, expected):
        # Hash and query the same private main-file bytes. Opening the archive
        # directly would apply adjacent, unregistered WAL/journal content, and
        # hashing it before opening would also leave a replacement race.
        with tempfile.TemporaryDirectory(prefix='.publication-verify-') as temporary:
            sealed = Path(temporary) / 'vectors.sqlite'
            with database.open('rb') as source, sealed.open('xb') as target:
                shutil.copyfileobj(source, target, 65536)
            if _digest(sealed) != expected:
                raise ValueError('backup_database_integrity')
            with closing(connect(sealed, True)) as connection:
                yield connection

    def verify(self, snapshot):
        snapshot = Path(snapshot).resolve()
        if snapshot.is_symlink() or not snapshot.is_dir():
            raise ValueError('invalid_backup_manifest')
        manifest_file = _path(snapshot, 'publication.json')
        manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
        if (manifest.get('format') != 1 or type(manifest.get('assets')) is not list
                or manifest.get('model_profile') != self.service.model_profile
                or type(manifest.get('source_asset_root')) is not str
                or not Path(manifest['source_asset_root']).is_absolute()):
            raise ValueError('invalid_backup_manifest')
        database = _path(snapshot, 'database/vectors.sqlite')
        with self._sealed_database(database, manifest.get('database')) as connection:
            validate_schema(connection)
            if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('backup_database_integrity')
            self._validate_catalog(connection)
            references = self._references(connection)
            # The fixed DB, never a mutable outside directory, is authoritative.
            expected = {asset['path']: asset for asset in references}
            actual = {}
            for asset in manifest['assets']:
                if type(asset) is not dict or type(asset.get('present')) is not bool:
                    raise ValueError('invalid_backup_manifest')
                name = asset.get('path')
                path = _path(snapshot / 'assets', name)
                if name in actual or name not in expected or asset.get('sha256') != expected[name]['sha256']:
                    raise ValueError('invalid_backup_manifest')
                if asset['present']:
                    if _digest(path) != {'sha256': asset['sha256'], 'size': asset.get('size')}:
                        raise ValueError('backup_asset_integrity')
                elif expected[name]['required'] or path.exists():
                    raise ValueError('backup_asset_missing')
                actual[name] = asset
            if set(actual) != set(expected):
                raise ValueError('invalid_backup_manifest')
        return manifest

    def restore(self, snapshot, target):
        target = Path(target).absolute()
        if target.exists() or target.is_symlink():
            raise FileExistsError('restore_target_exists')
        # Preserve the existing compatibility gate; backups cannot grant admission.
        require_admission(target, self.service.store.integration_config)
        manifest = self.verify(snapshot)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.restore-', dir=target.parent) as temporary:
            stage = Path(temporary) / 'ready'
            (stage / 'database').mkdir(parents=True)
            (stage / 'assets').mkdir()
            snapshot = Path(snapshot).resolve()
            self._copy_asset(_path(snapshot, 'database/vectors.sqlite'), stage / 'database' / 'vectors.sqlite', manifest['database']['sha256'])
            for asset in manifest['assets']:
                if asset['present']:
                    self._copy_asset(_path(snapshot / 'assets', asset['path']), _path(stage / 'assets', asset['path']), asset['sha256'])
            with closing(connect(stage / 'database' / 'vectors.sqlite')) as connection:
                # OS lock ownership cannot survive restore. Keep durable cleanup,
                # tombstones and task receipts, discard only transient pin leases.
                connection.execute('DELETE FROM document_pins')
                old_root = Path(manifest['source_asset_root'])
                new_root = target / 'assets'
                def relocate(value):
                    if type(value) is dict:
                        return {key: relocate(item) for key, item in value.items()}
                    if type(value) is list:
                        return [relocate(item) for item in value]
                    if type(value) is str:
                        path = Path(value)
                        if path.is_absolute() and path.is_relative_to(old_root):
                            return str(new_root / path.relative_to(old_root))
                    return value
                for table, key_columns, field in (
                        ('documents', ['document_id'], 'identity_json'),
                        ('document_revisions', ['document_id', 'revision'], 'metadata_json'),
                        ('document_tasks', ['task_id'], 'result_json')):
                    for row in connection.execute(f"SELECT {','.join(key_columns)},{field} FROM {table}").fetchall():
                        if row[-1] is not None:
                            value = json.dumps(relocate(json.loads(row[-1])), ensure_ascii=False, allow_nan=False)
                            predicate = ' AND '.join(key + '=?' for key in key_columns)
                            connection.execute(f'UPDATE {table} SET {field}=? WHERE {predicate}', (value, *row[:-1]))
                connection.commit()
                validate_schema(connection)
                if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError('restore_database_integrity')
                self._validate_catalog(connection)
            if target.exists():
                raise FileExistsError('restore_target_exists')
            stage.rename(target)
        return target
