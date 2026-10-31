"""Coherent online SQLite publication backups, real disk and connections."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest
from doc_processor import Chunk
from vector_store import VectorStore
from vector_runtime import SyntheticStorageConfig, connect
from services.document_publication import DocumentPublication
from services.backup import BackupManager

PROFILE = {'model': 'backup-fixed', 'revision': 'sha', 'dimension': 2, 'normalize': True}

@pytest.fixture
def service(monkeypatch):
    with SyntheticStorageConfig.create() as config:
        with monkeypatch.context() as isolated:
            isolated.chdir(config.root)
            store = VectorStore(persist_dir=str(config.root / 'database'), embedding_dim=2, embedding_model=PROFILE['model'], synthetic_config=config)
            yield DocumentPublication(store, config.root / 'assets', PROFILE)

def publish(service, task='one', expected=None, document='doc', text='v1'):
    asset = service.asset_root / (task + '.txt')
    asset.write_text(text)
    return service.publish(task, document, {'owner_id': 'owner', 'filename': 'same.txt'},
                           [Chunk('c1', text, 'text')], [[1., 0.]], expected_revision=expected,
                           assets=[{'path': asset.name, 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}])

def backup_type():
    from services.vector_backup import PublicationBackup
    return PublicationBackup

def test_snapshot_retains_inactive_prepared_receipts_tombstone_and_wal(service):
    publish(service)
    publish(service, 'two', 1, text='v2')
    with service.catalog() as catalog:
        catalog.delete('legacy', legacy={'document_id': 'legacy', 'owner_id': 'owner'})
        asset = service.asset_root / 'prepared.txt'
        asset.write_text('prepared')
        catalog.prepare('prepared', 'doc', {'owner_id': 'owner'}, expected_revision=2,
                        model_profile=PROFILE, collection_name='future',
                        assets=[{'path': asset.name, 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}])
    root = service.asset_root.parent
    destination = root / 'backup'
    backup_type()(service).create(destination)
    assert not (destination / 'database' / 'vectors.sqlite-wal').exists()
    assert not (destination / 'database' / 'vectors.sqlite-shm').exists()
    restored = backup_type()(service).restore(destination, root / 'restored')
    store = VectorStore(persist_dir=str(restored / 'database'), embedding_dim=2, embedding_model=PROFILE['model'], synthetic_config=service.store.synthetic_config)
    again = DocumentPublication(store, restored / 'assets', PROFILE)
    assert [r['text'] for r in again.search([1, 0], allowed_document_ids={'doc'})] == ['v2']
    assert {p.name for p in again.asset_root.glob('*.txt')} == {'one.txt', 'two.txt', 'prepared.txt'}
    with again.catalog() as catalog:
        assert catalog.task_receipt('one')['status'] == 'done'
        assert catalog.task_receipt('prepared')['status'] == 'prepared'
        assert not any(d['document_id'] == 'legacy' for d in catalog.visible_documents([{'document_id': 'legacy'}]))
        assert catalog.connection.execute('SELECT count(*) FROM document_pins').fetchone()[0] == 0

def test_backup_update_delete_cleanup_on_other_connection_keeps_fixed_snapshot(service, monkeypatch):
    publish(service)
    root = service.asset_root.parent
    cls = backup_type()
    copy_asset = cls._copy_asset
    seen = []
    def concurrent(self, source, target, expected):
        if not seen:
            seen.append(True)
            with ThreadPoolExecutor(max_workers=1) as executor:
                def mutate():
                    publish(service, 'two', 1, text='v2')
                    result = service.delete('doc')
                    assert result['cleanup_pending'] is True
                    assert (service.asset_root / 'one.txt').exists()
                executor.submit(mutate).result(timeout=10)
        return copy_asset(self, source, target, expected)
    monkeypatch.setattr(cls, '_copy_asset', concurrent)
    cls(service).create(root / 'backup')
    with service.catalog() as catalog:
        assert catalog.connection.execute('SELECT count(*) FROM document_pins').fetchone()[0] == 0
        assert catalog.cleanup('doc')['cleanup_pending'] is False
    restored = cls(service).restore(root / 'backup', root / 'restored')
    store = VectorStore(persist_dir=str(restored / 'database'), embedding_dim=2, embedding_model=PROFILE['model'], synthetic_config=service.store.synthetic_config)
    again = DocumentPublication(store, restored / 'assets', PROFILE)
    assert [r['text'] for r in again.search([1, 0], allowed_document_ids={'doc'})] == ['v1']
    assert not (restored / 'assets' / 'two.txt').exists()

def test_corrupt_asset_never_seals_success_and_releases_pins(service):
    publish(service)
    (service.asset_root / 'one.txt').write_text('corrupt')
    destination = service.asset_root.parent / 'backup'
    with pytest.raises(ValueError):
        backup_type()(service).create(destination)
    assert not destination.exists()
    with service.catalog() as catalog:
        assert catalog.connection.execute('SELECT count(*) FROM document_pins').fetchone()[0] == 0

@pytest.mark.parametrize('tamper', ['db', 'asset', 'path', 'schema'])
def test_restore_rejects_corruption_before_activation(service, tamper):
    publish(service)
    root = service.asset_root.parent
    destination = root / 'backup'
    cls = backup_type()
    cls(service).create(destination)
    manifest_path = destination / 'publication.json'
    manifest = json.loads(manifest_path.read_text())
    if tamper == 'db':
        with (destination / 'database' / 'vectors.sqlite').open('ab') as stream:
            stream.write(b'bad')
    elif tamper == 'asset':
        (destination / 'assets' / 'one.txt').write_text('bad')
    elif tamper == 'path':
        manifest['assets'][0]['path'] = '../outside.txt'
        manifest_path.write_text(json.dumps(manifest))
    else:
        connection = connect(destination / 'database' / 'vectors.sqlite')
        connection.execute('CREATE TABLE surprise(value TEXT)')
        connection.commit()
        connection.close()
        data = (destination / 'database' / 'vectors.sqlite').read_bytes()
        manifest['database'] = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(Exception):
        cls(service).restore(destination, root / 'restored')
    assert not (root / 'restored').exists()
    assert [r['text'] for r in service.search([1, 0], allowed_document_ids={'doc'})] == ['v1']

def test_restore_never_overwrites_existing_live_directory(service):
    publish(service)
    root = service.asset_root.parent
    cls = backup_type()
    cls(service).create(root / 'backup')
    before = service.store.path.read_bytes()
    with pytest.raises(FileExistsError):
        cls(service).restore(root / 'backup', service.store.path.parent)
    assert service.store.path.read_bytes() == before

def test_configured_manager_uses_online_publication_route(service):
    publish(service)
    manager = BackupManager(service.asset_root.parent / 'archives', publication=service)
    result = manager.create_backup()
    assert result.status == 'completed'
    assert manager.verify(result.backup_id)['valid'] is True
    assert manager.restore(result.backup_id).status == 'failed'  # explicit isolated target required
    target = service.asset_root.parent / 'isolated'
    manager.restore_target = target
    assert manager.restore(result.backup_id).status == 'completed'
    assert (target / 'database' / 'vectors.sqlite').is_file()

def test_deleted_pending_and_already_cleaned_state_roundtrip(service):
    publish(service)
    with service.catalog() as catalog:
        catalog.delete('doc')
        # Partial physical cleanup is legitimate; the durable pending receipt is
        # authoritative and retries must not resurrect the document.
        (service.asset_root / 'one.txt').unlink()
    root = service.asset_root.parent
    cls = backup_type()
    manifest = cls(service).create(root / 'backup')
    assert manifest['assets'] == [{'path': 'one.txt', 'sha256': hashlib.sha256(b'v1').hexdigest(), 'present': False}]
    restored = cls(service).restore(root / 'backup', root / 'restored')
    store = VectorStore(persist_dir=str(restored / 'database'), embedding_dim=2, embedding_model=PROFILE['model'], synthetic_config=service.store.synthetic_config)
    again = DocumentPublication(store, restored / 'assets', PROFILE)
    assert again.documents() == []
    with again.catalog() as catalog:
        assert catalog.cleanup_status('doc')['cleanup_pending'] is True
        assert catalog.cleanup('doc')['cleanup_pending'] is False
        assert catalog.task_receipt('one')['status'] == 'done'

@pytest.mark.parametrize('corruption', ['active', 'receipt', 'profile', 'cleanup'])
def test_inconsistent_catalog_cannot_be_sealed(service, corruption):
    publish(service)
    with service.catalog() as catalog:
        with catalog._write():
            if corruption == 'active':
                catalog.connection.execute('UPDATE documents SET active_revision=999')
            elif corruption == 'receipt':
                catalog.connection.execute("UPDATE document_tasks SET result_json='{}'")
            elif corruption == 'profile':
                catalog.connection.execute("UPDATE document_revisions SET model_json='{}'")
            else:
                catalog.connection.execute("INSERT INTO document_cleanup VALUES ('ghost',3,'[]','pending',NULL,0)")
    destination = service.asset_root.parent / 'backup'
    with pytest.raises(ValueError, match='catalog'):
        backup_type()(service).create(destination)
    assert not destination.exists()

def test_process_cleanup_and_new_prepare_do_not_change_snapshot(service, monkeypatch):
    import os
    import subprocess
    import sys
    publish(service)
    root = service.asset_root.parent
    cls = backup_type()
    original = cls._copy_asset
    first = []
    def copy_with_child(self, source, target, expected):
        if not first:
            first.append(True)
            code = '''
import hashlib,json,sys
from pathlib import Path
from vector_runtime import SyntheticStorageConfig
from vector_store import VectorStore
from services.document_publication import DocumentPublication
config=SyntheticStorageConfig.from_root(sys.argv[1])
store=VectorStore(persist_dir=str(config.root/'database'),embedding_dim=2,embedding_model='backup-fixed',synthetic_config=config)
service=DocumentPublication(store,config.root/'assets',json.loads(sys.argv[2]))
with service.catalog() as catalog:
    asset=service.asset_root/'new.txt'
    asset.write_text('not-in-snapshot')
    catalog.prepare('later','new_doc',{'owner_id':'owner'},model_profile=service.model_profile,collection_name='future',assets=[{'path':'new.txt','sha256':hashlib.sha256(asset.read_bytes()).hexdigest()}])
result=service.delete('doc')
assert result['cleanup_pending'] is True
assert (service.asset_root/'one.txt').is_file()
print('child-pinned')
'''
            env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
            child = subprocess.run([sys.executable, '-c', code, str(root), json.dumps(PROFILE)], env=env,
                                   capture_output=True, text=True, timeout=25)
            assert child.returncode == 0, child.stderr
            assert 'child-pinned' in child.stdout
        return original(self, source, target, expected)
    monkeypatch.setattr(cls, '_copy_asset', copy_with_child)
    cls(service).create(root / 'backup')
    manifest = json.loads((root / 'backup' / 'publication.json').read_text())
    assert [asset['path'] for asset in manifest['assets']] == ['one.txt']
    with service.catalog() as catalog:
        assert catalog.task_receipt('later')['status'] == 'prepared'
        assert catalog.cleanup('doc')['cleanup_pending'] is False
    cls(service).verify(root / 'backup')

def test_restore_relocates_registered_asset_metadata_and_success_receipt(service):
    asset = service.asset_root / 'original.txt'
    asset.write_text('original')
    service.publish('paths', 'doc', {'owner_id': 'owner', 'filepath': str(asset)},
                    [Chunk('c1', 'original', 'text')], [[1., 0.]],
                    assets=[{'path': 'original.txt', 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}])
    root = service.asset_root.parent
    cls = backup_type()
    cls(service).create(root / 'backup')
    restored = cls(service).restore(root / 'backup', root / 'restored')
    connection = connect(restored / 'database' / 'vectors.sqlite', True)
    try:
        path = str(restored / 'assets' / 'original.txt')
        identity = json.loads(connection.execute('SELECT identity_json FROM documents').fetchone()[0])
        result = json.loads(connection.execute('SELECT result_json FROM document_tasks').fetchone()[0])
        assert identity['filepath'] == path
        assert result['filepath'] == path
        assert Path(path).read_text() == 'original'
    finally:
        connection.close()

def test_lazy_manager_tracks_reconfigured_publication_without_raw_sqlite_copy(service, monkeypatch):
    from services import backup, document_runtime
    monkeypatch.setattr(backup, '_manager', None)
    monkeypatch.setattr(backup, 'BACKUP_DIR', service.asset_root.parent / 'archives')
    monkeypatch.setattr(document_runtime, '_publication', None)
    manager = backup.get_backup_manager()
    assert manager._publication() is None
    monkeypatch.setattr(document_runtime, '_publication', service)
    publish(service)
    assert manager is backup.get_backup_manager()
    result = manager.create_backup()
    assert result.status == 'completed'
    assert 'publication' in result.manifest.directories
    assert 'vectordb' not in result.manifest.directories
    assert manager.verify(result.backup_id)['valid'] is True

def test_manager_never_publishes_archive_after_asset_failure(service):
    publish(service)
    (service.asset_root / 'one.txt').write_text('changed')
    manager = BackupManager(service.asset_root.parent / 'archives', publication=service)
    result = manager.create_backup()
    assert result.status == 'failed'
    assert list(manager.base_dir.iterdir()) == []


@pytest.mark.parametrize('operation', ['verify', 'restore'])
def test_unregistered_wal_cannot_hide_invalid_sealed_main(service, operation):
    publish(service)
    root = service.asset_root.parent
    snapshot = root / 'backup'
    backup = backup_type()(service)
    backup.create(snapshot)
    database = snapshot / 'database' / 'vectors.sqlite'
    connection = connect(database)
    try:
        connection.execute('PRAGMA wal_autocheckpoint=0')
        connection.execute('UPDATE documents SET active_revision=999')
        connection.commit()
        assert connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0] == 0
        # Only the unregistered WAL repairs the deliberately invalid main file.
        connection.execute('UPDATE documents SET active_revision=1')
        connection.commit()
        wal = Path(str(database) + '-wal')
        assert wal.stat().st_size > 0
        manifest_path = snapshot / 'publication.json'
        manifest = json.loads(manifest_path.read_text())
        raw = database.read_bytes()
        manifest['database'] = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
        manifest_path.write_text(json.dumps(manifest))
        before_wal = wal.read_bytes()
        with pytest.raises(ValueError, match='catalog_integrity'):
            if operation == 'verify':
                backup.verify(snapshot)
            else:
                backup.restore(snapshot, root / 'restored')
        assert not (root / 'restored').exists()
        assert database.read_bytes() == raw
        assert wal.read_bytes() == before_wal
    finally:
        connection.close()


def test_restore_validates_catalog_after_staging_before_activation(service, monkeypatch):
    publish(service)
    root = service.asset_root.parent
    backup = backup_type()(service)
    snapshot = root / 'backup'
    backup.create(snapshot)
    original = backup._copy_asset
    damaged = []

    def damage_staged_catalog(source, target, expected):
        size = original(source, target, expected)
        if target.name == 'vectors.sqlite':
            connection = connect(target)
            try:
                connection.execute('UPDATE documents SET active_revision=999')
                connection.commit()
            finally:
                connection.close()
            damaged.append(target)
        return size

    monkeypatch.setattr(backup, '_copy_asset', damage_staged_catalog)
    with pytest.raises(ValueError, match='catalog_integrity'):
        backup.restore(snapshot, root / 'restored')
    assert len(damaged) == 1
    assert not (root / 'restored').exists()


def test_valid_sealed_main_ignores_adjacent_unregistered_wal(service):
    publish(service)
    root = service.asset_root.parent
    snapshot = root / 'backup'
    backup = backup_type()(service)
    backup.create(snapshot)
    database = snapshot / 'database' / 'vectors.sqlite'
    raw = database.read_bytes()
    connection = connect(database)
    try:
        connection.execute('PRAGMA wal_autocheckpoint=0')
        connection.execute('UPDATE documents SET active_revision=999')
        connection.commit()
        wal = Path(str(database) + '-wal')
        assert wal.stat().st_size > 0
        assert database.read_bytes() == raw
        before_wal = wal.read_bytes()
        backup.verify(snapshot)
        restored = backup.restore(snapshot, root / 'restored')
        assert database.read_bytes() == raw
        assert wal.read_bytes() == before_wal
        with closing(connect(restored / 'database' / 'vectors.sqlite', True)) as checked:
            assert checked.execute('SELECT active_revision FROM documents').fetchone() == (1,)
            assert checked.execute('SELECT count(*) FROM document_pins').fetchone() == (0,)
    finally:
        connection.close()
