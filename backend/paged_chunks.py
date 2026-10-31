"""One snapshot page stream retaining source and document identity metadata."""
import json
from types import SimpleNamespace

from doc_processor import Chunk


def iter_store_chunks(store, page_size=256):
    pages_method = getattr(store, 'iter_record_pages', None)
    if callable(pages_method):
        pages = iter(pages_method(page_size=page_size))
    else:
        pages = iter((store._collection.get(include=['documents', 'metadatas']),))
    try:
        for page in pages:
            ids = page.get('ids') or []
            documents = page.get('documents') or []
            metadatas = page.get('metadatas') or []
            if len(ids) != len(documents) or len(ids) != len(metadatas):
                raise ValueError('Page column lengths differ')
            for chunk_id, text, raw in zip(ids, documents, metadatas):
                metadata = {'source_file': '', 'source_format': '', 'page_idx': None,
                            'section_path': [], 'entity_ids': [], 'entity_types': [], **(raw or {})}
                for key in ('section_path', 'entity_ids', 'entity_types'):
                    if isinstance(metadata[key], str):
                        try:
                            metadata[key] = json.loads(metadata[key])
                        except json.JSONDecodeError:
                            metadata[key] = []
                table_json = metadata.get('table_json')
                if isinstance(table_json, str):
                    table_json = json.loads(table_json)
                yield Chunk(chunk_id, text or '', metadata.get('content_type', 'text'),
                            table_json=table_json, metadata=SimpleNamespace(**metadata))
    finally:
        close = getattr(pages, 'close', None)
        if close is not None:
            close()
