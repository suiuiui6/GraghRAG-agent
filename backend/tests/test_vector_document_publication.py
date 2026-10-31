"""Real SQLite catalog invariants; runtime admission is tested separately."""
import json
import sqlite3
import subprocess
import sys

import pytest

from services.document_catalog import DocumentCatalog, CatalogConflict, CatalogNotFound
from services.document_catalog_schema import install_catalog_schema


@pytest.fixture
def catalog(tmp_path):
    path = tmp_path / 'catalog.sqlite'
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute('PRAGMA foreign_keys=ON')
    install_catalog_schema(conn)
    instance = DocumentCatalog(conn, tmp_path)
    yield instance
    conn.close()


def prepare(catalog, task='task1', document='doc1', expected=None, text='v1'):
    asset = catalog.asset_root / (task + '.txt')
    asset.write_text(text, encoding='utf-8')
    import hashlib
    assets = [{'path': asset.name, 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}]
    return catalog.prepare(task, document, {'owner_id': 'a', 'filename': 'same.docx'},
                           expected_revision=expected, model_profile={'model': 'fixed', 'dimension': 2},
                           assets=assets, collection_name='revision_' + task)


def test_prepared_document_is_invisible_until_commit(catalog):
    prepare(catalog)
    assert catalog.visible_documents() == []
    result = catalog.commit('task1')
    assert result['active_revision'] == 1
    assert [d['document_id'] for d in catalog.visible_documents()] == ['doc1']
    assert catalog.task_receipt('task1')['status'] == 'done'


def test_same_task_replay_is_exactly_once(catalog):
    prepare(catalog)
    first = catalog.commit('task1')
    prepare(catalog)
    assert catalog.commit('task1') == first
    assert len(catalog.revisions('doc1')) == 1


def test_task_cannot_be_rebound_to_different_document(catalog):
    prepare(catalog)
    with pytest.raises(CatalogConflict):
        prepare(catalog, document='doc2')


def test_failed_asset_hash_preserves_old_active(catalog):
    prepare(catalog)
    catalog.commit('task1')
    prepare(catalog, 'task2', expected=1, text='v2')
    (catalog.asset_root / 'task2.txt').write_text('corrupt')
    with pytest.raises(CatalogConflict, match='asset_integrity'):
        catalog.commit('task2')
    assert catalog.visible_documents()[0]['active_revision'] == 1


def test_compare_and_swap_rejects_second_concurrent_update(catalog):
    prepare(catalog)
    catalog.commit('task1')
    prepare(catalog, 'task2', expected=1, text='v2')
    prepare(catalog, 'task3', expected=1, text='v3')
    catalog.commit('task2')
    with pytest.raises(CatalogConflict, match='revision_conflict'):
        catalog.commit('task3')
    assert catalog.task_receipt('task3')['error_code'] == 'revision_conflict'
    assert catalog.visible_documents()[0]['active_revision'] == 2


def test_update_inherits_identity_instead_of_accepting_new_owner(catalog):
    prepare(catalog)
    catalog.commit('task1')
    import hashlib
    asset = catalog.asset_root / 'task2.txt'
    asset.write_text('new text')
    catalog.prepare('task2', 'doc1', {'owner_id': 'b'}, expected_revision=1,
                    assets=[{'path': asset.name, 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}],
                    model_profile={'model': 'fixed', 'dimension': 2}, collection_name='revision_task2')
    doc = catalog.commit('task2')
    assert doc['owner_id'] == 'a'


def test_tombstone_blocks_prepared_task_and_legacy_fallback(catalog):
    prepare(catalog)
    catalog.commit('task1')
    prepare(catalog, 'task2', expected=1)
    deletion = catalog.delete('doc1')
    assert deletion['cleanup_pending'] is True
    assert catalog.visible_documents([{'document_id': 'doc1', 'owner_id': 'a'}]) == []
    with pytest.raises(CatalogNotFound):
        catalog.commit('task2')


def test_legacy_only_delete_survives_reopen(catalog):
    legacy = {'document_id': 'old', 'owner_id': 'a', 'filename': 'old.pdf'}
    catalog.delete('old', legacy=legacy)
    other = sqlite3.connect(catalog.connection.execute('PRAGMA database_list').fetchone()[2], isolation_level=None)
    try:
        restored = DocumentCatalog(other, catalog.asset_root)
        assert restored.visible_documents([legacy]) == []
        with pytest.raises(CatalogNotFound):
            restored.get_active('old')
    finally:
        other.close()


def test_bad_asset_path_does_not_block_logical_delete(catalog, tmp_path):
    prepare(catalog)
    catalog.commit('task1')
    catalog.connection.execute("UPDATE document_revisions SET assets_json=?", (json.dumps([{'path': '../escape', 'sha256': '0'*64}]),))
    result = catalog.delete('doc1')
    assert result['cleanup_status'] == 'blocked'
    assert catalog.visible_documents() == []


def test_pin_defers_physical_cleanup(catalog):
    prepare(catalog)
    catalog.commit('task1')
    with catalog.pin('doc1', 1):
        catalog.delete('doc1')
        assert catalog.cleanup('doc1')['cleanup_pending'] is True
        assert (catalog.asset_root / 'task1.txt').exists()
    assert catalog.cleanup('doc1')['cleanup_pending'] is False
    assert not (catalog.asset_root / 'task1.txt').exists()


def test_revoke_callback_runs_before_commit_and_failure_rolls_back(catalog):
    prepare(catalog)
    def reject(doc):
        raise PermissionError('revoked')
    with pytest.raises(PermissionError):
        catalog.commit('task1', authorize=reject)
    assert catalog.visible_documents() == []
    assert catalog.task_receipt('task1')['status'] == 'prepared'


def test_same_name_is_not_document_identity(catalog):
    prepare(catalog)
    catalog.commit('task1')
    prepare(catalog, 'task2', 'doc2')
    catalog.commit('task2')
    assert {d['document_id'] for d in catalog.visible_documents()} == {'doc1', 'doc2'}
    catalog.delete('doc1')
    assert [d['document_id'] for d in catalog.visible_documents()] == ['doc2']


def test_legacy_update_has_explicit_migration_error(catalog):
    with pytest.raises(CatalogConflict, match='migration_required'):
        catalog.require_revision({'document_id': 'old'}, 1)


def test_source_snapshot_is_shared_real_transaction(catalog):
    prepare(catalog)
    catalog.commit('task1')
    with catalog.read_snapshot() as snapshot:
        assert snapshot.connection is catalog.connection
        assert snapshot.documents[0]['active_revision'] == 1
        with pytest.raises(CatalogConflict, match='transaction_active'):
            prepare(catalog, 'task2', expected=1)


def test_actual_two_connection_update_preserves_consistent_snapshot(catalog):
    catalog.connection.execute('PRAGMA journal_mode=WAL')
    prepare(catalog)
    catalog.commit('task1')
    path = catalog.connection.execute('PRAGMA database_list').fetchone()[2]
    other = sqlite3.connect(path, isolation_level=None)
    other.execute('PRAGMA foreign_keys=ON')
    publisher = DocumentCatalog(other, catalog.asset_root)
    try:
        with catalog.read_snapshot() as snapshot:
            prepare(publisher, 'task2', expected=1)
            publisher.commit('task2')
            assert snapshot.documents[0]['active_revision'] == 1
            assert catalog.get_active('doc1')['active_revision'] == 1
        assert catalog.get_active('doc1')['active_revision'] == 2
    finally:
        other.close()


def test_failed_publication_callback_rolls_back_directory(catalog):
    prepare(catalog)
    def fail(connection, receipt):
        connection.execute('UPDATE document_catalog_state SET generation=99')
        raise OSError('disk failure')
    with pytest.raises(OSError):
        catalog.commit('task1', publish_vectors=fail)
    assert catalog.generation() == 0
    assert catalog.visible_documents() == []
    assert catalog.task_receipt('task1')['status'] == 'prepared'


def test_real_symlink_cleanup_never_changes_target(catalog, tmp_path):
    prepare(catalog)
    catalog.commit('task1')
    target = tmp_path / 'outside.txt'
    target.write_text('do not delete')
    alias = tmp_path / 'link.txt'
    alias.symlink_to(target)
    catalog.connection.execute('UPDATE document_revisions SET assets_json=?', (json.dumps([{'path': alias.name, 'sha256': '0'*64}]),))
    assert catalog.delete('doc1')['cleanup_status'] == 'blocked'
    assert target.read_text() == 'do not delete'
    assert catalog.cleanup('doc1')['cleanup_pending'] is True
    assert target.read_text() == 'do not delete'


def test_unknown_delete_has_no_side_effect(catalog):
    prepare(catalog)
    catalog.commit('task1')
    before = catalog.generation()
    with pytest.raises(CatalogNotFound):
        catalog.delete('unknown')
    assert catalog.generation() == before
    assert catalog.get_active('doc1')['active_revision'] == 1


def test_process_crash_before_commit_rolls_back_active_revision(catalog):
    prepare(catalog)
    catalog.commit('task1')
    path = catalog.connection.execute('PRAGMA database_list').fetchone()[2]
    script = "import sqlite3,sys,os;c=sqlite3.connect(sys.argv[1]);c.execute('BEGIN IMMEDIATE');c.execute('UPDATE documents SET active_revision=77');os._exit(0)"
    result = subprocess.run([sys.executable, '-B', '-c', script, path], capture_output=True, timeout=15)
    assert result.returncode == 0
    assert catalog.get_active('doc1')['active_revision'] == 1


def test_child_commit_receipt_survives_abrupt_process_exit(catalog):
    prepare(catalog)
    path = catalog.connection.execute('PRAGMA database_list').fetchone()[2]
    script = "import sqlite3,sys,os;from services.document_catalog import DocumentCatalog;c=sqlite3.connect(sys.argv[1],isolation_level=None);DocumentCatalog(c,sys.argv[2]).commit('task1');os._exit(0)"
    result = subprocess.run([sys.executable, '-B', '-c', script, path, str(catalog.asset_root)], capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr.decode()
    assert catalog.get_active('doc1')['active_revision'] == 1
    assert catalog.task_receipt('task1')['status'] == 'done'


def test_dead_process_pin_recovers_without_deleting_live_reader(catalog):
    prepare(catalog)
    catalog.commit('task1')
    path = catalog.connection.execute('PRAGMA database_list').fetchone()[2]
    script = "import sqlite3,sys,time;from services.document_catalog import DocumentCatalog;c=sqlite3.connect(sys.argv[1],isolation_level=None);cat=DocumentCatalog(c,sys.argv[2]);\nwith cat.pin('doc1',1):\n print('pinned',flush=True)\n time.sleep(30)"
    child = subprocess.Popen([sys.executable, '-B', '-c', script, path, str(catalog.asset_root)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == 'pinned'
        catalog.delete('doc1')
        assert catalog.cleanup('doc1')['cleanup_pending'] is True
        assert (catalog.asset_root / 'task1.txt').exists()
    finally:
        child.terminate()
        child.communicate(timeout=10)
    assert catalog.cleanup('doc1')['cleanup_pending'] is False
    assert catalog.connection.execute('SELECT COUNT(*) FROM document_pins').fetchone()[0] == 0


def test_corrupt_asset_manifest_still_allows_logical_revocation(catalog):
    prepare(catalog)
    catalog.commit('task1')
    catalog.connection.execute("UPDATE document_revisions SET assets_json='not-json'")
    assert catalog.delete('doc1')['cleanup_status'] == 'blocked'
    assert catalog.visible_documents() == []
    assert (catalog.asset_root / 'task1.txt').exists()


def test_shared_asset_allows_multiple_readers_in_same_snapshot(catalog):
    prepare(catalog)
    catalog.commit('task1')
    assets_json, model_json = catalog.connection.execute('SELECT assets_json,model_json FROM document_revisions WHERE task_id=?', ('task1',)).fetchone()
    catalog.prepare('task2', 'doc2', {'owner_id': 'a'}, expected_revision=None,
                    assets=json.loads(assets_json), model_profile=json.loads(model_json), collection_name='revision_task2')
    catalog.commit('task2')
    with catalog.read_snapshot() as snapshot:
        assert {doc['document_id'] for doc in snapshot.documents} == {'doc1', 'doc2'}
        assert catalog.connection.execute('SELECT COUNT(*) FROM document_pins').fetchone()[0] == 2


def test_active_revision_exposes_new_assets_metadata_but_retains_owner(catalog):
    prepare(catalog)
    catalog.commit('task1')
    import hashlib
    asset = catalog.asset_root / 'v2-original.docx'
    asset.write_text('v2')
    catalog.prepare('task2', 'doc1', {'owner_id': 'spoofed', 'filename': 'renamed.docx',
                                    'filepath': str(asset), 'kg_nodes': 99}, expected_revision=1,
                    assets=[{'path': asset.name, 'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}],
                    model_profile={'model': 'fixed', 'dimension': 2}, collection_name='revision_task2')
    updated = catalog.commit('task2')
    assert updated['filename'] == 'renamed.docx'
    assert updated['filepath'] == str(asset)
    assert updated['kg_nodes'] == 99
    assert updated['owner_id'] == 'a'
