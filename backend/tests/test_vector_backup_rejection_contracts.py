"""Real sealed archive corruption never activates a restore or mutates originals."""
from contextlib import closing
import hashlib
import json

import pytest

from backend.tests.test_vector_publication_backup import PROFILE, service, publish, backup_type
from vector_runtime import connect


def tree_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file()}


def save_manifest(snapshot, manifest):
    (snapshot / 'publication.json').write_text(json.dumps(manifest), encoding='utf-8')


@pytest.mark.parametrize('damage', [
    'format', 'assets_type', 'model', 'root_type', 'root_relative',
    'asset_type', 'present_type', 'duplicate', 'unregistered', 'sha',
    'size', 'missing_entry', 'required_absent', 'database_receipt',
])
@pytest.mark.parametrize('operation', ['verify', 'restore'])
def test_manifest_damage_rejected_without_archive_or_live_changes(service, damage, operation):
    publish(service)
    root = service.asset_root.parent
    snapshot, target = root / 'snapshot', root / 'restored'
    backup = backup_type()(service)
    backup.create(snapshot)
    manifest = json.loads((snapshot / 'publication.json').read_text(encoding='utf-8'))
    if damage == 'format': manifest['format'] = 2
    elif damage == 'assets_type': manifest['assets'] = {}
    elif damage == 'model': manifest['model_profile'] = {**PROFILE, 'dimension': 3}
    elif damage == 'root_type': manifest['source_asset_root'] = None
    elif damage == 'root_relative': manifest['source_asset_root'] = 'relative/assets'
    elif damage == 'asset_type': manifest['assets'] = ['one.txt']
    elif damage == 'present_type': manifest['assets'][0]['present'] = 1
    elif damage == 'duplicate': manifest['assets'].append(dict(manifest['assets'][0]))
    elif damage == 'unregistered': manifest['assets'][0]['path'] = 'unregistered.txt'
    elif damage == 'sha': manifest['assets'][0]['sha256'] = '0' * 64
    elif damage == 'size': manifest['assets'][0]['size'] += 1
    elif damage == 'missing_entry': manifest['assets'] = []
    elif damage == 'required_absent':
        manifest['assets'][0]['present'] = False
        (snapshot / 'assets' / 'one.txt').unlink()
    elif damage == 'database_receipt': manifest['database']['size'] += 1
    save_manifest(snapshot, manifest)
    archive_before, asset_before = tree_bytes(snapshot), tree_bytes(service.asset_root)
    with pytest.raises(ValueError, match='backup_(manifest|asset|database)'):
        if operation == 'verify': backup.verify(snapshot)
        else: backup.restore(snapshot, target)
    assert tree_bytes(snapshot) == archive_before
    assert tree_bytes(service.asset_root) == asset_before
    assert not target.exists()
    assert not list(root.glob('.restore-*'))
    assert [r['text'] for r in service.search([1, 0], allowed_document_ids={'doc'})] == ['v1']


@pytest.mark.parametrize('sql,params', [
    ('UPDATE documents SET identity_json=?', ('[]',)),
    ('UPDATE documents SET identity_json=?', ('{}',)),
    ('UPDATE documents SET deleted=?', (2,)),
    ('UPDATE documents SET active_revision=?', (0,)),
    ('UPDATE document_revisions SET metadata_json=?', ('[]',)),
    ('UPDATE document_tasks SET task_id=?', ('wrong-task',)),
    ('UPDATE document_tasks SET status=?', ('unknown',)),
    ('UPDATE document_tasks SET status=?', ('prepared',)),
    ('DELETE FROM document_tasks', ()),
    ('UPDATE collections SET dimension=?', (3,)),
])
def test_catalog_relationship_corruption_rejected_even_with_updated_db_digest(service, sql, params):
    publish(service)
    root = service.asset_root.parent
    snapshot, target = root / 'snapshot', root / 'restored'
    backup = backup_type()(service)
    backup.create(snapshot)
    database = snapshot / 'database' / 'vectors.sqlite'
    with closing(connect(database)) as connection:
        connection.execute(sql, params)
        connection.commit()
    raw = database.read_bytes()
    manifest = json.loads((snapshot / 'publication.json').read_text(encoding='utf-8'))
    manifest['database'] = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
    save_manifest(snapshot, manifest)
    before = tree_bytes(snapshot)
    with pytest.raises(ValueError, match='backup_catalog_integrity'):
        backup.restore(snapshot, target)
    assert tree_bytes(snapshot) == before
    assert not target.exists()
    assert not list(root.glob('.restore-*'))
    assert [r['text'] for r in service.search([1, 0], allowed_document_ids={'doc'})] == ['v1']


@pytest.mark.parametrize('assets', [
    {}, [None], [{'path': 'one.txt', 'sha256': 1}],
    [{'path': 'one.txt', 'sha256': 'short'}],
    [{'path': 'one.txt', 'sha256': 'G' * 64}],
    [{'path': '../outside', 'sha256': '0' * 64}],
])
def test_invalid_catalog_asset_registration_never_seals_and_releases_pins(service, assets):
    publish(service)
    with service.catalog() as catalog:
        with catalog._write():
            catalog.connection.execute('UPDATE document_revisions SET assets_json=?', (json.dumps(assets),))
    destination = service.asset_root.parent / 'snapshot'
    before = tree_bytes(service.asset_root)
    with pytest.raises(ValueError, match='(invalid_backup_manifest|unsafe_backup_asset)'):
        backup_type()(service).create(destination)
    assert not destination.exists()
    assert tree_bytes(service.asset_root) == before
    assert not list(destination.parent.glob('.publication-*'))
    with service.catalog() as catalog:
        assert catalog.connection.execute('SELECT count(*) FROM document_pins').fetchone() == (0,)


def test_two_revisions_cannot_register_conflicting_hash_for_same_asset(service):
    publish(service)
    publish(service, task='two', expected=1, text='v2')
    with service.catalog() as catalog:
        with catalog._write():
            catalog.connection.execute('UPDATE document_revisions SET assets_json=? WHERE revision=2',
                                       (json.dumps([{'path': 'one.txt', 'sha256': '0' * 64}]),))
    target = service.asset_root.parent / 'snapshot'
    with pytest.raises(ValueError, match='conflicting_backup_asset'):
        backup_type()(service).create(target)
    assert not target.exists()
    with service.catalog() as catalog:
        assert catalog.connection.execute('SELECT count(*) FROM document_pins').fetchone() == (0,)


def test_missing_required_live_asset_cannot_seal_backup(service):
    publish(service)
    (service.asset_root / 'one.txt').unlink()
    target = service.asset_root.parent / 'snapshot'
    with pytest.raises(ValueError, match='backup_asset_missing'):
        backup_type()(service).create(target)
    assert not target.exists()
    with service.catalog() as catalog:
        assert catalog.connection.execute('SELECT count(*) FROM document_pins').fetchone() == (0,)


def test_create_preserves_existing_destination(service):
    publish(service)
    target = service.asset_root.parent / 'snapshot'
    target.mkdir()
    (target / 'sentinel').write_bytes(b'existing archive')
    with pytest.raises(FileExistsError, match='backup_target_exists'):
        backup_type()(service).create(target)
    assert tree_bytes(target) == {'sentinel': b'existing archive'}


def test_deleted_optional_asset_declared_absent_must_really_be_absent(service):
    publish(service)
    with service.catalog() as catalog:
        catalog.delete('doc')
    root = service.asset_root.parent
    snapshot = root / 'snapshot'
    backup = backup_type()(service)
    backup.create(snapshot)
    manifest = json.loads((snapshot / 'publication.json').read_text(encoding='utf-8'))
    manifest['assets'][0]['present'] = False
    save_manifest(snapshot, manifest)
    before = tree_bytes(snapshot)
    with pytest.raises(ValueError, match='backup_asset_missing'):
        backup.restore(snapshot, root / 'restored')
    assert tree_bytes(snapshot) == before
    assert not (root / 'restored').exists()


def test_empty_publication_roundtrip_has_no_phantom_documents_or_assets(service):
    root = service.asset_root.parent
    backup = backup_type()(service)
    manifest = backup.create(root / 'snapshot')
    assert manifest['assets'] == []
    target = backup.restore(root / 'snapshot', root / 'restored')
    with closing(connect(target / 'database' / 'vectors.sqlite', True)) as connection:
        for table in ('documents', 'document_revisions', 'document_tasks', 'document_pins'):
            assert connection.execute(f'SELECT count(*) FROM {table}').fetchone() == (0,)
    assert tree_bytes(target / 'assets') == {}
