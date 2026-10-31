"""真实 SQLite 生产存储门面专项；不代表完整生命周期验收。"""
import ast
from contextlib import closing
import importlib
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

class ProductionStorageTests(unittest.TestCase):
    def test_default_module_does_not_import_chroma(self):
        imported = []
        import builtins
        original = builtins.__import__
        def observe(name, *args, **kwargs):
            imported.append(name)
            return original(name, *args, **kwargs)
        sys.modules.pop('vector_store', None)
        with patch.object(builtins, '__import__', observe):
            importlib.import_module('vector_store')
        self.assertFalse(any(name.startswith('chromadb') for name in imported), '默认生产门面仍尝试导入 Chroma')

    def test_default_factory_gate_leaves_no_empty_database(self):
        import vector_store as vs
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'production'
            try:
                vs.create_vector_store(persist_dir=str(target))
            except Exception as exc:
                self.assertEqual(getattr(exc, 'code', None), 'compatibility_not_approved')
            else:
                self.fail('兼容准入尚未关闭，默认工厂必须拒绝启动')
            self.assertFalse(target.exists())

    def test_direct_constructor_has_same_admission_gate(self):
        import vector_store as vs
        with tempfile.TemporaryDirectory() as directory:
            try:
                vs.VectorStore(persist_dir=str(Path(directory) / 'production'))
            except Exception as exc:
                self.assertEqual(getattr(exc, 'code', None), 'compatibility_not_approved')
            else:
                self.fail('直接构造不得绕过准入')

if __name__ == '__main__':
    unittest.main()

class RuntimeAndSchemaTests(unittest.TestCase):
    def setUp(self):
        import vector_store as vs
        self.vs = vs
        self.assertTrue(hasattr(vs, 'SyntheticIntegrationConfig'), '缺少显式合成集成配置')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = vs.SyntheticIntegrationConfig.create(self.root)
    def store(self, **kwargs):
        return self.vs.VectorStore(persist_dir=str(self.root / 'vectors'), embedding_dim=2, embedding_model='synthetic/model-a@sha256:fixed', integration_config=self.config, **kwargs)
    def test_real_roundtrip_snapshot_and_reopen(self):
        s = self.store()
        s._collection.add(ids=['a','b'], embeddings=[[1.,0.],[0.,1.]], documents=['甲','乙'], metadatas=[{'source_file':'a','n':1},{'source_file':'b','n':2}])
        with s.read_snapshot() as connection:
            self.assertEqual(s.count(connection=connection), 2)
            s.delete_by_chunk_ids(['b'])
            self.assertEqual([i for p in s.iter_record_pages(1, connection=connection) for i in p['ids']], ['a','b'])
            self.assertEqual(len(s.search([1.,0.], connection=connection)), 2)
        self.assertEqual(self.store().count(), 1)
    def test_old_chroma_requires_migration_no_empty_database(self):
        directory = self.root / 'vectors'; directory.mkdir()
        (directory / 'chroma.sqlite3').write_bytes(b'legacy')
        with self.assertRaises(Exception) as caught: self.store()
        self.assertEqual(caught.exception.code, 'migration_required')
        self.assertFalse((directory / 'vectors.sqlite').exists())
    def test_runtime_version_and_hardening_fail_closed(self):
        import vector_runtime
        with patch.object(vector_runtime.sqlite3, 'sqlite_version_info', (3,45,3)):
            with self.assertRaises(Exception) as caught: self.store()
        self.assertEqual(caught.exception.code, 'runtime_unsupported')
        self.assertFalse((self.root/'vectors'/'vectors.sqlite').exists())
        with patch.object(vector_runtime, 'HARDENING_OPTIONS', ((-1, True),)):
            with self.assertRaises(Exception) as caught: self.store()
        self.assertEqual(caught.exception.code, 'runtime_hardening_failed')
    def test_dimension_model_and_schema_conflicts(self):
        s = self.store()
        with self.assertRaises(Exception) as caught: s._collection.add(ids=['bad'], embeddings=[[1.]])
        self.assertEqual(caught.exception.code, 'invalid_dimension')
        with self.assertRaises(Exception) as caught:
            self.vs.VectorStore(persist_dir=str(self.root/'vectors'), embedding_dim=3, embedding_model=s.embedding_model, integration_config=self.config)
        self.assertEqual(caught.exception.code, 'dimension_conflict')
        with self.assertRaises(Exception) as caught:
            self.vs.VectorStore(persist_dir=str(self.root/'vectors'), embedding_dim=2, embedding_model='other', integration_config=self.config)
        self.assertEqual(caught.exception.code, 'model_conflict')
        with closing(sqlite3.connect(s.path)) as connection, connection:
            connection.execute('CREATE TABLE arbitrary(data TEXT)')
        with self.assertRaises(Exception) as caught: self.store()
        self.assertEqual(caught.exception.code, 'schema_mismatch')
    def test_synthetic_scope_and_connection_cannot_escape(self):
        with self.assertRaises(Exception) as caught:
            self.vs.VectorStore(persist_dir=str(self.root.parent/'escape'), integration_config=self.config)
        self.assertEqual(caught.exception.code, 'compatibility_not_approved')
        s = self.store()
        with sqlite3.connect(':memory:') as connection:
            with self.assertRaises(Exception): s.search([1.,0.], connection=connection)
    def test_backup_restore_verifies_identity(self):
        s = self.store(); s._collection.add(ids=['a'], embeddings=[[1.,0.]])
        snapshot = self.root/'backup.sqlite'; identity=s.backup(snapshot)
        target = self.root/'restored'
        restored = self.vs.VectorStore.restore(snapshot,target,**identity,embedding_dim=2,embedding_model=s.embedding_model,integration_config=self.config)
        self.assertEqual(restored.count(),1)
        with self.assertRaises(Exception):
            self.vs.VectorStore.restore(snapshot,self.root/'bad',sha256='0'*64,size=identity['size'],embedding_dim=2,embedding_model=s.embedding_model,integration_config=self.config)
        self.assertFalse((self.root/'bad').exists())
