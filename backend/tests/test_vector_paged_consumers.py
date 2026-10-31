"""Production pagination consumers against real disk SQLite pages."""
import sqlite3
from contextlib import closing

import pytest

from doc_processor import Chunk
from index_registry import build_bm25_from_chunks


def test_bm25_retains_single_pass_chunks_after_tokenization():
    chunks = (Chunk(str(i), f'alpha item{i}', 'text') for i in range(137))
    index, retained = build_bm25_from_chunks(chunks)
    assert isinstance(retained, list)
    assert [c.chunk_id for c in retained] == [str(i) for i in range(137)]
    assert len(index.get_scores(['alpha'])) == 137


class SQLitePages:
    def __init__(self, path):
        self.path = path
        self.closed = False
        self.pages = 0
        self._collection = self
        with closing(sqlite3.connect(path)) as conn, conn:
            conn.execute('CREATE TABLE items(id INTEGER PRIMARY KEY,text TEXT)')
            conn.executemany('INSERT INTO items VALUES (?,?)', [(i, f'alpha item{i}') for i in range(137)])

    def get(self, **kwargs):
        raise AssertionError('full get must not run')

    def iter_record_pages(self, page_size=256):
        try:
            with closing(sqlite3.connect(self.path)) as conn:
                conn.execute('BEGIN')
                cursor = conn.execute('SELECT id,text FROM items ORDER BY id')
                while rows := cursor.fetchmany(min(17, page_size)):
                    self.pages += 1
                    yield {'ids': [str(r[0]) for r in rows], 'documents': [r[1] for r in rows],
                           'metadatas': [{'content_type': 'text', 'source_file': 'same.docx',
                                          'document_id': 'authorized', 'document_version': 3} for _ in rows]}
        finally:
            self.closed = True


@pytest.mark.parametrize('entry', ['rag', 'build', 'eval'])
def test_all_consumers_keep_last_page_and_close(tmp_path, monkeypatch, entry):
    import index_registry
    monkeypatch.setattr(index_registry, 'BM25_ARTIFACT_PATH', tmp_path / 'bm25.json')
    monkeypatch.setattr(index_registry, 'TABLE_ARTIFACT_PATH', tmp_path / 'table.json')
    store = SQLitePages(tmp_path / 'pages.sqlite')
    if entry == 'rag':
        from routes.rag_query import _build_bm25_index_from_vector_store
        bm25 = _build_bm25_index_from_vector_store(store)
    elif entry == 'build':
        from build_indices import build_indices
        bm25, _ = build_indices(store)
    else:
        from run_evaluation import build_optional_indices
        bm25, _ = build_optional_indices(store)
    assert store.closed
    assert store.pages == 9
    assert len(bm25[1]) == 137
    assert bm25[1][-1].chunk_id == '136'
    from index_registry import _tokenize_for_bm25
    scores = bm25[0].get_scores(_tokenize_for_bm25('item136'))
    assert bm25[1][int(scores.argmax())].chunk_id == '136'


def test_page_iterator_early_close_and_trusted_metadata(tmp_path):
    from paged_chunks import iter_store_chunks
    store = SQLitePages(tmp_path / 'pages.sqlite')
    chunks = iter_store_chunks(store)
    first = next(chunks)
    chunks.close()
    assert store.closed
    assert first.metadata.document_id == 'authorized'
    assert first.metadata.document_version == 3


def test_bad_page_columns_fail_instead_of_silent_truncation():
    from paged_chunks import iter_store_chunks
    class BadPages:
        def iter_record_pages(self, page_size):
            yield {'ids': ['one'], 'documents': [], 'metadatas': [{}]}
    with pytest.raises(ValueError):
        list(iter_store_chunks(BadPages()))


@pytest.mark.parametrize('entry', ['build', 'eval'])
def test_local_consumers_preserve_global_indexes_and_artifacts(tmp_path, monkeypatch, entry):
    import index_registry
    from build_indices import build_indices
    from run_evaluation import build_optional_indices
    bm25_path = tmp_path / 'bm25.json'
    table_path = tmp_path / 'table.json'
    bm25_path.write_bytes(b'previous bm25')
    table_path.write_bytes(b'previous table')
    monkeypatch.setattr(index_registry, 'BM25_ARTIFACT_PATH', bm25_path)
    monkeypatch.setattr(index_registry, 'TABLE_ARTIFACT_PATH', table_path)
    old_bm25, old_table = object(), object()
    monkeypatch.setattr(index_registry, '_bm25_index', old_bm25)
    monkeypatch.setattr(index_registry, '_table_index', old_table)
    store = SQLitePages(tmp_path / 'pages.sqlite')
    build = build_indices if entry == 'build' else build_optional_indices
    bm25, table = build(store)
    assert len(bm25[1]) == 137 and bm25[1][-1].chunk_id == '136'
    assert index_registry.get_bm25_index() is old_bm25
    assert index_registry.get_table_index() is old_table
    assert bm25_path.read_bytes() == b'previous bm25'
    assert table_path.read_bytes() == b'previous table'
    assert store.closed


@pytest.mark.parametrize('entry', ['build', 'eval'])
def test_consumers_close_page_snapshot_when_tokenization_fails(tmp_path, monkeypatch, entry):
    import index_registry
    from build_indices import build_indices
    from run_evaluation import build_optional_indices
    def fail(text):
        raise RuntimeError('tokenization failed')
    monkeypatch.setattr(index_registry, '_tokenize_for_bm25', fail)
    store = SQLitePages(tmp_path / 'pages.sqlite')
    build = build_indices if entry == 'build' else build_optional_indices
    with pytest.raises(RuntimeError, match='tokenization failed'):
        build(store)
    assert store.closed


def test_page_conversion_error_closes_underlying_snapshot():
    from paged_chunks import iter_store_chunks
    closed = []
    class BadMetadata:
        def iter_record_pages(self, page_size):
            try:
                yield {'ids': ['one'], 'documents': ['table'],
                       'metadatas': [{'table_json': 'invalid json'}]}
            finally:
                closed.append(True)
    with pytest.raises(ValueError):
        list(iter_store_chunks(BadMetadata()))
    assert closed == [True]
