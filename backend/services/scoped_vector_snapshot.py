"""Sequential recall over one caller-owned authorized SQLite snapshot.

No global index registry writes or worker threads: SQLite ownership and the
adapter's request-local collection scope stay on the calling thread.
"""
from __future__ import annotations

import json
from contextlib import ExitStack

from paged_chunks import iter_store_chunks


class ScopedVectorSnapshot:
    def __init__(self, store, snapshot, *, page_size=256, asset_root=None):
        self.asset_root = asset_root
        self.store = store
        self.connection = snapshot.connection
        self.documents = snapshot.documents
        self.generation = snapshot.generation
        self.versions = {doc['document_id']: doc['active_revision'] for doc in self.documents}
        self.page_size = page_size

    def retrieve(self, query, *, enabled_sources, query_vector=None, top_k=20,
                 per_source_caps=None, table_conditions=None):
        from index_registry import build_bm25_from_chunks
        from retrieval import RetrievalConfig, _bm25_recall
        sources = set(enabled_sources)
        if sources - {'vector', 'bm25', 'table', 'kg'}:
            raise ValueError('Unsupported scoped retrieval source')
        if not self.documents or top_k <= 0:
            return []
        caps = per_source_caps or {}
        paths = []
        if 'vector' in sources:
            if query_vector is None:
                raise ValueError('Vector query required')
            rows = self.store.search(query_vector, top_k=min(top_k, caps.get('vector', top_k)))
            paths.append([{**row, 'source': 'vector'} for row in rows])
        if 'kg' in sources:
            from services.document_snapshot import contained_asset, _graph_from_directory
            from retrieval import _kg_recall, preprocess_query
            limit = min(top_k, caps.get('kg', top_k))
            rows = []
            for document in self.documents:
                if not document.get('kg_path'):
                    continue
                directory = contained_asset(document['kg_path'], self.asset_root)
                manifest = {asset['path']: asset['sha256'] for asset in document['assets']}
                graph = _graph_from_directory(document, directory, self.asset_root,
                                              document['active_revision'], manifest=manifest)
                graph = graph.subgraph([nid for nid, data in graph.nodes(data=True)
                                       if data.get('grounding_status') == 'grounded']).copy()
                hits = _kg_recall(preprocess_query(query), graph, RetrievalConfig(kg_top_k=limit))
                for row in hits:
                    row['metadata'] = {**row.get('metadata', {}),
                                       'document_id': document['document_id'],
                                       'document_version': document['active_revision']}
                rows.extend(hits)
            paths.append(sorted(rows, key=lambda row: -row['score'])[:limit])
        if sources & {'bm25', 'table'}:
            chunks = list(iter_store_chunks(self.store, page_size=self.page_size))
            metadata = {chunk.chunk_id: vars(chunk.metadata) for chunk in chunks}
            if 'bm25' in sources:
                index = build_bm25_from_chunks(chunks)
                if chunks and index is None:
                    raise RuntimeError('BM25 dependency unavailable')
                rows = _bm25_recall(query, index, RetrievalConfig(bm25_top_k=min(top_k, caps.get('bm25', top_k)))) if index else []
                paths.append([{**row, 'metadata': dict(metadata[row['chunk_id']])} for row in rows])
            if 'table' in sources:
                from table_index import TableIndex
                limit = min(top_k, caps.get('table', top_k))
                rows = []
                # Each table owns its source identity, including wide-table rows
                # whose generic TableIndex projection omits the source filename.
                for chunk in chunks:
                    if not chunk.table_json or chunk.content_type not in {'table', 'mixed'}:
                        continue
                    with ExitStack() as stack:
                        table = TableIndex()
                        stack.callback(table.conn.close)
                        table.ingest_chunks([chunk])
                        for position, row in enumerate(table.query(conditions=table_conditions, top_k=limit)):
                            rows.append({'chunk_id': f'{chunk.chunk_id}:table:{position}',
                                         'text': json.dumps(row, ensure_ascii=False), 'score': .8,
                                         'source': 'table', 'metadata': dict(metadata[chunk.chunk_id])})
                paths.append(rows[:limit])
        if len(paths) == 1:
            return paths[0][:top_k]
        # Reciprocal-rank fusion avoids comparing unrelated cosine/BM25 scales.
        merged = {}
        for rows in paths:
            for rank, row in enumerate(rows, 1):
                key = row['chunk_id']
                if key not in merged:
                    merged[key] = {**row, 'score': 0.0}
                merged[key]['score'] += 1.0 / (60 + rank)
        return sorted(merged.values(), key=lambda row: -row['score'])[:top_k]
